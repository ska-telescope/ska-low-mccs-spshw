###############################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the MccsStation project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
###############################################################################
"""
This module contains the tests for MccsStation.
"""
import logging
import pytest
import time
import tango

from ska.base import SKABaseDeviceStateModel
from ska.base.commands import CommandError, ResultCode
from ska.base.control_model import ControlMode, HealthState, SimulationMode, TestMode
from ska.low.mccs import MccsStation, release
from ska.low.mccs.station import StationHardwareManager, StationPowerManager


device_to_load = {
    "path": "charts/mccs/data/configuration.json",
    "package": "ska.low.mccs",
    "device": "station001",
}


@pytest.mark.mock_device_proxy
class TestMccsStation:
    """
    Test class for MccsStation tests
    """

    def test_InitDevice(self, device_under_test):
        """
        Test for Initial state.
        A freshly initialised station device has no assigned resources
        """
        assert device_under_test.healthState == HealthState.OK
        assert device_under_test.controlMode == ControlMode.REMOTE
        assert device_under_test.simulationMode == SimulationMode.FALSE
        assert device_under_test.testMode == TestMode.NONE

        # The following reads might not be allowed in this state once properly
        # implemented
        assert device_under_test.subarrayId == 0
        assert device_under_test.transientBufferFQDN == ""
        assert not device_under_test.isCalibrated
        assert not device_under_test.isConfigured
        assert device_under_test.calibrationJobId == 0
        assert device_under_test.daqJobId == 0
        assert device_under_test.dataDirectory == ""
        assert device_under_test.beamFQDNs is None
        assert list(device_under_test.delayCentre) == []
        assert device_under_test.calibrationCoefficients is None

    # overridden base class attributes
    def test_buildState(self, device_under_test):
        """Test for buildState"""
        build_info = release.get_release_info()
        assert device_under_test.buildState == build_info

    # overridden base class commands
    def test_GetVersionInfo(self, device_under_test):
        """Test for GetVersionInfo"""
        version_info = release.get_release_info(device_under_test.info().dev_class)
        assert device_under_test.GetVersionInfo() == [version_info]

    def test_versionId(self, device_under_test):
        """Test for versionId"""
        assert device_under_test.versionId == release.version

    # MccsStation attributes
    def test_subarrayId(self, device_under_test):
        """
        Test for subarrayId attribute
        """
        station = device_under_test  # to make test easier to read
        mock_tile_1 = tango.DeviceProxy("low-mccs/tile/0001")
        mock_tile_2 = tango.DeviceProxy("low-mccs/tile/0002")

        # These tiles are mock devices so we have to manually set their
        # initial states
        mock_tile_1.subarrayId = 0
        mock_tile_2.subarrayId = 0

        # check initial state
        assert station.subarrayId == 0
        assert mock_tile_1.subarrayId == 0
        assert mock_tile_2.subarrayId == 0

        # action under test
        station.subarrayId = 1

        # check
        assert station.subarrayId == 1
        assert mock_tile_1.subarrayId == 1
        assert mock_tile_2.subarrayId == 1

    def test_beamFQDNs(self, device_under_test):
        """Test for beamFQDNs attribute"""
        assert device_under_test.beamFQDNs is None

    def test_transientBufferFQDN(self, device_under_test):
        """Test for transientBufferFQDN attribute"""
        assert device_under_test.transientBufferFQDN == ""

    def test_delayCentre(self, device_under_test):
        """
        Test for delayCentre attribute. This is a messy test because:
        (a) it is a READWRITE attribute, so we want to test that we can write
        to it AND read the value back;
        (b) delayCentre is a polled attribute, so you have to wait a poll
        period in order to read back what you've written; else you just read
        back the cached value
        (c) there is some loss of floating-point precision during transfer, so
        you have to check approximate equality when reading back what you've
        written.

        """
        assert list(device_under_test.delayCentre) == []

        # SETUP
        dummy_location = (-30.72113, 21.411128)
        float_format = "{:3.4f}"
        dummy_location_str = [float_format.format(x) for x in dummy_location]
        sleep_seconds = (
            device_under_test.get_attribute_poll_period("delayCentre") / 1000.0 * 1.2
        )

        # RUN
        device_under_test.delayCentre = dummy_location
        time.sleep(sleep_seconds)
        delay_centre = device_under_test.delayCentre

        # CHECK
        delay_centre_str = [float_format.format(x) for x in delay_centre]
        assert delay_centre_str == dummy_location_str

    def test_calibrationCoefficients(self, device_under_test):
        """Test for calibrationCoefficients attribute"""
        assert device_under_test.calibrationCoefficients is None

    def test_isCalibrated(self, device_under_test):
        """Test for isCalibrated attribute"""
        assert not device_under_test.isCalibrated

    def test_isConfigured(self, device_under_test):
        """Test for isConfigured attribute"""
        assert not device_under_test.isConfigured

    def test_calibrationJobId(self, device_under_test):
        """Teset for calibrationJobId attribute"""
        assert device_under_test.calibrationJobId == 0

    def test_daqJobId(self, device_under_test):
        """Test for daqJobId attributes"""
        assert device_under_test.daqJobId == 0

    def test_dataDirectory(self, device_under_test):
        """Test for dataDirectory attribute"""
        assert device_under_test.dataDirectory == ""


