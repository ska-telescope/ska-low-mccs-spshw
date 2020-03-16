# -*- coding: utf-8 -*-
#
# This file is part of the LfaaAntenna project
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
from PyTango import AttrQuality, DispLevel, DevState
from PyTango import AttrWriteType, PipeWriteType
# Additional import
# PROTECTED REGION ID(LfaaAntenna.additionnal_import) ENABLED START #
# PROTECTED REGION END #    //  LfaaAntenna.additionnal_import

__all__ = ["LfaaAntenna", "main"]


class LfaaAntenna(Device):
    """
    An implementation of the Antenna Device Server for the MCCS based upon architecture in SKA-TEL-LFAA-06000052-02.
    """
    __metaclass__ = DeviceMeta
    # PROTECTED REGION ID(LfaaAntenna.class_variable) ENABLED START #
    # PROTECTED REGION END #    //  LfaaAntenna.class_variable

    # ----------
    # Attributes
    # ----------

    antennaId = attribute(
        dtype='int',
        label="AntennaID",
    )

    logicalTpmAntenna_id = attribute(
        dtype='int',
        label="logicalTpmAntenna_id",
    )

    logicalApiuAntenna_id = attribute(
        dtype='double',
        label="logicalApiuAntenna_id",
    )

    tpmId = attribute(
        dtype='double',
        label="tpmId",
    )

    apiuId = attribute(
        dtype='double',
        label="apiuId",
    )

    gain = attribute(
        dtype='float',
        label="gain",
    )

    rms = attribute(
        dtype='float',
        label="rms",
    )

    voltage = attribute(
        dtype='float',
        label="voltage",
        unit="volts",
    )

    temperature = attribute(
        dtype='float',
        label="temperature",
        unit="DegC",
    )

    xPolarisationFaulty = attribute(
        dtype='bool',
        label="xPolarisationFaulty",
    )

    yPolarisationFaulty = attribute(
        dtype='bool',
        label="yPolarisationFaulty",
    )

    fieldNodeLongitude = attribute(
        dtype='float',
        label="fieldNodeLongitude",
    )

    fieldNodeLatitude = attribute(
        dtype='float',
        label="fieldNodeLatitude",
    )

    altitude = attribute(
        dtype='float',
        label="altitude",
    )

    xDisplacement = attribute(
        dtype='float',
        label="xDisplacement",
    )

    yDisplacement = attribute(
        dtype='float',
    )

    timestampOfLastSpectrum = attribute(
        dtype='str',
        label="timestampOfLastSpectrum",
    )

    xPolarisationScalingFactor = attribute(
        dtype=('int',),
        max_dim_x=100,
        label="xPolarisationScalingFactor",
    )

    yPolarisationScalingFactor = attribute(
        dtype=('int',),
        max_dim_x=100,
        label="yPolarisationScalingFactor",
    )

    calibrationCoefficient = attribute(
        dtype=('float',),
        max_dim_x=100,
        label="calibrationCoefficient",
        doc="This is presented as a vector.",
    )

    pointingCoefficient = attribute(
        dtype=('float',),
        max_dim_x=100,
        doc="This is presented as a vector.",
    )

    spectrumX = attribute(
        dtype=('float',),
        max_dim_x=100,
        label="spectrumX",
    )

    spectrumY = attribute(
        dtype=('float',),
        max_dim_x=100,
        label="spectrumY",
    )

    position = attribute(
        dtype=('float',),
        max_dim_x=100,
        label="position",
    )

    # ---------------
    # General methods
    # ---------------

    def init_device(self):
        Device.init_device(self)
        # PROTECTED REGION ID(LfaaAntenna.init_device) ENABLED START #
        # PROTECTED REGION END #    //  LfaaAntenna.init_device

    def always_executed_hook(self):
        # PROTECTED REGION ID(LfaaAntenna.always_executed_hook) ENABLED START #
        pass
        # PROTECTED REGION END #    //  LfaaAntenna.always_executed_hook

    def delete_device(self):
        # PROTECTED REGION ID(LfaaAntenna.delete_device) ENABLED START #
        pass
        # PROTECTED REGION END #    //  LfaaAntenna.delete_device

    # ------------------
    # Attributes methods
    # ------------------

    def read_antennaId(self):
        # PROTECTED REGION ID(LfaaAntenna.antennaId_read) ENABLED START #
        return 0
        # PROTECTED REGION END #    //  LfaaAntenna.antennaId_read

    def read_logicalTpmAntenna_id(self):
        # PROTECTED REGION ID(LfaaAntenna.logicalTpmAntenna_id_read) ENABLED START #
        return 0
        # PROTECTED REGION END #    //  LfaaAntenna.logicalTpmAntenna_id_read

    def read_logicalApiuAntenna_id(self):
        # PROTECTED REGION ID(LfaaAntenna.logicalApiuAntenna_id_read) ENABLED START #
        return 0.0
        # PROTECTED REGION END #    //  LfaaAntenna.logicalApiuAntenna_id_read

    def read_tpmId(self):
        # PROTECTED REGION ID(LfaaAntenna.tpmId_read) ENABLED START #
        return 0.0
        # PROTECTED REGION END #    //  LfaaAntenna.tpmId_read

    def read_apiuId(self):
        # PROTECTED REGION ID(LfaaAntenna.apiuId_read) ENABLED START #
        return 0.0
        # PROTECTED REGION END #    //  LfaaAntenna.apiuId_read

    def read_gain(self):
        # PROTECTED REGION ID(LfaaAntenna.gain_read) ENABLED START #
        return 0.0
        # PROTECTED REGION END #    //  LfaaAntenna.gain_read

    def read_rms(self):
        # PROTECTED REGION ID(LfaaAntenna.rms_read) ENABLED START #
        return 0.0
        # PROTECTED REGION END #    //  LfaaAntenna.rms_read

    def read_voltage(self):
        # PROTECTED REGION ID(LfaaAntenna.voltage_read) ENABLED START #
        return 0.0
        # PROTECTED REGION END #    //  LfaaAntenna.voltage_read

    def read_temperature(self):
        # PROTECTED REGION ID(LfaaAntenna.temperature_read) ENABLED START #
        return 0.0
        # PROTECTED REGION END #    //  LfaaAntenna.temperature_read

    def read_xPolarisationFaulty(self):
        # PROTECTED REGION ID(LfaaAntenna.xPolarisationFaulty_read) ENABLED START #
        return False
        # PROTECTED REGION END #    //  LfaaAntenna.xPolarisationFaulty_read

    def read_yPolarisationFaulty(self):
        # PROTECTED REGION ID(LfaaAntenna.yPolarisationFaulty_read) ENABLED START #
        return False
        # PROTECTED REGION END #    //  LfaaAntenna.yPolarisationFaulty_read

    def read_fieldNodeLongitude(self):
        # PROTECTED REGION ID(LfaaAntenna.fieldNodeLongitude_read) ENABLED START #
        return 0.0
        # PROTECTED REGION END #    //  LfaaAntenna.fieldNodeLongitude_read

    def read_fieldNodeLatitude(self):
        # PROTECTED REGION ID(LfaaAntenna.fieldNodeLatitude_read) ENABLED START #
        return 0.0
        # PROTECTED REGION END #    //  LfaaAntenna.fieldNodeLatitude_read

    def read_altitude(self):
        # PROTECTED REGION ID(LfaaAntenna.altitude_read) ENABLED START #
        return 0.0
        # PROTECTED REGION END #    //  LfaaAntenna.altitude_read

    def read_xDisplacement(self):
        # PROTECTED REGION ID(LfaaAntenna.xDisplacement_read) ENABLED START #
        return 0.0
        # PROTECTED REGION END #    //  LfaaAntenna.xDisplacement_read

    def read_yDisplacement(self):
        # PROTECTED REGION ID(LfaaAntenna.yDisplacement_read) ENABLED START #
        return 0.0
        # PROTECTED REGION END #    //  LfaaAntenna.yDisplacement_read

    def read_timestampOfLastSpectrum(self):
        # PROTECTED REGION ID(LfaaAntenna.timestampOfLastSpectrum_read) ENABLED START #
        return ''
        # PROTECTED REGION END #    //  LfaaAntenna.timestampOfLastSpectrum_read

    def read_xPolarisationScalingFactor(self):
        # PROTECTED REGION ID(LfaaAntenna.xPolarisationScalingFactor_read) ENABLED START #
        return [0]
        # PROTECTED REGION END #    //  LfaaAntenna.xPolarisationScalingFactor_read

    def read_yPolarisationScalingFactor(self):
        # PROTECTED REGION ID(LfaaAntenna.yPolarisationScalingFactor_read) ENABLED START #
        return [0]
        # PROTECTED REGION END #    //  LfaaAntenna.yPolarisationScalingFactor_read

    def read_calibrationCoefficient(self):
        # PROTECTED REGION ID(LfaaAntenna.calibrationCoefficient_read) ENABLED START #
        return [0.0]
        # PROTECTED REGION END #    //  LfaaAntenna.calibrationCoefficient_read

    def read_pointingCoefficient(self):
        # PROTECTED REGION ID(LfaaAntenna.pointingCoefficient_read) ENABLED START #
        return [0.0]
        # PROTECTED REGION END #    //  LfaaAntenna.pointingCoefficient_read

    def read_spectrumX(self):
        # PROTECTED REGION ID(LfaaAntenna.spectrumX_read) ENABLED START #
        return [0.0]
        # PROTECTED REGION END #    //  LfaaAntenna.spectrumX_read

    def read_spectrumY(self):
        # PROTECTED REGION ID(LfaaAntenna.spectrumY_read) ENABLED START #
        return [0.0]
        # PROTECTED REGION END #    //  LfaaAntenna.spectrumY_read

    def read_position(self):
        # PROTECTED REGION ID(LfaaAntenna.position_read) ENABLED START #
        return [0.0]
        # PROTECTED REGION END #    //  LfaaAntenna.position_read


    # --------
    # Commands
    # --------

    @command(
    )
    @DebugIt()
    def PowerOn(self):
        # PROTECTED REGION ID(LfaaAntenna.PowerOn) ENABLED START #
        pass
        # PROTECTED REGION END #    //  LfaaAntenna.PowerOn

    @command(
    )
    @DebugIt()
    def PowerOff(self):
        # PROTECTED REGION ID(LfaaAntenna.PowerOff) ENABLED START #
        pass
        # PROTECTED REGION END #    //  LfaaAntenna.PowerOff

# ----------
# Run server
# ----------


def main(args=None, **kwargs):
    # PROTECTED REGION ID(LfaaAntenna.main) ENABLED START #
    return run((LfaaAntenna,), args=args, **kwargs)
    # PROTECTED REGION END #    //  LfaaAntenna.main

if __name__ == '__main__':
    main()
