#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module defined a pytest harness for unit testing the SPS Station module."""
from __future__ import annotations

import json
import logging
import unittest.mock

import numpy as np
import pytest
import tango
from ska_control_model import AdminMode, HealthState, PowerState, ResultCode
from ska_low_mccs_common.testing.mock import MockDeviceBuilder
from tango.server import command

from ska_low_mccs_spshw import SpsStation
from ska_low_mccs_spshw.station import SpsStationSelfCheckManager
from ska_low_mccs_spshw.station.tests import TpmSelfCheckTest
from tests.harness import get_subrack_name, get_tile_name


@pytest.fixture(name="mock_subrack_device_proxy")
def mock_subrack_device_proxy_fixture() -> unittest.mock.Mock:
    """
    Fixture that provides a mock MccsSubrack device proxy.

    :return: a mock MccsSubrack device.
    """
    builder = MockDeviceBuilder()
    builder.set_state(tango.DevState.ON)
    builder.add_attribute("adminMode", AdminMode.ONLINE)
    builder.add_attribute("healthState", HealthState.OK)
    builder.add_result_command("Off", ResultCode.STARTED)
    builder.add_result_command("On", ResultCode.STARTED)
    return builder()


@pytest.fixture(name="tile_initial_beamformer_table")
def tile_initial_beamformer_table_fixture() -> list[int]:
    """
    Return an example initial beamformer table for a tile.

    :returns: an example initial beamformer table for a tile.
    """
    return [128, 1, 1, 1, 1, 1, 101, 64, 2, 2, 2, 2, 2, 102]


@pytest.fixture(name="tile_initial_beamformer_regions")
def tile_initial_beamformer_regions_fixture(
    tile_initial_beamformer_table: list[int],
) -> list[int]:
    """
    Return an example initial beamformer regions for a tile.

    :param tile_initial_beamformer_table: an initial beamformer table for a tile.

    :returns: an example initial beamformer regions for a tile.
    """
    regions = []
    for i in range(0, len(tile_initial_beamformer_table), 7):
        chunk = tile_initial_beamformer_table[i : i + 7]
        regions.extend((list([chunk[0], 8]) + list(chunk[1:7])))
    return regions


@pytest.fixture(name="mock_tile_builder")
def mock_tile_builder_fixture(
    tile_id: int,
    tile_initial_beamformer_table: list[int],
    tile_initial_beamformer_regions: list[int],
) -> MockDeviceBuilder:
    """
    Fixture that provides a builder for a mock MccsTile device.

    :param tile_id: ID of the tile under test.
    :param tile_initial_beamformer_table: an initial beamformer table for a tile.
    :param tile_initial_beamformer_regions: an initial beamformer regions for a tile.

    :return: a mock MccsSubrack device builder.
    """
    # Logical tile id is the zero based TPM number.
    logical_tile_id = tile_id - 1
    builder = MockDeviceBuilder()
    builder.set_state(tango.DevState.ON)
    builder.add_attribute("adminMode", AdminMode.ONLINE)
    builder.add_attribute("healthState", HealthState.OK)
    builder.add_attribute("preaduLevels", np.array([22.0] * 32))
    builder.add_attribute("adcPower", np.array([17.0] * 32))
    builder.add_attribute("staticTimeDelays", np.array([0] * 32))
    builder.add_attribute("ppsDelay", 0)
    builder.add_attribute("cspRounding", np.array([2] * 384))
    builder.add_attribute("pendingDataRequests", False)
    builder.add_attribute("beamformerTable", tile_initial_beamformer_table)
    builder.add_attribute("beamformerRegions", tile_initial_beamformer_regions)
    builder.add_attribute("tileProgrammingState", "Unknown")
    builder.add_result_command("LoadPointingDelays", ResultCode.QUEUED)
    builder.add_attribute("logicalTileId", logical_tile_id)
    builder.add_command("dev_name", get_tile_name(tile_id, "ci-1"))
    for command_name in [
        "SetLmcDownload",
        "SendDataSamples",
        "SetLmcIntegratedDownload",
        "StartBeamformer",
        "ConfigureIntegratedChannelData",
        "StartAcquisition",
        "SetCspDownload",
        "StopDataTransmission",
        "StopIntegratedData",
        "StopBeamformer",
        "StopBeamformerForChannels",
        "ConfigureTestGenerator",
        "ConfigureIntegratedBeamData",
        "ApplyPointingDelays",
        "ApplyCalibration",
        "SetBeamformerRegions",
        "LoadCalibrationCoefficients",
    ]:
        builder.add_command(
            command_name, ([ResultCode.OK], [f"{command_name} completed OK."])
        )
    builder.add_command("BeamformerRunningForChannels", True)
    # Dummy commands for testing the async commands method
    builder.add_command("FailedCommand", ([ResultCode.FAILED], ["Command failed."]))
    builder.add_command(
        "RejectedCommand", ([ResultCode.REJECTED], ["Command rejected."])
    )
    builder.add_command("GoodCommand", ([ResultCode.OK], ["Command completed OK."]))
    return builder


