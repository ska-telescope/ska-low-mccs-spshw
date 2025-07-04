# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains pytest-specific test harness for SPSHW integration tests."""
from __future__ import annotations

import copy
import json
import logging
import unittest
from typing import Any, Iterator

import numpy as np
import pytest
from ska_control_model import LoggingLevel, SimulationMode, TestMode
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup
from tango import DeviceProxy
from tango.server import command

from ska_low_mccs_spshw.subrack import SubrackSimulator
from ska_low_mccs_spshw.tile import MccsTile, TileComponentManager, TileSimulator
from tests.harness import (
    SpsTangoTestHarness,
    SpsTangoTestHarnessContext,
    get_bandpass_daq_name,
    get_lmc_daq_name,
    get_subrack_name,
)


def pytest_itemcollected(item: pytest.Item) -> None:
    """
    Modify a test after it has been collected by pytest.

    This hook implementation adds the "forked" custom mark to all tests
    that use the `integration_test_context` fixture, causing them to be
    sandboxed in their own process.

    :param item: the collected test for which this hook is called
    """
    if "integration_test_context" in item.fixturenames:  # type: ignore[attr-defined]
        item.add_marker("forked")


@pytest.fixture(name="subrack_simulator")
def subrack_simulator_fixture(
    subrack_simulator_config: dict[str, Any],
) -> SubrackSimulator:
    """
    Return a subrack simulator.

    :param subrack_simulator_config: a keyword dictionary that specifies
        the desired configuration of the simulator backend.

    :return: a subrack simulator.
    """
    return SubrackSimulator(**subrack_simulator_config)


@pytest.fixture(name="subrack_bay")
def subrack_bay_fixture() -> int:
    """
    Return the subrack bay the tile is connected to.

    :return: the subrack bay.
    """
    return 1


@pytest.fixture(name="tpm_version")
def tpm_version_fixture() -> str:
    """
    Return the TPM version.

    :return: the TPM version
    """
    return "tpm_v1_6"


@pytest.fixture(name="preadu_level_property")
def preadu_level_property_fixture() -> list[float]:
    """
    Return the preaduAttenuation to configure TPM.

    :return: The preaduAttenuation property of the tile.
    """
    return [20.0] * 32


@pytest.fixture(name="daq_id")
def daq_id_fixture() -> int:
    """
    Return the daq id of this daq receiver.

    :return: the daq id of this daq receiver.
    """
    return 1


# pylint: disable=too-many-arguments
@pytest.fixture(name="integration_test_context")
def integration_test_context_fixture(
    subrack_id: int,
    subrack_simulator: SubrackSimulator,
    tile_id: int,
    subrack_bay: int,
    patched_tile_device_class: MccsTile,
    daq_id: int,
) -> Iterator[SpsTangoTestHarnessContext]:
    """
    Return a test context in which both subrack simulator and Tango device are running.

    :param subrack_id: the ID of the subrack under test
    :param subrack_simulator: the backend simulator that the Tango
        device will monitor and control
    :param tile_id: the ID of the tile under test
    :param subrack_bay: This tile's position in its subrack
    :param patched_tile_device_class: A MccsTile class patched with
        some command to help testing.
    :param daq_id: the ID number of the DAQ receiver.

    :yields: a test context.
    """
    harness = SpsTangoTestHarness()
    harness.add_subrack_simulator(subrack_id, subrack_simulator)
    harness.add_subrack_device(subrack_id, logging_level=int(LoggingLevel.ERROR))
    harness.add_pdu_device(
        "ENLOGIC", "10.135.253.170", "public", logging_level=int(LoggingLevel.ERROR)
    )
    harness.add_tile_device(
        tile_id,
        subrack_id,
        subrack_bay=subrack_bay,
        device_class=patched_tile_device_class,
    )
    harness.set_daq_instance()
    harness.set_lmc_daq_device(daq_id, address=None)
    harness.set_bandpass_daq_device(daq_id, address=None)
    harness.set_sps_station_device(
        subrack_ids=[subrack_id],
        tile_ids=[tile_id],
        lmc_daq_trl=get_lmc_daq_name(),
        bandpass_daq_trl=get_bandpass_daq_name(),
    )

    with harness as context:
        yield context


