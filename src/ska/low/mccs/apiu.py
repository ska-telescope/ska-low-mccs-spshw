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

from tango import DebugIt, EnsureOmniThread
from tango.server import attribute, command

from ska.base import SKABaseDevice
from ska.base.commands import BaseCommand, ResponseCommand, ResultCode
from ska.base.control_model import SimulationMode
from ska.low.mccs.hardware import (
    HardwareHealthEvaluator,
    OnOffHardwareManager,
    SimulableHardwareFactory,
    SimulableHardwareManager,
)
from ska.low.mccs.apiu_simulator import APIUHardwareSimulator
from ska.low.mccs.health import HealthModel


__all__ = [
    # "AntennaHardwareHealthEvaluator",
    "APIUHardwareHealthEvaluator",
    "APIUHardwareManager",
    "MccsAPIU",
    "main",
]


def create_return(success, action):
    """
    Helper function to package up a boolean result into a
    (:py:class:`~ska.base.commands.ResultCode`, message) tuple

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
    :rtype: (:py:class:`ska.base.commands.ResultCode`, str)
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
    antenna hardware manager evaluates the health of its hardware. At
    present this just inherits from the base class unchanged.
    """

    pass


class APIUHardwareFactory(SimulableHardwareFactory):
    """
    A hardware factory for APIU hardware. At present, this returns a
    :py:class:`~ska.low.mccs.apiu_simulator.APIUSimulator` object when
    in simulation mode, and raises :py:exception:`NotImplementedError`
    if the hardware is sought whilst not in simulation mode
    """

    def __init__(self, simulation_mode):
        """
        Create a new factory instance

        :param simulation_mode: the initial simulation mode of this
            hardware manager
        :type simulation_mode:
            :py:class:`~ska.base.control_model.SimulationMode`
        """
        super().__init__(simulation_mode)

    def _create_simulator(self):
        """
        Returns a hardware simulator

        :return: a hardware simulator for the tile
        :rtype: :py:class:`TpmSimulator`
        """
        return APIUHardwareSimulator()


class APIUHardwareManager(OnOffHardwareManager, SimulableHardwareManager):
    """
    This class manages APIU hardware.

    :todo: So far all we can do with APIU hardware is turn it off and
        on. We need to implement monitoring.
    """

    def __init__(self, simulation_mode, _factory=None):
        """
        Initialise a new APIUHardwareManager instance

        :param simulation_mode: the initial simulation mode of this
            hardware manager
        :type simulation_mode: :py:class:`~ska.base.control_model.SimulationMode`
        """
        hardware_factory = _factory or APIUHardwareFactory(
            simulation_mode == SimulationMode.TRUE
        )
        super().__init__(hardware_factory, APIUHardwareHealthEvaluator())

    @property
    def voltage(self):
        """
        The voltage of the hardware

        :return: the voltage of the hardware
        :rtype: float
        """
        return self._factory.hardware.voltage

    @property
    def current(self):
        """
        The current of the hardware

        :return: the current of the hardware
        :rtype: float
        """
        return self._factory.hardware.current

    @property
    def temperature(self):
        """
        The temperature of the hardware

        :return: the temperature of the hardware
        :rtype: float
        """
        return self._factory.hardware.temperature

    @property
    def humidity(self):
        """
        The humidity of the hardware

        :return: the humidity of the hardware
        :rtype: float
        """
        return self._factory.hardware.humidity

    def turn_off_antenna(self, logical_antenna_id):
        """
        Turn off a specified antenna

        :param logical_antenna_id: the APIU's internal id for the
            antenna to be turned off
        :type logical_antenna_id: int

        :return: whether successful, or None if there was nothing to do
        :rtype: bool or None
        """
        if not self._factory.hardware.is_antenna_on(logical_antenna_id):
            return None
        self._factory.hardware.turn_off_antenna(logical_antenna_id)
        return not self._factory.hardware.is_antenna_on(logical_antenna_id)

    def turn_on_antenna(self, logical_antenna_id):
        """
        Turn on a specified antenna

        :param logical_antenna_id: the APIU's internal id for the
            antenna to be turned on
        :type logical_antenna_id: int

        :return: whether successful, or None if there was nothing to do
        :rtype: bool or None
        """
        if self._factory.hardware.is_antenna_on(logical_antenna_id):
            return None
        self._factory.hardware.turn_on_antenna(logical_antenna_id)
        return self._factory.hardware.is_antenna_on(logical_antenna_id)

    def is_antenna_on(self, logical_antenna_id):
        """
        Gets whether a specified antenna is turned on

        :param logical_antenna_id: this APIU's internal id for the
            antenna being queried
        :type logical_antenna_id: int

        :return: whether the antenna is on
        :rtype: bool
        """
        return self._factory.hardware.is_antenna_on(logical_antenna_id)

    def get_antenna_current(self, logical_antenna_id):
        """
        Get the current of a specified antenna

        :param logical_antenna_id: this APIU's internal id for the
            antenna for which the current is requested
        :type logical_antenna_id: int

        :return: the antenna current
        :rtype: float
        """
        return self._factory.hardware.get_antenna_current(logical_antenna_id)

    def get_antenna_voltage(self, logical_antenna_id):
        """
        Get the voltage of a specified antenna

        :param logical_antenna_id: this APIU's internal id for the
            antenna for which the voltage is requested
        :type logical_antenna_id: int

        :return: the antenna voltage
        :rtype: float
        """
        return self._factory.hardware.get_antenna_voltage(logical_antenna_id)

    def get_antenna_temperature(self, logical_antenna_id):
        """
        Get the temperature of a specified antenna

        :param logical_antenna_id: this APIU's internal id for the
            antenna for which the temperature is requested
        :type logical_antenna_id: int

        :return: the antenna temperature
        :rtype: float
        """
        return self._factory.hardware.get_antenna_temperature(logical_antenna_id)


