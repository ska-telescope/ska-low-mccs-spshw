#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module defined a pytest harness for unit testing the SPS Station module."""
from __future__ import annotations

import unittest.mock

import pytest
import tango
from ska_control_model import PowerState, ResultCode
from ska_low_mccs_common.testing.mock import MockDeviceBuilder
from tango.server import command

from ska_low_mccs_spshw import SpsStation
from tests.harness import get_tile_name


@pytest.fixture(name="mock_subrack_device_proxy")
def mock_subrack_device_proxy_fixture() -> unittest.mock.Mock:
    """
    Fixture that provides a mock MccsSubrack device proxy.

    :return: a mock MccsSubrack device.
    """
    builder = MockDeviceBuilder()
    builder.set_state(tango.DevState.ON)
    builder.add_result_command("Off", ResultCode.STARTED)
    builder.add_result_command("On", ResultCode.STARTED)
    return builder()


@pytest.fixture(name="mock_tile_builder")
def mock_tile_builder_fixture(tile_id: int) -> MockDeviceBuilder:
    """
    Fixture that provides a builder for a mock MccsTile device.

    :param tile_id: ID of the tile under test.

    :return: a mock MccsSubrack device builder.
    """
    builder = MockDeviceBuilder()
    builder.set_state(tango.DevState.ON)
    builder.add_attribute("cspRounding", [2] * 384)
    builder.add_result_command("LoadPointingDelays", ResultCode.QUEUED)
    builder.add_attribute("logicalTileId", tile_id)
    builder.add_command("dev_name", get_tile_name(tile_id, "ci-1"))
    return builder


@pytest.fixture(name="mock_tile_device_proxy")
def mock_tile_device_proxy_fixture(
    mock_tile_builder: MockDeviceBuilder,
) -> unittest.mock.Mock:
    """
    Fixture that provides a mock MccsTile device proxy.

    :param mock_tile_builder: builder for mock Tiles

    :return: a mock MccsTile device proxy.
    """
    return mock_tile_builder()


@pytest.fixture(name="num_tiles")
def num_tiles_fixture() -> int:
    """
    Get the number of tiles to use in multi-mock-tile tests.

    :return: the number of tiles
    """
    return 4


@pytest.fixture(name="mock_tile_device_proxies")
def mock_tile_device_proxies_fixture(
    mock_tile_builder: MockDeviceBuilder, num_tiles: int
) -> list[unittest.mock.Mock]:
    """
    Fixture that provides a list of mock MccsTile devices.

    :param mock_tile_builder: builder for mock Tiles
    :param num_tiles: the number of tiles to make mocks of

    :return: a list of mock MccsTile devices.
    """
    return [mock_tile_builder() for _ in range(num_tiles)]


@pytest.fixture(name="patched_sps_station_device_class")
def patched_sps_station_device_class_fixture() -> type[SpsStation]:
    """
    Return a station device class patched with extra methods for testing.

    :return: a station device class patched with extra methods for
        testing.
    """

    class PatchedSpsStationDevice(SpsStation):
        """
        SpsStation patched with extra commands for testing purposes.

        The extra commands allow us to mock the receipt of a state
        change event from subservient subrack devices.
        """

        @command()
        def MockSubracksOff(self: PatchedSpsStationDevice) -> None:
            """
            Mock all subracks being turned off.

            Make the station device think it has received state change
            event from its subracks, indicating that the subracks are
            now OFF.
            """
            for name in self.component_manager._subrack_proxies:
                self.component_manager._subrack_state_changed(
                    name, power=PowerState.OFF
                )

            for name in self.component_manager._tile_proxies:
                self.component_manager._tile_state_changed(
                    name, power=PowerState.NO_SUPPLY
                )

        @command()
        def MockSubracksOn(self: PatchedSpsStationDevice) -> None:
            """
            Mock all subracks being turned on.

            Make the station device think it has received state change
            event from its subracks, indicating that the subracks are
            now ON.
            """
            for name in self.component_manager._subrack_proxies:
                self.component_manager._subrack_state_changed(name, power=PowerState.ON)

            for name in self.component_manager._tile_proxies:
                self.component_manager._tile_state_changed(name, power=PowerState.OFF)

        @command()
        def MockTilesOff(self: PatchedSpsStationDevice) -> None:
            """
            Mock all tiles being turned off.

            Make the station device think it has received state change
            event from its tiles, indicating that the tiles are now OFF.
            """
            for name in self.component_manager._tile_proxies:
                self.component_manager._tile_state_changed(name, power=PowerState.OFF)

        @command()
        def MockTilesOn(self: PatchedSpsStationDevice) -> None:
            """
            Mock all tiles being turned on.

            Make the station device think it has received state change
            event from its tiles, indicating that the tiles are now ON.
            """
            for name in self.component_manager._tile_proxies:
                self.component_manager._tile_state_changed(name, power=PowerState.ON)

    return PatchedSpsStationDevice


@pytest.fixture(name="antenna_uri")
def antenna_uri_fixture() -> list[str]:
    """
    Return a uri for antenna data.

    :returns: A URI for antenna data.
    """
    return [
        "car:ska-low-aavs3?main",
        "instrument/mccs-configuration/aavs3.yaml",
    ]
