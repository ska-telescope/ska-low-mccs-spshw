# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests for MccsTile."""
from __future__ import annotations

import pytest

from ska_tango_base.control_model import (
    AdminMode
)
from ska_low_mccs import MccsDeviceProxy
from ska_low_mccs.testing.mock import MockChangeEventCallback


@pytest.fixture(scope="module")
def devices_to_load() -> DevicesToLoadType:
    """
    Fixture that specifies the devices to be loaded for testing.

    :return: specification of the devices to be loaded
    """
    return {
        "path": "charts/ska-low-mccs/data/deployment_configuration.json",
        "package": "ska_low_mccs",
        "devices": [
            {"name": "controller", "proxy": MccsDeviceProxy},
            {"name": "subrack_01", "proxy": MccsDeviceProxy},
            {"name": "subarray_01", "proxy": MccsDeviceProxy},
            {"name": "subarray_02", "proxy": MccsDeviceProxy},
            {"name": "subarraybeam_01", "proxy": MccsDeviceProxy},
            {"name": "subarraybeam_02", "proxy": MccsDeviceProxy},
            {"name": "subarraybeam_03", "proxy": MccsDeviceProxy},
            {"name": "subarraybeam_04", "proxy": MccsDeviceProxy},
            {"name": "station_001", "proxy": MccsDeviceProxy},
            {"name": "station_002", "proxy": MccsDeviceProxy},
            {"name": "apiu_001", "proxy": MccsDeviceProxy},
            {"name": "apiu_002", "proxy": MccsDeviceProxy},
            {"name": "tile_0001", "proxy": MccsDeviceProxy},
            {"name": "tile_0002", "proxy": MccsDeviceProxy},
            {"name": "tile_0003", "proxy": MccsDeviceProxy},
            {"name": "tile_0004", "proxy": MccsDeviceProxy},
            {"name": "beam_01", "proxy": MccsDeviceProxy},
            {"name": "beam_02", "proxy": MccsDeviceProxy},
            {"name": "beam_03", "proxy": MccsDeviceProxy},
            {"name": "beam_04", "proxy": MccsDeviceProxy},
            {"name": "antenna_000001", "proxy": MccsDeviceProxy},
            {"name": "antenna_000002", "proxy": MccsDeviceProxy},
            {"name": "antenna_000003", "proxy": MccsDeviceProxy},
            {"name": "antenna_000004", "proxy": MccsDeviceProxy},
            {"name": "antenna_000005", "proxy": MccsDeviceProxy},
            {"name": "antenna_000006", "proxy": MccsDeviceProxy},
            {"name": "antenna_000007", "proxy": MccsDeviceProxy},
            {"name": "antenna_000008", "proxy": MccsDeviceProxy},
        ],
    }


@pytest.fixture()
def device_admin_mode_changed_callback(
    mock_change_event_callback_factory: Callable[[str], MockChangeEventCallback],
) -> MockChangeEventCallback:
    """
    Return a mock change event callback for device admin mode change.

    :param mock_change_event_callback_factory: fixture that provides a
        mock change event callback factory (i.e. an object that returns
        mock callbacks when called).

    :return: a mock change event callback to be registered with the
        device via a change event subscription, so that it gets called
        when the device admin mode changes.
    """
    return mock_change_event_callback_factory("adminMode")


@pytest.fixture()
def mock_callback_factory(
    mock_callback_called_timeout: float, mock_callback_not_called_timeout: float
) -> Callable[[], MockCallable]:
    """
    Return a factory that returns a new mock callback each time it is called.

    Use this fixture in tests that need more than one mock_callback. If
    your tests only needs a single mock callback, it is simpler to use
    the :py:func:`mock_callback` fixture.

    :param mock_callback_called_timeout: the time to wait for a mock
        callback to be called when a call is expected
    :param mock_callback_not_called_timeout: the time to wait for a mock
        callback to be called when a call is unexpected

    :return: a factory that returns a new mock callback each time it is
        called.
    """
    return lambda: MockCallable(
        called_timeout=mock_callback_called_timeout,
        not_called_timeout=mock_callback_not_called_timeout,
    )


def test_admin_mode_memorized_online(
    controller: MccsDeviceProxy,
    subrack: MccsDeviceProxy,
    subarrays: dict[int, MccsDeviceProxy],
    subarray_beams: dict[int, MccsDeviceProxy],
    stations: dict[int, MccsDeviceProxy],
    station_beams: dict[int, MccsDeviceProxy],
    apius: dict[int, MccsDeviceProxy],
    tiles: dict[int, MccsDeviceProxy],
    antennas: dict[int, MccsDeviceProxy],
    device_admin_mode_changed_callback: MockChangeEventCallback
) -> None:
    """
    Check all devices have adminMode set to ONLINE

    :param controller: a proxy to the controller device
    :type controller: :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`
    :param subrack: a proxy to the subrack device
    :type subrack: :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`
    :param subarrays: proxies to the subarray devices, keyed by number
    :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param subarray_beams: proxies to the subarray_beam devices, keyed by number
    :type subarray_beams: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param stations: proxies to the station devices, keyed by number
    :type stations: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param station_beams: proxies to the station_beam devices, keyed by number
    :type station_beams: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param apius: proxies to the apiu devices, keyed by number
    :type apius: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param tiles: proxies to the tile devices, keyed by number
    :type tiles: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param antennas: proxies to the antenna devices, keyed by number
    :type antennas: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    """
    controller.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
    device_admin_mode_changed_callback.assert_next_change_event(AdminMode.ONLINE)
    assert controller.adminMode == AdminMode.ONLINE
    
    subrack.add_change_event_callback(
        "adminMode",
        device_admin_mode_changed_callback,
    )
    device_admin_mode_changed_callback.assert_next_change_event(AdminMode.ONLINE)
    assert subrack.adminMode == AdminMode.ONLINE

    for subarray_device in subarrays.values():
        subarray_device.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.ONLINE)
        assert subarray_device.adminMode == AdminMode.ONLINE

    for subarray_beam_device in subarray_beams.values():
        subarray_beam_device.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.ONLINE)
        assert subarray_beam_device.adminMode == AdminMode.ONLINE

    for station_device in stations.values():
        station_device.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.ONLINE)
        assert station_device.adminMode == AdminMode.ONLINE

    for station_beam_device in station_beams.values():
        station_beam_device.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.ONLINE)
        assert station_beam_device.adminMode == AdminMode.ONLINE

    for apiu_device in apius.values():
        apiu_device.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.ONLINE)
        assert apiu_device.adminMode == AdminMode.ONLINE

    for tile_device in tiles.values():
        tile_device.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.ONLINE)
        assert tile_device.adminMode == AdminMode.ONLINE
    
    for antenna_device in antennas.values():
        antenna_device.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.ONLINE)
        assert antenna_device.adminMode == AdminMode.ONLINE
