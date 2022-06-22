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

from ska_low_mccs import MccsDeviceProxy
from ska_low_mccs.controller import ControllerComponentManager


class TestControllerComponentManager:
    """Tests of the controller component manager."""

    def test_communication(
        self: TestControllerComponentManager,
        controller_component_manager: ControllerComponentManager,
    ) -> None:
        """
        Test the controller component manager's management.

        :param controller_component_manager: the controller component
            manager under test.
        """
        assert (
            controller_component_manager.communication_state
            == CommunicationStatus.DISABLED
        )
        controller_component_manager.start_communicating()
        # time.sleep(0.1)
        assert (
            controller_component_manager.communication_state
            == CommunicationStatus.NOT_ESTABLISHED
        )
        for fqdn in controller_component_manager._subarrays.keys():
            controller_component_manager._device_communication_state_changed(
                fqdn,
                CommunicationStatus.ESTABLISHED,
            )
        for fqdn in controller_component_manager._subracks.keys():
            controller_component_manager._device_communication_state_changed(
                fqdn,
                CommunicationStatus.ESTABLISHED,
            )
        for fqdn in controller_component_manager._stations.keys():
            controller_component_manager._device_communication_state_changed(
                fqdn,
                CommunicationStatus.ESTABLISHED,
            )
        for fqdn in controller_component_manager._subarray_beams.keys():
            controller_component_manager._device_communication_state_changed(
                fqdn,
                CommunicationStatus.ESTABLISHED,
            )
        for fqdn in controller_component_manager._station_beams.keys():
            controller_component_manager._device_communication_state_changed(
                fqdn,
                CommunicationStatus.ESTABLISHED,
            )

        assert (
            controller_component_manager._communication_state
            == CommunicationStatus.ESTABLISHED
        )
        controller_component_manager.stop_communicating()
        time.sleep(0.1)
        assert (
            controller_component_manager._communication_state
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
        assert (
            controller_component_manager._communication_state
            == CommunicationStatus.ESTABLISHED
        )
        controller_component_manager.on()

        for proxy in subrack_proxies:
            result, msg = proxy.On()
            assert result == [ResultCode.QUEUED]
        for proxy in station_proxies:
            result, msg = proxy.On()
            assert result == [ResultCode.QUEUED]

        # pretend to receive events
        for fqdn in subrack_fqdns:
            controller_component_manager._component_state_changed_callback(
                {"power_state": PowerState.ON},
                fqdn=fqdn,
            )
        for fqdn in station_fqdns:
            controller_component_manager._component_state_changed_callback(
                {"power_state": PowerState.ON}, fqdn=fqdn
            )
        controller_component_manager.component_state_changed_callback(
            {"power_state": PowerState.ON}
        )

        controller_component_manager.off()

        for proxy in station_proxies:
            result, msg = proxy.Off()
            assert result == [ResultCode.QUEUED]

        # pretend to receive events
        for fqdn in station_fqdns:
            controller_component_manager._component_state_changed_callback(
                {"power_state": PowerState.OFF}, fqdn=fqdn
            )

        for proxy in subrack_proxies:
            result, msg = proxy.Off()
            assert result == [ResultCode.QUEUED]

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
        for fqdn in controller_component_manager._subarrays.keys():
            controller_component_manager._device_communication_state_changed(
                fqdn,
                CommunicationStatus.ESTABLISHED,
            )
        for fqdn in controller_component_manager._subracks.keys():
            controller_component_manager._device_communication_state_changed(
                fqdn,
                CommunicationStatus.ESTABLISHED,
            )
        for fqdn in controller_component_manager._stations.keys():
            controller_component_manager._device_communication_state_changed(
                fqdn,
                CommunicationStatus.ESTABLISHED,
            )
        for fqdn in controller_component_manager._subarray_beams.keys():
            controller_component_manager._device_communication_state_changed(
                fqdn,
                CommunicationStatus.ESTABLISHED,
            )
        for fqdn in controller_component_manager._station_beams.keys():
            controller_component_manager._device_communication_state_changed(
                fqdn,
                CommunicationStatus.ESTABLISHED,
            )
        assert (
            controller_component_manager._communication_state
            == CommunicationStatus.ESTABLISHED
        )

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
                99,
                [["low-mccs/station/001"]],
                ["low-mccs/subarraybeam/02"],
                [3, 4],  # unknown subarray id
            )

        # Callbacks are handled in the device, so need to tell the
        # component manager explicitly that each device is ON
        for fqdn in controller_component_manager._stations.keys():
            controller_component_manager._device_power_states[fqdn] = PowerState.ON
        for fqdn in controller_component_manager._subracks.keys():
            controller_component_manager._device_power_states[fqdn] = PowerState.ON
        controller_component_manager._evaluate_power_state()

        assert controller_component_manager._power_state == PowerState.ON

        # TODO: These tests have been suspended until a refactor of the allocate/_allocate
        # methods has been preformed. All the error checking is performed after the
        # _antenna task has been submitted. Should the checking be moved into the antenna
        # method?

        argin = json.dumps(
            {
                "interface": "https://schema.skao.int/ska-low-mccs-assignresources/1.0",
                "subarray_id": 1,
                "subarray_beam_ids": [2],
                "station_ids": [[99]],
                "channel_blocks": [3, 4],
            }
        )
        # this will never raise as the testing occurs in the submitted task
        # with pytest.raises(ValueError, match="Unsupported resources"):
        controller_component_manager.allocate(argin)


