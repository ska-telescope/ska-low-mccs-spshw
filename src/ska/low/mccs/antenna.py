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
from tango import DevState

# Additional import
from ska.base import SKABaseDevice
from ska.base.commands import BaseCommand, ResponseCommand, ResultCode


class MccsAntenna(SKABaseDevice):
    """
    An implementation of the Antenna Device Server for the MCCS based upon
    architecture in SKA-TEL-LFAA-06000052-02.
    """

    # -----------------
    # Device Properties
    # -----------------

    # ----------
    # Attributes
    # ----------

    antennaId = attribute(
        dtype="int", label="AntennaID", doc="Global antenna identifier"
    )

    logicalTpmAntenna_id = attribute(
        dtype="int",
        label="logicalTpmAntenna_id",
        doc="Local within Tile identifier for the Antenna TPM\n",
    )

    logicalApiuAntenna_id = attribute(
        dtype="double",
        label="logicalApiuAntenna_id",
        doc="Local within Tile identifier for the Antenna APIU",
    )

    tpmId = attribute(
        dtype="double",
        label="tpmId",
        doc="Global Tile ID to which the atenna is connected",
    )

    apiuId = attribute(dtype="double", label="apiuId")

    gain = attribute(dtype="float", label="gain", doc="The gain set for the antenna")

    rms = attribute(
        dtype="float", label="rms", doc="The measured RMS of the antenna (monitored)"
    )

    voltage = attribute(dtype="float", label="voltage", unit="volts")

    temperature = attribute(dtype="float", label="temperature", unit="DegC")

    xPolarisationFaulty = attribute(dtype="bool", label="xPolarisationFaulty")

    yPolarisationFaulty = attribute(dtype="bool", label="yPolarisationFaulty")

    fieldNodeLongitude = attribute(
        dtype="float",
        label="fieldNodeLongitude",
        doc="Longitude of field node (centre) to which antenna is associated.",
    )

    fieldNodeLatitude = attribute(
        dtype="float",
        label="fieldNodeLatitude",
        doc="""Latitude of the field node (centre) to which antenna is
        associated.""",
    )

    altitude = attribute(
        dtype="float", label="altitude", unit="meters", doc="Antenna altitude in meters"
    )

    xDisplacement = attribute(
        dtype="float",
        label="xDisplacement",
        unit="meters",
        doc="Horizontal displacement in meters from field node centre",
    )

    yDisplacement = attribute(
        dtype="float",
        label="yDisplacement",
        unit="meters",
        doc="Vertical displacement in meters from field centre",
    )

    timestampOfLastSpectrum = attribute(dtype="str", label="timestampOfLastSpectrum")

    logicalAntennaId = attribute(
        dtype="int",
        label="logicalAntennaId",
        doc="Local (within Tile) antenna identifier",
    )

    xPolarisationScalingFactor = attribute(
        dtype=("int",), max_dim_x=100, label="xPolarisationScalingFactor"
    )

    yPolarisationScalingFactor = attribute(
        dtype=("int",), max_dim_x=100, label="yPolarisationScalingFactor"
    )

    calibrationCoefficient = attribute(
        dtype=("float",),
        max_dim_x=100,
        label="calibrationCoefficient",
        doc="""Calibration coefficient to be applied for the next frequency
        channel in the calibration cycle (archived).
        This is presented as a vector.""",
    )

    pointingCoefficient = attribute(
        dtype=("float",), max_dim_x=100, doc="This is presented as a vector."
    )

    spectrumX = attribute(dtype=("float",), max_dim_x=100, label="spectrumX")

    spectrumY = attribute(dtype=("float",), max_dim_x=100, label="spectrumY")

    position = attribute(dtype=("float",), max_dim_x=100, label="position")

    delays = attribute(
        dtype=("float",),
        max_dim_x=100,
        label="delays",
        doc="Delay for each beam to be applied during the next pointing "
        "update (archived)",
    )

    delayRates = attribute(
        dtype=("float",),
        max_dim_x=100,
        label="delayRates",
        doc="Delay rate for each beam to be applied during the next "
        "pointing update (archived)",
    )

    bandpassCoefficient = attribute(
        dtype=("float",),
        max_dim_x=100,
        label="bandpassCoefficient",
        doc="Bandpass coefficient to apply during next calibration cycle to "
        "flatten the antenna's bandpass (archived)",
    )

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

        self.register_command_object(
            "PowerOn",
            self.PowerOn(*args)
        )
        
        self.register_command_object(
            "PowerOff",
            self.PowerOff(*args)
        )

    def always_executed_hook(self):

        pass

    def delete_device(self):

        pass

    # ------------------
    # Attributes methods
    # ------------------

    def antennaId(self):
        #return 0
        return self._antennaId

    def logicalTpmAntenna_id(self):
        #return 0
        return self._logicalTpmAntenna_id

    def logicalApiuAntenna_id(self):
        #return 0.0
        return self._logicalApiuAntenna_id

    def tpmId(self):
        #return 0.0
        return self._tpmId

    def apiuId(self):
        #return 0.0
        return self._apiuId

    def gain(self):
        #return 0.0
        return self._gain

    def rms(self):
        #return 0.0
        return self._rms

    def voltage(self):
        #return 0.0
        return self._voltage

    def temperature(self):
        #return 0.0
        return self._temperature

    def xPolarisationFaulty(self):
        #return False
        return self._xPolarisationFaulty
        
    def yPolarisationFaulty(self):
        #return False
        return self._yPolarisationFaulty

    def fieldNodeLongitude(self):
        #return 0.0
        return self._fieldNodeLongitude

    def fieldNodeLatitude(self):
        #return 0.0
        return self._fieldNodeLongitude

    def altitude(self):
        #return 0.0
        return self._altitude

    def xDisplacement(self):
        #return 0.0
        return self._xDisplacement

    def yDisplacement(self):
        #return 0.0
        return self._yDisplacement

    def timestampOfLastSpectrum(self):
        #return ""
        return self._timestampOfLastSpectrum

    def logicalAntennaId(self):
        #return 0
        return self._logicalAntennaId

    def xPolarisationScalingFactor(self):
        #return [0]
        return self._xPolarisationScalingFactor

    def yPolarisationScalingFactor(self):
        #return [0]
        return self._yPolarisationScalingFactor

    def calibrationCoefficient(self):
        #return [0.0]
        return self._calibrationCoefficient

    def pointingCoefficient(self):
        #return [0.0]
        return self._pointingCoefficient

    def spectrumX(self):
        #return [0.0]
        return self._spectrumX

    def spectrumY(self):
        #return [0.0]
        return self._spectrumY

    def position(self):
        #return [0.0]
        return self._position

    def delays(self):
        #return [0.0]
        return self._delays

    def delayRates(self):
        #return [0.0]
        return self._delayRates

    def bandpassCoefficient(self):
        #return [0.0]
        return self._bandpassCoefficient

    # --------
    # Commands
    # --------
    class PowerOnCommand(ResponseCommand):
        def do(self):
            """
            Stateless hook for implementation of ExceptionCallback()
            command functionality.
            """
            return (ResultCode.OK, "Stub implementation, does nothing")

    @command()
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

    @command()
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