class APIUHardware(Hardware):
    """
    A stub class to take the place of actual APIU hardware
    """

    VOLTAGE = 3.4
    CURRENT = 20.5
    TEMPERATURE = 20.4
    HUMIDITY = 23.9

    def __init__(self):
        """
        Initialise a new AntennaHardware instance
        """
        self._voltage = None
        self._current = None
        self._temperature = None
        self._humidity = None
        super().__init__()

    def off(self):
        """
        Turn me off
        """
        self._voltage = None
        self._current = None
        self._temperature = None
        self._humidity = None
        super().off()

    def on(self):
        """
        Turn me on
        """
        self._voltage = APIUHardware.VOLTAGE  # for testing purposes
        self._current = APIUHardware.CURRENT  # for testing purposes
        self._temperature = APIUHardware.TEMPERATURE  # for testing purposes
        self._humidity = APIUHardware.HUMIDITY  # for testing purposes
        super().on()

    @property
    def voltage(self):
        """
        Return my voltage

        :return: my voltage
        :rtype: float
        """
        return self._voltage

    @property
    def current(self):
        """
        Return my current

        :return: my current
        :rtype: float
        """
        return self._current

    @property
    def temperature(self):
        """
        Return my temperature

        :return: my temperature
        :rtype: float
        """
        return self._temperature

    @property
    def humidity(self):
        """
        Return my humidity

        :return: my humidity
        :rtype: float
        """
        return self._humidity