class TestStationPowerManager:
    """
    This class contains tests of the ska.low.mccs.station.StationPowerManager
    class
    """

    @pytest.fixture
    def logger(self):
        """
        Fixture that returns a logger for the power manager under test
        (or its components) to use
        """
        return logging.getLogger()

    @pytest.fixture
    def hardware_manager(self):
        """
        Fixture that returns a hardware manager for the power manager
        under test to use
        """
        return StationHardwareManager()

    @pytest.fixture
    def power_manager(self, hardware_manager):
        """
        Fixture that returns a power manager with no subservient devices

        :param hardware_manager: fixture that returns a hardware manager:
            something that can be turned off and on.
        """
        return StationPowerManager(hardware_manager, [])

    @pytest.fixture
    def state_model(self, logger):
        """
        Fixture that returns a state model for the power manager under
        test to use

        :param logger: a logger for the state model to use
        """
        return SKABaseDeviceStateModel(logger)

    def test_OnCommand(self, power_manager, state_model, logger):
        """
        Test the working of the On command.

        Because the PowerManager and SKABaseDeviceStateModel are thoroughly
        unit-tested elsewhere, here we just need to check that the On
        command drives them correctly. The scope of this test is: check
        that the On command is not allowed to run the state model is
        not in the OFF state; check that such attempts fail with no
        side-effects; check that On() command IS allowed to run when
        the state model is in the OFF state; check that running the
        On() command succeeds, and that the result is the state model
        moves to state ON, and the power manager thinks it is on.
        """
        on_command = MccsStation.OnCommand(power_manager, state_model, logger)
        assert not power_manager.is_on()

        all_states = {
            "UNINITIALISED",
            "FAULT_ENABLED",
            "FAULT_DISABLED",
            "INIT_ENABLED",
            "INIT_DISABLED",
            "DISABLED",
            "OFF",
            "ON",
        }

        # in all states except OFF, the on command is not permitted,
        # should not be allowed, should fail, should have no side-effect
        for state in all_states - {"OFF"}:
            state_model._straight_to_state(state)

            assert not on_command.is_allowed()
            with pytest.raises(CommandError):
                on_command()

            assert not power_manager.is_on()
            assert state_model._state == state

        # now push to OFF, the state in which the On command IS allowed
        state_model._straight_to_state("OFF")
        assert on_command.is_allowed()
        assert on_command() == (ResultCode.OK, "On command completed OK")
        assert power_manager.is_on()
        assert state_model._state == "ON"

    def test_OffCommand(self, power_manager, state_model):
        """
        Test the working of the Off command.

        Because the PowerManager and BaseDeviceStateModel are thoroughly
        unit-tested elsewhere, here we just need to check that the Off
        command drives them correctly. The scope of this test is: check
        that the Off command is not allowed to run if the state model is
        not in the ON state; check that such attempts fail with no
        side-effects; check that Off() command IS allowed to run when
        the state model is in the ON state; check that running the
        Off() command succeeds, and that the result is the state model
        moves to state OFF, and the power manager thinks it is off.
        """
        off_command = MccsStation.OffCommand(power_manager, state_model)
        power_manager.on()
        assert power_manager.is_on()

        all_states = {
            "UNINITIALISED",
            "FAULT_ENABLED",
            "FAULT_DISABLED",
            "INIT_ENABLED",
            "INIT_DISABLED",
            "DISABLED",
            "OFF",
            "ON",
        }

        # in all states except ON, the off command is not permitted,
        # should not be allowed, should fail, should have no side-effect
        for state in all_states - {"ON"}:
            state_model._straight_to_state(state)

            assert not off_command.is_allowed()
            with pytest.raises(CommandError):
                off_command()

            assert power_manager.is_on()
            assert state_model._state == state

        # now push to ON, the state in which the Off command IS allowed
        state_model._straight_to_state("ON")
        assert off_command.is_allowed()
        assert off_command() == (ResultCode.OK, "Off command completed OK")
        assert not power_manager.is_on()
        assert state_model._state == "OFF"