@pytest.fixture(name="mock_daq_device_proxy")
def mock_daq_device_proxy_fixture() -> MockDeviceBuilder:
    """
    Fixture that provides mock MccsDaqReceiver device proxy.

    :return: a mock MccsDaqReceiver device proxy.
    """
    builder = MockDeviceBuilder()
    builder.set_state(tango.DevState.ON)
    builder.add_command(
        "DaqStatus",
        json.dumps(
            {
                "Running Consumers": [],
                "Receiver Interface": "eth0",
                "Receiver Ports": [4660],
                "Receiver IP": ["10.244.170.166"],
                "Bandpass Monitor": False,
                "Daq Health": ["OK", 0],
            }
        ),
    )
    builder.add_result_command(
        "Stop", result_code=ResultCode.QUEUED, status="Task queued"
    )
    builder.add_result_command(
        "Start", result_code=ResultCode.QUEUED, status="Task queued"
    )
    return builder()


@pytest.fixture(name="mock_tile_device_proxy")
def mock_tile_device_proxy_fixture(
    mock_tile_builder: MockDeviceBuilder,
    tile_id: int,
    station_id: int,
) -> unittest.mock.Mock:
    """
    Fixture that provides a mock MccsTile device proxy.

    :param mock_tile_builder: builder for mock Tiles
    :param tile_id: the TileId fixture used to populate the
        device_property
    :param station_id: the stationID fixture used to populate the
        device_property

    :return: a mock MccsTile device proxy.
    """
    logical_tile_id = tile_id - 1
    return mock_tile_builder(TileId=[logical_tile_id], StationID=[station_id])


@pytest.fixture(name="num_tiles")
def num_tiles_fixture() -> int:
    """
    Get the number of tiles to use in multi-mock-tile tests.

    :return: the number of tiles
    """
    return 4


@pytest.fixture(name="mock_tile_device_proxies")
def mock_tile_device_proxies_fixture(
    mock_tile_builder: MockDeviceBuilder, num_tiles: int, station_id: int
) -> list[unittest.mock.Mock]:
    """
    Fixture that provides a list of mock MccsTile devices.

    :param mock_tile_builder: builder for mock Tiles
    :param num_tiles: the number of tiles to make mocks of
    :param station_id: the stationID fixture used to populate the
        device_property

    :return: a list of mock MccsTile devices.
    """
    return [
        mock_tile_builder(TileId=[i + 1], StationID=[station_id])
        for i in range(num_tiles)
    ]


