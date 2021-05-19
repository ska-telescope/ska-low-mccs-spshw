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
This module contains the tests for MccsSubarrayBeam.
"""
import json
import time

import pytest
from tango import AttrQuality, EventType

from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import (
    ControlMode,
    HealthState,
    SimulationMode,
    TestMode,
)
from ska_low_mccs import MccsDeviceProxy, MccsSubarrayBeam, release


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
        "device": "subarraybeam_01",
        "proxy": MccsDeviceProxy,
    }


# pylint: disable=invalid-name
class TestMccsSubarrayBeam:
    """
    Test class for MccsSubarrayBeam tests.
    """

    @pytest.fixture()
    def device_under_test(self, tango_harness):
        """
        Fixture that returns the device under test.

        :param tango_harness: a test harness for Tango devices

        :return: the device under test
        """
        return tango_harness.get_device("low-mccs/subarraybeam/01")

    def test_InitDevice(self, device_under_test):
        """
        Test for Initial state.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        # assert device_under_test.state() == tango.DevState.OFF
        assert device_under_test.status() == "The device is in OFF state."
        # assert device_under_test.healthState == HealthState.OK
        assert device_under_test.controlMode == ControlMode.REMOTE
        assert device_under_test.simulationMode == SimulationMode.FALSE
        assert device_under_test.testMode == TestMode.TEST

        # The following reads might not be allowed in this state once properly
        # implemented
        assert list(device_under_test.stationIds) == []
        assert device_under_test.logicalBeamId == 0
        assert device_under_test.channels is None
        assert list(device_under_test.desiredPointing) == []
        assert device_under_test.updateRate == 0.0
        assert not device_under_test.isBeamLocked

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
        assert device_under_test.healthState == HealthState.DEGRADED

        _ = device_under_test.subscribe_event(
            "healthState", EventType.CHANGE_EVENT, mock_callback
        )
        mock_callback.assert_called_once()

        event_data = mock_callback.call_args[0][0].attr_value
        assert event_data.name.lower() == "healthstate"
        assert event_data.value == HealthState.DEGRADED
        assert event_data.quality == AttrQuality.ATTR_VALID

        mock_callback.reset_mock()
        device_under_test.isBeamLocked = True
        assert device_under_test.healthState == HealthState.OK

        # Tango's event system is asynchronous. We need to allow time
        # for the event to arrive.
        time.sleep(0.2)
        mock_callback.assert_called_once()

        event_data = mock_callback.call_args[0][0].attr_value
        assert event_data.name.lower() == "healthstate"
        assert event_data.value == HealthState.OK
        assert event_data.quality == AttrQuality.ATTR_VALID

        mock_callback.reset_mock()
        device_under_test.isBeamLocked = False
        assert device_under_test.healthState == HealthState.DEGRADED

        # Tango's event system is asynchronous. We need to allow time
        # for the event to arrive.
        time.sleep(0.2)
        mock_callback.assert_called_once()

        event_data = mock_callback.call_args[0][0].attr_value
        assert event_data.name.lower() == "healthstate"
        assert event_data.value == HealthState.DEGRADED
        assert event_data.quality == AttrQuality.ATTR_VALID

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

    def test_versionId(self, device_under_test):
        """
        Test for versionId.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.versionId == release.version

    # MccsSubarrayBeam attributes
    def test_stationIds(self, device_under_test):
        """
        Test for stationIds attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert list(device_under_test.stationIds) == []
        device_under_test.stationIds = [3, 4, 5, 6]
        assert list(device_under_test.stationIds) == [3, 4, 5, 6]

    def test_logicalBeamId(self, device_under_test):
        """
        Test for logicalId attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.logicalBeamId == 0

    def test_updateRate(self, device_under_test):
        """
        Test for updateRate attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.updateRate == 0.0

    def test_isBeamLocked(self, device_under_test):
        """
        Test for isBeamLocked attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert not device_under_test.isBeamLocked

    def test_channels(self, device_under_test):
        """
        Test for channels.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.channels is None

    def test_desiredPointing(self, device_under_test):
        """
        Test of desired pointing attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        dummy_sky_coordinate = [1585619550.0, 192.85948, 2.0, 27.12825, 1.0]
        float_format = "{:3.4f}"
        self._test_readwrite_double_array(
            device_under_test, "desiredPointing", dummy_sky_coordinate, float_format
        )

    def _test_readwrite_double_array(
        self, device_under_test, attribute_name, value_to_write, float_format
    ):
        """
        Helper method for testing a READ-WRITE double array attribute.
        This is a messy test because there can be some loss of floating-
        point precision during transfer, so you have to check
        approximate equality when reading back what you've written. This
        is done here by comparing the values by their string
        representation.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param attribute_name: name of the attribute to test
        :type attribute_name: str
        :param value_to_write: value to write to and read from the
            attribute
        :type value_to_write: float
        :param float_format: a pair of double values will be considered
            equal if this string format yields the same string for both
        :type float_format: str
        """

        # SETUP
        write_as_string = [float_format.format(x) for x in value_to_write]

        # RUN
        device_under_test.write_attribute(attribute_name, value_to_write)
        value_as_read = device_under_test.read_attribute(attribute_name).value

        # CHECK
        read_as_string = [float_format.format(x) for x in value_as_read]
        assert read_as_string == write_as_string

    def test_Configure(self, device_under_test):
        """
        Test for Configure.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        config_dict = {
            "subarray_beam_id": 1,
            "station_ids": [1, 2],
            "channels": [[0, 8, 1, 1], [8, 8, 2, 1], [24, 16, 2, 1]],
            "update_rate": 3.14,
            "sky_coordinates": [1585619550.0, 192.0, 2.0, 27.0, 1.0],
            "antenna_weights": [1.0, 1.0, 1.0],
            "phase_centre": [0.0, 0.0],
        }
        json_str = json.dumps(config_dict)
        [[result_code], [message]] = device_under_test.Configure(json_str)
        assert result_code == ResultCode.OK
        assert message == MccsSubarrayBeam.ConfigureCommand.SUCCEEDED_MESSAGE
        assert device_under_test.subarrayBeamId == 1
        assert device_under_test.updateRate == 3.14
        assert list(device_under_test.stationIds) == [1, 2]
        assert len(list(device_under_test.channels)) == len(
            [[0, 8, 1, 1], [8, 8, 2, 1], [24, 16, 2, 1]]
        )
        for a, b in zip(
            list(device_under_test.channels),
            [[0, 8, 1, 1], [8, 8, 2, 1], [24, 16, 2, 1]],
        ):
            assert list(a) == list(b)
        assert list(device_under_test.desiredPointing) == [
            1585619550.0,
            192.0,
            2.0,
            27.0,
            1.0,
        ]
        assert len(list(device_under_test.antennaWeights)) == len([1.0, 1.0, 1.0])
        assert list(device_under_test.antennaWeights) == [1.0, 1.0, 1.0]
