# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains integration tests of MCCS device interactions."""
from __future__ import annotations

import time
import unittest.mock
from typing import Callable, Iterable, cast

import pytest
import tango
from ska_control_model import AdminMode, HealthState, ObsState, ResultCode
from ska_low_mccs_common import MccsDeviceProxy
from ska_low_mccs_common.testing.mock import MockChangeEventCallback, MockDeviceBuilder
from ska_low_mccs_common.testing.tango_harness import DevicesToLoadType, TangoHarness
from ska_low_mccs_common.utils import call_with_json


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
            {"name": "subarray_01", "proxy": MccsDeviceProxy},
            {"name": "subarray_02", "proxy": MccsDeviceProxy},
            {"name": "station_001", "proxy": MccsDeviceProxy},
            {"name": "station_002", "proxy": MccsDeviceProxy},
        ],
    }


@pytest.fixture()
def mock_apiu_factory() -> Callable[[], unittest.mock.Mock]:
    """
    Return a factory that returns mock APIU devices for use in testing.

    Each mock device will mock a powered-on APIU.

    :return: a factory that returns a mock APIU device for use in
        testing.
    """
    builder = MockDeviceBuilder()
    builder.set_state(tango.DevState.ON)
    builder.add_attribute("adminMode", AdminMode.ONLINE)
    builder.add_attribute("healthState", HealthState.OK)
    return builder


@pytest.fixture()
def mock_antenna_factory() -> Callable[[], unittest.mock.Mock]:
    """
    Return a factory that returns mock antenna device for use in testing.

    Each mock device will mock a powered-on antenna.

    :return: a mock APIU device for use in testing.
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

    :return: a mock subarray beam device for use in testing.
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

    :return: a mock station beam device for use in testing.
    """
    builder = MockDeviceBuilder()
    builder.set_state(tango.DevState.ON)
    builder.add_attribute("adminMode", AdminMode.ONLINE)
    builder.add_attribute("healthState", HealthState.OK)
    return builder


@pytest.fixture()
def mock_subrack_factory() -> Callable[[], unittest.mock.Mock]:
    """
    Return a factory that returns mock subrack devices for use in testing.

    Each mock device will mock a powered-on APIU.

    :return: a factory that returns a mock APIU device for use in
        testing.
    """
    builder = MockDeviceBuilder()
    builder.set_state(tango.DevState.ON)
    builder.add_attribute("adminMode", AdminMode.ONLINE)
    builder.add_attribute("healthState", HealthState.OK)
    return builder


@pytest.fixture()
def mock_tile_factory() -> Callable[[], unittest.mock.Mock]:
    """
    Return a factory that returns mock tile devices for use in testing.

    Each mock device will mock a powered-on tile.

    :return: a mock tile device for use in testing.
    """
    builder = MockDeviceBuilder()
    builder.set_state(tango.DevState.ON)
    builder.add_result_command("SetPointingDelay", ResultCode.OK)
    builder.add_attribute("adminMode", AdminMode.ONLINE)
    builder.add_attribute("healthState", HealthState.OK)
    return builder


@pytest.fixture()
def initial_mocks(
    mock_apiu_factory: Callable[[], unittest.mock.Mock],
    mock_antenna_factory: Callable[[], unittest.mock.Mock],
    mock_subarray_beam_factory: Callable[[], unittest.mock.Mock],
    mock_station_beam_factory: Callable[[], unittest.mock.Mock],
    mock_subrack_factory: Callable[[], unittest.mock.Mock],
    mock_tile_factory: Callable[[], unittest.mock.Mock],
) -> dict[str, unittest.mock.Mock]:
    """
    Return a specification of the mock devices to be set up in the Tango test harness.

    This is a pytest fixture that can be used to inject pre-build mock
    devices into the Tango test harness at specified FQDNs.

    :param mock_apiu_factory: a factory that returns a mock apiu device
    :param mock_antenna_factory: a factory that returns a mock antenna
        device
    :param mock_subarray_beam_factory: a factory that returns a mock
        subarray beam device
    :param mock_station_beam_factory: a factory that returns a mock
        station beam device
    :param mock_subrack_factory: a factory that returns a mock subrack
        device
    :param mock_tile_factory: a factory that returns a mock tile device

    :return: specification of the mock devices to be set up in the Tango
        test harness.
    """
    return {
        "low-mccs/antenna/000001": mock_antenna_factory(),
        "low-mccs/antenna/000002": mock_antenna_factory(),
        "low-mccs/antenna/000003": mock_antenna_factory(),
        "low-mccs/antenna/000004": mock_antenna_factory(),
        "low-mccs/antenna/000005": mock_antenna_factory(),
        "low-mccs/antenna/000006": mock_antenna_factory(),
        "low-mccs/antenna/000007": mock_antenna_factory(),
        "low-mccs/antenna/000008": mock_antenna_factory(),
        "low-mccs/apiu/001": mock_apiu_factory(),
        "low-mccs/apiu/002": mock_apiu_factory(),
        "low-mccs/subarraybeam/01": mock_subarray_beam_factory(),
        "low-mccs/subarraybeam/02": mock_subarray_beam_factory(),
        "low-mccs/subrack/01": mock_subrack_factory(),
        "low-mccs/tile/0001": mock_tile_factory(),
        "low-mccs/tile/0002": mock_tile_factory(),
        "low-mccs/tile/0003": mock_tile_factory(),
        "low-mccs/tile/0004": mock_tile_factory(),
        "low-mccs/beam/01": mock_station_beam_factory(),
        "low-mccs/beam/02": mock_station_beam_factory(),
        "low-mccs/beam/03": mock_station_beam_factory(),
        "low-mccs/beam/04": mock_station_beam_factory(),
    }


