# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""
This module contains an implementation of the MCCS APIU device and
related classes.
"""
import threading
import json

from tango import DebugIt, EnsureOmniThread, SerialModel, Util
from tango.server import attribute, command, device_property

from ska_tango_base import SKABaseDevice
from ska_tango_base.commands import BaseCommand, ResponseCommand, ResultCode
from ska_tango_base.control_model import HealthState, SimulationMode
from ska_low_mccs.events import EventManager
from ska_low_mccs.hardware import (
    HardwareHealthEvaluator,
    OnOffHardwareManager,
    PowerMode,
    SimulableHardwareFactory,
    SimulableHardwareManager,
)
from ska_low_mccs.health import HealthModel
from ska_low_mccs.apiu.apiu_simulator import APIUSimulator
from ska_low_mccs.message_queue import MessageQueue

__all__ = [
    "APIUHardwareFactory",
    "APIUHardwareHealthEvaluator",
    "APIUHardwareManager",
    "MccsAPIU",
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
        return (ResultCode.OK, f"APIU {action} is redundant")
    elif success:
        return (ResultCode.OK, f"APIU {action} successful")
    else:
        return (ResultCode.FAILED, f"APIU {action} failed")


class APIUHardwareHealthEvaluator(HardwareHealthEvaluator):
    """
    A placeholder for a class that implements a policy by which the
    antenna hardware manager evaluates the health of its hardware.

    At present this just inherits from the base class unchanged.
    """

    pass


class APIUHardwareFactory(SimulableHardwareFactory):
    """
    A hardware factory for APIU hardware.

    At present, this returns a
    :py:class:`~ska_low_mccs.apiu.apiu_simulator.APIUSimulator` object
    when in simulation mode, and raises :py:exc:`NotImplementedError`
    if the hardware is sought whilst not in simulation mode
    """

    def __init__(self, simulation_mode, antenna_count):
        """
        Create a new factory instance.

        :param antenna_count: number of antennas that are attached to
            the APIU
        :type antenna_count: int
        :param simulation_mode: the initial simulation mode of this
            hardware manager
        :type simulation_mode:
            :py:class:`~ska_tango_base.control_model.SimulationMode`
        """
        self._antenna_count = antenna_count
        super().__init__(simulation_mode)

    def _create_static_simulator(self):
        """
        Returns a hardware simulator.

        :return: a hardware simulator for the tile
        :rtype:
            :py:class:`ska_low_mccs.apiu.apiu_simulator.ApiuSimulator`
        """
        return APIUSimulator(self._antenna_count)


class APIUHardwareManager(OnOffHardwareManager, SimulableHardwareManager):
    """
    This class manages APIU hardware.

    :todo: So far all we can do with APIU hardware is turn it off and
        on. We need to implement monitoring.
    """

    def __init__(
        self,
        simulation_mode,
        antenna_count,
        are_antennas_on_change_callback,
        _factory=None,
    ):
        """
        Initialise a new APIUHardwareManager instance.

        :param simulation_mode: the initial simulation mode of this
            hardware manager
        :type simulation_mode: :py:class:`~ska_tango_base.control_model.SimulationMode`
        :param antenna_count: number of antennas that are attached to
            the APIU
        :type antenna_count: int
        :param are_antennas_on_change_callback: a callback to be called
            when the are_antennas_on property changes
        :type are_antennas_on_change_callback: callable
        :param _factory: allows for substitution of a hardware factory.
            This is useful for testing, but generally should not be used
            in operations.
        :type _factory: :py:class:`.APIUHardwareFactory`
        """
        hardware_factory = _factory or APIUHardwareFactory(
            simulation_mode == SimulationMode.TRUE, antenna_count
        )
        super().__init__(hardware_factory, APIUHardwareHealthEvaluator())

        self._are_antennas_on = None
        self._are_antennas_on_change_callback = are_antennas_on_change_callback

    def connect(self):
        """
        Establish a connection to the APIU hardware.

        :return: whether successful
        :rtype: bool
        """
        success = super().connect()
        if success:
            self._update_are_antennas_on()
        return success

    @property
    def voltage(self):
        """
        The voltage of the hardware.

        :return: the voltage of the hardware
        :rtype: float
        """
        return self._factory.hardware.voltage

    @property
    def current(self):
        """
        The current of the hardware.

        :return: the current of the hardware
        :rtype: float
        """
        return self._factory.hardware.current

    @property
    def temperature(self):
        """
        The temperature of the hardware.

        :return: the temperature of the hardware
        :rtype: float
        """
        return self._factory.hardware.temperature

    @property
    def humidity(self):
        """
        The humidity of the hardware.

        :return: the humidity of the hardware
        :rtype: float
        """
        return self._factory.hardware.humidity

    @property
    def antenna_count(self):
        """
        Return the number of antennas managed by this APIU.

        :return: the number of antennas managed by this APIU
        :rtype: int
        """
        return self._factory.hardware.antenna_count

    def turn_off_antenna(self, logical_antenna_id):
        """
        Turn off a specified antenna.

        :param logical_antenna_id: the APIU's internal id for the
            antenna to be turned off
        :type logical_antenna_id: int

        :return: whether successful, or None if there was nothing to do
        :rtype: bool or None
        """
        if not self._factory.hardware.is_antenna_on(logical_antenna_id):
            return None
        self._factory.hardware.turn_off_antenna(logical_antenna_id)
        self._update_are_antennas_on()
        return not self._factory.hardware.is_antenna_on(logical_antenna_id)

    def turn_on_antenna(self, logical_antenna_id):
        """
        Turn on a specified antenna.

        :param logical_antenna_id: the APIU's internal id for the
            antenna to be turned on
        :type logical_antenna_id: int

        :return: whether successful, or None if there was nothing to do
        :rtype: bool or None
        """
        if self._factory.hardware.is_antenna_on(logical_antenna_id):
            return None
        self._factory.hardware.turn_on_antenna(logical_antenna_id)
        self._update_are_antennas_on()
        return self._factory.hardware.is_antenna_on(logical_antenna_id)

    def turn_off_antennas(self):
        """
        Turn off all antennas.

        :return: whether successful, or None if there was nothing to do
        :rtype: bool or None
        """
        if not any(self.are_antennas_on()):
            return None
        self._factory.hardware.turn_off_antennas()
        self._update_are_antennas_on()
        return not any(self.are_antennas_on())

    def turn_on_antennas(self):
        """
        Turn on all antennas.

        :return: whether successful, or None if there was nothing to do
        :rtype: bool or None
        """
        if all(self.are_antennas_on()):
            return None
        self._factory.hardware.turn_on_antennas()
        self._update_are_antennas_on()
        return all(self.are_antennas_on())

    def are_antennas_on(self):
        """
        Returns whether each antenna is powered or not.

        :return: whether each antenna is powered or not.
        :rtype: list(bool)
        """
        self._update_are_antennas_on()
        return self._are_antennas_on

    def is_antenna_on(self, logical_antenna_id):
        """
        Gets whether a specified antenna is turned on.

        :param logical_antenna_id: this APIU's internal id for the
            antenna being queried
        :type logical_antenna_id: int

        :return: whether the antenna is on
        :rtype: bool
        """
        self._update_are_antennas_on()
        return (
            self._are_antennas_on is not None
            and self._are_antennas_on[logical_antenna_id - 1]
        )

    def _update_are_antennas_on(self):
        """
        Update our record of which antennas are off/on, ensureing that
        callbacks are called.
        """
        are_antennas_on = self._factory.hardware.are_antennas_on()
        if are_antennas_on is None:
            are_antennas_on = [False] * self.antenna_count

        if self._are_antennas_on != are_antennas_on:
            self._are_antennas_on = list(are_antennas_on)
            self._are_antennas_on_change_callback(self._are_antennas_on)

    def poll(self):
        """
        Poll the hardware.
        """
        super().poll()
        self._update_are_antennas_on()

    def get_antenna_current(self, logical_antenna_id):
        """
        Get the current of a specified antenna.

        :param logical_antenna_id: this APIU's internal id for the
            antenna for which the current is requested
        :type logical_antenna_id: int

        :return: the antenna current
        :rtype: float
        """
        return self._factory.hardware.get_antenna_current(logical_antenna_id)

    def get_antenna_voltage(self, logical_antenna_id):
        """
        Get the voltage of a specified antenna.

        :param logical_antenna_id: this APIU's internal id for the
            antenna for which the voltage is requested
        :type logical_antenna_id: int

        :return: the antenna voltage
        :rtype: float
        """
        return self._factory.hardware.get_antenna_voltage(logical_antenna_id)

    def get_antenna_temperature(self, logical_antenna_id):
        """
        Get the temperature of a specified antenna.

        :param logical_antenna_id: this APIU's internal id for the
            antenna for which the temperature is requested
        :type logical_antenna_id: int

        :return: the antenna temperature
        :rtype: float
        """
        return self._factory.hardware.get_antenna_temperature(logical_antenna_id)


class MccsAPIU(SKABaseDevice):
    """
    An implementation of MCCS APIU device.

    This class is a subclass of :py:class:`ska_tango_base.SKABaseDevice`.

    **Properties:**

    - Device Property
    """

    AntennaFQDNs = device_property(dtype=(str,))

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
            ("IsAntennaOn", self.IsAntennaOnCommand),
            ("PowerUpAntenna", self.PowerUpAntennaCommand),
            ("PowerDownAntenna", self.PowerDownAntennaCommand),
            ("PowerUp", self.PowerUpCommand),
            ("PowerDown", self.PowerDownCommand),
        ]:
            self.register_command_object(
                command_name,
                command_object(self.hardware_manager, self.state_model, self.logger),
            )

    class InitCommand(SKABaseDevice.InitCommand):
        """
        Class that implements device initialisation for the MCCS APIU
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
            :py:class:`.MccsAPIU`.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            super().do()
            device = self.target
            device._heart_beat = 0
            device.queue_debug = ""

            # TODO: the default value for simulationMode should be
            # FALSE, but we don't have real hardware to test yet, so we
            # can't take our devices out of simulation mode. Once we
            # have a driver for real hardware, we should change this
            # default to FALSE.
            device._simulation_mode = SimulationMode.TRUE

            device._are_antennas_on = None
            device.set_change_event("areAntennasOn", True, False)

            device._antenna_fqdns = list(device.AntennaFQDNs)

            device._isAlive = True
            device._overCurrentThreshold = 0.0
            device._overVoltageThreshold = 0.0
            device._humidityThreshold = 0.0

            device.hardware_manager = APIUHardwareManager(
                device._simulation_mode,
                len(device._antenna_fqdns),
                device.are_antennas_on_changed,
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
            device.event_manager = EventManager(self.logger)
            device._health_state = HealthState.UNKNOWN
            device.set_change_event("healthState", True, False)
            device.health_model = HealthModel(
                device.hardware_manager,
                None,
                device.event_manager,
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
            ensure that MccsAPIU transitions to a state that reflects
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
        :py:meth:`~.MccsAPIU.InitCommand.do` method of the nested
        :py:class:`~.MccsAPIU.InitCommand` class.

        This method allows for any memory or other resources allocated
        in the :py:meth:`~.MccsAPIU.InitCommand.do` method to be
        released. This method is called by the device destructor, and by
        the Init command when the Tango device server is re-initialised.
        """
        if self._message_queue.is_alive():
            self._message_queue.terminate_thread()
            self._message_queue.join()

    # ----------
    # Callbacks
    # ----------
    def are_antennas_on_changed(self, are_antennas_on):
        """
        Callback to be called whenever power to the antennas changes;
        responsible for updating the tango side of things i.e. making
        sure the attribute is up to date, and events are pushed.

        :param are_antennas_on: whether each antenna is pwoered
        :type are_antennas_on: list(bool)
        """
        if self._are_antennas_on == are_antennas_on:
            return
        self._are_antennas_on = list(are_antennas_on)
        self.push_change_event("areAntennasOn", self._are_antennas_on)

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
        self.logger.info("Switching simulation mode to " + str(value))
        self.hardware_manager.simulation_mode = value

    @attribute(dtype=int, label="antennas count")
    def antennaCount(self):
        """
        Return the number of antennas connected to this APIU.

        :return: the number of antennas connected to this APIU
        :rtype: int
        """
        return self.hardware_manager.antenna_count

    @attribute(dtype=(bool,), max_dim_x=256, label="Are Antennas On")
    def areAntennasOn(self):
        """
        Return whether each antenna is powered or not.

        :return: whether each antenna is powered or not
        :rtype: list(bool)
        """
        return self.hardware_manager.are_antennas_on()

    @attribute(dtype="DevDouble", label="Voltage", unit="Volts")
    def voltage(self):
        """
        Return the voltage attribute.

        :return: the voltage attribute
        :rtype: float
        """
        return self.hardware_manager.voltage

    @attribute(dtype="DevDouble", label="Current", unit="Amps")
    def current(self):
        """
        Return the current attribute.

        :return: the current value of the current attribute
        :rtype: float
        """
        return self.hardware_manager.current

    @attribute(dtype="DevDouble", label="Temperature", unit="degC")
    def temperature(self):
        """
        Return the temperature attribute.

        :return: the value of the temperature attribute
        :rtype: float
        """
        return self.hardware_manager.temperature

    @attribute(
        dtype="DevDouble",
        label="Humidity",
        unit="percent",
        # max_value=0.0,
        # min_value=100.0,
    )
    def humidity(self):
        """
        Return the humidity attribute.

        :return: the value of the humidity attribute
        :rtype: float
        """
        return self.hardware_manager.humidity

    @attribute(dtype="DevBoolean", label="Is alive?")
    def isAlive(self):
        """
        Return the isAlive attribute.

        :return: the value of the isAlive attribute
        :rtype: bool
        """
        return self._isAlive

    @attribute(dtype="DevDouble", label="Over current threshold", unit="Amp")
    def overCurrentThreshold(self):
        """
        Return the overCurrentThreshold attribute.

        :return: the value of the overCurrentThreshold attribute
        :rtype: float
        """
        return self._overCurrentThreshold

    @overCurrentThreshold.write
    def overCurrentThreshold(self, value):
        """
        Set the overCurrentThreshold attribute.

        :param value: new value for the overCurrentThreshold attribute
        :type value: float
        """
        self._overCurrentThreshold = value

    @attribute(dtype="DevDouble", label="Over Voltage threshold", unit="Volt")
    def overVoltageThreshold(self):
        """
        Return the overVoltageThreshold attribute.

        :return: the value of the overVoltageThreshold attribute
        :rtype: float
        """
        return self._overVoltageThreshold

    @overVoltageThreshold.write
    def overVoltageThreshold(self, value):
        """
        Set the overVoltageThreshold attribute.

        :param value: new value for the overVoltageThreshold attribute
        :type value: float
        """
        self._overVoltageThreshold = value

    @attribute(dtype="DevDouble", label="Humidity threshold", unit="percent")
    def humidityThreshold(self):
        """
        Return the humidity threshold.

        :return: the value of the humidityThreshold attribute
        :rtype: float
        """
        return self._humidityThreshold

    @humidityThreshold.write
    def humidityThreshold(self, value):
        """
        Set the humidityThreshold attribute.

        :param value: new value for the humidityThreshold attribute
        :type value: float
        """
        self._humidityThreshold = value

    # --------
    # Commands
    # --------
    class DisableCommand(SKABaseDevice.DisableCommand):
        """
        Class for handling the Disable() command.

        :todo: We assume for now that the APIU hardware has control of
            its own power mode i.e. is able to turn itself off and on.
            Actually it is more likely that some upstream hardware would
            turn the APIU off and on, in which case this command would be
            implemented by passing the command to the tango device that manages
            the upstream hardware
        """

        def do(self):
            """
            Stateless hook implementing the functionality of the
            (inherited) :py:meth:`ska_tango_base.SKABaseDevice.Disable`
            command for this :py:class:`.MccsAPIU` device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            hardware_manager = self.target

            success = hardware_manager.off()
            # because DISABLE is the state of lowest device readiness

            return create_return(success, "disable")

    class StandbyCommand(SKABaseDevice.StandbyCommand):
        """
        Class for handling the Standby() command.

        Actually the APIU hardware has no standby mode, so when this
        device is told to go to standby mode, it switches on / remains
        on.

        :todo: We assume for now that the APIU hardware has control of
            its own power mode i.e. is able to turn itself off and on.
            Actually it is more likely that some upstream hardware would
            turn the APIU off and on, in which case this command would
            be implemented by passing the command to the tango device
            that manages the upstream hardware.
        """

        def do(self):
            """
            Stateless hook implementing the functionality of the
            (inherited) :py:meth:`ska_tango_base.SKABaseDevice.Standby`
            command for this :py:class:`.MccsAPIU` device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            success = hardware_manager.on()
            return create_return(success, "standby")

    def _send_message(self, command, json_args):
        """
        Helper method to send a message to execute the specified
        command.

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
        self.logger.info(f"APIU {command}")

        kwargs = json.loads(json_args)
        respond_to_fqdn = kwargs.get("respond_to_fqdn")
        callback = kwargs.get("callback")
        if respond_to_fqdn and callback:
            self.logger.debug(f"APIU {command} message call")
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
            command = self.get_command_object(command)
            (result_code, message) = command(json_args)
            return [[result_code], [message]]

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def On(self, json_args):
        """
        Send a message to turn APIU on.

        :param json_args: JSON encoded messaging system and command arguments
        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        return self._send_message("On", json_args=json_args)

    class OnCommand(SKABaseDevice.OnCommand):
        """
        Class for handling the On() command.
        """

        def do(self, argin):
            """
            Stateless hook implementing the functionality of the
            (inherited) :py:meth:`ska_tango_base.SKABaseDevice.Off`
            command for this :py:class:`.MccsAPIU` device.

            :param argin: Argument containing JSON encoded command message and result
            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            (result_code, message) = super().do()
            # MCCS-specific Reset functionality goes here
            return (result_code, message)

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def Off(self, json_args):
        """
        Send a message to turn APIU off.

        :param json_args: JSON encoded messaging system and command arguments
        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        return self._send_message("Off", json_args=json_args)

    class OffCommand(SKABaseDevice.OffCommand):
        """
        Class for handling the Off() command.

        :todo: We assume for now that the APIU hardware has control of
            its own power mode i.e. is able to turn itself off and on.
            Actually it is more likely that some upstream hardware
            would turn the APIU off and on, in which case this command
            would be implemented by passing the command to the tango
            device that manages the upstream hardware.
        """

        def do(self, argin):
            """
            Stateless hook implementing the functionality of the
            (inherited) :py:meth:`ska_tango_base.SKABaseDevice.Off`
            command for this :py:class:`.MccsAPIU` device.

            :param argin: JSON encoded messaging system and command arguments
            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            hardware_manager = self.target

            success = hardware_manager.on()
            # because the OFF state is a state of high device readiness

            return create_return(success, "off")

    class IsAntennaOnCommand(BaseCommand):
        """
        The command class for the IsAntennaOn command.
        """

        def do(self, argin):
            """
            Stateless hook for implementation of
            :py:meth:`.MccsAPIU.IsAntennaOn` command functionality.

            :param argin: the logical antenna id of the antenna to power
                up
            :type argin: int

            :return: whether the specified antenna is on or not
            :rtype: bool
            """
            hardware_manager = self.target
            return hardware_manager.is_antenna_on(argin)

    @command(dtype_in="DevULong", dtype_out=bool)
    @DebugIt()
    def IsAntennaOn(self, argin):
        """
        Power up the antenna.

        :param argin: the logical antenna id of the antenna to power
            up
        :type argin: int

        :return: whether the specified antenna is on or not
        :rtype: bool
        """
        handler = self.get_command_object("IsAntennaOn")
        return handler(argin)

    class PowerUpAntennaCommand(ResponseCommand):
        """
        The command class for the PowerDownAntenna command.
        """

        def do(self, argin):
            """
            Stateless hook for implementation of
            :py:meth:`.MccsAPIU.PowerUpAntenna`
            command functionality.

            :param argin: the logical antenna id of the antenna to power
                up
            :type argin: int

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            success = hardware_manager.turn_on_antenna(argin)
            return create_return(success, f"antenna {argin} power-up")

    @command(
        dtype_in="DevULong",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def PowerUpAntenna(self, argin):
        """
        Power up the antenna.

        :param argin: the logical antenna id of the antenna to power
            up
        :type argin: int

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("PowerUpAntenna")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class PowerDownAntennaCommand(ResponseCommand):
        """
        The command class for the PowerDownAntenna command.
        """

        def do(self, argin):
            """
            Stateless hook for implementation of
            :py:meth:`.MccsAPIU.PowerDownAntenna`
            command functionality.

            :param argin: the logical antenna id of the antenna to power
                down
            :type argin: int

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            success = hardware_manager.turn_off_antenna(argin)
            return create_return(success, f"antenna {argin} power-down")

    @command(
        dtype_in="DevULong",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def PowerDownAntenna(self, argin):
        """
        Power down the antenna.

        :param argin: the logical antenna id of the antenna to power
            down
        :type argin: int

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("PowerDownAntenna")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class PowerUpCommand(ResponseCommand):
        """
        Class for handling the PowerUp() command.

        The PowerUp command turns on all of the antennas that are
        powered by this APIU.
        """

        def do(self):
            """
            Stateless hook for implementation of
            :py:meth:`.MccsAPIU.PowerUp` command
            functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            success = hardware_manager.turn_on_antennas()
            return create_return(success, "power-up")

    @command(
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def PowerUp(self):
        """
        Power up.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("PowerUp")
        (return_code, message) = handler()
        return [[return_code], [message]]

    class PowerDownCommand(ResponseCommand):
        """
        Class for handling the PowerDown() command.

        The PowerDown command turns on all of the antennas that are
        powered by this APIU.
        """

        def do(self):
            """
            Stateless hook for implementation of
            :py:meth:`.MccsAPIU.PowerDown`
            command functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            success = hardware_manager.turn_off_antennas()
            return create_return(success, "power-down")

    @command(
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def PowerDown(self):
        """
        Power down.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("PowerDown")
        (return_code, message) = handler()
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

    return MccsAPIU.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
