###############################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
###############################################################################
"""
This module contains the tests for MccsStation.
"""
import json
import threading
import time

import pytest
import tango
from tango import DevState

from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import (
    AdminMode,
    ControlMode,
    HealthState,
    SimulationMode,
    TestMode,
)
from ska_low_mccs import MccsDeviceProxy, MccsStation, release

from testing.harness.mock import MockDeviceBuilder


@pytest.fixture()
def device_to_load():
    """
    Fixture that specifies the device to be loaded for testing.

    :return: specification of the device to be loaded
    :rtype: dict
    """
    return {
        "path": "charts/ska-low-mccs/data/configuration.json",
        "package": "ska_low_mccs",
        "device": "station_001",
        "proxy": MccsDeviceProxy,
    }


@pytest.fixture()
def mock_factory(mocker):
    """
    Fixture that provides a mock factory for device proxy mocks. This
    default factory provides vanilla mocks, but this fixture can be
    overridden by test modules/classes to provide mocks with specified
    behaviours.

    :param mocker: the pytest `mocker` fixture is a wrapper around the
        `unittest.mock` package
    :type mocker: :py:class:`pytest_mock.mocker`

    :return: a factory for device proxy mocks
    :rtype: :py:class:`unittest.mock.Mock` (the class itself, not an
        instance)
    """
    builder = MockDeviceBuilder()
    builder.add_attribute("healthState", HealthState.UNKNOWN)
    builder.add_attribute("adminMode", AdminMode.ONLINE)
    builder.add_result_command("On", ResultCode.OK)
    return builder


