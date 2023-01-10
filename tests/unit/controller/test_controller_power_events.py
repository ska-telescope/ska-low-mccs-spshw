# type: ignore
# pylint: skip-file
# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests of the controller component manager."""
from __future__ import annotations

import functools
import time
from typing import Type

import pytest
import tango
from ska_control_model import CommunicationStatus, PowerState
from ska_low_mccs_common import MccsDeviceProxy
from ska_low_mccs_common.testing.tango_harness import DeviceToLoadType, TangoHarness

from ska_low_mccs import MccsController
from ska_low_mccs.controller import ControllerComponentManager


@pytest.fixture
def patched_controller_device_class(
    mock_controller_component_manager: ControllerComponentManager,
) -> Type[MccsController]:
    """
    Return a station device class, patched with extra methods for testing.

    :param mock_controller_component_manager: A fixture that provides a
        partially mocked component manager which has access to the
        component_state_changed_callback.

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
                self._component_state_changed_callback
            )
            for (
                subrack_fqdn,
                subrack_proxy,
            ) in mock_controller_component_manager._subracks.items():
                subrack_proxy._component_state_changed_callback = functools.partial(
                    mock_controller_component_manager._component_state_changed_callback,
                    fqdn=subrack_fqdn,
                )
            for (
                station_fqdn,
                station_proxy,
            ) in mock_controller_component_manager._stations.items():
                station_proxy._component_state_changed_callback = functools.partial(
                    mock_controller_component_manager._component_state_changed_callback,
                    fqdn=station_fqdn,
                )

            return mock_controller_component_manager

    return PatchedControllerDevice


@pytest.fixture()
def device_to_load(
    patched_controller_device_class: Type[MccsController],
) -> DeviceToLoadType:
    """
    Fixture that specifies the device to be loaded for testing.

    :param patched_controller_device_class: fixture returning an instance of
        a patched controller device.

    :return: specification of the device to be loaded
    """
    return {
        "path": "tests/data/configuration.json",
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
        self: TestControllerPowerEvents,
        device_under_test: MccsDeviceProxy,
        mock_controller_component_manager: ControllerComponentManager,
    ) -> None:
        """
        Test the controller component manager's management of power mode.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param mock_controller_component_manager:  A fixture that provides a
            partially mocked component manager which has access to the
            component_state_changed_callback.
        """
        time.sleep(0.2)
        mock_controller_component_manager.start_communicating()
        time.sleep(0.2)
        assert (
            mock_controller_component_manager._communication_state
            == CommunicationStatus.ESTABLISHED
        )
        time.sleep(0.1)
        assert mock_controller_component_manager.power_state == PowerState.UNKNOWN

        for station_proxy in mock_controller_component_manager._stations.values():
            station_proxy._device_state_changed(
                "state", tango.DevState.OFF, tango.AttrQuality.ATTR_VALID
            )
            assert mock_controller_component_manager.power_state == PowerState.UNKNOWN
        for subrack_proxy in mock_controller_component_manager._subracks.values():
            subrack_proxy._device_state_changed(
                "state", tango.DevState.OFF, tango.AttrQuality.ATTR_VALID
            )
        assert mock_controller_component_manager.power_state == PowerState.OFF
