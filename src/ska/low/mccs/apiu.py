# -*- coding: utf-8 -*-
#
# This file is part of the MccsAPIU project
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
from ska.base.commands import ResponseCommand, ResultCode
from ska.base.control_model import SimulationMode
from ska.low.mccs.hardware import HardwareManager, HardwareSimulator
from ska.low.mccs.health import HealthModel


__all__ = [
    "AntennaHardwareSimulator",
    "APIUHardwareManager",
    "APIUHardwareSimulator",
    "MccsAPIU",
    "main",
]


class AntennaHardwareSimulator(HardwareSimulator):
    """
    A simulator of antenna hardware. This is part of the apiu module
    because the physical antenna is not directly monitorable, but must
    rather be monitored via the APIU.
    """

    VOLTAGE = 3.3
    CURRENT = 20.5
    TEMPERATURE = 23.8

    def __init__(self):
        """
        Initialise a new AntennaHardwareSimulator instance
        """
        self._voltage = None
        self._current = None
        self._temperature = None
        super().__init__()

    def off(self):
        """
        Turn me off
        """
        self._voltage = None
        self._current = None
        self._temperature = None
        super().off()

    def on(self):
        """
        Turn me on
        """
        self._voltage = self.VOLTAGE
        self._current = self.CURRENT
        self._temperature = self.TEMPERATURE
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


class APIUHardwareSimulator(HardwareSimulator):
    """
    A simulator of APIU hardware
    """

    VOLTAGE = 3.4
    CURRENT = 20.5
    TEMPERATURE = 20.4
    HUMIDITY = 23.9
    NUMBER_OF_ANTENNAS = 2

    def __init__(self):
        """
        Initialise a new APIUHardwareSimulator instance
        """
        self._voltage = None
        self._current = None
        self._temperature = None
        self._humidity = None

        self._antennas = [
            AntennaHardwareSimulator() for antenna_id in range(self.NUMBER_OF_ANTENNAS)
        ]
        super().__init__()

    def off(self):
        """
        Turn me off
        """
        self._voltage = None
        self._current = None
        self._temperature = None
        self._humidity = None

        for antenna in self._antennas:
            antenna.off()
        super().off()

    def on(self):
        """
        Turn me on
        """
        self._voltage = APIUHardwareSimulator.VOLTAGE
        self._current = APIUHardwareSimulator.CURRENT
        self._temperature = APIUHardwareSimulator.TEMPERATURE
        self._humidity = APIUHardwareSimulator.HUMIDITY

        # but don't turn antennas on

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

    def is_antenna_on(self, logical_antenna_id):
        """
        Return whether a specified antenna is turned on

        :param logical_antenna_id: this APIU's internal id for the
            antenna to be turned off
        :type logical_antenna_id: int

        :return: whether the antenna is on, or None if the APIU itself
            is off
        :rtype: bool or None
        """
        if not self._is_on:
            return None
        return self._antennas[logical_antenna_id - 1].is_on

    def turn_off_antenna(self, logical_antenna_id):
        """
        Turn off a specified antenna

        :param logical_antenna_id: this APIU's internal id for the
            antenna to be turned off
        :type logical_antenna_id: int
        """
        if self._is_on:
            self._antennas[logical_antenna_id - 1].off()

    def turn_on_antenna(self, logical_antenna_id):
        """
        Turn on a specified antenna

        :param logical_antenna_id: this APIU's internal id for the
            antenna to be turned on
        :type logical_antenna_id: int
        """
        if self._is_on:
            self._antennas[logical_antenna_id - 1].on()

    def get_antenna_current(self, logical_antenna_id):
        """
        Get the current of a specified antenna

        :param logical_antenna_id: this APIU's internal id for the
            antenna for which the current is requested
        :type logical_antenna_id: int

        :return: the antenna current
        :rtype: float
        """
        if self._is_on:
            return self._antennas[logical_antenna_id - 1].current

    def get_antenna_voltage(self, logical_antenna_id):
        """
        Get the voltage of a specified antenna

        :param logical_antenna_id: this APIU's internal id for the
            antenna for which the voltage is requested
        :type logical_antenna_id: int

        :return: the antenna voltage
        :rtype: float
        """
        if self._is_on:
            return self._antennas[logical_antenna_id - 1].voltage

    def get_antenna_temperature(self, logical_antenna_id):
        """
        Get the temperature of a specified antenna

        :param logical_antenna_id: this APIU's internal id for the
            antenna for which the temperature is requested
        :type logical_antenna_id: int

        :return: the antenna temperature
        :rtype: float
        """
        if self._is_on:
            return self._antennas[logical_antenna_id - 1].temperature