#         argin = json.dumps(
#         {
#             "interface": "https://schema.skao.int/ska-low-mccs-assignresources/1.0",
#             "subarray_id": 1,
#             "subarray_beam_ids": [2],
#             "station_ids": [[1]],
#             "channel_blocks": [3,4],
#         }
#         )
#         # this will never raise as the testing occurs in the submitted task
#         #with pytest.raises(ValueError, match="Allocatee is unready"):
#         controller_component_manager.allocate(argin)
#
#         controller_component_manager._subarray_health_changed(
#             "low-mccs/subarray/01",
#             HealthState.OK,
#         )
#         controller_component_manager._subarray_health_changed(
#             "low-mccs/subarray/02",
#             HealthState.OK,
#         )
#
#         argin = json.dumps(
#         {
#             "interface": "https://schema.skao.int/ska-low-mccs-assignresources/1.0",
#             "subarray_id": 1,
#             "subarray_beam_ids": [2],
#             "station_ids": [[1]],
#             "channel_blocks": [3,4],
#         }
#         )
#         # this will never raise as the testing occurs in the submitted task
#         # with pytest.raises(ValueError, match="Cannot allocate unhealthy resources"):
#         controller_component_manager.allocate(argin)
#
#         controller_component_manager._station_health_changed(
#             "low-mccs/station/001",
#             HealthState.OK,
#         )
#
#         argin = json.dumps(
#         {
#             "interface": "https://schema.skao.int/ska-low-mccs-assignresources/1.0",
#             "subarray_id": 1,
#             "subarray_beam_ids": [2],
#             "station_ids": [[1]],
#             "channel_blocks": [3,4],
#         }
#         )
#         # this will never raise as the testing occurs in the submitted task
#         # with pytest.raises(ValueError, match="Cannot allocate unhealthy resources"):
#         controller_component_manager.allocate(argin)
#
#         controller_component_manager._subarray_beam_health_changed(
#             "low-mccs/subarraybeam/02",
#             HealthState.OK,
#         )
#
#         controller_component_manager.allocate(
#             1,
#             [["low-mccs/station/001"]],
#             ["low-mccs/subarraybeam/02"],
#             [3, 4],
#         )
#
#         time.sleep(0.25)
#         subarray_proxies[
#             "low-mccs/subarray/01"
#         ].AssignResources.assert_called_once_with(
#             json.dumps(
#                 {
#                     "stations": [["low-mccs/station/001"]],
#                     "subarray_beams": ["low-mccs/subarraybeam/02"],
#                     "station_beams": ["low-mccs/beam/04"],
#                     "channel_blocks": [3, 4],
#                 }
#             )
#         )
#
#         controller_component_manager.deallocate_all(1)
#         time.sleep(0.25)
#         subarray_proxies[
#             "low-mccs/subarray/01"
#         ].ReleaseAllResources.assert_called_once_with()
#
#         controller_component_manager.allocate(
#             2,
#             [["low-mccs/station/001"]],
#             ["low-mccs/subarraybeam/02"],
#             [3, 4],
#         )
#
#         time.sleep(0.25)
#         subarray_proxies[
#             "low-mccs/subarray/02"
#         ].AssignResources.assert_called_once_with(
#             json.dumps(
#                 {
#                     "stations": [["low-mccs/station/001"]],
#                     "subarray_beams": ["low-mccs/subarraybeam/02"],
#                     "station_beams": ["low-mccs/beam/04"],
#                     "channel_blocks": [3, 4],
#                 }
#             )
#         )
#
#         controller_component_manager.deallocate_all(1)
#         controller_component_manager.deallocate_all(2)
#         time.sleep(0.25)
#         controller_component_manager.allocate(
#             1,
#             [["low-mccs/station/001"]],
#             ["low-mccs/subarraybeam/02"],
#             [48],
#         )
#
#         # Now all 48 channel blocks of station 1 are assigned to subarray 1,
#         # assigning any more to subarray 2 should fail
#         time.sleep(0.25)
#         with pytest.raises(
#             ValueError, match="No free resources of type: channel_blocks."
#         ):
#             controller_component_manager.allocate(
#                 2,
#                 [["low-mccs/station/001"]],
#                 ["low-mccs/subarraybeam/02"],
#                 [1],
#             )
#
#         controller_component_manager.restart_subarray("low-mccs/subarray/02")
#         time.sleep(0.25)
#         subarray_proxies["low-mccs/subarray/02"].Restart.assert_called_once_with()
