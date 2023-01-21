# type: ignore
# pylint: skip-file
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
from typing import Any, Callable

import pytest
from ska_control_model import (
    CommunicationStatus,
    PowerState,
    ResultCode,
    SimulationMode,
    TestMode,
)
from ska_low_mccs_common import MccsDeviceProxy
from ska_low_mccs_common.testing import TangoHarness
from ska_low_mccs_common.testing.mock import MockChangeEventCallback, MockDeviceBuilder
from ska_low_mccs_common.testing.mock.mock_callable import MockCallable
from tango.server import command

from ska_low_mccs_spshw import MccsTile
from ska_low_mccs_spshw.tile import AavsTileSimulator, TileComponentManager, TpmDriver


@pytest.fixture()
def simulation_mode() -> SimulationMode:
    """
    Return the simulation mode to be used when initialising the tile class object.

    :return: the simulation mode to be used when initialising the
        tile class object under test.
    """
    return SimulationMode.TRUE


@pytest.fixture()
def test_mode() -> TestMode:
    """
    Return the test mode to be used when initialising the tile class object.

    :return: the test mode to be used when initialising the tile
        class object.
    """
    return TestMode.TEST


@pytest.fixture
def unique_id() -> str:
    """
    Return a unique ID used to test Tango layer infrastructure.

    :return: a unique ID
    """
    return "a unique id"


@pytest.fixture()
def subrack_fqdn() -> str:
    """
    Return the FQDN of the subrack that powers the tile.

    :return: the FQDN of the subrack that powers the tile.
    """
    return "low-mccs/subrack/01"


@pytest.fixture()
def subrack_tpm_id() -> int:
    """
    Return the tile's position in the subrack.

    :return: the tile's position in the subrack
    """
    return 1


@pytest.fixture()
def initial_tpm_power_state() -> PowerState:
    """
    Return the initial power mode of the TPM.

    :return: the initial power mode of the TPM.
    """
    return PowerState.OFF


