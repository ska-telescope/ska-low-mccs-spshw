# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module defined a pytest test harness for testing the MCCS antenna module."""
from __future__ import annotations

import logging
import unittest.mock
from typing import Callable

import pytest
import tango
from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import CommunicationStatus, PowerState
from tango.server import command

from ska_low_mccs import MccsAntenna, MccsDeviceProxy
from ska_low_mccs.antenna import AntennaComponentManager
from ska_low_mccs.antenna.antenna_component_manager import _ApiuProxy, _TileProxy
from ska_low_mccs.testing import TangoHarness
from ska_low_mccs.testing.mock import (
    MockCallable,
    MockChangeEventCallback,
    MockDeviceBuilder,
)


@pytest.fixture()
def apiu_fqdn() -> str:
    """
    Return the FQDN of the antenna's APIU device.

    :return: the FQDN of the antenna's APIU device.
    """
    return "low-mccs/apiu/001"


@pytest.fixture()
def apiu_antenna_id() -> int:
    """
    Return the id of the antenna in the APIU.

    :return: the id of the antenna in the APIU.
    """
    # TODO: This must match the LogicalApiuAntennaId property of the
    # antenna device. We should refactor the harness so that we can pull
    # it straight from the device configuration.
    return 1


@pytest.fixture()
def tile_fqdn() -> str:
    """
    Return the FQDN of the antenna's tile device.

    :return: the FQDN of the antenna's tile device.
    """
    return "low-mccs/tile/0001"


@pytest.fixture()
def tile_antenna_id() -> int:
    """
    Return the id of the antenna in the tile.

    :return: the id of the antenna in the tile.
    """
    return 1


@pytest.fixture()
def antenna_power_mode_changed_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> unittest.mock.Mock:
    """
    Return a mock callback for antenna power mode change.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the component manager
        detects that the power mode of its component has changed.
    """
    return mock_callback_factory()


@pytest.fixture()
def antenna_apiu_proxy(
    tango_harness: TangoHarness,
    apiu_fqdn: str,
    apiu_antenna_id: int,
    logger: logging.Logger,
    lrc_result_changed_callback: MockChangeEventCallback,
    communication_status_changed_callback: MockCallable,
    component_power_mode_changed_callback: MockCallable,
    component_fault_callback: MockCallable,
    antenna_power_mode_changed_callback: MockCallable,
) -> _ApiuProxy:
    """
    Return an antenna APIU proxy for testing.

    This is a pytest fixture.

    :param tango_harness: a test harness for MCCS tango devices
    :param apiu_fqdn: FQDN of the antenna's APIU device
    :param apiu_antenna_id: the id of the antenna in the APIU device
    :param logger: a loger for the antenna component manager to use
    :param lrc_result_changed_callback: a callback to
        be used to subscribe to device LRC result changes
    :param communication_status_changed_callback: callback to be called
        when the status of the communications channel between the
        component manager and its component changes
    :param component_power_mode_changed_callback: callback to be called
        when the component power mode changes
    :param component_fault_callback: callback to be called when the
        component faults (or stops faulting)
    :param antenna_power_mode_changed_callback: the callback to be called
        when the power mode of an antenna changes

    :return: an antenna APIU proxy
    """
    return _ApiuProxy(
        apiu_fqdn,
        apiu_antenna_id,
        logger,
        lrc_result_changed_callback,
        communication_status_changed_callback,
        component_power_mode_changed_callback,
        component_fault_callback,
        antenna_power_mode_changed_callback,
    )


@pytest.fixture()
def antenna_tile_proxy(
    tango_harness: TangoHarness,
    tile_fqdn: str,
    tile_antenna_id: int,
    logger: logging.Logger,
    lrc_result_changed_callback: MockChangeEventCallback,
    communication_status_changed_callback: Callable[[CommunicationStatus], None],
    component_fault_callback: Callable[[bool], None],
) -> _TileProxy:
    """
    Return an antenna tile proxy for testing.

    This is a pytest fixture.

    :param tango_harness: a test harness for MCCS tango devices
    :param tile_fqdn: FQDN of the antenna's tile device
    :param tile_antenna_id: the id of the antenna in the tile device
    :param logger: a loger for the antenna component manager to use
    :param lrc_result_changed_callback: a callback to
        be used to subscribe to device LRC result changes
    :param communication_status_changed_callback: callback to be called
        when the status of the communications channel between the
        component manager and its component changes
    :param component_fault_callback: callback to be called when the
        component faults (or stops faulting)

    :return: an antenna tile proxy for testing
    """
    return _TileProxy(
        tile_fqdn,
        tile_antenna_id,
        logger,
        lrc_result_changed_callback,
        communication_status_changed_callback,
        component_fault_callback,
    )


@pytest.fixture()
def antenna_component_manager(
    tango_harness: TangoHarness,
    apiu_fqdn: str,
    apiu_antenna_id: int,
    tile_fqdn: str,
    tile_antenna_id: int,
    logger: logging.Logger,
    lrc_result_changed_callback: MockChangeEventCallback,
    communication_status_changed_callback: Callable[[CommunicationStatus], None],
    component_power_mode_changed_callback: Callable[[PowerState], None],
    component_fault_callback: Callable[[bool], None],
) -> AntennaComponentManager:
    """
    Return an antenna component manager.

    :param tango_harness: a test harness for MCCS tango devices
    :param apiu_fqdn: FQDN of the antenna's APIU device
    :param apiu_antenna_id: the id of the antenna in the APIU device
    :param tile_fqdn: FQDN of the antenna's tile device
    :param tile_antenna_id: the id of the antenna in the tile device
    :param logger: a loger for the antenna component manager to use
    :param lrc_result_changed_callback: a callback to
        be used to subscribe to device LRC result changes
    :param communication_status_changed_callback: callback to be called
        when the status of the communications channel between the
        component manager and its component changes
    :param component_power_mode_changed_callback: callback to be called
        when the component power mode changes
    :param component_fault_callback: callback to be called when the
        component faults (or stops faulting)

    :return: an antenna component manager
    """
    return AntennaComponentManager(
        apiu_fqdn,
        apiu_antenna_id,
        tile_fqdn,
        tile_antenna_id,
        logger,
        lrc_result_changed_callback,
        communication_status_changed_callback,
        component_power_mode_changed_callback,
        component_fault_callback,
    )


