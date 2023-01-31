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

import functools
import logging
import unittest.mock
from typing import Any, Callable, Generator

import pytest
from ska_control_model import (
    CommunicationStatus,
    PowerState,
    ResultCode,
    SimulationMode,
    TestMode,
)
from ska_low_mccs_common import MccsDeviceProxy
from ska_low_mccs_common.testing.mock import (
    MockCallable,
    MockChangeEventCallback,
    MockDeviceBuilder,
)
from ska_low_mccs_common.testing.tango_harness import (
    ClientProxyTangoHarness,
    DevicesToLoadType,
    MccsDeviceInfo,
    MockingTangoHarness,
    StartingStateTangoHarness,
    TangoHarness,
    TestContextTangoHarness,
)
from tango.server import command

from ska_low_mccs_spshw import MccsTile
from ska_low_mccs_spshw.tile import (
    DynamicTpmSimulator,
    DynamicTpmSimulatorComponentManager,
    StaticTileSimulator,
    StaticTpmSimulator,
    StaticTpmSimulatorComponentManager,
    TileComponentManager,
)


@pytest.fixture()
def mock_factory() -> Callable[[], unittest.mock.Mock]:
    """
    Fixture that provides a mock factory for device proxy mocks.

    This default factory
    provides vanilla mocks, but this fixture can be overridden by test modules/classes
    to provide mocks with specified behaviours.

    :return: a factory for device proxy mocks
    """
    return MockDeviceBuilder()


@pytest.fixture(scope="session")
def tango_harness_factory(
    logger: logging.Logger,
) -> Callable[
    [
        dict[str, Any],
        DevicesToLoadType,
        Callable[[], unittest.mock.Mock],
        dict[str, unittest.mock.Mock],
    ],
    TangoHarness,
]:
    """
    Return a factory for creating a test harness for testing Tango devices.

    :param logger: the logger to be used by this object.

    :return: a tango harness factory
    """

    class _CPTCTangoHarness(ClientProxyTangoHarness, TestContextTangoHarness):
        """
        A Tango test harness.

        With the client proxy functionality of
        :py:class:`~ska_low_mccs_common.testing.tango_harness.ClientProxyTangoHarness`
        within the lightweight test context provided by
        :py:class:`~ska_low_mccs_common.testing.tango_harness.TestContextTangoHarness`.
        """

        pass

    def build_harness(
        tango_config: dict[str, Any],
        devices_to_load: DevicesToLoadType,
        mock_factory: Callable[[], unittest.mock.Mock],
        initial_mocks: dict[str, unittest.mock.Mock],
    ) -> TangoHarness:
        """
        Build the Tango test harness.

        :param tango_config: basic configuration information for a tango
            test harness
        :param devices_to_load: fixture that provides a specification of the
            devices that are to be included in the devices_info dictionary
        :param mock_factory: the factory to be used to build mocks
        :param initial_mocks: a pre-build dictionary of mocks to be used
            for particular

        :return: a tango test harness
        """
        if devices_to_load is None:
            device_info = None
        else:
            device_info = MccsDeviceInfo(**devices_to_load)

        tango_harness = _CPTCTangoHarness(device_info, logger, **tango_config)
        starting_state_harness = StartingStateTangoHarness(tango_harness)
        mocking_harness = MockingTangoHarness(
            starting_state_harness, mock_factory, initial_mocks
        )

        return mocking_harness

    return build_harness


@pytest.fixture()
def tango_config() -> dict[str, Any]:
    """
    Fixture that returns basic configuration information for a Tango test harness.

    For example whether or not to run in a separate process.

    :return: a dictionary of configuration key-value pairs
    """
    return {"process": False}


