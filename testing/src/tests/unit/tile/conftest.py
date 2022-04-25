# -*- coding: utf-8 -*-
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
from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import (
    CommunicationStatus,
    PowerState,
    SimulationMode,
    TestMode,
)
from tango.server import command

from ska_low_mccs import MccsDeviceProxy, MccsTile
from ska_low_mccs.testing import TangoHarness
from ska_low_mccs.testing.mock import MockChangeEventCallback, MockDeviceBuilder
from ska_low_mccs.tile import (
    DynamicTpmSimulator,
    DynamicTpmSimulatorComponentManager,
    StaticTpmSimulator,
    StaticTpmSimulatorComponentManager,
    SwitchingTpmComponentManager,
    TileComponentManager,
)


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
def component_state_changed_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> unittest.mock.Mock:
    """
    Return a mock callback for when the state of a component changes.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the state of a
        component changes.
    """
    return mock_callback_factory()


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
def static_tpm_simulator(logger: logging.Logger) -> StaticTpmSimulator:
    """
    Return a static TPM simulator.

    (This is a pytest fixture.)

    :param logger: a object that implements the standard logging
        interface of :py:class:`logging.Logger`

    :return: a static TPM simulator
    """
    return StaticTpmSimulator(logger)


@pytest.fixture()
def dynamic_tpm_simulator(logger: logging.Logger) -> DynamicTpmSimulator:
    """
    Return a dynamic TPM simulator.

    (This is a pytest fixture.)

    :param logger: a object that implements the standard logging
        interface of :py:class:`logging.Logger`

    :return: a dynamic TPM simulator
    """
    return DynamicTpmSimulator(logger)


@pytest.fixture()
def static_tpm_simulator_component_manager(
    logger: logging.Logger,
    max_workers: int,
    communication_status_changed_callback: Callable[[CommunicationStatus], None],
    component_state_changed_callback: Callable[[dict[str, Any]], None],
) -> StaticTpmSimulatorComponentManager:
    """
    Return an static TPM simulator component manager.

    (This is a pytest fixture.)

    :param logger: the logger to be used by this object.
    :param max_workers: nos of worker threads
    :param communication_status_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_state_changed_callback: callback to be
        called when the state changes

    :return: a static TPM simulator component manager.
    """
    return StaticTpmSimulatorComponentManager(
        logger,
        max_workers,
        communication_status_changed_callback,
        component_state_changed_callback,
    )


@pytest.fixture()
def dynamic_tpm_simulator_component_manager(
    logger: logging.Logger,
    max_workers: int,
    communication_status_changed_callback: Callable[[CommunicationStatus], None],
    component_state_changed_callback: Callable[[dict[str, Any]], None],
) -> DynamicTpmSimulatorComponentManager:
    """
    Return an dynamic TPM simulator component manager.

    (This is a pytest fixture.)

    :param logger: the logger to be used by this object.
    :param max_workers: nos of worker threads
    :param communication_status_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_state_changed_callback: callback to be
        called when the state changes

    :return: a static TPM simulator component manager.
    """
    return DynamicTpmSimulatorComponentManager(
        logger,
        max_workers,
        communication_status_changed_callback,
        component_state_changed_callback,
    )


@pytest.fixture()
def switching_tpm_component_manager(
    simulation_mode: SimulationMode,
    test_mode: TestMode,
    logger: logging.Logger,
    max_workers: int,
    tile_id: int,
    tpm_ip: str,
    tpm_cpld_port: int,
    tpm_version: str,
    communication_status_changed_callback: Callable[[CommunicationStatus], None],
    component_state_changed_callback: Callable[[dict[str, Any]], None],
) -> SwitchingTpmComponentManager:
    """
    Return a component manager that switches between TPM driver and simulators.

    (This is a pytest fixture.)

    :param simulation_mode: the initial simulation mode of this
        component manager
    :param test_mode: the initial test mode of this component manager
    :param logger: the logger to be used by this object.
    :param tpm_ip: the IP address of the tile
    :param tpm_cpld_port: the port at which the tile is accessed for control
    :param tpm_version: TPM version: "tpm_v1_2" or "tpm_v1_6"
    :param max_workers: nos. of worker threads
    :param tile_id: the unique ID for the tile
    :param communication_status_changed_callback: callback  to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_state_changed_callback: callback to be called when the
        component state changes

    :return: a component manager that switches between TPM simulator and
        TPM driver.
    """
    return SwitchingTpmComponentManager(
        simulation_mode,
        test_mode,
        logger,
        max_workers,
        tile_id,
        tpm_ip,
        tpm_cpld_port,
        tpm_version,
        communication_status_changed_callback,
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
    communication_status_changed_callback: Callable[[CommunicationStatus], None],
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
    :param communication_status_changed_callback: callback to be
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
        communication_status_changed_callback,
        component_state_changed_callback,
    )


@pytest.fixture()
def patched_tile_device_class() -> MccsTile:
    """
    Return a tile device class patched with extra methods for testing.

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
