# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains integration tests of MCCS power management functionality."""
from __future__ import annotations

import time
import unittest.mock
from typing import Any, Callable

import pytest

# from ska_tango_base.commands import ResultCode
import tango
from ska_tango_base.control_model import AdminMode, HealthState

from ska_low_mccs import MccsDeviceProxy
from ska_low_mccs.testing.mock import MockChangeEventCallback, MockDeviceBuilder
from ska_low_mccs.testing.tango_harness import TangoHarness


@pytest.fixture()
def devices_to_load() -> dict[str, Any]:
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
            {"name": "tile_0001", "proxy": MccsDeviceProxy},
            {"name": "tile_0002", "proxy": MccsDeviceProxy},
            {"name": "tile_0003", "proxy": MccsDeviceProxy},
            {"name": "tile_0004", "proxy": MccsDeviceProxy},
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
def mock_subarray_factory() -> Callable[[], unittest.mock.Mock]:
    """
    Fixture that provides a factory for mock subarrays.

    :return: a factory for mock subarray
    """
    builder = MockDeviceBuilder()
    builder.set_state(tango.DevState.ON)
    builder.add_attribute("adminMode", AdminMode.ONLINE)
    builder.add_attribute("healthState", HealthState.OK)
    return builder


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
def initial_mocks(
    mock_subarray_factory: Callable[[], unittest.mock.Mock],
    mock_subarray_beam_factory: Callable[[], unittest.mock.Mock],
) -> dict[str, unittest.mock.Mock]:
    """
    Return a specification of the mock devices to be set up in the Tango test harness.

    This is a pytest fixture that can be used to inject pre-build mock
    devices into the Tango test harness at specified FQDNs.

    :param mock_subarray_factory: a factory that returns a mock subarray
        device each time it is called
    :param mock_subarray_beam_factory: a factory that returns a mock
        subarray beam device each time it is called

    :return: specification of the mock devices to be set up in the Tango
        test harness.
    """
    return {
        "low-mccs/subarray/01": mock_subarray_factory(),
        "low-mccs/subarray/02": mock_subarray_factory(),
        "low-mccs/subarraybeam/01": mock_subarray_beam_factory(),
        "low-mccs/subarraybeam/02": mock_subarray_beam_factory(),
        "low-mccs/subarraybeam/03": mock_subarray_beam_factory(),
        "low-mccs/subarraybeam/04": mock_subarray_beam_factory(),
    }