@pytest.fixture(name="patched_tile_device_class")
def patched_tile_device_class_fixture(
    tile_component_manager: TileComponentManager,
) -> type[MccsTile]:
    """
    Return a tile device class patched with extra methods for testing.

    :param tile_component_manager: A component manager.

    :return: a tile device class patched with extra methods for testing.

    These methods are provided here because they are quite
    implementation dependent. If an implementation change breaks
    this, we only want to fix it in this one place.
    """

    class PatchedTileDevice(MccsTile):
        """
        MccsTile patched with extra commands for testing purposes.

        The extra commands allow us to mock the receipt of a state
        change event from its subrack device.

        These methods are provided here because they are quite
        implementation dependent. If an implementation change breaks
        this, we only want to fix it in this one place.
        """

        HEALTH_ATTRIBUTE_TO_SIMULATOR_MAP = {
            "fpga1Temperature": ["temperatures", "FPGA0"],
            "fpga2Temperature": ["temperatures", "FPGA1"],
            "boardTemperature": ["temperatures", "board"],
            "ppsPresent": ["timing", "pps", "status"],
        }

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.health_attribute_to_simulator_map = copy.deepcopy(
                self.HEALTH_ATTRIBUTE_TO_SIMULATOR_MAP
            )

            super().__init__(*args, **kwargs)

        def create_component_manager(
            self: PatchedTileDevice,
        ) -> TileComponentManager:
            """
            Return a mock component manager instead of the usual one.

            :return: a mock component manager
            """
            tile_component_manager._communication_state_callback = (
                self._communication_state_changed
            )
            tile_component_manager._component_state_callback = (
                self._component_state_changed
            )
            tile_component_manager._update_attribute_callback = (
                self._update_attribute_callback
            )

            return tile_component_manager

        def delete_device(self: PatchedTileDevice) -> None:
            """
            Clean up callbacks to ensure safe teardown.

            During teardown of the MccsTile device a segfault can occur.
            This is beleived to be due to the injection of the
            TileComponentManager. The teardown of the MccsTile device in the context was
            occuring before the teardown of the injected tilecomponentmanager,
            this was leading to messages reporting that we were trying to
            push a nonexistent attribute from TANGO during
            teardown (when the attribute did exist).
            Although i was not able to convince myself fully that this was concrete,
            the act of stopping communication and joining the polling thread
            removes the issue during teardown. This is supporting of the theory above.
            """
            tile_component_manager.stop_communicating()
            tile_component_manager._poller._polling_thread.join()
            super().delete_device()

        @command(dtype_in="DevString")
        def SetHealthStructureInBackend(
            self: PatchedTileDevice, attribute_to_set: str
        ) -> None:
            """
            Set a value in the backend TileSimulator.

            :param attribute_to_set: a json string of the form
                "{attr_name: attr_set_value}"
            """
            attributes = json.loads(attribute_to_set)
            for attribute, value in attributes.items():
                if attribute not in self.health_attribute_to_simulator_map:
                    pytest.fail(
                        f"Unable to set attribute {attribute} in TileSimulator "
                        "mapping not found."
                    )
                try:
                    indexes = self.health_attribute_to_simulator_map[attribute]

                    def _nested_set(
                        dic: dict[str, Any], keys: list[str], value: Any
                    ) -> None:
                        for key in keys[:-1]:
                            dic = dic.setdefault(key, {})
                        dic[keys[-1]] = value

                    _nested_set(
                        tile_component_manager.tile._tile_health_structure,
                        indexes,
                        value,
                    )

                except Exception as e:  # pylint: disable=broad-exception-caught
                    pytest.fail(
                        f"Failed to set {attribute} = {value} "
                        f"in backend TileSimulator : {repr(e)}"
                    )

    return PatchedTileDevice


