# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains integration tests of health management in MCCS."""
from __future__ import annotations

import unittest.mock
from typing import Callable

import pytest
import tango
from ska_tango_base.control_model import AdminMode, HealthState

from ska_low_mccs import MccsDeviceProxy
from ska_low_mccs.testing.mock import MockChangeEventCallback, MockDeviceBuilder
from ska_low_mccs.testing.tango_harness import DevicesToLoadType, TangoHarness
from ska_low_mccs.tile import DemoTile


@pytest.fixture()
def devices_to_load() -> DevicesToLoadType:
    """
    Fixture that specifies the devices to be loaded for testing.

    :return: specification of the devices to be loaded
    """
    return {
        "path": "charts/ska-low-mccs/data/configuration.json",
        "package": "ska_low_mccs",
        "devices": [
            {"name": "controller", "proxy": MccsDeviceProxy},
            {"name": "station_001", "proxy": MccsDeviceProxy},
            {"name": "station_002", "proxy": MccsDeviceProxy},
            {"name": "subrack_01", "proxy": MccsDeviceProxy},
            {"name": "tile_0001", "proxy": MccsDeviceProxy, "patch": DemoTile},
            {"name": "tile_0002", "proxy": MccsDeviceProxy, "patch": DemoTile},
            {"name": "tile_0003", "proxy": MccsDeviceProxy, "patch": DemoTile},
            {"name": "tile_0004", "proxy": MccsDeviceProxy, "patch": DemoTile},
            {"name": "apiu_001", "proxy": MccsDeviceProxy},
            {"name": "apiu_002", "proxy": MccsDeviceProxy},
            {"name": "antenna_000001", "proxy": MccsDeviceProxy},
            {"name": "antenna_000002", "proxy": MccsDeviceProxy},
            {"name": "antenna_000003", "proxy": MccsDeviceProxy},
            {"name": "antenna_000004", "proxy": MccsDeviceProxy},
            {"name": "antenna_000005", "proxy": MccsDeviceProxy},
            {"name": "antenna_000006", "proxy": MccsDeviceProxy},
            {"name": "antenna_000007", "proxy": MccsDeviceProxy},
            {"name": "antenna_000008", "proxy": MccsDeviceProxy},
        ],
    }


@pytest.fixture()
def mock_subarray_beam_factory() -> Callable[[], unittest.mock.Mock]:
    """
    Return a factory that returns mock subarray beam devices for use in testing.

    :return: a factory that returns mock subarray beam devices for use
        in testing
    """
    builder = MockDeviceBuilder()
    builder.set_state(tango.DevState.ON)
    builder.add_attribute("adminMode", AdminMode.ONLINE)
    builder.add_attribute("healthState", HealthState.OK)
    return builder


@pytest.fixture()
def mock_station_beam_factory() -> Callable[[], unittest.mock.Mock]:
    """
    Return a factory that returns mock station beam devices for use in testing.

    :return: a factory that returns mock station beam devices for use
        in testing
    """
    builder = MockDeviceBuilder()
    builder.set_state(tango.DevState.ON)
    builder.add_attribute("adminMode", AdminMode.ONLINE)
    builder.add_attribute("healthState", HealthState.OK)
    return builder


@pytest.fixture()
def initial_mocks(
    mock_subarray_beam_factory: Callable[[], unittest.mock.Mock],
    mock_station_beam_factory: Callable[[], unittest.mock.Mock],
) -> dict[str, unittest.mock.Mock]:
    """
    Return a specification of the mock devices to be set up in the Tango test harness.

    This is a pytest fixture that can be used to inject pre-build mock
    devices into the Tango test harness at specified FQDNs.

    :param mock_subarray_beam_factory: a factory that returns a mock
        subarray beam device

    :param mock_station_beam_factory: a factory that returns a mock
        station beam device

    :return: specification of the mock devices to be set up in the Tango
        test harness.
    """
    return {
        "low-mccs/subarraybeam/01": mock_subarray_beam_factory(),
        "low-mccs/subarraybeam/02": mock_subarray_beam_factory(),
        "low-mccs/subarraybeam/03": mock_subarray_beam_factory(),
        "low-mccs/subarraybeam/04": mock_subarray_beam_factory(),
        "low-mccs/beam/01": mock_station_beam_factory(),
        "low-mccs/beam/02": mock_station_beam_factory(),
        "low-mccs/beam/03": mock_station_beam_factory(),
        "low-mccs/beam/04": mock_station_beam_factory(),
    }


