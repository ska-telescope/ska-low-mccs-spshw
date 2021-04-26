# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""
This module contains an implementation of the MCCS Subrack Management
Board Tango device and related classes.
"""
import threading
import json
import time
from tango import DebugIt, EnsureOmniThread, SerialModel, Util

from tango.server import attribute, command, device_property

from ska_tango_base import SKABaseDevice
from ska_tango_base.commands import BaseCommand, ResponseCommand, ResultCode
from ska_tango_base.control_model import HealthState, SimulationMode
from ska_low_mccs.hardware import (
    HardwareHealthEvaluator,
    OnOffHardwareManager,
    PowerMode,
    SimulableHardwareFactory,
    SimulableHardwareManager,
)
from ska_low_mccs.health import HealthModel
from ska_low_mccs.subrack.subrack_simulator import SubrackBoardSimulator
from ska_low_mccs.subrack.subrack_driver import SubrackBoardDriver
from ska_low_mccs.message_queue import MessageQueue


__all__ = [
    "SubrackHardwareFactory",
    "SubrackHardwareHealthEvaluator",
    "SubrackHardwareManager",
    "MccsSubrack",
    "main",
]


def create_return(success, action):
    """
    Helper function to package up a boolean result into a
    (:py:class:`~ska_tango_base.commands.ResultCode`, message) tuple.

    :param success: whether execution of the action was successful. This
        may be None, in which case the action was not performed due to
        redundancy (i.e. it was already done).
    :type success: bool or None
    :param action: Informal description of the action that the command
        performs, for use in constructing a message
    :type action: str

    :return: A tuple containing a return code and a string
        message indicating status. The message is for
        information purpose only.
    :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
    """
    if success is None:
        return (ResultCode.OK, f"Subrack {action} is redundant")
    elif success:
        return (ResultCode.OK, f"Subrack {action} successful")
    else:
        return (ResultCode.FAILED, f"Subrack {action} failed")


class SubrackHardwareHealthEvaluator(HardwareHealthEvaluator):
    """
    A placeholder for a class that implements a policy by which the
    subrack hardware manager evaluates the health of the subrack
    management board hardware that it manages.

    At present this just inherits from the base class unchanged.
    """

    pass


class SubrackHardwareFactory(SimulableHardwareFactory):
    """
    A hardware factory for Subrack hardware.

    At present, this returns a
    :py:class:`~ska_low_mccs.subrack.subrack_simulator.SubrackBoardSimulator`
    object when in simulation mode, and raises
    :py:exc:`NotImplementedError` if the hardware is sought whilst not
    in simulation mode
    """

    def __init__(
        self,
        simulation_mode,
        logger,
        subrack_ip="0.0.0.0",
        subrack_port=0,
        tpm_count=None,
    ):
        """
        Create a new factory instance.

        :param simulation_mode: the initial simulation mode of this
            hardware manager
        :type simulation_mode:
            :py:class:`~ska_tango_base.control_model.SimulationMode`
        :param logger: the logger to be used by this hardware manager.
        :type logger: :py:class:`logging.Logger`
        :param subrack_ip: the IP address of the subrack
        :type subrack_ip: str
        :param subrack_port: the port at which the subrack is accessed for control
        :type subrack_port: int
        :param tpm_count: Optional number of TPMs that are attached to
            the subrack. If omitted, the subrack uses its own default.
        :type tpm_count: int
        """
        self._logger = logger
        self._subrack_ip = subrack_ip
        self._subrack_port = subrack_port
        self._tpm_count = tpm_count
        super().__init__(simulation_mode)

    def _create_driver(self):
        """
        Returns a hardware driver.

        :return: a hardware driver for the subrack
        :rtype: :py:class:`ska_low_mccs.subrack.subrack_driver.SubrackBoardDriver`
        """
        return SubrackBoardDriver(self._logger, self._subrack_ip, self._subrack_port)

    def _create_static_simulator(self):
        """
        Returns a hardware simulator.

        :return: a hardware simulator for the tile
        :rtype:
            :py:class:`.SubrackHardwareSimulator`
        """
        if self._tpm_count is None:
            return SubrackBoardSimulator()
        else:
            return SubrackBoardSimulator(
                tpm_power_modes=[PowerMode.OFF] * self._tpm_count,
                tpm_present=[True] * self._tpm_count,
            )


class SubrackHardwareManager(OnOffHardwareManager, SimulableHardwareManager):
    """
    This class manages MCCS subrack hardware.

    :todo:
    """

    def __init__(
        self,
        simulation_mode,
        are_tpms_on_change_callback,
        logger,
        subrack_ip,
        subrack_port,
        tpm_count=None,
        _factory=None,
    ):
        """
        Initialise a new SubrackHardwareManager instance.

        :param simulation_mode: the initial simulation mode of this
            hardware manager
        :type simulation_mode: :py:class:`~ska_tango_base.control_model.SimulationMode`
        :param are_tpms_on_change_callback: a callback to be called when
            the are_tpms_on property changes
        :type are_tpms_on_change_callback: callable
        :param logger: a logger for this hardware manager to use
        :type logger: :py:class:`logging.Logger`
        :param subrack_ip: IP address of Subrack board
        :type subrack_ip: str
        :param subrack_port: port address of subrack control port
        :type subrack_port: int
        :param tpm_count: Optional number of TPMs that are attached to
            the subrack. If omitted, the subrack uses its own default
            value.
        :type tpm_count: int
        :param _factory: allows for substitution of a hardware factory.
            This is useful for testing, but generally should not be used
            in operations.
        :type _factory: :py:class:`.SubrackHardwareFactory`
        """
        hardware_factory = _factory or SubrackHardwareFactory(
            simulation_mode == SimulationMode.TRUE,
            logger,
            subrack_ip,
            subrack_port,
            tpm_count=tpm_count,
        )
        super().__init__(hardware_factory, SubrackHardwareHealthEvaluator())

        self._are_tpms_on = None
        self._are_tpms_on_change_callback = are_tpms_on_change_callback

    def connect(self):
        """
        Establish a connection to the subrack hardware.

        :return: whether successful
        :rtype: bool
        """
        success = super().connect()
        if success:
            self._update_are_tpms_on()
        return success

    def _connect(self):
        """
        Check connection in actual hardware
        :return: connect status
        :rtype: Bool
        """
        return self._factory.hardware.connect()

    @property
    def backplane_temperatures(self):
        """
        Return the temperature of this subrack's backplane.

        :return: the backplane temperatures, in degrees celsius
        :rtype: list(float)
        """
        return self._factory.hardware.backplane_temperatures

    @property
    def board_temperatures(self):
        """
        Return the temperature of this subrack's management board.

        :return: the board temperatures, in degrees celsius, from sensor 1 and 2
        :rtype: list(float)
        """
        return self._factory.hardware.board_temperatures

    @property
    def board_current(self):
        """
        Return the current of this subrack's management board.

        :return: the board current
        :rtype: float
        """
        return self._factory.hardware.board_current

    @property
    def subrack_fan_speeds(self):
        """
        Return this subrack's backplane fan speeds.

        :return: the fan speeds, in RPMs
        :rtype: list(float)
        """
        return self._factory.hardware.subrack_fan_speeds

    @property
    def subrack_fan_speeds_percent(self):
        """
        Return this subrack's backplane fan speeds in  percent.

        :return: the fan speeds, in percent
        :rtype: list(float)
        """
        return self._factory.hardware.subrack_fan_speeds_percent

    @property
    def subrack_fan_mode(self):
        """
        Return the subrack backplane fan Mode .

        :return: subrack fan mode 1 for AUTO or 0 for MANUAL
        :rtype: int
        """
        return self._factory.hardware.subrack_fan_mode

    @property
    def bay_count(self):
        """
        Return the number of TPM bays managed by this subrack.

        :return: the number of TPM bays managed by this subrack
        :rtype: int
        """
        return self._factory.hardware.bay_count

    @property
    def tpm_count(self):
        """
        Return the number of TPMs managed by this subrack.

        :return: the number of TPMs managed by this subrack
        :rtype: int
        """
        return self._factory.hardware.tpm_count

    @property
    def tpm_temperatures(self):
        """
        Return a list of bay temperatures for this subrack.

        :return: a list of bay temperatures, in degrees celsius
        :rtype: list(float)
        """
        return self._factory.hardware.tpm_temperatures

    @property
    def tpm_powers(self):
        """
        Return a list of bay powers for this subrack.

        :return: a list of bay powers, in Watt
        :rtype: list(float)
        """
        return self._factory.hardware.tpm_powers

    @property
    def tpm_voltages(self):
        """
        Return a list of bay voltages for this subrack.

        :return: a list of bay voltages, in volt
        :rtype: list(float)
        """
        return self._factory.hardware.tpm_voltages

    @property
    def power_supply_fan_speeds(self):
        """
        Return the power supply fan speed for this subrack.

        :return: the power supply fan speed
        :rtype: list(float)
        """
        return self._factory.hardware.power_supply_fan_speeds

    @property
    def power_supply_currents(self):
        """
        Return the power_supply currents for this subrack.

        :return: the power_supply currents
        :rtype: list(float)
        """
        return self._factory.hardware.power_supply_currents

    @property
    def power_supply_powers(self):
        """
        Return the power supply powers for this subrack.

        :return: the power supply powers
        :rtype: list(float)
        """
        return self._factory.hardware.power_supply_powers

    @property
    def power_supply_voltages(self):
        """
        Return the power supply voltages for this subrack.

        :return: the power supply voltages
        :rtype: list(float)
        """
        return self._factory.hardware.power_supply_voltages

    @property
    def tpm_present(self):
        """
        Return the tpms detected in the subrack.

        :return: list of tpm detected
        :rtype: list(bool)
        """
        return self._factory.hardware.tpm_present

    @property
    def tpm_supply_fault(self):
        """
        Return info about about TPM supply fault status.

        :return: the TPM supply fault status
        :rtype: list(int)
        """
        return self._factory.hardware.tpm_supply_fault

    @property
    def tpm_currents(self):
        """
        Return a list of bay currents for this subrack.

        :return: a list of bay currents
        :rtype: list(float)
        """
        return self._factory.hardware.tpm_currents

    def are_tpms_on(self):
        """
        Returns whether each TPM is powered or not.

        :return: whether each TPM is powered or not.
        :rtype: list(bool)
        """
        self._update_are_tpms_on()
        return self._are_tpms_on

    def is_tpm_on(self, logical_tpm_id):
        """
        Check whether this subrack is supplying power to a specified
        TPM.

        :param logical_tpm_id: this subrack's internal id for the
            TPM being queried
        :type logical_tpm_id: int

        :return: whether this subrack is supplying power to the specified TPM
        :rtype: bool
        """
        self._update_are_tpms_on()
        return self._are_tpms_on is not None and self._are_tpms_on[logical_tpm_id - 1]

    def turn_on_tpm(self, logical_tpm_id):
        """
        Turn on a specified TPM. Reading the device status just after a
        command execution can return the old power status since the
        hardware takes a finite time to update it. For this reason a
        delay of 0.1s is added.

        :param logical_tpm_id: the subrack's internal id for the
            TPM to be turned on
        :type logical_tpm_id: int

        :return: whether successful, or None if there was nothing to do
        :rtype: bool or None
        """
        if self._factory.hardware.is_tpm_on(logical_tpm_id):
            return None
        self._factory.hardware.turn_on_tpm(logical_tpm_id)
        time.sleep(0.1)
        self._update_are_tpms_on()
        return self._factory.hardware.is_tpm_on(logical_tpm_id)

    def turn_off_tpm(self, logical_tpm_id):
        """
        Turn off a specified TPM.

        :param logical_tpm_id: the subrack's internal id for the
            TPM to be turned off
        :type logical_tpm_id: int

        :return: whether successful, or None if there was nothing to do
        :rtype: bool or None
        """
        if not self._factory.hardware.is_tpm_on(logical_tpm_id):
            return None
        self._factory.hardware.turn_off_tpm(logical_tpm_id)
        time.sleep(0.1)
        self._update_are_tpms_on()
        return not self._factory.hardware.is_tpm_on(logical_tpm_id)

    def turn_on_tpms(self):
        """
        Turn on all TPMs.

        :return: whether the action was successful, or None if there was nothing to do
        :rtype: bool
        """
        tpms_on = self.are_tpms_on()
        if tpms_on is None:
            return None
        tpms_present = self.tpm_present
        n_tpms = len(tpms_on)
        all_on = True
        for i in range(n_tpms):
            all_on = all_on and (not tpms_present[i] or tpms_on[i])
        if all_on:
            return None
        self._factory.hardware.turn_on_tpms()
        time.sleep(0.1)
        self._update_are_tpms_on()
        all_on = True
        for i in range(n_tpms):
            all_on = all_on and (not tpms_present[i] or self._are_tpms_on[i])
        return all_on

    def turn_off_tpms(self):
        """
        Turn off all TPMs.

        :return: whether the action was successful, or None if there was nothing to do
        :rtype: bool
        """
        tpms_on = self.are_tpms_on()
        if tpms_on is None:
            return None
        tpms_present = self.tpm_present
        n_tpms = len(tpms_on)
        all_off = True
        for i in range(n_tpms):
            all_off = all_off and (not tpms_present[i] or not tpms_on[i])
        if all_off:
            return None
        self._factory.hardware.turn_off_tpms()
        time.sleep(0.1)
        self._update_are_tpms_on()
        all_off = True
        for i in range(n_tpms):
            all_off = all_off and (not tpms_present[i] or not self._are_tpms_on[i])
        return all_off

    def _update_are_tpms_on(self):
        """
        Update our record of which TPMs are off/on, ensureing that
        registered callbacks are called.
        """
        are_tpms_on = self._factory.hardware.are_tpms_on()
        if are_tpms_on is None:
            are_tpms_on = [False] * self.tpm_count

        if self._are_tpms_on != are_tpms_on:
            self._are_tpms_on = list(are_tpms_on)
            self._are_tpms_on_change_callback(self._are_tpms_on)

    def poll(self):
        """
        Poll the hardware.
        """
        super().poll()
        self._update_are_tpms_on()

    def set_subrack_fan_speed(self, fan_id, speed_percent):
        """
        Set the subrack backplane fan speed.

        :param fan_id: id of the selected fan accepted value: 1-4
        :type fan_id: int
        :param speed_percent: percentage value of fan RPM  (MIN 0=0% - MAX 100=100%)
        :type speed_percent: float
        """
        self._factory.hardware.set_subrack_fan_speed(fan_id, speed_percent)

    def set_subrack_fan_mode(self, fan_id, mode):
        """
        Set subrack Fan Operational Mode.

        :param fan_id: id of the selected fan accepted value: 1-4
        :type fan_id: int
        :param mode:  1 AUTO, 0 MANUAL
        :type mode: int
        """
        self._factory.hardware.set_subrack_fan_mode(fan_id, mode)

    def set_power_supply_fan_speed(self, power_supply_fan_id, speed_percent):
        """
        Set the power supply  fan speed.

        :param power_supply_fan_id: power supply id from 1 to 2
        :type power_supply_fan_id: int
        :param speed_percent: fan speed in percent (MIN 0=0% - MAX 100=100%)
        :type speed_percent: float
        """
        self._factory.hardware.set_power_supply_fan_speed(
            power_supply_fan_id, speed_percent
        )


class MccsSubrack(SKABaseDevice):
    """
    An implementation of MCCS Subrack device. The device is controlled
    by a remote microcontroller, which answers to simple commands. It
    has the capabilities to switch on and off individual TPMs, to
    measure temperatures, voltages and currents, and to set-check fan
    speeds.

    This class is a subclass of
    :py:class:`ska_tango_base.SKABaseDevice`.

    **Properties:**

    - Device Property
    """

    # -----------------
    # Device Properties
    # -----------------

    SubrackIp = device_property(dtype=str, default_value="0.0.0.0")
    SubrackPort = device_property(dtype=int, default_value=8081)
    TileFQDNs = device_property(dtype=(str,), default_value=[])

    def init_device(self):
        """
        Initialise the device; overridden here to change the Tango
        serialisation model.
        """
        util = Util.instance()
        util.set_serial_model(SerialModel.NO_SYNC)
        super().init_device()

    def init_command_objects(self):
        """
        Initialises the command handlers for commands supported by this
        device.
        """
        super().init_command_objects()

        for (command_name, command_object) in [
            ("Disable", self.DisableCommand),
            ("Standby", self.StandbyCommand),
            ("Off", self.OffCommand),
            ("IsTpmOn", self.IsTpmOnCommand),
            ("PowerOnTpm", self.PowerOnTpmCommand),
            ("PowerOffTpm", self.PowerOffTpmCommand),
            ("PowerUpTpms", self.PowerUpTpmsCommand),
            ("PowerDownTpms", self.PowerDownTpmsCommand),
            ("SetSubrackFanSpeed", self.SetSubrackFanSpeedCommand),
            ("SetSubrackFanMode", self.SetSubrackFanModeCommand),
            ("SetPowerSupplyFanSpeed", self.SetPowerSupplyFanSpeedCommand),
        ]:
            self.register_command_object(
                command_name,
                command_object(self.hardware_manager, self.state_model, self.logger),
            )
            self.logger.warning("Adding command " + command_name)

        for (command_name, command_object) in [
            ("On", self.OnCommand),
        ]:
            self.register_command_object(
                command_name,
                command_object(self, self.state_model, self.logger),
            )

    class InitCommand(SKABaseDevice.InitCommand):
        """
        Class that implements device initialisation for the MCCS Subrack
        device.
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
            Initialises the attributes and properties of the
            :py:class:`.MccsSubrack`.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            super().do()
            device = self.target
            device._tile_fqdns = list(device.TileFQDNs)
            device.queue_debug = ""
            device._heart_beat = 0

            # TODO: the default value for simulationMode should be
            # FALSE, but we don't have real hardware to test yet, so we
            # can't take our devices out of simulation mode. Once we
            # have a driver for real hardware, we should change this
            # default to FALSE.
            device._simulation_mode = SimulationMode.TRUE
            device._are_tpms_on = None
            device.set_change_event("areTpmsOn", True, False)

            device.hardware_manager = SubrackHardwareManager(
                device._simulation_mode,
                device.are_tpms_on_changed,
                device.logger,
                device.SubrackIp,
                device.SubrackPort,
                tpm_count=len(device._tile_fqdns),
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
            Thread target for asynchronous initialisation of connections
            to external entities such as hardware and other devices.

            :param device: the device being initialised
            :type device: :py:class:`ska_tango_base.SKABaseDevice`
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
                with self._lock:
                    self.succeeded()

        def _initialise_hardware_management(self, device):
            """
            Initialise the connection to the hardware being managed by
            this device. May also register commands that depend upon a
            connection to that hardware.

            :param device: the device for which a connection to the
                hardware is being initialised
            :type device: :py:class:`ska_tango_base.SKABaseDevice`
            """
            device.hardware_manager.connect()

        def _initialise_health_monitoring(self, device):
            """
            Initialise the health model for this device.

            :param device: the device for which the health model is
                being initialised
            :type device: :py:class:`ska_tango_base.SKABaseDevice`
            """
            device._health_state = HealthState.UNKNOWN
            device.set_change_event("healthState", True, False)
            device.health_model = HealthModel(
                device.hardware_manager,
                None,
                None,
                device.health_changed,
            )

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
            ensure that MccsSubrack transitions to a state that reflects
            the state of its hardware
            """
            device = self.target
            if device.hardware_manager.power_mode == PowerMode.OFF:
                action = "init_succeeded_disable"
            else:
                action = "init_succeeded_off"
            self.state_model.perform_action(action)

    def always_executed_hook(self):
        """
        Method always executed before any TANGO command is executed.
        """
        if self.hardware_manager is not None:
            self.hardware_manager.poll()

    def delete_device(self):
        """
        Hook to delete resources allocated in the
        :py:meth:`~.MccsSubrack.InitCommand.do` method of the nested
        :py:class:`~.MccsSubrack.InitCommand` class.

        This method allows for any memory or other resources allocated
        in the :py:meth:`~.MccsSubrack.InitCommand.do` method to be
        released. This method is called by the device destructor, and by
        the Init command when the Tango device server is re-initialised.
        """
        self._message_queue.terminate_thread()
        self._message_queue.join()

    # ----------
    # Callbacks
    # ----------
    def are_tpms_on_changed(self, are_tpms_on):
        """
        Callback to be called whenever power to the TPMs changes;
        responsible for updating the tango side of things i.e. making
        sure the attribute is up to date, and events are pushed.

        :param are_tpms_on: whether each TPM is pwoered
        :type are_tpms_on: list(bool)
        """
        if self._are_tpms_on == are_tpms_on:
            return
        self._are_tpms_on = list(are_tpms_on)
        self.push_change_event("areTpmsOn", self._are_tpms_on)

    def health_changed(self, health):
        """
        Callback to be called whenever the HealthModel's health state
        changes; responsible for updating the tango side of things i.e.
        making sure the attribute is up to date, and events are pushed.

        :param health: the new health value
        :type health: :py:class:`~ska_tango_base.control_model.HealthState`
        """
        if self._health_state == health:
            return
        self._health_state = health
        self.push_change_event("healthState", health)

    # ----------
    # Attributes
    # ----------

    @attribute(dtype="DevULong")
    def aHeartBeat(self):
        """
        Return the Heartbeat attribute value.

        :return: heart beat as a percentage
        """
        return self._heart_beat

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
        self.logger.warning("Switching simulation mode to " + str(value))
        self.hardware_manager.simulation_mode = value

    @attribute(
        dtype=("DevFloat",),
        max_dim_x=2,
        label="Backplane temperatures",
        unit="Celsius",
    )
    def backplaneTemperatures(self):
        """
        Return the temperatures of the subrack backplane. Two values are
        returned, respectively for the first (bays 1-4) and second (bays
        5-8) halves of the backplane.

        :return: the temperatures of the subrack backplane
        :rtype: tuple(float)
        """
        return tuple(self.hardware_manager.backplane_temperatures)

    @attribute(
        dtype=("DevFloat",),
        max_dim_x=2,
        label="Subrack board temperatures",
        unit="Celsius",
    )
    def boardTemperatures(self):

        """
        Return the temperatures of the subrack management board. Two
        values are returned.

        :return: the temperatures of the subrack management board
        :rtype: tuple(float)
        """
        return tuple(self.hardware_manager.board_temperatures)

    @attribute(dtype="float", label="Board current")
    def boardCurrent(self):
        """
        Return the subrack management board current. Total current
        provided by the two power supplies.

        :return: the subrack management board current
        :rtype: float
        """
        return self.hardware_manager.board_current

    @attribute(
        dtype=("DevFloat",),
        max_dim_x=4,
        label="Subrack fans speeds (RPM)",
    )
    def subrackFanSpeeds(self):
        """
        Return the subrack fan speeds, in RPM Four fans are present in
        the subrack back side.

        :return: the subrack fan speeds
        :rtype: tuple(float)
        """
        return tuple(self.hardware_manager.subrack_fan_speeds)

    @attribute(
        dtype=("DevFloat",),
        max_dim_x=4,
        label="Subrack fans speeds (%)",
    )
    def subrackFanSpeedsPercent(self):
        """
        Return the subrack fan speeds in percent. This is the commanded
        value, the relation between this level and the actual RPMs is
        not linear. Subrack speed is managed automatically by the
        controller, by default (see subrack_fan_mode) Commanded speed is
        the same for fans 1-2 and 3-4.

        :return: the subrack fan speeds in percent
        :rtype: list(float)
        """
        return tuple(self.hardware_manager.subrack_fan_speeds_percent)

    @attribute(
        dtype=("DevUShort",),
        max_dim_x=4,
        label="Subrack Fan Mode",
    )
    def subrackFanMode(self):
        """
        Return the subrackFanMode. The mode is 1 (AUTO) at power-on When
        mode is AUTO, the fan speed is managed automatically. When mode
        is MANUAL (0), the fan speed is directly controlled using the
        SetSubrackFanSpeed command Mode is the same for fans 1-2 and
        3-4.

        :return: the subrack fan mode, 1 AUTO 0 MANUAL
        :rtype: tuple(int)
        """
        return tuple(self.hardware_manager.subrack_fan_mode)

    # @attribute(
    #     dtype=("DevShort",),
    #     label="TPM On/Off",
    #     max_dim_x=8,
    # )
    # def tpmOnOff(self):
    #     """
    #     Return a list to get Power On status of inserted tpm: 0 off or
    #     not present, 1 power on.
    #
    #     :return: the TPMs On or Off
    #     :rtype: tuple(int)
    #     """
    #     return tuple(self.hardware_manager.tpm_on_off)

    @attribute(
        dtype=("DevBoolean",),
        max_dim_x=8,
        label="TPM present",
    )
    def tpmPresent(self):
        """
        Return info about TPM board present on subrack. Returns a list
        of 8 Bool specifying presence of TPM in bays 1-8.

        :return: the TPMs detected
        :rtype: tuple(bool)
        """
        return tuple(self.hardware_manager.tpm_present)

    @attribute(
        dtype=("DevUShort",),
        max_dim_x=8,
        label="TPM Supply Fault",
    )
    def tpmSupplyFault(self):
        """
        Return info about about TPM supply fault status. Returns a list
        of 8 int specifying fault codeof TPM in bays 1-8 Current codes
        are 0 (no fault) or 1 (fault)

        :return: the TPM supply fault status
        :rtype: tuple(int)
        """
        return tuple(self.hardware_manager.tpm_supply_fault)

    @attribute(dtype=(float,), label="TPM temperatures", max_dim_x=8)
    def tpmTemperatures(self):
        """
        Return the temperatures of the TPMs housed in subrack bays.
        COmmand is not yet implemented.

        :return: the TPM temperatures
        :rtype: tuple(float)
        """
        return tuple(self.hardware_manager.tpm_temperatures)

    @attribute(
        dtype=("DevFloat",),
        max_dim_x=8,
        label="TPM power",
    )
    def tpmPowers(self):
        """
        Return the power used by TPMs in the subrack bays.

        :return: the TPM powers
        :rtype: tuple(float)
        """
        return tuple(self.hardware_manager.tpm_powers)

    @attribute(
        dtype=("DevFloat",),
        max_dim_x=8,
        label="TPM voltage",
    )
    def tpmVoltages(self):
        """
        Return the voltage at the power connector in the subrack bays
        Voltage is (approx) 0 for powered off bays.

        :return: the TPM voltages
        :rtype: tuple(float)
        """
        return tuple(self.hardware_manager.tpm_voltages)

    @attribute(
        dtype=("DevFloat",),
        max_dim_x=8,
        label="TPM currents",
    )
    def tpmCurrents(self):
        """
        Return the currents of the subrack bays (hence the currents of
        the TPMs housed in those bays).

        :return: the TPM currents
        :rtype: tuple(float)
        """
        return self.hardware_manager.tpm_currents

    @attribute(dtype=int, label="TPM count")
    def tpmCount(self):
        """
        Return the number of TPMs connected to this subrack.

        :return: the number of TPMs connected to this subrack
        :rtype: int
        """
        return self.hardware_manager.tpm_count

    @attribute(dtype=(bool,), max_dim_x=256, label="Are TPMs On")
    def areTpmsOn(self):
        """
        Return whether each TPM is powered or not.

        The main reason this attribute exists is so that individual Tile
        devices can subscribe to change events on it. From this they can
        figure out when the subrack has turned off/on power to their
        TPM.

        :return: whether each TPM is powered or not
        :rtype: tuple(bool)
        """
        return self.hardware_manager.are_tpms_on()

    @attribute(
        dtype=("DevFloat",),
        max_dim_x=3,
        label="power supply fan speed",
    )
    def powerSupplyFanSpeeds(self):
        """
        Return the powerSupply FanSpeed for the two redundant power
        supplies in percent of maximum.

        :return: the power supply fan speeds
        :rtype: tuple(float)
        """
        return tuple(self.hardware_manager.power_supply_fan_speeds)

    @attribute(
        dtype=("DevFloat",),
        max_dim_x=2,
        label="power_supply current",
    )
    def powerSupplyCurrents(self):
        """
        Return the power supply currents.

        :return: the power supply currents for the two redundant power supplies
        :rtype: tuple(float)
        """
        return tuple(self.hardware_manager.power_supply_currents)

    @attribute(
        dtype=("DevFloat",),
        max_dim_x=2,
        label="power_supply Powers",
    )
    def powerSupplyPowers(self):
        """
        Return the power supply power for the two redundant power
        supplies.

        :return: the power supply power
        :rtype: tuple(float)
        """
        return tuple(self.hardware_manager.power_supply_powers)

    @attribute(
        dtype=("DevFloat",),
        max_dim_x=2,
        label="power_supply voltage",
    )
    def powerSupplyVoltages(self):
        """
        Return the power supply voltages for the two redundant power
        supplies.

        :return: the power supply voltages
        :rtype: tuple(float)
        """
        return tuple(self.hardware_manager.power_supply_voltages)

    # --------
    # Commands
    # --------
    class DisableCommand(SKABaseDevice.DisableCommand):
        """
        Class for handling the Disable() command.

        :todo: We assume for now that the Subrack hardware has control of
            its own power mode i.e. is able to turn itself off and on.
            Actually it is more likely that some upstream hardware would
            turn the subrack off and on, in which case this command would be
            implemented by passing the command to the tango device that manages
            the upstream hardware
        """

        def do(self):
            """
            Stateless hook implementing the functionality of the
            (inherited) :py:meth:`ska_tango_base.SKABaseDevice.Disable`
            command for this :py:class:`.MccsSubrack` device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            success = hardware_manager.off()

            return create_return(success, "disable")

    class StandbyCommand(SKABaseDevice.StandbyCommand):
        """
        Class for handling the Standby() command.

        Actually the subrack hardware has no standby mode, so when this
        device is told to go to standby mode, it switches on / remains
        on.

        :todo: We assume for now that the subrack hardware has control of
            its own power mode i.e. is able to turn itself off and on.
            Actually it is more likely that some upstream hardware would
            turn the subrack off and on, in which case this command would
            be implemented by passing the command to the tango device
            that manages the upstream hardware.
        """

        def do(self):
            """
            Stateless hook implementing the functionality of the
            (inherited) :py:meth:`ska_tango_base.SKABaseDevice.Standby`
            command for this :py:class:`.MccsSubrack` device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            success = hardware_manager.on()
            return create_return(success, "standby")

    class OffCommand(SKABaseDevice.OffCommand):
        """
        Class for handling the Off() command.

        :todo: We assume for now that the subrack hardware has control of
            its own power mode i.e. is able to turn itself off and on.
            Actually it is more likely that some upstream hardware
            would turn the subrack off and on, in which case this command
            would be implemented by passing the command to the tango
            device that manages the upstream hardware.
        """

        def do(self):
            """
            Stateless hook implementing the functionality of the
            (inherited) :py:meth:`ska_tango_base.SKABaseDevice.Off`
            command for this :py:class:`.MccsSubrack` device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            # TODO: For now, OFF represents the highest state of device
            # readiness for a device that is not actually on. i.e. state
            # OFF means the hardware is on. This is a
            # counterintuitive mess that will be fixed in SP-1501.
            hardware_manager = self.target
            success = hardware_manager.on()
            return create_return(success, "off")

    class IsTpmOnCommand(BaseCommand):
        """
        The command class for the IsTpmOn command.
        """

        def do(self, argin):
            """
            Stateless hook for implementation of
            :py:meth:`.MccsSubrack.IsTpmOn` command functionality.

            :param argin: the logical tpm id of the TPM to power
                up
            :type argin: int

            :return: whether the specified TPM is on or not
            :rtype: bool
            """
            hardware_manager = self.target
            try:
                return hardware_manager.is_tpm_on(argin)
            except ValueError:
                # The subrack itself is not on. We don't want o
                return None

        def is_allowed(self):
            """
            Whether this command is allowed to run.

            :returns: whether this command is allowed to run
            :rtype: bool
            """
            return self.target.power_mode in [PowerMode.OFF, PowerMode.ON]

    def is_IsTpmOn_allowed(self):
        """
        Whether the ``Reset()`` command is allowed to be run in the
        current state.

        :returns: whether the ``Reset()`` command is allowed to be run in the
            current state
        :rtype: bool
        """
        handler = self.get_command_object("IsTpmOn")
        return handler.is_allowed()

    @command(dtype_in="DevULong", dtype_out=bool)
    @DebugIt()
    def IsTpmOn(self, argin):
        """
        Check Power up the TPM.

        :param argin: the logical TPM id of the TPM to check
        :type argin: int

        :return: whether the specified TPM is on or not
        :rtype: bool
        """
        handler = self.get_command_object("IsTpmOn")
        return handler(argin)

    class PowerOnTpmCommand(ResponseCommand):
        """
        The command class for the PowerOnTpm command.

        Power on an individual TPM, specified by the TPM ID (range 1-8)
        """

        def do(self, argin):
            """
            Stateless hook for implementation of
            :py:meth:`.MccsSubrack.PowerOnTpm`
            command functionality.

            :param argin: the logical TPM id of the TPM to power
                up
            :type argin: int

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            success = hardware_manager.turn_on_tpm(argin)
            return create_return(success, f"TPM {argin} power-on")

        def is_allowed(self):
            """
            Whether this command is allowed to run.

            :returns: whether this command is allowed to run
            :rtype: bool
            """
            return self.target.power_mode in [PowerMode.OFF, PowerMode.ON]

    def is_PowerOnTpm_allowed(self):
        """
        Whether the ``PowerOnTpm()`` command is allowed to be run in the
        current state.

        :returns: whether the ``PowerOnTpm()`` command is allowed to be run in the
            current state
        :rtype: bool
        """
        handler = self.get_command_object("PowerOnTpm")
        return handler.is_allowed()

    @command(
        dtype_in="DevULong",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def PowerOnTpm(self, argin):
        """
        Power up the TPM. Power on an individual TPM, specified by the
        TPM ID (range 1-8) Execution time is ~1.5 seconds.

        :param argin: the logical id of the TPM to power
            up
        :type argin: int

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("PowerOnTpm")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class PowerOffTpmCommand(ResponseCommand):
        """
        The command class for the PowerOffTpm command.
        """

        def do(self, argin):
            """
            Stateless hook for implementation of
            :py:meth:`.MccsSubrack.PowerOffTpm`
            command functionality.

            :param argin: the logical id of the TPM to power
                down
            :type argin: int

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            success = hardware_manager.turn_off_tpm(argin)
            return create_return(success, f"TPM {argin} power-off")

        def is_allowed(self):
            """
            Whether this command is allowed to run.

            :returns: whether this command is allowed to run
            :rtype: bool
            """
            return self.target.power_mode in [PowerMode.OFF, PowerMode.ON]

    def is_PowerOffTpm_allowed(self):
        """
        Whether the ``PowerOffTpm()`` command is allowed to be run in
        the current state.

        :returns: whether the ``PowerOffTpm()`` command is allowed to be run in the
            current state
        :rtype: bool
        """
        handler = self.get_command_object("PowerOffTpm")
        return handler.is_allowed()

    @command(
        dtype_in="DevULong",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def PowerOffTpm(self, argin):
        """
        Power down the TPM. Power off an individual TPM, specified by
        the TPM ID (range 1-8) Execution time is ~1.5 seconds.

        :param argin: the logical id of the TPM to power
            down
        :type argin: int

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("PowerOffTpm")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class PowerUpTpmsCommand(ResponseCommand):
        """
        The command class for the PowerUpTpms command.
        """

        def do(self):
            """
            Stateless hook for implementation of
            :py:meth:`.MccsSubrack.PowerUpTpms`
            command functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            success = hardware_manager.turn_on_tpms()
            return create_return(success, "TPMs power-up")

        def is_allowed(self):
            """
            Whether this command is allowed to run.

            :returns: whether this command is allowed to run
            :rtype: bool
            """
            return self.target.power_mode in [PowerMode.OFF, PowerMode.ON]

    def is_PowerUpTpms_allowed(self):
        """
        Whether the ``PowerUpTpm()`` command is allowed to be run in the
        current state.

        :returns: whether the ``PowerUpTpms()`` command is allowed to be run in the
            current state
        :rtype: bool
        """
        handler = self.get_command_object("PowerUpTpms")
        return handler.is_allowed()

    @command(
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def PowerUpTpms(self):
        """
        Power up the TPMs. Power on all the TPMs in the subrack.
        Execution time depends on the number of TPMs present, for a
        fully populated subrack it may exceed 10 seconds.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("PowerUpTpms")
        (return_code, message) = handler()
        return [[return_code], [message]]

    class PowerDownTpmsCommand(ResponseCommand):
        """
        The command class for the PowerDownTpms command.
        """

        def do(self):
            """
            Stateless hook for implementation of
            :py:meth:`.MccsSubrack.PowerDownTpms`
            command functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            success = hardware_manager.turn_off_tpms()
            return create_return(success, "TPM power-down")

        def is_allowed(self):
            """
            Whether this command is allowed to run.

            :returns: whether this command is allowed to run
            :rtype: bool
            """
            return self.target.power_mode in [PowerMode.OFF, PowerMode.ON]

    def is_PowerDownTpms_allowed(self):
        """
        Whether the ``PowerDownTpms()`` command is allowed to be run in
        the current state.

        :returns: whether the ``PowerDownTpms()`` command is allowed to be run in the
            current state
        :rtype: bool
        """
        handler = self.get_command_object("PowerDownTpms")
        return handler.is_allowed()

    @command(
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def PowerDownTpms(self):
        """
        Power down all the TPMs. Power off all the TPMs in the subrack.
        Execution time depends on the number of TPMs present, for a
        fully populated subrack it may exceed 10 seconds.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("PowerDownTpms")
        (return_code, message) = handler()
        return [[return_code], [message]]

    class SetSubrackFanSpeedCommand(ResponseCommand):
        """
        Class for handling the SetSubrackFanSpeed() command.

        This command set the backplane fan speed.
        """

        SUCCEEDED_MESSAGE = "SetSubrackFanSpeed command completed OK"

        def do(self, argin):
            """
            Hook for implementation of
            :py:meth:'.MccsSubrack.SetSubrackFanSpeed' command
            functionality.

            :param argin: a JSON-encoded dictionary of arguments
            :type argin: str

            :return: A tuple containing a return code and a string message
                indicating status. The message is for information purpose only.
            :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            :raises ValueError: if the JSON input lacks mandatory parameters
            """
            hardware_manager = self.target

            params = json.loads(argin)
            fan_id = params.get("FanID", None)
            speed_percent = params.get("SpeedPWN%", None)
            if fan_id or speed_percent is None:
                self.logger.error("fan_ID and fan speed are mandatory parameters")
                raise ValueError("fan_ID and fan speed are mandatory parameters")

            success = hardware_manager.set_subrack_fan_speed(fan_id, speed_percent)
            return create_return(success, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def SetSubrackFanSpeed(self, argin):
        """
        Set the subrack backplane fan speed.

        :param argin: json dictionary with mandatory keywords:

        * fan_id - (int) id of the selected fan accepted value: 1-4
        * speed_percent - (float) percentage value of fan RPM  (MIN 0=0% - MAX
                100=100%)

        Setting fan speed for one of fans in groups (1-2) and (3-4) sets
        the speed for both fans in that group

        :type argin: str

        :return: A tuple containing return code and string message indicating
                status. The message is for information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("SetSubrackFanSpeed")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class SetSubrackFanModeCommand(ResponseCommand):
        """
        Class for handling the SetSubrackFanMode() command.

        This command can set the selected fan to manual or auto mode.
        """

        SUCCEEDED_MESSAGE = "SetSubrackFanMode command completed OK"

        def do(self, argin):
            """
            Hook for the implementation of
            py:meth:`.MccsSubrack.SetSubrackFanMode` command
            functionality.

            :param argin: a JSON-encoded dictionary of arguments
            :type argin: str

            :return: A tuple containing a return code and a string
                    message indicating status. The message is for
                    information purpose only.
            :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            :raises ValueError: if the JSON input lacks of mandatory parameters
            """
            hardware_manager = self.target
            params = json.loads(argin)
            fan_id = params.get("fan_id", None)
            mode = params.get("mode", None)
            if fan_id or mode is None:
                self.logger.error("Fan_id and mode are mandatory parameters")
                raise ValueError("Fan_id and mode are mandatory parameter")

            success = hardware_manager.set_subrack_fan_mode(fan_id, mode)
            return create_return(success, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def SetSubrackFanMode(self, argin):
        """
        Set Fan Operational Mode: 1 AUTO, 0 MANUAL.

        :param argin: json dictionary with mandatory keywords:

        * fan_id - (int) id of the selected fan accepted value: 1-4
        * mode - (int) 1 AUTO, 0 MANUAL

        Setting fan speed for one of fans in groups (1-2) and (3-4) sets
        the speed for both fans in that group

        :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("SetSubrackFanMode")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class SetPowerSupplyFanSpeedCommand(ResponseCommand):
        """
        Class for handling the SetPowerSupplyFanSpeed command.

        This command set the selected power supply fan speed.
        """

        SUCCEEDED_MESSAGE = "SetPowerSupplyFanSpeed command completed OK"

        def do(self, argin):
            """
            Hook for the implementation of
            py:meth:`.MccsSubrack.SetPowerSupplyFanSpeed` command
            functionality.

            :param argin: a JSON-encoded dictionary of arguments
            :type argin: str

            :return: A tuple containing a return code and a string
                    message indicating status. The message is for
                    information purpose only.
            :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            :raises ValueError: if the JSON input lacks of mandatory parameters
            """
            hardware_manager = self.target

            params = json.loads(argin)
            power_supply_fan_id = params.get("power_supply_fan_id", None)
            speed_percent = params.get("speed_%", None)
            if power_supply_fan_id or speed_percent is None:
                self.logger.error(
                    "power_supply_fan_id and speed_percent are mandatory " "parameters"
                )
                raise ValueError(
                    "power_supply_fan_id and speed_percent are mandatory " "parameters"
                )

            success = hardware_manager.set_power_supply_fan_speed(
                power_supply_fan_id, speed_percent
            )
            return create_return(success, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    @DebugIt()
    def SetPowerSupplyFanSpeed(self, argin):
        """
        Set the selected power supply fan speed.

        :param argin: json dictionary with mandatory keywords:

        * power_supply_id - (int) power supply id from 1 to 2
        * speed_percent - (float) fanspeed in percent

        :type argin: str

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("SetPowerSupplyFanSpeed")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    def _update_health_state(self, health_state):
        """
        Update and push a change event for the healthState attribute.

        :param health_state: The new health state
        :type health_state: :py:class:`~ska_tango_base.control_model.HealthState`
        """
        self.push_change_event("healthState", health_state)
        self._health_state = health_state
        self.logger.info("health state = " + str(health_state))

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    @DebugIt()
    def On(self, json_args):
        """
        Send message with response.

        :param json_args: JSON encoded messaging system and command arguments
        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """

        # TODO: The callback parameters here could be empty as this "On"
        #       command is used by the StartUp command that is still
        #       executed sequentially.
        kwargs = json.loads(json_args)
        respond_to_fqdn = kwargs.get("respond_to_fqdn")
        callback = kwargs.get("callback")

        if respond_to_fqdn and callback:
            (
                result_code,
                _,
                message_uid,
            ) = self._message_queue.send_message_with_response(
                command="On", respond_to_fqdn=respond_to_fqdn, callback=callback
            )
            return [[result_code], [message_uid]]
        else:
            # Call On sequentially
            handler = self.get_command_object("On")
            (result_code, message) = handler(json_args)
            return [[result_code], [message]]

    class OnCommand(SKABaseDevice.OnCommand):
        """
        Class for handling the On() command.
        """

        SUCCEEDED_MESSAGE = "Subrack On command completed OK"
        FAILED_MESSAGE = "Subrack On command failed"

        def do(self, argin):
            """
            Stateless hook implementing the functionality of the
            (inherited) :py:meth:`ska_tango_base.SKABaseDevice.On`
            command for this :py:class:`.MccsStation` device.

            :param argin: JSON encoded messaging system and command arguments
            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            # :rcltodo We can't add simulated time here because
            # a) it should be simulated in a simulator (ideally)
            # b) the startup command doesn't use messages throughout so would
            #    cause a Tango command timeout
            # time.sleep(5)
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)


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

    return MccsSubrack.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
