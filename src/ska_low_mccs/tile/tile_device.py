# type: ignore
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""
SKA MCCS Tile Device Server.

The Tile Device represents the TANGO interface to a Tile (TPM) unit
"""
__all__ = ["MccsTile", "TilePowerManager", "main"]

import json
import numpy as np
import threading
import os.path

from tango import DebugIt, DevFailed, DevState, EnsureOmniThread, SerialModel, Util
from tango.server import attribute, command
from tango.server import device_property

from ska_tango_base import SKABaseDevice
from ska_tango_base.control_model import HealthState, SimulationMode, AdminMode
from ska_tango_base.commands import BaseCommand, ResponseCommand, ResultCode

from ska_low_mccs import MccsDeviceProxy
from ska_low_mccs.events import EventManager, EventSubscriptionHandler
from ska_low_mccs.hardware import ConnectionStatus, PowerMode
from ska_low_mccs.health import HealthModel
from ska_low_mccs.tile import TileHardwareManager
from ska_low_mccs.message_queue import MessageQueue


class TilePowerManager:
    """
    This class performs power management of the TPM on behalf of the MCCS Tile device.

    It has a simple job; all it needs to do is talk to the subrack that
    houses this TPM, to keep track of ensure that the TPM is
    supplied/denied power as required,
    """

    def __init__(self, subrack_fqdn, subrack_bay, logger, callback):
        """
        Initialise a new TilePowerManager.

        :param subrack_fqdn: FQDN of the subrack TANGO device that
            manages the subrack that houses this Tile device's TPM
        :type subrack_fqdn: str
        :param subrack_bay: then number of the subrack bay in which this
            Tile device's TPM is installed. We count from one, so a
            value of 1 means the TPM is installed in the first subrack
            bay
        :type subrack_bay: int
        :param logger: the logger to be used by this object.
        :type logger: :py:class:`logging.Logger`
        :param callback: to be called when the power mode changes
        :type callback: callable
        """
        self._subrack_fqdn = subrack_fqdn
        self._subrack = None
        self._subrack_bay = subrack_bay

        self._logger = logger
        self._callback = callback

        self._power_mode = PowerMode.UNKNOWN

    def connect(self):
        """
        Establish a connection to the subrack that powers this tile device's TPM.
        """
        self._subrack = MccsDeviceProxy(self._subrack_fqdn, self._logger)
        self._subrack.check_initialised()

        self._power_mode = self._read_power_mode()
        self._callback(self._power_mode)

        self.subrack_event_handler = EventSubscriptionHandler(
            self._subrack, "areTpmsOn", self._logger
        )
        self.subrack_event_handler.register_callback(self._subrack_power_changed)

    def off(self):
        """
        Turn off power to the TPM.

        :return: whether the command was successful or not, or None if
            there was nothing to do.
        :rtype: bool

        :raises NotImplementedError: if our call to PowerOffTpm gets a
            ResultCode other than OK or FAILED
        """
        if self._power_mode == PowerMode.OFF:
            return None  # already off

        [[result_code], [_]] = self._subrack.PowerOffTpm(self._subrack_bay)
        if result_code == ResultCode.OK:
            self._update_power_mode(PowerMode.OFF)
            return True
        elif result_code == ResultCode.FAILED:
            return False
        else:
            raise NotImplementedError(
                f"Subrack.PowerOffTpm returned unexpected ResultCode {result_code.name}."
            )

    def on(self):
        """
        Turn on power to the TPM.

        :return: whether the command was successful or not, or None if
            there was nothing to do.
        :rtype: bool

        :raises NotImplementedError: if our call to PowerOnTpm gets a
            ResultCode other than OK or FAILED
        """
        if self._power_mode == PowerMode.ON:
            return None  # already on

        [[result_code], [_]] = self._subrack.PowerOnTpm(self._subrack_bay)
        if result_code == ResultCode.OK:
            self._update_power_mode(PowerMode.ON)
            return True
        elif result_code == ResultCode.FAILED:
            return False
        else:
            raise NotImplementedError(
                f"Subrack.PowerOnTpm returned unexpected ResultCode {result_code.name}."
            )

    @property
    def power_mode(self):
        """
        Return the power mode of this PowerManager object.

        :return: the power mode of thei PowerManager object
        :rtype: :py:class:`~ska_low_mccs.hardware.power_mode_hardware.PowerMode`
        """
        return self._power_mode

    def _subrack_power_changed(self, event_name, event_value, event_quality):
        """
        Callback that this device registers with the event manager, so that it is
        informed when the subrack power changes.

        Because events may be delayed, a rapid off-on command sequence
        can result in an "off" event arriving after the on() command has
        been executed. We therefore don't put our full trust in these
        events.

        :param event_name: name of the event; will always be
            "areTpmsOn" for this callback
        :type event_name: str
        :param event_value: the new attribute value
        :type event_value: list(bool)
        :param event_quality: the quality of the change event
        :type event_quality: :py:class:`tango.AttrQuality`
        """
        assert event_name.lower() == "areTpmsOn".lower(), (
            "subrack 'areTpmsOn' attribute changed callback called but "
            f"event_name is {event_name}."
        )

        according_to_event = (
            PowerMode.ON if event_value[self._subrack_bay - 1] else PowerMode.OFF
        )
        according_to_command = self._read_power_mode()
        if according_to_command == PowerMode.UNKNOWN:
            self._update_power_mode(according_to_event)
        elif according_to_event != according_to_command:
            self._logger.warning(
                f"Received a TPM power change event for {according_to_event.name} but "
                f"a manual read says {according_to_command.name}; discarding."
            )
        else:
            self._update_power_mode(according_to_command)

    def _read_power_mode(self):
        """
        Helper method to read and interpret the power mode of the hardware.

        :return: the power mode of the hardware
        :rtype: :py:class:`ska_low_mccs.hardware.power_mode_hardware.PowerMode`
        """
        try:
            subrack_state = self._subrack.state()
        except DevFailed:
            self._logger.warning("Reading subrack state failed")
            return PowerMode.UNKNOWN

        if subrack_state == DevState.DISABLE:
            return PowerMode.OFF
        # Subrack power state is on, can provide power state
        elif subrack_state not in [DevState.OFF, DevState.ON, DevState.STANDBY]:
            self._logger.warning(
                f"Cannot determine TPM power as subrack is in {subrack_state} state"
            )
            return PowerMode.UNKNOWN

        try:
            is_tpm_on = self._subrack.IsTpmOn(self._subrack_bay)
        except DevFailed:
            self._logger.warning("IsTpmOn command failed for subrack")
            return PowerMode.UNKNOWN

        return PowerMode.ON if is_tpm_on else PowerMode.OFF

    def _update_power_mode(self, power_mode):
        """
        Update the power mode, ensuring that callbacks are called.

        :param power_mode: the power mode of the hardware
        :type power_mode:
            :py:class:`ska_low_mccs.hardware.power_mode_hardware.PowerMode`
        """
        if self._power_mode != power_mode:
            self._power_mode = power_mode
            self._callback(power_mode)


class MccsTile(SKABaseDevice):
    """
    The Tile Device represents the TANGO interface to a Tile (TPM) unit.

    This class is a subclass of :py:class:`ska_tango_base.SKABaseDevice`.

    **Properties:**

    - Device Property
    """

    # -----------------
    # Device Properties
    # -----------------
    AntennasPerTile = device_property(dtype=int, default_value=16)

    SubrackFQDN = device_property(dtype=str)
    SubrackBay = device_property(dtype=int)

    TileId = device_property(dtype=int, default_value=0)
    TpmIp = device_property(dtype=str, default_value="0.0.0.0")
    TpmCpldPort = device_property(dtype=int, default_value=10000)
    TpmVersion = device_property(dtype=str, default_value="tpm_v1_6")

    # ---------------
    # General methods
    # ---------------
    def init_device(self):
        """
        Initialise the device; overridden here to change the Tango serialisation model.
        """
        util = Util.instance()
        util.set_serial_model(SerialModel.NO_SYNC)
        super().init_device()

    class InitCommand(SKABaseDevice.InitCommand):
        """
        Class that implements device initialisation for the MCCS Tile is managed under
        the hood; the basic sequence is:

        1. Device state is set to INIT
        2. The do() method is run
        3. Device state is set to the appropriate outgoing state,
           usually off
        """

        def __init__(self, target, state_model, logger=None):
            """
            Create a new InitCommand.

            :param target: the object that this command acts upon; for
                example, the device for which this class implements the
                command
            :type target: object
            :param state_model: the state model that this command uses
                 to check that it is allowed to run, and that it drives
                 with actions.
            :type state_model:
                :py:class:`~ska_tango_base.DeviceStateModel`
            :param logger: the logger to be used by this Command. If not
                provided, then a default module logger will be used.
            :type logger: :py:class:`logging.Logger`
            """
            super().__init__(target, state_model, logger)

            self._thread = None
            self._lock = threading.Lock()
            self._interrupt = False
            self._message_queue = None
            self._qdebuglock = threading.Lock()

        def do(self):
            """
            Initialises the attributes and properties of the MCCS Tile device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            (result_code, message) = super().do()
            device = self.target
            device._heart_beat = 0
            device.queue_debug = ""
            device._simulation_mode = SimulationMode.FALSE

            device._logical_tile_id = 0
            device._subarray_id = 0
            device._station_id = 0

            device._csp_destination_ip = ""
            device._csp_destination_mac = ""
            device._csp_destination_port = 0

            device._antenna_ids = []

            device.hardware_manager = TileHardwareManager(
                device._simulation_mode,
                device._test_mode,
                device.logger,
                device.TpmIp,
                device.TpmCpldPort,
                device.TpmVersion,
            )

            device.power_manager = TilePowerManager(
                device.SubrackFQDN, device.SubrackBay, self.logger, device.power_changed
            )

            # Start the Message queue for this device
            device._message_queue = MessageQueue(
                target=device, lock=self._qdebuglock, logger=self.logger
            )
            device._message_queue.start()

            self._thread = threading.Thread(
                target=self._initialise_connections, args=(device,)
            )
            with self._lock:
                self._thread.start()
                return (ResultCode.STARTED, "Init command started")

        def _initialise_connections(self, device):
            """
            Thread target for asynchronous initialisation of connections to external
            entities such as hardware and other devices.

            :param device: the device being initialised
            :type device: :py:class:`ska_tango_base.SKABaseDevice`
            """
            # https://pytango.readthedocs.io/en/stable/howto.html
            # #using-clients-with-multithreading
            with EnsureOmniThread():
                self._initialise_health_monitoring(device)
                if self._interrupt:
                    self._thread = None
                    self._interrupt = False
                    return
                self._initialise_power_management(device)
                if self._interrupt:
                    self._thread = None
                    self._interrupt = False
                    return
                with self._lock:
                    self.succeeded()

        def _initialise_health_monitoring(self, device):
            """
            Initialise the health model for this device.

            :param device: the device for which the health model is
                being initialised
            :type device: :py:class:`ska_tango_base.SKABaseDevice`
            """
            device.event_manager = EventManager(self.logger)
            device._health_state = HealthState.UNKNOWN
            device.set_change_event("healthState", True, False)
            device.health_model = HealthModel(
                device.hardware_manager,
                None,
                device.event_manager,
                device.health_changed,
            )

        def _initialise_power_management(self, device):
            """
            Initialise power management for this device.

            :param device: the device for which power management is
                being initialised
            :type device: :py:class:`ska_tango_base.SKABaseDevice`
            """
            device.power_manager.connect()

            if device.power_manager.power_mode == PowerMode.ON:
                device.hardware_manager.set_connectible(True)

        def interrupt(self):
            """
            Interrupt the initialisation thread (if one is running)

            :return: whether the initialisation thread was interrupted
            :rtype: bool
            """
            if self._thread is None:
                return False
            self._interrupt = True
            return True

        def succeeded(self):
            """
            Called when initialisation completes.

            Here we override the base class default implementation to
            ensure that MccsTile transitions to a state that reflects
            the state of its hardware
            """
            device = self.target
            if device.hardware_manager.connection_status != ConnectionStatus.CONNECTED:
                action = "init_succeeded_disable"
            else:
                if device.hardware_manager.is_programmed:
                    action = "init_succeeded_off"
                else:
                    action = "init_succeeded_standby"
            self.state_model.perform_action(action)

    class DisableCommand(SKABaseDevice.DisableCommand):
        """
        Class for handling the Disable() command.
        """

        REDUNDANT_MESSAGE = "TPM was already off: nothing to do to disable device."
        FAILED_MESSAGE = "Failed to disable device: could not turn TPM off"
        SUCCEEDED_MESSAGE = "Device disabled; TPM has been turned off"

        def do(self):
            """
            Stateless hook implementing the functionality of the (inherited)
            :py:meth:`ska_tango_base.SKABaseDevice.Disable` command for this
            :py:class:`.MccsTile` device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            result = self.target.power_manager.off()
            if result is None:
                self.target.hardware_manager.set_connectible(False)
                return (ResultCode.OK, self.REDUNDANT_MESSAGE)

            if not result:
                return (ResultCode.FAILED, self.FAILED_MESSAGE)

            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    class StandbyCommand(SKABaseDevice.StandbyCommand):
        """
        Class for handling the Standby() command.

        Actually the TPM has no standby mode, so when this device is
        told to go to standby mode, it switches on / remains on.
        """

        SUCCEEDED_FROM_ON_MESSAGE = "TPM was re-initialised; device is now on standby."
        FAILED_MESSAGE = "Failed to go to standby: could not turn TPM on"
        SUCCEEDED_FROM_OFF_MESSAGE = "TPM has been turned on"

        def do(self):
            """
            Stateless hook implementing the functionality of the (inherited)
            :py:meth:`ska_tango_base.SKABaseDevice.Standby` command for this
            :py:class:`.MccsTile` device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            device = self.target
            result = device.power_manager.on()
            if result is None:
                # TODO: The TPM was already powered, so it might
                # already be programmed!
                # Putting in Standby could mean deprogram it, in order
                # to reduce power usage
                # This needs attention from an expert.
                if device.hardware_manager.is_programmed:
                    # deprogram FPGAs
                    pass

                return (
                    ResultCode.OK,
                    self.SUCCEEDED_FROM_ON_MESSAGE,
                )
            if not result:
                return (ResultCode.FAILED, self.FAILED_MESSAGE)

            device.hardware_manager.set_connectible(True)
            return (ResultCode.OK, self.SUCCEEDED_FROM_OFF_MESSAGE)

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def On(self, json_args):
        """
        Send a message to turn Tile on and program TPM firmware.

        This command will transition a Tile from Off/Standby to
        On and program the TPM firmware.

        :param json_args: JSON encoded messaging system and command arguments
        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        self.logger.debug("Tile On")

        # TODO: This sequence will all need to be messages so as not to cause
        #       a 3 second timeout with Tango commands. This is especially true
        #       when real hardware is connected to MCCS as programming the FPGA
        #       will take several seconds as part of the initialise step.
        self._command_sequence = [
            "TileOn",
            "Initialise",
        ]
        if self.state_model.op_state == DevState.STANDBY:
            self._command_sequence.insert(0, "Off")

        return self._send_message("On", json_args)

    class OnCommand(SKABaseDevice.OnCommand):
        """
        Class for handling the On command sequence.
        """

        SUCCEEDED_MESSAGE = "Tile On command sequence completed OK"

        def do(self, argin):
            """
            Stateless do hook for implementing the functionality of the
            :py:meth:`.MccsTile.On` command.

            :param argin: Argument containing JSON encoded command message and result
            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            self.logger.debug("Tile OnCommand EXE")
            device = self.target
            super().do()

            # Execute the following commands to:
            # 1. Off - Transition out of Standby state (if required)
            # 2. On - Turn the power on to the Tile
            # 3. Initialise - Download TPM firmware and initialise
            return_code = ResultCode.UNKNOWN
            for step in device._command_sequence:
                command = device.get_command_object(step)
                (return_code, message) = command()
                if return_code == ResultCode.FAILED:
                    self.logger.warning(
                        f"Tile OnCommand EXE FAILED command={command}, "
                        "rc={return_code}, status={message}"
                    )
                    return (return_code, message)
            self.logger.debug(self.SUCCEEDED_MESSAGE)
            return (return_code, self.SUCCEEDED_MESSAGE)

    class TileOnCommand(SKABaseDevice.OnCommand):
        """
        Class for handling the On() command.
        """

        SUCCEEDED_MESSAGE = "Tile On command completed OK"
        FAILED_MESSAGE = "Tile On command failed"

        def do(self):
            """
            Stateless hook implementing the functionality of the (inherited)
            :py:meth:`ska_tango_base.SKABaseDevice.On` command for this
            :py:class:`.MccsTile` device.

            At present this does nothing but call its `super().do()`
            method, and interfere in the return message.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            self.logger.debug("Tile TileOnCommand EXE")
            (result_code, _) = super().do()

            if result_code == ResultCode.OK:
                return (ResultCode.OK, self.SUCCEEDED_MESSAGE)
            else:
                return (ResultCode.FAILED, self.FAILED_MESSAGE)

    def _send_message(self, command, json_args):
        """
        Helper method to send a message to execute the specified command.

        :param command: the command to send a message for
        :type command: str
        :param json_args: arguments to pass with the command
        :type json_args: str

        :return: A tuple containing a return code, a string
            message indicating status and message UID.
            The string message is for information purposes only, but
            the message UID is for message management use.
        :rtype:
            (:py:class:`~ska_tango_base.commands.ResultCode`, [str, str])
        """
        kwargs = json.loads(json_args)
        respond_to_fqdn = kwargs.get("respond_to_fqdn")
        callback = kwargs.get("callback")
        if respond_to_fqdn and callback:
            (
                result_code,
                message_uid,
                status,
            ) = self._message_queue.send_message_with_response(
                command=command, respond_to_fqdn=respond_to_fqdn, callback=callback
            )
            return [[result_code], [status, message_uid]]
        else:
            # Call command sequentially
            handler = self.get_command_object(command)
            (result_code, status) = handler(json_args)
            return [[result_code], [status]]

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def Off(self, json_args):
        """
        Send a message to turn Tile off.

        :param json_args: JSON encoded messaging system and command arguments
        :return: A tuple containing a return code, a string
            message indicating status and message UID.
            The string message is for information purposes only, but
            the message UID is for message management use.
        :rtype:
            (:py:class:`~ska_tango_base.commands.ResultCode`, [str, str])
        """
        self.logger.debug("Tile Off")
        return self._send_message("Off", json_args)

    class OffCommand(SKABaseDevice.OffCommand):
        """
        Class for handling the Off() command.

        This command will transition a Tile from Standby to Off and
        program the TPM firmware. Off status means that the TPM is
        powered and programmed
        """

        SUCCEEDED_FROM_ON_MESSAGE = "TPM is on and programmed; device is now off."
        SUCCEEDED_FROM_DISABLE_MESSAGE = "TPM has been turned on"
        FAILED_MESSAGE = "Failed to go to OFF: could not turn TPM on"

        def do(self, argin):
            """
            Stateless hook implementing the functionality of the (inherited)
            :py:meth:`ska_tango_base.SKABaseDevice.Off` command for this
            :py:class:`.MccsTile` device.

            :param argin: Argument containing JSON encoded command message and result
            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            self.logger.debug("Tile OffCommand EXE")

            # TODO: We maybe shouldn't be allowing transition straight
            # from Disable to Off, without going through Standby.
            device = self.target
            result = device.power_manager.on()
            if result is None:
                # What does it mean to put it into "off" mode?
                # FOr now, program it using the current default firmware
                # programmed yet. i.e. it might still be in standby mode
                if not device.hardware_manager.is_programmed:
                    device.hardware_manager.download_firmware(
                        device.hardware_manager._default_firmware
                    )
                    self.logger.debug("Tile OffCommand EXE completed OK! Branch 1")
                return (ResultCode.OK, self.SUCCEEDED_FROM_ON_MESSAGE)

            if not result:
                self.logger.warning("Tile OffCommand EXE completed FAILED!")
                return (ResultCode.FAILED, self.FAILED_MESSAGE)

            device.hardware_manager.set_connectible(True)

            # TODO: Okay, the TPM was been powered on. Now we need to
            # get it fully operational.
            # This needs attention from an expert.
            # But for now, let's initialise it and pretend to flash some firmware.
            device.hardware_manager.download_firmware(
                device.hardware_manager._default_firmware
            )

            # TODO: This is a sad state of affairs. We need to wait a sec here to drain
            # the events system. Otherwise we run the risk of transitioning as a result
            # of command success, only to receive an old event telling us of an earlier
            # change in TPM power mode, making us transition again.
            self.logger.debug("Tile OffCommand EXE completed OK! Branch 2")
            return (ResultCode.OK, self.SUCCEEDED_FROM_DISABLE_MESSAGE)

    def always_executed_hook(self):
        """
        Method always executed before any TANGO command is executed.
        """
        if self.hardware_manager is not None:
            self.hardware_manager.poll()

    def delete_device(self):
        """
        Hook to delete resources allocated in the
        :py:meth:`~.MccsTile.InitCommand.do` method of the nested
        :py:class:`~.MccsTile.InitCommand` class.

        This method allows for any memory or other resources allocated
        in the
        :py:meth:`~.MccsTile.InitCommand.do` method to be released. This
        method is called by the device destructor, and by the Init
        command when the Tango device server is re-initialised.
        """
        if self._message_queue.is_alive():
            self._message_queue.terminate_thread()
            self._message_queue.join()

    # ----------
    # Callbacks
    # ----------
    @attribute(dtype="DevULong")
    def aHeartBeat(self):
        """
        Return the Heartbeat attribute value.

        :return: heart beat as a percentage
        """
        return self._heart_beat

    def health_changed(self, health):
        """
        Callback to be called whenever the HealthModel's health state changes;
        responsible for updating the tango side of things i.e. making sure the attribute
        is up to date, and events are pushed.

        :param health: the new health value
        :type health: :py:class:`~ska_tango_base.control_model.HealthState`
        """
        if self._health_state == health:
            return
        self._health_state = health
        self.push_change_event("healthState", health)

    def power_changed(self, power_mode):
        """
        Callback to be called whenever the TilePowerManager's record of the power mode
        of the TPM changes; responsible for updating the tango side of things i.e.
        making sure the attribute is up to date, and events are pushed.

        :todo: There's way too much explicit management of state in this
            callback. We need to get this into the state machine so we
            can simply
            ``self.state_model.perform_action("tpm_was_turned_off")``.

        :param power_mode: the new power_mode
        :type power_mode:
            :py:class:`~ska_low_mccs.hardware.power_mode_hardware.PowerMode`
        """
        if self.get_state() == DevState.INIT:
            # Don't respond to power mode changes while initialising.
            # We'll worry about it when it comes time to transition out
            # of INIT.
            return

        # TODO: For now, we need to get our devices to OFF state
        # (the highest state of device readiness for a device that
        # isn't actually on) before we can put them into ON state.
        # This is a counterintuitive mess that will be fixed in
        # SP-1501.
        if power_mode == PowerMode.UNKNOWN:
            self.state_model.perform_action("fatal_error")
        elif power_mode == PowerMode.OFF:
            self.hardware_manager.set_connectible(False)
            if self.get_state() == DevState.ON:
                self.state_model.perform_action("off_succeeded")
            self.state_model.perform_action("disable_succeeded")
        elif power_mode == PowerMode.ON:
            self.hardware_manager.set_connectible(True)
            self.state_model.perform_action("off_succeeded")

    def _update_admin_mode(self, admin_mode):
        """
        Helper method for changing admin_mode; passed to the state model as a callback
        Deselect test generator if mode is not MAINTENANCE.

        :param admin_mode: the new admin_mode value
        :type admin_mode: :py:class:`~ska_tango_base.control_model.AdminMode`
        """
        if not (admin_mode == AdminMode.MAINTENANCE) and self.TestGeneratorActive:
            self.TestGeneratorActive = False
            if self.hardware_manager is not None:
                self.hardware_manager.test_generator_input_select(0)
                self.hardware_manager.test_generator_active = False

        super()._update_admin_mode(admin_mode)

    # ----------
    # Attributes
    # ----------
    @attribute(dtype="DevString")
    def aQueueDebug(self):
        """
        Return the queueDebug attribute.

        :return: queueDebug attribute
        """
        return self.queue_debug

    @aQueueDebug.write
    def aQueueDebug(self, debug_string):
        """
        Update the queue debug attribute.

        :param debug_string: the new debug string for this attribute
        :type debug_string: str
        """
        self.queue_debug = debug_string

    @attribute(dtype="DevLong")
    def logicalTileId(self):
        """
        Return the logical tile id.

        :todo: This documentation should differentiate this from the
            tile id

        :return: the logical tile id
        :rtype: int
        """
        return self.hardware_manager.tile_id

    @logicalTileId.write
    def logicalTileId(self, value):
        """
        Set the logicalTileId attribute.

        :todo: This documentation should differentiate this from the
            tile id

        :param value: the new logical tile id
        :type value: int
        """
        self.hardware_manager.tile_id = value

    @attribute(dtype="DevLong")
    def subarrayId(self):
        """
        Return the id of the subarray to which this tile is assigned.

        :return: the id of the subarray to which this tile is assigned
        :rtype: int
        """
        return self._subarray_id

    @subarrayId.write
    def subarrayId(self, value):
        """
        Set the id of the subarray to which this tile is assigned.

        :param value: the subarray id
        :type value: int
        """
        self._subarray_id = value

    @attribute(dtype="DevLong")
    def stationId(self):
        """
        Return the id of the station to which this tile is assigned.

        :return: the id of the station to which this tile is assigned
        :rtype: int
        """
        return self.hardware_manager.station_id

    @stationId.write
    def stationId(self, value):
        """
        Set the id of the station to which this tile is assigned.

        :param value: the station id
        :type value: int
        """
        self.hardware_manager.station_id = value

    @attribute(
        dtype="DevString",
    )
    def cspDestinationIp(self):
        """
        Return the CSP destination IP address.

        :return: the CSP destination IP address
        :rtype: str
        """
        return self._csp_destination_ip

    @cspDestinationIp.write
    def cspDestinationIp(self, value):
        """
        Set the CSP destination IP address.

        :param value: the new IP address
        :type value: str
        """
        self._csp_destination_ip = value

    @attribute(
        dtype="DevString",
    )
    def cspDestinationMac(self):
        """
        Return the CSP destination MAC address.

        :return: a MAC address
        :rtype: str
        """
        return self._csp_destination_mac

    @cspDestinationMac.write
    def cspDestinationMac(self, value):
        """
        Set the CSP destination MAC address.

        :param value: MAC address
        :type value: str
        """
        self._csp_destination_mac = value

    @attribute(
        dtype="DevLong",
    )
    def cspDestinationPort(self):
        """
        Return the cspDestinationPort attribute.

        :return: CSP destination port
        :rtype: int
        """
        return self._csp_destination_port

    @cspDestinationPort.write
    def cspDestinationPort(self, value):
        """
        Set the CSP destination port.

        :param value: CSP destination port
        :type value: int
        """
        self._csp_destination_port = value

    @attribute(dtype="DevString")
    def firmwareName(self):
        """
        Return the firmware name.

        :return: firmware name
        :rtype: str
        """
        return self.hardware_manager.firmware_name

    @firmwareName.write
    def firmwareName(self, value):
        """
        Set the firmware name.

        :param value: firmware name
        :type value: str
        """
        self.hardware_manager.firmware_name = value

    @attribute(dtype="DevString")
    def firmwareVersion(self):
        """
        Return the firmware version.

        :return: firmware version
        :rtype: str
        """
        return self.hardware_manager.firmware_version

    @firmwareVersion.write
    def firmwareVersion(self, value):
        """
        Set the firmware version.

        :param value: firmware version
        :type value: str
        """
        self.hardware_manager.firmware_version = value

    @attribute(
        dtype="DevDouble",
        abs_change=0.05,
        min_value=4.5,
        max_value=5.5,
        min_alarm=4.55,
        max_alarm=5.45,
    )
    def voltage(self):
        """
        Return the voltage.

        :return: voltage
        :rtype: float
        """
        return self.hardware_manager.voltage

    @attribute(
        dtype="DevDouble",
        abs_change=0.05,
        min_value=0.0,
        max_value=3.0,
        min_warning=0.1,
        max_warning=2.85,
        min_alarm=0.05,
        max_alarm=2.95,
    )
    def current(self):
        """
        Return the current.

        :return: current
        :rtype: float
        """
        return self.hardware_manager.current

    @attribute(
        dtype="DevBoolean",
    )
    def isProgrammed(self):
        """
        Return a flag indicating whether of not the board is programmed.

        :return: whether of not the board is programmed
        :rtype: bool
        """
        return self.hardware_manager.is_programmed

    @attribute(
        dtype="DevDouble",
        abs_change=0.1,
        min_value=15.0,
        max_value=50.0,
        min_alarm=16.0,
        max_alarm=47.0,
    )
    def board_temperature(self):
        """
        Return the board temperature.

        :return: the board temperature
        :rtype: float
        """
        return self.hardware_manager.board_temperature

    @attribute(
        dtype="DevDouble",
        abs_change=0.1,
        min_value=15.0,
        max_value=50.0,
        min_alarm=16.0,
        max_alarm=47.0,
    )
    def fpga1_temperature(self):
        """
        Return the temperature of FPGA 1.

        :return: the temperature of FPGA 1
        :rtype: float
        """
        return self.hardware_manager.fpga1_temperature

    @attribute(
        dtype="DevDouble",
        abs_change=0.2,
        min_value=15.0,
        max_value=50.0,
        min_alarm=16.0,
        max_alarm=47.0,
    )
    def fpga2_temperature(self):
        """
        Return the temperature of FPGA 2.

        :return: the temperature of FPGA 2
        :rtype: float
        """
        return self.hardware_manager.fpga2_temperature

    @attribute(dtype="DevLong")
    def fpga1_time(self):
        """
        Return the time for FPGA 1.

        :return: the time for FPGA 1
        :rtype: int
        """
        return self.hardware_manager.fpga1_time

    @attribute(dtype="DevLong")
    def fpga2_time(self):
        """
        Return the time for FPGA 2.

        :return: the time for FPGA 2
        :rtype: int
        """
        return self.hardware_manager.fpga2_time

    @attribute(
        dtype=("DevLong",),
        max_dim_x=8,
        label="Antenna ID's",
    )
    def antennaIds(self):
        """
        Return the antenna IDs.

        :return: the antenna IDs
        :rtype: list(int)
        """
        return tuple(self._antenna_ids)

    @antennaIds.write
    def antennaIds(self, antenna_ids):
        """
        Set the antenna IDs.

        :param antenna_ids: the antenna IDs
        :type antenna_ids: list(int)
        """
        self._antenna_ids = list(antenna_ids)

    @attribute(
        dtype=("DevString",),
        max_dim_x=256,
    )
    def fortyGbDestinationIps(self):
        """
        Return the destination IPs for all 40Gb ports on the tile.

        :return: IP addresses
        :rtype: list(str)
        """
        return tuple(
            item["DstIP"] for item in self.hardware_manager.get_40g_configuration()
        )

    @attribute(
        dtype=("DevLong",),
        max_dim_x=256,
    )
    def fortyGbDestinationPorts(self):
        """
        Return the destination ports for all 40Gb ports on the tile.

        :return: ports
        :rtype: list(int)
        """
        return tuple(
            item["DstPort"] for item in self.hardware_manager.get_40g_configuration()
        )

    @attribute(
        dtype=("DevDouble",),
        max_dim_x=32,
    )
    def adcPower(self):
        """
        Return the RMS power of every ADC signal (so a TPM processes 16 antennas, this
        should return 32 RMS value.

        :return: RMP power of ADC signals
        :rtype: list(float)
        """
        return self.hardware_manager.adc_rms

    @attribute(
        dtype="DevLong",
    )
    def currentTileBeamformerFrame(self):
        """
        Return current frame, in units of 256 ADC frames (276,48 us) Currently this is
        required, not sure if it will remain so.

        :return: current frame
        :rtype: int
        """
        return self.hardware_manager.current_tile_beamformer_frame

    @attribute(dtype="DevBoolean")
    def checkPendingDataRequests(self):
        """
        Check for pending data requests.

        :return: whether there are data requests pending
        :rtype: bool
        """
        return self.hardware_manager.check_pending_data_requests()

    @attribute(dtype="DevBoolean")
    def isBeamformerRunning(self):
        """
        Check if beamformer is running.

        :return: whether the beamformer is running
        :rtype: bool
        """
        return self.hardware_manager.is_beamformer_running

    @attribute(dtype="DevLong")
    def phaseTerminalCount(self):
        """
        Get phase terminal count.

        :return: phase terminal count
        :rtype: int
        """
        return self.hardware_manager.phase_terminal_count

    @phaseTerminalCount.write
    def phaseTerminalCount(self, value):
        """
        Set the phase terminal count.

        :param value: the phase terminal count
        :type value: int
        """
        self.hardware_manager.phase_terminal_count = value

    @attribute(dtype="DevLong")
    def ppsDelay(self):
        """
        Return the PPS delay.

        :return: Return the PPS delay
        :rtype: int
        """
        return self.hardware_manager.pps_delay

    @attribute(
        dtype="DevLong",
        memorized=True,
        hw_memorized=True,
    )
    def simulationMode(self):
        """
        Reports the simulation mode of the device.

        :return: Return the current simulation mode
        :rtype: int
        """
        return super().read_simulationMode()

    @simulationMode.write
    def simulationMode(self, value):
        """
        Set the simulation mode.

        :param value: The simulation mode, as a SimulationMode value
        """
        super().write_simulationMode(value)
        self.logger.info("Switching simulation mode to " + str(value))
        self.hardware_manager.simulation_mode = value

    @attribute(dtype="DevLong")
    def testMode(self):
        """
        Reports the test mode of the device.

        :return: Return the current test mode of this device
        :rtype: int
        """
        return super().read_testMode()

    @testMode.write
    def testMode(self, value):
        """
        Set the test mode.

        :param value: The test mode, as a TestMode value
        """
        super().write_testMode(value)
        self.logger.info("Switching test mode to " + str(value))
        self.hardware_manager.test_mode = value

    @attribute(dtype="DevBoolean")
    def TestGeneratorActive(self):
        """
        Reports if the test generator is used for some channels.

        :return: test generator status
        :rtype: bool
        """
        return self.hardware_manager.test_generator_active

    # # --------
    # # Commands
    # # --------
    def init_command_objects(self):
        """
        Set up the handler objects for Commands.
        """
        super().init_command_objects()

        for (command_name, command_object) in [
            ("Initialise", self.InitialiseCommand),
            ("GetFirmwareAvailable", self.GetFirmwareAvailableCommand),
            ("DownloadFirmware", self.DownloadFirmwareCommand),
            ("ProgramCPLD", self.ProgramCPLDCommand),
            ("GetRegisterList", self.GetRegisterListCommand),
            ("ReadRegister", self.ReadRegisterCommand),
            ("WriteRegister", self.WriteRegisterCommand),
            ("ReadAddress", self.ReadAddressCommand),
            ("WriteAddress", self.WriteAddressCommand),
            ("Configure40GCore", self.Configure40GCoreCommand),
            ("Get40GCoreConfiguration", self.Get40GCoreConfigurationCommand),
            ("SetLmcDownload", self.SetLmcDownloadCommand),
            ("GetArpTable", self.GetArpTableCommand),
            ("SetChanneliserTruncation", self.SetChanneliserTruncationCommand),
            ("SetBeamFormerRegions", self.SetBeamFormerRegionsCommand),
            ("ConfigureStationBeamformer", self.ConfigureStationBeamformerCommand),
            ("LoadCalibrationCoefficients", self.LoadCalibrationCoefficientsCommand),
            ("LoadCalibrationCurve", self.LoadCalibrationCurveCommand),
            ("LoadBeamAngle", self.LoadBeamAngleCommand),
            ("SwitchCalibrationBank", self.SwitchCalibrationBankCommand),
            ("LoadPointingDelay", self.LoadPointingDelayCommand),
            ("StartBeamformer", self.StartBeamformerCommand),
            ("StopBeamformer", self.StopBeamformerCommand),
            (
                "ConfigureIntegratedChannelData",
                self.ConfigureIntegratedChannelDataCommand,
            ),
            ("StopIntegratedChannelData", self.StopIntegratedChannelDataCommand),
            ("ConfigureIntegratedBeamData", self.ConfigureIntegratedBeamDataCommand),
            ("StopIntegratedBeamData", self.StopIntegratedBeamDataCommand),
            ("StopIntegratedData", self.StopIntegratedDataCommand),
            ("SendRawData", self.SendRawDataCommand),
            ("SendChannelisedData", self.SendChannelisedDataCommand),
            (
                "SendChannelisedDataContinuous",
                self.SendChannelisedDataContinuousCommand,
            ),
            ("SendBeamData", self.SendBeamDataCommand),
            ("StopDataTransmission", self.StopDataTransmissionCommand),
            (
                "ComputeCalibrationCoefficients",
                self.ComputeCalibrationCoefficientsCommand,
            ),
            ("StartAcquisition", self.StartAcquisitionCommand),
            ("SetTimeDelays", self.SetTimeDelaysCommand),
            ("SetCspRounding", self.SetCspRoundingCommand),
            ("SetLmcIntegratedDownload", self.SetLmcIntegratedDownloadCommand),
            ("SendRawDataSynchronised", self.SendRawDataSynchronisedCommand),
            (
                "SendChannelisedDataNarrowband",
                self.SendChannelisedDataNarrowbandCommand,
            ),
            ("TweakTransceivers", self.TweakTransceiversCommand),
            ("PostSynchronisation", self.PostSynchronisationCommand),
            ("SyncFpgas", self.SyncFpgasCommand),
            ("CalculateDelay", self.CalculateDelayCommand),
            ("ConfigureTestGenerator", self.ConfigureTestGeneratorCommand),
        ]:
            self.register_command_object(
                command_name,
                command_object(self.hardware_manager, self.state_model, self.logger),
            )

        antenna_args = (
            self.hardware_manager,
            self.state_model,
            self.logger,
            self.AntennasPerTile,
        )
        self.register_command_object(
            "LoadAntennaTapering", self.LoadAntennaTaperingCommand(*antenna_args)
        )
        self.register_command_object(
            "SetPointingDelay", self.SetPointingDelayCommand(*antenna_args)
        )

        for (command_name, command_object) in [
            ("Disable", self.DisableCommand),
            ("Standby", self.StandbyCommand),
            ("Off", self.OffCommand),
            ("On", self.OnCommand),
            ("TileOn", self.TileOnCommand),
        ]:
            self.register_command_object(
                command_name,
                command_object(self, self.state_model, self.logger),
            )

    class InitialiseCommand(ResponseCommand):
        """
        Class for handling the Initialise() command.
        """

        SUCCEEDED_MESSAGE = "Initialise command completed OK"

        def do(self):
            """
            Implementation of
            :py:meth:`.MccsTile.Initialise` command
            functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            hardware_manager.initialise()
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def Initialise(self):
        """
        Performs all required initialisation (switches on on-board devices, locks PLL,
        performs synchronisation and other operations required to start configuring the
        signal processing functions of the firmware, such as channelisation and
        beamforming)

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("Initialise")
        """
        handler = self.get_command_object("Initialise")
        (return_code, message) = handler()
        return [[return_code], [message]]

    class GetFirmwareAvailableCommand(BaseCommand):
        """
        Class for handling the GetFirmwareAvailable() command.
        """

        def do(self):
            """
            Implementation of
            :py:meth:`.MccsTile.GetFirmwareAvailable` command
            functionality.

            :return: json encoded string containing list of dictionaries
            :rtype: str
            """
            hardware_manager = self.target
            return json.dumps(hardware_manager.firmware_available)

    @command(dtype_out="DevString")
    @DebugIt()
    def GetFirmwareAvailable(self):
        """
        Return a dictionary containing the following information for each firmware
        stored on the board (such as in Flash memory). For each firmware, a dictionary
        containing the following keys with their respective values should be provided:
        ‘design’, which is a textual name for the firmware, ‘major’, which is the major
        version number, and ‘minor’.

        :return: a JSON-encoded dictionary of firmware details
        :rtype: str

        :example:
            >>> dp = tango.DeviceProxy("mccs/tile/01")
            >>> jstr = dp.command_inout("GetFirmwareAvailable")
            >>> dict = json.load(jstr)
            {
            "firmware1": {"design": "model1", "major": 2, "minor": 3},
            "firmware2": {"design": "model2", "major": 3, "minor": 7},
            "firmware3": {"design": "model3", "major": 2, "minor": 6},
            }
        """
        handler = self.get_command_object("GetFirmwareAvailable")
        return handler()

    class DownloadFirmwareCommand(ResponseCommand):
        """
        Class for handling the DownloadFirmware(argin) command.
        """

        SUCCEEDED_MESSAGE = "DownloadFirmware command completed OK"

        def do(self, argin):
            """
            Implementation of
            :py:meth:`.MccsTile.DownloadFirmware` command
            functionality.

            :param argin: path to the bitfile to be downloaded
            :type argin: str

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            bitfile = argin
            if os.path.isfile(bitfile):
                hardware_manager.download_firmware(bitfile)
                return (ResultCode.OK, self.SUCCEEDED_MESSAGE)
            else:
                return (ResultCode.FAILED, f"{bitfile} doesn't exist")

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def DownloadFirmware(self, argin):
        """
        Downloads the firmware contained in bitfile to all FPGAs on the board. This
        should also update the internal register mapping, such that registers become
        available for use.

        :param argin: can either be the design name returned from
            :py:meth:`.GetFirmwareAvailable` command, or a path to a
            file
        :type argin: str

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("DownloadFirmware", "/tmp/firmware/bitfile")
        """
        handler = self.get_command_object("DownloadFirmware")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class ProgramCPLDCommand(ResponseCommand):
        """
        Class for handling the ProgramCPLD(argin) command.
        """

        SUCCEEDED_MESSAGE = "ProgramCPLD command completed OK"

        def do(self, argin):
            """
            Implementation of
            :py:meth:`.MccsTile.ProgramCPLD` command
            functionality.

            :param argin: path to the bitfile to be loaded
            :type argin: str

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            bitfile = argin
            self.logger.info("Downloading bitstream to CPLD FLASH")
            hardware_manager.cpld_flash_write(bitfile)
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def ProgramCPLD(self, argin):
        """
        If the TPM has a CPLD (or other management chip which need firmware), this
        function program it with the provided bitfile.

        :param argin: is the path to a file containing the required CPLD firmware
        :type argin: str

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("ProgramCPLD", "/tmp/firmware/bitfile")
        """
        handler = self.get_command_object("ProgramCPLD")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class GetRegisterListCommand(BaseCommand):
        """
        Class for handling the GetRegisterList() command.
        """

        def do(self):
            """
            Implementation of
            :py:meth:`.MccsTile.GetRegisterList` command
            functionality.

            :return:a list of firmware & cpld registers
            :rtype: list(str)
            """
            hardware_manager = self.target
            return hardware_manager.register_list

    @command(dtype_out="DevVarStringArray")
    @DebugIt()
    def GetRegisterList(self):
        """
        Return a list containing description of the exposed firmware (and CPLD)
        registers.

        :return: a list of register names
        :rtype: list(str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> reglist = dp.command_inout("GetRegisterList")
        """
        handler = self.get_command_object("GetRegisterList")
        return handler()

    class ReadRegisterCommand(BaseCommand):
        """
        Class for handling the ReadRegister(argin) command.
        """

        def do(self, argin):
            """
            Implementation of
            :py:meth:`.MccsTile.ReadRegister` command
            functionality.

            :param argin: a JSON-encoded dictionary of arguments
                including RegisterName, NbRead, Offset, Device
            :type argin: str
            :return: list of register values
            :rtype: list(int)

            :raises ValueError: if the JSON input lacks mandatory parameters

            :todo: Mandatory JSON parameters should be handled by validation
                against a schema
            """
            hardware_manager = self.target

            params = json.loads(argin)
            name = params.get("RegisterName", None)
            if name is None:
                self.logger.error("RegisterName is a mandatory parameter")
                raise ValueError("RegisterName is a mandatory parameter")
            nb_read = params.get("NbRead", None)
            if nb_read is None:
                self.logger.error("NbRead is a mandatory parameter")
                raise ValueError("NbRead is a mandatory parameter")
            offset = params.get("Offset", None)
            if offset is None:
                self.logger.error("Offset is a mandatory parameter")
                raise ValueError("Offset is a mandatory parameter")
            device = params.get("Device", None)
            if device is None:
                self.logger.error("Device is a mandatory parameter")
                raise ValueError("Device is a mandatory parameter")

            return hardware_manager.read_register(name, nb_read, offset, device)

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongArray",
    )
    @DebugIt()
    def ReadRegister(self, argin):
        """
        Return the value(s) of the specified register.

        :param argin: json dictionary with mandatory keywords:

        * RegisterName - (string) register_name is the registers string representation
        * NbRead - (int) is the number of 32-bit values to read
        * Offset - (int) offset is the address offset within the register to write to
        * Device - (int) device is the FPGA to write to (0 or 1)

        :type argin: str

        :return: a list of register values
        :rtype: list(int)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"RegisterName": "test-reg1", "NbRead": nb_read,
                    "Offset": offset, "Device":device}
        >>> jstr = json.dumps(dict)
        >>> values = dp.command_inout("ReadRegister", jstr)
        """
        handler = self.get_command_object("ReadRegister")
        return handler(argin)

    class WriteRegisterCommand(ResponseCommand):
        """
        Class for handling the WriteRegister(argin) command.
        """

        SUCCEEDED_MESSAGE = "WriteRegister command completed OK"

        def do(self, argin):
            """
            Implementation of
            :py:meth:`.MccsTile.WriteRegister` command
            functionality.

            :param argin: a JSON-encoded dictionary of arguments
                including RegisterName, Values, Offset, Device
            :type argin: str

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

            :raises ValueError: if the JSON input lacks
                mandatory parameters

            :todo: Mandatory JSON parameters should be handled by validation
                against a schema

            """
            hardware_manager = self.target

            params = json.loads(argin)
            name = params.get("RegisterName", None)
            if name is None:
                self.logger.error("RegisterName is a mandatory parameter")
                raise ValueError("RegisterName is a mandatory parameter")
            values = params.get("Values", None)
            if values is None:
                self.logger.error("Values is a mandatory parameter")
                raise ValueError("Values is a mandatory parameter")
            offset = params.get("Offset", None)
            if offset is None:
                self.logger.error("Offset is a mandatory parameter")
                raise ValueError("Offset is a mandatory parameter")
            device = params.get("Device", None)
            if device is None:
                self.logger.error("Device is a mandatory parameter")
                raise ValueError("Device is a mandatory parameter")

            hardware_manager.write_register(name, values, offset, device)
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def WriteRegister(self, argin):
        """
        Write values to the specified register.

        :param argin: json dictionary with mandatory keywords:

        * RegisterName - (string) register_name is the registers string representation
        * Values - (list) is a list containing the 32-bit values to write
        * Offset - (int) offset is the address offset within the register to write to
        * Device - (int) device is the FPGA to write to (0 or 1)

        :type argin: str

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"RegisterName": "test-reg1", "Values": values,
                    "Offset": offset, "Device":device}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("WriteRegister", jstr)
        """
        handler = self.get_command_object("WriteRegister")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class ReadAddressCommand(BaseCommand):
        """
        Class for handling the ReadAddress(argin) command.
        """

        def do(self, argin):
            """
            Implementation of
            :py:meth:`.MccsTile.ReadAddress` command
            functionality.

            :param argin: sequence of length two, containing an address and
                a value
            :type argin: list

            :return: [values, ]

            :raises ValueError: if the argin argument has the wrong length
                or structure
            """
            hardware_manager = self.target

            if len(argin) < 2:
                self.logger.error("Two parameters are required")
                raise ValueError("Two parameters are required")
            address = argin[0]
            nvalues = argin[1]
            return hardware_manager.read_address(address, nvalues)

    @command(
        dtype_in="DevVarLongArray",
        dtype_out="DevVarULongArray",
    )
    @DebugIt()
    def ReadAddress(self, argin):
        """
        Read n 32-bit values from address.

        :param argin: [0] = address to read from
                      [1] = number of values to read

        :return: list of values
        :rtype: list(int)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> reglist = dp.command_inout("ReadAddress", [address, nvalues]])
        """
        handler = self.get_command_object("ReadAddress")
        return handler(argin)

    class WriteAddressCommand(ResponseCommand):
        """
        Class for handling the WriteAddress(argin) command.
        """

        SUCCEEDED_MESSAGE = "WriteAddress command completed OK"

        def do(self, argin):
            """
            Implementation of
            :py:meth:`.MccsTile.WriteAddress` command
            functionality.

            :param argin: sequence of length two, containing an address and
                a value
            :type argin: list

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)

            :raises ValueError: if the argin has the wrong length/structure
            """
            hardware_manager = self.target
            if len(argin) < 2:
                self.logger.error("A minimum of two parameters are required")
                raise ValueError("A minium of two parameters are required")
            hardware_manager.write_address(argin[0], argin[1:])
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_in="DevVarULongArray",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def WriteAddress(self, argin):
        """
        Write list of values at address.

        :param argin: [0] = address to write to
                      [1..n] = list of values to write

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> values = [.....]
        >>> address = 0xfff
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("WriteAddress", [address, values])
        """
        handler = self.get_command_object("WriteAddress")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class Configure40GCoreCommand(ResponseCommand):
        """
        Class for handling the Configure40GCore(argin) command.
        """

        SUCCEEDED_MESSAGE = "Configure40GCore command completed OK"

        def do(self, argin):
            """
            Implementation of
            :py:meth:`.MccsTile.Configure40GCore` command
            functionality.

            :param argin: a JSON-encoded dictionary of arguments
            :type argin: str

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)

            :raises ValueError: if the JSON input lacks mandatory parameters

            :todo: Mandatory JSON parameters should be handled by validation
                against a schema
            """
            params = json.loads(argin)

            core_id = params.get("CoreID", None)
            if core_id is None:
                message = "CoreID is a mandatory parameter."
                self.logger.error(message)
                raise ValueError(message)
            arp_table_entry = params.get("ArpTableEntry", None)
            if arp_table_entry is None:
                message = "ArpTableEntry is a mandatory parameter."
                self.logger.error(message)
                raise ValueError(message)
            src_mac = params.get("SrcMac", None)
            if src_mac is None:
                message = "SrcMac is a mandatory parameter."
                self.logger.error(message)
                raise ValueError(message)
            src_ip = params.get("SrcIP", None)
            src_port = params.get("SrcPort", None)
            if src_port is None:
                message = "SrcPort is a mandatory parameter."
                self.logger.error(message)
                raise ValueError(message)
            dst_ip = params.get("DstIP", None)
            if dst_ip is None:
                message = "DstIP is a mandatory parameter."
                self.logger.error(message)
                raise ValueError(message)
            dst_port = params.get("DstPort", None)
            if dst_port is None:
                message = "DstPort is a mandatory parameter."
                self.logger.error(message)
                raise ValueError(message)

            hardware_manager = self.target
            hardware_manager.configure_40g_core(
                core_id, arp_table_entry, src_mac, src_ip, src_port, dst_ip, dst_port
            )
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def Configure40GCore(self, argin):
        """
        Configure 40g core_id with specified parameters.

        :param argin: json dictionary with optional keywords:

        * CoreID - (int) core id
        * ArpTableEntry - (int) ARP table entry ID
        * SrcMac - (int) mac address
        * SrcIP - (string) IP dot notation.
        * SrcPort - (int) source port
        * SrcPort - (int) source port
        * DstIP - (string) IP dot notation
        * DstPort - (int) destination port

        :type argin: str

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"CoreID":2, "ArpTableEntry":0, "SrcMac":0x62000a0a01c9,
                    "SrcIP":"10.0.99.3", "SrcPort":4000, "DstMac":"10:fe:ed:08:0a:58",
                    "DstIP":"10.0.99.3", "DstPort":5000}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("Configure40GCore", jstr)
        """
        handler = self.get_command_object("Configure40GCore")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class Get40GCoreConfigurationCommand(BaseCommand):
        """
        Class for handling the Get40GCoreConfiguration(argin) command.
        """

        def do(self, argin):
            """
            Implementation of
            :py:meth:`.MccsTile.Get40GCoreConfiguration`
            command functionality.

            :param argin: a JSON-encoded dictionary of arguments
            :type argin: str

            :return: json string with configuration
            :rtype: str

            :raises ValueError: if the argin is an invalid code id
            """
            params = json.loads(argin)
            core_id = params.get("CoreID", None)
            arp_table_entry = params.get("ArpTableEntry", 0)

            hardware_manager = self.target
            item = hardware_manager.get_40g_configuration(core_id, arp_table_entry)
            if item is not None:
                return json.dumps(item)
            raise ValueError("Invalid core id or arp table id specified")

    @command(
        dtype_in="DevString",
        dtype_out="DevString",
    )
    @DebugIt()
    def Get40GCoreConfiguration(self, argin):
        """
        Get 40g core configuration for core_id. This is required to chain up TPMs to
        form a station.

        :param argin: json dictionary with optional keywords:

        * CoreID - (int) core id
        * ArpTableEntry - (int) ARP table entry ID to use

        :return: the configuration is a json string comprising:
                 core_id, arp_table_entry, src_mac, src_ip, src_port, dest_ip, dest_port
        :rtype: str

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> core_id = 2
        >>> arp_table_entry = 0
        >>> argout = dp.command_inout("Get40GCoreConfiguration, core_id,
                                        arp_table_entry)
        >>> params = json.loads(argout)
        """
        handler = self.get_command_object("Get40GCoreConfiguration")
        return handler(argin)

    class SetLmcDownloadCommand(ResponseCommand):
        """
        Class for handling the SetLmcDownload(argin) command.
        """

        SUCCEEDED_MESSAGE = "SetLmcDownload command completed OK"

        def do(self, argin):
            """
            Implementation of
            :py:meth:`.MccsTile.SetLmcDownload` command
            functionality.

            :param argin: a JSON-encoded dictionary of arguments
            :type argin: str

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)

            :raises ValueError: if the JSON input lacks mandatory parameters

            :todo: Mandatory JSON parameters should be handled by validation
                against a schema
            """
            params = json.loads(argin)
            mode = params.get("Mode", None)
            if mode is None:
                self.logger.error("Mode is a mandatory parameter")
                raise ValueError("Mode is a mandatory parameter")
            payload_length = params.get("PayloadLength", 1024)
            dst_ip = params.get("DstIP", None)
            src_port = params.get("SrcPort", 0xF0D0)
            dst_port = params.get("DstPort", 4660)
            lmc_mac = params.get("LmcMac", None)

            hardware_manager = self.target
            hardware_manager.set_lmc_download(
                mode, payload_length, dst_ip, src_port, dst_port, lmc_mac
            )
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def SetLmcDownload(self, argin):
        """
        Specify whether control data will be transmitted over 1G or 40G networks.

        :param argin: json dictionary with optional keywords:

        * Mode - (string) '1g' or '10g' (Mandatory) (use '10g' for 40g also)
        * PayloadLength - (int) SPEAD payload length for channel data
        * DstIP - (string) Destination IP.
        * SrcPort - (int) Source port for integrated data streams
        * DstPort - (int) Destination port for integrated data streams
        * LmcMac: - (int) LMC Mac address is required for 10G lane configuration

        :type argin: str

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"Mode": "1G", "PayloadLength":4,DstIP="10.0.1.23"}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SetLmcDownload", jstr)
        """
        handler = self.get_command_object("SetLmcDownload")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class GetArpTableCommand(BaseCommand):
        """
        Class for handling the GetArpTable() command.
        """

        def do(self):
            """
            Implementation of
            :py:meth:`.MccsTile.GetArpTable` command functionality.

            :return: a JSON-encoded dictionary of coreId and populated arpID table
            :rtype: str
            """
            hardware_manager = self.target
            return json.dumps(hardware_manager.arp_table)

    @command(dtype_out="DevString")
    @DebugIt()
    def GetArpTable(self):
        """
        Return a dictionary with populated ARP table  for all used cores. 40G interfaces
        use cores 0 (fpga0) and 1(fpga1) and ARP ID 0 for beamformer, 1 for LMC. 10G
        interfaces use cores 0,1 (fpga0) and 4,5 (fpga1) for beamforming, and 2, 6 for
        LMC with only one ARP.

        :return: a JSON-encoded dictionary of coreId and populated arpID table
        :rtype: str

        :example:

        >>> argout = dp.command_inout("GetArpTable")
        >>> dict = json.loads(argout)
        >>>    {
        >>>    "core_id0": [arpID0, arpID1],
        >>>    "core_id1": [arpID0],
        >>>    "core_id3": [],
        >>>    }
        """
        handler = self.get_command_object("GetArpTable")
        return handler()

    class SetChanneliserTruncationCommand(ResponseCommand):
        """
        Class for handling the SetChanneliserTruncation(argin) command.
        """

        SUCCEEDED_MESSAGE = "SetChanneliserTruncation command completed OK"

        def do(self, argin):
            """
            Implementation of
            :py:meth:`.MccsTile.SetChanneliserTruncation`
            command functionality.

            :param argin: a truncation array
            :type argin: list(int)

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)

            :raises ValueError: if the argin argument does not have the
                right length / structure
            """
            if len(argin) < 3:
                self.logger.error("Insufficient values supplied")
                raise ValueError("Insufficient values supplied")
            nb_chan = argin[0]
            nb_freq = argin[1]
            arr = np.array(argin[2:])
            np.reshape(arr, (nb_chan, nb_freq))

            hardware_manager = self.target
            hardware_manager.set_channeliser_truncation(arr)
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_in="DevVarLongArray",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def SetChanneliserTruncation(self, argin):
        """
        Set the coefficients to modify (flatten) the bandpass.

        :param argin: truncation is a N x M array

        * argin[0] - is N, the number of input channels
        * argin[1] - is M, the number of frequency channel
        * argin[2:] - is the data

        :type argin: list(int)

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> n=4
        >>> m=3
        >>> trunc = [[0, 1, 2], [3, 4, 5],[6, 7, 0], [1, 2, 3],]
        >>> arr = np.array(trunc).ravel()
        >>> argin = np.concatenate([np.array((4, 3)), arr])
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("SetChanneliserTruncation", argin)
        """
        handler = self.get_command_object("SetChanneliserTruncation")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class SetBeamFormerRegionsCommand(ResponseCommand):
        """
        Class for handling the SetBeamFormerRegions(argin) command.
        """

        SUCCEEDED_MESSAGE = "SetBeamFormerRegions command completed OK"

        def do(self, argin):
            """
            Implementation of
            :py:meth:`.MccsTile.SetBeamFormerRegions`
            command functionality.

            :param argin: a region array
            :type argin: list(int)

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)

            :raises ValueError: if the argin argument does not have the
                right length / structure
            """
            if len(argin) < 4:
                self.logger.error("Insufficient parameters specified")
                raise ValueError("Insufficient parameters specified")
            if len(argin) > 192:
                self.logger.error("Too many regions specified")
                raise ValueError("Too many regions specified")
            if len(argin) % 4 != 0:
                self.logger.error("Incomplete specification of region")
                raise ValueError("Incomplete specification of region")
            regions = []
            total_chan = 0
            for i in range(0, len(argin), 4):
                region = argin[i : i + 4]  # noqa: E203
                start_channel = region[0]
                if start_channel % 2 != 0:
                    self.logger.error("Start channel in region must be even")
                    raise ValueError("Start channel in region must be even")
                nchannels = region[1]
                if nchannels % 8 != 0:
                    self.logger.error(
                        "Nos. of channels in region must be multiple of 8"
                    )
                    raise ValueError("Nos. of channels in region must be multiple of 8")
                beam_index = region[2]
                if beam_index < 0 or beam_index > 47:
                    self.logger.error("Beam_index is out side of range 0-47")
                    raise ValueError("Beam_index is out side of range 0-47")
                total_chan += nchannels
                if total_chan > 384:
                    self.logger.error("Too many channels specified > 384")
                    raise ValueError("Too many channels specified > 384")
                regions.append(region)

            hardware_manager = self.target
            hardware_manager.set_beamformer_regions(regions)
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_in="DevVarLongArray",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def SetBeamFormerRegions(self, argin):
        """
        Set the frequency regions which are going to be beamformed into each beam.
        region_array is defined as a 2D array, for a maximum of 48 regions. Total number
        of channels must be <= 384.

        :param argin: list of regions. Each region comprises:

        * start_channel - (int) region starting channel, must be even in range 0 to 510
        * num_channels - (int) size of the region, must be a multiple of 8
        * beam_index - (int) beam used for this region with range 0 to 47
        * substation_id - (int) Substation

        :type argin: list(int)

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> regions = [[4, 24, 0, 0],[26, 40, 1, 0]]
        >>> input = list(itertools.chain.from_iterable(regions))
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("SetBeamFormerRegions", input)
        """
        handler = self.get_command_object("SetBeamFormerRegions")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class ConfigureStationBeamformerCommand(ResponseCommand):
        """
        Class for handling the ConfigureStationBeamformer(argin) command.
        """

        SUCCEEDED_MESSAGE = "LoadCalibrationCoefficients command completed OK"

        def do(self, argin):
            """
            Implementation of
            :py:meth:`.MccsTile.ConfigureStationBeamformer`
            command functionality.

            :param argin: a JSON-encoded dictionary of arguments
            :type argin: str

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)

            :raises ValueError: if the argin argument does not have the
                right length / structure
            """
            params = json.loads(argin)
            start_channel = params.get("StartChannel", None)
            if start_channel is None:
                self.logger.error("StartChannel is a mandatory parameter")
                raise ValueError("StartChannel is a mandatory parameter")
            ntiles = params.get("NumTiles", None)
            if ntiles is None:
                self.logger.error("NumTiles is a mandatory parameter")
                raise ValueError("NumTiles is a mandatory parameter")
            is_first = params.get("IsFirst", None)
            if is_first is None:
                self.logger.error("IsFirst is a mandatory parameter")
                raise ValueError("IsFirst is a mandatory parameter")
            is_last = params.get("IsLast", None)
            if is_last is None:
                self.logger.error("IsLast is a mandatory parameter")
                raise ValueError("IsLast is a mandatory parameter")

            hardware_manager = self.target
            hardware_manager.initialise_beamformer(
                start_channel, ntiles, is_first, is_last
            )
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def ConfigureStationBeamformer(self, argin):
        """
        Initialise and start the station beamformer.

        :param argin: json dictionary with mandatory keywords:

        * StartChannel - (int) start channel
        * NumTiles - (int) is the number of tiles in the station
        * IsFirst - (bool) specifies whether the tile is the first one in the station
        * IsLast - (bool) specifies whether the tile is the last one in the station

        :type argin: str

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"StartChannel":1, "NumTiles":10, "IsTile":True}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("ConfigureStationBeamformer", jstr)
        """
        handler = self.get_command_object("ConfigureStationBeamformer")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class LoadCalibrationCoefficientsCommand(ResponseCommand):
        """
        Class for handling the LoadCalibrationCoefficients(argin) command.
        """

        SUCCEEDED_MESSAGE = "ConfigureStationBeamformer command completed OK"

        def do(self, argin):
            """
            Implementation of
            :py:meth:`.MccsTile.LoadCalibrationCoefficients`
            command functionality.

            :param argin: calibration coefficients
            :type argin: list(float)

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)

            :raises ValueError: if the argin argument does not have the
                right length / structure
            """
            if len(argin) < 9:
                self.logger.error("Insufficient calibration coefficients")
                raise ValueError("Insufficient calibration coefficients")
            if len(argin[1:]) % 8 != 0:
                self.logger.error("Incomplete specification of coefficient")
                raise ValueError("Incomplete specification of coefficient")
            antenna = int(argin[0])
            calibration_coefficients = [
                [
                    complex(argin[i], argin[i + 1]),
                    complex(argin[i + 2], argin[i + 3]),
                    complex(argin[i + 4], argin[i + 5]),
                    complex(argin[i + 6], argin[i + 7]),
                ]
                for i in range(1, len(argin), 8)
            ]

            hardware_manager = self.target
            hardware_manager.load_calibration_coefficients(
                antenna, calibration_coefficients
            )
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_in="DevVarDoubleArray",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def LoadCalibrationCoefficients(self, argin):
        """
        Loads calibration coefficients (but does not apply them, this is performed by
        switch_calibration_bank). The calibration coefficients may include any rotation
        matrix (e.g. the parallactic angle), but do not include the geometric delay.

        :param argin: list comprises:

        * antenna - (int) is the antenna to which the coefficients will be applied.
        * calibration_coefficients - [array] a bidimensional complex array comprising
            calibration_coefficients[channel, polarization], with each element
            representing a normalized coefficient, with (1.0, 0.0) being the
            normal, expected response for an ideal antenna.

            * channel - (int) channel is the index specifying the channels at the
                              beamformer output, i.e. considering only those channels
                              actually processed and beam assignments.
            * polarization index ranges from 0 to 3.

                * 0: X polarization direct element
                * 1: X->Y polarization cross element
                * 2: Y->X polarization cross element
                * 3: Y polarization direct element

        :type argin: list(float)

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> antenna = 2
        >>> complex_coefficients = [[complex(3.4, 1.2), complex(2.3, 4.1),
        >>>            complex(4.6, 8.2), complex(6.8, 2.4)]]*5
        >>> inp = list(itertools.chain.from_iterable(complex_coefficients))
        >>> out = [[v.real, v.imag] for v in inp]
        >>> coefficients = list(itertools.chain.from_iterable(out))
        >>> coefficients.insert(0, float(antenna))
        >>> input = list(itertools.chain.from_iterable(coefficients))
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("LoadCalibrationCoefficients", input)
        """
        handler = self.get_command_object("LoadCalibrationCoefficients")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class LoadCalibrationCurveCommand(ResponseCommand):
        """
        Class for handling the LoadCalibrationCurve(argin) command.
        """

        SUCCEEDED_MESSAGE = "LoadCalibrationCurve command completed OK"

        def do(self, argin):
            """
            Implementation of
            :py:meth:`.MccsTile.LoadCalibrationCurve`
            command functionality.

            :param argin: antenna, beam, calibration coefficients
            :type argin: list(float)

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)

            :raises ValueError: if the argin argument does not have the
                right length / structure
            """
            if len(argin) < 10:
                self.logger.error("Insufficient calibration coefficients")
                raise ValueError("Insufficient calibration coefficients")
            if len(argin[2:]) % 8 != 0:
                self.logger.error("Incomplete specification of coefficient")
                raise ValueError("Incomplete specification of coefficient")
            antenna = int(argin[0])
            beam = int(argin[1])
            calibration_coefficients = [
                [
                    complex(argin[i], argin[i + 1]),
                    complex(argin[i + 2], argin[i + 3]),
                    complex(argin[i + 4], argin[i + 5]),
                    complex(argin[i + 6], argin[i + 7]),
                ]
                for i in range(2, len(argin), 8)
            ]

            hardware_manager = self.target
            hardware_manager.load_calibration_curve(
                antenna, beam, calibration_coefficients
            )
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevVarDoubleArray", dtype_out="DevVarLongStringArray")
    @DebugIt()
    def LoadCalibrationCurve(self, argin):
        """
        Load calibration curve. This is the frequency dependent response for a single
        antenna and beam, as a function of frequency. It will be combined together with
        tapering coefficients and beam angles by ComputeCalibrationCoefficients, which
        will also make them active like SwitchCalibrationBank. The calibration
        coefficients do not include the geometric delay.

        :param argin: list comprises:

        * antenna - (int) is the antenna to which the coefficients will be applied.
        * beam    - (int) is the beam to which the coefficients will be applied.
        * calibration_coefficients - [array] a bidimensional complex array comprising
            calibration_coefficients[channel, polarization], with each element
            representing a normalized coefficient, with (1.0, 0.0) being the
            normal, expected response for an ideal antenna.

            * channel - (int) channel is the index specifying the channels at the
                              beamformer output, i.e. considering only those channels
                              actually processed and beam assignments.
            * polarization index ranges from 0 to 3.

                * 0: X polarization direct element
                * 1: X->Y polarization cross element
                * 2: Y->X polarization cross element
                * 3: Y polarization direct element

        :type argin: list(float)

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> antenna = 2
        >>> beam = 3
        >>> complex_coefficients = [[complex(3.4, 1.2), complex(2.3, 4.1),
        >>>            complex(4.6, 8.2), complex(6.8, 2.4)]]*5
        >>> inp = list(itertools.chain.from_iterable(complex_coefficients))
        >>> out = [[v.real, v.imag] for v in inp]
        >>> coefficients = list(itertools.chain.from_iterable(out))
        >>> coefficients.insert(0, float(antenna))
        >>> coefficients.insert(1, float(beam))
        >>> input = list(itertools.chain.from_iterable(coefficients))
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("LoadCalbrationCurve", input)
        """
        handler = self.get_command_object("LoadCalibrationCurve")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class LoadBeamAngleCommand(ResponseCommand):
        """
        Class for handling the LoadBeamAngle(argin) command.
        """

        SUCCEEDED_MESSAGE = "LoadBeamAngle command completed OK"

        def do(self, argin):
            """
            Implementation of
            :py:meth:`.MccsTile.LoadBeamAngle` command
            functionality.

            :param argin: angle coefficients
            :type argin: list(float)

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            hardware_manager.load_beam_angle(argin)
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_in="DevVarDoubleArray",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def LoadBeamAngle(self, argin):
        """
        angle_coefficients is an array of one element per beam, specifying a rotation
        angle, in radians, for the specified beam. The rotation is the same for all
        antennas. Default is 0 (no rotation). A positive pi/4 value transfers the X
        polarization to the Y polarization. The rotation is applied after regular
        calibration.

        :param argin: list of angle coefficients for each beam
        :type argin: list(float)

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> angle_coefficients = [3.4] * 16
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("LoadBeamAngle", angle_coefficients)
        """
        handler = self.get_command_object("LoadBeamAngle")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class LoadAntennaTaperingCommand(ResponseCommand):
        """
        Class for handling the LoadAntennaTapering(argin) command.
        """

        SUCCEEDED_MESSAGE = "LoadAntennaTapering command completed OK"

        def __init__(self, target, state_model, logger, antennas_per_tile):
            """
            Initialise a new LoadAntennaTaperingCommand instance.

            :param target: the object that this command acts upon; for
                example, the device for which this class implements the
                command
            :type target: object
            :param state_model: the state model that this command uses
                 to check that it is allowed to run, and that it drives
                 with actions.
            :type state_model:
                :py:class:`~ska_tango_base.DeviceStateModel`
            :param logger: the logger to be used by this Command. If not
                provided, then a default module logger will be used.
            :type logger: :py:class:`logging.Logger`
            :param antennas_per_tile: the number of antennas per tile
            :type antennas_per_tile: int
            """
            super().__init__(target, state_model, logger)
            self._antennas_per_tile = antennas_per_tile

        def do(self, argin):
            """
            Implementation of
            :py:meth:`.MccsTile.LoadAntennaTapering`
            command functionality.

            :param argin: beam index, antenna tapering coefficients
            :type argin: list(float)

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)

            :raises ValueError: if the argin argument does not have the
                right length / structure
            """
            if len(argin) < self._antennas_per_tile + 1:
                self.logger.error(
                    f"Insufficient coefficients should be {self._antennas_per_tile+1}"
                )
                raise ValueError(
                    f"Insufficient coefficients should be {self._antennas_per_tile+1}"
                )

            beam = int(argin[0])
            if beam < 0 or beam > 47:
                self.logger.error("Beam index should be in range 0 to 47")
                raise ValueError("Beam index should be in range 0 to 47")

            tapering = argin[1:]
            hardware_manager = self.target
            hardware_manager.load_antenna_tapering(beam, tapering)
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_in="DevVarDoubleArray",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def LoadAntennaTapering(self, argin):
        """
        tapering_coefficients is a vector contains a value for each antenna the TPM
        processes. Default at initialisation is 1.0.

        :param argin: beam index, list of tapering coefficients for each antenna
        :type argin: list(float)

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> beam = 2
        >>> tapering_coefficients = [3.4] * 16
        >>> tapering_coefficients.insert(0, float(beam))
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("LoadAntennaTapering", tapering_coefficients)
        """
        handler = self.get_command_object("LoadAntennaTapering")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class SwitchCalibrationBankCommand(ResponseCommand):
        """
        Class for handling the SwitchCalibrationBank(argin) command.
        """

        SUCCEEDED_MESSAGE = "SwitchCalibrationBank command completed OK"

        def do(self, argin):
            """
            Implementation of
            :py:meth:`.MccsTile.SwitchCalibrationBank`
            command functionality.

            :param argin: switch time
            :type argin: int

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            switch_time = argin
            hardware_manager = self.target
            hardware_manager.switch_calibration_bank(switch_time)
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_in="DevLong",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def SwitchCalibrationBank(self, argin):
        """
        Load the calibration coefficients at the specified time delay.

        :param argin: switch time
        :type argin: int

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("SwitchCalibrationBank", 10)
        """
        handler = self.get_command_object("SwitchCalibrationBank")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class SetPointingDelayCommand(ResponseCommand):
        """
        Class for handling the SetPointingDelay(argin) command.
        """

        SUCCEEDED_MESSAGE = "SetPointingDelay command completed OK"

        def __init__(self, target, state_model, logger, antennas_per_tile):
            """
            Initialise a new SetPointingDelayCommand instance.

            :param target: the object that this command acts upon; for
                example, the device for which this class implements the
                command
            :type target: object
            :param state_model: the state model that this command uses
                 to check that it is allowed to run, and that it drives
                 with actions.
            :type state_model:
                :py:class:`~ska_tango_base.DeviceStateModel`
            :param logger: the logger to be used by this Command. If not
                provided, then a default module logger will be used.
            :type logger: :py:class:`logging.Logger`
            :param antennas_per_tile: the number of antennas per tile
            :type antennas_per_tile: int
            """
            super().__init__(target, state_model, logger)
            self._antennas_per_tile = antennas_per_tile

        def do(self, argin):
            """
            Implementation of
            :py:meth:`.MccsTile.SetPointingDelay` command
            functionality.

            :param argin: an array containing a beam index and antenna
                delays
            :type argin: list(float)

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)

            :raises ValueError: if the argin argument does not have the
                right length / structure
            """
            if len(argin) != self._antennas_per_tile * 2 + 1:
                self.logger.error("Insufficient parameters")
                raise ValueError("Insufficient parameters")
            beam_index = int(argin[0])
            if beam_index < 0 or beam_index > 7:
                self.logger.error("Invalid beam index")
                raise ValueError("Invalid beam index")
            delay_array = []
            for i in range(self._antennas_per_tile):
                delay_array.append([argin[i * 2 + 1], argin[i * 2 + 2]])

            hardware_manager = self.target
            hardware_manager.set_pointing_delay(delay_array, beam_index)
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_in="DevVarDoubleArray",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def SetPointingDelay(self, argin):
        """
        Specifies the delay in seconds and the delay rate in seconds/second. The
        delay_array specifies the delay and delay rate for each antenna. beam_index
        specifies which beam is desired (range 0-7)

        :param argin: the delay in seconds and the delay rate in
            seconds/second.
        :type argin: list(float)

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("SetPointingDelay")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class LoadPointingDelayCommand(ResponseCommand):
        """
        Class for handling the LoadPointingDelay(argin) command.
        """

        SUCCEEDED_MESSAGE = "LoadPointingDelay command completed OK"

        def do(self, argin):
            """
            Implementation of
            :py:meth:`.MccsTile.LoadPointingDelay` command
            functionality.

            :param argin: load time
            :type argin: int

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            load_time = argin
            hardware_manager = self.target
            hardware_manager.load_pointing_delay(load_time)
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_in="DevLong",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def LoadPointingDelay(self, argin):
        """
        Loads the pointing delays at the specified time delay.

        :param argin: time delay (default = 0)
        :type argin: int

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("LoadPointingDelay", 10)
        """
        handler = self.get_command_object("LoadPointingDelay")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class StartBeamformerCommand(ResponseCommand):
        """
        Class for handling the StartBeamformer(argin) command.
        """

        SUCCEEDED_MESSAGE = "StartBeamformer command completed OK"

        def do(self, argin):
            """
            Implementation of
            :py:meth:`.MccsTile.StartBeamformer` command
            functionality.

            :param argin: a JSON-encoded dictionary of arguments
                "StartTime" and "Duration"
            :type argin: str

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            hardware_manager = self.target

            params = json.loads(argin)
            start_time = params.get("StartTime", 0)
            duration = params.get("Duration", -1)
            hardware_manager.start_beamformer(start_time, duration)
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def StartBeamformer(self, argin):
        """
        Start the beamformer at the specified time delay.

        :param argin: json dictionary with optional keywords:

        * StartTime - (int) start time
        * Duration - (int) if > 0 is a duration in frames * 256 (276.48 us)
                           if == -1 run forever

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"StartTime":10, "Duration":20}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("StartBeamformer", jstr)
        """
        handler = self.get_command_object("StartBeamformer")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class StopBeamformerCommand(ResponseCommand):
        """
        Class for handling the StopBeamformer() command.
        """

        SUCCEEDED_MESSAGE = "StopBeamformer command completed OK"

        def do(self):
            """
            Implementation of
            :py:meth:`.MccsTile.StopBeamformer` command
            functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            hardware_manager.stop_beamformer()
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def StopBeamformer(self):
        """
        Stop the beamformer.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("StopBeamformer")
        """
        handler = self.get_command_object("StopBeamformer")
        (return_code, message) = handler()
        return [[return_code], [message]]

    class ConfigureIntegratedChannelDataCommand(ResponseCommand):
        """
        Class for handling the ConfigureIntegratedChannelData(argin) command.
        """

        SUCCEEDED_MESSAGE = "ConfigureIntegratedChannelData command completed OK"

        def do(self, argin):
            """
            Stateless do-hook for implementation of
            :py:meth:`.MccsTile.ConfigureIntegratedChannelData`
            command functionality.

            :param argin: a JSON-encoded dictionary of arguments
                "integration time", "first_channel", "last_channel"
            :type argin: str

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            params = json.loads(argin)
            integration_time = params.get("IntegrationTime", 0.5)
            first_channel = params.get("FirstChannel", 0)
            last_channel = params.get("LastChannel", 511)

            hardware_manager = self.target
            hardware_manager.configure_integrated_channel_data(
                integration_time,
                first_channel,
                last_channel,
            )
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def ConfigureIntegratedChannelData(self, argin):
        """
        Configure and start the transmission of integrated channel data with the
        provided integration time, first channel and last channel. Data are sent
        continuously until the StopIntegratedChannelData command is run.

        :param argin: json dictionary with optional keywords:

        * integration time - (float) in seconds (default = 0.5)
        * first_channel - (int) default 0
        * last_channel - (int) default 511

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("ConfigureIntegratedChannelData", 6.284, 0, 511)
        """
        handler = self.get_command_object("ConfigureIntegratedChannelData")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class StopIntegratedChannelDataCommand(ResponseCommand):
        """
        Class for handling the StopIntegratedChannelData command.
        """

        SUCCEEDED_MESSAGE = "StopIntegratedChannelData command completed OK"

        def do(self):
            """
            Implementation of
            :py:meth:`.MccsTile.StopIntegratedChannelData`
            command functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            hardware_manager.stop_integrated_channel_data()
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def StopIntegratedChannelData(self):
        """
        Stop the integrated channel data.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("StopIntegratedChannelData")
        (return_code, message) = handler()
        return [[return_code], [message]]

    class ConfigureIntegratedBeamDataCommand(ResponseCommand):
        """
        Class for handling the ConfigureIntegratedBeamData(argin) command.
        """

        SUCCEEDED_MESSAGE = "ConfigureIntegratedBeamData command completed OK"

        def do(self, argin):
            """
            Implementation of
            :py:meth:`.MccsTile.ConfigureIntegratedBeamData`
            command functionality.

            :param argin: a JSON-encoded dictionary of arguments
                "integration time", "first_channel", "last_channel"
            :type argin: str

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            params = json.loads(argin)
            integration_time = params.get("IntegrationTime", 0.5)
            first_channel = params.get("FirstChannel", 0)
            last_channel = params.get("LastChannel", 191)

            hardware_manager = self.target
            hardware_manager.configure_integrated_beam_data(
                integration_time,
                first_channel,
                last_channel,
            )
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def ConfigureIntegratedBeamData(self, argin):
        """
        Configure the transmission of integrated beam data with the provided integration
        time, the first channel and the last channel. The data are sent continuously
        until the StopIntegratedBeamData command is run.

        :param argin: json dictionary with optional keywords:

        * integration time - (float) in seconds (default = 0.5)
        * first_channel - (int) default 0
        * last_channel - (int) default 191

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("ConfigureIntegratedBeamData", 3.142, 0, 191)
        """
        handler = self.get_command_object("ConfigureIntegratedBeamData")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class StopIntegratedBeamDataCommand(ResponseCommand):
        """
        Class for handling the StopIntegratedBeamData command.
        """

        SUCCEEDED_MESSAGE = "StopIntegratedBeamData command completed OK"

        def do(self):
            """
            Implementation of
            :py:meth:`.MccsTile.StopIntegratedBeamData`
            command functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            hardware_manager.stop_integrated_beam_data()
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def StopIntegratedBeamData(self):
        """
        Stop the integrated beam data.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("StopIntegratedBeamData")
        (return_code, message) = handler()
        return [[return_code], [message]]

    class StopIntegratedDataCommand(ResponseCommand):
        """
        Class for handling the StopIntegratedData command.
        """

        SUCCEEDED_MESSAGE = "StopIntegratedData command completed OK"

        def do(self):
            """
            Implementation of
            :py:meth:`.MccsTile.StopIntegratedData`
            command functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            hardware_manager.stop_integrated_data()
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def StopIntegratedData(self):
        """
        Stop the integrated  data.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("StopIntegratedData")
        (return_code, message) = handler()
        return [[return_code], [message]]

    class SendRawDataCommand(ResponseCommand):
        """
        Class for handling the SendRawData(argin) command.
        """

        SUCCEEDED_MESSAGE = "SendRawData command completed OK"

        def do(self, argin):
            """
            Implementation of
            :py:meth:`.MccsTile.SendRawData` command
            functionality.

            :param argin: a JSON-encoded dictionary of arguments
            :type argin: str

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            params = json.loads(argin)
            sync = params.get("Sync", False)
            timestamp = params.get("Timestamp", None)
            seconds = params.get("Seconds", 0.2)

            hardware_manager = self.target
            hardware_manager.send_raw_data(sync, timestamp, seconds)
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def SendRawData(self, argin):
        """
        Transmit a snapshot containing raw antenna data.

        :param argin: json dictionary with optional keywords:

        * Sync - (bool) synchronised flag
        * Timestamp - (int??) When to start
        * Seconds - (float) When to synchronise

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"Sync":True, "Seconds": 0.2}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SendRawData", jstr)
        """
        handler = self.get_command_object("SendRawData")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class SendChannelisedDataCommand(ResponseCommand):
        """
        Class for handling the SendChannelisedData(argin) command.
        """

        SUCCEEDED_MESSAGE = "SendChannelisedData command completed OK"

        def do(self, argin):
            """
            Implementation of
            :py:meth:`.MccsTile.SendChannelisedData` command
            functionality.

            :param argin: a JSON-encoded dictionary of arguments
            :type argin: str

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            params = json.loads(argin)
            number_of_samples = params.get("NSamples", 1024)
            first_channel = params.get("FirstChannel", 0)
            last_channel = params.get("LastChannel", 511)
            timestamp = params.get("Timestamp", None)
            seconds = params.get("Seconds", 0.2)

            hardware_manager = self.target
            hardware_manager.send_channelised_data(
                number_of_samples,
                first_channel,
                last_channel,
                timestamp,
                seconds,
            )
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def SendChannelisedData(self, argin):
        """
        Transmit a snapshot containing channelized data totalling number_of_samples
        spectra.

        :param argin: json dictionary with optional keywords:

        * NSamples - (int) number of spectra to send
        * FirstChannel - (int) first channel to send
        * LastChannel - (int) last channel to send
        * Timestamp - (int??) When to start
        * Seconds - (float) When to synchronise

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"FirstChannel":10, "LastChannel": 200, "Seconds": 0.5}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SendChannelisedData", jstr)
        """
        handler = self.get_command_object("SendChannelisedData")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class SendChannelisedDataContinuousCommand(ResponseCommand):
        """
        Class for handling the SendChannelisedDataContinuous(argin) command.
        """

        SUCCEEDED_MESSAGE = "SendChannelisedDataContinuous command completed OK"

        def do(self, argin):
            """
            Implementation of
            :py:meth:`.MccsTile.SendChannelisedDataContinuous`
            command functionality.

            :param argin: a JSON-encoded dictionary of arguments
            :type argin: str

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)

            :raises ValueError: if the JSON input lacks mandatory parameters

            :todo: Mandatory JSON parameters should be handled by validation
                against a schema
            """
            params = json.loads(argin)
            channel_id = params.get("ChannelID")
            if channel_id is None:
                self.logger.error("ChannelID is a mandatory parameter")
                raise ValueError("ChannelID is a mandatory parameter")
            number_of_samples = params.get("NSamples", 128)
            wait_seconds = params.get("WaitSeconds", 0)
            timestamp = params.get("Timestamp", None)
            seconds = params.get("Seconds", 0.2)

            hardware_manager = self.target
            hardware_manager.send_channelised_data_continuous(
                channel_id, number_of_samples, wait_seconds, timestamp, seconds
            )
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def SendChannelisedDataContinuous(self, argin):
        """
        Send data from channel channel continuously (until stopped)

        :param argin: json dictionary with 1 mandatory and optional keywords:

        * ChannelID - (int) channel_id (Mandatory)
        * NSamples -  (int) number of spectra to send
        * WaitSeconds - (int) Wait time before sending data
        * Timestamp - (int??) When to start
        * Seconds - (float) When to synchronise

        :type argin: str

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"ChannelID":2, "NSamples":256, "Seconds": 0.5}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SendChannelisedDataContinuous", jstr)
        """
        handler = self.get_command_object("SendChannelisedDataContinuous")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class SendBeamDataCommand(ResponseCommand):
        """
        Class for handling the SendBeamData(argin) command.
        """

        SUCCEEDED_MESSAGE = "SendBeamData command completed OK"

        def do(self, argin):
            """
            Implementation of
            :py:meth:`.MccsTile.SendBeamData` command
            functionality.

            :param argin: a JSON-encoded dictionary of arguments
            :type argin: str

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            params = json.loads(argin)
            timestamp = params.get("Timestamp", None)
            seconds = params.get("Seconds", 0.2)

            hardware_manager = self.target
            hardware_manager.send_beam_data(timestamp, seconds)
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def SendBeamData(self, argin):
        """
        Transmit a snapshot containing beamformed data.

        :param argin: json dictionary with optional keywords:

        * Timestamp - (string??) When to send
        * Seconds - (float) When to synchronise

        :type argin: str

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"Seconds": 0.5}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SendBeamData", jstr)
        """
        handler = self.get_command_object("SendBeamData")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class StopDataTransmissionCommand(ResponseCommand):
        """
        Class for handling the StopDataTransmission() command.
        """

        SUCCEEDED_MESSAGE = "StopDataTransmission command completed OK"

        def do(self):
            """
            Implementation of
            :py:meth:`.MccsTile.StopDataTransmission`
            command functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            hardware_manager.stop_data_transmission()
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def StopDataTransmission(self):
        """
        Stop data transmission from board.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("StopDataTransmission")
        """
        handler = self.get_command_object("StopDataTransmission")
        (return_code, message) = handler()
        return [[return_code], [message]]

    class ComputeCalibrationCoefficientsCommand(ResponseCommand):
        """
        Class for handling the ComputeCalibrationCoefficients() command.
        """

        SUCCEEDED_MESSAGE = "ComputeCalibrationCoefficients command completed OK"

        def do(self):
            """
            Implementation of
            :py:meth:`.MccsTile.ComputeCalibrationCoefficients`
            command functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            hardware_manager.compute_calibration_coefficients()
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def ComputeCalibrationCoefficients(self):
        """
        Compute the calibration coefficients from previously specified gain curves,
        tapering weights and beam angles, load them in the hardware. It must be followed
        by switch_calibration_bank() to make these active.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("ComputeCalibrationCoefficients")
        """
        handler = self.get_command_object("ComputeCalibrationCoefficients")
        (return_code, message) = handler()
        return [[return_code], [message]]

    class StartAcquisitionCommand(ResponseCommand):
        """
        Class for handling the StartAcquisition(argin) command.
        """

        SUCCEEDED_MESSAGE = "StartAcquisition command completed OK"

        def do(self, argin):
            """
            Implementation of
            :py:meth:`.MccsTile.StartAcquisition` command
            functionality.

            :param argin: a JSON-encoded dictionary of arguments
            :type argin: str

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            params = json.loads(argin)
            start_time = params.get("StartTime", None)
            delay = params.get("Delay", 2)

            hardware_manager = self.target
            hardware_manager.start_acquisition(start_time, delay)
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def StartAcquisition(self, argin):
        """
        Start data acquisition.

        :param argin: json dictionary with optional keywords:

        * StartTime - (int) start time
        * Delay - (int) delay start

        :type argin: str

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"StartTime":10, "Delay":20}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("StartAcquisition", jstr)
        """
        handler = self.get_command_object("StartAcquisition")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class SetTimeDelaysCommand(ResponseCommand):
        """
        Class for handling the SetTimeDelays(argin) command.
        """

        SUCCEEDED_MESSAGE = "SetTimeDelays command completed OK"

        def do(self, argin):
            """
            Implementation of
            :py:meth:`.MccsTile.SetTimeDelays` command
            functionality.

            :param argin: time delays
            :type argin: list(float)

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            delays = argin
            hardware_manager = self.target
            hardware_manager.set_time_delays(delays)
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_in="DevVarDoubleArray",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def SetTimeDelays(self, argin):
        """
        Set coarse zenith delay for input ADC streams Delay specified in nanoseconds,
        nominal is 0.

        :param argin: the delay in samples, positive delay adds delay
                       to the signal stream
        :type argin: list(int)

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> delays = [3.4] * n (How many & int or float : Alessio?)
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("SetTimedelays", delays)
        """
        handler = self.get_command_object("SetTimeDelays")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class SetCspRoundingCommand(ResponseCommand):
        """
        Class for handling the SetCspRounding(argin) command.
        """

        SUCCEEDED_MESSAGE = "SetCspRounding command completed OK"

        def do(self, argin):
            """
            Implementation of
            :py:meth:`.MccsTile.SetCspRounding` command
            functionality.

            :param argin: csp rounding
            :type argin: float

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            rounding = argin
            hardware_manager = self.target
            hardware_manager.set_csp_rounding(rounding)
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_in="DevDouble",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def SetCspRounding(self, argin):
        """
        Set output rounding for CSP.

        :param argin: the rounding
        :type argin: float

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("SetCspRounding", 3.142)
        """
        handler = self.get_command_object("SetCspRounding")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class SetLmcIntegratedDownloadCommand(ResponseCommand):
        """
        Class for handling the SetLmcIntegratedDownload(argin) command.
        """

        SUCCEEDED_MESSAGE = "SetLmcIntegratedDownload command completed OK"

        def do(self, argin):
            """
            Implementation of
            :py:meth:`.MccsTile.SetLmcIntegratedDownload`
            command functionality.

            :param argin: a JSON-encoded dictionary of arguments
            :type argin: str

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)

            :raises ValueError: if the JSON input lacks mandatory parameters

            :todo: Mandatory JSON parameters should be handled by validation
                against a schema
            """
            params = json.loads(argin)
            mode = params.get("Mode", None)
            if mode is None:
                self.logger.error("Mode is a mandatory parameter")
                raise ValueError("Mode is a mandatory parameter")
            channel_payload_length = params.get("ChannelPayloadLength", 2)
            beam_payload_length = params.get("BeamPayloadLength", 2)
            dst_ip = params.get("DstIP", None)
            src_port = params.get("SrcPort", 0xF0D0)
            dst_port = params.get("DstPort", 4660)
            lmc_mac = params.get("LmcMac", None)

            hardware_manager = self.target
            hardware_manager.set_lmc_integrated_download(
                mode,
                channel_payload_length,
                beam_payload_length,
                dst_ip,
                src_port,
                dst_port,
                lmc_mac,
            )
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def SetLmcIntegratedDownload(self, argin):
        """
        Configure link and size of control data.

        :param argin: json dictionary with optional keywords:

        * Mode - (string) '1g' or '10g' (Mandatory)
        * ChannelPayloadLength - (int) SPEAD payload length for integrated channel data
        * BeamPayloadLength - (int) SPEAD payload length for integrated beam data
        * DstIP - (string) Destination IP
        * SrcPort - (int) Source port for integrated data streams
        * DstPort - (int) Destination port for integrated data streams
        * LmcMac: - (int) LMC Mac address is required for 10G lane configuration

        :type argin: str

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"Mode": "1G", "ChannelPayloadLength":4,
                    "BeamPayloadLength": 6, DstIP="10.0.1.23"}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SetLmcIntegratedDownload", jstr)
        """
        handler = self.get_command_object("SetLmcIntegratedDownload")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class SendRawDataSynchronisedCommand(ResponseCommand):
        """
        Class for handling the SendRawDataSynchronised(argin) command.
        """

        SUCCEEDED_MESSAGE = "SendRawDataSynchronised command completed OK"

        def do(self, argin):
            """
            Implementation of
            :py:meth:`.MccsTile.SendRawDataSynchronised`
            command functionality.

            :param argin: a JSON-encoded dictionary of arguments
            :type argin: str

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            params = json.loads(argin)
            timestamp = params.get("Timestamp", None)
            seconds = params.get("Seconds", 0.1)

            hardware_manager = self.target
            hardware_manager.send_raw_data(
                sync=True, timestamp=timestamp, seconds=seconds
            )
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    def SendRawDataSynchronised(self, argin):
        """
        Send synchronised raw data.

        :param argin: json dictionary with optional keywords:

        * Timestamp - (string??) When to send
        * Seconds - (float) When to synchronise

        :type argin: str

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"Seconds": 0.5}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SendRawDataSynchronised", jstr)
        """
        handler = self.get_command_object("SendRawDataSynchronised")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class SendChannelisedDataNarrowbandCommand(ResponseCommand):
        """
        Class for handling the SendChannelisedDataNarrowband(argin) command.
        """

        SUCCEEDED_MESSAGE = "SendChannelisedDataNarrowband command completed OK"

        def do(self, argin):
            """
            Implementation of
            :py:meth:`.MccsTile.SendChannelisedDataNarrowband`
            command functionality.

            :param argin: a JSON-encoded dictionary of arguments
            :type argin: str

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)

            :raises ValueError: if the JSON input lacks mandatory parameters

            :todo: Mandatory JSON parameters should be handled by validation
                against a schema
            """
            params = json.loads(argin)
            frequency = params.get("Frequency", None)
            if frequency is None:
                self.logger.error("Frequency is a mandatory parameter")
                raise ValueError("Frequency is a mandatory parameter")
            round_bits = params.get("RoundBits", None)
            if round_bits is None:
                self.logger.error("RoundBits is a mandatory parameter")
                raise ValueError("RoundBits is a mandatory parameter")
            number_of_samples = params.get("NSamples", 128)
            wait_seconds = params.get("WaitSeconds", 0)
            timestamp = params.get("Timestamp", None)
            seconds = params.get("Seconds", 0.2)
            hardware_manager = self.target
            hardware_manager.send_channelised_data_narrowband(
                frequency,
                round_bits,
                number_of_samples,
                wait_seconds,
                timestamp,
                seconds,
            )
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def SendChannelisedDataNarrowband(self, argin):
        """
        Continuously send channelised data from a single channel end data from channel
        channel continuously (until stopped)

        This is a special mode used for UAV campaigns and not really
        part of the standard signal processing chain. I don’t know if
        this mode will be kept or not.

        :param argin: json dictionary with 2 mandatory and optional keywords:

        * Frequency - (int) Sky frequency to transmit
        * RoundBits - (int)  Specify which bits to round
        * NSamples -  (int) number of spectra to send
        * WaitSeconds - (int) Wait time before sending data
        * Timeout - (int) When to stop
        * Timestamp - (string??) When to start
        * Seconds - (float) When to synchronise

        :type argin: str

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"Frequency":2000, "RoundBits":256, "NSamples":256,
                    "WaitSeconds": 10, "Seconds": 0.5}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SendChannelisedDataNarrowband", jstr)
        """
        handler = self.get_command_object("SendChannelisedDataNarrowband")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class TweakTransceiversCommand(ResponseCommand):
        """
        Class for handling the TweakTransceivers() command.
        """

        SUCCEEDED_MESSAGE = "TweakTransceivers command completed OK"

        def do(self):
            """
            Implementation of
            :py:meth:`.MccsTile.TweakTransceivers` command
            functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            hardware_manager.tweak_transceivers()
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def TweakTransceivers(self):
        """
        Tweak the transceivers.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("tweak_transceivers")
        """
        handler = self.get_command_object("TweakTransceivers")
        (return_code, message) = handler()
        return [[return_code], [message]]

    class PostSynchronisationCommand(ResponseCommand):
        """
        Class for handling the PostSynchronisation() command.
        """

        SUCCEEDED_MESSAGE = "PostSynchronisation command completed OK"

        def do(self):
            """
            Implementation of
            :py:meth:`.MccsTile.PostSynchronisation` command
            functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            hardware_manager.post_synchronisation()
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def PostSynchronisation(self):
        """
        Post tile configuration synchronization.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("PostSynchronisation")
        """
        handler = self.get_command_object("PostSynchronisation")
        (return_code, message) = handler()
        return [[return_code], [message]]

    class SyncFpgasCommand(ResponseCommand):
        """
        Class for handling the SyncFpgas() command.
        """

        SUCCEEDED_MESSAGE = "SyncFpgas command completed OK"

        def do(self):
            """
            Implementation of
            :py:meth:`.MccsTile.SyncFpgas` command
            functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            hardware_manager.sync_fpgas()
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def SyncFpgas(self):
        """
        Synchronise the FPGAs.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("SyncFpgas")
        """
        handler = self.get_command_object("SyncFpgas")
        (return_code, message) = handler()
        return [[return_code], [message]]

    class CalculateDelayCommand(ResponseCommand):
        """
        Class for handling the CalculateDelay(argin) command.
        """

        SUCCEEDED_MESSAGE = "CalculateDelay command completed OK"

        def do(self, argin):
            """
            Implementation of
            :py:meth:`.MccsTile.CalculateDelay` command
            functionality.

            :param argin: a JSON-encoded dictionary of arguments
            :type argin: str

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)

            :raises ValueError: if the JSON input lacks
                mandatory parameters

            :todo: Mandatory JSON parameters should be handled by validation
                against a schema
            """
            params = json.loads(argin)
            current_delay = params.get("CurrentDelay", None)
            if current_delay is None:
                self.logger.error("CurrentDelay is a mandatory parameter")
                raise ValueError("CurrentDelay is a mandatory parameter")
            current_tc = params.get("CurrentTC", None)
            if current_tc is None:
                self.logger.error("CurrentTC is a mandatory parameter")
                raise ValueError("CurrentTC is a mandatory parameter")
            ref_lo = params.get("RefLo", None)
            if ref_lo is None:
                self.logger.error("RefLo is a mandatory parameter")
                raise ValueError("RefLo is a mandatory parameter")
            ref_hi = params.get("RefHi", None)
            if ref_hi is None:
                self.logger.error("RefHi is a mandatory parameter")
                raise ValueError("RefHi is a mandatory parameter")

            hardware_manager = self.target
            hardware_manager.calculate_delay(current_delay, current_tc, ref_lo, ref_hi)
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def CalculateDelay(self, argin):
        """
        Calculate delay.

        :param argin: json dictionary with 4 mandatory keywords:

        * CurrentDelay - (float??) Current delay
        * CurrentTC - (float??) Current phase register terminal count
        * RefLo - (float??) Low reference
        * RefHi -(float??) High reference

        :type argin: str

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"CurrentDelay":0.4, "CurrentTC":56.2, "RefLo":3.0, "RefHi":78.9}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("CalculateDelay", jstr)
        """
        handler = self.get_command_object("CalculateDelay")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class ConfigureTestGeneratorCommand(BaseCommand):
        """
        Class for handling the ConfigureTestGenerator(argin) command.
        """

        SUCCEEDED_MESSAGE = "ConfigureTestGenerator command completed OK"

        def do(self, argin):
            """
            Implementation of
            :py:meth:`.MccsTile.ConfigureTestGenerator` command
            functionality.

            :param argin: a JSON-encoded dictionary of arguments
            :type argin: str
            :raises ValueError: if the JSON input has invalid parameters

            :todo: Mandatory JSON parameters should be handled by validation
                   against a schema
            :return: A tuple containing a return code and a string
                   message indicating status. The message is for
                   information purpose only.
            :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            hardware_manager = self.target

            params = json.loads(argin)
            active = False
            set_time = params.get("SetTime", 0)
            if "ToneFrequency" in params:
                frequency0 = params["ToneFrequency"]
                amplitude0 = params.get("ToneAmplitude", 1.0)
                active = True
            else:
                frequency0 = 0.0
                amplitude0 = 0.0

            if "Tone2Frequency" in params:
                frequency1 = params["Tone2Frequency"]
                amplitude1 = params.get("Tone2Amplitude", 1.0)
                active = True
            else:
                frequency1 = 0.0
                amplitude1 = 0.0

            if "NoiseAmplitude" in params:
                amplitude_noise = params.get("NoiseAmplitude", 1.0)
                active = True
            else:
                amplitude_noise = 0.0

            if "PulseFrequency" in params:
                pulse_code = params["PulseFrequency"]
                if (pulse_code < 0) or (pulse_code > 7):
                    raise ValueError("PulseFrequency must be between 0 and 7")
                amplitude_pulse = params.get("PulseAmplitude", 1.0)
                active = True
            else:
                pulse_code = 7
                amplitude_pulse = 0.0

            hardware_manager.configure_test_generator(
                frequency0,
                amplitude0,
                frequency1,
                amplitude1,
                amplitude_noise,
                pulse_code,
                amplitude_pulse,
                set_time,
            )

            chans = params.get("AdcChannels")
            inputs = 0
            if chans is None:
                if active:
                    inputs = 0xFFFFFFFF
            else:
                for channel in chans:
                    inputs = inputs | (1 << channel)
            hardware_manager.test_generator_input_select(inputs)
            hardware_manager.test_generator_active = active
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

        def check_allowed(self):
            """
            command is allowed only in maintenance mode.

            :returns: whether the command is allowed
            :rtype: bool
            """
            return self.state_model.admin_mode == AdminMode.MAINTENANCE

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def ConfigureTestGenerator(self, argin):
        """
        Set the test signal generator.

        :param argin: json dictionary with keywords:

        * ToneFrequency: first tone frequency, in Hz. The frequency
            is rounded to the resolution of the generator. If this
            is not specified, the tone generator is disabled.
        * ToneAmplitude: peak tone amplitude, normalized to 31.875 ADC
            units. The amplitude is rounded to 1/8 ADC unit. Default
            is 1.0. A value of -1.0 keeps the previously set value.
        * Tone2Frequency: frequency for the second tone. Same
            as ToneFrequency.
        * Tone2Amplitude: peak tone amplitude for the second tone.
            Same as ToneAmplitude.
        * NoiseAmplitude: RMS amplitude of the pseudorandom Gaussian
            white noise, normalized to 26.03 ADC units.
        * PulseFrequency: frequency of the periodic pulse. A code
            in the range 0 to 7, corresponding to (16, 12, 8, 6, 4, 3, 2)
            times the ADC frame frequency.
        * PulseAmplitude: peak amplitude of the periodic pulse, normalized
            to 127 ADC units. Default is 1.0. A value of -1.0 keeps the
            previously set value.
        * SetTime: time at which the generator is set, for synchronization
            among different TPMs.
        * AdcChannels: list of adc channels which will be substituted with
            the test signal. Channels are numbered from 0 to 31, with each
            even-odd pair (2N, 2N+1) corresponding to X and Y polarizations
            of channel N. Default to all signals if at least one generator
            is specified, or none if no generator is specified (empty
            json string).

        :type argin: str

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"ToneFrequency": 150e6, "ToneAmplitude": 0.1,
                "NoiseAmplitude": 0.9, "PulseFrequency": 7, "LoadTime":0}
        >>> jstr = json.dumps(dict)
        >>> values = dp.command_inout("ConfigureTestGenerator", jstr)
        """
        handler = self.get_command_object("ConfigureTestGenerator")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]


# ----------
# Run server
# ----------
def main(args=None, **kwargs):
    """
    Entry point for module.

    :param args: positional arguments
    :type args: list
    :param kwargs: named arguments
    :type kwargs: dict

    :return: exit code
    :rtype: int
    """
    return MccsTile.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
