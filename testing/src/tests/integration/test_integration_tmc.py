# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains integration tests of interactions between TMC and MCCS."""
from __future__ import annotations

import json
import time
import unittest
from typing import Callable

import pytest
import tango
from ska_low_mccs_common import MccsDeviceProxy
from ska_low_mccs_common.testing.mock import MockChangeEventCallback, MockDeviceBuilder
from ska_low_mccs_common.testing.tango_harness import DevicesToLoadType, TangoHarness
from ska_low_mccs_common.utils import call_with_json
from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import AdminMode, HealthState, ObsState, PowerState
from tango.server import attribute, command

from ska_low_mccs import MccsController, MccsStation


@pytest.fixture()
def patched_station_device_class() -> type[MccsStation]:
    """
    Return a station device class, patched with extra commands for testing.

    :return: a station device class, patched with extra commands for
        testing
    """

    class PatchedStationDevice(MccsStation):
        """
        MccsStation patched with extra commands for testing purposes.

        The extra commands allow us to mock the receipt of state change
        event from subservient devices.
        """

        @command(dtype_in=int)
        def FakeSubservientDevicesPowerState(
            self: PatchedStationDevice, power_state: int
        ) -> None:
            power_state = PowerState(power_state)
            with self.component_manager._power_state_lock:
                self.component_manager._apiu_power_state = power_state
                for fqdn in self.component_manager._tile_power_states:
                    self.component_manager._tile_power_states[fqdn] = power_state
                for fqdn in self.component_manager._antenna_power_states:
                    self.component_manager._antenna_power_states[fqdn] = power_state
            self.component_manager._evaluate_power_state()

    return PatchedStationDevice


@pytest.fixture()
def patched_controller_device_class() -> type[MccsController]:
    """
    Return a controller device class, patched with extra commands for testing.

    :return: a controller device class, patched with extra commands for
        testing
    """

    class PatchedControllerDevice(MccsController):
        """MccsController patched to allow for testing of controller resource health."""

        @attribute(dtype="str")
        def resourcesHealthy(self: MccsController) -> str:
            """
            Read the healthyness of the controller's resources.

            :return: a string representing a dictionary containing whether or not
                each resource is healthy.
            """
            return json.dumps(
                self.component_manager._resource_manager._resource_manager._healthy
            )

    return PatchedControllerDevice


@pytest.fixture()
def devices_to_load(
    patched_station_device_class: MccsStation,
    patched_controller_device_class: MccsController,
) -> DevicesToLoadType:
    """
    Fixture that specifies the devices to be loaded for testing.

    :param patched_station_device_class: a station device class that has
        been patched with extra commands to support testing
    :param patched_controller_device_class: a controller device class that has
        been patched with extra commands to support testing
    :return: specification of the devices to be loaded
    """
    # TODO: Once https://github.com/tango-controls/cppTango/issues/816 is resolved, we
    # should reinstate the APIUs and antennas in these tests.
    return {
        "path": "charts/ska-low-mccs/data/configuration.json",
        "package": "ska_low_mccs",
        "devices": [
            {
                "name": "controller",
                "proxy": MccsDeviceProxy,
                "patch": patched_controller_device_class,
            },
            {"name": "subarray_01", "proxy": MccsDeviceProxy},
            {"name": "subarray_02", "proxy": MccsDeviceProxy},
            {
                "name": "station_001",
                "proxy": MccsDeviceProxy,
                "patch": patched_station_device_class,
            },
            {
                "name": "station_002",
                "proxy": MccsDeviceProxy,
                "patch": patched_station_device_class,
            },
            {"name": "subrack_01", "proxy": MccsDeviceProxy},
            {"name": "subarraybeam_01", "proxy": MccsDeviceProxy},
            {"name": "subarraybeam_02", "proxy": MccsDeviceProxy},
            {"name": "subarraybeam_03", "proxy": MccsDeviceProxy},
            {"name": "subarraybeam_04", "proxy": MccsDeviceProxy},
        ],
    }


@pytest.fixture()
def mock_apiu_factory() -> Callable[[], unittest.mock.Mock]:
    """
    Return a factory that returns mock APIU devices for use in testing.

    :return: a factory that returns mock APIU devices for use in testing
    """
    builder = MockDeviceBuilder()
    builder.set_state(tango.DevState.OFF)
    builder.add_attribute("adminMode", AdminMode.ONLINE)
    builder.add_result_command("On", ResultCode.OK)
    return builder


