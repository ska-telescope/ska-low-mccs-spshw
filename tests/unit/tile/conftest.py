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
import time
import unittest.mock
from typing import Callable, Final, Iterator

import pytest
import tango
from ska_control_model import (
    AdminMode,
    PowerState,
    ResultCode,
    SimulationMode,
    TestMode,
)
from ska_low_mccs_common.testing.mock import MockDeviceBuilder
from ska_tango_testing.mock import MockCallable, MockCallableGroup
from tango.server import command

from ska_low_mccs_spshw import MccsTile
from ska_low_mccs_spshw.tile import (
    DynamicTileSimulator,
    TileComponentManager,
    TileSimulator,
)
from tests.harness import (
    SpsTangoTestHarness,
    SpsTangoTestHarnessContext,
    get_subrack_name,
)


@pytest.fixture(name="tile_state_map")
def tile_state_map() -> dict[tuple[PowerState, bool], tango.DevState]:
    """
    Return a map to expected state.

    :returns: a dictionary containing a tuple with first entry being
        Tpm Power as reported by the subrack, the second entry being
        whether the TPM is connectable as the key. The result is the
        expected state of the device.
    """
    # (subrack_says_tpm_power, is_tpm_reachable) -> resulting DevState
    return {
        (PowerState.UNKNOWN, False): tango.DevState.UNKNOWN,
        (PowerState.OFF, False): tango.DevState.OFF,
        (PowerState.ON, False): tango.DevState.FAULT,
        (PowerState.UNKNOWN, True): tango.DevState.FAULT,
        (PowerState.OFF, True): tango.DevState.FAULT,
        (PowerState.ON, True): tango.DevState.ON,
    }


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


@pytest.fixture(name="mock_station_device_proxy")
def mock_station_device_proxy_fixture() -> unittest.mock.Mock:
    """
    Fixture that provides a mock station device proxy.

    This is needed for subscription to adminMode for adminMode
    inheritance feature.

    :return: a mock station device.
    """
    builder = MockDeviceBuilder()
    builder.add_attribute("adminmode", AdminMode.ONLINE)
    return builder()


@pytest.fixture(name="test_context")
def test_context_fixture(
    subrack_id: int,
    mock_subrack_device_proxy: unittest.mock.Mock,
    mock_station_device_proxy: unittest.mock.Mock,
) -> Iterator[None]:
    """
    Yield into a context in which Tango is running, with a mock subrack device.

    :param subrack_id: ID of the subrack Tango device to be mocked
    :param mock_subrack_device_proxy: a mock subrack device proxy that
        has been configured with the required subrack behaviours.
    :param mock_station_device_proxy: A mock procy to the spsstation device.

    :yields: into a context in which Tango is running, with a mock
        subrack device.
    """
    harness = SpsTangoTestHarness()
    harness.add_mock_subrack_device(subrack_id, mock_subrack_device_proxy)
    # SpsStation added for adminMode inheritance, without this
    # our test logs are filled with noise.
    harness.add_mock_station_device(mock_station_device_proxy)
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
        "attribute_state",
        "task",
        "task_lrc",
        timeout=15.0,
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


PREADU_ATTENUATION: Final = [20.0] * 32
STATIC_TIME_DELAYS: Final = [2.5] * 32


@pytest.fixture(name="preadu_attenuation")
def preadu_attenuation_fixture() -> list[float]:
    """
    Return the preADU attenuation to set on the tile under test.

    :return: the preADU attenuation to set on the tile under test.
    """
    return PREADU_ATTENUATION


@pytest.fixture(name="static_time_delays")
def static_time_delays_fixture() -> list[float]:
    """
    Return the preADU attenuation to set on the tile under test.

    :return: the preADU attenuation to set on the tile under test.
    """
    return STATIC_TIME_DELAYS


@pytest.fixture(name="tile_simulator")
def tile_simulator_fixture(logger: logging.Logger) -> TileSimulator:
    """
    Return a TileSimulator.

    :param logger: logger
    :return: a TileSimulator
    """
    return TileSimulator(logger)


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
    preadu_attenuation: list[float],
    static_time_delays: list[float],
    subrack_id: int,
    subrack_tpm_id: int,
    callbacks: MockCallableGroup,
    tile_simulator: TileSimulator,
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
    :param preadu_attenuation: the preADU attenuation to set on the tile.
    :param static_time_delays: the static delays offset to apply to the tile.
    :param subrack_id: ID of the subrack that controls power to this tile
    :param subrack_tpm_id: This tile's position in its subrack
    :param poll_rate: the polling rate
    :param callbacks: dictionary of driver callbacks.
    :param tile_simulator: The tile_simulator fixture

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
        preadu_attenuation,
        static_time_delays,
        get_subrack_name(subrack_id),
        subrack_tpm_id,
        [True] * 2,
        callbacks["communication_status"],
        callbacks["component_state"],
        callbacks["attribute_state"],
        tile_simulator,
    )


@pytest.fixture(name="dynamic_tile_simulator")
def dynamic_tile_simulator_fixture(logger: logging.Logger) -> DynamicTileSimulator:
    """
    Return a DynamicTileSimulator.

    :param logger: logger
    :return: a TileSimulator
    """
    return DynamicTileSimulator(logger)


