# -*- coding: utf-8 -*-
#
# This file is part of the MccsAntenna project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

""" LFAA Antenna Device Server

An implementation of the Antenna Device Server for the MCCS based upon
architecture in SKA-TEL-LFAA-06000052-02.
"""
__all__ = ["AntennaHardwareSimulator", "AntennaHardwareManager", "MccsAntenna", "main"]

import threading

# tango imports
from tango import DebugIt, EnsureOmniThread
from tango.server import attribute, command, AttrWriteType

# Additional import
from ska.base import SKABaseDevice
from ska.base.commands import ResponseCommand, ResultCode
from ska.base.control_model import SimulationMode

from ska.low.mccs.hardware import (
    OnOffHardwareHealthEvaluator,
    OnOffHardwareSimulator,
    OnOffHardwareManager,
)
from ska.low.mccs.health import HealthModel


class AntennaHardwareSimulator(OnOffHardwareSimulator):
    """
    A simulator of AntennaHardware
    """

    VOLTAGE = 3.5
    TEMPERATURE = 20.6

    def __init__(self):
        """
        Initialise a new AntennaHardwareSimulator instance
        """
        self._voltage = None
        self._temperature = None
        super().__init__()

    def off(self):
        """
        Turn me off
        """
        super().off()
        self._voltage = None
        self._temperature = None

    def on(self):
        """
        Turn me on
        """
        super().on()
        self._voltage = self.VOLTAGE
        self._temperature = self.TEMPERATURE

    @property
    def voltage(self):
        """
        Return my voltage

        :return: my voltage
        :rtype: float
        """
        self.check_connected()
        return self._voltage

    @property
    def temperature(self):
        """
        Return my temperature

        :return: my temperature
        :rtype: float
        """
        self.check_connected()
        return self._temperature


class AntennaHardwareHealthEvaluator(OnOffHardwareHealthEvaluator):
    """
    A placeholder for a class that implements a policy by which the
    antenna hardware manager evaluates the health of its hardware. At
    present this just inherits from the base class unchanged.
    """

    pass


class AntennaHardwareManager(OnOffHardwareManager):
    """
    This class manages antenna hardware.

    :todo: So far only voltage and temperature have been moved in here.
        There are lots of other attributes that should be.
    """

    def __init__(self, simulation_mode):
        """
        Initialise a new AntennaHardwareManager instance

        :param simulation_mode: the initial simulation mode of this
            hardware manager
        :type simulation_mode: :py:class:`~ska.base.control_model.SimulationMode`
        """
        super().__init__(simulation_mode, AntennaHardwareHealthEvaluator())

    def _create_simulator(self):
        """
        Helper method to create and return a hardware simulator

        :return: a simulator of antenna hardware
        :rtype: :py:class:`AntennaHardwareSimulator`
        """
        return AntennaHardwareSimulator()

    @property
    def voltage(self):
        """
        The voltage of the hardware

        :return: the voltage of the hardware
        :rtype: float
        """
        return self._hardware.voltage

    @property
    def temperature(self):
        """
        Return the temperature of the hardware

        :return: the temperature of the hardware
        :rtype: float
        """
        return self._hardware.temperature