class TestMccsIntegration:
    """Integration test cases for the Mccs device classes."""

    @pytest.mark.timeout(19)
    def test_controller_allocate_subarray(
        self: TestMccsIntegration,
        tango_harness: TangoHarness,
        state_changed_callback_factory: Callable[[], MockChangeEventCallback],
        obs_state_changed_callback_factory: Callable[[], MockChangeEventCallback],
    ) -> None:
        """
        Test that an MccsController can allocate resources to an MccsSubarray.

        :param tango_harness: a test harness for tango devices
        :param state_changed_callback_factory: a factory for callbacks
            to be used to subscribe to change events on device state
        :param obs_state_changed_callback_factory: a factory for callbacks
            to be used to subscribe to change events on device obs state
        """
        controller = tango_harness.get_device("low-mccs/control/control")
        subarray_1 = tango_harness.get_device("low-mccs/subarray/01")
        subarray_2 = tango_harness.get_device("low-mccs/subarray/02")
        station_1 = tango_harness.get_device("low-mccs/station/001")
        station_2 = tango_harness.get_device("low-mccs/station/002")

        controller_device_state_changed_callback = state_changed_callback_factory()
        subarray_1_device_state_changed_callback = state_changed_callback_factory()
        subarray_2_device_state_changed_callback = state_changed_callback_factory()
        station_1_device_state_changed_callback = state_changed_callback_factory()
        station_2_device_state_changed_callback = state_changed_callback_factory()
        subarray_1_obs_state_changed_callback = obs_state_changed_callback_factory()

        controller.add_change_event_callback(
            "state", controller_device_state_changed_callback
        )
        subarray_1.add_change_event_callback(
            "state", subarray_1_device_state_changed_callback
        )
        subarray_2.add_change_event_callback(
            "state", subarray_2_device_state_changed_callback
        )
        station_1.add_change_event_callback(
            "state", station_1_device_state_changed_callback
        )
        station_2.add_change_event_callback(
            "state", station_2_device_state_changed_callback
        )
        # register a callback so we can block on obsState changes
        # instead of sleeping
        subarray_1.add_change_event_callback(
            "obsState", subarray_1_obs_state_changed_callback
        )

        # It seems that we need a fairly long sleep to allow time for all the relevant events
        # to be pushed by the polled PushChanges command
        time.sleep(0.2)

        # TODO: This occansionally segfaults with warnings from Tango stating that
        # the event channel is not responding. Find out why.
        """controller_device_state_changed_callback.assert_last_change_event(
            tango.DevState.DISABLE
        )
        subarray_1_device_state_changed_callback.assert_last_change_event(
            tango.DevState.DISABLE
        )
        subarray_2_device_state_changed_callback.assert_last_change_event(
            tango.DevState.DISABLE
        )

        station_1_device_state_changed_callback.assert_last_change_event(
            tango.DevState.DISABLE
        )

        station_2_device_state_changed_callback.assert_last_change_event(
            tango.DevState.DISABLE
        )"""

        controller.adminMode = AdminMode.ONLINE
        subarray_1.adminMode = AdminMode.ONLINE
        subarray_2.adminMode = AdminMode.ONLINE
        station_1.adminMode = AdminMode.ONLINE
        station_2.adminMode = AdminMode.ONLINE

        # It seems that we need a fairly long sleep to allow time for all the relevant events
        # to be pushed by the polled PushChanges command
        time.sleep(0.2)

        # Subracks are mocked ON. APIUs, Antennas and Tiles are mocked ON, so stations
        # will be ON too. Therefore controller will already be ON.

        # TODO: This occansionally segfaults with warnings from Tango stating that
        # the event channel is not responding. Find out why.
        """subarray_1_device_state_changed_callback.assert_last_change_event(
            tango.DevState.ON
        )
        subarray_2_device_state_changed_callback.assert_last_change_event(
            tango.DevState.ON
        )
        station_1_device_state_changed_callback.assert_last_change_event(
            tango.DevState.ON
        )
        station_2_device_state_changed_callback.assert_last_change_event(
            tango.DevState.ON
        )
        controller_device_state_changed_callback.assert_last_change_event(
            tango.DevState.ON
        )"""

        assert subarray_1.state() == tango.DevState.ON
        assert subarray_2.state() == tango.DevState.ON
        assert station_1.state() == tango.DevState.ON
        assert station_2.state() == tango.DevState.ON

        # TODO: Subarray is ON, and resources are all healthy, but there's a small
        # chance that the controller hasn't yet received all the events telling it so.
        # We need a better way to handle this than taking a short nap with our fingers
        # crossed.
        time.sleep(0.4)

        subarray_1_obs_state_changed_callback.assert_last_change_event(ObsState.EMPTY)
        assert subarray_1.obsState == ObsState.EMPTY

        # check initial state
        assert subarray_1.stationFQDNs is None
        assert subarray_2.stationFQDNs is None

        # TODO: allocate command not executed in resource manager
        # allocate station_1 to subarray_1
        ([result_code], _) = call_with_json(
            controller.Allocate,
            subarray_id=1,
            station_ids=[[1]],
            subarray_beam_ids=[1],
            channel_blocks=[2],
        )
        assert result_code == ResultCode.QUEUED

        time.sleep(0.2)
        subarray_1_obs_state_changed_callback.assert_last_change_event(ObsState.IDLE)
        assert subarray_1.obsState == ObsState.IDLE

        # check that station_1 and only station_1 is allocated
        station_fqdns: Iterable = cast(Iterable, subarray_1.stationFQDNs)
        assert list(station_fqdns) == [station_1.dev_name()]
        assert subarray_2.stationFQDNs is None

        # allocating station_1 to subarray 2 should fail, because it is already
        # allocated to subarray 1
        result_code, unique_id = call_with_json(
            controller.Allocate,
            subarray_id=2,
            station_ids=[[1]],
            subarray_beam_ids=[1],
            channel_blocks=[2],
        )

        time.sleep(0.2)
        assert [controller.longRunningCommandResult[0]] == unique_id

        # A subarray/station beam cannot be allocated to multiple subarrays.
        assert (
            "The allocate command has failed with the exception: Cannot allocate resources:"
            and "subarraybeam"
            or "beam" in controller.longRunningCommandResult[1]
        )

        # check no side-effects
        # station_fqdns = cast(Iterable, subarray_1.stationFQDNs)
        assert list(station_fqdns) == [station_1.dev_name()]
        assert subarray_2.stationFQDNs is None

        # TODO: We have a problem with the obs state during the 2nd Allocate command.
        #       The subarray complains with:
        #       "Action component_resourced is not allowed in obs state RESOURCING."
        #       Technical debt: Fix this later.
        # allocating stations 1 and 2 to subarray 1 should succeed,
        # ecause the already allocated station is allocated to the same
        # subarray, BUT we must remember that the subarray cannot reallocate
        # the same subarray_beam.
        # ([result_code], [_]) = call_with_json(
        #     controller.Allocate,
        #     subarray_id=1,
        #     station_ids=[[1, 2]],
        #     subarray_beam_ids=[2],
        #     channel_blocks=[2],
        # )
        # assert result_code == ResultCode.OK
        # subarray_1_obs_state_changed_callback.assert_last_change_event(
        #     ObsState.IDLE
        # )
        # assert subarray_1.obsState == ObsState.IDLE

        # station_fqdns = cast(Iterable, subarray_1.stationFQDNs)
        # assert list(station_fqdns) == [
        #     station_1.dev_name(),
        #     station_2.dev_name(),
        # ]
        # assert subarray_2.stationFQDNs is None

    # TODO This test is an extension from the test above, which is only
    #      half working due to an obs state issue with subarray.
    @pytest.mark.xfail(reason="obs state issue with subarray")
    def test_controller_release_subarray(
        self: TestMccsIntegration,
        tango_harness: TangoHarness,
        state_changed_callback_factory: Callable[[], MockChangeEventCallback],
    ) -> None:
        """
        Test that an MccsController can release the resources of an MccsSubarray.

        :param tango_harness: a test harness for tango devices
        :param state_changed_callback_factory: a factory for callbacks
            to be used to subscribe to change events on device state
        """
        controller = tango_harness.get_device("low-mccs/control/control")
        subarray_1 = tango_harness.get_device("low-mccs/subarray/01")
        subarray_2 = tango_harness.get_device("low-mccs/subarray/02")
        station_1 = tango_harness.get_device("low-mccs/station/001")
        station_2 = tango_harness.get_device("low-mccs/station/002")

        controller_device_state_changed_callback = state_changed_callback_factory()
        subarray_1_device_state_changed_callback = state_changed_callback_factory()
        subarray_2_device_state_changed_callback = state_changed_callback_factory()
        station_1_device_state_changed_callback = state_changed_callback_factory()
        station_2_device_state_changed_callback = state_changed_callback_factory()

        controller.add_change_event_callback(
            "state", controller_device_state_changed_callback
        )
        subarray_1.add_change_event_callback(
            "state", subarray_1_device_state_changed_callback
        )
        subarray_2.add_change_event_callback(
            "state", subarray_2_device_state_changed_callback
        )
        station_1.add_change_event_callback(
            "state", station_1_device_state_changed_callback
        )
        station_2.add_change_event_callback(
            "state", station_2_device_state_changed_callback
        )

        controller_device_state_changed_callback.assert_next_change_event(
            tango.DevState.DISABLE
        )
        subarray_1_device_state_changed_callback.assert_next_change_event(
            tango.DevState.DISABLE
        )
        subarray_2_device_state_changed_callback.assert_next_change_event(
            tango.DevState.DISABLE
        )

        station_1_device_state_changed_callback.assert_next_change_event(
            tango.DevState.DISABLE
        )

        station_2_device_state_changed_callback.assert_next_change_event(
            tango.DevState.DISABLE
        )

        controller.adminMode = AdminMode.ONLINE
        subarray_1.adminMode = AdminMode.ONLINE
        subarray_2.adminMode = AdminMode.ONLINE
        station_1.adminMode = AdminMode.ONLINE
        station_2.adminMode = AdminMode.ONLINE

        # Subracks are mocked ON. APIUs, Antennas and Tiles are mocked ON, so stations
        # will be ON too. Therefore controller will already be ON.
        controller_device_state_changed_callback.assert_last_change_event(
            tango.DevState.ON
        )
        subarray_1_device_state_changed_callback.assert_next_change_event(
            tango.DevState.UNKNOWN
        )
        subarray_1_device_state_changed_callback.assert_next_change_event(
            tango.DevState.ON
        )
        subarray_2_device_state_changed_callback.assert_next_change_event(
            tango.DevState.UNKNOWN
        )
        subarray_2_device_state_changed_callback.assert_next_change_event(
            tango.DevState.ON
        )

        # TODO: Subarray is ON, and resources are all healthy, but there's a small
        # chance that the controller hasn't yet received all the events telling it so.
        # We need a better way to handle this than taking a short nap with our fingers
        # crossed.
        time.sleep(1.0)

        assert subarray_1.obsState == ObsState.EMPTY

        # allocate station_1 to subarray_1
        ([result_code], [_]) = call_with_json(
            controller.Allocate,
            subarray_id=1,
            station_ids=[[1]],
            subarray_beam_ids=[1],
            channel_blocks=[1],
        )
        assert result_code == ResultCode.OK
        assert subarray_1.obsState == ObsState.IDLE

        # allocate station 2 to subarray 2
        ([result_code], [_]) = call_with_json(
            controller.Allocate,
            subarray_id=2,
            station_ids=[[2]],
            subarray_beam_ids=[2],
            channel_blocks=[2],
        )
        assert result_code == ResultCode.QUEUED

        # TODO: It's a bit rubbish that we can't detect when this
        # command is complete. For now, just increase the delay.
        time.sleep(0.3)

        # check initial state
        assert list(subarray_1.stationFQDNs) == [station_1.dev_name()]
        assert list(subarray_2.stationFQDNs) == [station_2.dev_name()]

        # release resources of subarray_2
        ([result_code], [_]) = call_with_json(
            controller.Release, subarray_id=2, release_all=True
        )
        assert result_code == ResultCode.QUEUED

        # TODO: It's a bit rubbish that we can't detect when this
        # command is complete. For now, just increase the delay.
        time.sleep(0.3)

        # check
        assert list(subarray_1.stationFQDNs) == [station_1.dev_name()]
        assert subarray_2.stationFQDNs is None

        # releasing resources of unresourced subarray_2 should succeed (as redundant)
        # i.e. OK not QUEUED because it's quick
        ([result_code], [_]) = call_with_json(
            controller.Release, subarray_id=2, release_all=True
        )
        assert result_code == ResultCode.OK

        # check no side-effect to failed release
        assert list(subarray_1.stationFQDNs) == [station_1.dev_name()]
        assert subarray_2.stationFQDNs is None

        # release resources of subarray_1
        ([result_code], [_]) = call_with_json(
            controller.Release, subarray_id=1, release_all=True
        )
        assert result_code == ResultCode.QUEUED

        time.sleep(0.1)

        assert subarray_1.stationFQDNs is None
        assert subarray_2.stationFQDNs is None