class TestPowerManagement:
    """
    Integration test cases for MCCS subsystem's power management.

    These tests focus on the path from the controller down to the tiles
    and antennas.

    :todo: Due to https://github.com/tango-controls/cppTango/issues/816,
        a device test context cannot contain more than six device
        classes. The subarray beam devices are therefore mocked out in
        these tests. Once the above bug is fixed, we should update these
        tests to use real subarray beam devices.
    """

    def _check_states(
        self: TestPowerManagement,
        devices: list[MccsDeviceProxy],
        expected_state: tango.DevState,
    ) -> None:
        """
        Check each of the devices has the expected state.

        :param devices: a list of MccsDeviceProxy devices
        :param expected_state: the expected state of each of the devices
        """
        for device in devices:
            assert device.state() == expected_state, f"device = {device.name}"

    def test_controller_state_rollup(
        self: TestPowerManagement, tango_harness: TangoHarness
    ) -> None:
        """
        Test rollup.

        Test that changes to admin mode in subservient devices result in state changes
        which roll up to the controller.

        :param tango_harness: A tango context of some sort; possibly a
            :py:class:`tango.test_context.MultiDeviceTestContext`, possibly
            the real thing. The only requirement is that it provide a
            ``get_device(fqdn)`` method that returns a
            :py:class:`tango.DeviceProxy`.
        """
        controller = tango_harness.get_device("low-mccs/control/control")
        station_1 = tango_harness.get_device("low-mccs/station/001")
        station_2 = tango_harness.get_device("low-mccs/station/002")
        subrack = tango_harness.get_device("low-mccs/subrack/01")
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

        # sleep enough time for single polling cycle for each device to complete. This
        # is because (as of v0.13 of the base classes) state changes are only passed to
        # the Tango layer by the polled base class command PushChanges. Because polling
        # only starts after device initialisation, we need to allow enough time for the
        # state changes performed during device inittialisation to be picked up by the
        # first polling cycle.
        # time.sleep(0.1)
        time.sleep(0.4)

        # putting controller online makes it transition to UNKNOWN because it doesn't
        # yet know the state of its stations and subracks
        assert controller.adminMode == AdminMode.OFFLINE
        assert controller.state() == tango.DevState.DISABLE
        controller.adminMode = AdminMode.ONLINE
        # time.sleep(0.1)
        # sleep enough time for one polling cycle of PushChanges to occur
        time.sleep(0.4)
        assert controller.state() == tango.DevState.UNKNOWN

        # putting a station online makes it transition to UNKNOWN because it doesn't yet
        # know the state of its apiu, antennas and tiles.
        stations = [station_1, station_2]
        for station in stations:
            assert station.adminMode == AdminMode.OFFLINE
            assert station.state() == tango.DevState.DISABLE
            station.adminMode = AdminMode.ONLINE
        # time.sleep(0.1)
        # sleep enough time for one polling cycle of PushChanges to occur
        time.sleep(0.4)
        self._check_states(stations + [controller], tango.DevState.UNKNOWN)

        # putting an antenna online makes it transition to UNKNOWN because it needs its
        # APIU and tile to be online in order to determine its state
        antennas = [
            antenna_1,
            antenna_2,
            antenna_3,
            antenna_4,
            antenna_5,
            antenna_6,
            antenna_7,
            antenna_8,
        ]
        for antenna in antennas:
            assert antenna.adminMode == AdminMode.OFFLINE
            assert antenna.state() == tango.DevState.DISABLE
            antenna.adminMode = AdminMode.ONLINE
        # time.sleep(0.1)
        # sleep enough time for one polling cycle of PushChanges to occur
        time.sleep(0.4)
        self._check_states(antennas + stations + [controller], tango.DevState.UNKNOWN)

        # putting the APIU online makes it transition to OFF because it knows it is off.
        # And the antennas transition to OFF too, because they infer from the APIU being
        # off that they must be off too.
        apius = [apiu_1, apiu_2]
        for apiu in apius:
            assert apiu.adminMode == AdminMode.OFFLINE
            assert apiu.state() == tango.DevState.DISABLE
            # PAC: I noticed that putting the APIU online makes it pass through ON before
            # it transitions to OFF... is this intended?
            apiu.adminMode = AdminMode.ONLINE
        # time.sleep(0.1)
        # sleep enough time for one polling cycle of PushChanges to occur
        time.sleep(0.4)
        # self._check_states(apius + antennas, tango.DevState.OFF)
        self._check_states(apius, tango.DevState.OFF)
        self._check_states(antennas, tango.DevState.OFF)
        self._check_states(stations + [controller], tango.DevState.UNKNOWN)

        # putting a tile online makes it transition to UNKNOWN because it needs the
        # subrack to be on in order to determine its state
        tiles = [tile_1, tile_2, tile_3, tile_4]
        for tile in tiles:
            assert tile.adminMode == AdminMode.OFFLINE
            assert tile.state() == tango.DevState.DISABLE
            tile.adminMode = AdminMode.ONLINE
        # time.sleep(0.1)
        # sleep enough time for one polling cycle of PushChanges to occur
        time.sleep(0.4)
        self._check_states(tiles + stations + [controller], tango.DevState.UNKNOWN)

        # putting the subrack online will make it transition to OFF (having detected
        # that the subrack hardware is turned off. Tile infers that its TPM is off, so
        # transitions to OFF. Station has all it neds to infer that it is OFF. Finally,
        # controller infers that it is OFF.
        assert subrack.adminMode == AdminMode.OFFLINE
        assert subrack.state() == tango.DevState.DISABLE
        subrack.adminMode = AdminMode.ONLINE
        # time.sleep(0.1)
        # sleep enough time for one polling cycle of PushChanges to occur
        time.sleep(0.4)
        self._check_states(
            tiles + stations + [controller] + [subrack], tango.DevState.OFF
        )

    @pytest.mark.timeout(19)
    def test_power_on(
        self: TestPowerManagement,
        tango_harness: TangoHarness,
        lrc_result_changed_callback: MockChangeEventCallback,
        controller_device_state_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test that a MccsController device can enable an MccsSubarray device.

        :param tango_harness: a test harness for tango devices
        :param lrc_result_changed_callback: a callback to
            be used to subscribe to device LRC result changes
        :param controller_device_state_changed_callback: a callback to
            be used to subscribe to controller state change
        """
        controller = tango_harness.get_device("low-mccs/control/control")

        controller.add_change_event_callback(
            "state",
            controller_device_state_changed_callback,
        )
        assert "state" in controller._change_event_subscription_ids

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

        time.sleep(0.4)
        controller_device_state_changed_callback.assert_last_change_event(
            tango.DevState.DISABLE
        )

        devices = [
            apiu_1,
            apiu_2,
            subrack,
            tile_1,
            tile_2,
            tile_3,
            tile_4,
            antenna_1,
            antenna_2,
            antenna_3,
            antenna_4,
            antenna_5,
            antenna_6,
            antenna_7,
            antenna_8,
            station_1,
            station_2,
            controller,
        ]

        for device in devices:
            device.adminMode = AdminMode.ONLINE
        time.sleep(0.1)

        controller_device_state_changed_callback.assert_next_change_event(
            tango.DevState.UNKNOWN
        )
        controller_device_state_changed_callback.assert_last_change_event(
            tango.DevState.OFF
        )

        for device in devices:
            assert device.state() == tango.DevState.OFF

        # Subscribe to controller's LRC result attribute
        controller.add_change_event_callback(
            "longRunningCommandResult",
            lrc_result_changed_callback,
        )
        assert (
            "longRunningCommandResult".casefold()
            in controller._change_event_subscription_ids
        )

        time.sleep(0.1)  # allow event system time to run
        initial_lrc_result = ("", "")
        assert controller.longRunningCommandResult == initial_lrc_result
        lrc_result_changed_callback.assert_next_change_event(initial_lrc_result)

        # TODO: This next call causes a segmentation fault so is unstable
        #       for inclusion in our unit tests. Investigation required.
        # # Message queue length is non-zero so command is queued
        # ([result_code], [unique_id]) = controller.On()
        # assert result_code == ResultCode.QUEUED
        # assert "OnCommand" in unique_id

        # lrc_result_changed_callback.assert_long_running_command_result_change_event(
        #     unique_id=unique_id,
        #     expected_result_code=ResultCode.OK,
        #     expected_message="Controller On command completed OK",
        # )
        # self._show_state_of_devices(devices)

        # # Double check that the controller fired a state change event
        # controller_device_state_changed_callback.assert_last_change_event(
        #     tango.DevState.ON
        # )

        # for device in devices:
        #     assert device.state() == tango.DevState.ON

    def _show_state_of_devices(
        self: TestPowerManagement,
        devices: list[MccsDeviceProxy],
    ) -> None:
        """
        Show the state of the requested devices.

        :param devices: list of MCCS device proxies
        """
        for device in devices:
            print(f"Device: {device.name} = {device.state()}")
