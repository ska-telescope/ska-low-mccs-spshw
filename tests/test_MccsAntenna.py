#########################################################################
# !/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of the MccsAntenna project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
#########################################################################
"""Contain the tests for the SKA MCCS Antenna Device Server."""

# Imports
from tango import DevState
from ska.base.control_model import AdminMode, ControlMode, HealthState, LoggingLevel


class TestMccsAntenna(object):
    """Test case for Antenna DS."""

    properties = {
        "SkaLevel": "4",
        "GroupDefinitions": "",
        "LoggingLevelDefault": "4",
        "LoggingTargetsDefault": "",
    }

    def test_properties(self, tango_device):
        """Test the properties """
        assert tango_device.loggingLevel == LoggingLevel.INFO

    def test_State(self, tango_device):
        """Test for State"""
        assert tango_device.state() == DevState.ON

    def test_Status(self, tango_device):
        """Test for Status"""
        assert tango_device.status() == "The device is in ON state."

    def test_PowerOn(self, tango_device):
        """Test for PowerOn"""
        assert tango_device.PowerOn() is None

    def test_PowerOff(self, tango_device):
        """Test for PowerOff"""
        assert tango_device.PowerOff() is None

    def test_Reset(self, tango_device):
        """Test for Reset"""
        assert tango_device.Reset() is None

    def test_antennaId(self, tango_device):
        """Test for antennaId"""
        assert tango_device.antennaId == 0

    def test_logicalTpmAntenna_id(self, tango_device):
        """Test for logicalTpmAntenna_id"""
        assert tango_device.logicalTpmAntenna_id == 0

    def test_logicalApiuAntenna_id(self, tango_device):
        """Test for logicalApiuAntenna_id"""
        assert tango_device.logicalApiuAntenna_id == 0.0

    def test_tpmId(self, tango_device):
        """Test for tpmId"""
        assert tango_device.tpmId == 0.0

    def test_apiuId(self, tango_device):
        """Test for apiuId"""
        assert tango_device.apiuId == 0.0

    def test_gain(self, tango_device):
        """Test for gain"""
        assert tango_device.gain == 0.0

    def test_rms(self, tango_device):
        """Test for rms"""
        assert tango_device.rms == 0.0

    def test_voltage(self, tango_device):
        """Test for voltage"""
        assert tango_device.voltage == 0.0

    def test_temperature(self, tango_device):
        """Test for temperature"""
        assert tango_device.temperature == 0.0

    def test_xPolarisationFaulty(self, tango_device):
        """Test for xPolarisationFaulty"""
        assert tango_device.xPolarisationFaulty is False

    def test_yPolarisationFaulty(self, tango_device):
        """Test for yPolarisationFaulty"""
        assert tango_device.yPolarisationFaulty is False

    def test_fieldNodeLongitude(self, tango_device):
        """Test for fieldNodeLongitude"""
        assert tango_device.fieldNodeLongitude == 0.0

    def test_fieldNodeLatitude(self, tango_device):
        """Test for fieldNodeLatitude"""
        assert tango_device.fieldNodeLatitude == 0.0

    def test_altitude(self, tango_device):
        """Test for altitude"""
        assert tango_device.altitude == 0.0

    def test_xDisplacement(self, tango_device):
        """Test for xDisplacement"""
        assert tango_device.xDisplacement == 0.0

    def test_yDisplacement(self, tango_device):
        """Test for yDisplacement"""
        assert tango_device.yDisplacement == 0.0

    def test_timestampOfLastSpectrum(self, tango_device):
        """Test for timestampOfLastSpectrum"""
        assert tango_device.timestampOfLastSpectrum == ""

    def test_loggingLevel(self, tango_device):
        """Test for loggingLevel"""
        assert tango_device.loggingLevel == 4

    def test_healthState(self, tango_device):
        """Test for healthState"""
        assert tango_device.healthState == HealthState.OK

    def test_adminMode(self, tango_device):
        """Test for adminMode"""
        assert tango_device.adminMode == AdminMode.ONLINE

    def test_controlMode(self, tango_device):
        """Test for controlMode"""
        assert tango_device.controlMode == ControlMode.REMOTE

    def test_simulationMode(self, tango_device):
        """Test for simulationMode"""
        assert tango_device.SimulationMode == 0  # Equates to False

    def test_logicalAntennaId(self, tango_device):
        """Test for logicalAntennaId"""
        assert tango_device.logicalAntennaId == 0

    def test_xPolarisationScalingFactor(self, tango_device):
        """Test for xPolarisationScalingFactor"""
        assert list(tango_device.xPolarisationScalingFactor) == [0]

    def test_yPolarisationScalingFactor(self, tango_device):
        """Test for yPolarisationScalingFactor"""
        assert list(tango_device.yPolarisationScalingFactor) == [0]

    def test_calibrationCoefficient(self, tango_device):
        """Test for calibrationCoefficient"""
        assert list(tango_device.calibrationCoefficient) == [0.0]

    def test_pointingCoefficient(self, tango_device):
        """Test for pointingCoefficient"""
        assert list(tango_device.pointingCoefficient) == [0.0]

    def test_spectrumX(self, tango_device):
        """Test for spectrumX"""
        assert list(tango_device.spectrumX) == [0.0]

    def test_spectrumY(self, tango_device):
        """Test for spectrumY"""
        assert list(tango_device.spectrumY) == [0.0]

    def test_position(self, tango_device):
        """Test for position"""
        assert list(tango_device.position) == [0.0]

    def test_loggingTargets(self, tango_device):
        """Test for loggingTargets"""
        assert tango_device.loggingTargets == ('tango::logger',)

    def test_delays(self, tango_device):
        """Test for delays"""
        assert list(tango_device.delays) == [0.0]

    def test_delayRates(self, tango_device):
        """Test for delayRates"""
        assert list(tango_device.delayRates) == [0.0]

    def test_bandpassCoefficient(self, tango_device):
        """Test for bandpassCoefficient"""
        assert list(tango_device.bandpassCoefficient) == [0.0]