@pytest.fixture(name="tile_component_manager")
def tile_component_manager_fixture(
    logger: logging.Logger,
    tile_id: int,
    station_id: int,
    subrack_id: int,
    subrack_bay: int,
    preadu_level_property: list[float],
    static_time_delays: np.ndarray,
    tpm_version: str,
    tile_simulator: TileSimulator,
) -> TileComponentManager:
    """
    Return a tile component manager (in simulation and test mode as specified).

    :param logger: the logger to be used by this object.
    :param tile_id: the unique ID for the tile
    :param station_id: the ID of the station to which this tile belongs.
    :param tile_simulator: a tile_simulator to use as the backend.
    :param subrack_id: ID of the subrack that controls power to this tile
    :param subrack_bay: This tile's position in its subrack
    :param tpm_version: TPM version: "tpm_v1_2" or "tpm_v1_6"
    :param preadu_level_property: the tpms preaduattentuaion configuration.
    :param static_time_delays: a fixture containing the static_time_delays.

    :return: a TPM component manager in the specified simulation mode.
    """
    poll_rate = 0.1
    tpm_cpld_port = 6

    return TileComponentManager(
        SimulationMode.TRUE,
        TestMode.TEST,
        logger,
        poll_rate,
        tile_id - 1,
        station_id,
        "tpm_ip",
        tpm_cpld_port,
        tpm_version,
        preadu_level_property,
        static_time_delays.tolist(),
        get_subrack_name(subrack_id),
        subrack_bay,
        unittest.mock.Mock(),
        unittest.mock.Mock(),
        unittest.mock.Mock(),
        tile_simulator,
    )


@pytest.fixture(name="tile_simulator")
def tile_simulator_fixture(logger: logging.Logger) -> TileSimulator:
    """
    Return a TileSimulator.

    :param logger: logger
    :return: a TileSimulator
    """
    return TileSimulator(logger)


@pytest.fixture(name="static_time_delays")
def static_time_delays_fixture() -> np.ndarray:
    """
    Return the static time delays.

    :return: the static time delays.
    """
    return np.array([2.5] * 32)


@pytest.fixture(name="sps_station_device")
def sps_station_device_fixture(
    integration_test_context: SpsTangoTestHarnessContext,
) -> DeviceProxy:
    """
    Return the SPS station Tango device under test.

    :param integration_test_context: the test context in which
        integration tests will be run.

    :return: the SPS station Tango device under test.
    """
    return integration_test_context.get_sps_station_device()


@pytest.fixture(name="subrack_device")
def subrack_device_fixture(
    integration_test_context: SpsTangoTestHarnessContext,
    subrack_id: int,
) -> DeviceProxy:
    """
    Return the subrack Tango device under test.

    :param integration_test_context: the test context in which
        integration tests will be run.
    :param subrack_id: ID of the subrack Tango device.

    :return: the subrack Tango device under test.
    """
    return integration_test_context.get_subrack_device(subrack_id)


@pytest.fixture(name="pdu_device")
def pdu_device_fixture(
    integration_test_context: SpsTangoTestHarnessContext,
) -> DeviceProxy:
    """
    Fixture that returns the pdu Tango device under test.

    :param integration_test_context: the test context in which
        integration tests will be run.

    :return: the tile Tango device under test.
    """
    return integration_test_context.get_pdu_device()


@pytest.fixture(name="tile_device")
def tile_device_fixture(
    integration_test_context: SpsTangoTestHarnessContext,
    tile_id: int,
) -> DeviceProxy:
    """
    Fixture that returns the tile Tango device under test.

    :param integration_test_context: the test context in which
        integration tests will be run.
    :param tile_id: ID of the tile Tango device.

    :return: the tile Tango device under test.
    """
    return integration_test_context.get_tile_device(tile_id)


@pytest.fixture(name="daq_device")
def daq_device_fixture(
    integration_test_context: SpsTangoTestHarnessContext,
) -> DeviceProxy:
    """
    Fixture that returns the daq Tango device under test.

    :param integration_test_context: the test context in which
        integration tests will be run.

    :return: the daq Tango device under test.
    """
    return integration_test_context.get_daq_device()


@pytest.fixture(name="change_event_callbacks")
def change_event_callbacks_fixture() -> MockTangoEventCallbackGroup:
    """
    Return a dictionary of callables to be used as Tango change event callbacks.

    :return: a dictionary of callables to be used as tango change event
        callbacks.
    """
    return MockTangoEventCallbackGroup(
        "subrack_state",
        "subrack_result",
        "subrack_tpm_power_state",
        "tile_state",
        "tile_command_status",
        "tile_programming_state",
        timeout=2.0,
    )