@pytest.fixture()
def mock_antenna_factory() -> Callable[[], unittest.mock.Mock]:
    """
    Return a factory that returns mock antenna devices for use in testing.

    :return: a factory that returns mock antenna devices for use in
        testing
    """
    builder = MockDeviceBuilder()
    builder.set_state(tango.DevState.OFF)
    builder.add_attribute("adminMode", AdminMode.ONLINE)
    builder.add_result_command("On", ResultCode.OK)
    return builder


@pytest.fixture()
def mock_tile_factory() -> Callable[[], unittest.mock.Mock]:
    """
    Return a factory that returns mock tile devices for use in testing.

    :return: a factory that returns mock tile devices for use in
        testing
    """
    builder = MockDeviceBuilder()
    builder.set_state(tango.DevState.OFF)
    builder.add_attribute("adminMode", AdminMode.ONLINE)
    builder.add_result_command("On", ResultCode.OK)
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
def initial_mocks(
    mock_apiu_factory: Callable[[], unittest.mock.Mock],
    mock_antenna_factory: Callable[[], unittest.mock.Mock],
    mock_tile_factory: Callable[[], unittest.mock.Mock],
    mock_station_beam_factory: Callable[[], unittest.mock.Mock],
) -> dict[str, unittest.mock.Mock]:
    """
    Return a specification of the mock devices to be set up in the Tango test harness.

    This is a pytest fixture that can be used to inject pre-build mock
    devices into the Tango test harness at specified FQDNs.

    :param mock_apiu_factory: a factory that returns a mock APIU device
        each time it is called
    :param mock_antenna_factory: a factory that returns a mock antenna
        device each time it is called
    :param mock_tile_factory: a factory that returns a mock tile device
        each time it is called
    :param mock_station_beam_factory: a factory that returns a mock station beam device
        each time it is called

    :return: specification of the mock devices to be set up in the Tango
        test harness.
    """
    return {
        "low-mccs/apiu/001": mock_apiu_factory(),
        "low-mccs/apiu/002": mock_apiu_factory(),
        "low-mccs/tile/0001": mock_tile_factory(),
        "low-mccs/tile/0002": mock_tile_factory(),
        "low-mccs/tile/0003": mock_tile_factory(),
        "low-mccs/tile/0004": mock_tile_factory(),
        "low-mccs/antenna/000001": mock_antenna_factory(),
        "low-mccs/antenna/000002": mock_antenna_factory(),
        "low-mccs/antenna/000003": mock_antenna_factory(),
        "low-mccs/antenna/000004": mock_antenna_factory(),
        "low-mccs/antenna/000005": mock_antenna_factory(),
        "low-mccs/antenna/000006": mock_antenna_factory(),
        "low-mccs/antenna/000007": mock_antenna_factory(),
        "low-mccs/antenna/000008": mock_antenna_factory(),
        "low-mccs/beam/01": mock_station_beam_factory(),
        "low-mccs/beam/02": mock_station_beam_factory(),
        "low-mccs/beam/03": mock_station_beam_factory(),
        "low-mccs/beam/04": mock_station_beam_factory(),
    }


@pytest.fixture()
def controller(tango_harness: TangoHarness) -> MccsDeviceProxy:
    """
    Return a proxy to the controller.

    :param tango_harness: a test harness for tango devices

    :return: a proxy to the controller.
    """
    return tango_harness.get_device("low-mccs/control/control")


@pytest.fixture()
def subarray_1(tango_harness: TangoHarness) -> MccsDeviceProxy:
    """
    Return a proxy to subarray 1.

    :param tango_harness: a test harness for tango devices

    :return: a proxy to subarray 1.
    """
    return tango_harness.get_device("low-mccs/subarray/01")


@pytest.fixture()
def subarray_2(tango_harness: TangoHarness) -> MccsDeviceProxy:
    """
    Return a proxy to subarray 2.

    :param tango_harness: a test harness for tango devices

    :return: a proxy to subarray 2.
    """
    return tango_harness.get_device("low-mccs/subarray/02")


@pytest.fixture()
def subrack(tango_harness: TangoHarness) -> MccsDeviceProxy:
    """
    Return a proxy to the subrack.

    :param tango_harness: a test harness for tango devices

    :return: a proxy to the subrack.
    """
    return tango_harness.get_device("low-mccs/subrack/01")


