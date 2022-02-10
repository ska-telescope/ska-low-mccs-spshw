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
from typing import Type

import pytest
from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import SimulationMode, TestMode
from tango.server import command

from ska_low_mccs import MccsDeviceProxy, MccsTile
from ska_low_mccs.component import ExtendedPowerState
from ska_low_mccs.testing import TangoHarness
from ska_low_mccs.testing.mock import MockCallable, MockChangeEventCallback, MockDeviceBuilder
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
def initial_tpm_power_mode() -> ExtendedPowerState:
    """
    Return the initial power mode of the TPM.

    :return: the initial power mode of the TPM.
    """
    return ExtendedPowerState.OFF


@pytest.fixture()
def mock_subrack(subrack_tpm_id: int, initial_tpm_power_mode: ExtendedPowerState) -> unittest.mock.Mock:
    """
    Fixture that provides a mock MccsSubrack device.

    :param subrack_tpm_id: This tile's position in its subrack
    :param initial_tpm_power_mode: the initial power mode of the
        specified TPM.

    :return: a mock MccsSubrack device.
    """
    builder = MockDeviceBuilder()
    builder.add_attribute(f"tpm{subrack_tpm_id}PowerState", initial_tpm_power_mode)
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
def mock_subrack_device_proxy(subrack_fqdn: str, logger: logging.Logger) -> MccsDeviceProxy:
    """
    Return a mock device proxy to an subrack device.

    :param subrack_fqdn: FQDN of the subrack device.
    :param logger: a logger for the device proxy to use.

    :return: a mock device proxy to an subrack device.
    """
    return MccsDeviceProxy(subrack_fqdn, logger)


@pytest.fixture()
def tile_power_mode_changed_callback(subrack_tpm_id: int) -> MockChangeEventCallback:
    """
    Return a mock callback for tile power mode change.

    :param subrack_tpm_id: This tile's position in its subrack

    :return: a mock change event callback to be registered with the tile
        device via a change event subscription, so that it gets called
        when the tile device health state changes.
    """
    return MockChangeEventCallback(f"tpm{subrack_tpm_id}PowerState")


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
    lrc_result_changed_callback: MockChangeEventCallback,
    communication_status_changed_callback: MockCallable,
    component_fault_callback: MockCallable,
) -> StaticTpmSimulatorComponentManager:
    """
    Return an static TPM simulator component manager.

    (This is a pytest fixture.)

    :param logger: the logger to be used by this object.
    :param lrc_result_changed_callback: a callback to
        be used to subscribe to device LRC result changes
    :param communication_status_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_fault_callback: callback to be called when the
        component faults (or stops faulting)

    :return: a static TPM simulator component manager.
    """
    return StaticTpmSimulatorComponentManager(
        logger,
        lrc_result_changed_callback,
        communication_status_changed_callback,
        component_fault_callback,
    )


@pytest.fixture()
def dynamic_tpm_simulator_component_manager(
    logger: logging.Logger,
    lrc_result_changed_callback: MockChangeEventCallback,
    communication_status_changed_callback: MockCallable,
    component_fault_callback: MockCallable,
) -> DynamicTpmSimulatorComponentManager:
    """
    Return an dynamic TPM simulator component manager.

    (This is a pytest fixture.)

    :param logger: the logger to be used by this object.
    :param lrc_result_changed_callback: a callback to
        be used to subscribe to device LRC result changes
    :param communication_status_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_fault_callback: callback to be called when the
        component faults (or stops faulting)

    :return: a static TPM simulator component manager.
    """
    return DynamicTpmSimulatorComponentManager(
        logger,
        lrc_result_changed_callback,
        communication_status_changed_callback,
        component_fault_callback,
    )