@pytest.fixture(name="voltage_warning_thresholds")
def voltage_warning_thresholds_fixture() -> dict[str, dict[str, float]]:
    """
    Return the standard voltage warning thresholds.

    :return: the standard voltage warning thresholds.
    """
    return {
        "MGT_AVCC": {"min": 0.0, "max": 65.535},
        "MGT_AVTT": {"min": 0.0, "max": 65.535},
        "SW_AVDD1": {"min": 0.0, "max": 65.535},
        "SW_AVDD2": {"min": 0.0, "max": 65.535},
        "AVDD3": {"min": 0.0, "max": 65.535},
        "MAN_1V2": {"min": 0.0, "max": 65.535},
        "DDR0_VREF": {"min": 0.0, "max": 65.535},
        "DDR1_VREF": {"min": 0.0, "max": 65.535},
        "VM_DRVDD": {"min": 0.0, "max": 65.535},
        "VIN": {"min": 11.4, "max": 12.6},
        "MON_3V3": {"min": 0.0, "max": 65.535},
        "MON_1V8": {"min": 0.0, "max": 65.535},
        "MON_5V0": {"min": 0.0, "max": 65.535},
    }


@pytest.fixture(name="updated_voltage_warning_thresholds")
def updated_voltage_warning_thresholds_fixture() -> dict[str, dict[str, float]]:
    """
    Return non-standard voltage warning thresholds.

    :return: the non-standard voltage warning thresholds.
    """
    return {
        "MGT_AVCC": {"min": 1.0, "max": 2.0},
        "MGT_AVTT": {"min": 3.0, "max": 4.0},
        "SW_AVDD1": {"min": 5.0, "max": 6.535},
        "SW_AVDD2": {"min": 7.0, "max": 8.535},
        "AVDD3": {"min": 9.0, "max": 10.535},
        "MAN_1V2": {"min": 11.0, "max": 12.535},
        "DDR0_VREF": {"min": 13.0, "max": 14.535},
        "DDR1_VREF": {"min": 15.0, "max": 16.535},
        "VM_DRVDD": {"min": 17.0, "max": 18.535},
        "VIN": {"min": 19.4, "max": 20.6},
        "MON_3V3": {"min": 21.0, "max": 22.535},
        "MON_1V8": {"min": 23.0, "max": 24.535},
        "MON_5V0": {"min": 25.0, "max": 26.535},
    }


@pytest.fixture(name="current_warning_thresholds")
def current_warning_thresholds_fixture() -> dict[str, dict[str, float]]:
    """
    Return the standard current warning thresholds.

    :return: the standard current warning thresholds.
    """
    return {
        "FE0_mVA": {"min": 0.0, "max": 65.535},
        "FE1_mVA": {"min": 0.0, "max": 65.535},
    }


@pytest.fixture(name="updated_current_warning_thresholds")
def updated_current_warning_thresholds_fixture() -> dict[str, dict[str, float]]:
    """
    Return the standard current warning thresholds.

    :return: the standard current warning thresholds.
    """
    return {
        "FE0_mVA": {"min": 1.0, "max": 5.535},
        "FE1_mVA": {"min": 2.0, "max": 6.535},
    }


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
    preadu_attenuation: list[float],
    static_time_delays: list[float],
    subrack_id: int,
    subrack_tpm_id: int,
    callbacks: MockCallableGroup,
    dynamic_tile_simulator: DynamicTileSimulator,
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
    :param preadu_attenuation: the preADU attenuation to set on the tile.
    :param static_time_delays: the static delays offset to apply to the tile.
    :param subrack_id: ID of the subrack that controls power to this tile
    :param subrack_tpm_id: This tile's position in its subrack
    :param poll_rate: the polling rate
    :param callbacks: dictionary of driver callbacks.
    :param dynamic_tile_simulator: the dynamic_tile_simulator_fixture.

    :return: a TPM component manager in the specified simulation mode.
    """
    return TileComponentManager(
        SimulationMode.TRUE,
        TestMode.NONE,
        logger,
        poll_rate,
        tile_id,
        station_id,
        tpm_ip,
        tpm_cpld_port,
        preadu_attenuation,
        static_time_delays,
        get_subrack_name(subrack_id),
        subrack_tpm_id,
        [True] * 2,
        callbacks["communication_status"],
        callbacks["component_state"],
        callbacks["attribute_state"],
        dynamic_tile_simulator,
    )


@pytest.fixture(name="patched_tile_device_class")
def patched_tile_device_class_fixture(
    tile_component_manager: TileComponentManager,
    tile_id: int,
) -> type[MccsTile]:
    """
    Return a tile device class patched with extra methods for testing.

    :param tile_component_manager: A mock component manager.
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
            tile_component_manager.set_communication_state_callback(
                self._communication_state_changed,
            )
            tile_component_manager.set_component_state_callback(
                self._component_state_changed,
            )
            tile_component_manager._update_attribute_callback = (
                self._update_attribute_callback
            )
            wrapped_set_up_antenna_buffer = MockCallable(
                wraps=tile_component_manager.set_up_antenna_buffer
            )
            tile_component_manager.set_up_antenna_buffer = (  # type: ignore[assignment]
                wrapped_set_up_antenna_buffer
            )
            wrapped_start_antenna_buffer = MockCallable(
                wraps=tile_component_manager._start_antenna_buffer
            )
            tile_component_manager._start_antenna_buffer = (  # type: ignore[assignment]
                wrapped_start_antenna_buffer
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
            self.component_manager.tile.mock_off()

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
        def UpdateAttributes(self: PatchedTileDevice) -> None:
            """
            Call update_attributes on the TpmDriver.

            Note: attributes are updated dependent on the time passed since
            the last read. Here the last update time is set to
            zero meaning they can be updated (assuming device state permits).
            """
            time.sleep(10)

        @command()
        def MockTpmOn(self: PatchedTileDevice) -> None:
            """Mock power on the tpm."""
            self.component_manager._subrack_says_tpm_power_changed(
                f"tpm{tile_id}PowerState",
                PowerState.ON,
                tango.EventType.CHANGE_EVENT,
            )
            self.component_manager.tile.mock_on()

    return PatchedTileDevice