@pytest.fixture()
def mock_subrack(
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


@pytest.fixture()
def initial_mocks(
    subrack_fqdn: str,
    mock_subrack: unittest.mock.Mock,
) -> dict[str, unittest.mock.Mock]:
    """
    Return a dictionary of pre-registered device proxy mocks.

    The default fixture is overridden here to provide an MccsSubrack mock
    and an MccsTile mock..

    :param subrack_fqdn: FQDN of the subrack device
    :param mock_subrack: the mock subrack device to be provided when a device
        proxy to the subrack FQDN is requested.

    :return: a dictionary of mocks, keyed by FQDN
    """
    return {
        subrack_fqdn: mock_subrack,
    }


@pytest.fixture()
def mock_subrack_device_proxy(
    subrack_fqdn: str, logger: logging.Logger
) -> MccsDeviceProxy:
    """
    Return a mock device proxy to an subrack device.

    :param subrack_fqdn: FQDN of the subrack device.
    :param logger: a logger for the device proxy to use.

    :return: a mock device proxy to an subrack device.
    """
    return MccsDeviceProxy(subrack_fqdn, logger)


@pytest.fixture()
def mock_task_callback() -> MockCallable:
    """
    Return a MockCallable for use as a task_callback.

    :return: a mock callable to be called when the state of a task changes.
    """
    return MockCallable()


@pytest.fixture()
def component_state_changed_callback(
    mock_callback_deque_factory: Callable[[], unittest.mock.Mock],
) -> unittest.mock.Mock:
    """
    Return a mock callback for when the state of a component changes.

    :param mock_callback_deque_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the state of a
        component changes.
    """
    return mock_callback_deque_factory()


@pytest.fixture()
def tile_power_state_changed_callback(
    subrack_tpm_id: int,
) -> MockChangeEventCallback:
    """
    Return a mock callback for tile power mode change.

    :param subrack_tpm_id: This tile's position in its subrack

    :return: a mock change event callback to be registered with the tile
        device via a change event subscription, so that it gets called
        when the tile device health state changes.
    """
    return MockChangeEventCallback(f"tpm{subrack_tpm_id}PowerState")


@pytest.fixture()
def max_workers() -> int:
    """
    Return the number of worker threads.

    (This is a pytest fixture.)

    :return: the number of worker threads
    """
    return 1


@pytest.fixture()
def tpm_ip() -> str:
    """
    Return the IP address of the TPM.

    :return: the IP address of the TPM.
    """
    return "0.0.0.0"


@pytest.fixture()
def tpm_cpld_port() -> int:
    """
    Return the port at which the TPM can be controlled.

    :return: the port at which the TPM can be controlled.
    """
    return 10000


@pytest.fixture()
def tpm_version() -> str:
    """
    Return the TPM version.

    :return: the TPM version
    """
    return "tpm_v1_6"


@pytest.fixture()
def tile_id() -> int:
    """
    Return the tile id.

    :return: the tile id
    """
    return 1


@pytest.fixture()
def aavs_tile_simulator(logger: logging.Logger) -> TileComponentManager:
    """
    Return a AavsTileSimulator.

    (This is a pytest fixture.)

    :param logger: logger
    :return: a AavsTileSimulator
    """
    return AavsTileSimulator(
        logger,
    )


@pytest.fixture()
def tpm_driver(
    logger: logging.Logger,
    max_workers: int,
    tile_id: int,
    aavs_tile_simulator: AavsTileSimulator,
    tpm_version: str,
    communication_state_changed_callback: Callable[[CommunicationStatus], None],
    component_state_changed_callback: Callable[[dict[str, Any]], None],
) -> TpmDriver:
    """
    Return a TpmDriver driving a AavsTileSimulator.

    (This is a pytest fixture.)

    :param logger: the logger to be used by this object.
    :param max_workers: nos. of worker threads
    :param tile_id: the unique ID for the tile
    :param aavs_tile_simulator: the aavs_tile_simulator
    :param tpm_version: the tpm_version
    :param communication_state_changed_callback: callback  to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_state_changed_callback: callback to be called when the
        component state changes

    :return: Tpmdriver with simulated tile.
    """
    return TpmDriver(
        logger,
        max_workers,
        tile_id,
        aavs_tile_simulator,
        tpm_version,
        communication_state_changed_callback,
        component_state_changed_callback,
    )


@pytest.fixture()
def tile_component_manager(
    tango_harness: TangoHarness,
    simulation_mode: SimulationMode,
    test_mode: TestMode,
    logger: logging.Logger,
    max_workers: int,
    tile_id: int,
    tpm_ip: str,
    tpm_cpld_port: int,
    tpm_version: str,
    subrack_fqdn: str,
    subrack_tpm_id: int,
    communication_state_changed_callback: Callable[[CommunicationStatus], None],
    component_state_changed_callback: Callable[[dict[str, Any]], None],
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
    :param subrack_fqdn: FQDN of the subrack that controls power to
        this tile
    :param subrack_tpm_id: This tile's position in its subrack
    :param max_workers: nos. of worker threads
    :param communication_state_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_state_changed_callback: callback to be
        called when the component state changes

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
        subrack_fqdn,
        subrack_tpm_id,
        communication_state_changed_callback,
        component_state_changed_callback,
    )


@pytest.fixture()
def mock_tile_component_manager(
    simulation_mode: SimulationMode,
    test_mode: TestMode,
    logger: logging.Logger,
    max_workers: int,
    tile_id: int,
    tpm_ip: str,
    tpm_cpld_port: int,
    tpm_version: str,
    subrack_fqdn: str,
    subrack_tpm_id: int,
    communication_state_changed_callback: Callable[[CommunicationStatus], None],
    component_state_changed_callback: Callable[[dict[str, Any]], None],
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
    :param subrack_fqdn: FQDN of the subrack that controls power to
        this tile
    :param subrack_tpm_id: This tile's position in its subrack
    :param max_workers: nos. of worker threads
    :param communication_state_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_state_changed_callback: callback to be
        called when the component state changes

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
        subrack_fqdn,
        subrack_tpm_id,
        communication_state_changed_callback,
        component_state_changed_callback,
    )


@pytest.fixture()
def patched_tile_device_class(
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
            # self._communication_state: Optional[CommunicationStatus] = None
            mock_tile_component_manager._communication_state_changed_callback = (
                self._component_communication_state_changed
            )
            mock_tile_component_manager._component_state_changed_callback = (
                self.component_state_changed_callback
            )
            orchestrator = mock_tile_component_manager._tile_orchestrator
            orchestrator._component_state_changed_callback = (
                self.component_state_changed_callback
            )
            orchestrator._communication_state_changed_callback = (
                self._component_communication_state_changed
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
            self.component_manager._tpm_power_state_changed(PowerState.ON)

    return PatchedTileDevice
