# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests of the station component state changed callback."""
from __future__ import annotations

import logging
import time
import unittest.mock
import functools

import pytest
import tango
from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import CommunicationStatus, PowerState

from ska_low_mccs import MccsDeviceProxy
from ska_low_mccs.station import StationComponentManager, MccsStation
from ska_low_mccs.testing.mock import MockCallable
from ska_low_mccs.testing.mock.mock_callable import MockCallableDeque

@pytest.fixture
def patched_station_device_class(
    mock_station_component_manager: StationComponentManager,
) -> Type[MccsStation]:
    """
    Return a station device class, patched with extra methods for testing.

    :param mock_Station_component_manager: A fixture that provides a partially mocked component manager
            which has access to the component_state_changed_callback.

    :return: a patched station device class, patched with extra methods
        for testing
    """

    class PatchedStationDevice(MccsStation):
        """
        MccsStation patched with extra commands for testing purposes.

        The extra commands allow us to mock the receipt of obs state
        change events from subservient devices.
        """
        def create_component_manager(
            self: PatchedStationDevice,
        ) -> StationComponentManager:
            """
            Return a partially mocked component manager instead of the usual one.

            :return: a mock component manager
            """
            mock_station_component_manager._component_state_changed_callback = (
                self.component_state_changed_callback
            )
            mock_station_component_manager._apiu_proxy._component_state_changed_callback = (
                functools.partial(
                    mock_station_component_manager._component_state_changed_callback, 
                    fqdn=mock_station_component_manager._apiu_fqdn,
                )
            )
            for tile_fqdn, tile_proxy in mock_station_component_manager._tile_proxies.items():
                tile_proxy._component_state_changed_callback = (
                    functools.partial(
                        mock_station_component_manager._component_state_changed_callback, 
                        fqdn=tile_fqdn,
                    )
                )
            for antenna_fqdn, antenna_proxy in mock_station_component_manager._antenna_proxies.items():
                antenna_proxy._component_state_changed_callback = (
                    functools.partial(
                        mock_station_component_manager._component_state_changed_callback,
                        fqdn=antenna_fqdn,
                    )
                )

            return mock_station_component_manager

    return PatchedStationDevice

@pytest.fixture()
def device_to_load(
    patched_station_device_class: PatchedStationDevice,
    ) -> DeviceToLoadType:
    """
    Fixture that specifies the device to be loaded for testing.

    :return: specification of the device to be loaded
    """
    return {
        "path": "charts/ska-low-mccs/data/configuration.json",
        "package": "ska_low_mccs",
        "device": "station_001",
        "proxy": MccsDeviceProxy,
        "patch": patched_station_device_class,
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
    return tango_harness.get_device("low-mccs/station/001")

class TestStationComponentStateChangedCallback:
    """Tests of the station component manager."""

    def test_power_events(
        self: TestStationComponentStateChangedCallback,
        device_under_test: MccsDeviceProxy,
        mock_station_component_manager: StationComponentManager,
    ):
        """ Test the station component manager's management of power mode. """
        mock_station_component_manager.power_state = None
        mock_station_component_manager.start_communicating()
        time.sleep(0.1) # wait for events to come through

        # TODO: implement a way to check that the tango device's _component_power_state_changed
        # callback is called
        # i.e. component_power_state_changed_callback.assert_next_call(PowerState.UNKNOWN)
        assert mock_station_component_manager.power_state == PowerState.UNKNOWN

        for antenna_proxy in mock_station_component_manager._antenna_proxies.values():
            antenna_proxy._device_state_changed(
                "state", tango.DevState.OFF, tango.AttrQuality.ATTR_VALID
            )
            assert mock_station_component_manager.power_state == PowerState.UNKNOWN
            # TODO: implement a way to check that the tango device's _component_power_state_changed
            # callback is NOT called
            # i.e. component_power_state_changed_callback.assert_not_called()
        for tile_proxy in mock_station_component_manager._tile_proxies.values():
            tile_proxy._device_state_changed(
                "state", tango.DevState.OFF, tango.AttrQuality.ATTR_VALID
            )
            assert mock_station_component_manager.power_state == PowerState.UNKNOWN
            # TODO: implement a way to check that the tango device's _component_power_state_changed
            # callback is NOT called
            # i.e. component_power_state_changed_callback.assert_not_called()
        mock_station_component_manager._apiu_proxy._device_state_changed(
            "state", tango.DevState.OFF, tango.AttrQuality.ATTR_VALID
        )
        # TODO: implement a way to check that the tango device's _component_power_state_changed
        # callback is called
        # i.e. component_power_state_changed_callback.assert_next_call(PowerState.OFF)
        assert mock_station_component_manager.power_state == PowerState.OFF
    
    def test_apply_pointing(
        self: TestStationComponentManager,
        #station_component_manager: StationComponentManager,
        tile_fqdns: list[str],
        logger: logging.Logger,
        pointing_delays: unittest.mock.Mock,
        communication_state_changed_callback: MockCallable,
        device_under_test: MccsDeviceProxy,
        mock_station_component_manager: StationComponentManager,
    ) -> None:
        """
        Test tile attribute assignment.

        Specifically, test that when the station component manager
        established communication with its tiles, it write its station
        id and a unique logical tile id to each one.

        :param station_component_manager: the station component manager
            under test.
        :param tile_fqdns: FQDNs of the Tango devices that manage this
            station's tiles.
        :param logger: a logger
        :param pointing_delays: some mock pointing delays
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_power_state_changed_callback: callback to be
            called when the component power mode changes
        """
        mock_station_component_manager.start_communicating()
        time.sleep(0.1) # wait for the events from subservient devices to come through

        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.ESTABLISHED
        )

        # TODO < 0.13: Using "last" instead of "next" here is a sneaky way of forcing a delay
        # so that we don't start faking receipt of events below until the real events
        # have all been received.
        #component_power_state_changed_callback.assert_last_call(PowerState.UNKNOWN)

        # TODO: implement a way to check that the tango device's _component_power_state_changed
        # callback is called
        # i.e. component_power_state_changed_callback.assert_next_call(PowerState.UNKNOWN)
        assert mock_station_component_manager.power_state == PowerState.UNKNOWN

        # Tell this station each of its components is on, so that it thinks it is on
        mock_station_component_manager._apiu_proxy._device_state_changed(
            "state", tango.DevState.ON, tango.AttrQuality.ATTR_VALID
        )
        for tile_proxy in mock_station_component_manager._tile_proxies.values():
            tile_proxy._device_state_changed(
                "state", tango.DevState.ON, tango.AttrQuality.ATTR_VALID
            )
        for antenna_proxy in mock_station_component_manager._antenna_proxies.values():
            antenna_proxy._device_state_changed(
                "state", tango.DevState.ON, tango.AttrQuality.ATTR_VALID
            )

        #component_power_state_changed_callback.assert_last_call(PowerState.ON)

        # TODO: implement a way to check that the tango device's _component_power_state_changed
        # callback is called
        # i.e. component_power_state_changed_callback.assert_next_call(PowerState.ON)
        assert mock_station_component_manager.power_state == PowerState.ON

        mock_station_component_manager._apply_pointing(pointing_delays)
        for tile_fqdn in tile_fqdns:
            tile_device_proxy = MccsDeviceProxy(tile_fqdn, logger)
            tile_device_proxy.SetPointingDelay.assert_next_call(pointing_delays)