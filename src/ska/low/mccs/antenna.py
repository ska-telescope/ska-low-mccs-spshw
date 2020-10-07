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
__all__ = ["AntennaHardware", "AntennaHardwareManager", "MccsAntenna", "main"]

# tango imports
from tango import DebugIt
from tango.server import attribute, command

# Additional import
from ska.base import SKABaseDevice
from ska.base.commands import ResponseCommand, ResultCode

from ska.base.control_model import HealthState

from ska.low.mccs.events import EventManager
from ska.low.mccs.health import HealthModel


class AntennaHardware:
    """
    A stub class to take the place of actual antenna hardware
    """

    VOLTAGE = 3.5
    TEMPERATURE = 20.6

    def __init__(self):
        """
        Initialise a new AntennaHardware instance
        """
        self._is_on = False
        self._voltage = None
        self._temperature = None

    def off(self):
        """
        Turn me off
        """
        self._is_on = False
        self._voltage = None
        self._temperature = None

    def on(self):
        """
        Turn me on
        """
        self._is_on = True
        self._voltage = AntennaHardware.VOLTAGE  # for testing purposes
        self._temperature = AntennaHardware.TEMPERATURE  # for testing purposes

    @property
    def is_on(self):
        """
        Return whether I am on or off

        :return: whether I am on or off
        :rtype: bool
        """
        return self._is_on

    @property
    def voltage(self):
        """
        Return my voltage

        :return: my voltage
        :rtype: float
        """
        return self._voltage

    @property
    def temperature(self):
        """
        Return my temperature

        :return: my temperature
        :rtype: float
        """
        return self._temperature


class AntennaHardwareManager:
    """
    This class manages antenna hardware.

    :todo: So far only voltage and temperature have been moved in here.
        There are lots of other attributes that should be.
    """

    def __init__(self, hardware=None):
        """
        Initialise a new AntennaHardwareManager instance

        At present, hardware is simulated by stub software, and so the
        only argument is an optional "hardware" instance. In future, its
        arguments will allow connection to the actual hardware

        :param hardware: the hardware itself, defaults to None. This only
            exists to facilitate testing.
        :type hardware: AntennaHardware
        """
        self._hardware = AntennaHardware() if hardware is None else hardware

        # polled attributes
        self._is_on = None
        self._voltage = None
        self._temperature = None

        self._health = None
        self._health_callbacks = []

    def off(self):
        """
        Turn the hardware off

        :return: whether successful
        :rtype: boolean, or None if there was nothing to do.
        """
        if not self._hardware.is_on:
            return None
        self._hardware.off()
        return not self._hardware.is_on

    def on(self):
        """
        Turn the hardware on

        :return: whether successful
        :rtype: boolean, or None if there was nothing to do.
        """
        if self._hardware.is_on:
            return None
        self._hardware.on()
        return self._hardware.is_on

    def poll_hardware(self):
        """
        Poll the hardware and update local attributes with values
        reported by the hardware.
        """
        self._is_on = self._hardware.is_on
        if self._is_on:
            self._voltage = self._hardware.voltage
            self._temperature = self._hardware.temperature
            self._evaluate_health()

    @property
    def is_on(self):
        """
        Whether the hardware is on or not

        :return: whether the hardware is on or not
        :rtype: boolean
        """
        return self._is_on

    @property
    def voltage(self):
        """
        The voltage of the hardware

        :return: the voltage of the hardware
        :rtype: float
        """
        return self._voltage

    @property
    def temperature(self):
        """
        Return the temperature of the hardware

        :return: the temperature of the hardware
        :rtype: float
        """
        return self._temperature

    @property
    def health(self):
        """
        The health of the hardware, as evaluated by this manager

        :return: the health of the hardware
        :rtype: HealthState
        """
        return self._health

    def _evaluate_health(self):
        """
        Evaluate the health of the hardware
        """
        # look at the polled hardware values and maybe further poke the
        # hardware to check that it is okay
        self._update_health(HealthState.OK)

    def _update_health(self, health):
        """
        Update the health of this hardware, ensuring that any registered
        callbacks are called

        :param health: the new health value
        :type health: HealthState
        """
        if self._health == health:
            return
        self._health = health
        for callback in self._health_callbacks:
            callback(health)

    def register_health_callback(self, callback):
        """
        Register a callback to be called when the health of the hardware
        changes

        :param callback: A callback to be called when the health of the
            hardware changes
        :type callback: callable
        """
        self._health_callbacks.append(callback)