@pytest.fixture()
def initial_antenna_power_mode() -> int:
    """
    Return the initial power mode of the antenna.

    :return: the initial power mode of the antenna.
    """
    return PowerState.OFF


@pytest.fixture()
def initial_are_antennas_on(
    apiu_antenna_id: int,
    initial_antenna_power_mode: PowerState,
) -> list[bool]:
    """
    Return whether each antenna is initially on in the APIU.

    The antenna under test will be set off or on in accordance with the
    initial_antenna_power_mode argument. All other antennas will
    initially be off.

    :param apiu_antenna_id: the id of the antenna under test.
    :param initial_antenna_power_mode: whether the antenna under test is
        initially on.

    :return: whether each antenna is initially on in the APIU.
    """
    are_antennas_on = [False] * apiu_antenna_id
    are_antennas_on[apiu_antenna_id - 1] = initial_antenna_power_mode == PowerState.ON
    return are_antennas_on


@pytest.fixture()
def mock_apiu(initial_are_antennas_on: list[bool]) -> unittest.mock.Mock:
    """
    Fixture that provides a mock MccsApiu device.

    :param initial_are_antennas_on: whether each antenna is initially on
        in the APIU

    :return: a mock MccsApiu device.
    """
    builder = MockDeviceBuilder()
    builder.set_state(tango.DevState.OFF)
    builder.add_command("IsAntennaOn", False)
    builder.add_result_command("On", ResultCode.OK)
    builder.add_result_command("PowerUpAntenna", ResultCode.OK)
    builder.add_result_command("PowerDownAntenna", ResultCode.OK)
    builder.add_attribute("areAntennasOn", initial_are_antennas_on)
    return builder()


@pytest.fixture()
def mock_tile() -> unittest.mock.Mock:
    """
    Fixture that provides a mock MccsTile device.

    This has no tile-specific functionality at present.

    :return: a mock MccsApiu device.
    """
    builder = MockDeviceBuilder()
    return builder()


@pytest.fixture()
def initial_mocks(
    apiu_fqdn: str,
    mock_apiu: unittest.mock.Mock,
    tile_fqdn: str,
    mock_tile: unittest.mock.Mock,
) -> dict[str, unittest.mock.Mock]:
    """
    Return a dictionary of pre-registered device proxy mocks.

    The default fixture is overridden here to provide an MccsApiu mock
    and an MccsTile mock..

    :param apiu_fqdn: FQDN of the APIU device
    :param mock_apiu: the mock APIU device to be provided when a device
        proxy to the APIU FQDN is requested.
    :param tile_fqdn: FQDN of the Tile device
    :param mock_tile: the mock Tile device to be provided when a device
        proxy to the Tile FQDN is requested.

    :return: a dictionary of mocks, keyed by FQDN
    """
    return {
        apiu_fqdn: mock_apiu,
        tile_fqdn: mock_tile,
    }


@pytest.fixture()
def mock_apiu_device_proxy(apiu_fqdn: str, logger: logging.Logger) -> MccsDeviceProxy:
    """
    Return a mock device proxy to an APIU device.

    :param apiu_fqdn: FQDN of the APIU device.
    :param logger: a logger for the device proxy to use.

    :return: a mock device proxy to an APIU device.
    """
    return MccsDeviceProxy(apiu_fqdn, logger)


@pytest.fixture()
def patched_antenna_device_class(
    initial_are_antennas_on: list[bool],
) -> type[MccsAntenna]:
    """
    Return an antenna device class, patched with extra methods for testing.

    :param initial_are_antennas_on: whether each antenna is initially on
        in the APIU
    :return: an antenna device class, patched with extra methods for testing.
    """

    class PatchedAntennaDevice(MccsAntenna):
        """
        MccsAntenna patched with extra commands for testing purposes.

        The extra commands allow us to mock the receipt of a state change
        event from its APIU device.

        These methods are provided here because they are quite
        implementation dependent. If an implementation change breaks
        this, we only want to fix it in this one place.
        """

        @command()
        def MockAntennaPoweredOn(self: PatchedAntennaDevice) -> None:
            are_antennas_on = list(initial_are_antennas_on)
            are_antennas_on[self.LogicalApiuAntennaId - 1] = True
            self.component_manager._apiu_proxy._antenna_power_mode_changed(
                "areAntennasOn",
                are_antennas_on,
                tango.AttrQuality.ATTR_VALID,
            )

        @command()
        def MockApiuOff(self: PatchedAntennaDevice) -> None:
            """
            Mock the APIU being turned off.

            Make the antenna device think it has received a state change
            event from its APIU indicating that the APIU is now OFF.
            """
            self.component_manager._apiu_proxy._device_state_changed(
                "state", tango.DevState.OFF, tango.AttrQuality.ATTR_VALID
            )

        @command()
        def MockApiuOn(self: PatchedAntennaDevice) -> None:
            """
            Mock the APIU being turned on.

            Make the antenna device think it has received a state change
            event from its APIU indicating that the APIU is now ON.
            """
            self.component_manager._apiu_proxy._device_state_changed(
                "state", tango.DevState.ON, tango.AttrQuality.ATTR_VALID
            )

    return PatchedAntennaDevice