@pytest.fixture()
def station_1(tango_harness: TangoHarness) -> MccsDeviceProxy:
    """
    Return a proxy to station 1.

    :param tango_harness: a test harness for tango devices

    :return: a proxy to station 1.
    """
    return tango_harness.get_device("low-mccs/station/001")


@pytest.fixture()
def station_2(tango_harness: TangoHarness) -> MccsDeviceProxy:
    """
    Return a proxy to station 2.

    :param tango_harness: a test harness for tango devices

    :return: a proxy to station 2.
    """
    return tango_harness.get_device("low-mccs/station/002")


@pytest.fixture()
def subarray_beam_1(tango_harness: TangoHarness) -> MccsDeviceProxy:
    """
    Return a proxy to subarray beam 1.

    :param tango_harness: a test harness for tango devices

    :return: a proxy to subarray beam 1.
    """
    return tango_harness.get_device("low-mccs/subarraybeam/01")


@pytest.fixture()
def subarray_beam_2(tango_harness: TangoHarness) -> MccsDeviceProxy:
    """
    Return a proxy to subarray beam 2.

    :param tango_harness: a test harness for tango devices

    :return: a proxy to subarray beam 2.
    """
    return tango_harness.get_device("low-mccs/subarraybeam/02")


@pytest.fixture()
def subarray_beam_3(tango_harness: TangoHarness) -> MccsDeviceProxy:
    """
    Return a proxy to subarray beam 3.

    :param tango_harness: a test harness for tango devices

    :return: a proxy to subarray beam 3
    """
    return tango_harness.get_device("low-mccs/subarraybeam/03")


@pytest.fixture()
def subarray_beam_4(tango_harness: TangoHarness) -> MccsDeviceProxy:
    """
    Return a proxy to subarray beam 4.

    :param tango_harness: a test harness for tango devices

    :return: a proxy to subarray beam 4.
    """
    return tango_harness.get_device("low-mccs/subarraybeam/04")