class APIUHardwareManager(HardwareManager):
    """
    This class manages APIU hardware.

    :todo: So far all we can do with APIU hardware is turn it off and
        on. We need to implement monitoring.
    """

    def __init__(self, hardware=None):
        """
        Initialise a new APIUHardwareManager instance

        At present, hardware is simulated by stub software, and so the
        only argument is an optional "hardware" instance. In future, its
        arguments will allow connection to the actual hardware

        :param hardware: the hardware itself, defaults to None. This only
            exists to facilitate testing.
        :type hardware: :py:class:`APIUHardware`
        """
        # polled hardware attributes
        self._voltage = None
        self._current = None
        self._temperature = None
        self._humidity = None
        super().__init__(hardware or APIUHardware())

    def poll_hardware(self):
        """
        Poll the hardware and update local attributes with values
        reported by the hardware.
        """
        self._is_on = self._hardware.is_on
        if self._is_on:
            self._voltage = self._hardware.voltage
            self._current = self._hardware.current
            self._temperature = self._hardware.temperature
            self._humidity = self._hardware.humidity
        else:
            self._voltage = None
            self._current = None
            self._temperature = None
            self._humidity = None
        self._update_health()

    @property
    def voltage(self):
        """
        The voltage of the hardware

        :return: the voltage of the hardware
        :rtype: float
        """
        return self._voltage

    @property
    def current(self):
        """
        The current of the hardware

        :return: the current of the hardware
        :rtype: float
        """
        return self._current

    @property
    def temperature(self):
        """
        The temperature of the hardware

        :return: the temperature of the hardware
        :rtype: float
        """
        return self._temperature

    @property
    def humidity(self):
        """
        The humidity of the hardware

        :return: the humidity of the hardware
        :rtype: float
        """
        return self._humidity

    def _evaluate_health(self):
        """
        Evaluate the health of the hardware

        :return: an evaluation of the health of the managed hardware
        :rtype: :py:class:`~ska.base.control_model.HealthState`
        """
        # TODO: look at the polled hardware values and maybe further
        # poke the hardware to check that it is okay. But for now:
        return HealthState.OK


