# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module defined a pytest test harness for testing the MCCS tile module."""
from __future__ import annotations

import logging
import unittest.mock
from typing import Callable, Iterator

import pytest
import tango
from ska_control_model import PowerState, ResultCode, SimulationMode, TestMode
from ska_low_mccs_common.testing.mock import MockDeviceBuilder
from ska_tango_testing.mock import MockCallableGroup
from tango.server import command

from ska_low_mccs_spshw import MccsTile
from ska_low_mccs_spshw.tile import (
    BaseTpmSimulator,
    DynamicTpmSimulator,
    StaticTpmSimulator,
    TileComponentManager,
    TileSimulator,
)
from tests.harness import (
    SpsTangoTestHarness,
    SpsTangoTestHarnessContext,
    get_subrack_name,
)


@pytest.fixture(name="mock_factory")
def mock_factory_fixture() -> Callable[[], unittest.mock.Mock]:
    """
    Fixture that provides a mock factory for device proxy mocks.

    This default factory
    provides vanilla mocks, but this fixture can be overridden by test modules/classes
    to provide mocks with specified behaviours.

    :return: a factory for device proxy mocks
    """
    return MockDeviceBuilder()


@pytest.fixture(name="test_mode")
def test_mode_fixture() -> TestMode:
    """
    Return the test mode to be used when initialising the tile class object.

    :return: the test mode to be used when initialising the tile
        class object.
    """
    return TestMode.TEST


@pytest.fixture(name="unique_id")
def unique_id_fixture() -> str:
    """
    Return a unique ID used to test Tango layer infrastructure.

    :return: a unique ID
    """
    return "a unique id"


@pytest.fixture(name="subrack_tpm_id")
def subrack_tpm_id_fixture() -> int:
    """
    Return the tile's position in the subrack.

    :return: the tile's position in the subrack
    """
    return 1


@pytest.fixture(name="initial_tpm_power_state")
def initial_tpm_power_state_fixture() -> PowerState:
    """
    Return the initial power mode of the TPM.

    :return: the initial power mode of the TPM.
    """
    return PowerState.OFF


@pytest.fixture(name="mock_subrack_device_proxy")
def mock_subrack_device_proxy_fixture(
    subrack_tpm_id: int, initial_tpm_power_state: PowerState
) -> unittest.mock.Mock:
    """
    Fixture that provides a mock subrack device proxy.

    :param subrack_tpm_id: This tile's position in its subrack
    :param initial_tpm_power_state: the initial power mode of the
        specified TPM.

    :return: a mock MccsSubrack device.
    """
    builder = MockDeviceBuilder()
    builder.add_attribute("tpm1PowerState", initial_tpm_power_state)
    builder.add_result_command("PowerOnTpm", ResultCode.OK)
    builder.add_result_command("PowerOffTpm", ResultCode.OK)
    return builder()


@pytest.fixture(name="test_context")
def test_context_fixture(
    subrack_id: int,
    mock_subrack_device_proxy: unittest.mock.Mock,
) -> Iterator[None]:
    """
    Yield into a context in which Tango is running, with a mock subrack device.

    :param subrack_id: ID of the subrack Tango device to be mocked
    :param mock_subrack_device_proxy: a mock subrack device proxy that
        has been configured with the required subrack behaviours.

    :yields: into a context in which Tango is running, with a mock
        subrack device.
    """
    harness = SpsTangoTestHarness()
    harness.add_mock_subrack_device(subrack_id, mock_subrack_device_proxy)
    with harness:
        yield


@pytest.fixture(name="callbacks")
def callbacks_fixture() -> MockCallableGroup:
    """
    Return a dictionary of callables to be used as callbacks.

    :return: a dictionary of callables to be used as callbacks.
    """
    return MockCallableGroup(
        "communication_status",
        "component_state",
        "task",
        timeout=5.0,
    )


@pytest.fixture(name="poll_rate")
def poll_rate_fixture() -> float:
    """
    Return the poll rate.

    :return: poll rate
    """
    return 0.05


@pytest.fixture(name="tpm_ip")
def tpm_ip_fixture() -> str:
    """
    Return the IP address of the TPM.

    :return: the IP address of the TPM.
    """
    return "0.0.0.0"


@pytest.fixture(name="tpm_cpld_port")
def tpm_cpld_port_fixture() -> int:
    """
    Return the port at which the TPM can be controlled.

    :return: the port at which the TPM can be controlled.
    """
    return 10000


@pytest.fixture(name="tpm_version")
def tpm_version_fixture() -> str:
    """
    Return the TPM version.

    :return: the TPM version
    """
    return "tpm_v1_6"


@pytest.fixture(name="mock_tpm")
def mock_tpm_fixture(logger: logging.Logger) -> BaseTpmSimulator:
    """
    Return the TPM version.

    :param logger: the logger to be used by this object.

    :return: the TPM version
    """
    return BaseTpmSimulator(
        logger, unittest.mock.MagicMock(), unittest.mock.MagicMock()
    )


