# pylint: disable=too-many-lines
#
# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests of the tile component manage."""
from __future__ import annotations

import time
import unittest.mock
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pytest
import pytest_mock
from ska_control_model import CommunicationStatus, PowerState, TaskStatus, TestMode
from ska_tango_testing.mock import MockCallableGroup
from ska_tango_testing.mock.placeholders import Anything

from ska_low_mccs_spshw.tile import (
    DynamicTileSimulator,
    MockTpm,
    TileComponentManager,
    TileSimulator,
    TpmDriver,
    TpmStatus,
)


class TestTileComponentManager:
    """
    Class for testing the tile component manager.

    Many of its methods and properties map to the underlying TPM
    simulator or driver, and these are tested in the class below. Here,
    we just perform tests of functionality in the tile component manager
    itself.
    """

    @pytest.mark.parametrize("power_state", list(PowerState))
    def test_communication(
        self: TestTileComponentManager,
        tile_component_manager: TileComponentManager,
        callbacks: MockCallableGroup,
        power_state: PowerState,
    ) -> None:
        """
        Test communication between the tile component manager and its tile.

        :param tile_component_manager: the tile component manager
            under test
        :param callbacks: dictionary of driver callbacks.
        :param power_state: the power mode of the TPM when we break off
            comms
        """
        assert (
            tile_component_manager.communication_state == CommunicationStatus.DISABLED
        )

        # takes the component out of DISABLED. Connects with subrack (NOT with TPM)
        tile_component_manager.start_communicating()
        callbacks["communication_status"].assert_call(
            CommunicationStatus.NOT_ESTABLISHED
        )

        if power_state == PowerState.UNKNOWN:
            tile_component_manager._tpm_power_state_changed(PowerState.UNKNOWN)
        elif power_state == PowerState.NO_SUPPLY:
            tile_component_manager._tpm_power_state_changed(PowerState.NO_SUPPLY)
        elif power_state == PowerState.OFF:
            pass  # test harness starts with TPM off
        elif power_state == PowerState.ON:
            tile_component_manager._tpm_power_state_changed(PowerState.ON)
            callbacks["communication_status"].assert_call(
                CommunicationStatus.ESTABLISHED
            )

        tile_component_manager.stop_communicating()

        callbacks["communication_status"].assert_call(CommunicationStatus.DISABLED)
        assert (
            tile_component_manager.communication_state == CommunicationStatus.DISABLED
        )

    def test_state_with_adminode(
        self: TestTileComponentManager,
        tile_component_manager: TileComponentManager,
        callbacks: MockCallableGroup,
    ) -> None:
        """
        Test `TileComponentManager` gets updated as expected.

        The `TileComponentManager` should report the power and communication state
        of the device under control:
        - when `start_communicating` is called the `TileComponentManager` should
        transition to the state of the device under test.
        - when `stop_communicating` is called the `TileComponentManager` should
        transition to UNKNOWN since connection to the subrack is lost.

        :param tile_component_manager: the tile component manager
            under test
        :param callbacks: dictionary of driver callbacks.
        """
        assert (
            tile_component_manager.communication_state == CommunicationStatus.DISABLED
        )
        tile_component_manager.start_communicating()
        callbacks["communication_status"].assert_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        callbacks["component_state"].assert_call(power=PowerState.OFF)
        callbacks["communication_status"].assert_not_called()

        # Stop communicating will break the connection with the subrack
        # therefore component state becomes UNKNOWN
        tile_component_manager.stop_communicating()
        callbacks["communication_status"].assert_call(CommunicationStatus.DISABLED)
        callbacks["component_state"].assert_call(power=PowerState.UNKNOWN)
        callbacks["component_state"].assert_not_called()

    # TODO: find out if TPM has standby mode, and if so add this case
    @pytest.mark.parametrize(
        "second_power_state",
        [
            PowerState.UNKNOWN,
            PowerState.NO_SUPPLY,
            PowerState.OFF,
            PowerState.ON,
        ],
    )
    @pytest.mark.parametrize(
        "first_power_state",
        [
            PowerState.UNKNOWN,
            PowerState.NO_SUPPLY,
            PowerState.OFF,
            PowerState.ON,
        ],
    )
    def test_power_state_changes(
        self: TestTileComponentManager,
        tile_component_manager: TileComponentManager,
        callbacks: MockCallableGroup,
        first_power_state: PowerState,
        second_power_state: PowerState,
    ) -> None:
        """
        Test handling of notifications of TPM power mode changes from the subrack.

        :param tile_component_manager: the tile component manager
            under test
        :param callbacks: dictionary of driver callbacks.
        :param first_power_state: the power mode of the initial event
        :param second_power_state: the power mode of the subsequent event
        """
        assert (
            tile_component_manager.communication_state == CommunicationStatus.DISABLED
        )

        tile_component_manager.start_communicating()

        callbacks["communication_status"].assert_call(
            CommunicationStatus.NOT_ESTABLISHED
        )

        assert (
            tile_component_manager.communication_state
            == CommunicationStatus.NOT_ESTABLISHED
        )

        tile_component_manager._tpm_power_state_changed(first_power_state)

        if first_power_state == PowerState.ON:
            callbacks["communication_status"].assert_call(
                CommunicationStatus.ESTABLISHED
            )
        else:
            callbacks["communication_status"].assert_not_called()

        tile_component_manager._tpm_power_state_changed(second_power_state)

        if first_power_state != PowerState.ON and second_power_state == PowerState.ON:
            callbacks["communication_status"].assert_call(
                CommunicationStatus.ESTABLISHED
            )
        else:
            callbacks["communication_status"].assert_not_called()

    def test_off_on(
        self: TestTileComponentManager,
        tile_component_manager: TileComponentManager,
        callbacks: MockCallableGroup,
        subrack_tpm_id: int,
        mock_subrack_device_proxy: unittest.mock.Mock,
    ) -> None:
        """
        Test that we can turn the TPM on and off when the subrack is on.

        :param tile_component_manager: the tile component manager
            under test
        :param callbacks: dictionary of driver callbacks.
        :param subrack_tpm_id: This tile's position in its subrack
        :param mock_subrack_device_proxy: a mock device proxy to a
            subrack device.
        """
        tile_component_manager.start_communicating()

        callbacks["communication_status"].assert_call(
            CommunicationStatus.NOT_ESTABLISHED
        )

        tile_component_manager._tpm_power_state_changed(PowerState.OFF)

        tile_component_manager.on()
        # TODO: This is still an old-school MockCallable because -common
        mock_subrack_device_proxy.PowerOnTpm.assert_next_call(subrack_tpm_id)
        tile_component_manager._tpm_power_state_changed(PowerState.ON)

        # TODO: this may be a bug, why do we need a sleep?
        time.sleep(0.3)

        tile_component_manager.off()
        # TODO: This is still an old-school MockCallable because -common
        mock_subrack_device_proxy.PowerOffTpm.assert_next_call(subrack_tpm_id)
        tile_component_manager._tpm_power_state_changed(PowerState.OFF)

    def test_eventual_consistency_of_on_command(
        self: TestTileComponentManager,
        tile_component_manager: TileComponentManager,
        subrack_tpm_id: int,
        mock_subrack_device_proxy: unittest.mock.Mock,
        callbacks: MockCallableGroup,
    ) -> None:  # noqa: DAR401
        """
        Test that eventual consistency semantics of the on command.

        This test tells the tile component manager to turn on, in
        circumstances in which it cannot possibly do so (the subrack is
        turned off). Instead of failing, it waits for the subrack to
        turn on, and then executes the on command.

        :param tile_component_manager: the tile component manager
            under test
        :param callbacks: dictionary of driver callbacks.
        :param subrack_tpm_id: This tile's position in its subrack
        :param mock_subrack_device_proxy: a mock device proxy to a
            subrack device.
        :param callbacks: dictionary of mock callbacks
        """
        tile_component_manager.on(task_callback=callbacks["task"])
        callbacks["task"].assert_call(status=TaskStatus.QUEUED)
        callbacks["task"].assert_call(status=TaskStatus.IN_PROGRESS)

        # TODO: WHY are we receiving FAILED twice?!!
        for _ in range(2):
            call_details = callbacks["task"].assert_call(
                status=TaskStatus.FAILED,
                exception=Anything,
            )
            with pytest.raises(
                ConnectionError, match="TPM cannot be turned off / on when not online."
            ):
                raise call_details["exception"]

        callbacks["task"].assert_not_called()

        tile_component_manager.start_communicating()

        callbacks["communication_status"].assert_call(
            CommunicationStatus.NOT_ESTABLISHED
        )

        callbacks["communication_status"].assert_not_called()

        # mock an event from subrack announcing it to be turned off
        tile_component_manager._tpm_power_state_changed(PowerState.NO_SUPPLY)

        mock_subrack_device_proxy.PowerOnTpm.assert_not_called()

        result_code, message = tile_component_manager.on()
        assert result_code == TaskStatus.QUEUED
        assert message == "Task queued"
        time.sleep(0.2)

        # no action taken initially because the subrack is switched off
        mock_subrack_device_proxy.PowerOnTpm.assert_not_called()

        # mock an event from subrack announcing it to be turned on
        tile_component_manager._tpm_power_state_changed(PowerState.OFF)

        # now that the tile has been notified that the subrack is on,
        # it tells it to turn on its TPM
        # TODO: This is still an old-school MockCallable because -common
        mock_subrack_device_proxy.PowerOnTpm.assert_next_call(subrack_tpm_id)


