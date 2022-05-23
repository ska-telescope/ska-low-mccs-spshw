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
from ska_tango_base.control_model import CommunicationStatus, HealthState, PowerState

from ska_low_mccs import MccsDeviceProxy
from ska_low_mccs.controller import ControllerComponentManager
from ska_low_mccs.testing.mock import MockCallable
from ska_low_mccs.testing.mock.mock_callable import MockCallable


class TestControllerComponentManager:
    """Tests of the controller component manager."""

    def test_communication(
        self: TestControllerComponentManager,
        controller_component_manager: ControllerComponentManager,
        communication_state_changed_callback: MockCallable,
    ) -> None:
        """
        Test the controller component manager's management of communication.

        :param controller_component_manager: the controller component
            manager under test.
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        """
        assert (
            controller_component_manager.communication_state
            == CommunicationStatus.DISABLED
        )

        controller_component_manager.start_communicating()
        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        time.sleep(0.5)
        call_args = communication_state_changed_callback.get_whole_queue()
        args = [call_arg[0] for call_arg in call_args]

        for fqdn in controller_component_manager._subarrays.keys():
            assert (fqdn, CommunicationStatus.NOT_ESTABLISHED) in args
            assert (fqdn, CommunicationStatus.ESTABLISHED) in args

        for fqdn in controller_component_manager._subracks.keys():
            assert (fqdn, CommunicationStatus.NOT_ESTABLISHED) in args
            assert (fqdn, CommunicationStatus.ESTABLISHED) in args

        for fqdn in controller_component_manager._stations.keys():
            assert (fqdn, CommunicationStatus.NOT_ESTABLISHED) in args
            assert (fqdn, CommunicationStatus.ESTABLISHED) in args

        for fqdn in controller_component_manager._subarray_beams.keys():
            assert (fqdn, CommunicationStatus.NOT_ESTABLISHED) in args
            assert (fqdn, CommunicationStatus.ESTABLISHED) in args

        for fqdn in controller_component_manager._station_beams.keys():
            assert (fqdn, CommunicationStatus.NOT_ESTABLISHED) in args
            assert (fqdn, CommunicationStatus.ESTABLISHED) in args

        call_args = communication_state_changed_callback.get_whole_queue()
        print(call_args)
        # assert (None, CommunicationStatus.ESTABLISHED)
        assert (
            controller_component_manager.communication_state
            == CommunicationStatus.ESTABLISHED
        )
        assert False

        controller_component_manager.stop_communicating()
        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.DISABLED
        )
        assert (
            controller_component_manager.communication_state
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
        time.sleep(0.25)
        controller_component_manager.on()

        for proxy in subrack_proxies:
            result = proxy.On()
            assert result
        for proxy in station_proxies:
            result = proxy.On()
            assert result

        # pretend to receive events
        for fqdn in subrack_fqdns:
            controller_component_manager._subrack_power_state_changed(
                fqdn, PowerState.ON
            )
        for fqdn in station_fqdns:
            controller_component_manager._station_power_state_changed(
                fqdn, PowerState.ON
            )
        controller_component_manager.off()

        # pretend to receive events
        for fqdn in station_fqdns:
            controller_component_manager._station_power_state_changed(
                fqdn, PowerState.OFF
            )
        for fqdn in station_fqdns:
            controller_component_manager._station_power_state_changed(
                fqdn, PowerState.OFF
            )

    def test_power_events(
        self: TestControllerComponentManager,
        controller_component_manager: ControllerComponentManager,
        component_state_changed_callback: MockCallableDeque,
    ) -> None:
        """
        Test the controller component manager's management of power mode.

        :param controller_component_manager: the controller component
            manager under test.
        :param component_state_changed_callback: callback to be
            called when the component state changes
        """
        controller_component_manager.start_communicating()
        time.sleep(0.2)
        component_state_changed_callback.assert_next_call_with_keys(
            {"power_state": PowerState.ON}
        )
        controller_component_manager.power_state = PowerState.ON
        assert controller_component_manager.power_state == PowerState.ON

        for station_proxy in controller_component_manager._stations.values():
            station_proxy._device_state_changed(
                "state", tango.DevState.OFF, tango.AttrQuality.ATTR_VALID
            )
            # assert controller_component_manager.power_state == PowerState.UNKNOWN
            component_state_changed_callback.assert_next_call_with_keys(
                {"power_state": PowerState.OFF}, fqdn=station_proxy._fqdn
            )
            # print(component_state_changed_callback.get_next_call_with_keys('power_state', fqdn='low-mccs/station/001'))

        for subrack_proxy in controller_component_manager._subracks.values():
            subrack_proxy._device_state_changed(
                "state", tango.DevState.OFF, tango.AttrQuality.ATTR_VALID
            )
            component_state_changed_callback.get_next_call_with_keys(
                {"power_state": PowerState.OFF}, fqdn=subrack_proxy._fqdn
            )

        print(component_state_changed_callback.get_next_call_with_keys("power_state"))
        assert False
        # component_state_changed_callback.assert_next_call_with_keys({'power_state': PowerState.OFF})
        controller_component_manager.power_state = PowerState.OFF
        assert controller_component_manager.power_state == PowerState.OFF

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
        time.sleep(0.25)

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

        #         with pytest.raises(ConnectionError, match="Component is not turned on"):
        #             controller_component_manager.allocate(
        #                 99,
        #                 [["low-mccs/station/001"]],
        #                 ["low-mccs/subarraybeam/02"],
        #                 [3, 4],  # unknown subarray id
        #             )

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

        time.sleep(0.25)
        subarray_proxies[
            "low-mccs/subarray/01"
        ].AssignResources.assert_called_once_with(
            json.dumps(
                {
                    "stations": [["low-mccs/station/001"]],
                    "subarray_beams": ["low-mccs/subarraybeam/02"],
                    "station_beams": ["low-mccs/beam/04"],
                    "channel_blocks": [3, 4],
                }
            )
        )

        controller_component_manager.deallocate_all(1)
        time.sleep(0.25)
        subarray_proxies[
            "low-mccs/subarray/01"
        ].ReleaseAllResources.assert_called_once_with()

        controller_component_manager.allocate(
            2,
            [["low-mccs/station/001"]],
            ["low-mccs/subarraybeam/02"],
            [3, 4],
        )

        time.sleep(0.25)
        subarray_proxies[
            "low-mccs/subarray/02"
        ].AssignResources.assert_called_once_with(
            json.dumps(
                {
                    "stations": [["low-mccs/station/001"]],
                    "subarray_beams": ["low-mccs/subarraybeam/02"],
                    "station_beams": ["low-mccs/beam/04"],
                    "channel_blocks": [3, 4],
                }
            )
        )

        controller_component_manager.deallocate_all(1)
        controller_component_manager.deallocate_all(2)
        time.sleep(0.25)
        controller_component_manager.allocate(
            1,
            [["low-mccs/station/001"]],
            ["low-mccs/subarraybeam/02"],
            [48],
        )

        # Now all 48 channel blocks of station 1 are assigned to subarray 1,
        # assigning any more to subarray 2 should fail
        time.sleep(0.25)
        with pytest.raises(
            ValueError, match="No free resources of type: channel_blocks."
        ):
            controller_component_manager.allocate(
                2,
                [["low-mccs/station/001"]],
                ["low-mccs/subarraybeam/02"],
                [1],
            )

        controller_component_manager.restart_subarray("low-mccs/subarray/02")
        time.sleep(0.25)
        subarray_proxies["low-mccs/subarray/02"].Restart.assert_called_once_with()