class MccsAntenna(SKABaseDevice):
    """
    An implementation of the Antenna Device Server for the MCCS based upon
    architecture in SKA-TEL-LFAA-06000052-02.

    This class is a subclass of :py:class:`ska.base.SKABaseDevice`.
    """

    # -----------------
    # Device Properties
    # -----------------

    # ---------------
    # General methods
    # ---------------
    class InitCommand(SKABaseDevice.InitCommand):
        """
        Initialises the command handlers for commands supported by this
        device.
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
            Stateless hook for device initialisation: initialises the
            attributes and properties of the :py:class:`MccsAntenna`.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`ska.base.commands.ResultCode`, str)
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

            device._antennaId = 0
            device._logicalTpmAntenna_id = 0
            device._logicalApiuAntenna_id = 0
            device._tpmId = 0
            device._apiuId = 0
            device._gain = 0.0
            device._rms = 0.0
            device._xPolarisationFaulty = False
            device._yPolarisationFaulty = False
            device._fieldNodeLongitude = 0.0
            device._fieldNodeLatitude = 0.0
            device._altitude = 0.0
            device._xDisplacement = 0.0
            device._yDisplacement = 0.0
            device._timestampOfLastSpectrum = ""
            device._logicalAntennaId = 0
            device._xPolarisationScalingFactor = [0]
            device._yPolarisationScalingFactor = [0]
            device._calibrationCoefficient = [0.0]
            device._pointingCoefficient = [0.0]
            device._spectrumX = [0.0]
            device._spectrumY = [0.0]
            device._position = [0.0]
            device._delays = [0.0]
            device._delayRates = [0.0]
            device._bandpassCoefficient = [0.0]
            device._first = True

            event_names = [
                "voltage",
                "temperature",
                "xPolarisationFaulty",
                "yPolarisationFaulty",
            ]
            for name in event_names:
                device.set_change_event(name, True, True)
                device.set_archive_event(name, True, True)

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
                    self._thread = None
                    self._interrupt = False

        def _initialise_hardware_management(self, device):
            """
            Initialise the connection to the hardware being managed by
            this device. May also register commands that depend upon a
            connection to that hardware

            :param device: the device for which a connection to the
                hardware is being initialised
            :type device: :py:class:`~ska.base.SKABaseDevice`
            """
            device.hardware_manager = AntennaHardwareManager(device._simulation_mode)
            hardware_args = (device.hardware_manager, device.state_model, self.logger)
            device.register_command_object("Reset", device.ResetCommand(*hardware_args))
            device.register_command_object(
                "PowerOn", device.PowerOnCommand(*hardware_args)
            )
            device.register_command_object(
                "PowerOff", device.PowerOffCommand(*hardware_args)
            )

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
        :py:meth:`~ska.low.mccs.antenna.MccsAntenna.InitCommand.do` method of the
        nested :py:class:`~ska.low.mccs.antenna.MccsAntenna.InitCommand` class.

        This method allows for any memory or other resources allocated in the
        :py:meth:`~ska.low.mccs.antenna.MccsAntenna.InitCommand.do` method to be
        released. This method is called by the device destructor, and by the Init
        command when the Tango device server is re-initialised.
        """

    # ----------
    # Attributes
    # ----------

    # override from base classes so that it can be stored in the hardware manager
    @attribute(dtype=SimulationMode, access=AttrWriteType.READ_WRITE, memorized=True)
    def simulationMode(self):
        """
        Return the simulation mode of this device

        :return: the simulation mode of this device
        :rtype: :py:class:`~ska.base.control_model.SimulationMode`
        """
        return self.hardware_manager.simulation_mode

    @simulationMode.write
    def simulationMode(self, value):
        """
        Set the simulation mode of this device

        :param value: the new simulation mode
        :type value: :py:class:`~ska.base.control_model.SimulationMode`
        """
        self.hardware_manager.simulation_mode = value

    @attribute(dtype="int", label="AntennaID", doc="Global antenna identifier")
    def antennaId(self):
        """
        Return the antenna ID attribute.

        :return: antenna ID
        :rtype: int
        """
        return self._antennaId

    @attribute(
        dtype="int",
        label="logicalTpmAntenna_id",
        doc="Local within Tile identifier for the Antenna TPM\n",
    )
    def logicalTpmAntenna_id(self):
        """
        Return the logical antenna ID attribute.

        :return: logical antenna ID within the tpm
        :rtype: int
        """
        return self._logicalTpmAntenna_id

    @attribute(
        dtype="int",
        label="logicalApiuAntenna_id",
        doc="Local within Tile identifier for the Antenna APIU",
    )
    def logicalApiuAntenna_id(self):
        """
        Return the logical APIU antenna ID attribute.

        :return: logical APIU antenna ID
        :rtype: int
        """
        return self._logicalApiuAntenna_id

    @attribute(
        dtype="int",
        label="tpmId",
        doc="Global Tile ID to which the antenna is connected",
    )
    def tpmId(self):
        """
        Return the global tile ID attribute.

        :return: tpm ID
        :rtype: int
        """
        return self._tpmId

    @attribute(dtype="int", label="apiuId")
    def apiuId(self):
        """
        Return the APIU ID attribute.

        :return: tpm ID
        :rtype: int
        """
        return self._apiuId

    @attribute(dtype="float", label="gain", doc="The gain set for the antenna")
    def gain(self):
        """
        Return the gain attribute.

        :return: the gain
        :rtype: float
        """
        return self._gain

    @attribute(
        dtype="float", label="rms", doc="The measured RMS of the antenna (monitored)"
    )
    def rms(self):
        """
        Return the measured RMS of the antenna.

        :return: the measured rms
        :rtype: float
        """
        return self._rms

    @attribute(
        dtype="float",
        label="voltage",
        unit="volts",
        abs_change=0.05,
        min_value=2.5,
        max_value=5.5,
        min_alarm=2.75,
        max_alarm=5.45,
        polling_period=1000,
    )
    def voltage(self):
        """
        Return the voltage attribute.

        :return: the voltage
        :rtype: float
        """
        return self.hardware_manager.voltage

    @attribute(dtype="float", label="temperature", unit="DegC")
    def temperature(self):
        """
        Return the temperature attribute.

        :return: the temperature
        :rtype: float
        """
        return self.hardware_manager.temperature

    @attribute(dtype="bool", label="xPolarisationFaulty")
    def xPolarisationFaulty(self):
        """
        Return the xPolarisationFaulty attribute.

        :return: the x-polarisation faulty flag
        :rtype: boolean
        """
        return self._xPolarisationFaulty

    @attribute(dtype="bool", label="yPolarisationFaulty")
    def yPolarisationFaulty(self):
        """
        Return the yPolarisationFaulty attribute.

        :return: the y-polarisation faulty flag
        :rtype: boolean
        """
        return self._yPolarisationFaulty

    @attribute(
        dtype="float",
        label="fieldNodeLongitude",
        doc="Longitude of field node (centre) to which antenna is associated.",
    )
    def fieldNodeLongitude(self):
        """
        Return the fieldNodeLongitude attribute.

        :return: the Longitude of field node centre
        :rtype: float
        """
        return self._fieldNodeLongitude

    @attribute(
        dtype="float",
        label="fieldNodeLatitude",
        doc="""Latitude of the field node (centre) to which antenna is
        associated.""",
    )
    def fieldNodeLatitude(self):
        """
        Return the fieldNodeLatitude attribute.

        :return: the Latitude of field node centre
        :rtype: float
        """
        return self._fieldNodeLongitude

    @attribute(
        dtype="float", label="altitude", unit="meters", doc="Antenna altitude in meters"
    )
    def altitude(self):
        """
        Return the altitude attribute.

        :return: the altitude of the antenna
        :rtype: float
        """
        return self._altitude

    @attribute(
        dtype="float",
        label="xDisplacement",
        unit="meters",
        doc="Horizontal displacement in meters from field node centre",
    )
    def xDisplacement(self):
        """
        Return the Horizontal displacement attribute.

        :return: the horizontal displacement from field node centre
        :rtype: float
        """
        return self._xDisplacement

    @attribute(
        dtype="float",
        label="yDisplacement",
        unit="meters",
        doc="Vertical displacement in meters from field centre",
    )
    def yDisplacement(self):
        """
        Return the vertical displacement attribute.

        :return: the vertical displacement from field node centre
        :rtype: float
        """
        return self._yDisplacement

    @attribute(dtype="str", label="timestampOfLastSpectrum")
    def timestampOfLastSpectrum(self):
        """
        Return the timestampOfLastSpectrum attribute.

        :return: the timestamp of the last spectrum
        :rtype: str
        """
        return self._timestampOfLastSpectrum

    @attribute(
        dtype="int",
        label="logicalAntennaId",
        doc="Local (within Tile) antenna identifier",
    )
    def logicalAntennaId(self):
        """
        Return the logical antenna ID attribute.

        :return: the logical antenna ID
        :rtype: int
        """
        return self._logicalAntennaId

    @attribute(dtype=("int",), max_dim_x=100, label="xPolarisationScalingFactor")
    def xPolarisationScalingFactor(self):
        """
        Return the logical antenna ID attribute.

        :return: the x polarisation scaling factor
        :rtype: array of int
        """
        return self._xPolarisationScalingFactor

    @attribute(dtype=("int",), max_dim_x=100, label="yPolarisationScalingFactor")
    def yPolarisationScalingFactor(self):
        """
        Return the yPolarisationScalingFactor attribute.

        :return: the y polarisation scaling factor
        :rtype: array of int
        """
        return self._yPolarisationScalingFactor

    @attribute(
        dtype=("float",),
        max_dim_x=100,
        label="calibrationCoefficient",
        doc="""Calibration coefficient to be applied for the next frequency
        channel in the calibration cycle (archived).
        This is presented as a vector.""",
    )
    def calibrationCoefficient(self):
        """
        Return theCalibration coefficient to be applied for the next frequency
        channel in the calibration cycle

        :return: the calibration coefficients
        :rtype: array of float
        """
        return self._calibrationCoefficient

    @attribute(dtype=("float",), max_dim_x=100, doc="This is presented as a vector.")
    def pointingCoefficient(self):
        """
        Return the pointingCoefficient attribute.

        :return: the pointing coefficients
        :rtype: array of float
        """
        return self._pointingCoefficient

    @attribute(dtype=("float",), max_dim_x=100, label="spectrumX")
    def spectrumX(self):
        """
        Return the spectrumX attribute.

        :return: x spectrum
        :rtype: array of float
        """
        return self._spectrumX

    @attribute(dtype=("float",), max_dim_x=100, label="spectrumY")
    def spectrumY(self):
        """
        Return the spectrumY attribute.

        :return: y spectrum
        :rtype: array of float
        """
        return self._spectrumY

    @attribute(dtype=("float",), max_dim_x=100, label="position")
    def position(self):
        """
        Return the position attribute.

        :return: positions
        :rtype: array of float
        """
        return self._position

    @attribute(
        dtype=("float",),
        max_dim_x=100,
        label="delays",
        doc="Delay for each beam to be applied during the next pointing "
        "update (archived)",
    )
    def delays(self):
        """
        Return the delays attribute.

        :return: delay for each beam
        :rtype: array of float
        """
        return self._delays

    @attribute(
        dtype=("float",),
        max_dim_x=100,
        label="delayRates",
        doc="Delay rate for each beam to be applied during the next "
        "pointing update (archived)",
    )
    def delayRates(self):
        """
        Return the delayRates attribute.

        :return: delay rate for each beam
        :rtype: array of float
        """
        return self._delayRates

    @attribute(
        dtype=("float",),
        max_dim_x=100,
        label="bandpassCoefficient",
        doc="Bandpass coefficient to apply during next calibration cycle to "
        "flatten the antenna's bandpass (archived)",
    )
    def bandpassCoefficient(self):
        """
        Return the bandpassCoefficient attribute.

        :return: bandpass coefficients
        :rtype: array of float
        """
        return self._bandpassCoefficient

    # --------
    # Commands
    # --------
    class ResetCommand(SKABaseDevice.ResetCommand):
        """
        Command class for the Reset() command.
        """

        def do(self):
            """
            Stateless hook implementing the functionality of the
            :py:meth:`MccsAntenna.Reset` command.
            This implementation resets the MCCS system as a whole as an
            attempt to clear a FAULT state.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`ska.base.commands.ResultCode`, str)
            """

            (result_code, message) = super().do()
            # MCCS-specific Reset functionality goes here
            return (result_code, message)

    class PowerOnCommand(ResponseCommand):
        """
        Class for handling the PowerOn command.
        """

        def do(self):
            """
            Stateless hook for implementation of the
            :py:meth:`MccsAntenna.PowerOn` command
            functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`ska.base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            hardware_manager.on()
            return (ResultCode.OK, "Hardware got turned on")

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def PowerOn(self):
        """
        Turn power On.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`ska.base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("PowerOn")
        (return_code, message) = handler()
        return [[return_code], [message]]

    class PowerOffCommand(ResponseCommand):
        """
        Class for handling the PowerOff command.
        """

        def do(self):
            """
            Stateless hook for implementation of the
            :py:meth:`MccsAntenna.PowerOff` command
            functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`ska.base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            hardware_manager.off()
            return (ResultCode.OK, "Stub implementation, does nothing")

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def PowerOff(self):
        """
        Turn power Off.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`ska.base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("PowerOff")
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
    Main function of the :py:mod:`ska.low.mccs.antenna` module.

    :param args: positional arguments
    :type args: list
    :param kwargs: named arguments
    :type kwargs: dict

    :return: exit code
    :rtype: int
    """
    return MccsAntenna.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
