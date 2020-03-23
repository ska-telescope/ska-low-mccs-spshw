#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of the MccsAntenna project
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
    # PROTECTED REGION ID(MccsAntenna.test_additionnal_import) ENABLED START #
    # PROTECTED REGION END #    //  MccsAntenna.test_additionnal_import
    device = LfaaAntenna
    properties = {'SkaLevel': '4', 'GroupDefinitions': '', 'LoggingLevelDefault': '4', 'LoggingTargetsDefault': '', 
                  }
    empty = None  # Should be []

    @classmethod
    def mocking(cls):
        """Mock external libraries."""
        # Example : Mock numpy
        # cls.numpy = MccsAntenna.numpy = MagicMock()
        # PROTECTED REGION ID(MccsAntenna.test_mocking) ENABLED START #
        # PROTECTED REGION END #    //  MccsAntenna.test_mocking

    def test_properties(self):
        # test the properties
        # PROTECTED REGION ID(MccsAntenna.test_properties) ENABLED START #
        # PROTECTED REGION END #    //  MccsAntenna.test_properties
        pass

    def test_State(self):
        """Test for State"""
        # PROTECTED REGION ID(MccsAntenna.test_State) ENABLED START #
        self.device.State()
        # PROTECTED REGION END #    //  MccsAntenna.test_State

    def test_Status(self):
        """Test for Status"""
        # PROTECTED REGION ID(MccsAntenna.test_Status) ENABLED START #
        self.device.Status()
        # PROTECTED REGION END #    //  MccsAntenna.test_Status

    def test_PowerOn(self):
        """Test for PowerOn"""
        # PROTECTED REGION ID(MccsAntenna.test_PowerOn) ENABLED START #
        self.device.PowerOn()
        # PROTECTED REGION END #    //  MccsAntenna.test_PowerOn

    def test_PowerOff(self):
        """Test for PowerOff"""
        # PROTECTED REGION ID(MccsAntenna.test_PowerOff) ENABLED START #
        self.device.PowerOff()
        # PROTECTED REGION END #    //  MccsAntenna.test_PowerOff

    def test_GetVersionInfo(self):
        """Test for GetVersionInfo"""
        # PROTECTED REGION ID(MccsAntenna.test_GetVersionInfo) ENABLED START #
        self.device.GetVersionInfo()
        # PROTECTED REGION END #    //  MccsAntenna.test_GetVersionInfo

    def test_Reset(self):
        """Test for Reset"""
        # PROTECTED REGION ID(MccsAntenna.test_Reset) ENABLED START #
        self.device.Reset()
        # PROTECTED REGION END #    //  MccsAntenna.test_Reset

    def test_antennaId(self):
        """Test for antennaId"""
        # PROTECTED REGION ID(MccsAntenna.test_antennaId) ENABLED START #
        self.device.antennaId
        # PROTECTED REGION END #    //  MccsAntenna.test_antennaId

    def test_logicalTpmAntenna_id(self):
        """Test for logicalTpmAntenna_id"""
        # PROTECTED REGION ID(MccsAntenna.test_logicalTpmAntenna_id) ENABLED START #
        self.device.logicalTpmAntenna_id
        # PROTECTED REGION END #    //  MccsAntenna.test_logicalTpmAntenna_id

    def test_logicalApiuAntenna_id(self):
        """Test for logicalApiuAntenna_id"""
        # PROTECTED REGION ID(MccsAntenna.test_logicalApiuAntenna_id) ENABLED START #
        self.device.logicalApiuAntenna_id
        # PROTECTED REGION END #    //  MccsAntenna.test_logicalApiuAntenna_id

    def test_tpmId(self):
        """Test for tpmId"""
        # PROTECTED REGION ID(MccsAntenna.test_tpmId) ENABLED START #
        self.device.tpmId
        # PROTECTED REGION END #    //  MccsAntenna.test_tpmId

    def test_apiuId(self):
        """Test for apiuId"""
        # PROTECTED REGION ID(MccsAntenna.test_apiuId) ENABLED START #
        self.device.apiuId
        # PROTECTED REGION END #    //  MccsAntenna.test_apiuId

    def test_gain(self):
        """Test for gain"""
        # PROTECTED REGION ID(MccsAntenna.test_gain) ENABLED START #
        self.device.gain
        # PROTECTED REGION END #    //  MccsAntenna.test_gain

    def test_rms(self):
        """Test for rms"""
        # PROTECTED REGION ID(MccsAntenna.test_rms) ENABLED START #
        self.device.rms
        # PROTECTED REGION END #    //  MccsAntenna.test_rms

    def test_voltage(self):
        """Test for voltage"""
        # PROTECTED REGION ID(MccsAntenna.test_voltage) ENABLED START #
        self.device.voltage
        # PROTECTED REGION END #    //  MccsAntenna.test_voltage

    def test_temperature(self):
        """Test for temperature"""
        # PROTECTED REGION ID(MccsAntenna.test_temperature) ENABLED START #
        self.device.temperature
        # PROTECTED REGION END #    //  MccsAntenna.test_temperature

    def test_xPolarisationFaulty(self):
        """Test for xPolarisationFaulty"""
        # PROTECTED REGION ID(MccsAntenna.test_xPolarisationFaulty) ENABLED START #
        self.device.xPolarisationFaulty
        # PROTECTED REGION END #    //  MccsAntenna.test_xPolarisationFaulty

    def test_yPolarisationFaulty(self):
        """Test for yPolarisationFaulty"""
        # PROTECTED REGION ID(MccsAntenna.test_yPolarisationFaulty) ENABLED START #
        self.device.yPolarisationFaulty
        # PROTECTED REGION END #    //  MccsAntenna.test_yPolarisationFaulty

    def test_fieldNodeLongitude(self):
        """Test for fieldNodeLongitude"""
        # PROTECTED REGION ID(MccsAntenna.test_fieldNodeLongitude) ENABLED START #
        self.device.fieldNodeLongitude
        # PROTECTED REGION END #    //  MccsAntenna.test_fieldNodeLongitude

    def test_fieldNodeLatitude(self):
        """Test for fieldNodeLatitude"""
        # PROTECTED REGION ID(MccsAntenna.test_fieldNodeLatitude) ENABLED START #
        self.device.fieldNodeLatitude
        # PROTECTED REGION END #    //  MccsAntenna.test_fieldNodeLatitude

    def test_altitude(self):
        """Test for altitude"""
        # PROTECTED REGION ID(MccsAntenna.test_altitude) ENABLED START #
        self.device.altitude
        # PROTECTED REGION END #    //  MccsAntenna.test_altitude

    def test_xDisplacement(self):
        """Test for xDisplacement"""
        # PROTECTED REGION ID(MccsAntenna.test_xDisplacement) ENABLED START #
        self.device.xDisplacement
        # PROTECTED REGION END #    //  MccsAntenna.test_xDisplacement

    def test_yDisplacement(self):
        """Test for yDisplacement"""
        # PROTECTED REGION ID(MccsAntenna.test_yDisplacement) ENABLED START #
        self.device.yDisplacement
        # PROTECTED REGION END #    //  MccsAntenna.test_yDisplacement

    def test_timestampOfLastSpectrum(self):
        """Test for timestampOfLastSpectrum"""
        # PROTECTED REGION ID(MccsAntenna.test_timestampOfLastSpectrum) ENABLED START #
        self.device.timestampOfLastSpectrum
        # PROTECTED REGION END #    //  MccsAntenna.test_timestampOfLastSpectrum

    def test_buildState(self):
        """Test for buildState"""
        # PROTECTED REGION ID(MccsAntenna.test_buildState) ENABLED START #
        self.device.buildState
        # PROTECTED REGION END #    //  MccsAntenna.test_buildState

    def test_versionId(self):
        """Test for versionId"""
        # PROTECTED REGION ID(MccsAntenna.test_versionId) ENABLED START #
        self.device.versionId
        # PROTECTED REGION END #    //  MccsAntenna.test_versionId

    def test_loggingLevel(self):
        """Test for loggingLevel"""
        # PROTECTED REGION ID(MccsAntenna.test_loggingLevel) ENABLED START #
        self.device.loggingLevel
        # PROTECTED REGION END #    //  MccsAntenna.test_loggingLevel

    def test_healthState(self):
        """Test for healthState"""
        # PROTECTED REGION ID(MccsAntenna.test_healthState) ENABLED START #
        self.device.healthState
        # PROTECTED REGION END #    //  MccsAntenna.test_healthState

    def test_adminMode(self):
        """Test for adminMode"""
        # PROTECTED REGION ID(MccsAntenna.test_adminMode) ENABLED START #
        self.device.adminMode
        # PROTECTED REGION END #    //  MccsAntenna.test_adminMode

    def test_controlMode(self):
        """Test for controlMode"""
        # PROTECTED REGION ID(MccsAntenna.test_controlMode) ENABLED START #
        self.device.controlMode
        # PROTECTED REGION END #    //  MccsAntenna.test_controlMode

    def test_simulationMode(self):
        """Test for simulationMode"""
        # PROTECTED REGION ID(MccsAntenna.test_simulationMode) ENABLED START #
        self.device.simulationMode
        # PROTECTED REGION END #    //  MccsAntenna.test_simulationMode

    def test_testMode(self):
        """Test for testMode"""
        # PROTECTED REGION ID(MccsAntenna.test_testMode) ENABLED START #
        self.device.testMode
        # PROTECTED REGION END #    //  MccsAntenna.test_testMode

    def test_logicalAntennaId(self):
        """Test for logicalAntennaId"""
        # PROTECTED REGION ID(MccsAntenna.test_logicalAntennaId) ENABLED START #
        self.device.logicalAntennaId
        # PROTECTED REGION END #    //  MccsAntenna.test_logicalAntennaId

    def test_xPolarisationScalingFactor(self):
        """Test for xPolarisationScalingFactor"""
        # PROTECTED REGION ID(MccsAntenna.test_xPolarisationScalingFactor) ENABLED START #
        self.device.xPolarisationScalingFactor
        # PROTECTED REGION END #    //  MccsAntenna.test_xPolarisationScalingFactor

    def test_yPolarisationScalingFactor(self):
        """Test for yPolarisationScalingFactor"""
        # PROTECTED REGION ID(MccsAntenna.test_yPolarisationScalingFactor) ENABLED START #
        self.device.yPolarisationScalingFactor
        # PROTECTED REGION END #    //  MccsAntenna.test_yPolarisationScalingFactor

    def test_calibrationCoefficient(self):
        """Test for calibrationCoefficient"""
        # PROTECTED REGION ID(MccsAntenna.test_calibrationCoefficient) ENABLED START #
        self.device.calibrationCoefficient
        # PROTECTED REGION END #    //  MccsAntenna.test_calibrationCoefficient

    def test_pointingCoefficient(self):
        """Test for pointingCoefficient"""
        # PROTECTED REGION ID(MccsAntenna.test_pointingCoefficient) ENABLED START #
        self.device.pointingCoefficient
        # PROTECTED REGION END #    //  MccsAntenna.test_pointingCoefficient

    def test_spectrumX(self):
        """Test for spectrumX"""
        # PROTECTED REGION ID(MccsAntenna.test_spectrumX) ENABLED START #
        self.device.spectrumX
        # PROTECTED REGION END #    //  MccsAntenna.test_spectrumX

    def test_spectrumY(self):
        """Test for spectrumY"""
        # PROTECTED REGION ID(MccsAntenna.test_spectrumY) ENABLED START #
        self.device.spectrumY
        # PROTECTED REGION END #    //  MccsAntenna.test_spectrumY

    def test_position(self):
        """Test for position"""
        # PROTECTED REGION ID(MccsAntenna.test_position) ENABLED START #
        self.device.position
        # PROTECTED REGION END #    //  MccsAntenna.test_position

    def test_loggingTargets(self):
        """Test for loggingTargets"""
        # PROTECTED REGION ID(MccsAntenna.test_loggingTargets) ENABLED START #
        self.device.loggingTargets
        # PROTECTED REGION END #    //  MccsAntenna.test_loggingTargets

    def test_delays(self):
        """Test for delays"""
        # PROTECTED REGION ID(MccsAntenna.test_delays) ENABLED START #
        self.device.delays
        # PROTECTED REGION END #    //  MccsAntenna.test_delays

    def test_delayRates(self):
        """Test for delayRates"""
        # PROTECTED REGION ID(MccsAntenna.test_delayRates) ENABLED START #
        self.device.delayRates
        # PROTECTED REGION END #    //  MccsAntenna.test_delayRates

    def test_bandpassCoefficient(self):
        """Test for bandpassCoefficient"""
        # PROTECTED REGION ID(MccsAntenna.test_bandpassCoefficient) ENABLED START #
        self.device.bandpassCoefficient
        # PROTECTED REGION END #    //  MccsAntenna.test_bandpassCoefficient


# Main execution
if __name__ == "__main__":
    main()
