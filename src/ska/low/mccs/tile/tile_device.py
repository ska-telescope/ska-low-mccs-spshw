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
__all__ = ["MccsTile", "main"]

import json
import numpy as np
import threading
import os.path

from tango import DebugIt, EnsureOmniThread, DevState
from tango.server import attribute, command
from tango.server import device_property

from ska.base import SKABaseDevice
from ska.base.control_model import HealthState, SimulationMode
from ska.base.commands import BaseCommand, ResponseCommand, ResultCode

from ska.low.mccs.events import EventManager
from ska.low.mccs.hardware import PowerMode
from ska.low.mccs.health import HealthModel
from ska.low.mccs.tile import TileHardwareManager
from ska.low.mccs.utils import backoff_connect


class TilePowerManager:
    """
    This class performs tile management on behalf of the MCCS Tile
    device.

    It has a simply job; all it needs to do is talk to the subrack that
    houses this TPM, to ensure that the TPM is supplied/denied power as
    required.
    """

    def __init__(self, subrack_fqdn, subrack_bay, logger):
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
        """
        self._logger = logger
        self._power_mode = PowerMode.UNKNOWN

        self._subrack = backoff_connect(subrack_fqdn, logger)
        self._subrack_bay = subrack_bay

        if not self._subrack.IsTpmOn(self._subrack_bay):
            self._power_mode = PowerMode.OFF
        else:
            self._power_mode = PowerMode.ON

    def off(self):
        """
        Turn off power to the TPM.

        :return: whether the command was successful or not, or None if
            there was nothing to do.
        :rtype: bool

        :raises NotImplementedError: if our call to PowerOffTpm gets a
            ResultCode other than OK or FAILED
        """
        if not self._subrack.IsTpmOn(self._subrack_bay):
            return None  # already off

        [[result_code], [_]] = self._subrack.PowerOffTpm(self._subrack_bay)
        if result_code == ResultCode.OK:
            self._power_mode = PowerMode.OFF
            return True
        elif result_code == ResultCode.FAILED:
            return False
        else:
            raise NotImplementedError(
                f"Subrack.PowerOffTpm returned unexpected ResultCode {result_code}."
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
        if self._subrack.IsTpmOn(self._subrack_bay):
            return None  # already off

        [[result_code], [_]] = self._subrack.PowerOnTpm(self._subrack_bay)
        if result_code == ResultCode.OK:
            self._power_mode = PowerMode.ON
            return True
        elif result_code == ResultCode.FAILED:
            return False
        else:
            raise NotImplementedError(
                f"Subrack.PowerOnTpm returned unexpected ResultCode {result_code}."
            )

    @property
    def power_mode(self):
        """
        Return the power mode of this PowerManager object.

        :return: the power mode of thei PowerManager object
        :rtype: :py:class:`~ska.low.mccs.hardware.PowerMode`
        """
        return self._power_mode


class MccsTile(SKABaseDevice):
    """
    The Tile Device represents the TANGO interface to a Tile (TPM) unit.

    This class is a subclass of :py:class:`ska.base.SKABaseDevice`.

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

    # TODO: These properties are not currently being used in any way.
    # Can they be removed, or do they need to be handled somehow?
    # LmcIp = device_property(dtype=str, default_value="0.0.0.0")
    # DstPort = device_property(dtype=int, default_value=30000)

    # ---------------
    # General methods
    # ---------------

    class InitCommand(SKABaseDevice.InitCommand):
        """
        Class that implements device initialisation for the MCCS Tile is
        managed under the hood; the basic sequence is:

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
                :py:class:`~ska.base.DeviceStateModel`
            :param logger: the logger to be used by this Command. If not
                provided, then a default module logger will be used.
            :type logger: :py:class:`logging.Logger`
            """
            super().__init__(target, state_model, logger)

            self._thread = None
            self._lock = threading.Lock()
            self._interrupt = False

        def do(self):
            """
            Initialises the attributes and properties of the MCCS Tile
            device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            (result_code, message) = super().do()
            device = self.target

            # TODO: the default value for simulationMode should be
            # FALSE, but we don't have real hardware to test yet, so we
            # can't take our devices out of simulation mode. However,
            # simulationMode is a memorized attribute, and
            # pytango.test_context.MultiDeviceTestContext will soon
            # support memorized attributes. Once it does, we should
            # figure out how to inject memorized values into our real
            # tango deployment, then start honouring the default of
            # FALSE by removing this next line.
            device._simulation_mode = SimulationMode.TRUE
            device.hardware_manager = None

            device._logical_tile_id = 0
            device._subarray_id = 0
            device._station_id = 0

            device._csp_destination_ip = ""
            device._csp_destination_mac = ""
            device._csp_destination_port = 0

            device._antenna_ids = []

            self._thread = threading.Thread(
                target=self._initialise_connections, args=(device,)
            )
            with self._lock:
                self._thread.start()
                return (ResultCode.STARTED, "Init command started")

        def _initialise_connections(self, device):
            """
            Thread target for asynchronous initialisation of connections
            to external entities such as hardware and other devices.

            :param device: the device being initialised
            :type device: :py:class:`~ska.base.SKABaseDevice`
            """
            # https://pytango.readthedocs.io/en/stable/howto.html
            # #using-clients-with-multithreading
            with EnsureOmniThread():
                self._initialise_hardware_management(device)
                if self._interrupt:
                    self._thread = None
                    self._interrupt = False
                    return
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

        def _initialise_hardware_management(self, device):
            """
            Initialise the connection to the hardware being managed by
            this device. May also register commands that depend upon a
            connection to that hardware.

            :param device: the device for which a connection to the
                hardware is being initialised
            :type device: :py:class:`~ska.base.SKABaseDevice`
            """
            device.logger.info(
                "Initialising hardware manager with ip"
                + device.TpmIp
                + ":"
                + str(device.TpmCpldPort)
            )
            device.hardware_manager = TileHardwareManager(
                device._simulation_mode, device.logger, device.TpmIp, device.TpmCpldPort
            )
            args = (device.hardware_manager, device.state_model, device.logger)
            device.register_command_object(
                "Initialise", device.InitialiseCommand(*args)
            )
            device.register_command_object(
                "GetFirmwareAvailable", device.GetFirmwareAvailableCommand(*args)
            )
            device.register_command_object(
                "DownloadFirmware", device.DownloadFirmwareCommand(*args)
            )
            device.register_command_object(
                "ProgramCPLD", device.ProgramCPLDCommand(*args)
            )
            device.register_command_object(
                "GetRegisterList", device.GetRegisterListCommand(*args)
            )
            device.register_command_object(
                "ReadRegister", device.ReadRegisterCommand(*args)
            )
            device.register_command_object(
                "WriteRegister", device.WriteRegisterCommand(*args)
            )
            device.register_command_object(
                "ReadAddress", device.ReadAddressCommand(*args)
            )
            device.register_command_object(
                "WriteAddress", device.WriteAddressCommand(*args)
            )
            device.register_command_object(
                "Configure40GCore", device.Configure40GCoreCommand(*args)
            )
            device.register_command_object(
                "Get40GCoreConfiguration", device.Get40GCoreConfigurationCommand(*args)
            )
            device.register_command_object(
                "SetLmcDownload", device.SetLmcDownloadCommand(*args)
            )
            device.register_command_object(
                "SetChanneliserTruncation",
                device.SetChanneliserTruncationCommand(*args),
            )
            device.register_command_object(
                "SetBeamFormerRegions", device.SetBeamFormerRegionsCommand(*args)
            )
            device.register_command_object(
                "ConfigureStationBeamformer",
                device.ConfigureStationBeamformerCommand(*args),
            )
            device.register_command_object(
                "LoadCalibrationCoefficients",
                device.LoadCalibrationCoefficientsCommand(*args),
            )
            device.register_command_object(
                "LoadBeamAngle", device.LoadBeamAngleCommand(*args)
            )

            device.register_command_object(
                "SwitchCalibrationBank", device.SwitchCalibrationBankCommand(*args)
            )
            device.register_command_object(
                "LoadPointingDelay", device.LoadPointingDelayCommand(*args)
            )
            device.register_command_object(
                "StartBeamformer", device.StartBeamformerCommand(*args)
            )
            device.register_command_object(
                "StopBeamformer", device.StopBeamformerCommand(*args)
            )
            device.register_command_object(
                "ConfigureIntegratedChannelData",
                device.ConfigureIntegratedChannelDataCommand(*args),
            )
            device.register_command_object(
                "ConfigureIntegratedBeamData",
                device.ConfigureIntegratedBeamDataCommand(*args),
            )
            device.register_command_object(
                "SendRawData", device.SendRawDataCommand(*args)
            )
            device.register_command_object(
                "SendChannelisedData", device.SendChannelisedDataCommand(*args)
            )
            device.register_command_object(
                "SendChannelisedDataContinuous",
                device.SendChannelisedDataContinuousCommand(*args),
            )
            device.register_command_object(
                "SendBeamData", device.SendBeamDataCommand(*args)
            )
            device.register_command_object(
                "StopDataTransmission", device.StopDataTransmissionCommand(*args)
            )
            device.register_command_object(
                "ComputeCalibrationCoefficients",
                device.ComputeCalibrationCoefficientsCommand(*args),
            )
            device.register_command_object(
                "StartAcquisition", device.StartAcquisitionCommand(*args)
            )
            device.register_command_object(
                "SetTimeDelays", device.SetTimeDelaysCommand(*args)
            )
            device.register_command_object(
                "SetCspRounding", device.SetCspRoundingCommand(*args)
            )
            device.register_command_object(
                "SetLmcIntegratedDownload",
                device.SetLmcIntegratedDownloadCommand(*args),
            )
            device.register_command_object(
                "SendRawDataSynchronised", device.SendRawDataSynchronisedCommand(*args)
            )
            device.register_command_object(
                "SendChannelisedDataNarrowband",
                device.SendChannelisedDataNarrowbandCommand(*args),
            )
            device.register_command_object(
                "TweakTransceivers", device.TweakTransceiversCommand(*args)
            )
            device.register_command_object(
                "PostSynchronisation", device.PostSynchronisationCommand(*args)
            )
            device.register_command_object("SyncFpgas", device.SyncFpgasCommand(*args))
            device.register_command_object(
                "CalculateDelay", device.CalculateDelayCommand(*args)
            )

            antenna_args = (
                device.hardware_manager,
                device.state_model,
                device.logger,
                device.AntennasPerTile,
            )
            device.register_command_object(
                "LoadAntennaTapering", device.LoadAntennaTaperingCommand(*antenna_args)
            )
            device.register_command_object(
                "SetPointingDelay", device.SetPointingDelayCommand(*antenna_args)
            )

        def _initialise_health_monitoring(self, device):
            """
            Initialise the health model for this device.

            :param device: the device for which the health model is
                being initialised
            :type device: :py:class:`~ska.base.SKABaseDevice`
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
            :type device: :py:class:`~ska.base.SKABaseDevice`
            """
            device.power_manager = TilePowerManager(
                device.SubrackFQDN, device.SubrackBay, self.logger
            )

            power_args = (device, device.state_model, self.logger)
            device.register_command_object(
                "Disable", device.DisableCommand(*power_args)
            )
            device.register_command_object(
                "Standby", device.StandbyCommand(*power_args)
            )
            device.register_command_object("Off", device.OffCommand(*power_args))

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
            if device.power_manager.power_mode == PowerMode.OFF:
                action = "init_succeeded_disable"
            elif device.hardware_manager.is_programmed:
                action = "init_succeeded_on"
            else:
                action = "init_succeeded_standby"
            self.state_model.perform_action(action)

    class DisableCommand(SKABaseDevice.DisableCommand):
        """
        Class for handling the Disable() command.
        """

        def do(self):
            """
            Stateless hook implementing the functionality of the
            (inherited) :py:meth:`ska.base.SKABaseDevice.Disable`
            command for this :py:class:`.MccsTile` device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            result = self.target.power_manager.off()
            if result is None:
                return (
                    ResultCode.OK,
                    "TPM was already off: nothing to do to disable device.",
                )
            if not result:
                return (
                    ResultCode.FAILED,
                    "Failed to disable device: could not turn TPM off",
                )
            return (ResultCode.OK, "Device disabled; TPM has been turned off")

    class StandbyCommand(SKABaseDevice.StandbyCommand):
        """
        Class for handling the Standby() command.

        Actually the TPM has no standby mode, so when this device is
        told to go to standby mode, it switches on / remains on.
        """

        def do(self):
            """
            Stateless hook implementing the functionality of the
            (inherited) :py:meth:`ska.base.SKABaseDevice.Standby`
            command for this :py:class:`.MccsTile` device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            device = self.target
            result = device.power_manager.on()
            if result is None:
                # TODO: The TPM was already powered, so it might already be programmed!
                # What does it mean to put it into standby?
                # This needs attention from an expert.
                # But for now, let's reinitialise.
                if device.hardware_manager.is_programmed:
                    # device.hardware_manager.initialise()  # raises NotImplementedError
                    pass

                return (
                    ResultCode.OK,
                    "TPM was re-initialised; device is now on standby.",
                )
            if result:
                return (ResultCode.OK, "TPM has been turned on")
            if not result:
                return (
                    ResultCode.FAILED,
                    "Failed to go to standby: could not turn TPM on",
                )

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ReturnType, 'informational message')",
    )
    @DebugIt()
    def On(self):
        """
        Turn device on and program TPM firmware.

        This command will transition a Tile from Off/Standby to
        On and program the TPM firmware.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)
        """
        command_sequence = ["On", "Initialise"]
        if self.state_model.op_state == DevState.STANDBY:
            command_sequence.insert(0, "Off")

        # Execute the following commands to:
        # 1. Off - Transition out of Standby state (if required)
        # 2. On - Turn the power on to the Tile
        # 3. Initialise - Download TPM firmware and initialise
        return_code = ResultCode.UNKNOWN
        message = ""
        for step in command_sequence:
            command = self.get_command_object(step)
            (return_code, message) = command()
            if return_code == ResultCode.FAILED:
                return [[return_code], [message]]
        return [[return_code], ["On command completed OK"]]

    class OffCommand(SKABaseDevice.OffCommand):
        """
        Class for handling the Off() command.
        """

        def do(self):
            """
            Stateless hook implementing the functionality of the
            (inherited) :py:meth:`ska.base.SKABaseDevice.Off` command
            for this :py:class:`.MccsTile` device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            # TODO: We maybe shouldn't be allowing transition straight
            # from Disable to Off, without going through Standby.
            device = self.target
            result = device.power_manager.on()
            if result is None:
                # TODO: The TPM was already powered, but it might not have been
                # programmed yet. i.e. it might still be in standby mode
                # What does it mean to put it into "on" mode?
                # This needs attention from an expert.
                # But for now, let's pretend to flash some firmware.
                if not device.hardware_manager.is_programmed:
                    device.hardware_manager.download_firmware("firmware1")
                return (ResultCode.OK, "TPM is on and programmed; device is now off.")
            if result:
                # TODO: Okay, the TPM was been powered on. Now we need to
                # get it fully operational.
                # This needs attention from an expert.
                # But for now, let's initialise it and pretend to flash some firmware.

                # device.hardware_manager.initialise()  # raises NotImplementedError
                device.hardware_manager.download_firmware("firmware1")
                return (ResultCode.OK, "TPM has been turned on")
            if not result:
                return (
                    ResultCode.FAILED,
                    "Failed to go to standby: could not turn TPM on",
                )

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

    # ----------
    # Attributes
    # ----------
    def health_changed(self, health):
        """
        Callback to be called whenever the HealthModel's health state
        changes; responsible for updating the tango side of things i.e.
        making sure the attribute is up to date, and events are pushed.

        :param health: the new health value
        :type health: :py:class:`~ska.base.control_model.HealthState`
        """
        if self._health_state == health:
            return
        self._health_state = health
        self.push_change_event("healthState", health)

    @attribute(dtype="DevLong", doc="Logical tile identifier within a station")
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

    @attribute(dtype="DevLong", doc="The identifier of the associated subarray.")
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

    @attribute(dtype="DevLong", doc="The identifier of the associated station.")
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
        doc="""CSP ingest node IP address for station beam (use if Tile is
        last one in the beamforming chain)""",
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
        doc="""CSP ingest node MAC address for station beam (use if Tile is
        last one in the beamforming chain)""",
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
        doc="""CSP ingest node port address for station beam (use if Tile is
        last one in the beamforming chain)""",
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

    @attribute(
        dtype="DevString", doc="Name and identifier of currently running firmware"
    )
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

    @attribute(dtype="DevString", doc="Version of currently running firmware")
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
        polling_period=1000,
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
        polling_period=1000,
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
        doc="Return True if the all FPGAs are programmed, False otherwise",
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
        doc="The board temperature",
        abs_change=0.1,
        min_value=15.0,
        max_value=50.0,
        min_alarm=16.0,
        max_alarm=47.0,
        polling_period=1000,
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
        polling_period=1000,
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
        polling_period=1000,
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
        doc="Array holding the logical ID`s of the antenna associated with "
        "the Tile device",
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
        doc="""40Gb destination IP for all 40Gb ports on the Tile (source
        automatically set during initialization)""",
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
        dtype=("DevString",),
        max_dim_x=256,
        doc="""40Gb destination MACs for all 40Gb ports on the Tile (source
        automatically set during initialization)""",
    )
    def fortyGbDestinationMacs(self):
        """
        Return the destination MAC addresses for all 40Gb ports on the
        tile.

        :return: MAC addresses
        :rtype: list(str)
        """
        return tuple(
            item["DstMac"] for item in self.hardware_manager.get_40g_configuration()
        )

    @attribute(
        dtype=("DevLong",),
        max_dim_x=256,
        doc="""40Gb destination ports for all 40Gb ports on the Tile (source
        automatically set during initialization"")""",
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
        doc="Return the RMS power of every ADC signal (so a TPM processes "
        "16 antennas, this should return 32 RMS values)",
    )
    def adcPower(self):
        """
        Return the RMS power of every ADC signal (so a TPM processes 16
        antennas, this should return 32 RMS value.

        :return: RMP power of ADC signals
        :rtype: list(float)
        """
        return self.hardware_manager.adc_rms

    @attribute(
        dtype="DevLong",
        doc="Return current frame, in units of 256 ADC frames (276,48 us)",
    )
    def currentTileBeamformerFrame(self):
        """
        Return current frame, in units of 256 ADC frames (276,48 us)
        Currently this is required, not sure if it will remain so.

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

    @attribute(dtype="DevLong")
    def simulationMode(self):
        """
        Reports the simulation mode of the device.

        Some devices may implement both modes,
        while others will have simulators that set simulationMode
        to True while the real devices always set simulationMode to False.
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
        self.hardware_manager.simulation_mode = self._simulation_mode

    # # --------
    # # Commands
    # # --------
    def init_command_objects(self):
        """
        Set up the handler objects for Commands.
        """
        # Technical debt -- forced to register base class stuff rather than
        # calling super(), because On() and Off() are registered on a
        # thread, and we don't want the super() method clobbering them
        args = (self, self.state_model, self.logger)
        self.register_command_object("On", self.OnCommand(*args))
        self.register_command_object("Reset", self.ResetCommand(*args))
        self.register_command_object(
            "GetVersionInfo", self.GetVersionInfoCommand(*args)
        )

    class InitialiseCommand(ResponseCommand):
        """
        Class for handling the Initialise() command.
        """

        def do(self):
            """
            Implementation of
            :py:meth:`.MccsTile.Initialise` command
            functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            hardware_manager.initialise()
            return (ResultCode.OK, "Initialise command completed OK")

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def Initialise(self):
        """
        Performs all required initialisation (switches on on-board
        devices, locks PLL, performs synchronisation and other
        operations required to start configuring the signal processing
        functions of the firmware, such as channelisation and
        beamforming)

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

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

    @command(dtype_out="DevString", doc_out="list of firmware")
    @DebugIt()
    def GetFirmwareAvailable(self):
        """
        Return a dictionary containing the following information for
        each firmware stored on the board (such as in Flash memory). For
        each firmware, a dictionary containing the following keys with
        their respective values should be provided: ‘design’, which is a
        textual name for the firmware, ‘major’, which is the major
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
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            bitfile = argin
            if os.path.isfile(bitfile):
                hardware_manager.download_firmware(bitfile)
                return (ResultCode.OK, "DownloadFirmware command completed OK")
            else:
                return (ResultCode.FAILED, f"{bitfile} doesn't exist")

    @command(
        dtype_in="DevString",
        doc_in="bitfile location",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def DownloadFirmware(self, argin):
        """
        Downloads the firmware contained in bitfile to all FPGAs on the
        board. This should also update the internal register mapping,
        such that registers become available for use.

        :param argin: can either be the design name returned from
            :py:meth:`.GetFirmwareAvailable` command, or a path to a
            file
        :type argin: str

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

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
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            bitfile = argin
            self.logger.info("Downloading bitstream to CPLD FLASH")
            hardware_manager.cpld_flash_write(bitfile)
            return (ResultCode.OK, "ProgramCPLD command completed OK")

    @command(
        dtype_in="DevString",
        doc_in="bitfile location",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def ProgramCPLD(self, argin):
        """
        If the TPM has a CPLD (or other management chip which need
        firmware), this function program it with the provided bitfile.

        :param argin: is the path to a file containing the required CPLD firmware
        :type argin: str

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

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
        Return a list containing description of the exposed firmware
        (and CPLD) registers.

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
        doc_in="json dictionary with keywords:\n"
        "RegisterName, NbRead, Offset, Device",
        dtype_out="DevVarLongArray",
        doc_out="list of register values",
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
            :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

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
            return (ResultCode.OK, "WriteRegister command completed OK")

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with keywords:\n"
        "RegisterName, Values, Offset, Device",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
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
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

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
        doc_in="address, n",
        dtype_out="DevVarULongArray",
        doc_out="values",
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
                (:py:class:`~ska.base.commands.ResultCode`, str)

            :raises ValueError: if the argin has the wrong length/structure
            """
            hardware_manager = self.target
            if len(argin) < 2:
                self.logger.error("A minimum of two parameters are required")
                raise ValueError("A minium of two parameters are required")
            hardware_manager.write_address(argin[0], argin[1:])
            return (ResultCode.OK, "WriteAddress command completed OK")

    @command(
        dtype_in="DevVarULongArray",
        doc_in="address, values",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
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
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

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
                (:py:class:`~ska.base.commands.ResultCode`, str)

            :raises ValueError: if the JSON input lacks mandatory parameters

            :todo: Mandatory JSON parameters should be handled by validation
                against a schema
            """
            params = json.loads(argin)
            core_id = params.get("CoreID", None)
            if core_id is None:
                self.logger.error("CoreID is a mandatory parameter")
                raise ValueError("CoreID is a mandatory parameter")
            src_mac = params.get("SrcMac", None)
            if src_mac is None:
                self.logger.error("SrcMac is a mandatory parameter")
                raise ValueError("SrcMac is a mandatory parameter")
            src_ip = params.get("SrcIP", None)
            if src_ip is None:
                self.logger.error("SrcIP is a mandatory parameter")
                raise ValueError("SrcIP is a mandatory parameter")
            src_port = params.get("SrcPort", None)
            if src_port is None:
                self.logger.error("SrcPort is a mandatory parameter")
                raise ValueError("SrcPort is a mandatory parameter")
            dst_mac = params.get("DstMac", None)
            if dst_mac is None:
                self.logger.error("DstMac is a mandatory parameter")
                raise ValueError("DstMac is a mandatory parameter")
            dst_ip = params.get("DstIP", None)
            if dst_ip is None:
                self.logger.error("DstIP is a mandatory parameter")
                raise ValueError("DstIP is a mandatory parameter")
            dst_port = params.get("DstPort", None)
            if dst_port is None:
                self.logger.error("DstPort is a mandatory parameter")
                raise ValueError("DstPort is a mandatory parameter")

            hardware_manager = self.target
            hardware_manager.configure_40g_core(
                core_id, src_mac, src_ip, src_port, dst_mac, dst_ip, dst_port
            )
            return (ResultCode.OK, "Configure40GCore command completed OK")

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with keywords:\n"
        "CoreID, SrcMac, SrcIP, SrcPort, DstMac, DstIP, DstPort",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def Configure40GCore(self, argin):
        """
        Configure 40g core_id with specified parameters.

        :param argin: json dictionary with optional keywords:

        * CoreID - (int) core id
        * SrcMac - (string) mac address dot notation
        * SrcIP - (string) IP dot notation
        * SrcPort - (int) src port
        * DstMac - (string) mac address dot notation
        * DstIP - (string) IP dot notation
        * DstPort - (int) dest port

        :type argin: str

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"CoreID":2, "SrcMac":"10:fe:ed:08:0a:58", "SrcIP":"10.0.99.3",
                    "SrcPort":4000, "DstMac":"10:fe:ed:08:0a:58", "DstIP":"10.0.99.3",
                    "DstPort":5000}
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

            :param argin: the core id
            :type argin: int

            :return: json string with configuration
            :rtype: str

            :raises ValueError: if the argin is an invalid code id
            """
            core_id = argin
            hardware_manager = self.target
            item = hardware_manager.get_40g_configuration(core_id)
            if item is not None:
                return json.dumps(item.pop("CoreID"))
            raise ValueError("Invalid core id specified")

    @command(
        dtype_in="DevLong",
        doc_in="coreId",
        dtype_out="DevString",
        doc_out="configuration dict as a json string",
    )
    @DebugIt()
    def Get40GCoreConfiguration(self, argin):
        """
        Get 40g core configuration for core_id. This is required to
        chain up TPMs to form a station.

        :param argin: the core id
        :type argin: int

        :return: the configuration is a json string comprising:
                 src_mac, src_ip, src_port, dest_mac, dest_ip, dest_port
        :rtype: str

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> core_id = 2
        >>> argout = dp.command_inout("Get40GCoreConfiguration, core_id)
        >>> params = json.loads(argout)
        """
        handler = self.get_command_object("Get40GCoreConfiguration")
        return handler(argin)

    class SetLmcDownloadCommand(ResponseCommand):
        """
        Class for handling the SetLmcDownload(argin) command.
        """

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
                (:py:class:`~ska.base.commands.ResultCode`, str)

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
            return (ResultCode.OK, "SetLmcDownload command completed OK")

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with keywords:\n"
        "Mode,PayloadLength,DstIP,SrcPort,DstPort, LmcMac",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def SetLmcDownload(self, argin):
        """
        Specify whether control data will be transmitted over 1G or 40G
        networks.

        :param argin: json dictionary with optional keywords:

        * Mode - (string) '1g' or '10g' (Mandatory)
        * PayloadLength - (int) SPEAD payload length for integrated channel data
        * DstIP - (string) Destination IP
        * SrcPort - (int) Source port for integrated data streams
        * DstPort - (int) Destination port for integrated data streams
        * LmcMac: - (int) LMC Mac address is required for 10G lane configuration

        :type argin: str

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"Mode": "1G", "PayloadLength":4,DstIP="10.0.1.23"}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SetLmcDownload", jstr)
        """
        handler = self.get_command_object("SetLmcDownload")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class SetChanneliserTruncationCommand(ResponseCommand):
        """
        Class for handling the SetChanneliserTruncation(argin) command.
        """

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
                (:py:class:`~ska.base.commands.ResultCode`, str)

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
            return (ResultCode.OK, "SetChanneliserTruncation command completed OK")

    @command(
        dtype_in="DevVarLongArray",
        doc_in="truncation array",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
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
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

        :example:

        >>> n=4
        >>> m=3
        >>> trunc = [[0, 1, 2], [3, 4, 5],[6, 7, 8], [9, 10, 11],]
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
                (:py:class:`~ska.base.commands.ResultCode`, str)

            :raises ValueError: if the argin argument does not have the
                right length / structure
            """
            if len(argin) < 3:
                self.logger.error("Insufficient parameters specified")
                raise ValueError("Insufficient parameters specified")
            if len(argin) > 48:
                self.logger.error("Too many regions specified")
                raise ValueError("Too many regions specified")
            if len(argin) % 3 != 0:
                self.logger.error("Incomplete specification of region")
                raise ValueError("Incomplete specification of region")
            regions = []
            total_chan = 0
            for i in range(0, len(argin), 3):
                region = argin[i : i + 3]  # noqa: E203
                nchannels = region[1]
                if nchannels % 8 != 0:
                    self.logger.error(
                        "Nos. of channels in region must be multiple of 8"
                    )
                    raise ValueError("Nos. of channels in region must be multiple of 8")
                beam_index = region[2]
                if beam_index < 0 or beam_index > 7:
                    self.logger.error("Beam_index is out side of range 0-7")
                    raise ValueError("Beam_index is out side of range 0-7")
                total_chan += nchannels
                if total_chan > 384:
                    self.logger.error("Too many channels specified > 384")
                    raise ValueError("Too many channels specified > 384")
                regions.append(region)

            hardware_manager = self.target
            hardware_manager.set_beamformer_regions(regions)
            return (ResultCode.OK, "SetBeamFormerRegions command completed OK")

    @command(
        dtype_in="DevVarLongArray",
        doc_in="region_array",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def SetBeamFormerRegions(self, argin):
        """
        Set the frequency regions which are going to be beamformed into
        a single beam. region_array is defined as a 2D array, for a
        maximum of 16 regions. Total number of channels must be <= 384.

        :param argin: list of regions. Each region comprises:

        * start_channel - (int) region starting channel
        * num_channels - (int) size of the region, must be a multiple of 8
        * beam_index - (int) beam used for this region with range 0 to 7

        :type argin: list(int)

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

        :example:

        >>> regions = [[5, 20, 1],[25, 40, 2]]
        >>> input = list(itertools.chain.from_iterable(regions))
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("SetBeamFormerRegions", input)
        """
        handler = self.get_command_object("SetBeamFormerRegions")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class ConfigureStationBeamformerCommand(ResponseCommand):
        """
        Class for handling the ConfigureStationBeamformer(argin)
        command.
        """

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
                (:py:class:`~ska.base.commands.ResultCode`, str)

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
            return (ResultCode.OK, "ConfigureStationBeamformer command completed OK")

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with mandatory keywords:\n"
        "StartChannel,Numtiles, IsFirst, IsLast",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
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
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

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
        Class for handling the LoadCalibrationCoefficients(argin)
        command.
        """

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
                (:py:class:`~ska.base.commands.ResultCode`, str)

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
            calib_coeffs = [
                [
                    complex(argin[i], argin[i + 1]),
                    complex(argin[i + 2], argin[i + 3]),
                    complex(argin[i + 4], argin[i + 5]),
                    complex(argin[i + 6], argin[i + 7]),
                ]
                for i in range(1, len(argin), 8)
            ]

            hardware_manager = self.target
            hardware_manager.load_calibration_coefficients(antenna, calib_coeffs)
            return (ResultCode.OK, "LoadCalibrationCoefficients command completed OK")

    @command(
        dtype_in="DevVarDoubleArray",
        doc_in="antenna, calibration_coefficients",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def LoadCalibrationCoefficients(self, argin):
        """
        Loads calibration coefficients (but does not apply them, this is
        performed by switch_calibration_bank). The calibration
        coefficients may include any rotation matrix (e.g. the
        parallactic angle), but do not include the geometric delay.

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
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

        :example:

        >>> antenna = 2
        >>> complex_coeffs = [[complex(3.4, 1.2), complex(2.3, 4.1),
        >>>            complex(4.6, 8.2), complex(6.8, 2.4)]]*5
        >>> inp = list(itertools.chain.from_iterable(complex_coeffs))
        >>> out = [[v.real, v.imag] for v in inp]
        >>> coeffs = list(itertools.chain.from_iterable(out))
        >>> coeffs.insert(0, float(antenna))
        >>> input = list(itertools.chain.from_iterable(coeffs))
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("LoadCalibrationCoefficients", input)
        """
        handler = self.get_command_object("LoadCalibrationCoefficients")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class LoadBeamAngleCommand(ResponseCommand):
        """
        Class for handling the LoadBeamAngle(argin) command.
        """

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
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            hardware_manager.load_beam_angle(argin)
            return (ResultCode.OK, "LoadBeamAngle command completed OK")

    @command(
        dtype_in="DevVarDoubleArray",
        doc_in="angle_coefficients",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def LoadBeamAngle(self, argin):
        """
        angle_coefs is an array of one element per beam, specifying a
        rotation angle, in radians, for the specified beam. The rotation
        is the same for all antennas. Default is 0 (no rotation). A
        positive pi/4 value transfers the X polarization to the Y
        polarization. The rotation is applied after regular calibration.

        :param argin: list of angle coefficients for each beam
        :type argin: list(float)

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

        :example:

        >>> angle_coeffs = [3.4] * 16
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("LoadBeamAngle", angle_coeffs)
        """
        handler = self.get_command_object("LoadBeamAngle")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class LoadAntennaTaperingCommand(ResponseCommand):
        """
        Class for handling the LoadAntennaTapering(argin) command.
        """

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
                :py:class:`~ska.base.DeviceStateModel`
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

            :param argin: antenna tapering coefficients
            :type argin: list(float)

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska.base.commands.ResultCode`, str)

            :raises ValueError: if the argin argument does not have the
                right length / structure
            """
            if len(argin) < self._antennas_per_tile:
                self.logger.error(
                    f"Insufficient coefficients should be {self._antennas_per_tile}"
                )
                raise ValueError(
                    f"Insufficient coefficients should be {self._antennas_per_tile}"
                )

            hardware_manager = self.target
            hardware_manager.load_antenna_tapering(argin)
            return (ResultCode.OK, "LoadAntennaTapering command completed OK")

    @command(
        dtype_in="DevVarDoubleArray",
        doc_in="tapering coefficients",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def LoadAntennaTapering(self, argin):
        """
        tapering_coeffs is a vector contains a value for each antenna
        the TPM processes. Default at initialisation is 1.0.

        :param argin: list of tapering coefficients for each antenna
        :type argin: list(float)

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

        :example:

        >>> tapering_coeffs = [3.4] * 16
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("LoadAntennaTapering", tapering_coeffs)
        """
        handler = self.get_command_object("LoadAntennaTapering")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class SwitchCalibrationBankCommand(ResponseCommand):
        """
        Class for handling the SwitchCalibrationBank(argin) command.
        """

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
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            switch_time = argin
            hardware_manager = self.target
            hardware_manager.switch_calibration_bank(switch_time)
            return (ResultCode.OK, "SwitchCalibrationBank command completed OK")

    @command(
        dtype_in="DevLong",
        doc_in="switch time",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
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
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

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
                :py:class:`~ska.base.DeviceStateModel`
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
                (:py:class:`~ska.base.commands.ResultCode`, str)

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
            return (ResultCode.OK, "SetPointingDelay command completed OK")

    @command(
        dtype_in="DevVarDoubleArray",
        doc_in="delay_array, beam_index",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def SetPointingDelay(self, argin):
        """
        Specifies the delay in seconds and the delay rate in
        seconds/second. The delay_array specifies the delay and delay
        rate for each antenna. beam_index specifies which beam is
        desired (range 0-7)

        :param argin: the delay in seconds and the delay rate in
            seconds/second.
        :type argin: list(float)

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("SetPointingDelay")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class LoadPointingDelayCommand(ResponseCommand):
        """
        Class for handling the LoadPointingDelay(argin) command.
        """

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
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            load_time = argin
            hardware_manager = self.target
            hardware_manager.load_pointing_delay(load_time)
            return (ResultCode.OK, "LoadPointingDelay command completed OK")

    @command(
        dtype_in="DevLong",
        doc_in="load_time",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
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
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

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
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            hardware_manager = self.target

            params = json.loads(argin)
            start_time = params.get("StartTime", 0)
            duration = params.get("Duration", -1)
            hardware_manager.start_beamformer(start_time, duration)
            return (ResultCode.OK, "StartBeamformer command completed OK")

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with keywords:\n" "StartTime, Duration",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
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
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

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

        def do(self):
            """
            Implementation of
            :py:meth:`.MccsTile.StopBeamformer` command
            functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            hardware_manager.stop_beamformer()
            return (ResultCode.OK, "StopBeamformer command completed OK")

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def StopBeamformer(self):
        """
        Stop the beamformer.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("StopBeamformer")
        """
        handler = self.get_command_object("StopBeamformer")
        (return_code, message) = handler()
        return [[return_code], [message]]

    class ConfigureIntegratedChannelDataCommand(ResponseCommand):
        """
        Class for handling the ConfigureIntegratedChannelData(argin)
        command.
        """

        def do(self, argin):
            """
            Stateless do-hook for implementation of
            :py:meth:`.MccsTile.ConfigureIntegratedChannelData`
            command functionality.

            :param argin: integration time. Default to 0.5 for values
                less than 0
            :type argin: float

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            integration_time = argin
            if integration_time <= 0:
                integration_time = 0.5

            hardware_manager = self.target
            hardware_manager.configure_integrated_channel_data(integration_time)
            return (
                ResultCode.OK,
                "ConfigureIntegratedChannelData command completed OK",
            )

    @command(
        dtype_in="DevDouble",
        doc_in="Integration time",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def ConfigureIntegratedChannelData(self, argin):
        """
        Configure the transmission of integrated channel data with the
        provided integration time.

        :param argin: integration_time in seconds (default = 0.5)
        :type argin: float

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("ConfigureIntegratedChannelData", 6.284)
        """
        handler = self.get_command_object("ConfigureIntegratedChannelData")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class ConfigureIntegratedBeamDataCommand(ResponseCommand):
        """
        Class for handling the ConfigureIntegratedBeamData(argin)
        command.
        """

        def do(self, argin):
            """
            Implementation of
            :py:meth:`.MccsTile.ConfigureIntegratedBeamData`
            command functionality.

            :param argin: integration time
            :type argin: float

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            integration_time = argin
            if integration_time <= 0:
                integration_time = 0.5

            hardware_manager = self.target
            hardware_manager.configure_integrated_beam_data(integration_time)
            return (ResultCode.OK, "ConfigureIntegratedBeamData command completed OK")

    @command(
        dtype_in="DevDouble",
        doc_in="Integration time",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def ConfigureIntegratedBeamData(self, argin):
        """
        Configure the transmission of integrated beam data with the
        provided integration time.

        :param argin: integration time in seconds (default = 0.5)
        :type argin: float

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("ConfigureIntegratedBeamData", 3.142)
        """
        handler = self.get_command_object("ConfigureIntegratedBeamData")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class SendRawDataCommand(ResponseCommand):
        """
        Class for handling the SendRawData(argin) command.
        """

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
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            params = json.loads(argin)
            sync = params.get("Sync", False)
            period = params.get("Period", 0)
            timeout = params.get("Timeout", 0)
            timestamp = params.get("Timestamp", None)
            seconds = params.get("Seconds", 0.2)

            hardware_manager = self.target
            hardware_manager.send_raw_data(sync, period, timeout, timestamp, seconds)
            return (ResultCode.OK, "SendRawData command completed OK")

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with keywords:\n"
        "Sync,Period,Timeout,Timestamp,Seconds",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def SendRawData(self, argin):
        """
        Transmit a snapshot containing raw antenna data.

        :param argin: json dictionary with optional keywords:

        * Sync - (bool) synchronised flag
        * Period - (int) in seconds to send data
        * Timeout - (int) When to stop
        * Timestamp - (int??) When to start
        * Seconds - (float) When to synchronise

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"Sync":True, "Period": 200, "Seconds": 0.5}
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
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            params = json.loads(argin)
            number_of_samples = params.get("NSamples", 1024)
            first_channel = params.get("FirstChannel", 0)
            last_channel = params.get("LastChannel", 511)
            period = params.get("Period", 0)
            timeout = params.get("Timeout", 0)
            timestamp = params.get("Timestamp", None)
            seconds = params.get("Seconds", 0.2)

            hardware_manager = self.target
            hardware_manager.send_channelised_data(
                number_of_samples,
                first_channel,
                last_channel,
                period,
                timeout,
                timestamp,
                seconds,
            )
            return (ResultCode.OK, "SendChannelisedData command completed OK")

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with keywords:\n"
        "NSamples,FirstChannel,LastChannel,Period,"
        "Timeout,Timestamp,Seconds",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def SendChannelisedData(self, argin):
        """
        Transmit a snapshot containing channelized data totalling
        number_of_samples spectra.

        :param argin: json dictionary with optional keywords:

        * NSamples - (int) number of spectra to send
        * FirstChannel - (int) first channel to send
        * LastChannel - (int) last channel to send
        * Period - (int) in seconds to send data
        * Timeout - (int) When to stop
        * Timestamp - (int??) When to start
        * Seconds - (float) When to synchronise

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

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
        Class for handling the SendChannelisedDataContinuous(argin)
        command.
        """

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
                (:py:class:`~ska.base.commands.ResultCode`, str)

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
            timeout = params.get("Timeout", 0)
            timestamp = params.get("Timestamp", None)
            seconds = params.get("Seconds", 0.2)

            hardware_manager = self.target
            hardware_manager.send_channelised_data_continuous(
                channel_id, number_of_samples, wait_seconds, timeout, timestamp, seconds
            )
            return (ResultCode.OK, "SendChannelisedDataContinuous command completed OK")

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with keywords:\n"
        "ChannelID,NSamples,WaitSeconds,Timeout,"
        "Timestamp,Seconds",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def SendChannelisedDataContinuous(self, argin):
        """
        Send data from channel channel continuously (until stopped)

        :param argin: json dictionary with 1 mandatory and optional keywords:

        * ChannelID - (int) channel_id (Mandatory)
        * NSamples -  (int) number of spectra to send
        * WaitSeconds - (int) Wait time before sending data
        * Timeout - (int) When to stop
        * Timestamp - (int??) When to start
        * Seconds - (float) When to synchronise

        :type argin: str

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"ChannelID":2, "NSamples":256, "Period": 10, "Seconds": 0.5}
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
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            params = json.loads(argin)
            period = params.get("Period", 0)
            timeout = params.get("Timeout", 0)
            timestamp = params.get("Timestamp", None)
            seconds = params.get("Seconds", 0.2)

            hardware_manager = self.target
            hardware_manager.send_beam_data(period, timeout, timestamp, seconds)
            return (ResultCode.OK, "SendBeamData command completed OK")

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with keywords:\n" "Period,Timeout,Timestamp,Seconds",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def SendBeamData(self, argin):
        """
        Transmit a snapshot containing beamformed data.

        :param argin: json dictionary with optional keywords:

        * Period - (int) in seconds to send data
        * Timeout - (int) When to stop
        * Timestamp - (string??) When to send
        * Seconds - (float) When to synchronise

        :type argin: str

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"Period": 10, "Timeout":4, "Seconds": 0.5}
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

        def do(self):
            """
            Implementation of
            :py:meth:`.MccsTile.StopDataTransmission`
            command functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            hardware_manager.stop_data_transmission()
            return (ResultCode.OK, "StopDataTransmission command completed OK")

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def StopDataTransmission(self):
        """
        Stop data transmission from board.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

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

        def do(self):
            """
            Implementation of
            :py:meth:`.MccsTile.ComputeCalibrationCoefficients`
            command functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            hardware_manager.compute_calibration_coefficients()
            return (
                ResultCode.OK,
                "ComputeCalibrationCoefficients command completed OK",
            )

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def ComputeCalibrationCoefficients(self):
        """
        Compute the calibration coefficients and load them in the
        hardware.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

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
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            params = json.loads(argin)
            start_time = params.get("StartTime", None)
            delay = params.get("Delay", 2)

            hardware_manager = self.target
            hardware_manager.start_acquisition(start_time, delay)
            return (ResultCode.OK, "StartAcquisition command completed OK")

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with keywords:\n" "StartTime, Delay",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
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
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

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
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            delays = argin
            hardware_manager = self.target
            hardware_manager.set_time_delays(delays)
            return (ResultCode.OK, "SetTimeDelays command completed OK")

    @command(
        dtype_in="DevVarDoubleArray",
        doc_in="time delays",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def SetTimeDelays(self, argin):
        """
        Set coarse zenith delay for input ADC streams Delay specified in
        nanoseconds, nominal is 0.

        :param argin: the delay in samples, positive delay adds delay
                       to the signal stream
        :type argin: list(int)

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

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
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            rounding = argin
            hardware_manager = self.target
            hardware_manager.set_csp_rounding(rounding)
            return (ResultCode.OK, "SetCspRounding command completed OK")

    @command(
        dtype_in="DevDouble",
        doc_in="csp rounding",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
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
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

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
                (:py:class:`~ska.base.commands.ResultCode`, str)

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
            return (ResultCode.OK, "SetLmcIntegratedDownload command completed OK")

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with keywords:\n"
        "Mode,ChannelPayloadLength,BeamPayloadLength|n"
        "DstIP,SrcPort,DstPort, LmcMac",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
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
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

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
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            params = json.loads(argin)
            period = params.get("Period", 0)
            timeout = params.get("Timeout", 0)
            timestamp = params.get("Timestamp", None)
            seconds = params.get("Seconds", 0.2)

            hardware_manager = self.target
            hardware_manager.send_raw_data_synchronised(
                period, timeout, timestamp, seconds
            )
            return (ResultCode.OK, "SendRawDataSynchronised command completed OK")

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with keywords:\n" "Period,Timeout,Timestamp,Seconds",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    def SendRawDataSynchronised(self, argin):
        """
        Send synchronised raw data.

        :param argin: json dictionary with optional keywords:

        * Period - (int) in seconds to send data
        * Timeout - (int) When to stop
        * Timestamp - (string??) When to send
        * Seconds - (float) When to synchronise

        :type argin: str

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"Period": 10, "Timeout":4, "Seconds": 0.5}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SendRawDataSynchronised", jstr)
        """
        handler = self.get_command_object("SendRawDataSynchronised")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class SendChannelisedDataNarrowbandCommand(ResponseCommand):
        """
        Class for handling the SendChannelisedDataNarrowband(argin)
        command.
        """

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
                (:py:class:`~ska.base.commands.ResultCode`, str)

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
            timeout = params.get("Timeout", 0)
            timestamp = params.get("Timestamp", None)
            seconds = params.get("Seconds", 0.2)
            hardware_manager = self.target
            hardware_manager.send_channelised_data_narrowband(
                frequency,
                round_bits,
                number_of_samples,
                wait_seconds,
                timeout,
                timestamp,
                seconds,
            )
            return (ResultCode.OK, "SendChannelisedDataNarrowband command completed OK")

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with keywords:\n"
        "Frequency,RoundBits,NSamples,WaitSeconds,Timeout,Timestamp,Seconds",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def SendChannelisedDataNarrowband(self, argin):
        """
        Continuously send channelised data from a single channel end
        data from channel channel continuously (until stopped)

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
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

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

        def do(self):
            """
            Implementation of
            :py:meth:`.MccsTile.TweakTransceivers` command
            functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            hardware_manager.tweak_transceivers()
            return (ResultCode.OK, "TweakTransceivers command completed OK")

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def TweakTransceivers(self):
        """
        Tweak the transceivers.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

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

        def do(self):
            """
            Implementation of
            :py:meth:`.MccsTile.PostSynchronisation` command
            functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            hardware_manager.post_synchronisation()
            return (ResultCode.OK, "PostSynchronisation command completed OK")

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def PostSynchronisation(self):
        """
        Post tile configuration synchronization.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

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

        def do(self):
            """
            Implementation of
            :py:meth:`.MccsTile.SyncFpgas` command
            functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            hardware_manager.sync_fpgas()
            return (ResultCode.OK, "SyncFpgas command completed OK")

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def SyncFpgas(self):
        """
        Synchronise the FPGAs.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

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
                (:py:class:`~ska.base.commands.ResultCode`, str)

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
            return (ResultCode.OK, "CalculateDelay command completed OK")

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with keywords:\n" "CurrentDelay,CurrentTC,RefLo,RefHi",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
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
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"CurrentDelay":0.4, "CurrentTC":56.2, "RefLo":3.0, "RefHi":78.9}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("CalculateDelay", jstr)
        """
        handler = self.get_command_object("CalculateDelay")
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
