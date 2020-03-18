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
from PyTango.server import device_property
from PyTango import AttrQuality, DispLevel, DevState
from PyTango import AttrWriteType, PipeWriteType
###from SKABaseDevice import SKABaseDevice
# Additional import
from ska.base import SKABaseDevice
# PROTECTED REGION ID(LfaaAntenna.additionnal_import) ENABLED START #
# PROTECTED REGION END #    //  LfaaAntenna.additionnal_import

__all__ = ["LfaaAntenna", "main"]


class LfaaAntenna(SKABaseDevice):
    """
    An implementation of the Antenna Device Server for the MCCS based upon architecture in SKA-TEL-LFAA-06000052-02.
    """
    __metaclass__ = DeviceMeta
    # PROTECTED REGION ID(LfaaAntenna.class_variable) ENABLED START #
    # PROTECTED REGION END #    //  LfaaAntenna.class_variable

    # -----------------
    # Device Properties
    # -----------------





    # ----------
    # Attributes
    # ----------

    # ---------------
    # General methods
    # ---------------

    def init_device(self):
        SKABaseDevice.init_device(self)
        # PROTECTED REGION ID(LfaaAntenna.init_device) ENABLED START #
        self._antennaId = 0
        self._logicalTpmAntenna_id = 0
        self._logicalApiuAntenna_id = 0.0
        self._tpmId = 0.0
        self._apiuId = 0.0
        self._gain = 0.0
        self._rms = 0.0
        self._voltage = 0.0
        self._temperature = 0.0
        self._xPolarisationFaulty = False
        self._yPolarisationFaulty = False
        self._fieldNodeLongitude = 0.0
        self._fieldNodeLatitude = 0.0
        self._altitude = 0.0
        self._xDisplacement = 0.0
        self._yDisplacement = 0.0
        self._timestampOfLastSpectrum = ''
        self._logicalAntennaId = 0
        self._xPolarisationScalingFactor = [0]
        self._yPolarisationScalingFactor = [0]
        self._calibrationCoefficient = [0.0]
        self._pointingCoefficient = [0.0]
        self._spectrumX = [0.0]
        self._spectrumY = [0.0]
        self._position = [0.0]
        self._delays = [0.0]
        self._delayRates = [0.0]
        self._bandpassCoefficient = [0.0]


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
    @attribute(
        dtype='int',
        label="AntennaID",
        doc="Global antenna identifier",
    )
    def antennaId(self):
        # PROTECTED REGION ID(LfaaAntenna.antennaId) ENABLED START #
        return self._antennaId
        # PROTECTED REGION END #    //  LfaaAntenna.antennaId

    @attribute(
        dtype='int',
        label="logicalTpmAntenna_id",
        doc="Local within Tile identifier for the Antenna TPM\n",
    )
    def logicalTpmAntenna_id(self):
        # PROTECTED REGION ID(LfaaAntenna.logicalTpmAntenna_id) ENABLED START #
        return self._logicalTpmAntenna_id
        # PROTECTED REGION END #    //  LfaaAntenna.logicalTpmAntenna_id

    @attribute(
        dtype='double',
        label="logicalApiuAntenna_id",
        doc="Local within Tile identifier for the Antenna APIU",
    )
    def logicalApiuAntenna_id(self):
        # PROTECTED REGION ID(LfaaAntenna.logicalApiuAntenna_id) ENABLED START #
        return self._logicalApiuAntenna_id
        # PROTECTED REGION END #    //  LfaaAntenna.logicalApiuAntenna_id

    @attribute(
        dtype='double',
        label="tpmId",
        doc="Global Tile ID to which the atenna is connected",
    )
    def tpmId(self):
        # PROTECTED REGION ID(LfaaAntenna.tpmId) ENABLED START #
        return self._tpmId
        # PROTECTED REGION END #    //  LfaaAntenna.tpmId

    @attribute(
        dtype='double',
        label="apiuId",
    )
    def apiuId(self):
        # PROTECTED REGION ID(LfaaAntenna.apiuId) ENABLED START #
        return self._apiuId
        # PROTECTED REGION END #    //  LfaaAntenna.apiuId

    @attribute(
        dtype='float',
        label="gain",
        doc="The gain set for the antenna",
    )
    def gain(self):
        # PROTECTED REGION ID(LfaaAntenna.gain) ENABLED START #
        return self._gain
        # PROTECTED REGION END #    //  LfaaAntenna.gain

    @attribute(
        dtype='float',
        label="rms",
        doc="The measured RMS of the antenna (monitored)",
    )
    def rms(self):
        # PROTECTED REGION ID(LfaaAntenna.rms) ENABLED START #
        return self._rms
        # PROTECTED REGION END #    //  LfaaAntenna.rms

    @attribute(
        dtype='float',
        label="voltage",
        unit="volts",
    )
    def voltage(self):
        # PROTECTED REGION ID(LfaaAntenna.voltage) ENABLED START #
        return self._voltage
        # PROTECTED REGION END #    //  LfaaAntenna.voltage

    @attribute(
        dtype='float',
        label="temperature",
        unit="DegC",
    )
    def temperature(self):
        # PROTECTED REGION ID(LfaaAntenna.temperature) ENABLED START #
        return self._temperature
        # PROTECTED REGION END #    //  LfaaAntenna.temperature

    @attribute(
        dtype='bool',
        label="xPolarisationFaulty",
    )
    def xPolarisationFaulty(self):
        # PROTECTED REGION ID(LfaaAntenna.xPolarisationFaulty) ENABLED START #
        return self._xPolarisationFaulty
        # PROTECTED REGION END #    //  LfaaAntenna.xPolarisationFaulty

    @attribute(
        dtype='bool',
        label="yPolarisationFaulty",
    )
    def yPolarisationFaulty(self):
        # PROTECTED REGION ID(LfaaAntenna.yPolarisationFaulty) ENABLED START #
        return self._yPolarisationFaulty
        # PROTECTED REGION END #    //  LfaaAntenna.yPolarisationFaulty

    @attribute(
        dtype='float',
        label="fieldNodeLongitude",
        doc="Longnitude of field node (centre) to which antenna is asociated.",
    )
    def fieldNodeLongitude(self):
        # PROTECTED REGION ID(LfaaAntenna.fieldNodeLongitude) ENABLED START #
        return self._fieldNodeLongitude
        # PROTECTED REGION END #    //  LfaaAntenna.fieldNodeLongitude

    @attribute(
        dtype='float',
        label="fieldNodeLatitude",
        doc="Latitude of the field node (centre) to which antenna is asociated.",
    )
    def fieldNodeLatitude(self):
        # PROTECTED REGION ID(LfaaAntenna.fieldNodeLatitude) ENABLED START #
        return self._fieldNodeLatitude
        # PROTECTED REGION END #    //  LfaaAntenna.fieldNodeLatitude

    @attribute(
        dtype='float',
        label="altitude",
        unit="meters",
        doc="Antenna altitude in meters",
    )
    def altitude(self):
        # PROTECTED REGION ID(LfaaAntenna.altitude) ENABLED START #
        return self._altitude
        # PROTECTED REGION END #    //  LfaaAntenna.altitude

    @attribute(
        dtype='float',
        label="xDisplacement",
        unit="meters",
        doc="Horizontal displacement in meters from field node centre",
    )
    def xDisplacement(self):
        # PROTECTED REGION ID(LfaaAntenna.xDisplacement) ENABLED START #
        return self._xDisplacement
        # PROTECTED REGION END #    //  LfaaAntenna.xDisplacement

    @attribute(
        dtype='float',
        label="yDisplacement",
        unit="meters",
        doc="Vertical displacement in meters from field centre",
    )
    def yDisplacement(self):
        # PROTECTED REGION ID(LfaaAntenna.yDisplacement) ENABLED START #
        return self._yDisplacement
        # PROTECTED REGION END #    //  LfaaAntenna.yDisplacement

    @attribute(
        dtype='str',
        label="timestampOfLastSpectrum",
    )
    def timestampOfLastSpectrum(self):
        # PROTECTED REGION ID(LfaaAntenna.timestampOfLastSpectrum) ENABLED START #
        return self._timestampOfLastSpectrum
        # PROTECTED REGION END #    //  LfaaAntenna.timestampOfLastSpectrum

    @attribute(
        dtype='int',
        label="logicalAntennaId",
        doc="Local (within Tile) antenna identifier",
    )
    def logicalAntennaId(self):
        # PROTECTED REGION ID(LfaaAntenna.logicalAntennaId) ENABLED START #
        return self._logicalAntennaId
        # PROTECTED REGION END #    //  LfaaAntenna.logicalAntennaId

    @attribute(
        dtype=('int',),
        max_dim_x=100,
        label="xPolarisationScalingFactor",
    )
    def xPolarisationScalingFactor(self):
        # PROTECTED REGION ID(LfaaAntenna.xPolarisationScalingFactor) ENABLED START #
        return self._xPolarisationScalingFactor
        # PROTECTED REGION END #    //  LfaaAntenna.xPolarisationScalingFactor

    @attribute(
        dtype=('int',),
        max_dim_x=100,
        label="yPolarisationScalingFactor",
    )
    def yPolarisationScalingFactor(self):
        # PROTECTED REGION ID(LfaaAntenna.yPolarisationScalingFactor) ENABLED START #
        return self._yPolarisationScalingFactor
        # PROTECTED REGION END #    //  LfaaAntenna.yPolarisationScalingFactor

    @attribute(
        dtype=('float',),
        max_dim_x=100,
        label="calibrationCoefficient",
        doc="Callibration coefficient to be applied for the next frequency channel in the calibration cycle (archived)\n\nThis is presented as a vector.\n",
    )
    def calibrationCoefficient(self):
        # PROTECTED REGION ID(LfaaAntenna.calibrationCoefficient) ENABLED START #
        return self._calibrationCoefficient
        # PROTECTED REGION END #    //  LfaaAntenna.calibrationCoefficient

    @attribute(
        dtype=('float',),
        max_dim_x=100,
        doc="This is presented as a vector.",
    )
    def pointingCoefficient(self):
        # PROTECTED REGION ID(LfaaAntenna.pointingCoefficient) ENABLED START #
        return self._pointingCoefficient
        # PROTECTED REGION END #    //  LfaaAntenna.pointingCoefficient

    @attribute(
        dtype=('float',),
        max_dim_x=100,
        label="spectrumX",
    )
    def spectrumX(self):
        # PROTECTED REGION ID(LfaaAntenna.spectrumX) ENABLED START #
        return self._spectrumX
        # PROTECTED REGION END #    //  LfaaAntenna.spectrumX

    @attribute(
        dtype=('float',),
        max_dim_x=100,
        label="spectrumY",
    )
    def spectrumY(self):
        # PROTECTED REGION ID(LfaaAntenna.spectrumY) ENABLED START #
        return self._spectrumY
        # PROTECTED REGION END #    //  LfaaAntenna.spectrumY

    @attribute(
        dtype=('float',),
        max_dim_x=100,
        label="position",
    )
    def position(self):
        # PROTECTED REGION ID(LfaaAntenna.position) ENABLED START #
        return self._position
        # PROTECTED REGION END #    //  LfaaAntenna.position
    @attribute(
        dtype=('float',),
        max_dim_x=100,
        label="delays",
        doc="Delay for each beam to be applied during the next pointing update (archived)",
    )
    def delays(self):
        # PROTECTED REGION ID(LfaaAntenna.delays) ENABLED START #
        return self._delays
        # PROTECTED REGION END #    //  LfaaAntenna.delays
    @attribute(
        dtype=('float',),
        max_dim_x=100,
        label="delayRates",
        doc="Delay rate for each beam to be applied during the next pointing update (archived)",
    )
    def delayRates(self):
        # PROTECTED REGION ID(LfaaAntenna.delayRates) ENABLED START #
        return self._delayRates
        # PROTECTED REGION END #    //  LfaaAntenna.delayRates

    @attribute(
        dtype=('float',),
        max_dim_x=100,
        label="bandpassCoefficient",
        doc="Bandpass coefficient to apply during next calibration cycle to flatten the antenna's bandpass (archived)",
    )
    def bandpassCoefficient(self):
        # PROTECTED REGION ID(LfaaAntenna.bandpassCoefficient_read) ENABLED START #
        return self._bandpassCoefficient
        # PROTECTED REGION END #    //  LfaaAntenna.bandpassCoefficient_read


    # --------
    # Commands
    # --------

    @command(
    )
    @DebugIt()
    def PowerOn(self, argin):
        # PROTECTED REGION ID(LfaaAntenna.PowerOn) ENABLED START #
        return ""
        # PROTECTED REGION END #    //  LfaaAntenna.PowerOn

    @command(
    )
    @DebugIt()
    def PowerOff(self, argin):
        # PROTECTED REGION ID(LfaaAntenna.PowerOff) ENABLED START #
        return ""
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
