#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of the LfaaAntenna project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""Contain the tests for the LFAA Antenna Device Server."""

# Path
import sys
import os
path = os.path.join(os.path.dirname(__file__), os.pardir)
sys.path.insert(0, os.path.abspath(path))

# Imports
from time import sleep
from mock import MagicMock
from PyTango import DevFailed, DevState
from devicetest import DeviceTestCase, main
from LfaaAntenna import LfaaAntenna

# Note:
#
# Since the device uses an inner thread, it is necessary to
# wait during the tests in order the let the device update itself.
# Hence, the sleep calls have to be secured enough not to produce
# any inconsistent behavior. However, the unittests need to run fast.
# Here, we use a factor 3 between the read period and the sleep calls.
#
# Look at devicetest examples for more advanced testing


# Device test case
class LfaaAntennaDeviceTestCase(DeviceTestCase):
    """Test case for packet generation."""
    # PROTECTED REGION ID(LfaaAntenna.test_additionnal_import) ENABLED START #
    # PROTECTED REGION END #    //  LfaaAntenna.test_additionnal_import
    device = LfaaAntenna
    properties = {
                  }
    empty = None  # Should be []

    @classmethod
    def mocking(cls):
        """Mock external libraries."""
        # Example : Mock numpy
        # cls.numpy = LfaaAntenna.numpy = MagicMock()
        # PROTECTED REGION ID(LfaaAntenna.test_mocking) ENABLED START #
        # PROTECTED REGION END #    //  LfaaAntenna.test_mocking

    def test_properties(self):
        # test the properties
        # PROTECTED REGION ID(LfaaAntenna.test_properties) ENABLED START #
        # PROTECTED REGION END #    //  LfaaAntenna.test_properties
        pass

    def test_State(self):
        """Test for State"""
        # PROTECTED REGION ID(LfaaAntenna.test_State) ENABLED START #
        self.device.State()
        # PROTECTED REGION END #    //  LfaaAntenna.test_State

    def test_Status(self):
        """Test for Status"""
        # PROTECTED REGION ID(LfaaAntenna.test_Status) ENABLED START #
        self.device.Status()
        # PROTECTED REGION END #    //  LfaaAntenna.test_Status

    def test_PowerOn(self):
        """Test for PowerOn"""
        # PROTECTED REGION ID(LfaaAntenna.test_PowerOn) ENABLED START #
        self.device.PowerOn()
        # PROTECTED REGION END #    //  LfaaAntenna.test_PowerOn

    def test_PowerOff(self):
        """Test for PowerOff"""
        # PROTECTED REGION ID(LfaaAntenna.test_PowerOff) ENABLED START #
        self.device.PowerOff()
        # PROTECTED REGION END #    //  LfaaAntenna.test_PowerOff

    def test_antennaId(self):
        """Test for antennaId"""
        # PROTECTED REGION ID(LfaaAntenna.test_antennaId) ENABLED START #
        self.device.antennaId
        # PROTECTED REGION END #    //  LfaaAntenna.test_antennaId

    def test_logicalTpmAntenna_id(self):
        """Test for logicalTpmAntenna_id"""
        # PROTECTED REGION ID(LfaaAntenna.test_logicalTpmAntenna_id) ENABLED START #
        self.device.logicalTpmAntenna_id
        # PROTECTED REGION END #    //  LfaaAntenna.test_logicalTpmAntenna_id

    def test_logicalApiuAntenna_id(self):
        """Test for logicalApiuAntenna_id"""
        # PROTECTED REGION ID(LfaaAntenna.test_logicalApiuAntenna_id) ENABLED START #
        self.device.logicalApiuAntenna_id
        # PROTECTED REGION END #    //  LfaaAntenna.test_logicalApiuAntenna_id

    def test_tpmId(self):
        """Test for tpmId"""
        # PROTECTED REGION ID(LfaaAntenna.test_tpmId) ENABLED START #
        self.device.tpmId
        # PROTECTED REGION END #    //  LfaaAntenna.test_tpmId

    def test_apiuId(self):
        """Test for apiuId"""
        # PROTECTED REGION ID(LfaaAntenna.test_apiuId) ENABLED START #
        self.device.apiuId
        # PROTECTED REGION END #    //  LfaaAntenna.test_apiuId

    def test_gain(self):
        """Test for gain"""
        # PROTECTED REGION ID(LfaaAntenna.test_gain) ENABLED START #
        self.device.gain
        # PROTECTED REGION END #    //  LfaaAntenna.test_gain

    def test_rms(self):
        """Test for rms"""
        # PROTECTED REGION ID(LfaaAntenna.test_rms) ENABLED START #
        self.device.rms
        # PROTECTED REGION END #    //  LfaaAntenna.test_rms

    def test_voltage(self):
        """Test for voltage"""
        # PROTECTED REGION ID(LfaaAntenna.test_voltage) ENABLED START #
        self.device.voltage
        # PROTECTED REGION END #    //  LfaaAntenna.test_voltage

    def test_temperature(self):
        """Test for temperature"""
        # PROTECTED REGION ID(LfaaAntenna.test_temperature) ENABLED START #
        self.device.temperature
        # PROTECTED REGION END #    //  LfaaAntenna.test_temperature

    def test_xPolarisationFaulty(self):
        """Test for xPolarisationFaulty"""
        # PROTECTED REGION ID(LfaaAntenna.test_xPolarisationFaulty) ENABLED START #
        self.device.xPolarisationFaulty
        # PROTECTED REGION END #    //  LfaaAntenna.test_xPolarisationFaulty

    def test_yPolarisationFaulty(self):
        """Test for yPolarisationFaulty"""
        # PROTECTED REGION ID(LfaaAntenna.test_yPolarisationFaulty) ENABLED START #
        self.device.yPolarisationFaulty
        # PROTECTED REGION END #    //  LfaaAntenna.test_yPolarisationFaulty

    def test_fieldNodeLongitude(self):
        """Test for fieldNodeLongitude"""
        # PROTECTED REGION ID(LfaaAntenna.test_fieldNodeLongitude) ENABLED START #
        self.device.fieldNodeLongitude
        # PROTECTED REGION END #    //  LfaaAntenna.test_fieldNodeLongitude

    def test_fieldNodeLatitude(self):
        """Test for fieldNodeLatitude"""
        # PROTECTED REGION ID(LfaaAntenna.test_fieldNodeLatitude) ENABLED START #
        self.device.fieldNodeLatitude
        # PROTECTED REGION END #    //  LfaaAntenna.test_fieldNodeLatitude

    def test_altitude(self):
        """Test for altitude"""
        # PROTECTED REGION ID(LfaaAntenna.test_altitude) ENABLED START #
        self.device.altitude
        # PROTECTED REGION END #    //  LfaaAntenna.test_altitude

    def test_xDisplacement(self):
        """Test for xDisplacement"""
        # PROTECTED REGION ID(LfaaAntenna.test_xDisplacement) ENABLED START #
        self.device.xDisplacement
        # PROTECTED REGION END #    //  LfaaAntenna.test_xDisplacement

    def test_yDisplacement(self):
        """Test for yDisplacement"""
        # PROTECTED REGION ID(LfaaAntenna.test_yDisplacement) ENABLED START #
        self.device.yDisplacement
        # PROTECTED REGION END #    //  LfaaAntenna.test_yDisplacement

    def test_timestampOfLastSpectrum(self):
        """Test for timestampOfLastSpectrum"""
        # PROTECTED REGION ID(LfaaAntenna.test_timestampOfLastSpectrum) ENABLED START #
        self.device.timestampOfLastSpectrum
        # PROTECTED REGION END #    //  LfaaAntenna.test_timestampOfLastSpectrum

    def test_xPolarisationScalingFactor(self):
        """Test for xPolarisationScalingFactor"""
        # PROTECTED REGION ID(LfaaAntenna.test_xPolarisationScalingFactor) ENABLED START #
        self.device.xPolarisationScalingFactor
        # PROTECTED REGION END #    //  LfaaAntenna.test_xPolarisationScalingFactor

    def test_yPolarisationScalingFactor(self):
        """Test for yPolarisationScalingFactor"""
        # PROTECTED REGION ID(LfaaAntenna.test_yPolarisationScalingFactor) ENABLED START #
        self.device.yPolarisationScalingFactor
        # PROTECTED REGION END #    //  LfaaAntenna.test_yPolarisationScalingFactor

    def test_calibrationCoefficient(self):
        """Test for calibrationCoefficient"""
        # PROTECTED REGION ID(LfaaAntenna.test_calibrationCoefficient) ENABLED START #
        self.device.calibrationCoefficient
        # PROTECTED REGION END #    //  LfaaAntenna.test_calibrationCoefficient

    def test_pointingCoefficient(self):
        """Test for pointingCoefficient"""
        # PROTECTED REGION ID(LfaaAntenna.test_pointingCoefficient) ENABLED START #
        self.device.pointingCoefficient
        # PROTECTED REGION END #    //  LfaaAntenna.test_pointingCoefficient

    def test_spectrumX(self):
        """Test for spectrumX"""
        # PROTECTED REGION ID(LfaaAntenna.test_spectrumX) ENABLED START #
        self.device.spectrumX
        # PROTECTED REGION END #    //  LfaaAntenna.test_spectrumX

    def test_spectrumY(self):
        """Test for spectrumY"""
        # PROTECTED REGION ID(LfaaAntenna.test_spectrumY) ENABLED START #
        self.device.spectrumY
        # PROTECTED REGION END #    //  LfaaAntenna.test_spectrumY

    def test_position(self):
        """Test for position"""
        # PROTECTED REGION ID(LfaaAntenna.test_position) ENABLED START #
        self.device.position
        # PROTECTED REGION END #    //  LfaaAntenna.test_position


# Main execution
if __name__ == "__main__":
    main()