# pylint: disable=too-many-arguments
@pytest.fixture(name="plain_tile_component_manager")
def plain_tile_component_manager_fixture(
    test_context: SpsTangoTestHarnessContext,
    test_mode: TestMode,
    logger: logging.Logger,
    poll_rate: float,
    tile_id: int,
    station_id: int,
    tpm_ip: str,
    tpm_cpld_port: int,
    tpm_version: str,
    subrack_id: int,
    subrack_tpm_id: int,
    callbacks: MockCallableGroup,
) -> TileComponentManager:
    """
    Return a tile component manager (in simulation and test mode as specified).

    :param test_context: a test context in which Tango is running,
        with a single mock subrack device.
    :param test_mode: the initial test mode of this component manager
    :param logger: the logger to be used by this object.
    :param tile_id: the unique ID for the tile
    :param station_id: the ID of the station to which this tile belongs.
    :param tpm_ip: the IP address of the tile
    :param tpm_cpld_port: the port at which the tile is accessed for control
    :param tpm_version: TPM version: "tpm_v1_2" or "tpm_v1_6"
    :param subrack_id: ID of the subrack that controls power to this tile
    :param subrack_tpm_id: This tile's position in its subrack
    :param poll_rate: the polling rate
    :param callbacks: dictionary of driver callbacks.

    :return: a TPM component manager in the specified simulation mode.
    """
    return TileComponentManager(
        SimulationMode.TRUE,
        test_mode,
        logger,
        poll_rate,
        tile_id,
        station_id,
        tpm_ip,
        tpm_cpld_port,
        tpm_version,
        get_subrack_name(subrack_id),
        subrack_tpm_id,
        callbacks["communication_status"],
        callbacks["component_state"],
    )


# pylint: disable=too-many-arguments
@pytest.fixture(name="tile_component_manager")
def tile_component_manager_fixture(
    test_context: SpsTangoTestHarnessContext,
    test_mode: TestMode,
    logger: logging.Logger,
    poll_rate: float,
    tile_id: int,
    station_id: int,
    tpm_ip: str,
    tpm_cpld_port: int,
    tpm_version: str,
    subrack_id: int,
    subrack_tpm_id: int,
    callbacks: MockCallableGroup,
    mock_tpm: BaseTpmSimulator,
) -> TileComponentManager:
    """
    Return a tile component manager (in simulation and test mode as specified).

    :param test_context: a test context in which Tango is running,
        with a single mock subrack device.
    :param test_mode: the initial test mode of this component manager
    :param logger: the logger to be used by this object.
    :param tile_id: the unique ID for the tile
    :param station_id: the ID of the station to which this tile belongs.
    :param tpm_ip: the IP address of the tile
    :param tpm_cpld_port: the port at which the tile is accessed for control
    :param tpm_version: TPM version: "tpm_v1_2" or "tpm_v1_6"
    :param subrack_id: ID of the subrack that controls power to this tile
    :param subrack_tpm_id: This tile's position in its subrack
    :param poll_rate: the polling rate
    :param callbacks: dictionary of driver callbacks.
    :param mock_tpm: The mock_tpm fixture

    :return: a TPM component manager in the specified simulation mode.
    """
    return TileComponentManager(
        SimulationMode.TRUE,
        test_mode,
        logger,
        poll_rate,
        tile_id,
        station_id,
        tpm_ip,
        tpm_cpld_port,
        tpm_version,
        get_subrack_name(subrack_id),
        subrack_tpm_id,
        callbacks["communication_status"],
        callbacks["component_state"],
        mock_tpm,
    )


@pytest.fixture(name="tile_simulator")
def tile_simulator_fixture(logger: logging.Logger) -> TileSimulator:
    """
    Return a TileSimulator.

    :param logger: logger
    :return: a TileSimulator
    """
    return TileSimulator(logger)


# pylint: disable=too-many-arguments
@pytest.fixture(name="dynamic_tile_component_manager")
def dynamic_tile_component_manager_fixture(
    test_context: SpsTangoTestHarnessContext,
    logger: logging.Logger,
    poll_rate: float,
    tile_id: int,
    station_id: int,
    tpm_ip: str,
    tpm_cpld_port: int,
    tpm_version: str,
    subrack_id: int,
    subrack_tpm_id: int,
    callbacks: MockCallableGroup,
) -> TileComponentManager:
    """
    Return a tile component manager (That drives a DynamicTileSimulator).

    :param test_context: a test context in which Tango is running,
        with a single mock subrack device.
    :param logger: the logger to be used by this object.
    :param tile_id: the unique ID for the tile
    :param station_id: the ID of the station to which this tile belongs.
    :param tpm_ip: the IP address of the tile
    :param tpm_cpld_port: the port at which the tile is accessed for control
    :param tpm_version: TPM version: "tpm_v1_2" or "tpm_v1_6"
    :param subrack_id: ID of the subrack that controls power to this tile
    :param subrack_tpm_id: This tile's position in its subrack
    :param poll_rate: the polling rate
    :param callbacks: dictionary of driver callbacks.

    :return: a TPM component manager in the specified simulation mode.
    """
    component_manager = TileComponentManager(
        SimulationMode.TRUE,
        TestMode.NONE,
        logger,
        poll_rate,
        tile_id,
        station_id,
        tpm_ip,
        tpm_cpld_port,
        tpm_version,
        get_subrack_name(subrack_id),
        subrack_tpm_id,
        callbacks["communication_status"],
        callbacks["component_state"],
        DynamicTpmSimulator(logger, callbacks["component_state"]),
    )
    component_manager._tpm_driver._communication_state_changed = (  # type: ignore
        component_manager._tpm_communication_state_changed
    )
    component_manager._tpm_driver._component_state_changed_callback = (
        component_manager._update_component_state
    )
    return component_manager