@pytest.fixture()
def tango_harness(
    tango_harness_factory: Callable[
        [
            dict[str, Any],
            DevicesToLoadType,
            Callable[[], unittest.mock.Mock],
            dict[str, unittest.mock.Mock],
        ],
        TangoHarness,
    ],
    tango_config: dict[str, str],
    devices_to_load: DevicesToLoadType,
    mock_factory: Callable[[], unittest.mock.Mock],
    initial_mocks: dict[str, unittest.mock.Mock],
) -> Generator[TangoHarness, None, None]:
    """
    Create a test harness for testing Tango devices.

    :param tango_harness_factory: a factory that provides a test harness
        for testing tango devices
    :param tango_config: basic configuration information for a tango
        test harness
    :param devices_to_load: fixture that provides a specification of the
        devices that are to be included in the devices_info dictionary
    :param mock_factory: the factory to be used to build mocks
    :param initial_mocks: a pre-build dictionary of mocks to be used
        for particular

    :yields: a tango test harness
    """
    with tango_harness_factory(
        tango_config, devices_to_load, mock_factory, initial_mocks
    ) as harness:
        yield harness


@pytest.fixture()
def mock_callback_called_timeout() -> float:
    """
    Return the time to wait for a mock callback to be called when a call is expected.

    This is a high value because calls will usually arrive much much
    sooner, but we should be prepared to wait plenty of time before
    giving up and failing a test.

    :return: the time to wait for a mock callback to be called when a
        call is asserted.
    """
    return 7.5


@pytest.fixture()
def mock_callback_not_called_timeout() -> float:
    """
    Return the time to wait for a mock callback to be called when a call is unexpected.

    An assertion that a callback has not been called can only be passed
    once we have waited the full timeout period without a call being
    received. Thus, having a high value for this timeout will make such
    assertions very slow. It is better to keep this value fairly low,
    and accept the risk of an assertion passing prematurely.

    :return: the time to wait for a mock callback to be called when a
        call is unexpected.
    """
    return 0.5


@pytest.fixture()
def mock_change_event_callback_factory(
    mock_callback_called_timeout: float,
    mock_callback_not_called_timeout: float,
) -> Callable[[str], MockChangeEventCallback]:
    """
    Return a factory that returns a new mock change event callback each call.

    :param mock_callback_called_timeout: the time to wait for a mock
        callback to be called when a call is expected
    :param mock_callback_not_called_timeout: the time to wait for a mock
        callback to be called when a call is unexpected

    :return: a factory that returns a new mock change event callback
        each time it is called with the name of a device attribute.
    """
    return functools.partial(
        MockChangeEventCallback,
        called_timeout=mock_callback_called_timeout,
        not_called_timeout=mock_callback_not_called_timeout,
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
    return "low-mccs/subrack/0001"


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
def static_tile_simulator(logger: logging.Logger) -> StaticTpmSimulator:
    """
    Return a static TPM simulator.

    (This is a pytest fixture.)

    :param logger: a object that implements the standard logging
        interface of :py:class:`logging.Logger`

    :return: a static TPM simulator
    """
    return StaticTileSimulator(logger)


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
    communication_state_changed_callback: Callable[[CommunicationStatus], None],
    component_state_changed_callback: Callable[[dict[str, Any]], None],
) -> StaticTpmSimulatorComponentManager:
    """
    Return an static TPM simulator component manager.

    (This is a pytest fixture.)

    :param logger: the logger to be used by this object.
    :param max_workers: nos of worker threads
    :param communication_state_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_state_changed_callback: callback to be
        called when the state changes

    :return: a static TPM simulator component manager.
    """
    return StaticTpmSimulatorComponentManager(
        logger,
        max_workers,
        communication_state_changed_callback,
        component_state_changed_callback,
    )


@pytest.fixture()
def dynamic_tpm_simulator_component_manager(
    logger: logging.Logger,
    max_workers: int,
    communication_state_changed_callback: Callable[[CommunicationStatus], None],
    component_state_changed_callback: Callable[[dict[str, Any]], None],
) -> DynamicTpmSimulatorComponentManager:
    """
    Return an dynamic TPM simulator component manager.

    (This is a pytest fixture.)

    :param logger: the logger to be used by this object.
    :param max_workers: nos of worker threads
    :param communication_state_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_state_changed_callback: callback to be
        called when the state changes

    :return: a static TPM simulator component manager.
    """
    return DynamicTpmSimulatorComponentManager(
        logger,
        max_workers,
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