class TestMccsStation:
    """
    Test class for MccsStation tests.
    """

    @pytest.fixture()
    def device_under_test(self, tango_harness):
        """
        Fixture that returns the device under test.

        :param tango_harness: a test harness for Tango devices

        :return: the device under test
        """
        return tango_harness.get_device("low-mccs/station/001")

    def test_InitDevice(self, device_under_test, dummy_json_args):
        """
        Test for Initial state. A freshly initialised station device has
        no assigned resources.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param dummy_json_args: dummy json encoded arguments
        :type dummy_json_args: str
        """
        assert device_under_test.healthState == HealthState.UNKNOWN
        assert device_under_test.controlMode == ControlMode.REMOTE
        assert device_under_test.simulationMode == SimulationMode.FALSE
        assert device_under_test.testMode == TestMode.TEST

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

        # check that initialisation leaves us in a state where turning
        # the device on doesn't put it into ALARM state
        device_under_test.On(dummy_json_args)

        def check_device_state(device, state):
            """
            Helper to check that the device is in the expected state
            with a timeout.

            :param device: the devices to check
            :type device: dict
            :param state: the state the device is expected to be in
            :type state: list(:py:class:`tango.DevState`)
            """
            count = 0.0
            while device.State() != state and count < 3.0:
                count += 0.1
                time.sleep(0.1)
            assert device.State() == state

        check_device_state(device_under_test, DevState.ON)
        time.sleep(0.2)
        check_device_state(device_under_test, DevState.ON)

    def test_healthState(self, device_under_test, mock_callback):
        """
        Test for healthState.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param mock_callback: a mock to pass as a callback
        :type mock_callback: :py:class:`unittest.mock.Mock`
        """

        # The device has subscribed to healthState change events on
        # its subsidiary, but hasn't heard from them (because in unit
        # testing these devices are mocked out), so its healthState is
        # UNKNOWN
        assert device_under_test.healthState == HealthState.UNKNOWN

        _ = device_under_test.subscribe_event(
            "healthState", tango.EventType.CHANGE_EVENT, mock_callback
        )
        mock_callback.assert_called_once()

        event_data = mock_callback.call_args[0][0].attr_value
        assert event_data.name == "healthState"
        assert event_data.value == HealthState.UNKNOWN
        assert event_data.quality == tango.AttrQuality.ATTR_VALID

        mock_callback.reset_mock()

    # overridden base class attributes
    def test_buildState(self, device_under_test):
        """
        Test for buildState.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        build_info = release.get_release_info()
        assert device_under_test.buildState == build_info

    # overridden base class commands
    def test_GetVersionInfo(self, device_under_test):
        """
        Test for GetVersionInfo.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        version_info = release.get_release_info(device_under_test.info().dev_class)
        assert device_under_test.GetVersionInfo() == [version_info]

    def test_versionId(self, device_under_test):
        """
        Test for versionId.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.versionId == release.version

    # MccsStation attributes
    def test_subarrayId(self, device_under_test, logger):
        """
        Test for subarrayId attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param logger: the logger to be used by the object under test
        :type logger: :py:class:`logging.Logger`
        """
        station = device_under_test  # to make test easier to read
        mock_tile_1 = MccsDeviceProxy("low-mccs/tile/0001", logger)
        mock_tile_2 = MccsDeviceProxy("low-mccs/tile/0002", logger)

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
        """
        Test for beamFQDNs attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.beamFQDNs is None

    def test_transientBufferFQDN(self, device_under_test):
        """
        Test for transientBufferFQDN attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.transientBufferFQDN == ""

    def test_delayCentre(self, device_under_test):
        """
        Test for delayCentre attribute. This is a messy test because
        there is some loss of floating-point precision during transfer,
        so you have to check approximate equality when reading back what
        you've written.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert list(device_under_test.delayCentre) == []

        # SETUP
        dummy_location = (-30.72113, 21.411128)
        float_format = "{:3.4f}"
        dummy_location_str = [float_format.format(x) for x in dummy_location]

        # RUN
        device_under_test.delayCentre = dummy_location
        delay_centre = device_under_test.delayCentre

        # CHECK
        delay_centre_str = [float_format.format(x) for x in delay_centre]
        assert delay_centre_str == dummy_location_str

    def test_calibrationCoefficients(self, device_under_test):
        """
        Test for calibrationCoefficients attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.calibrationCoefficients is None

    def test_isCalibrated(self, device_under_test):
        """
        Test for isCalibrated attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert not device_under_test.isCalibrated

    def test_isConfigured(self, device_under_test):
        """
        Test for isConfigured attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert not device_under_test.isConfigured

    def test_calibrationJobId(self, device_under_test):
        """
        Test for calibrationJobId attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.calibrationJobId == 0

    def test_daqJobId(self, device_under_test):
        """
        Test for daqJobId attributes.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.daqJobId == 0

    def test_dataDirectory(self, device_under_test):
        """
        Test for dataDirectory attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.dataDirectory == ""

    def test_configure(self, device_under_test):
        """
        Test for configure command.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        config_dict = {"station_id": 1}
        json_str = json.dumps(config_dict)
        [[result_code], [message]] = device_under_test.configure(json_str)
        assert result_code == ResultCode.OK
        assert message == MccsStation.ConfigureCommand.SUCCEEDED_MESSAGE
        assert device_under_test.isConfigured is True


class TestInitCommand:
    """
    Contains the tests of :py:class:`~ska_low_mccs.station.MccsStation`'s
    :py:class:`~ska_low_mccs.station.MccsStation.InitCommand`.
    """

    class HangableInitCommand(MccsStation.InitCommand):
        """
        A subclass of InitCommand with the following properties that
        support testing:

        * A lock that, if acquired prior to calling the command, causes
          the command to hang until the lock is released
        * Call trace attributes that record which methods were called
        """

        def __init__(self, target, state_model, logger=None):
            """
            Create a new HangableInitCommand instance.

            :param target: the object that this command acts upon; for
                example, the device for which this class implements the
                command
            :type target: object
            :param state_model: the state model that this command uses
                 to check that it is allowed to run, and that it drives
                 with actions.
            :type state_model:
                :py:class:`~ska_tango_base.DeviceStateModel`
            :param logger: the logger to be used by this Command. If not
                provided, then a default module logger will be used.
            :type logger: :py:class:`logging.Logger`
            """
            super().__init__(target, state_model, logger)
            self._hang_lock = threading.Lock()
            self._initialise_device_pool_called = False
            self._initialise_health_monitoring_called = False

        def _initialise_device_pool(self, device):
            """
            Initialise the device pool for this device (overridden here
            to inject a call trace attribute).

            :param device: the device for which the device pool is
                being initialised
            :type device: :py:class:`ska_tango_base.SKABaseDevice`
            """
            self._initialise_device_pool_called = True
            super()._initialise_device_pool(device)
            with self._hang_lock:
                # hang until the hang lock is released
                pass

        def _initialise_health_monitoring(self, device):
            """
            Initialise the health model for this device (overridden here
            to inject a call trace attribute).

            :param device: the device for which the health model is
                being initialised
            :type device: :py:class:`ska_tango_base.SKABaseDevice`
            """
            self._initialise_health_monitoring_called = True
            super()._initialise_health_monitoring(device)

    @pytest.mark.skip(
        reason="This is taking forever to run; need to investigate"
        # TODO: investigate this.
    )
    def test_interrupt(self, mocker):
        """
        Test that the command's interrupt method will cause a running
        thread to stop prematurely.

        :param mocker: fixture that wraps the :py:mod:`unittest.mock`
            module
        :type mocker: :py:class:`pytest_mock.mocker`
        """
        mock_device = mocker.MagicMock()
        mock_state_model = mocker.Mock()

        init_command = self.HangableInitCommand(mock_device, mock_state_model)

        with init_command._hang_lock:
            init_command()

            # We got the hang lock first, so the initialisation thread will hang in
            # device pool manager initialisation until we release it.

            assert init_command._initialise_device_pool_called
            assert not init_command._initialise_health_monitoring_called

            init_command.interrupt()

        init_command._thread.join()

        # Now that we've released the hang lock, the thread can exit its
        # _initialise_device_pool method, but before it enters its
        # _initialise_health_monitoring, it will detect that it has been
        # interrupted, and return
        assert init_command._initialise_device_pool_called
        assert not init_command._initialise_health_monitoring_called