@pytest.fixture(name="patched_sps_station_device_class")
def patched_sps_station_device_class_fixture() -> type[SpsStation]:
    """
    Return a station device class patched with extra methods for testing.

    :return: a station device class patched with extra methods for
        testing.
    """

    class PatchedSpsStationDevice(SpsStation):  # pylint: disable=too-many-ancestors
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

        @command()
        def MockSubdeviceHealth(self: PatchedSpsStationDevice, argin: str) -> None:
            """
            Mock a subdevice health change.

            :param argin: A json string with the device trl and new health.

            Make the station device think it has received a health change
            event from a subdevice.
            """
            argin_dict = json.loads(argin)
            device = argin_dict["device"]
            health = argin_dict["health"]
            self._health_rollup.health_changed(source=device, health=health)

        @command()
        def MockCalibrationDataReceived(self: PatchedSpsStationDevice) -> None:
            """
            Mock calibration data received.

            Make the station device think it has received calibration data
            after a send data samples.
            """
            base_dir = "/product/eb-mvp01-20250314-00005/ska-low-mccs/5/correlator_data"
            file_name = "/correlation_burst_106_20250314_58668_0.hdf5"
            self.component_manager._lmc_daq_state_changed(
                "some/daq/fqdn",
                dataReceivedResult=(
                    "correlator",
                    json.dumps({"file_name": base_dir + file_name}),
                ),
            )

        @command()
        def MockBeamformerTableChange(
            self: PatchedSpsStationDevice, argin: str
        ) -> None:
            """
            Mock a change in tile beamformerTable.

            :param argin: contains the tile id we are mocking a change for
                and the value

            Mock a puched change event from a tile.
            """
            args = json.loads(argin)
            self.component_manager._on_tile_attribute_change(
                args["tile_id"],
                "beamformertable",
                np.array(args["value"]),
                tango.AttrQuality.ATTR_VALID,
            )

        @command()
        def MockTileProgrammingStateChange(
            self: PatchedSpsStationDevice, argin: str
        ) -> None:
            """
            Mock a change in tile programming state.

            :param argin: contains the tile id we are mocking a change for
                and the value

            Mock a puched change event from a tile.
            """
            args = json.loads(argin)
            self.component_manager._on_tile_attribute_change(
                args["tile_id"],
                "tileprogrammingstate",
                args["value"],
                tango.AttrQuality.ATTR_VALID,
            )

    return PatchedSpsStationDevice


@pytest.fixture(name="antenna_uri")
def antenna_uri_fixture() -> list[str]:
    """
    Return a uri for antenna data.

    :returns: A URI for antenna data.
    """
    return [
        "gitlab://gitlab.com/ska-telescope/ska-low-aavs3?a7d76d9f#tmdata",
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

    def check_requirements(self: TpmSelfCheckTest) -> tuple[bool, str]:
        """
        Strip engineering mode requirements for testing.

        :returns: True
        """
        return (True, "Not test requirements")


class PassTest(TpmSelfCheckTest):
    """Test class for test that passes."""

    def test(self: PassTest) -> None:
        """This test will pass."""
        my_dictionary = {"key1": 1, "key2": 2}
        assert "key1" in my_dictionary
        assert "key2" in my_dictionary

    def check_requirements(self: TpmSelfCheckTest) -> tuple[bool, str]:
        """
        Strip engineering mode requirements for testing.

        :returns: True
        """
        return (True, "Not test requirements")


class FailTest(TpmSelfCheckTest):
    """Test class for test that fails."""

    def test(self: FailTest) -> None:
        """This test will fail."""
        my_dictionary = {"key1": 1, "key2": 2}
        assert "key1" in my_dictionary
        assert "key2" in my_dictionary
        assert "key3" in my_dictionary

    def check_requirements(self: TpmSelfCheckTest) -> tuple[bool, str]:
        """
        Strip engineering mode requirements for testing.

        :returns: True
        """
        return (True, "Not test requirements")


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
    test_context: None,
    logger: logging.Logger,
) -> SpsStationSelfCheckManager:
    """
    Return a station self check manager with patched example tests.

    :param test_context: a Tango test context running the required
        mock subservient devices.
    :param logger: logger for use in the tests.

    :returns: a station self check manager with patched example tests.
    """
    tile_trls = [get_tile_name(1)]
    subrack_trls = [get_subrack_name(1)]
    mock_component_manager = unittest.mock.Mock()
    station_self_check_manager = SpsStationSelfCheckManager(
        component_manager=mock_component_manager,
        logger=logger,
        tile_trls=tile_trls,
        subrack_trls=subrack_trls,
        daq_trl="",
    )
    # Jank to get around https://github.com/python/mypy/issues/3115 and
    # https://github.com/python/mypy/issues/16509
    tpm_tests_1 = [
        tpm_test(
            component_manager=mock_component_manager,
            logger=logger,
            tile_trls=list(tile_trls),
            subrack_trls=list(subrack_trls),
            daq_trl="",
        )
        for tpm_test in [
            PassTest,
            FailTest,
        ]
    ]
    tpm_tests_2 = [
        tpm_test(
            component_manager=mock_component_manager,
            logger=logger,
            tile_trls=list(tile_trls),
            subrack_trls=list(subrack_trls),
            daq_trl="",
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