class TestMccsIntegrationTmc:
    """Integration test cases for interactions between TMC and MCCS device classes."""

    def test_controller_on_off(
        self: TestMccsIntegrationTmc,
        controller: MccsDeviceProxy,
        subarray_1: MccsDeviceProxy,
        subarray_2: MccsDeviceProxy,
        subrack: MccsDeviceProxy,
        station_1: MccsDeviceProxy,
        station_2: MccsDeviceProxy,
        subarray_beam_1: MccsDeviceProxy,
        subarray_beam_2: MccsDeviceProxy,
        subarray_beam_3: MccsDeviceProxy,
        subarray_beam_4: MccsDeviceProxy,
        controller_device_state_changed_callback: MockChangeEventCallback,
        subarray_device_obs_state_changed_callback: MockChangeEventCallback,
        lrc_result_changed_callback: MockChangeEventCallback,
        controller_device_admin_mode_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test that we can turn the controller on.

        :param controller: a proxy to the MCCS controller device
        :param subrack: a proxy to the subrack device
        :param subarray_1: a proxy to subarray 1
        :param subarray_2: a proxy to subarray 2
        :param station_1: a proxy to station 1
        :param station_2: a proxy to station 2
        :param subarray_beam_1: a proxy to subarray beam 1
        :param subarray_beam_2: a proxy to subarray beam 2
        :param subarray_beam_3: a proxy to subarray beam 3
        :param subarray_beam_4: a proxy to subarray beam 4
        :param controller_device_state_changed_callback: a callback to
            be used to subscribe to controller state change
        :param subarray_device_obs_state_changed_callback: a callback to
            be used to subscribe to subarray obs state change
        :param lrc_result_changed_callback: a callback to
            be used to subscribe to device LRC result changes
        :param controller_device_admin_mode_changed_callback:  a callback
            to be used to subscribe to controller admin_mode changes
        """
        time.sleep(0.2)
        assert controller.state() == tango.DevState.DISABLE
        assert subrack.state() == tango.DevState.DISABLE
        assert subarray_1.state() == tango.DevState.DISABLE
        assert subarray_2.state() == tango.DevState.DISABLE
        assert station_1.state() == tango.DevState.DISABLE
        assert station_2.state() == tango.DevState.DISABLE
        assert subarray_beam_1.state() == tango.DevState.DISABLE
        assert subarray_beam_2.state() == tango.DevState.DISABLE
        assert subarray_beam_3.state() == tango.DevState.DISABLE
        assert subarray_beam_4.state() == tango.DevState.DISABLE

        # register a callback so we can block on state changes
        # instead of sleeping
        controller.add_change_event_callback(
            "state", controller_device_state_changed_callback
        )
        controller_device_state_changed_callback.assert_next_change_event(
            tango.DevState.DISABLE
        )

        controller.add_change_event_callback(
            "adminMode",
            controller_device_admin_mode_changed_callback,
        )
        controller_device_admin_mode_changed_callback.assert_next_change_event(
            AdminMode.OFFLINE
        )

        # register a callback so we can block on obsState changes
        # instead of sleeping
        subarray_1.add_change_event_callback(
            "obsState", subarray_device_obs_state_changed_callback
        )
        # subarray_device_obs_state_changed_callback.assert_last_change_event(
        #     ObsState.EMPTY
        # )

        # controller.adminMode = AdminMode.ONLINE
        # time.sleep(0.1)

        subarray_1.adminMode = AdminMode.ONLINE
        subarray_2.adminMode = AdminMode.ONLINE
        subrack.adminMode = AdminMode.ONLINE
        station_1.adminMode = AdminMode.ONLINE
        station_2.adminMode = AdminMode.ONLINE
        subarray_beam_1.adminMode = AdminMode.ONLINE
        subarray_beam_2.adminMode = AdminMode.ONLINE
        subarray_beam_3.adminMode = AdminMode.ONLINE
        subarray_beam_4.adminMode = AdminMode.ONLINE

        time.sleep(0.2)
        controller.adminMode = AdminMode.ONLINE

        time.sleep(0.2)
        controller_device_state_changed_callback.assert_next_change_event(
            tango.DevState.UNKNOWN
        )

        # All resources should be healthy, so check that the controller
        # resource manager's records reflect this
        resources_healthy = json.loads(controller.resourcesHealthy)
        for resource_group_healthy in resources_healthy.values():
            assert all(resource_group_healthy.values())

        # Make the station think it has received events from its APIU,
        # tiles and antennas, telling it they are all OFF. This makes
        # the station transition to OFF, and this flows up to the
        # controller.
        station_1.FakeSubservientDevicesPowerState(PowerState.OFF)
        station_2.FakeSubservientDevicesPowerState(PowerState.OFF)

        controller_device_state_changed_callback.assert_next_change_event(
            tango.DevState.OFF
        )

        assert controller.state() == tango.DevState.OFF
        assert subarray_1.state() == tango.DevState.ON
        assert subarray_2.state() == tango.DevState.ON
        assert subrack.state() == tango.DevState.OFF
        assert station_1.state() == tango.DevState.OFF
        assert station_2.state() == tango.DevState.OFF
        assert subarray_beam_1.state() == tango.DevState.ON
        assert subarray_beam_2.state() == tango.DevState.ON
        assert subarray_beam_3.state() == tango.DevState.ON
        assert subarray_beam_4.state() == tango.DevState.ON

        # TODO: Understand this race condition and resolve it properly
        time.sleep(0.1)

        # Subscribe to controller's LRC result attribute
        controller.add_change_event_callback(
            "longRunningCommandResult",
            lrc_result_changed_callback,
        )
        assert (
            "longRunningCommandResult".casefold()
            in controller._change_event_subscription_ids
        )

        # Message queue length is non-zero so command is queued
        ([result_code], [unique_id]) = controller.On()
        assert result_code == ResultCode.QUEUED
        assert "On" in unique_id

        controller_device_state_changed_callback.assert_next_change_event(
            tango.DevState.UNKNOWN
        )

        # Make the station think it has received events from its APIU,
        # tiles and antennas, telling it they are all ON. This makes
        # the station transition to ON, and this flows up to the
        # controller.
        station_1.FakeSubservientDevicesPowerState(PowerState.ON)
        station_2.FakeSubservientDevicesPowerState(PowerState.ON)

        time.sleep(0.2)
        controller_device_state_changed_callback.assert_last_change_event(
            tango.DevState.ON
        )

        assert controller.state() == tango.DevState.ON
        assert subarray_1.state() == tango.DevState.ON
        assert subarray_2.state() == tango.DevState.ON
        assert station_1.state() == tango.DevState.ON
        assert station_2.state() == tango.DevState.ON

        # TODO: Subarray is ON, and resources are all healthy, but there's a small
        # chance that the controller hasn't yet received all the events telling it so.
        # We need a better way to handle this than taking a short nap with our fingers
        # crossed.
        time.sleep(0.5)

        # check initial state
        assert subarray_1.stationFQDNs is None
        assert subarray_2.stationFQDNs is None

        subarray_device_obs_state_changed_callback.assert_last_change_event(
            ObsState.EMPTY
        )

        # allocate station_1 to subarray_1
        ([result_code], [message]) = call_with_json(
            controller.Allocate,
            subarray_id=1,
            station_ids=[[1, 2]],
            subarray_beam_ids=[1],
            channel_blocks=[2],
        )
        assert result_code == ResultCode.QUEUED
        assert "Allocate" in message

        subarray_device_obs_state_changed_callback.assert_next_change_event(
            ObsState.RESOURCING
        )

        subarray_device_obs_state_changed_callback.assert_next_change_event(
            ObsState.IDLE
        )

        assert subarray_beam_1.state() == tango.DevState.ON
        assert subarray_beam_2.state() == tango.DevState.ON
        assert subarray_beam_3.state() == tango.DevState.ON
        assert subarray_beam_4.state() == tango.DevState.ON

        # TODO: This section of the integration test is too unstable at the moment
        #       We have a combination of Long and short running commands that
        #       are not playing nicely.
        #  time.sleep(0.2)  # TODO: to give subarray beams time to turn on

        # # configure subarray
        # ([result_code], [unique_id]) = call_with_json(
        #     subarray_1.Configure,
        #     stations=[{"station_id": 1}, {"station_id": 2}],
        #     subarray_beams=[
        #         {
        #             "subarray_beam_id": 1,
        #             "station_ids": [1, 2],
        #             "channels": [[0, 8, 1, 1], [8, 8, 2, 1]],
        #             "update_rate": 0.0,
        #             "sky_coordinates": [0.0, 180.0, 0.0, 45.0, 0.0],
        #             "antenna_weights": [1.0, 1.0, 1.0],
        #             "phase_centre": [0.0, 0.0],
        #         }
        #     ],
        # )
        # assert result_code == ResultCode.QUEUED
        # assert "ConfigureCommand" in unique_id

        # subarray_device_obs_state_changed_callback.assert_next_change_event(
        #     ObsState.CONFIGURING
        # )
        # subarray_device_obs_state_changed_callback.assert_next_change_event(
        #     ObsState.READY
        # )

        # ([result_code], [unique_id]) = call_with_json(
        #     subarray_1.Scan, scan_id=1, start_time=4
        # )
        # assert result_code == ResultCode.QUEUED
        # assert "ScanCommand" in unique_id

        # subarray_device_obs_state_changed_callback.assert_next_change_event(
        #     ObsState.SCANNING
        # )

        # ([result_code], [unique_id]) = subarray_1.EndScan()
        # assert result_code == ResultCode.QUEUED
        # assert "EndScanCommand" in unique_id

        # subarray_device_obs_state_changed_callback.assert_next_change_event(
        #     ObsState.READY
        # )

        # ([result_code], [unique_id]) = subarray_1.End()
        # assert result_code == ResultCode.QUEUED
        # assert "EndCommand" in unique_id

        # subarray_device_obs_state_changed_callback.assert_next_change_event(
        #     ObsState.IDLE
        # )

        # TODO: Currently short running, but calls a LRC in Subarray!
        ([result_code], [message]) = call_with_json(
            controller.Release,
            subarray_id=1,
            release_all=True,
        )
        assert result_code == ResultCode.QUEUED
        assert "Release" in message

        subarray_device_obs_state_changed_callback.assert_next_change_event(
            ObsState.RESOURCING
        )
        subarray_device_obs_state_changed_callback.assert_next_change_event(
            ObsState.EMPTY
        )

        ([result_code], [unique_id]) = controller.Off()
        assert result_code == ResultCode.QUEUED
        assert "Off" in unique_id

        devices = [
            controller,
            subarray_1,
            subarray_2,
            subrack,
            station_1,
            station_2,
            subarray_beam_1,
            subarray_beam_2,
            subarray_beam_3,
            subarray_beam_4,
        ]
        self._show_state_of_devices(devices)

        controller_device_state_changed_callback.assert_next_change_event(
            tango.DevState.OFF
        )

    def _show_state_of_devices(
        self: TestMccsIntegrationTmc,
        devices: list[MccsDeviceProxy],
    ) -> None:
        """
        Show the state of the requested devices.

        :param devices: list of MCCS device proxies
        """
        for device in devices:
            print(f"Device: {device.name} = {device.state()}")
