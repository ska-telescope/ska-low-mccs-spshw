###############################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA-Low-MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
###############################################################################
"""Contains the tests for the MccsController Tango device_under_test prototype."""
from __future__ import annotations

import pytest
from ska_tango_base.commands import ResultCode

from ska_low_mccs import MccsDeviceProxy, release
from ska_low_mccs.testing.mock import MockChangeEventCallback
from ska_low_mccs.testing.tango_harness import DeviceToLoadType, TangoHarness


@pytest.fixture()
def device_to_load() -> DeviceToLoadType:
    """
    Fixture that specifies the device to be loaded for testing.

    :return: specification of the device to be loaded
    """
    return {
        "path": "charts/ska-low-mccs/data/configuration.json",
        "package": "ska_low_mccs",
        "device": "controller",
        "proxy": MccsDeviceProxy,
    }


@pytest.fixture()
def device_under_test(tango_harness: TangoHarness) -> MccsDeviceProxy:
    """
    Fixture that returns the device under test.

    :param tango_harness: a test harness for Tango devices

    :return: the device under test
    """
    return tango_harness.get_device("low-mccs/control/control")


class TestMccsControllerLrc:
    """Tests of the MccsController device for long-running commands."""

    def test_get_version_info(
        self: TestMccsControllerLrc,
        device_under_test: MccsDeviceProxy,
        lrc_result_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for GetVersionInfo.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param lrc_result_changed_callback: a callback to
            be used to subscribe to device LRC result changes
        """
        # Subscribe to controller's LRC result attribute
        device_under_test.add_change_event_callback(
            "longRunningCommandResult", lrc_result_changed_callback,
        )
        assert "longRunningCommandResult".casefold() in device_under_test._change_event_subscription_ids
        initial_lrc_result = ("", "", "")
        assert device_under_test.longRunningCommandResult == initial_lrc_result
        lrc_result_changed_callback.assert_next_change_event(initial_lrc_result)

        ([result_code], [unique_id]) = device_under_test.GetVersionInfo()
        assert result_code == ResultCode.QUEUED
        assert "GetVersionInfo" in unique_id

        vinfo = release.get_release_info(device_under_test.info().dev_class)
        lrc_result = (
            unique_id,
            str(ResultCode.OK.value),
            str([vinfo]),
        )
        lrc_result_changed_callback.assert_last_change_event(lrc_result)
