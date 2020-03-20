# -*- coding: utf-8 -*-
#
# This file is part of the MccsAntenna project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

""" LFAA Antenna Device Server

An implementation of the Antenna Device Server for the MCCS based upon architecture in SKA-TEL-LFAA-06000052-02.
"""

# PyTango imports
import PyTango
from PyTango import DebugIt
from PyTango.server import run
from PyTango.server import Device, DeviceMeta
from PyTango.server import attribute, command
from PyTango.server import device_property
from PyTango import AttrQuality, DispLevel, DevState
from PyTango import AttrWriteType, PipeWriteType

###from SKABaseDevice import SKABaseDevice
# Additional import
from ska.base import SKABaseDevice

# PROTECTED REGION ID(MccsAntenna.additionnal_import) ENABLED START #
# PROTECTED REGION END #    //  MccsAntenna.additionnal_import

__all__ = ["MccsAntenna", "main"]


class MccsAntenna(SKABaseDevice):
    """
    An implementation of the Antenna Device Server for the MCCS based upon architecture in SKA-TEL-LFAA-06000052-02.
    """

    __metaclass__ = DeviceMeta
    # PROTECTED REGION ID(MccsAntenna.class_variable) ENABLED START #
    # PROTECTED REGION END #    //  MccsAntenna.class_variable

    # -----------------
    # Device Properties
    # -----------------

    # ----------
    # Attributes
    # ----------

    antennaId = attribute(
        dtype="int", label="AntennaID", doc="Global antenna identifier",
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

    apiuId = attribute(dtype="double", label="apiuId",)

    gain = attribute(dtype="float", label="gain", doc="The gain set for the antenna",)

    rms = attribute(
        dtype="float", label="rms", doc="The measured RMS of the antenna (monitored)",
    )

    voltage = attribute(dtype="float", label="voltage", unit="volts",)

    temperature = attribute(dtype="float", label="temperature", unit="DegC",)

    xPolarisationFaulty = attribute(dtype="bool", label="xPolarisationFaulty",)

    yPolarisationFaulty = attribute(dtype="bool", label="yPolarisationFaulty",)

    fieldNodeLongitude = attribute(
        dtype="float",
        label="fieldNodeLongitude",
        doc="Longnitude of field node (centre) to which antenna is asociated.",
    )

    fieldNodeLatitude = attribute(
        dtype="float",
        label="fieldNodeLatitude",
        doc="Latitude of the field node (centre) to which antenna is asociated.",
    )

    altitude = attribute(
        dtype="float",
        label="altitude",
        unit="meters",
        doc="Antenna altitude in meters",
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

    timestampOfLastSpectrum = attribute(dtype="str", label="timestampOfLastSpectrum",)

    logicalAntennaId = attribute(
        dtype="int",
        label="logicalAntennaId",
        doc="Local (within Tile) antenna identifier",
    )

    xPolarisationScalingFactor = attribute(
        dtype=("int",), max_dim_x=100, label="xPolarisationScalingFactor",
    )

    yPolarisationScalingFactor = attribute(
        dtype=("int",), max_dim_x=100, label="yPolarisationScalingFactor",
    )

    calibrationCoefficient = attribute(
        dtype=("float",),
        max_dim_x=100,
        label="calibrationCoefficient",
        doc="Callibration coefficient to be applied for the next frequency channel in the calibration cycle (archived)\n\nThis is presented as a vector.\n",
    )

    pointingCoefficient = attribute(
        dtype=("float",), max_dim_x=100, doc="This is presented as a vector.",
    )

    spectrumX = attribute(dtype=("float",), max_dim_x=100, label="spectrumX",)

    spectrumY = attribute(dtype=("float",), max_dim_x=100, label="spectrumY",)

    position = attribute(dtype=("float",), max_dim_x=100, label="position",)

    delays = attribute(
        dtype=("float",),
        max_dim_x=100,
        label="delays",
        doc="Delay for each beam to be applied during the next pointing update (archived)",
    )

    delayRates = attribute(
        dtype=("float",),
        max_dim_x=100,
        label="delayRates",
        doc="Delay rate for each beam to be applied during the next pointing update (archived)",
    )

    bandpassCoefficient = attribute(
        dtype=("float",),
        max_dim_x=100,
        label="bandpassCoefficient",
        doc="Bandpass coefficient to apply during next calibration cycle to flatten the antenna's bandpass (archived)",
    )

    # ---------------
    # General methods
    # ---------------

    def init_device(self):
        SKABaseDevice.init_device(self)
        # PROTECTED REGION ID(MccsAntenna.init_device) ENABLED START #
        # PROTECTED REGION END #    //  MccsAntenna.init_device

    def always_executed_hook(self):
        # PROTECTED REGION ID(MccsAntenna.always_executed_hook) ENABLED START #
        pass
        # PROTECTED REGION END #    //  MccsAntenna.always_executed_hook

    def delete_device(self):
        # PROTECTED REGION ID(MccsAntenna.delete_device) ENABLED START #
        pass
        # PROTECTED REGION END #    //  MccsAntenna.delete_device

    # ------------------
    # Attributes methods
    # ------------------

    def read_antennaId(self):
        # PROTECTED REGION ID(MccsAntenna.antennaId_read) ENABLED START #
        return 0
        # PROTECTED REGION END #    //  MccsAntenna.antennaId_read

    def read_logicalTpmAntenna_id(self):
        # PROTECTED REGION ID(MccsAntenna.logicalTpmAntenna_id_read) ENABLED START #
        return 0
        # PROTECTED REGION END #    //  MccsAntenna.logicalTpmAntenna_id_read

    def read_logicalApiuAntenna_id(self):
        # PROTECTED REGION ID(MccsAntenna.logicalApiuAntenna_id_read) ENABLED START #
        return 0.0
        # PROTECTED REGION END #    //  MccsAntenna.logicalApiuAntenna_id_read

    def read_tpmId(self):
        # PROTECTED REGION ID(MccsAntenna.tpmId_read) ENABLED START #
        return 0.0
        # PROTECTED REGION END #    //  MccsAntenna.tpmId_read

    def read_apiuId(self):
        # PROTECTED REGION ID(MccsAntenna.apiuId_read) ENABLED START #
        return 0.0
        # PROTECTED REGION END #    //  MccsAntenna.apiuId_read

    def read_gain(self):
        # PROTECTED REGION ID(MccsAntenna.gain_read) ENABLED START #
        return 0.0
        # PROTECTED REGION END #    //  MccsAntenna.gain_read

    def read_rms(self):
        # PROTECTED REGION ID(MccsAntenna.rms_read) ENABLED START #
        return 0.0
        # PROTECTED REGION END #    //  MccsAntenna.rms_read

    def read_voltage(self):
        # PROTECTED REGION ID(MccsAntenna.voltage_read) ENABLED START #
        return 0.0
        # PROTECTED REGION END #    //  MccsAntenna.voltage_read

    def read_temperature(self):
        # PROTECTED REGION ID(MccsAntenna.temperature_read) ENABLED START #
        return 0.0
        # PROTECTED REGION END #    //  MccsAntenna.temperature_read

    def read_xPolarisationFaulty(self):
        # PROTECTED REGION ID(MccsAntenna.xPolarisationFaulty_read) ENABLED START #
        return False
        # PROTECTED REGION END #    //  MccsAntenna.xPolarisationFaulty_read

    def read_yPolarisationFaulty(self):
        # PROTECTED REGION ID(MccsAntenna.yPolarisationFaulty_read) ENABLED START #
        return False
        # PROTECTED REGION END #    //  MccsAntenna.yPolarisationFaulty_read

    def read_fieldNodeLongitude(self):
        # PROTECTED REGION ID(MccsAntenna.fieldNodeLongitude_read) ENABLED START #
        return 0.0
        # PROTECTED REGION END #    //  MccsAntenna.fieldNodeLongitude_read

    def read_fieldNodeLatitude(self):
        # PROTECTED REGION ID(MccsAntenna.fieldNodeLatitude_read) ENABLED START #
        return 0.0
        # PROTECTED REGION END #    //  MccsAntenna.fieldNodeLatitude_read

    def read_altitude(self):
        # PROTECTED REGION ID(MccsAntenna.altitude_read) ENABLED START #
        return 0.0
        # PROTECTED REGION END #    //  MccsAntenna.altitude_read

    def read_xDisplacement(self):
        # PROTECTED REGION ID(MccsAntenna.xDisplacement_read) ENABLED START #
        return 0.0
        # PROTECTED REGION END #    //  MccsAntenna.xDisplacement_read

    def read_yDisplacement(self):
        # PROTECTED REGION ID(MccsAntenna.yDisplacement_read) ENABLED START #
        return 0.0
        # PROTECTED REGION END #    //  MccsAntenna.yDisplacement_read

    def read_timestampOfLastSpectrum(self):
        # PROTECTED REGION ID(MccsAntenna.timestampOfLastSpectrum_read) ENABLED START #
        return ""
        # PROTECTED REGION END #    //  MccsAntenna.timestampOfLastSpectrum_read

    def read_logicalAntennaId(self):
        # PROTECTED REGION ID(MccsAntenna.logicalAntennaId_read) ENABLED START #
        return 0
        # PROTECTED REGION END #    //  MccsAntenna.logicalAntennaId_read

    def read_xPolarisationScalingFactor(self):
        # PROTECTED REGION ID(MccsAntenna.xPolarisationScalingFactor_read) ENABLED START #
        return [0]
        # PROTECTED REGION END #    //  MccsAntenna.xPolarisationScalingFactor_read

    def read_yPolarisationScalingFactor(self):
        # PROTECTED REGION ID(MccsAntenna.yPolarisationScalingFactor_read) ENABLED START #
        return [0]
        # PROTECTED REGION END #    //  MccsAntenna.yPolarisationScalingFactor_read

    def read_calibrationCoefficient(self):
        # PROTECTED REGION ID(MccsAntenna.calibrationCoefficient_read) ENABLED START #
        return [0.0]
        # PROTECTED REGION END #    //  MccsAntenna.calibrationCoefficient_read

    def read_pointingCoefficient(self):
        # PROTECTED REGION ID(MccsAntenna.pointingCoefficient_read) ENABLED START #
        return [0.0]
        # PROTECTED REGION END #    //  MccsAntenna.pointingCoefficient_read

    def read_spectrumX(self):
        # PROTECTED REGION ID(MccsAntenna.spectrumX_read) ENABLED START #
        return [0.0]
        # PROTECTED REGION END #    //  MccsAntenna.spectrumX_read

    def read_spectrumY(self):
        # PROTECTED REGION ID(MccsAntenna.spectrumY_read) ENABLED START #
        return [0.0]
        # PROTECTED REGION END #    //  MccsAntenna.spectrumY_read

    def read_position(self):
        # PROTECTED REGION ID(MccsAntenna.position_read) ENABLED START #
        return [0.0]
        # PROTECTED REGION END #    //  MccsAntenna.position_read

    def read_delays(self):
        # PROTECTED REGION ID(MccsAntenna.delays_read) ENABLED START #
        return [0.0]
        # PROTECTED REGION END #    //  MccsAntenna.delays_read

    def read_delayRates(self):
        # PROTECTED REGION ID(MccsAntenna.delayRates_read) ENABLED START #
        return [0.0]
        # PROTECTED REGION END #    //  MccsAntenna.delayRates_read

    def read_bandpassCoefficient(self):
        # PROTECTED REGION ID(MccsAntenna.bandpassCoefficient_read) ENABLED START #
        return [0.0]
        # PROTECTED REGION END #    //  MccsAntenna.bandpassCoefficient_read

    # --------
    # Commands
    # --------

    @command()
    @DebugIt()
    def PowerOn(self):
        # PROTECTED REGION ID(MccsAntenna.PowerOn) ENABLED START #
        pass
        # PROTECTED REGION END #    //  MccsAntenna.PowerOn

    @command()
    @DebugIt()
    def PowerOff(self):
        # PROTECTED REGION ID(MccsAntenna.PowerOff) ENABLED START #
        pass
        # PROTECTED REGION END #    //  MccsAntenna.PowerOff


# ----------
# Run server
# ----------


def main(args=None, **kwargs):
    # PROTECTED REGION ID(MccsAntenna.main) ENABLED START #
    return run((MccsAntenna,), args=args, **kwargs)
    # PROTECTED REGION END #    //  MccsAntenna.main


if __name__ == "__main__":
    main()
