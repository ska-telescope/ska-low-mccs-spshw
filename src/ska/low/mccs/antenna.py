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
__all__ = ["MccsAntenna", "main"]

# tango imports
from tango import DebugIt
from tango.server import attribute, command

# Additional import
from ska.base import SKABaseDevice
from ska.base.commands import ResponseCommand, ResultCode


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
        def do(self):
            """
            Stateless hook for device initialisation: initialises the
            attributes and properties of the MccsDevice.
            """
            super().do()

            device = self.target
            device._antennaId = 0
            device._logicalTpmAntenna_id = 0
            device._logicalApiuAntenna_id = 0.0
            device._tpmId = 0.0
            device._apiuId = 0.0
            device._gain = 0.0
            device._rms = 0.0
            device._voltage = 0.0
            device._temperature = 0.0
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
            return (ResultCode.OK, "Init command succeeded")

    def init_command_objects(self):
        """
        Set up the handler objects for Commands
        """
        super().init_command_objects()

        args = (self, self.state_model, self.logger)

        self.register_command_object("Reset", self.ResetCommand(*args))
        self.register_command_object("PowerOn", self.PowerOnCommand(*args))
        self.register_command_object("PowerOff", self.PowerOffCommand(*args))

    def always_executed_hook(self):
        """Method always executed before any TANGO command is executed."""

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
        return self._antennaId

    @attribute(
        dtype="int",
        label="logicalTpmAntenna_id",
        doc="Local within Tile identifier for the Antenna TPM\n",
    )
    def logicalTpmAntenna_id(self):
        return self._logicalTpmAntenna_id

    @attribute(
        dtype="double",
        label="logicalApiuAntenna_id",
        doc="Local within Tile identifier for the Antenna APIU",
    )
    def logicalApiuAntenna_id(self):
        return self._logicalApiuAntenna_id

    @attribute(
        dtype="double",
        label="tpmId",
        doc="Global Tile ID to which the atenna is connected",
    )
    def tpmId(self):
        return self._tpmId

    @attribute(dtype="double", label="apiuId")
    def apiuId(self):
        return self._apiuId

    @attribute(dtype="float", label="gain", doc="The gain set for the antenna")
    def gain(self):
        return self._gain

    @attribute(
        dtype="float", label="rms", doc="The measured RMS of the antenna (monitored)"
    )
    def rms(self):
        return self._rms

    @attribute(dtype="float", label="voltage", unit="volts")
    def voltage(self):
        return self._voltage

    @attribute(dtype="float", label="temperature", unit="DegC")
    def temperature(self):
        return self._temperature

    @attribute(dtype="bool", label="xPolarisationFaulty")
    def xPolarisationFaulty(self):
        return self._xPolarisationFaulty

    @attribute(dtype="bool", label="yPolarisationFaulty")
    def yPolarisationFaulty(self):
        return self._yPolarisationFaulty

    @attribute(
        dtype="float",
        label="fieldNodeLongitude",
        doc="Longitude of field node (centre) to which antenna is associated.",
    )
    def fieldNodeLongitude(self):
        return self._fieldNodeLongitude

    @attribute(
        dtype="float",
        label="fieldNodeLatitude",
        doc="""Latitude of the field node (centre) to which antenna is
        associated.""",
    )
    def fieldNodeLatitude(self):
        return self._fieldNodeLongitude

    @attribute(
        dtype="float", label="altitude", unit="meters", doc="Antenna altitude in meters"
    )
    def altitude(self):
        return self._altitude

    @attribute(
        dtype="float",
        label="xDisplacement",
        unit="meters",
        doc="Horizontal displacement in meters from field node centre",
    )
    def xDisplacement(self):
        return self._xDisplacement

    @attribute(
        dtype="float",
        label="yDisplacement",
        unit="meters",
        doc="Vertical displacement in meters from field centre",
    )
    def yDisplacement(self):
        return self._yDisplacement

    @attribute(dtype="str", label="timestampOfLastSpectrum")
    def timestampOfLastSpectrum(self):
        return self._timestampOfLastSpectrum

    @attribute(
        dtype="int",
        label="logicalAntennaId",
        doc="Local (within Tile) antenna identifier",
    )
    def logicalAntennaId(self):
        return self._logicalAntennaId

    @attribute(dtype=("int",), max_dim_x=100, label="xPolarisationScalingFactor")
    def xPolarisationScalingFactor(self):
        return self._xPolarisationScalingFactor

    @attribute(dtype=("int",), max_dim_x=100, label="yPolarisationScalingFactor")
    def yPolarisationScalingFactor(self):
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
        return self._calibrationCoefficient

    @attribute(dtype=("float",), max_dim_x=100, doc="This is presented as a vector.")
    def pointingCoefficient(self):
        return self._pointingCoefficient

    @attribute(dtype=("float",), max_dim_x=100, label="spectrumX")
    def spectrumX(self):
        return self._spectrumX

    @attribute(dtype=("float",), max_dim_x=100, label="spectrumY")
    def spectrumY(self):
        return self._spectrumY

    @attribute(dtype=("float",), max_dim_x=100, label="position")
    def position(self):
        return self._position

    @attribute(
        dtype=("float",),
        max_dim_x=100,
        label="delays",
        doc="Delay for each beam to be applied during the next pointing "
        "update (archived)",
    )
    def delays(self):
        return self._delays

    @attribute(
        dtype=("float",),
        max_dim_x=100,
        label="delayRates",
        doc="Delay rate for each beam to be applied during the next "
        "pointing update (archived)",
    )
    def delayRates(self):
        return self._delayRates

    @attribute(
        dtype=("float",),
        max_dim_x=100,
        label="bandpassCoefficient",
        doc="Bandpass coefficient to apply during next calibration cycle to "
        "flatten the antenna's bandpass (archived)",
    )
    def bandpassCoefficient(self):
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
        def do(self):
            """
            Stateless hook for implementation of ExceptionCallback()
            command functionality.
            """
            return (ResultCode.OK, "Stub implementation, does nothing")

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def PowerOn(self):
        handler = self.get_command_object("PowerOn")
        (return_code, message) = handler()
        return [[return_code], [message]]

    class PowerOffCommand(ResponseCommand):
        def do(self):
            """
            Stateless hook for implementation of ExceptionCallback()
            command functionality.
            """
            return (ResultCode.OK, "Stub implementation, does nothing")

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def PowerOff(self):
        handler = self.get_command_object("PowerOff")
        (return_code, message) = handler()
        return [[return_code], [message]]


# ----------
# Run server
# ----------


def main(args=None, **kwargs):

    return MccsAntenna.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
