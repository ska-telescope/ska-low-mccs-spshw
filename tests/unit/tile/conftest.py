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
from typing import Callable

import pytest
from ska_control_model import PowerState, ResultCode, SimulationMode, TestMode
from ska_low_mccs_common import MccsDeviceProxy
from ska_low_mccs_common.testing.mock import MockDeviceBuilder
from ska_tango_testing.context import TangoContextProtocol
from ska_tango_testing.mock import MockCallableGroup
from tango.server import command

from ska_low_mccs_spshw import MccsTile
from ska_low_mccs_spshw.tile import (
    TileSimulator,
    DynamicTpmSimulator,
    DynamicTpmSimulatorComponentManager,
    StaticTpmSimulator,
    StaticTpmSimulatorComponentManager,
    TileComponentManager,
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


@pytest.fixture(name="simulation_mode")
def simulation_mode_fixture() -> SimulationMode:
    """
    Return the simulation mode to be used when initialising the tile class object.

    :return: the simulation mode to be used when initialising the
        tile class object under test.
    """
    return SimulationMode.TRUE


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


@pytest.fixture(name="mock_subrack")
def mock_subrack_fixture(
    subrack_tpm_id: int, initial_tpm_power_state: PowerState
) -> unittest.mock.Mock:
    """
    Fixture that provides a mock MccsSubrack device.

    :param subrack_tpm_id: This tile's position in its subrack
    :param initial_tpm_power_state: the initial power mode of the
        specified TPM.

    :return: a mock MccsSubrack device.
    """
    builder = MockDeviceBuilder()
    builder.add_attribute(f"tpm{subrack_tpm_id}PowerState", initial_tpm_power_state)
    builder.add_result_command("PowerOnTpm", ResultCode.OK)
    builder.add_result_command("PowerOffTpm", ResultCode.OK)
    return builder()


@pytest.fixture(name="mock_subrack_device_proxy")
def mock_subrack_device_proxy_fixture(
    subrack_name: str, logger: logging.Logger
) -> MccsDeviceProxy:
    """
    Return a mock device proxy to an subrack device.

    :param subrack_name: name of the subrack device.
    :param logger: a logger for the device proxy to use.

    :return: a mock device proxy to an subrack device.
    """
    return MccsDeviceProxy(subrack_name, logger)


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


@pytest.fixture(name="max_workers")
def max_workers_fixture() -> int:
    """
    Return the number of worker threads.

    (This is a pytest fixture.)

    :return: the number of worker threads
    """
    return 1


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


@pytest.fixture(name="tile_id")
def tile_id_fixture() -> int:
    """
    Return the tile id.

    :return: the tile id
    """
    return 1


@pytest.fixture(name="static_tpm_simulator")
def static_tpm_simulator_fixture(logger: logging.Logger) -> StaticTpmSimulator:
    """
    Return a static TPM simulator.

    (This is a pytest fixture.)

    :param logger: a object that implements the standard logging
        interface of :py:class:`logging.Logger`

    :return: a static TPM simulator
    """
    return StaticTpmSimulator(logger)


@pytest.fixture(name="dynamic_tpm_simulator")
def dynamic_tpm_simulator_fixture(logger: logging.Logger) -> DynamicTpmSimulator:
    """
    Return a dynamic TPM simulator.

    (This is a pytest fixture.)

    :param logger: a object that implements the standard logging
        interface of :py:class:`logging.Logger`

    :return: a dynamic TPM simulator
    """
    return DynamicTpmSimulator(logger)


@pytest.fixture(name="static_tpm_simulator_component_manager")
def static_tpm_simulator_component_manager_fixture(
    logger: logging.Logger,
    callbacks: MockCallableGroup,
) -> StaticTpmSimulatorComponentManager:
    """
    Return an static TPM simulator component manager.

    (This is a pytest fixture.)

    :param logger: the logger to be used by this object.
    :param callbacks: dictionary of driver callbacks.

    :return: a static TPM simulator component manager.
    """
    return StaticTpmSimulatorComponentManager(
        logger,
        callbacks["communication_status"],
        callbacks["component_state"],
    )


@pytest.fixture(name="dynamic_tpm_simulator_component_manager")
def dynamic_tpm_simulator_component_manager_fixture(
    logger: logging.Logger,
    callbacks: MockCallableGroup,
) -> DynamicTpmSimulatorComponentManager:
    """
    Return an dynamic TPM simulator component manager.

    (This is a pytest fixture.)

    :param logger: the logger to be used by this object.
    :param callbacks: dictionary of driver callbacks.

    :return: a static TPM simulator component manager.
    """
    return DynamicTpmSimulatorComponentManager(
        logger,
        callbacks["communication_status"],
        callbacks["component_state"],
    )


# pylint: disable=too-many-arguments
@pytest.fixture(name="tile_component_manager")
def tile_component_manager_fixture(
    tango_harness: TangoContextProtocol,
    simulation_mode: SimulationMode,
    test_mode: TestMode,
    logger: logging.Logger,
    max_workers: int,
    tile_id: int,
    tpm_ip: str,
    tpm_cpld_port: int,
    tpm_version: str,
    subrack_name: str,
    subrack_tpm_id: int,
    callbacks: MockCallableGroup,
) -> TileComponentManager:
    """
    Return a tile component manager (in simulation and test mode as specified).

    (This is a pytest fixture.)

    :param tango_harness: a test harness for MCCS tango devices
    :param simulation_mode: the initial simulation mode of this
        component manager
    :param test_mode: the initial test mode of this component manager
    :param logger: the logger to be used by this object.
    :param tile_id: the unique ID for the tile
    :param tpm_ip: the IP address of the tile
    :param tpm_cpld_port: the port at which the tile is accessed for control
    :param tpm_version: TPM version: "tpm_v1_2" or "tpm_v1_6"
    :param subrack_name: FQDN of the subrack that controls power to
        this tile
    :param subrack_tpm_id: This tile's position in its subrack
    :param max_workers: nos. of worker threads
    :param callbacks: dictionary of driver callbacks.

    :return: a TPM component manager in the specified simulation mode.
    """
    return TileComponentManager(
        simulation_mode,
        test_mode,
        logger,
        max_workers,
        tile_id,
        tpm_ip,
        tpm_cpld_port,
        tpm_version,
        subrack_name,
        subrack_tpm_id,
        callbacks["communication_status"],
        callbacks["component_state"],
    )


@pytest.fixture(name="tile_simulator")
def tile_simulator_fixture(logger: logging.Logger) -> TileSimulator:
    """
    Return a TileSimulator.

    (This is a pytest fixture.)

    :param logger: logger
    :return: a TileSimulator
    """
    return TileSimulator(logger)


# pylint: disable=too-many-arguments
@pytest.fixture(name="mock_tile_component_manager")
def mock_tile_component_manager_fixture(
    simulation_mode: SimulationMode,
    test_mode: TestMode,
    logger: logging.Logger,
    max_workers: int,
    tile_id: int,
    tpm_ip: str,
    tpm_cpld_port: int,
    tpm_version: str,
    subrack_name: str,
    subrack_tpm_id: int,
    callbacks: MockCallableGroup,
) -> TileComponentManager:
    """
    Return a tile component manager (in simulation and test mode as specified).

    (This is a pytest fixture.)

    :param simulation_mode: the initial simulation mode of this
        component manager
    :param test_mode: the initial test mode of this component manager
    :param logger: the logger to be used by this object.
    :param tile_id: the unique ID for the tile
    :param tpm_ip: the IP address of the tile
    :param tpm_cpld_port: the port at which the tile is accessed for control
    :param tpm_version: TPM version: "tpm_v1_2" or "tpm_v1_6"
    :param subrack_name: name of the subrack that controls power to
        this tile
    :param subrack_tpm_id: This tile's position in its subrack
    :param max_workers: nos. of worker threads
    :param callbacks: dictionary of driver callbacks.

    :return: a TPM component manager in the specified simulation mode.
    """
    return TileComponentManager(
        simulation_mode,
        test_mode,
        logger,
        max_workers,
        tile_id,
        tpm_ip,
        tpm_cpld_port,
        tpm_version,
        subrack_name,
        subrack_tpm_id,
        callbacks["communication_status"],
        callbacks["component_state"],
    )


@pytest.fixture(name="patched_tile_device_class")
def patched_tile_device_class_fixture(
    mock_tile_component_manager: TileComponentManager,
) -> type[MccsTile]:
    """
    Return a tile device class patched with extra methods for testing.

    :param mock_tile_component_manager: A mock component manager.

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
            mock_tile_component_manager.set_communication_state_callback(
                self._communication_state_changed,
            )
            mock_tile_component_manager.set_component_state_callback(
                self._component_state_changed,
            )

            return mock_tile_component_manager

        @command()
        def MockTpmOff(self: PatchedTileDevice) -> None:
            """
            Mock the subrack being turned on.

            Make the tile device think it has received a state change
            event from its subrack indicating that the suback is now ON.
            """
            self.component_manager._tpm_power_state_changed(PowerState.OFF)

        @command()
        def MockTpmNoSupply(self: PatchedTileDevice) -> None:
            """
            Mock the subrack being turned off.

            Make the tile device think it has received a state change
            event from its subrack indicating that the subrack is now
            OFF.
            """
            self.component_manager._tpm_power_state_changed(PowerState.NO_SUPPLY)

        @command()
        def MockTpmOn(self: PatchedTileDevice) -> None:
            """Mock power on the tpm."""
            self.component_manager._tpm_power_state_changed(PowerState.ON)

    return PatchedTileDevice
