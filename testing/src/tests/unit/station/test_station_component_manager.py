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

import tango
from pydaq.daq_receiver_interface import DaqModes
from ska_control_model import CommunicationStatus, PowerState, TaskStatus
from ska_low_mccs_common import MccsDeviceProxy
from ska_low_mccs_common.testing.mock import MockCallable
from ska_low_mccs_common.testing.mock.mock_callable import MockCallableDeque

from ska_low_mccs.station import StationComponentManager


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
        :param component_state_changed_callback: callback to be called
            when the station state changes
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
        :param component_state_changed_callback: callback to be called
            when the station state changes
        :param antenna_fqdns: list of antenna fqdns
        :param tile_fqdns: list of antenna fqdns
        :param apiu_fqdn: apiu fqdn
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
        :param component_state_changed_callback: callback to be called
            when the station state changes
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

        component_state_changed_callback.assert_next_call_with_keys(
            {"is_configured": True}
        )
        assert station_component_manager.is_configured

    def test_instantiate_daq(
        self: TestStationComponentManager,
        station_component_manager: StationComponentManager,
        communication_state_changed_callback: MockCallable,
    ) -> None:
        """
        Test basic DAQ functionality.

        This test merely instantiates DAQ as a member of station_component_manager, starts a consumer,
        waits for a time and then stops the consumer. Data can also be logged if available.

        :param station_component_manager: the station component manager
            under test.
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        """
        # Override the default config.
        # The duration should be long enough to actually receive data.
        # This defaults to around 20-30 sec after delays are accounted for.
        modes_to_start = [DaqModes.INTEGRATED_CHANNEL_DATA]
        # data_received_callback isn't currently used as we don't yet have a
        # reliable way of making data available in a test context.
        # data_received_callback = MockCallable()
        daq_config = {
            "nof_tiles": 2,
            "receiver_ports": "4660",
            "receiver_interface": "eth0",
            "receiver_ip": "172.17.0.2",
            "directory": ".",
            "acquisition_duration": 5,
        }
        station_component_manager._daq_instance.populate_configuration(daq_config)

        station_component_manager.start_communicating()
        communication_state_changed_callback.assert_last_call(
            CommunicationStatus.ESTABLISHED
        )

        mock_task_callback = MockCallable()
        result_code, message = station_component_manager.on(
            task_callback=mock_task_callback
        )
        assert result_code == TaskStatus.QUEUED
        assert message == "Task queued"

        # Start DAQ and check our consumer is running.
        # station_component_manager.start_daq(modes_to_start, data_received_callback)
        station_component_manager.start_daq(modes_to_start)
        for mode in modes_to_start:
            assert station_component_manager._daq_instance._running_consumers[mode]

        # Wait for data etc
        time.sleep(
            station_component_manager._daq_instance._config["acquisition_duration"]
        )

        # Stop DAQ and check our consumer is not running.
        station_component_manager.stop_daq()
        for mode in modes_to_start:
            assert not station_component_manager._daq_instance._running_consumers[mode]