@pytest.fixture()
def switching_tpm_component_manager(
    simulation_mode: SimulationMode,
    test_mode: TestMode,
    logger: logging.Logger,
    lrc_result_changed_callback: MockChangeEventCallback,
    tpm_ip: str,
    tpm_cpld_port: int,
    tpm_version: str,
    communication_status_changed_callback: MockCallable,
    component_fault_callback: MockCallable,
) -> SwitchingTpmComponentManager:
    """
    Return a component manager that switches between TPM driver and simulators.

    (This is a pytest fixture.)

    :param simulation_mode: the initial simulation mode of this
        component manager
    :param test_mode: the initial test mode of this component manager
    :param logger: the logger to be used by this object.
    :param lrc_result_changed_callback: a callback to
        be used to subscribe to device LRC result changes
    :param tpm_ip: the IP address of the tile
    :param tpm_cpld_port: the port at which the tile is accessed for control
    :param tpm_version: TPM version: "tpm_v1_2" or "tpm_v1_6"
    :param communication_status_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_fault_callback: callback to be called when the
        component faults (or stops faulting)

    :return: a component manager that switches between TPM simulator and
        TPM driver.
    """
    return SwitchingTpmComponentManager(
        simulation_mode,
        test_mode,
        logger,
        lrc_result_changed_callback,
        1,  # default tile_id
        tpm_ip,
        tpm_cpld_port,
        tpm_version,
        communication_status_changed_callback,
        component_fault_callback,
    )


@pytest.fixture()
def tile_component_manager(
    tango_harness: TangoHarness,
    simulation_mode: SimulationMode,
    test_mode: TestMode,
    logger: logging.Logger,
    lrc_result_changed_callback: MockChangeEventCallback,
    tpm_ip: str,
    tpm_cpld_port: int,
    tpm_version: str,
    subrack_fqdn: str,
    subrack_tpm_id: int,
    communication_status_changed_callback: MockCallable,
    component_power_mode_changed_callback: MockCallable,
    component_fault_callback: MockCallable,
) -> TileComponentManager:
    """
    Return a tile component manager (in simulation and test mode as specified).

    (This is a pytest fixture.)

    :param tango_harness: a test harness for MCCS tango devices
    :param simulation_mode: the initial simulation mode of this
        component manager
    :param test_mode: the initial test mode of this component manager
    :param logger: the logger to be used by this object.
    :param lrc_result_changed_callback: a callback to
        be used to subscribe to device LRC result changes
    :param tpm_ip: the IP address of the tile
    :param tpm_cpld_port: the port at which the tile is accessed for control
    :param tpm_version: TPM version: "tpm_v1_2" or "tpm_v1_6"
    :param subrack_fqdn: FQDN of the subrack that controls power to
        this tile
    :param subrack_tpm_id: This tile's position in its subrack
    :param communication_status_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_power_mode_changed_callback: callback to be
        called when the component power mode changes
    :param component_fault_callback: callback to be called when the
        component faults (or stops faulting)

    :return: a TPM component manager in the specified simulation mode.
    """
    return TileComponentManager(
        simulation_mode,
        test_mode,
        logger,
        lrc_result_changed_callback,
        1,  # default tile_id
        tpm_ip,
        tpm_cpld_port,
        tpm_version,
        subrack_fqdn,
        subrack_tpm_id,
        communication_status_changed_callback,
        component_power_mode_changed_callback,
        component_fault_callback,
    )


@pytest.fixture()
def patched_tile_device_class() -> Type[MccsTile]:
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
            self.component_manager._tpm_power_mode_changed(ExtendedPowerState.OFF)

        @command()
        def MockTpmNoSupply(self: PatchedTileDevice) -> None:
            """
            Mock the subrack being turned off.

            Make the tile device think it has received a state change
            event from its subrack indicating that the subrack is now
            OFF.
            """
            self.component_manager._tpm_power_mode_changed(ExtendedPowerState.NO_SUPPLY)

        @command()
        def MockTpmOn(self: PatchedTileDevice) -> None:
            self.component_manager._tpm_power_mode_changed(ExtendedPowerState.ON)

    return PatchedTileDevice
