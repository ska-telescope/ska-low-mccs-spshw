#########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
#########################################################################
"""This module contains the tests of the controller component manager."""
from __future__ import annotations

import json
import time

import unittest.mock

import pytest
import tango

from ska_tango_base.control_model import HealthState, PowerMode

from ska_low_mccs import MccsDeviceProxy
from ska_low_mccs.component import CommunicationStatus
from ska_low_mccs.controller import ControllerComponentManager

from ska_low_mccs.testing.mock import MockCallable


class TestControllerComponentManager:
    """Tests of the controller component manager."""

    def test_communication(
        self: TestControllerComponentManager,
        controller_component_manager: ControllerComponentManager,
        communication_status_changed_callback: MockCallable,
    ) -> None:
        """
        Test the controller component manager's management of communication.

        :param controller_component_manager: the controller component
            manager under test.
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        """
        assert (
            controller_component_manager.communication_status
            == CommunicationStatus.DISABLED
        )

        controller_component_manager.start_communicating()
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.ESTABLISHED
        )
        assert (
            controller_component_manager.communication_status
            == CommunicationStatus.ESTABLISHED
        )

        controller_component_manager.stop_communicating()
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.DISABLED
        )
        assert (
            controller_component_manager.communication_status
            == CommunicationStatus.DISABLED
        )

    def test_power_commands(
        self: TestControllerComponentManager,
        controller_component_manager: ControllerComponentManager,
        station_fqdns: list[str],
        station_proxies: list[unittest.mock.Mock],
        subrack_fqdns: list[str],
        subrack_proxies: list[unittest.mock.Mock],
    ) -> None:
        """
        Test that the power commands work as expected.

        :param controller_component_manager: the controller component
            manager under test.
        :param station_fqdns: FQDNS of station devices
        :param station_proxies: list of proxies to MCCS station devices
        :param subrack_fqdns: FQDNS of subrack devices
        :param subrack_proxies: list of proxies to MCCS subrack devices
        """
        controller_component_manager.start_communicating()
        time.sleep(0.1)
        controller_component_manager.on()
        for proxy in subrack_proxies:
            proxy.On.assert_next_call()

        # pretend to receive events
        for fqdn in subrack_fqdns:
            controller_component_manager._subrack_power_mode_changed(fqdn, PowerMode.ON)
        for proxy in station_proxies:
            proxy.On.assert_next_call()

        controller_component_manager.off()
        for proxy in station_proxies:
            proxy.Off.assert_next_call()

        # pretend to receive events
        for fqdn in station_fqdns:
            controller_component_manager._station_power_mode_changed(
                fqdn, PowerMode.OFF
            )
        for proxy in subrack_proxies:
            proxy.Off.assert_next_call()

    def test_power_events(
        self: TestControllerComponentManager,
        controller_component_manager: ControllerComponentManager,
        component_power_mode_changed_callback: MockCallable,
    ) -> None:
        """
        Test the controller component manager's management of power mode.

        :param controller_component_manager: the controller component
            manager under test.
        :param component_power_mode_changed_callback: callback to be
            called when the component power mode changes
        """
        controller_component_manager.start_communicating()
        time.sleep(0.1)
        component_power_mode_changed_callback.assert_next_call(PowerMode.UNKNOWN)
        assert controller_component_manager.power_mode == PowerMode.UNKNOWN

        for station_proxy in controller_component_manager._stations.values():
            station_proxy._device_state_changed(
                "state", tango.DevState.OFF, tango.AttrQuality.ATTR_VALID
            )
            assert controller_component_manager.power_mode == PowerMode.UNKNOWN
            component_power_mode_changed_callback.assert_not_called()
        for subrack_proxy in controller_component_manager._subracks.values():
            subrack_proxy._device_state_changed(
                "state", tango.DevState.OFF, tango.AttrQuality.ATTR_VALID
            )
        component_power_mode_changed_callback.assert_next_call(PowerMode.OFF)
        assert controller_component_manager.power_mode == PowerMode.OFF

    def test_subarray_allocation(
        self: TestControllerComponentManager,
        controller_component_manager: ControllerComponentManager,
        subarray_proxies: dict[str, MccsDeviceProxy],
    ) -> None:
        """
        Test for subarray allocation.

        That:

        * If we try to allocate resources to a subarray before we the
          controller component manager has been turned on, the attempt
          will fail.

        * If we try to allocate resources to an unknown subarray, the
          allocation will be rejected

        * If we try to allocate unknown resources to a known subarray,
          the allocation will be rejected

        * If we try to allocate known resources to a known subarray, the
          allocation will be rejected until the controller component
          manager learns that the subarray is online

        * If we try to allocate known resources to an online subarray,
          the allocation will be rejected until the controller component
          manager learns that the resources are healthy.

        * If we try to allocate healthy resources to an online subarray,
          the allocation will succeed, and the subarray will be assigned
          the resources.

        :param controller_component_manager: the controller component
            manager under test.
        :param subarray_proxies: proxies to the this controller's
            subarrays.
        """
        controller_component_manager.start_communicating()
        time.sleep(0.2)

        # Subarray is an always-on device, so this should always be received after we
        # establish communication with it.
        controller_component_manager._subarrays[
            "low-mccs/subarray/01"
        ]._device_state_changed(
            "state", tango.DevState.ON, tango.AttrQuality.ATTR_VALID
        )
        controller_component_manager._subarrays[
            "low-mccs/subarray/02"
        ]._device_state_changed(
            "state", tango.DevState.ON, tango.AttrQuality.ATTR_VALID
        )
        controller_component_manager._subarray_beams[
            "low-mccs/subarraybeam/01"
        ]._device_state_changed(
            "state", tango.DevState.ON, tango.AttrQuality.ATTR_VALID
        )
        controller_component_manager._subarray_beams[
            "low-mccs/subarraybeam/02"
        ]._device_state_changed(
            "state", tango.DevState.ON, tango.AttrQuality.ATTR_VALID
        )
        controller_component_manager._station_beams[
            "low-mccs/beam/01"
        ]._device_state_changed(
            "state", tango.DevState.ON, tango.AttrQuality.ATTR_VALID
        )
        controller_component_manager._station_beams[
            "low-mccs/beam/02"
        ]._device_state_changed(
            "state", tango.DevState.ON, tango.AttrQuality.ATTR_VALID
        )
        controller_component_manager._station_beams[
            "low-mccs/beam/03"
        ]._device_state_changed(
            "state", tango.DevState.ON, tango.AttrQuality.ATTR_VALID
        )
        controller_component_manager._station_beams[
            "low-mccs/beam/04"
        ]._device_state_changed(
            "state", tango.DevState.ON, tango.AttrQuality.ATTR_VALID
        )
        controller_component_manager._station_beam_health_changed(
            "low-mccs/beam/01",
            HealthState.OK,
        )
        controller_component_manager._station_beam_health_changed(
            "low-mccs/beam/02",
            HealthState.OK,
        )
        controller_component_manager._station_beam_health_changed(
            "low-mccs/beam/03",
            HealthState.OK,
        )
        controller_component_manager._station_beam_health_changed(
            "low-mccs/beam/04",
            HealthState.OK,
        )

        with pytest.raises(ConnectionError, match="Component is not turned on"):
            controller_component_manager.allocate(
                99,  # unknown subarray id
                [["low-mccs/station/001"]],
                ["low-mccs/subarraybeam/02"],
                [3, 4],
            )

        # Fake events to tell this controller component manager that its devices are all
        # turned on, so that it decided that it is turned on.
        for station_proxy in controller_component_manager._stations.values():
            station_proxy._device_state_changed(
                "state", tango.DevState.ON, tango.AttrQuality.ATTR_VALID
            )
        for subrack_proxy in controller_component_manager._subracks.values():
            subrack_proxy._device_state_changed(
                "state", tango.DevState.ON, tango.AttrQuality.ATTR_VALID
            )

        with pytest.raises(ValueError, match="Unsupported resources"):
            controller_component_manager.allocate(
                1,
                [["low-mccs/station/unknown"]],
                ["low-mccs/subarraybeam/02"],
                [3, 4],
            )

        with pytest.raises(ValueError, match="Allocatee is unready"):
            controller_component_manager.allocate(
                1,
                [["low-mccs/station/001"]],
                ["low-mccs/subarraybeam/02"],
                [3, 4],
            )

        controller_component_manager._subarray_health_changed(
            "low-mccs/subarray/01",
            HealthState.OK,
        )
        controller_component_manager._subarray_health_changed(
            "low-mccs/subarray/02",
            HealthState.OK,
        )

        with pytest.raises(ValueError, match="Cannot allocate unhealthy resources"):
            controller_component_manager.allocate(
                1,
                [["low-mccs/station/001"]],
                ["low-mccs/subarraybeam/02"],
                [3, 4],
            )

        controller_component_manager._station_health_changed(
            "low-mccs/station/001",
            HealthState.OK,
        )

        with pytest.raises(ValueError, match="Cannot allocate unhealthy resources"):
            controller_component_manager.allocate(
                1,
                [["low-mccs/station/001"]],
                ["low-mccs/subarraybeam/02"],
                [3, 4],
            )

        controller_component_manager._subarray_beam_health_changed(
            "low-mccs/subarraybeam/02",
            HealthState.OK,
        )

        controller_component_manager.allocate(
            1,
            [["low-mccs/station/001"]],
            ["low-mccs/subarraybeam/02"],
            [3, 4],
        )

        time.sleep(0.1)
        subarray_proxies[
            "low-mccs/subarray/01"
        ].AssignResources.assert_called_once_with(
            json.dumps(
                {
                    "stations": ["low-mccs/station/001"],
                    "subarray_beams": ["low-mccs/subarraybeam/02"],
                    "station_beams": ["low-mccs/beam/04"],
                    "channel_blocks": [3, 4],
                }
            )
        )

        controller_component_manager.deallocate_all(1)
        time.sleep(0.1)
        subarray_proxies[
            "low-mccs/subarray/01"
        ].ReleaseAllResources.assert_called_once_with()

        controller_component_manager.allocate(
            2,
            [["low-mccs/station/001"]],
            ["low-mccs/subarraybeam/02"],
            [3, 4],
        )

        time.sleep(0.1)
        subarray_proxies[
            "low-mccs/subarray/02"
        ].AssignResources.assert_called_once_with(
            json.dumps(
                {
                    "stations": ["low-mccs/station/001"],
                    "subarray_beams": ["low-mccs/subarraybeam/02"],
                    "station_beams": ["low-mccs/beam/04"],
                    "channel_blocks": [3, 4],
                }
            )
        )

        controller_component_manager.deallocate_all(2)
        time.sleep(0.1)
        with pytest.raises(
            ValueError, match="No free resources of type: channel_blocks."
        ):
            controller_component_manager.allocate(
                2,
                [["low-mccs/station/001"]],
                ["low-mccs/subarraybeam/02"],
                [100],
            )

        controller_component_manager.restart_subarray("low-mccs/subarray/02")
        time.sleep(0.1)
        subarray_proxies["low-mccs/subarray/02"].Restart.assert_called_once_with()
