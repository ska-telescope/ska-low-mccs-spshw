# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests of the station component manager."""
from __future__ import annotations

import logging
import time
import unittest.mock

import pytest
import tango
from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import CommunicationStatus, PowerState
from ska_tango_base.executor import TaskStatus

from ska_low_mccs import MccsDeviceProxy
from ska_low_mccs.station import StationComponentManager
from ska_low_mccs.testing.mock import MockCallable
from ska_low_mccs.testing.mock.mock_callable import MockCallableDeque


class TestStationComponentManager:
    """Tests of the station component manager."""

    def test_communication(
        self: TestStationComponentManager,
        station_component_manager: StationComponentManager,
        communication_state_changed_callback: MockCallable,
        component_state_changed_callback: MockCallableDeque,
    ) -> None:
        """
        Test the station component manager's management of communication.

        :param station_component_manager: the station component manager
            under test.
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param is_configured_changed_callback: callback to be called
            when whether the station is configured changes
        """
        assert (
            station_component_manager.communication_state
            == CommunicationStatus.DISABLED
        )

        station_component_manager.start_communicating()

        # allow some time for device communication to start before testing
        time.sleep(0.1)
        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.ESTABLISHED
        )
        assert (
            station_component_manager.communication_state
            == CommunicationStatus.ESTABLISHED
        )

        component_state_changed_callback.assert_next_call_with_keys(
            {"is_configured": False}
        )

        station_component_manager.stop_communicating()
        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.DISABLED
        )
        assert (
            station_component_manager.communication_state
            == CommunicationStatus.DISABLED
        )

    # Note: test_power_commands has been moved to TestStationComponentStateChangedCallback::test_power_commands

    def test_power_events_received(
        self: TestStationComponentManager,
        station_component_manager: StationComponentManager,
        component_state_changed_callback: MockCallableDeque,
        antenna_fqdns: list[str],
        tile_fqdns: list[str],
        apiu_fqdn: str,
    ) -> None:
        """
        Test the station component manager's management of power mode.

        :param station_component_manager: the station component manager
            under test.
        :param component_power_state_changed_callback: callback to be
            called when the component power mode changes
        """
        # Note: since the base class 0.13 adoption most of this test has been moved into
        # TestStationComponentStateChangedCallback::test_power_events.
        # Therefore this test is very thin, and only checks that change events from the
        # tile, antenna and apiu devices are being received.
        station_component_manager.start_communicating()
        time.sleep(0.1)  # wait for events to come through
        expected_calls = (
            [({"power_state": PowerState.UNKNOWN}, fqdn) for fqdn in antenna_fqdns]
            + [({"power_state": PowerState.UNKNOWN}, fqdn) for fqdn in tile_fqdns]
            + [({"power_state": PowerState.UNKNOWN}, apiu_fqdn)]
        )
        component_state_changed_callback.assert_next_calls_with_keys(expected_calls)

    def test_tile_setup(
        self: TestStationComponentManager,
        station_component_manager: StationComponentManager,
        station_id: int,
        tile_fqdns: list[str],
        logger: logging.Logger,
        communication_state_changed_callback: MockCallable,
    ) -> None:
        """
        Test tile attribute assignment.

        Specifically, test that when the station component manager
        established communication with its tiles, it write its station
        id and a unique logical tile id to each one.

        :param station_component_manager: the station component manager
            under test.
        :param station_id: the id of the station
        :param tile_fqdns: FQDNs of the Tango devices that manage this
            station's tiles.
        :param logger: a logger
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        """
        station_component_manager.start_communicating()
        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.ESTABLISHED
        )

        # receive notification that the tile is on
        for tile_proxy in station_component_manager._tile_proxies.values():
            tile_proxy._device_state_changed(
                "state", tango.DevState.ON, tango.AttrQuality.ATTR_VALID
            )
        time.sleep(0.1)

        for logical_tile_id, tile_fqdn in enumerate(tile_fqdns):
            tile_device_proxy = MccsDeviceProxy(tile_fqdn, logger)
            assert tile_device_proxy.stationId == station_id
            assert tile_device_proxy.logicalTileId == logical_tile_id

    # Note: test_apply_pointing has been moved to TestStationComponentStateChangedCallback::test_appy_pointing

    def test_configure(
        self: TestStationComponentManager,
        station_component_manager: StationComponentManager,
        communication_state_changed_callback: MockCallable,
        # is_configured_changed_callback: MockCallable,
        component_state_changed_callback: MockCallableDeque,
        station_id: int,
    ) -> None:
        """
        Test tile attribute assignment.

        Specifically, test that when the station component manager
        established communication with its tiles, it write its station
        id and a unique logical tile id to each one.

        :param station_component_manager: the station component manager
            under test.
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param is_configured_changed_callback: callback to be called
            when whether the station is configured changes
        :param station_id: the id of the station
        """
        station_component_manager.start_communicating()
        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.ESTABLISHED
        )
        time.sleep(0.1)
        component_state_changed_callback.assert_next_call_with_keys(
            {"is_configured": False}
        )
        assert not station_component_manager.is_configured

        # with pytest.raises(ValueError, match="Wrong station id"):
        mock_task_callback = MockCallable()
        station_component_manager._configure(
            station_id + 1, task_callback=mock_task_callback
        )
        mock_task_callback.assert_next_call(status=TaskStatus.IN_PROGRESS)
        mock_task_callback.assert_next_call(
            status=TaskStatus.FAILED,
            result="Configure command has failed: Wrong station id",
        )

        # is_configured_changed_callback.assert_not_called()
        component_state_changed_callback.assert_not_called_with_keys("is_configured")
        assert not station_component_manager.is_configured

        # result = station_component_manager._configure(station_id)
        station_component_manager._configure(station_id, mock_task_callback)
        mock_task_callback.assert_next_call(status=TaskStatus.IN_PROGRESS)
        mock_task_callback.assert_next_call(
            status=TaskStatus.COMPLETED, result="Configure command has completed"
        )

        # assert result == ResultCode.OK
        # is_configured_changed_callback.assert_next_call(True)
        component_state_changed_callback.assert_next_call_with_keys(
            {"is_configured": True}
        )
        assert station_component_manager.is_configured
