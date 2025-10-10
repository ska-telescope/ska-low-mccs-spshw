# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains integration tests for AdminMode propagation."""

from __future__ import annotations

import pytest
import tango
from ska_control_model import AdminMode
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup


@pytest.fixture(name="change_event_callbacks")
def change_event_callbacks_fixture() -> MockTangoEventCallbackGroup:
    """
    Return a dictionary of change event callbacks with asynchrony support.

    :return: a collections.defaultdict that returns change event
        callbacks by name.
    """
    return MockTangoEventCallbackGroup(
        "station_adminMode",
        "tile_adminMode",
        "subrack_adminMode",
        "daq_adminMode",
        timeout=15.0,
        assert_no_error=False,
    )


class TestAdminModePropagation:
    """Test adminMode propagation."""

    def test_subrack_mode_propagation(
        self: TestAdminModePropagation,
        sps_station_device: tango.DeviceProxy,
        subrack_device: tango.DeviceProxy,
        change_event_callbacks: MockTangoEventCallbackGroup,
    ) -> None:
        """
        Test AdminMode propagation for subrack.

        :param sps_station_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param subrack_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param change_event_callbacks: group of Tango change event
            callback with asynchronous support
        """
        subrack_device.inheritModes = True

        assert sps_station_device.adminMode == AdminMode.OFFLINE
        assert subrack_device.adminMode == AdminMode.OFFLINE

        subrack_device.subscribe_event(
            "adminMode",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["subrack_adminMode"],
        )

        sps_station_device.adminMode = AdminMode.ONLINE

        # First change events might be subscription errors so we set
        # a higher lookahead value
        change_event_callbacks.assert_change_event(
            "subrack_adminMode", AdminMode.ONLINE, lookahead=2, consume_nonmatches=True
        )
        assert subrack_device.adminMode == AdminMode.ONLINE

        sps_station_device.adminMode = AdminMode.OFFLINE
        change_event_callbacks.assert_change_event(
            "subrack_adminMode", AdminMode.OFFLINE
        )
        assert subrack_device.adminMode == AdminMode.OFFLINE

        # Turn inheritance off by setting directly
        subrack_device.adminMode = AdminMode.ENGINEERING
        change_event_callbacks.assert_change_event(
            "subrack_adminMode", AdminMode.ENGINEERING
        )

        sps_station_device.adminMode = AdminMode.ONLINE
        change_event_callbacks["subrack_adminMode"].assert_not_called()
        assert subrack_device.adminMode == AdminMode.ENGINEERING

        # Go back to inheriting
        subrack_device.inheritModes = True
        change_event_callbacks.assert_change_event(
            "subrack_adminMode", AdminMode.ONLINE
        )
        assert subrack_device.adminMode == AdminMode.ONLINE

        sps_station_device.adminMode = AdminMode.OFFLINE
        change_event_callbacks.assert_change_event(
            "subrack_adminMode", AdminMode.OFFLINE
        )
        assert subrack_device.adminMode == AdminMode.OFFLINE

    def test_tile_mode_propagation(
        self: TestAdminModePropagation,
        sps_station_device: tango.DeviceProxy,
        tile_device: tango.DeviceProxy,
        change_event_callbacks: MockTangoEventCallbackGroup,
    ) -> None:
        """
        Test AdminMode propagation for tile.

        :param sps_station_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param change_event_callbacks: group of Tango change event
            callback with asynchronous support
        """
        tile_device.inheritModes = True

        assert sps_station_device.adminMode == AdminMode.OFFLINE
        assert tile_device.adminMode == AdminMode.OFFLINE

        tile_device.subscribe_event(
            "adminMode",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["tile_adminMode"],
        )

        sps_station_device.adminMode = AdminMode.ONLINE

        # First change events might be subscription errors so we set
        # a higher lookahead value
        change_event_callbacks.assert_change_event(
            "tile_adminMode", AdminMode.ONLINE, lookahead=2, consume_nonmatches=True
        )
        assert tile_device.adminMode == AdminMode.ONLINE

        sps_station_device.adminMode = AdminMode.OFFLINE
        change_event_callbacks.assert_change_event("tile_adminMode", AdminMode.OFFLINE)
        assert tile_device.adminMode == AdminMode.OFFLINE

        # Turn inheritance off by setting directly
        tile_device.adminMode = AdminMode.ENGINEERING
        change_event_callbacks.assert_change_event(
            "tile_adminMode", AdminMode.ENGINEERING
        )

        sps_station_device.adminMode = AdminMode.ONLINE
        change_event_callbacks["tile_adminMode"].assert_not_called()
        assert tile_device.adminMode == AdminMode.ENGINEERING

        # Go back to inheriting
        tile_device.inheritModes = True
        change_event_callbacks.assert_change_event("tile_adminMode", AdminMode.ONLINE)
        assert tile_device.adminMode == AdminMode.ONLINE

        sps_station_device.adminMode = AdminMode.OFFLINE
        change_event_callbacks.assert_change_event("tile_adminMode", AdminMode.OFFLINE)
        assert tile_device.adminMode == AdminMode.OFFLINE