# pylint: disable=too-many-arguments
@pytest.fixture(name="static_tile_component_manager")
def static_tile_component_manager_fixture(
    test_context: SpsTangoTestHarnessContext,
    test_mode: TestMode,
    logger: logging.Logger,
    poll_rate: float,
    tile_id: int,
    station_id: int,
    tpm_ip: str,
    tpm_cpld_port: int,
    tpm_version: str,
    subrack_id: int,
    subrack_tpm_id: int,
    callbacks: MockCallableGroup,
) -> TileComponentManager:
    """
    Return a tile component manager (in simulation and test mode as specified).

    :param test_context: a test context in which Tango is running,
        with a single mock subrack device.
    :param test_mode: the initial test mode of this component manager
    :param logger: the logger to be used by this object.
    :param tile_id: the unique ID for the tile
    :param station_id: the ID of the station to which the tile belongs.
    :param tpm_ip: the IP address of the tile
    :param tpm_cpld_port: the port at which the tile is accessed for control
    :param tpm_version: TPM version: "tpm_v1_2" or "tpm_v1_6"
    :param subrack_id: ID of the subrack that controls power to this tile
    :param subrack_tpm_id: This tile's position in its subrack
    :param poll_rate: the polling rate
    :param callbacks: dictionary of driver callbacks.

    :return: a TPM component manager in the specified simulation mode.
    """
    component_manager = TileComponentManager(
        SimulationMode.TRUE,
        test_mode,
        logger,
        poll_rate,
        tile_id,
        station_id,
        tpm_ip,
        tpm_cpld_port,
        tpm_version,
        get_subrack_name(subrack_id),
        subrack_tpm_id,
        callbacks["communication_status"],
        callbacks["component_state"],
        StaticTpmSimulator(logger, callbacks["component_state"]),
    )
    component_manager._tpm_driver._communication_state_changed = (  # type: ignore
        component_manager._tpm_communication_state_changed
    )
    component_manager._tpm_driver._component_state_changed_callback = (
        component_manager._update_component_state
    )
    return component_manager


@pytest.fixture(name="patched_tile_device_class")
def patched_tile_device_class_fixture(
    plain_tile_component_manager: TileComponentManager,
    tile_id: int,
) -> type[MccsTile]:
    """
    Return a tile device class patched with extra methods for testing.

    :param plain_tile_component_manager: A mock component manager.
    :param tile_id: the unique ID for the tile

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

        def create_component_manager(
            self: PatchedTileDevice,
        ) -> TileComponentManager:
            """
            Return a mock component manager instead of the usual one.

            :return: a mock component manager
            """
            plain_tile_component_manager.set_communication_state_callback(
                self._communication_state_changed,
            )
            plain_tile_component_manager.set_component_state_callback(
                self._component_state_changed,
            )

            return plain_tile_component_manager

        @command()
        def MockTpmOff(self: PatchedTileDevice) -> None:
            """
            Mock the subrack being turned on.

            Make the tile device think it has received a state change
            event from its subrack indicating that the suback is now ON.
            """
            self.component_manager._subrack_says_tpm_power_changed(
                f"tpm{tile_id}PowerState",
                PowerState.OFF,
                tango.EventType.CHANGE_EVENT,
            )

        @command()
        def MockTpmNoSupply(self: PatchedTileDevice) -> None:
            """
            Mock the subrack being turned off.

            Make the tile device think it has received a state change
            event from its subrack indicating that the subrack is now
            OFF.
            """
            self.component_manager._subrack_says_tpm_power_changed(
                f"tpm{tile_id}PowerState",
                PowerState.NO_SUPPLY,
                tango.EventType.CHANGE_EVENT,
            )

        @command()
        def MockTpmOn(self: PatchedTileDevice) -> None:
            """Mock power on the tpm."""
            self.component_manager._subrack_says_tpm_power_changed(
                f"tpm{tile_id}PowerState",
                PowerState.ON,
                tango.EventType.CHANGE_EVENT,
            )

    return PatchedTileDevice