class MccsAPIU(SKABaseDevice):
    """
    An implementation of MCCS APIU device.

    This class is a subclass of :py:class:`ska.base.SKABaseDevice`.

    **Properties:**

    - Device Property
    """

    class InitCommand(SKABaseDevice.InitCommand):
        """
        Class that implements device initialisation for the MCCS APIU
        device
        """

        def __init__(self, target, state_model, logger=None):
            """
            Create a new InitCommand

            :param target: the object that this command acts upon; for
                example, the device for which this class implements the
                command
            :type target: object
            :param state_model: the state model that this command uses
                 to check that it is allowed to run, and that it drives
                 with actions.
            :type state_model: :py:class:`DeviceStateModel`
            :param logger: the logger to be used by this Command. If not
                provided, then a default module logger will be used.
            :type logger: a logger that implements the standard library
                logger interface
            """
            super().__init__(target, state_model, logger)

            self._thread = None
            self._lock = threading.Lock()
            self._interrupt = False

        def do(self):
            """
            Initialises the attributes and properties of the
            :py:class:`MccsAPIU`.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`ska.base.commands.ResultCode`, str)
            """
            super().do()
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

            device._isAlive = True
            device._overCurrentThreshold = 0.0
            device._overVoltageThreshold = 0.0
            device._humidityThreshold = 0.0

            device.hardware_manager = APIUHardwareManager()
            device.event_manager = EventManager()
            device.health_model = HealthModel(
                device.hardware_manager, None, device.event_manager
            )

            device.hardware_manager.on()  # HACK until we have power management commands

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
                with self._lock:
                    self.succeeded()

        def _initialise_hardware_management(self, device):
            """
            Initialise the connection to the hardware being managed by
            this device. May also register commands that depend upon a
            connection to that hardware

            :param device: the device for which a connection to the
                hardware is being initialised
            :type device: :py:class:`~ska.base.SKABaseDevice`
            """
            device.hardware_manager = APIUHardwareManager(device._simulation_mode)

            args = (device.hardware_manager, device.state_model, self.logger)

            device.register_command_object(
                "IsAntennaOn", device.IsAntennaOnCommand(*args)
            )
            device.register_command_object(
                "PowerUpAntenna", device.PowerUpAntennaCommand(*args)
            )
            device.register_command_object(
                "PowerDownAntenna", device.PowerDownAntennaCommand(*args)
            )
            device.register_command_object("PowerUp", device.PowerUpCommand(*args))
            device.register_command_object("PowerDown", device.PowerDownCommand(*args))

        def _initialise_health_monitoring(self, device):
            """
            Initialise the health model for this device.

            :param device: the device for which the health model is
                being initialised
            :type device: :py:class:`~ska.base.SKABaseDevice`
            """
            device.set_change_event("healthState", True, True)
            device.set_archive_event("healthState", True, True)

            device.health_model = HealthModel(
                device.hardware_manager, None, None, device._update_health_state
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

    def always_executed_hook(self):
        """Method always executed before any TANGO command is executed."""
        if self.hardware_manager is not None:
            self.hardware_manager.poll()

    def delete_device(self):
        """
        Hook to delete resources allocated in the
        :py:meth:`~ska.low.mccs.apiu.MccsAPIU.InitCommand.do` method of the
        nested :py:class:`~ska.low.mccs.apiu.MccsAPIU.InitCommand` class.

        This method allows for any memory or other resources allocated in the
        :py:meth:`~ska.low.mccs.apiu.MccsAPIU.InitCommand.do` method to be
        released. This method is called by the device destructor, and by the Init
        command when the Tango device server is re-initialised.
        """

    # ----------
    # Attributes
    # ----------

    # redefinition from base classes to turn polling on
    @attribute(
        dtype=HealthState,
        polling_period=1000,
        doc="The health state reported for this device. "
        "It interprets the current device"
        " condition and condition of all managed devices to set this. "
        "Most possibly an aggregate attribute.",
    )
    def healthState(self):
        """
        returns the health of this device; which in this case means the
        rolled-up health of the entire MCCS subsystem

        :return: the rolled-up health of the MCCS subsystem
        :rtype: :py:class:`~ska.base.control_model.HealthState`
        """
        return self.health_model.health

    @attribute(dtype="DevDouble", label="Voltage", unit="Volts", polling_period=1000)
    def voltage(self):
        """
        Return the voltage attribute.

        :return: the voltage attribute
        :rtype: double
        """
        return self.hardware_manager.voltage

    @attribute(dtype="DevDouble", label="Current", unit="Amps", polling_period=1000)
    def current(self):
        """
        Return the current attribute.

        :return: the current value of the current attribute
        :rtype: double
        """
        return self.hardware_manager.current

    @attribute(dtype="DevDouble", label="Temperature", unit="degC", polling_period=1000)
    def temperature(self):
        """
        Return the temperature attribute.

        :return: the value of the temperature attribute
        :rtype: double
        """
        return self.hardware_manager.temperature

    @attribute(
        dtype="DevDouble",
        label="Humidity",
        unit="percent",
        polling_period=1000,
        # max_value=0.0,
        # min_value=100.0,
    )
    def humidity(self):
        """
        Return the humidity attribute.

        :return: the value of the humidity attribute
        :rtype: double
        """
        return self.hardware_manager.humidity

    @attribute(dtype="DevBoolean", label="Is alive?")
    def isAlive(self):
        """
        Return the isAlive attribute

        :return: the value of the isAlive attribute
        :rtype: boolean
        """
        return self._isAlive

    @attribute(dtype="DevDouble", label="Over current threshold", unit="Amp")
    def overCurrentThreshold(self):
        """
        Return the overCurrentThreshold attribute

        :return: the value of the overCurrentThreshold attribute
        :rtype: double
        """
        return self._overCurrentThreshold

    @overCurrentThreshold.write
    def overCurrentThreshold(self, value):
        """
        Set the overCurrentThreshold attribute.

        :param value: new value for the overCurrentThreshold attribute
        :type value: double
        """
        self._overCurrentThreshold = value

    @attribute(dtype="DevDouble", label="Over Voltage threshold", unit="Volt")
    def overVoltageThreshold(self):
        """
        Return the overVoltageThreshold attribute

        :return: the value of the overVoltageThreshold attribute
        :rtype: double
        """
        return self._overVoltageThreshold

    @overVoltageThreshold.write
    def overVoltageThreshold(self, value):
        """
        Set the overVoltageThreshold attribute.

        :param value: new value for the overVoltageThreshold attribute
        :type value: double
        """
        self._overVoltageThreshold = value

    @attribute(dtype="DevDouble", label="Humidity threshold", unit="percent")
    def humidityThreshold(self):
        """
        Return the humidity threshold

        :return: the value of the humidityThreshold attribute
        :rtype: double
        """
        return self._humidityThreshold

    @humidityThreshold.write
    def humidityThreshold(self, value):
        """
        Set the humidityThreshold attribute.

        :param value: new value for the humidityThreshold attribute
        :type value: double
        """
        self._humidityThreshold = value

    # --------
    # Commands
    # --------

    class IsAntennaOnCommand(BaseCommand):
        """
        The command class for the IsAntennaOn command
        """

        def do(self, argin):
            """
            Stateless hook for implementation of
            :py:meth:`MccsAPIU.IsAntennaOn` command functionality.

            :param argin: the logical antenna id of the antenna to power
                up
            :type argin: int

            :return: whether the specified antenna is on or not
            :rtype: bool
            """
            hardware_manager = self.target
            return hardware_manager.is_antenna_on(argin)

    @command(dtype_in="DevULong", doc_in="logicalAntennaId", dtype_out=bool)
    @DebugIt()
    def IsAntennaOn(self, argin):
        """
        Power up the antenna

        :param argin: the logical antenna id of the antenna to power
            up
        :type argin: int

        :return: whether the specified antenna is on or not
        :rtype: bool
        """
        handler = self.get_command_object("PowerUpAntenna")
        return handler(argin)

    class PowerUpAntennaCommand(ResponseCommand):
        """
        The command class for the PowerDownAntenna command
        """

        def do(self, argin):
            """
            Stateless hook for implementation of
            :py:meth:`MccsAPIU.PowerUpAntenna`
            command functionality.

            :param argin: the logical antenna id of the antenna to power
                up
            :type argin: int

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            success = hardware_manager.turn_on_antenna(argin)
            return create_return(success, f"antenna {argin} power-up")

    @command(
        dtype_in="DevULong",
        doc_in="logicalAntennaId",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def PowerUpAntenna(self, argin):
        """
        Power up the antenna

        :param argin: the logical antenna id of the antenna to power
            up
        :type argin: int

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("PowerUpAntenna")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class PowerDownAntennaCommand(ResponseCommand):
        """
        The command class for the PowerDownAntenna command
        """

        def do(self, argin):
            """
            Stateless hook for implementation of
            :py:meth:`MccsAPIU.PowerDownAntenna`
            command functionality.

            :param argin: the logical antenna id of the antenna to power
                down
            :type argin: int

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            success = hardware_manager.turn_off_antenna(argin)
            return create_return(success, f"antenna {argin} power-down")

    @command(
        dtype_in="DevULong",
        doc_in="logicalAntennaId",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def PowerDownAntenna(self, argin):
        """
        Power down the antenna

        :param argin: the logical antenna id of the antenna to power
            down
        :type argin: int

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("PowerDownAntenna")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class PowerUpCommand(ResponseCommand):
        """
        Class for handling the PowerUp() command.

        :todo: What is this command supposed to do? It takes no
            argument, and returns nothing.
        """

        def do(self):
            """
            Stateless hook for implementation of
            :py:meth:`MccsAPIU.PowerUp` command
            functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            success = hardware_manager.on()
            return create_return(success, "power-up")

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def PowerUp(self):
        """
        Power up

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("PowerUp")
        (return_code, message) = handler()
        return [[return_code], [message]]

    class PowerDownCommand(ResponseCommand):
        """
        Class for handling the PowerDown() command.

        :todo: What is this command supposed to do? It takes no
            argument, and returns nothing.
        """

        def do(self):
            """
            Stateless hook for implementation of
            :py:meth:`MccsAPIU.PowerDown`
            command functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            success = hardware_manager.off()
            return create_return(success, "power-down")

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def PowerDown(self):
        """
        Power down

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("PowerDown")
        (return_code, message) = handler()
        return [[return_code], [message]]

    def _update_health_state(self, health_state):
        """
        Update and push a change event for the healthState attribute

        :param health_state: The new health state
        :type health_state: :py:class:`ska.base.control_model.HealthState`
        """
        self.push_change_event("healthState", health_state)
        self._health_state = health_state
        self.logger.info("health state = " + str(health_state))


# ----------
# Run server
# ----------


def main(args=None, **kwargs):
    """
    Main function of the :py:mod:`ska.low.mccs.apiu` module.

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
