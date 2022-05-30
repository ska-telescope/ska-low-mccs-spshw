# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests of the controller component manager."""
from __future__ import annotations

import json
import time
import unittest.mock

import pytest
import tango
from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import CommunicationStatus, HealthState, PowerState

from ska_low_mccs import MccsDeviceProxy, MccsController
from ska_low_mccs.controller import ControllerComponentManager


@pytest.fixture
def patched_controller_device_class(
    mock_controller_component_manager: ControerComponentManager,
) -> Type[MccsController]:
    """
    Return a station device class, patched with extra methods for testing.

    :param mock_station_component_manager: A fixture that provides a partially mocked component manager
            which has access to the component_state_changed_callback.

    :return: a patched station device class, patched with extra methods
        for testing
    """

    class PatchedControllerDevice(MccsController):
        """
        MccsStation patched with extra commands for testing purposes.

        The extra commands allow us to mock the receipt of obs state
        change events from subservient devices.
        """

        def create_component_manager(
            self: PatchedControllerDevice,
        ) -> ControllerComponentManager:
            """
            Return a partially mocked component manager instead of the usual one.

            :return: a mock component manager
            """
            mock_controller_component_manager._component_state_changed_callback = (
                self.component_state_changed_callback
            )
            mock_station_component_manager._apiu_proxy._component_state_changed_callback = functools.partial(
                mock_station_component_manager._component_state_changed_callback,
                fqdn=mock_station_component_manager._apiu_fqdn,
            )
            for (
                tile_fqdn,
                tile_proxy,
            ) in mock_station_component_manager._tile_proxies.items():
                tile_proxy._component_state_changed_callback = functools.partial(
                    mock_station_component_manager._component_state_changed_callback,
                    fqdn=tile_fqdn,
                )
            for (
                antenna_fqdn,
                antenna_proxy,
            ) in mock_station_component_manager._antenna_proxies.items():
                antenna_proxy._component_state_changed_callback = functools.partial(
                    mock_station_component_manager._component_state_changed_callback,
                    fqdn=antenna_fqdn,
                )

            return mock_controller_component_manager

    return PatchedControllerDevice


@pytest.fixture()
def device_to_load(
    patched_controller_device_class: Type[MccsController],
) -> DeviceToLoadType:
    """
    Fixture that specifies the device to be loaded for testing.

    :param patched_station_device_class: fixture returning an instance of
        a patched station device.

    :return: specification of the device to be loaded
    """
    return {
        "path": "charts/ska-low-mccs/data/configuration.json",
        "package": "ska_low_mccs",
        "device": "controller",
        "proxy": MccsDeviceProxy,
        "patch": patched_controller_device_class,
    }


@pytest.fixture()
def device_under_test(
    tango_harness: TangoHarness,
) -> MccsDeviceProxy:
    """
    Fixture that returns the device under test.

    :param tango_harness: a test harness for Tango devices

    :return: the device under test
    """
    return tango_harness.get_device("low-mccs/control/control")


class TestControllerPowerEvents:
    """Tests of the controller component manager."""

    def test_power_events(
        self: TestControllerComponentManager,
        controller_component_manager: ControllerComponentManager,
    ) -> None:
        """
        Test the controller component manager's management of power mode.

        :param controller_component_manager: the controller component
            manager under test.
        """
        controller_component_manager.start_communicating()
        time.sleep(0.1)
        assert (
            controller_component_manager._communication_state
            == CommunicationStatus.ESTABLISHED
        )
        #         print(controller_component_manager._component_state_changed_callback.get_whole_queue())
        #         controller_component_manager._component_state_changed_callback.assert_next_call_with_keys(
        #             {"power_state": PowerState.UNKNOWN})
        # assert controller_component_manager.power_state == PowerState.UNKNOWN

        for station_proxy in controller_component_manager._stations.values():
            station_proxy._device_state_changed(
                "state", tango.DevState.OFF, tango.AttrQuality.ATTR_VALID
            )
            # assert controller_component_manager.power_state == PowerState.UNKNOWN
            # controller_component_manager.component_state_changed_callback.assert_not_called()
        for subrack_proxy in controller_component_manager._subracks.values():
            subrack_proxy._device_state_changed(
                "state", tango.DevState.OFF, tango.AttrQuality.ATTR_VALID
            )
        controller_component_manager._component_state_changed_callback.assert_next_call_with_keys(
            {"power_state": PowerState.OFF}
        )
        assert controller_component_manager.power_state == PowerState.OFF


#         # generate fake events from mock subservient devices
#         for fqdn in controller_component_manager._stations.keys():
#             controller_component_manager._component_state_changed_callback(
#                 {"power_state": PowerState.ON},
#                 fqdn=fqdn,
#             )
#         for fqdn in controller_component_manager._subracks.keys():
#             controller_component_manager._component_state_changed_callback(
#                 {"power_state": PowerState.ON},
#                 fqdn=fqdn,
#             )
#         controller_component_manager._component_state_changed_callback.assert_next_call_with_keys(
#                      {"power_state": PowerState.ON})
#
#         for station_proxy in controller_component_manager._stations.values():
#             station_proxy._device_state_changed(
#                 "state", tango.DevState.OFF, tango.AttrQuality.ATTR_VALID
#             )
#             station_proxy.component_state_changed_callback(
#                 {"power_state": PowerState.OFF}
#             )
#             print(station_proxy.component_state_changed_callback)
#             station_proxy._device_state_changed.assert_next_call_with_keys(
#                 {'power_state': PowerState.OFF}, fqdn=station_proxy._fqdn)
#
#         for subrack_proxy in controller_component_manager._subracks.values():
#             #             subrack_proxy._device_state_changed(
#             #                 "state", tango.DevState.OFF, tango.AttrQuality.ATTR_VALID
#             #             )
#             subrack_proxy.component_state_changed_callback(
#                 {"power_state": PowerState.OFF}
#             )
#         # print(component_state_changed_callback.get_next_call_with_keys("power_state"))
#         # controller_component_manager.power_state = PowerState.OFF
#         assert controller_component_manager.power_state == PowerState.OFF