class TestStaticSimulatorCommon:
    """
    Class for testing commands common to several component manager layers.

    Because the TileComponentManager is designed to pass commands
    through to the Tpmdriver to the TPM simulator, many
    commands are common to multiple classes. Here we test the flow of
    commands to the simulator. Tests in this class are tested against:

    * the TileSimulator
    * the TpmDriver
    * the TileComponentManager.
    """

    @pytest.fixture()
    def initial_tpm_power_state(
        self: TestStaticSimulatorCommon,
    ) -> PowerState:
        """
        Return the initial power mode of the TPM.

        Overridden here to put the TPM into ON state, so that we don't
        have to fiddle around with state change events to get the tile
        component manager communicating with its tile.

        :return: the initial power mode of the TPM.
        """
        return PowerState.ON

    @pytest.fixture()
    def tile(
        self: TestStaticSimulatorCommon,
        static_tile_component_manager: TileComponentManager,
        callbacks: MockCallableGroup,
    ) -> TileComponentManager:
        """
        Return the tile component under test (Driving a TileSimulator).

        :param static_tile_component_manager: the tile component manager (
            driving a TileSimulator)
        :param callbacks: dictionary of driver callbacks.

        :return: the tile class object under test
        """
        # pylint: disable=attribute-defined-outside-init
        self.tile_name = "tile_component_manager"

        static_tile_component_manager.start_communicating()
        callbacks["communication_status"].assert_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)
        callbacks["component_state"].assert_call(power=PowerState.ON)
        callbacks["component_state"].assert_call(fault=False, lookahead=3)
        callbacks["component_state"].assert_call(
            programming_state=TpmStatus.UNPROGRAMMED
        )
        callbacks["component_state"].assert_call(programming_state=TpmStatus.PROGRAMMED)
        callbacks["component_state"].assert_call(
            programming_state=TpmStatus.INITIALISED, lookahead=2
        )
        return static_tile_component_manager

    @pytest.mark.parametrize(
        ("attribute_name", "expected_value"),
        (
            (
                "voltage_mon",
                TileSimulator.TILE_MONITORING_POINTS["voltages"]["MON_5V0"],
            ),
            (
                "board_temperature",
                TileSimulator.TILE_MONITORING_POINTS["temperatures"]["board"],
            ),
            (
                "fpga1_temperature",
                TileSimulator.TILE_MONITORING_POINTS["temperatures"]["FPGA0"],
            ),
            (
                "fpga2_temperature",
                TileSimulator.TILE_MONITORING_POINTS["temperatures"]["FPGA1"],
            ),
            ("adc_rms", TileSimulator.ADC_RMS),
            ("fpgas_time", TileSimulator.FPGAS_TIME),
            (
                "current_tile_beamformer_frame",
                TileSimulator.CURRENT_TILE_BEAMFORMER_FRAME,
            ),
            ("fpga_current_frame", 0),
            ("pps_delay", TileSimulator.PPS_DELAY),
            ("firmware_available", TileSimulator.FIRMWARE_LIST),
            ("register_list", list(MockTpm._register_map.keys())),
            (
                "pps_present",
                TileSimulator.TILE_MONITORING_POINTS["timing"]["pps"]["status"],
            ),
            ("clock_present", True),
            ("sysref_present", True),
            ("pll_locked", False),
            ("pending_data_requests", False),
        ),
    )
    def test_read_attribute(
        self: TestStaticSimulatorCommon,
        tile: TileComponentManager,
        tpm_driver: TpmDriver,
        attribute_name: str,
        expected_value: Any,
    ) -> None:
        """
        Tests that read-only attributes take certain known initial values.

        This is a weak test; over time we should find ways to more thoroughly
        test each of these independently.

        :param tile: the tile class object under test.
        :param tpm_driver: the tpm_driver fixture.
        :param attribute_name: the name of the attribute under test
        :param expected_value: the expected value of the attribute. This
            can be any type, but the test of the attribute is a single
            "==" equality test.
        """
        tpm_driver._update_attributes()
        assert getattr(tile, attribute_name) == expected_value

    @pytest.mark.parametrize(
        ("attribute_name", "expected_value", "expected_component_value"),
        (
            ("fpga_reference_time", 0, "1970-01-01T00:00:00.000000Z"),
            ("fpga_frame_time", None, "1970-01-01T00:00:00.000000Z"),
        ),
    )
    def test_read_time_attribute(
        self: TestStaticSimulatorCommon,
        tile: TileComponentManager,
        attribute_name: str,
        expected_value: Any,
        expected_component_value: Any,
    ) -> None:
        """
        Tests that read-only time attributes take known initial values.

        This is a weak test; over time we should find ways to more thoroughly
        test each of these independently.

        :param tile: the tile class object under test.
        :param attribute_name: the name of the attribute under test
        :param expected_value: the expected value of the attribute. This
            can be any type, but the test of the attribute is a single
            "==" equality test.
        :param expected_component_value: the expected value in the component
            manager, which is in different format wrt. the value in the
            underlying driver/simulator
        """
        if not isinstance(tile, TileComponentManager):
            if expected_value is not None:
                assert getattr(tile, attribute_name) == expected_value
        else:
            assert getattr(tile, attribute_name) == expected_component_value

    @pytest.mark.parametrize(
        ("attribute_name", "initial_value", "values_to_write"),
        (
            (
                "phase_terminal_count",
                TileSimulator.PHASE_TERMINAL_COUNT,
                [1, 2],
            ),
            (
                "static_delays",
                TileSimulator.STATIC_DELAYS,
                [[1.0, 2.0, 3.0, 4.0] * 8],
            ),
            (
                "csp_rounding",
                np.array(TpmDriver.CSP_ROUNDING),
                np.array([[1, 2, 3, 4] * 96]),
            ),
            (
                "preadu_levels",
                TileSimulator.PREADU_LEVELS,
                [[-10.0, -5, 5, 10] * 8],
            ),
            (
                "channeliser_truncation",
                TileSimulator.CHANNELISER_TRUNCATION,
                [[2] * 512],
            ),
            ("tile_id", TileSimulator.TILE_ID, [123]),
            ("station_id", TileSimulator.STATION_ID, [321]),
            ("test_generator_active", False, [True]),
        ),
    )
    def test_write_attribute(  # pylint: disable=too-many-arguments
        self: TestStaticSimulatorCommon,
        tile: TileComponentManager,
        tpm_driver: TpmDriver,
        attribute_name: str,
        initial_value: Any,
        values_to_write: list,
    ) -> None:
        """
        Test read-write attributes.

        Take certain known initial values, and that
        their values can be updated.

        This is a weak test; over time we should find ways to more
        thoroughly test each of these independently.

        :param tile: the tile class object under test.
        :param attribute_name: the name of the attribute under test
        :param initial_value: the expected initial value of the
            attribute. This can be any type, but the test of the
            attribute is a simple "==" equality test.
        :param values_to_write: a sequence of values to write, in order
            to check that the writes are sticking. The values can be of
            any type, but the test of the attribute is a simple "=="
            equality test.
        :param tpm_driver: the tpm_driver fixture.
        """
        tpm_driver._update_attributes()
        if isinstance(initial_value, np.ndarray):
            assert (getattr(tile, attribute_name) == initial_value).all()
        else:
            assert getattr(tile, attribute_name) == initial_value

        for value in values_to_write:
            setattr(tile, attribute_name, value)
            tpm_driver._update_attributes()
            if isinstance(value, np.ndarray):
                assert (getattr(tile, attribute_name) == value).all()
            else:
                assert getattr(tile, attribute_name) == value

    @pytest.mark.parametrize(
        ("command_name", "args"),
        (
            ("load_pointing_delays", [[2] * 32, 1]),
            ("configure_integrated_channel_data", []),
            ("configure_integrated_beam_data", []),
            ("start_acquisition", []),
            ("stop_integrated_data", []),
            ("set_lmc_integrated_download", ["raw", 8190, 8190]),
            ("post_synchronisation", []),
        ),
    )
    def test_command(  # pylint: disable=too-many-arguments
        self: TestStaticSimulatorCommon,
        tile: TileComponentManager,
        tpm_driver: TpmDriver,
        mocker: pytest_mock.MockerFixture,
        command_name: str,
        args: int,
    ) -> None:
        """
        Test of commands that aren't implemented yet.

        Since the commands don't really do
        anything, these tests simply check that the command can be called.

        :param mocker: fixture that wraps unittest.mock
        :param tile: the tile class object under test.
        :param tpm_driver: the tpm_driver fixture.
        :param command_name: the name of the command under test
        :param args: the args the command takes
        """
        lrc_list = [
            "start_acquisition",
            "post_synchronisation",
        ]
        if command_name in lrc_list and self.tile_name == "tile_component_manager":
            command_name = "_" + command_name

        getattr(tile, command_name)(*args)

    def test_set_lmc_download(
        self: TestStaticSimulatorCommon,
        tile: TileComponentManager,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """
        Test of set_lmc_download command.

        Since the commands don't really do
        anything, these tests simply check that the command can be called.

        :param mocker: fixture that wraps unittest.mock
        :param tile: the tile class object under test.
        """
        tile.set_lmc_download("10G", 1024, "10.0.10.1")

    @pytest.mark.parametrize(
        ("command_name", "implemented"),
        (
            ("apply_calibration", True),
            ("apply_pointing_delays", True),
            ("start_beamformer", True),
        ),
    )
    def test_timed_command(
        self: TestStaticSimulatorCommon,
        tile: TileComponentManager,
        command_name: str,
        implemented: bool,
    ) -> None:
        """
        Test of commands that require a UTC time.

        Since the commands don't really do
        anything, these tests simply check that the command can be called.

        :param tile: the tile class object under test.
        :param command_name: the name of the command under test
        :param implemented: the command is implemented, does not raise error
        """
        # Use ISO formatted time for component manager, numeric for drivers
        # Must also set FPGA sync time in driver
        #
        if self.tile_name == "tile_component_manager":
            args = "2022-11-10T12:34:56.0Z"
            dt = datetime.strptime("2022-11-10T00:00:00.0Z", "%Y-%m-%dT%H:%M:%S.%fZ")
            timestamp = int(dt.replace(tzinfo=timezone.utc).timestamp())
            # TODO: there is no fpga_sync_time method.
            # tile._tpm_driver.fpga_sync_time = timestamp
            # assert tile._tpm_driver.fpga_sync_time == timestamp
            tile._tile_time.set_reference_time(timestamp)  # type: ignore[union-attr]
        else:
            args = "123456"

        getattr(tile, command_name)()
        getattr(tile, command_name)(0)
        getattr(tile, command_name)(args)

    def test_initialise(
        self: TestStaticSimulatorCommon,
        tile: TileComponentManager,
    ) -> None:
        """
        Test of the initialise command, which programs the TPM.

        :param tile: the tile class object under test.
        """
        tile.erase_fpga()
        time.sleep(0.2)
        assert not tile.is_programmed
        time.sleep(0.2)
        tile.initialise()
        time.sleep(2)
        assert tile.is_programmed
        assert tile.firmware_name == "itpm_v1_6.bit"

    def test_download_firmware(
        self: TestStaticSimulatorCommon,
        tile: TileComponentManager,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """
        Test.

        Tests that:
        * the download_firmware command.
        * the is_programmed attribute

        :param tile: the tile class object under test.
        :param mocker: fixture that wraps unittest.mock
        """
        tile.erase_fpga()
        time.sleep(0.2)
        assert not tile.is_programmed
        mock_bitfile = mocker.Mock()
        time.sleep(0.2)
        tile.download_firmware(mock_bitfile)
        time.sleep(0.2)
        assert tile.is_programmed

    @pytest.mark.parametrize(
        "register", [f"fpga1.test_generator.delay_{i}" for i in (1, 4)]
    )
    @pytest.mark.parametrize("write_values", ([], [1], [2, 2]), ids=(0, 1, 2))
    def test_read_and_write_register(
        self: TestStaticSimulatorCommon,
        tile: TileComponentManager,
        register: str,
        write_values: list[int],
    ) -> None:
        """
        Test read and write registers.

        Test the:
        * read_register command
        * write_register command

        :param tile: the tile class object under test.
        :param register: which register is being addressed
        :param write_values: values to write to the register
        """
        expected_read = write_values
        tile.write_register(register, write_values)
        assert tile.read_register(register) == expected_read

    # pylint: disable=too-many-arguments
    @pytest.mark.parametrize(
        "write_address",
        [
            9,
        ],
    )
    @pytest.mark.parametrize("write_values", [[], [1], [2, 2]], ids=(0, 1, 2))
    @pytest.mark.parametrize("read_address", [10])
    @pytest.mark.parametrize("read_length", [0, 4])
    def test_read_and_write_address(
        self: TestStaticSimulatorCommon,
        tile: TileComponentManager,
        write_address: int,
        write_values: list[int],
        read_address: int,
        read_length: int,
    ) -> None:
        """
        Test read and write address registers.

        Test the:
        * read_address command
        * write_address command

        :param tile: the tile class object under test.
        :param write_address: address to write to
        :param write_values: values to write
        :param read_address: address to read from
        :param read_length: length to read
        """
        min_address = min(read_address, write_address)
        max_address = max(read_address + read_length, write_address + len(write_values))
        buffer = [0] * (max_address - min_address)

        def buffer_slice(address: int, length: int) -> slice:
            """
            Return a slice that tells you where to read from or write to the buffer.

            :param address: the start address being read from or written
                to
            :param length: the size of the write or read

            :return: a buffer slice defining where in the buffer the
                read or write should be applied
            """
            return slice(address - min_address, address - min_address + length)

        buffer[buffer_slice(write_address, len(write_values))] = write_values
        expected_read = list(buffer[buffer_slice(read_address - 1, read_length)])
        tile.write_address(write_address, write_values)
        assert tile.read_address(read_address, read_length) == expected_read

    def test_start_stop_beamformer(
        self: TestStaticSimulatorCommon,
        tile: TileComponentManager,
    ) -> None:
        """
        Test start and stop beamformer.

        Test that:
        * the start_beamformer command.
        * the stop_beamformer command.
        * the is_beamformer_running attribute

        :param tile: the tile class object under test.
        """
        assert not tile.is_beamformer_running
        tile.start_beamformer()
        assert tile.is_beamformer_running
        tile.stop_beamformer()
        assert not tile.is_beamformer_running

    def test_initialise_beamformer(
        self: TestStaticSimulatorCommon,
        tile: TileComponentManager,
    ) -> None:
        """
        Test initialise_beamformer.

        Test that:
        * the initialise_beamformer command executes
        * the beamformer table is correctly configured

        :param tile: the tile class object under test.
        """
        tile.initialise_beamformer(64, 32, False, False)
        tile._tpm_driver._update_attributes()
        table = tile.beamformer_table
        expected = [
            [64, 0, 0, 0, 0, 0, 0],
            [72, 0, 0, 8, 0, 0, 0],
            [80, 0, 0, 16, 0, 0, 0],
            [88, 0, 0, 24, 0, 0, 0],
        ]

        assert table == expected

    def test_set_beamformer_regions(
        self: TestStaticSimulatorCommon,
        tile: TileComponentManager,
    ) -> None:
        """
        Test set_beamformer_regions.

        Test that:
        * the set_beamformer_regions accepts 2 regions
        * the beamformer table is correctly configured

        :param tile: the tile class object under test.
        """
        regions = [[64, 16, 2, 3, 8, 7, 8, 9], [140, 16, 4, 5, 32, 10, 11, 12]]
        tile.set_beamformer_regions(regions)

        table = tile.beamformer_table
        expected = [
            [64, 2, 3, 8, 7, 8, 9],
            [72, 2, 3, 16, 7, 8, 9],
            [140, 4, 5, 32, 10, 11, 12],
            [148, 4, 5, 40, 10, 11, 12],
        ]

        assert table == expected

    def test_40g_configuration(
        self: TestStaticSimulatorCommon,
        tile: TileComponentManager,
    ) -> None:
        """
        Test 40G configuration.

        Test that:
        * the configure_40g_core command
        * the get_40g_configuration command

        :param tile: the tile class object under test.
        """
        assert tile.get_40g_configuration(-1, 0) == []
        assert tile.get_40g_configuration(9) == []

        tile.configure_40g_core(
            1,
            0,
            0x123456,
            "mock_src_ip",
            8888,
            "mock_dst_ip",
            3333,
        )

        expected = {
            "core_id": 1,
            "arp_table_entry": 0,
            "src_mac": 0x123456,
            "src_ip": "mock_src_ip",
            "src_port": 8888,
            "dst_ip": "mock_dst_ip",
            "dst_port": 3333,
            "rx_port_filter": None,
            "netmask": None,
            "gateway_ip": None,
        }

        assert tile.get_40g_configuration(-1, 0) == [expected]
        assert tile.get_40g_configuration(1) == [expected]
        assert tile.get_40g_configuration(10) == []


class TestDynamicSimulatorCommon:
    """
    Class for testing commands common to several component manager layers.

    Because the TileComponentManager is designed to pass commands
    through to the TPM simulator or driver that it is driving, many
    commands are common to multiple classes. Here we test the flow of
    commands to the dynamic TPM simulator. Tests in this class are
    tested against:

    * the TileComponentManager (Driving the DynamicTileSimulator)
    """

    @pytest.fixture()
    def test_mode(self: TestDynamicSimulatorCommon) -> TestMode:
        """
        Return the test mode to be used when initialising the tile class object.

        :return: the test mode to be used when initialising the tile
            class object.
        """
        return TestMode.NONE

    @pytest.fixture()
    def initial_tpm_power_state(
        self: TestDynamicSimulatorCommon,
    ) -> PowerState:
        """
        Return the initial power mode of the TPM.

        Overridden here to put the TPM into ON state, so that we don't
        have to fiddle around with state change events to get the tile
        component manager communicating with its tile.

        :return: the initial power mode of the TPM.
        """
        return PowerState.ON

    @pytest.fixture()
    def tile(
        self: TestDynamicSimulatorCommon,
        dynamic_tile_component_manager: TileComponentManager,
        callbacks: MockCallableGroup,
    ) -> TileComponentManager:
        """
        Return the tile component under test. (Driving a DynamicTileSimulator).

        :param dynamic_tile_component_manager: the tile component manager (
            Driving a DynamicTileSimulator)
        :param callbacks: dictionary of driver callbacks.

        :return: the tile class object under test
        """
        dynamic_tile_component_manager.start_communicating()

        callbacks["communication_status"].assert_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)
        callbacks["component_state"].assert_call(power=PowerState.ON)
        callbacks["component_state"].assert_call(fault=False, lookahead=2)
        callbacks["component_state"].assert_call(
            programming_state=TpmStatus.UNPROGRAMMED,
            lookahead=2,
            consume_nonmatches=True,
        )
        callbacks["component_state"].assert_call(
            programming_state=TpmStatus.PROGRAMMED, lookahead=2, consume_nonmatches=True
        )
        callbacks["component_state"].assert_call(
            programming_state=TpmStatus.INITIALISED,
            lookahead=2,
            consume_nonmatches=True,
        )
        return dynamic_tile_component_manager

    @pytest.mark.parametrize(
        "attribute_name",
        (
            "voltage_mon",
            "board_temperature",
            "fpga1_temperature",
            "fpga2_temperature",
        ),
    )
    def test_dynamic_attribute(
        self: TestDynamicSimulatorCommon,
        tile: TileComponentManager,
        attribute_name: str,
    ) -> None:
        """
        Tests that dynamic attributes can be read.

        Check that they are NOT equal to the
        static value assigned in the static dynamic simulator.

        :param tile: the tile class object under test.
        :param attribute_name: the name of the attribute under test
        """
        attribute_value = getattr(tile, attribute_name)
        assert attribute_value is not None
        time.sleep(8.1)
        tile._tpm_driver._update_attributes()
        new_attribute_value = getattr(tile, attribute_name)
        assert new_attribute_value is not None
        assert new_attribute_value != attribute_value

    @pytest.mark.parametrize(
        ("attribute_name", "expected_value"),
        (
            ("adc_rms", DynamicTileSimulator.ADC_RMS),
            ("fpgas_time", DynamicTileSimulator.FPGAS_TIME),
            (
                "current_tile_beamformer_frame",
                DynamicTileSimulator.CURRENT_TILE_BEAMFORMER_FRAME,
            ),
            ("pps_delay", DynamicTileSimulator.PPS_DELAY),
            ("firmware_available", DynamicTileSimulator.FIRMWARE_LIST),
            (
                "register_list",
                list(MockTpm._register_map.keys()),
            ),
        ),
    )
    def test_read_static_attribute(
        self: TestDynamicSimulatorCommon,
        tile: TileComponentManager,
        attribute_name: str,
        expected_value: Any,
    ) -> None:
        """
        Tests that read-only attributes take certain known initial values.

        This test covers attributes that have not been made dynamic yet.

        :param tile: the tile class object under test.
        :param attribute_name: the name of the attribute under test
        :param expected_value: the expected value of the attribute. This
            can be any type, but the test of the attribute is a single
            "==" equality test.
        """
        tile._tpm_driver._update_attributes()
        time.sleep(0.1)
        assert getattr(tile, attribute_name) == expected_value
