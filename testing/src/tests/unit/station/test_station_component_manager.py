"""This module contains the tests of the station component manager."""
from __future__ import annotations

import logging
import time
import unittest.mock

import pytest
import tango

from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import PowerMode

from ska_low_mccs import MccsDeviceProxy
from ska_low_mccs.component import CommunicationStatus
from ska_low_mccs.station import StationComponentManager

from ska_low_mccs.testing.mock import MockCallable


class TestStationComponentManager:
    """Tests of the station component manager."""

    def test_communication(
        self: TestStationComponentManager,
        station_component_manager: StationComponentManager,
        communication_status_changed_callback: MockCallable,
        is_configured_changed_callback: MockCallable,
    ) -> None:
        """
        Test the station component manager's management of communication.

        :param station_component_manager: the station component manager
            under test.
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param is_configured_changed_callback: callback to be called
            when whether the station is configured changes
        """
        assert (
            station_component_manager.communication_status
            == CommunicationStatus.DISABLED
        )

        station_component_manager.start_communicating()
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.ESTABLISHED
        )
        assert (
            station_component_manager.communication_status
            == CommunicationStatus.ESTABLISHED
        )

        is_configured_changed_callback.assert_next_call(False)

        station_component_manager.stop_communicating()
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.DISABLED
        )
        assert (
            station_component_manager.communication_status
            == CommunicationStatus.DISABLED
        )

    def test_power_commands(
        self: TestStationComponentManager,
        station_component_manager: StationComponentManager,
        communication_status_changed_callback: MockCallable,
        apiu_proxy: unittest.mock.Mock,
        tile_fqdns: list[str],
        tile_proxies: list[unittest.mock.Mock],
        antenna_fqdns: list[str],
        antenna_proxies: list[unittest.mock.Mock],
    ) -> None:
        """
        Test that the power commands work as expected.

        :param station_component_manager: the station component manager
            under test.
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param apiu_proxy: proxy to this station's APIU device
        :param tile_fqdns: FQDNs of tile devices
        :param tile_proxies: list of proxies to this station's tile
            devices
        :param antenna_fqdns: FQDNs of antenna devices
        :param antenna_proxies: list of proxies to this station's
            antenna devices
        """
        station_component_manager.start_communicating()
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        communication_status_changed_callback.assert_last_call(
            CommunicationStatus.ESTABLISHED
        )
        station_component_manager.on()

        apiu_proxy.On.assert_next_call()

        # pretend to receive APIU power mode changed event
        station_component_manager._apiu_power_mode_changed(PowerMode.ON)

        for tile_proxy in tile_proxies:
            tile_proxy.On.assert_next_call()
        for antenna_proxy in antenna_proxies:
            antenna_proxy.On.assert_next_call()

        # pretend to receive tile and antenna events
        for fqdn in tile_fqdns:
            station_component_manager._tile_power_mode_changed(fqdn, PowerMode.ON)
        for fqdn in antenna_fqdns:
            station_component_manager._antenna_power_mode_changed(fqdn, PowerMode.ON)

        assert station_component_manager.power_mode == PowerMode.ON

        station_component_manager.off()
        for proxy in [apiu_proxy] + tile_proxies:
            proxy.Off.assert_next_call()

    def test_power_events(
        self: TestStationComponentManager,
        station_component_manager: StationComponentManager,
        component_power_mode_changed_callback: MockCallable,
    ) -> None:
        """
        Test the station component manager's management of power mode.

        :param station_component_manager: the station component manager
            under test.
        :param component_power_mode_changed_callback: callback to be
            called when the component power mode changes
        """
        station_component_manager.start_communicating()
        component_power_mode_changed_callback.assert_next_call(PowerMode.UNKNOWN)
        assert station_component_manager.power_mode == PowerMode.UNKNOWN

        time.sleep(0.1)  # to let the UNKNOWN events subside

        for antenna_proxy in station_component_manager._antenna_proxies:
            antenna_proxy._device_state_changed(
                "state", tango.DevState.OFF, tango.AttrQuality.ATTR_VALID
            )
            assert station_component_manager.power_mode == PowerMode.UNKNOWN
            component_power_mode_changed_callback.assert_not_called()
        for tile_proxy in station_component_manager._tile_proxies:
            tile_proxy._device_state_changed(
                "state", tango.DevState.OFF, tango.AttrQuality.ATTR_VALID
            )
            assert station_component_manager.power_mode == PowerMode.UNKNOWN
            component_power_mode_changed_callback.assert_not_called()
        station_component_manager._apiu_proxy._device_state_changed(
            "state", tango.DevState.OFF, tango.AttrQuality.ATTR_VALID
        )
        component_power_mode_changed_callback.assert_next_call(PowerMode.OFF)
        assert station_component_manager.power_mode == PowerMode.OFF

    def test_tile_setup(
        self: TestStationComponentManager,
        station_component_manager: StationComponentManager,
        station_id: int,
        tile_fqdns: list[str],
        logger: logging.Logger,
        communication_status_changed_callback: MockCallable,
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
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        """
        station_component_manager.start_communicating()
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.ESTABLISHED
        )

        # receive notification that the tile is on
        for tile_proxy in station_component_manager._tile_proxies:
            tile_proxy._device_state_changed(
                "state", tango.DevState.ON, tango.AttrQuality.ATTR_VALID
            )
        time.sleep(0.1)

        def _show_state_of_devices(
            devices: list[MccsDeviceProxy],
        ) -> None:
            """
            Show the state of the requested devices.

            :param devices: list of MCCS device proxies
            """
            for device in devices:
                print(f"Device: {device.name} = {device.state()}")

        devices = []
        for tile_proxy in station_component_manager._tile_proxies:
            devices.append(tile_proxy._proxy)
        _show_state_of_devices(devices)

        for logical_tile_id, tile_fqdn in enumerate(tile_fqdns):
            tile_device_proxy = MccsDeviceProxy(tile_fqdn, logger)
            # TODO RCL: We have an issue here because nothing has written to
            #      tile_device_proxy.stationId and the comparison fails     
            assert tile_device_proxy.stationId == station_id
            assert tile_device_proxy.logicalTileId == logical_tile_id

    def test_apply_pointing(
        self: TestStationComponentManager,
        station_component_manager: StationComponentManager,
        tile_fqdns: list[str],
        logger: logging.Logger,
        pointing_delays: unittest.mock.Mock,
        communication_status_changed_callback: MockCallable,
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
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        """
        station_component_manager.start_communicating()
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.ESTABLISHED
        )

        # Tell this station each of its components is on, so that it thinks it is on
        station_component_manager._apiu_proxy._device_state_changed(
            "state", tango.DevState.ON, tango.AttrQuality.ATTR_VALID
        )
        for tile_proxy in station_component_manager._tile_proxies:
            tile_proxy._device_state_changed(
                "state", tango.DevState.ON, tango.AttrQuality.ATTR_VALID
            )
        for antenna_proxy in station_component_manager._antenna_proxies:
            antenna_proxy._device_state_changed(
                "state", tango.DevState.ON, tango.AttrQuality.ATTR_VALID
            )

        station_component_manager.apply_pointing(pointing_delays)
        for tile_fqdn in tile_fqdns:
            tile_device_proxy = MccsDeviceProxy(tile_fqdn, logger)
            tile_device_proxy.SetPointingDelay.assert_next_call(pointing_delays)

    def test_configure(
        self: TestStationComponentManager,
        station_component_manager: StationComponentManager,
        communication_status_changed_callback: MockCallable,
        is_configured_changed_callback: MockCallable,
        station_id: int,
    ) -> None:
        """
        Test tile attribute assignment.

        Specifically, test that when the station component manager
        established communication with its tiles, it write its station
        id and a unique logical tile id to each one.

        :param station_component_manager: the station component manager
            under test.
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param is_configured_changed_callback: callback to be called
            when whether the station is configured changes
        :param station_id: the id of the station
        """
        station_component_manager.start_communicating()
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.ESTABLISHED
        )

        is_configured_changed_callback.assert_next_call(False)
        assert not station_component_manager.is_configured

        with pytest.raises(ValueError, match="Wrong station id"):
            station_component_manager.configure(station_id + 1)

        is_configured_changed_callback.assert_not_called()
        assert not station_component_manager.is_configured

        result = station_component_manager.configure(station_id)

        assert result == ResultCode.OK
        is_configured_changed_callback.assert_next_call(True)
        assert station_component_manager.is_configured