class APIUHardwareManager(HardwareManager):
    """
    This class manages APIU hardware.

    :todo: So far all we can do with APIU hardware is turn it off and
        on. We need to implement monitoring.
    """

    def __init__(self, simulation_mode):
        """
        Initialise a new AntennaHardwareManager instance

        :param simulation_mode: the initial simulation mode of this
            hardware manager
        :type simulation_mode: :py:class:`~ska.base.control_model.SimulationMode`
        """
        # polled hardware attributes
        self._voltage = None
        self._current = None
        self._temperature = None
        self._humidity = None

        self.antenna_voltages = None
        self.antenna_currents = None
        self.antenna_temperatures = None
        self.antenna_power_states = None

        super().__init__(simulation_mode)

    def _create_simulator(self):
        """
        Helper method to create and return a hardware simulator

        :return: a simulator of antenna hardware
        :rtype: :py:class:`APIUHardwareSimulator`
        """
        return APIUHardwareSimulator()

    def poll_hardware(self):
        """
        Poll the hardware and update local attributes with values
        reported by the hardware.
        """
        hardware = self._hardware
        self._is_on = hardware.is_on
        if self._is_on:
            self._voltage = hardware.voltage
            self._current = hardware.current
            self._temperature = hardware.temperature
            self._humidity = hardware.humidity

            self.antenna_voltages = [
                hardware.get_antenna_voltage(i + 1)
                for i in range(hardware.NUMBER_OF_ANTENNAS)
            ]
            self.antenna_currents = [
                hardware.get_antenna_current(i + 1)
                for i in range(hardware.NUMBER_OF_ANTENNAS)
            ]
            self.antenna_temperatures = [
                hardware.get_antenna_temperature(i + 1)
                for i in range(hardware.NUMBER_OF_ANTENNAS)
            ]
            self.antenna_power_states = [
                hardware.is_antenna_on(i + 1)
                for i in range(hardware.NUMBER_OF_ANTENNAS)
            ]
        else:
            self._voltage = None
            self._current = None
            self._temperature = None
            self._humidity = None

            self.antenna_voltages = None
            self.antenna_currents = None
            self.antenna_temperatures = None
            self.antenna_power_states = None
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

    def turn_off_antenna(self, logical_antenna_id):
        """
        Turn off a specified antenna

        :raises ValueError: if the APIU is turned off

        :param logical_antenna_id: the APIU's internal id for the
            antenna to be turned off
        :type logical_antenna_id: int

        :return: whether successful, or None if there was nothing to do
        :rtype: bool or None
        """
        if not self.is_on:
            raise ValueError("Cannot act on antenna when APIU is off")
        if not self.antenna_power_states[logical_antenna_id - 1]:
            return None

        self._hardware.turn_off_antenna(logical_antenna_id)
        self.poll_hardware()
        return not self.antenna_power_states[logical_antenna_id - 1]

    def turn_on_antenna(self, logical_antenna_id):
        """
        Turn on a specified antenna

        :raises ValueError: if the APIU is turned off

        :param logical_antenna_id: the APIU's internal id for the
            antenna to be turned on
        :type logical_antenna_id: int

        :return: whether successful, or None if there was nothing to do
        :rtype: bool or None
        """
        if not self.is_on:
            raise ValueError("Cannot act on antenna when APIU is off")
        if self.antenna_power_states[logical_antenna_id - 1]:
            return None

        self._hardware.turn_on_antenna(logical_antenna_id)
        self.poll_hardware()
        return self.antenna_power_states[logical_antenna_id - 1]

    def is_antenna_on(self, logical_antenna_id):
        """
        Gets whether a specified antenna is turned on

        :param logical_antenna_id: this APIU's internal id for the
            antenna being queried
        :type logical_antenna_id: int

        :raises ValueError: if the APIU, is turned off

        :return: whether the antenna is on
        :rtype: bool
        """
        if not self.is_on:
            raise ValueError("Cannot monitor antenna when APIU is off")
        return self.antenna_power_states[logical_antenna_id - 1]

    def get_antenna_current(self, logical_antenna_id):
        """
        Get the current of a specified antenna

        :param logical_antenna_id: this APIU's internal id for the
            antenna for which the current is requested
        :type logical_antenna_id: int

        :raises ValueError: if this antenna, or the entire APIU, is turned off

        :return: the antenna current
        :rtype: float
        """
        if not self.is_on:
            raise ValueError("Cannot monitor antenna when APIU is off")
        if not self.antenna_power_states[logical_antenna_id - 1]:
            raise ValueError("Cannot monitor antenna when antenna is off")
        return self.antenna_currents[logical_antenna_id - 1]

    def get_antenna_voltage(self, logical_antenna_id):
        """
        Get the voltage of a specified antenna

        :param logical_antenna_id: this APIU's internal id for the
            antenna for which the voltage is requested
        :type logical_antenna_id: int

        :raises ValueError: if this antenna, or the entire APIU, is turned off

        :return: the antenna voltage
        :rtype: float
        """
        if not self.is_on:
            raise ValueError("Cannot monitor antenna when APIU is off")
        if not self.antenna_power_states[logical_antenna_id - 1]:
            raise ValueError("Cannot monitor antenna when antenna is off")
        return self.antenna_voltages[logical_antenna_id - 1]

    def get_antenna_temperature(self, logical_antenna_id):
        """
        Get the temperature of a specified antenna

        :param logical_antenna_id: this APIU's internal id for the
            antenna for which the temperature is requested
        :type logical_antenna_id: int

        :raises ValueError: if this antenna, or the entire APIU, is turned off

        :return: the antenna temperature
        :rtype: float
        """
        if not self.is_on:
            raise ValueError("Cannot monitor antenna when APIU is off")
        if not self.antenna_power_states[logical_antenna_id - 1]:
            raise ValueError("Cannot monitor antenna when antenna is off")
        return self.antenna_temperatures[logical_antenna_id - 1]


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

            # Used to ensure that our child thread can't return before
            # the parent thread returns STARTED
            self._lock = threading.Lock()

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

            device._isAlive = True
            device._overCurrentThreshold = 0.0
            device._overVoltageThreshold = 0.0
            device._humidityThreshold = 0.0

            device.set_change_event("voltage", True, False)
            device.set_archive_event("voltage", True, False)

            init_connections_thread = threading.Thread(
                target=self._initialise_connections, args=(device,)
            )
            with self._lock:
                init_connections_thread.start()
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
                self._initialise_health_monitoring(device)
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

    def always_executed_hook(self):
        """Method always executed before any TANGO command is executed."""

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

    @attribute(dtype="DevDouble", label="Voltage", unit="Volts")
    def voltage(self):
        """
        Return the voltage attribute.

        :return: the voltage attribute
        :rtype: double
        """
        return self.hardware_manager.voltage

    @attribute(dtype="DevDouble", label="Current", unit="Amps")
    def current(self):
        """
        Return the current attribute.

        :return: the current value of the current attribute
        :rtype: double
        """
        return self.hardware_manager.current

    @attribute(dtype="DevDouble", label="Temperature", unit="degC")
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

    class PowerUpAntennaCommand(ResponseCommand):
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
            :rtype: (:py:class:`ska.base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            success = hardware_manager.turn_on_antenna(argin)
            if success is None:
                return (ResultCode.OK, f"Antenna {argin} was already powered up")
            elif success:
                return (ResultCode.OK, f"Antenna {argin} successfully powered up")
            else:
                return (ResultCode.FAILED, f"Antenna {argin} power-up failed")

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
        :rtype: (:py:class:`ska.base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("PowerUpAntenna")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class PowerDownAntennaCommand(ResponseCommand):
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
            :rtype: (:py:class:`ska.base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            success = hardware_manager.turn_off_antenna(argin)
            if success is None:
                return (ResultCode.OK, f"Antenna {argin} was already powered down")
            elif success:
                return (ResultCode.OK, f"Antenna {argin} successfully powered down")
            else:
                return (ResultCode.FAILED, f"Antenna {argin} power-down failed")

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
        :rtype: (:py:class:`ska.base.commands.ResultCode`, str)
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
            :rtype: (:py:class:`ska.base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            success = hardware_manager.on()
            if success is None:
                return (ResultCode.OK, "APIU was already powered up")
            elif success:
                return (ResultCode.OK, "APIU successfully powered up")
            else:
                return (ResultCode.FAILED, "APIU power-up failed")

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
        :rtype: (:py:class:`ska.base.commands.ResultCode`, str)
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
            :rtype: (:py:class:`ska.base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            success = hardware_manager.off()
            if success is None:
                return (ResultCode.OK, "APIU was already powered down")
            elif success:
                return (ResultCode.OK, "APIU successfully powered down")
            else:
                return (ResultCode.FAILED, "APIU power-down failed")

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
        :rtype: (:py:class:`ska.base.commands.ResultCode`, str)
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
