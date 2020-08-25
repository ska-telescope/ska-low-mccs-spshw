#########################################################################
# !/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of the SKA-Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
#########################################################################
"""
This module contains the tests for the MccsAntenna.
"""
import time
import pytest
import tango

from ska.base.control_model import (
    ControlMode,
    TestMode,
    SimulationMode,
    HealthState,
    LoggingLevel,
)
from ska.low.mccs import MccsAntenna
from ska.base.commands import ResultCode


device_info = {
    "class": MccsAntenna,
    "properties": {
        "SkaLevel": "4",
        "GroupDefinitions": "",
        "LoggingLevelDefault": "4",
        # "LoggingTargetsDefault": "",
    },
}


class TestMccsAntenna(object):
    """
    Test class for MccsAntenna tests.
    """

    def test_PowerOn(self, device_under_test):
        """Test for PowerOn"""
        (result, info) = device_under_test.PowerOn()
        assert result == ResultCode.OK

    def test_PowerOff(self, device_under_test):
        """Test for PowerOff"""
        (result, info) = device_under_test.PowerOff()
        assert result == ResultCode.OK

    def test_Reset(self, device_under_test):
        """
        Test for Reset.
        Expected to fail as can't reset in the Off state
        """
        with pytest.raises(tango.DevFailed):
            device_under_test.Reset()

    def test_antennaId(self, device_under_test):
        """Test for antennaId"""
        assert device_under_test.antennaId == 0

    def test_logicalTpmAntenna_id(self, device_under_test):
        """Test for logicalTpmAntenna_id"""
        assert device_under_test.logicalTpmAntenna_id == 0

    def test_logicalApiuAntenna_id(self, device_under_test):
        """Test for logicalApiuAntenna_id"""
        assert device_under_test.logicalApiuAntenna_id == 0.0

    def test_tpmId(self, device_under_test):
        """Test for tpmId"""
        assert device_under_test.tpmId == 0.0

    def test_apiuId(self, device_under_test):
        """Test for apiuId"""
        assert device_under_test.apiuId == 0.0

    def test_gain(self, device_under_test):
        """Test for gain"""
        assert device_under_test.gain == 0.0

    def test_rms(self, device_under_test):
        """Test for rms"""
        assert device_under_test.rms == 0.0

    def test_voltage(self, device_under_test):
        """Test for voltage"""
        # device_under_test.testMode = TestMode.NONE
        time.sleep(1.1)
        assert device_under_test.voltage == 3.5

    def test_temperature(self, device_under_test):
        """Test for temperature"""
        # device_under_test.testMode = TestMode.NONE
        time.sleep(1.1)
        assert device_under_test.temperature == 20.6

    def test_xPolarisationFaulty(self, device_under_test):
        """Test for xPolarisationFaulty"""
        assert device_under_test.xPolarisationFaulty is False

    def test_yPolarisationFaulty(self, device_under_test):
        """Test for yPolarisationFaulty"""
        assert device_under_test.yPolarisationFaulty is False

    def test_fieldNodeLongitude(self, device_under_test):
        """Test for fieldNodeLongitude"""
        assert device_under_test.fieldNodeLongitude == 0.0

    def test_fieldNodeLatitude(self, device_under_test):
        """Test for fieldNodeLatitude"""
        assert device_under_test.fieldNodeLatitude == 0.0

    def test_altitude(self, device_under_test):
        """Test for altitude"""
        assert device_under_test.altitude == 0.0

    def test_xDisplacement(self, device_under_test):
        """Test for xDisplacement"""
        assert device_under_test.xDisplacement == 0.0

    def test_yDisplacement(self, device_under_test):
        """Test for yDisplacement"""
        assert device_under_test.yDisplacement == 0.0

    def test_timestampOfLastSpectrum(self, device_under_test):
        """Test for timestampOfLastSpectrum"""
        assert device_under_test.timestampOfLastSpectrum == ""

    def test_loggingLevel(self, device_under_test):
        """Test for loggingLevel"""
        assert device_under_test.loggingLevel == 4

    def test_healthState(self, device_under_test):
        """Test for healthState"""
        assert device_under_test.healthState == HealthState.OK

    def test_controlMode(self, device_under_test):
        """Test for controlMode"""
        assert device_under_test.controlMode == ControlMode.REMOTE

    def test_simulationMode(self, device_under_test):
        """Test for simulationMode"""
        assert device_under_test.SimulationMode == SimulationMode.FALSE

    def test_logicalAntennaId(self, device_under_test):
        """Test for logicalAntennaId"""
        assert device_under_test.logicalAntennaId == 0

    def test_xPolarisationScalingFactor(self, device_under_test):
        """Test for xPolarisationScalingFactor"""
        assert list(device_under_test.xPolarisationScalingFactor) == [0]

    def test_yPolarisationScalingFactor(self, device_under_test):
        """Test for yPolarisationScalingFactor"""
        assert list(device_under_test.yPolarisationScalingFactor) == [0]

    def test_calibrationCoefficient(self, device_under_test):
        """Test for calibrationCoefficient"""
        assert list(device_under_test.calibrationCoefficient) == [0.0]

    def test_pointingCoefficient(self, device_under_test):
        """Test for pointingCoefficient"""
        assert list(device_under_test.pointingCoefficient) == [0.0]

    def test_spectrumX(self, device_under_test):
        """Test for spectrumX"""
        assert list(device_under_test.spectrumX) == [0.0]

    def test_spectrumY(self, device_under_test):
        """Test for spectrumY"""
        assert list(device_under_test.spectrumY) == [0.0]

    def test_position(self, device_under_test):
        """Test for position"""
        assert list(device_under_test.position) == [0.0]

    def test_loggingTargets(self, device_under_test):
        """Test for loggingTargets"""
        assert device_under_test.loggingTargets == ("tango::logger",)

    def test_delays(self, device_under_test):
        """Test for delays"""
        assert list(device_under_test.delays) == [0.0]

    def test_delayRates(self, device_under_test):
        """Test for delayRates"""
        assert list(device_under_test.delayRates) == [0.0]

    def test_bandpassCoefficient(self, device_under_test):
        """Test for bandpassCoefficient"""
        assert list(device_under_test.bandpassCoefficient) == [0.0]
