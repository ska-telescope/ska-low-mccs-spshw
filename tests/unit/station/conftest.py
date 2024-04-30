#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module defined a pytest harness for unit testing the SPS Station module."""
from __future__ import annotations

import logging
import unittest.mock

import pytest
import tango
from ska_control_model import PowerState, ResultCode
from ska_low_mccs_common.testing.mock import MockDeviceBuilder
from tango.server import command

from ska_low_mccs_spshw import SpsStation
from ska_low_mccs_spshw.station import StationSelfCheckManager
from ska_low_mccs_spshw.station.tests import TpmSelfCheckTest
from tests.harness import get_daq_name, get_subrack_name, get_tile_name


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


class ErrorTest(TpmSelfCheckTest):
    """Test class for test that errors."""

    def test(self: ErrorTest) -> None:
        """This test will raise a KeyError."""
        my_dictionary = {"key1": 1, "key2": 2}
        assert "key1" in my_dictionary

        # Oh no!
        _ = my_dictionary["key3"]


class PassTest(TpmSelfCheckTest):
    """Test class for test that passes."""

    def test(self: PassTest) -> None:
        """This test will pass."""
        my_dictionary = {"key1": 1, "key2": 2}
        assert "key1" in my_dictionary
        assert "key2" in my_dictionary


class FailTest(TpmSelfCheckTest):
    """Test class for test that fails."""

    def test(self: FailTest) -> None:
        """This test will fail."""
        my_dictionary = {"key1": 1, "key2": 2}
        assert "key1" in my_dictionary
        assert "key2" in my_dictionary
        assert "key3" in my_dictionary


class BadRequirementsTest(TpmSelfCheckTest):
    """Test class for test which we fail to meet requirements of."""

    def test(self: BadRequirementsTest) -> None:
        """This test won't be run."""
        my_dictionary = {"key1": 1, "key2": 2}
        assert "key1" in my_dictionary
        assert "key2" in my_dictionary

    def check_requirements(self: BadRequirementsTest) -> tuple[bool, str]:
        """
        Unreasonable test requirements which we won't meet.

        :returns: False as we don't meet the requirements.
        """
        if len(self.tile_trls) < 20:
            return (False, "For some reason this test wants 20 tiles")
        return (True, "Damn you really have 20 tiles?")


@pytest.fixture(name="station_self_check_manager")
def station_self_check_manager_fixture(
    logger: logging.Logger,
) -> StationSelfCheckManager:
    """
    Return a station self check manager with patched example tests.

    :param logger: logger for use in the tests.

    :returns: a station self check manager with patched example tests.
    """
    tile_trls = [get_tile_name(i) for i in range(1, 5)]
    subrack_trls = [get_subrack_name(1)]
    daq_trl = get_daq_name()
    station_self_check_manager = StationSelfCheckManager(
        logger=logger,
        tile_trls=tile_trls,
        subrack_trls=subrack_trls,
        daq_trl=daq_trl,
    )
    # Jank to get around https://github.com/python/mypy/issues/3115 and
    # https://github.com/python/mypy/issues/16509
    tpm_tests_1 = [
        tpm_test(
            logger=logger,
            tile_trls=list(tile_trls),
            subrack_trls=list(subrack_trls),
            daq_trl=daq_trl,
        )
        for tpm_test in [
            PassTest,
            FailTest,
        ]
    ]
    tpm_tests_2 = [
        tpm_test(
            logger=logger,
            tile_trls=list(tile_trls),
            subrack_trls=list(subrack_trls),
            daq_trl=daq_trl,
        )
        for tpm_test in [
            ErrorTest,
            BadRequirementsTest,
        ]
    ]
    tpm_tests = tpm_tests_1 + tpm_tests_2
    station_self_check_manager._tpm_test_names = [
        tpm_test.__class__.__name__ for tpm_test in tpm_tests
    ]
    station_self_check_manager._tpm_tests = {
        tpm_test.__class__.__name__: tpm_test for tpm_test in tpm_tests
    }
    return station_self_check_manager