@pytest.fixture()
def controller_device_health_state_changed_callback(
    mock_change_event_callback_factory: Callable[[str], MockChangeEventCallback],
) -> MockChangeEventCallback:
    """
    Return a mock change event callback for controller device health state change.

    :param mock_change_event_callback_factory: fixture that provides a
        mock change event callback factory (i.e. an object that returns
        mock callbacks when called).

    :return: a mock change event callback to be called when the
        controller device health state changes. (The callback has not
        yet been subscribed to the device; this must be done as part of
        the test.)
    """
    return mock_change_event_callback_factory("healthState")


class TestHealthManagement:
    """Test cases for the MCCS health management subsystem."""

    def test_controller_health_rollup(
        self: TestHealthManagement,
        tango_harness: TangoHarness,
        controller_device_state_changed_callback: MockChangeEventCallback,
        controller_device_health_state_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test that health rolls up to the controller.

        :param tango_harness: A tango context of some sort; possibly a
            :py:class:`tango.test_context.MultiDeviceTestContext`, possibly
            the real thing. The only requirement is that it provide a
            ``get_device(fqdn)`` method that returns a
            :py:class:`tango.DeviceProxy`.
        :param controller_device_state_changed_callback: a callback to
            be used to subscribe to controller state change
        :param controller_device_health_state_changed_callback: a
            callback to be used to subscribe to controller state change
        """
        controller = tango_harness.get_device("low-mccs/control/control")
        subrack = tango_harness.get_device("low-mccs/subrack/01")
        station_1 = tango_harness.get_device("low-mccs/station/001")
        station_2 = tango_harness.get_device("low-mccs/station/002")
        tile_1 = tango_harness.get_device("low-mccs/tile/0001")
        tile_2 = tango_harness.get_device("low-mccs/tile/0002")
        tile_3 = tango_harness.get_device("low-mccs/tile/0003")
        tile_4 = tango_harness.get_device("low-mccs/tile/0004")
        apiu_1 = tango_harness.get_device("low-mccs/apiu/001")
        apiu_2 = tango_harness.get_device("low-mccs/apiu/002")
        antenna_1 = tango_harness.get_device("low-mccs/antenna/000001")
        antenna_2 = tango_harness.get_device("low-mccs/antenna/000002")
        antenna_3 = tango_harness.get_device("low-mccs/antenna/000003")
        antenna_4 = tango_harness.get_device("low-mccs/antenna/000004")
        antenna_5 = tango_harness.get_device("low-mccs/antenna/000005")
        antenna_6 = tango_harness.get_device("low-mccs/antenna/000006")
        antenna_7 = tango_harness.get_device("low-mccs/antenna/000007")
        antenna_8 = tango_harness.get_device("low-mccs/antenna/000008")

        # register a callback so we can block on state changes
        # instead of sleeping
        controller.add_change_event_callback(
            "state", controller_device_state_changed_callback
        )
        controller_device_state_changed_callback.assert_next_change_event(
            tango.DevState.UNKNOWN
        )
        controller_device_state_changed_callback.assert_next_change_event(
            tango.DevState.INIT
        )
        controller_device_state_changed_callback.assert_next_change_event(
            tango.DevState.DISABLE
        )

        controller.add_change_event_callback(
            "healthState",
            controller_device_health_state_changed_callback,
        )
        controller_device_health_state_changed_callback.assert_next_change_event(
            HealthState.UNKNOWN
        )

        assert antenna_1.healthState == HealthState.UNKNOWN
        assert antenna_2.healthState == HealthState.UNKNOWN
        assert antenna_3.healthState == HealthState.UNKNOWN
        assert antenna_4.healthState == HealthState.UNKNOWN
        assert antenna_5.healthState == HealthState.UNKNOWN
        assert antenna_6.healthState == HealthState.UNKNOWN
        assert antenna_7.healthState == HealthState.UNKNOWN
        assert antenna_8.healthState == HealthState.UNKNOWN
        assert apiu_1.healthState == HealthState.UNKNOWN
        assert apiu_2.healthState == HealthState.UNKNOWN
        assert tile_1.healthState == HealthState.UNKNOWN
        assert tile_2.healthState == HealthState.UNKNOWN
        assert tile_3.healthState == HealthState.UNKNOWN
        assert tile_4.healthState == HealthState.UNKNOWN
        assert station_1.healthState == HealthState.UNKNOWN
        assert station_2.healthState == HealthState.UNKNOWN
        assert subrack.healthState == HealthState.UNKNOWN
        assert controller.healthState == HealthState.UNKNOWN

        # TODO: Fix this test once the below bug is fixed.
        # Due to https://gitlab.com/tango-controls/cppTango/-/issues/843
        # we can only run tests for ten seconds before the Tango
        # keepalive thread dies. This is about as far as this test gets
        # before its ten seconds are up.

        # controller.adminMode = AdminMode.ONLINE
        # subrack.adminMode = AdminMode.ONLINE
        # station_1.adminMode = AdminMode.ONLINE
        # station_2.adminMode = AdminMode.ONLINE
        # tile_1.adminMode = AdminMode.ONLINE
        # tile_2.adminMode = AdminMode.ONLINE
        # tile_3.adminMode = AdminMode.ONLINE
        # tile_4.adminMode = AdminMode.ONLINE
        # apiu_1.adminMode = AdminMode.ONLINE
        # apiu_2.adminMode = AdminMode.ONLINE
        # antenna_1.adminMode = AdminMode.ONLINE
        # antenna_2.adminMode = AdminMode.ONLINE
        # antenna_3.adminMode = AdminMode.ONLINE
        # antenna_4.adminMode = AdminMode.ONLINE
        # antenna_5.adminMode = AdminMode.ONLINE
        # antenna_6.adminMode = AdminMode.ONLINE
        # antenna_7.adminMode = AdminMode.ONLINE
        # antenna_8.adminMode = AdminMode.ONLINE

        # controller_device_state_changed_callback.assert_next_change_event(
        #     tango.DevState.UNKNOWN
        # )
        # controller_device_state_changed_callback.assert_next_change_event(
        #     tango.DevState.OFF
        # )

        # assert antenna_1.state() == tango.DevState.OFF
        # assert antenna_2.state() == tango.DevState.OFF
        # assert antenna_3.state() == tango.DevState.OFF
        # assert antenna_4.state() == tango.DevState.OFF
        # assert antenna_5.state() == tango.DevState.OFF
        # assert antenna_6.state() == tango.DevState.OFF
        # assert antenna_7.state() == tango.DevState.OFF
        # assert antenna_8.state() == tango.DevState.OFF
        # assert apiu_1.state() == tango.DevState.OFF
        # assert apiu_2.state() == tango.DevState.OFF
        # assert tile_1.state() == tango.DevState.OFF
        # assert tile_2.state() == tango.DevState.OFF
        # assert tile_3.state() == tango.DevState.OFF
        # assert tile_4.state() == tango.DevState.OFF
        # assert station_1.state() == tango.DevState.OFF
        # assert station_2.state() == tango.DevState.OFF
        # assert subrack.state() == tango.DevState.OFF
        # assert controller.state() == tango.DevState.OFF

        # controller_device_health_state_changed_callback.assert_next_change_event(
        #     HealthState.OK
        # )

        # assert antenna_1.healthState == HealthState.OK
        # assert antenna_2.healthState == HealthState.OK
        # assert antenna_3.healthState == HealthState.OK
        # assert antenna_4.healthState == HealthState.OK
        # assert antenna_5.healthState == HealthState.OK
        # assert antenna_6.healthState == HealthState.OK
        # assert antenna_7.healthState == HealthState.OK
        # assert antenna_8.healthState == HealthState.OK
        # assert apiu_1.healthState == HealthState.OK
        # assert apiu_2.healthState == HealthState.OK
        # assert tile_1.healthState == HealthState.OK
        # assert tile_2.healthState == HealthState.OK
        # assert tile_3.healthState == HealthState.OK
        # assert tile_4.healthState == HealthState.OK
        # assert station_1.healthState == HealthState.OK
        # assert station_2.healthState == HealthState.OK
        # assert subrack.healthState == HealthState.OK
        # assert controller.healthState == HealthState.OK

        # controller.On()

        # controller_device_state_changed_callback.assert_last_change_event(
        #     tango.DevState.ON
        # )

        # assert antenna_1.state() == tango.DevState.ON
        # assert antenna_2.state() == tango.DevState.ON
        # assert antenna_3.state() == tango.DevState.ON
        # assert antenna_4.state() == tango.DevState.ON
        # assert antenna_5.state() == tango.DevState.ON
        # assert antenna_6.state() == tango.DevState.ON
        # assert antenna_7.state() == tango.DevState.ON
        # assert antenna_8.state() == tango.DevState.ON
        # assert apiu_1.state() == tango.DevState.ON
        # assert apiu_2.state() == tango.DevState.ON
        # assert tile_1.state() == tango.DevState.ON
        # assert tile_2.state() == tango.DevState.ON
        # assert tile_3.state() == tango.DevState.ON
        # assert tile_4.state() == tango.DevState.ON
        # assert station_1.state() == tango.DevState.ON
        # assert station_2.state() == tango.DevState.ON
        # assert subrack.state() == tango.DevState.ON
        # assert controller.state() == tango.DevState.ON

        # assert antenna_1.healthState == HealthState.OK
        # assert antenna_2.healthState == HealthState.OK
        # assert antenna_3.healthState == HealthState.OK
        # assert antenna_4.healthState == HealthState.OK
        # assert antenna_5.healthState == HealthState.OK
        # assert antenna_6.healthState == HealthState.OK
        # assert antenna_7.healthState == HealthState.OK
        # assert antenna_8.healthState == HealthState.OK
        # assert apiu_1.healthState == HealthState.OK
        # assert apiu_2.healthState == HealthState.OK
        # assert tile_1.healthState == HealthState.OK
        # assert tile_2.healthState == HealthState.OK
        # assert tile_3.healthState == HealthState.OK
        # assert tile_4.healthState == HealthState.OK
        # assert station_1.healthState == HealthState.OK
        # assert station_2.healthState == HealthState.OK
        # assert subrack.healthState == HealthState.OK
        # assert controller.healthState == HealthState.OK

        # # Now let's make tile 1 fail. We should see that failure
        # # propagate up to station and then to controller
        # tile_1.SimulateFault(True)

        # controller_device_health_state_changed_callback.assert_last_change_event(
        #     HealthState.FAILED
        # )

        # assert tile_1.state() == tango.DevState.FAULT
        # assert tile_1.healthState == HealthState.FAILED

        # assert tile_2.healthState == HealthState.OK
        # assert tile_3.healthState == HealthState.OK
        # assert tile_4.healthState == HealthState.OK

        # assert antenna_1.healthState == HealthState.FAILED  # depends on that tile
        # assert antenna_2.healthState == HealthState.FAILED  # depends on that tile
        # assert antenna_3.healthState == HealthState.OK
        # assert antenna_4.healthState == HealthState.OK
        # assert antenna_5.healthState == HealthState.OK
        # assert antenna_6.healthState == HealthState.OK
        # assert antenna_7.healthState == HealthState.OK
        # assert antenna_8.healthState == HealthState.OK
        # assert apiu_1.healthState == HealthState.OK
        # assert apiu_2.healthState == HealthState.OK
        # assert station_1.healthState == HealthState.FAILED
        # assert station_2.healthState == HealthState.OK
        # assert subrack.healthState == HealthState.OK
        # assert controller.healthState == HealthState.FAILED

        # # It might take some time to replace the failed tile 1, and
        # # meanwhile we don't want it alarming for weeks. Let's disable it,
        # # then take it offline. The tile will still report itself as FAILED,
        # # but station will not take it into account when calculating its own
        # # health.
        # tile_1.adminMode = AdminMode.OFFLINE

        # controller_device_health_state_changed_callback.assert_next_change_event(
        #     HealthState.OK
        # )

        # assert tile_1.state() == tango.DevState.DISABLE
        # assert tile_1.healthState == HealthState.UNKNOWN  # and it won't roll up

        # assert tile_2.healthState == HealthState.OK
        # assert tile_3.healthState == HealthState.OK
        # assert tile_4.healthState == HealthState.OK

        # assert antenna_1.healthState == HealthState.OK  # not rolling up tile health
        # assert antenna_2.healthState == HealthState.OK  # not rolling up tile health
        # assert antenna_3.healthState == HealthState.OK
        # assert antenna_4.healthState == HealthState.OK
        # assert antenna_5.healthState == HealthState.OK
        # assert antenna_6.healthState == HealthState.OK
        # assert antenna_7.healthState == HealthState.OK
        # assert antenna_8.healthState == HealthState.OK
        # assert apiu_1.healthState == HealthState.OK
        # assert apiu_2.healthState == HealthState.OK
        # assert station_1.healthState == HealthState.OK  # not rolling up tile health
        # assert station_2.healthState == HealthState.OK
        # assert subrack.healthState == HealthState.OK
        # assert controller.healthState == HealthState.OK  # not rolling up tile health

        # # Okay, we've finally fixed the tile. Let's make it work again, and
        # # put it back online
        # tile_1.SimulateFault(False)
        # tile_1.adminMode = AdminMode.ONLINE

        # controller_device_health_state_changed_callback.assert_last_change_event(
        #     HealthState.OK
        # )

        # assert tile_1.healthState == HealthState.OK
        # assert tile_2.healthState == HealthState.OK
        # assert tile_3.healthState == HealthState.OK
        # assert tile_4.healthState == HealthState.OK

        # assert antenna_1.healthState == HealthState.OK
        # assert antenna_2.healthState == HealthState.OK
        # assert antenna_3.healthState == HealthState.OK
        # assert antenna_4.healthState == HealthState.OK
        # assert antenna_5.healthState == HealthState.OK
        # assert antenna_6.healthState == HealthState.OK
        # assert antenna_7.healthState == HealthState.OK
        # assert antenna_8.healthState == HealthState.OK
        # assert apiu_1.healthState == HealthState.OK
        # assert apiu_2.healthState == HealthState.OK
        # assert station_1.healthState == HealthState.OK
        # assert station_2.healthState == HealthState.OK
        # assert subrack.healthState == HealthState.OK
        # assert controller.healthState == HealthState.OK
