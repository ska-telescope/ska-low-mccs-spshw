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
# import sys
# import os
# path = os.path.join(os.path.dirname(__file__), os.pardir)
# sys.path.insert(0, os.path.abspath(path))

# Imports
import pytest

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
# @pytest.mark.skip(reason="needs to be fixed")
@pytest.mark.usefixtures("tango_context", "initialize_device")
class TestMccsAntenna:
    """Test case for packet generation."""

    properties = {
        "SkaLevel": "4",
        "GroupDefinitions": "",
        "LoggingLevelDefault": "4",
        "LoggingTargetsDefault": "",
    }

    def test_properties(self):
        # test the properties
        pass

    def test_State(self):
        """Test for State"""

        self.device.State()

    def test_Status(self):
        """Test for Status"""

        self.device.Status()

    def test_PowerOn(self):
        """Test for PowerOn"""

        self.device.PowerOn()

    def test_PowerOff(self):
        """Test for PowerOff"""

        self.device.PowerOff()

    def test_GetVersionInfo(self):
        """Test for GetVersionInfo"""

        self.device.GetVersionInfo()

    def test_Reset(self):
        """Test for Reset"""

        self.device.Reset()

    def test_antennaId(self):
        """Test for antennaId"""

        self.device.antennaId

    def test_logicalTpmAntenna_id(self):
        """Test for logicalTpmAntenna_id"""

        self.device.logicalTpmAntenna_id

    def test_logicalApiuAntenna_id(self):
        """Test for logicalApiuAntenna_id"""

        self.device.logicalApiuAntenna_id

    def test_tpmId(self):
        """Test for tpmId"""

        self.device.tpmId

    def test_apiuId(self):
        """Test for apiuId"""

        self.device.apiuId

    def test_gain(self):
        """Test for gain"""

        self.device.gain

    def test_rms(self):
        """Test for rms"""

        self.device.rms

    def test_voltage(self):
        """Test for voltage"""

        self.device.voltage

    def test_temperature(self):
        """Test for temperature"""

        self.device.temperature

    def test_xPolarisationFaulty(self):
        """Test for xPolarisationFaulty"""

        self.device.xPolarisationFaulty

    def test_yPolarisationFaulty(self):
        """Test for yPolarisationFaulty"""

        self.device.yPolarisationFaulty

    def test_fieldNodeLongitude(self):
        """Test for fieldNodeLongitude"""

        self.device.fieldNodeLongitude

    def test_fieldNodeLatitude(self):
        """Test for fieldNodeLatitude"""

        self.device.fieldNodeLatitude

    def test_altitude(self):
        """Test for altitude"""

        self.device.altitude

    def test_xDisplacement(self):
        """Test for xDisplacement"""

        self.device.xDisplacement

    def test_yDisplacement(self):
        """Test for yDisplacement"""

        self.device.yDisplacement

    def test_timestampOfLastSpectrum(self):
        """Test for timestampOfLastSpectrum"""

        self.device.timestampOfLastSpectrum

    def test_buildState(self):
        """Test for buildState"""

        self.device.buildState

    def test_versionId(self):
        """Test for versionId"""

        self.device.versionId

    def test_loggingLevel(self):
        """Test for loggingLevel"""

        self.device.loggingLevel

    def test_healthState(self):
        """Test for healthState"""

        self.device.healthState

    def test_adminMode(self):
        """Test for adminMode"""

        self.device.adminMode

    def test_controlMode(self):
        """Test for controlMode"""

        self.device.controlMode

    def test_simulationMode(self):
        """Test for simulationMode"""

        self.device.simulationMode

    def test_testMode(self):
        """Test for testMode"""

        self.device.testMode

    def test_logicalAntennaId(self):
        """Test for logicalAntennaId"""

        self.device.logicalAntennaId

    def test_xPolarisationScalingFactor(self):
        """Test for xPolarisationScalingFactor"""

        self.device.xPolarisationScalingFactor

    def test_yPolarisationScalingFactor(self):
        """Test for yPolarisationScalingFactor"""

        self.device.yPolarisationScalingFactor

    def test_calibrationCoefficient(self):
        """Test for calibrationCoefficient"""

        self.device.calibrationCoefficient

    def test_pointingCoefficient(self):
        """Test for pointingCoefficient"""

        self.device.pointingCoefficient

    def test_spectrumX(self):
        """Test for spectrumX"""

        self.device.spectrumX

    def test_spectrumY(self):
        """Test for spectrumY"""

        self.device.spectrumY

    def test_position(self):
        """Test for position"""

        self.device.position

    def test_loggingTargets(self):
        """Test for loggingTargets"""

        self.device.loggingTargets

    def test_delays(self):
        """Test for delays"""

        self.device.delays

    def test_delayRates(self):
        """Test for delayRates"""

        self.device.delayRates

    def test_bandpassCoefficient(self):
        """Test for bandpassCoefficient"""

        self.device.bandpassCoefficient