class MccsAntenna(SKABaseDevice):
    """
    An implementation of the Antenna Device Server for the MCCS based upon
    architecture in SKA-TEL-LFAA-06000052-02.
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

        def do(self):
            """
            Stateless hook for device initialisation: initialises the
            attributes and properties of the MccsDevice.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (ResultCode, str)
            """
            super().do()

            device = self.target
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
            device.set_change_event("healthState", True, True)
            device.set_archive_event("healthState", True, True)
            device._first = True

            device.hardware_manager = AntennaHardwareManager()
            device.event_manager = EventManager()
            device.health_model = HealthModel(
                device.hardware_manager,
                None,
                device.event_manager,
                device._update_health_state,
            )

            event_names = [
                "voltage",
                "temperature",
                "xPolarisationFaulty",
                "yPolarisationFaulty",
            ]
            for name in event_names:
                device.set_change_event(name, True, True)
                device.set_archive_event(name, True, True)

            return (ResultCode.OK, "Init command succeeded")

    def always_executed_hook(self):
        """Method always executed before any TANGO command is executed."""
        self.hardware_manager.poll_hardware()

    def delete_device(self):
        """Hook to delete resources allocated in init_device.

        This method allows for any memory or other resources allocated in the
        init_device method to be released.  This method is called by the device
        destructor and by the device Init command.
        """

    # ----------
    # Attributes
    # ----------

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
    def init_command_objects(self):
        """
        Set up the handler objects for Commands
        """
        super().init_command_objects()

        hardware_args = (self.hardware_manager, self.state_model, self.logger)

        self.register_command_object("Reset", self.ResetCommand(*hardware_args))
        self.register_command_object("PowerOn", self.PowerOnCommand(*hardware_args))
        self.register_command_object("PowerOff", self.PowerOffCommand(*hardware_args))

    class ResetCommand(SKABaseDevice.ResetCommand):
        """
        Class for handling the Reset() command.
        """

        def do(self):
            """
            Stateless hook implementing the functionality of the
            Reset command. This implementation resets the MCCS
            system as a whole as an attempt to clear a FAULT
            state.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (ResultCode, str)
            """

            (result_code, message) = super().do()
            # MCCS-specific Reset functionality goes here
            return (result_code, message)

    class PowerOnCommand(ResponseCommand):
        """
        Class for handling the PowerOn() command.
        """

        def do(self):
            """
            Stateless hook for implementation of PowerOn()
            command functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (ResultCode, str)
            """
            hardware_manager = self.target
            hardware_manager.on()
            return (ResultCode.OK, "Stub implementation, does nothing")

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
        :rtype: (ResultCode, str)
        """
        handler = self.get_command_object("PowerOn")
        (return_code, message) = handler()
        return [[return_code], [message]]

    class PowerOffCommand(ResponseCommand):
        """
        Class for handling the PowerOff() command.
        """

        def do(self):
            """
            Stateless hook for implementation of PowerOff()
            command functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (ResultCode, str)
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
        :rtype: (ResultCode, str)
        """
        handler = self.get_command_object("PowerOff")
        (return_code, message) = handler()
        return [[return_code], [message]]

    def _update_health_state(self, health_state):
        """
        Update and push a change event for the healthstate attribute

        :param health_state: The new healthstate
        :type health_state: enum (defined in ska.base.control_model)
        """
        self.push_change_event("healthState", health_state)
        self._health_state = health_state
        self.logger.info("health state = " + str(health_state))


# ----------
# Run server
# ----------


def main(args=None, **kwargs):
    """
    Main function of the MccsAntenna module.

    :param args: command line arguments
    :param kwargs: command line keyword arguments

    :return: device server instance
    """

    return MccsAntenna.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
