# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests of the tile component manage."""
from __future__ import annotations

import logging
import time
import unittest.mock
from typing import Any, Callable, Union

import pytest
import pytest_mock
from _pytest.fixtures import SubRequest
from ska_control_model import (
    CommunicationStatus,
    PowerState,
    SimulationMode,
    TaskStatus,
    TestMode,
)
from ska_low_mccs_common.testing.mock import MockCallable

from ska_low_mccs.tile import (
    DynamicTpmSimulator,
    DynamicTpmSimulatorComponentManager,
    StaticTpmSimulator,
    StaticTpmSimulatorComponentManager,
    SwitchingTpmComponentManager,
    TileComponentManager,
    TpmDriver,
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
        communication_state_changed_callback: MockCallable,
        power_state: PowerState,
    ) -> None:
        """
        Test communication between the tile component manager and its tile.

        :param tile_component_manager: the tile component manager
            under test
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param power_state: the power mode of the TPM when we break off
            comms
        """
        assert (
            tile_component_manager.communication_state == CommunicationStatus.DISABLED
        )

        # takes the component out of DISABLED. Connects with subrack (NOT with TPM)
        tile_component_manager.start_communicating()
        time.sleep(0.2)
        communication_state_changed_callback.assert_next_call(
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
            communication_state_changed_callback.assert_next_call(
                CommunicationStatus.ESTABLISHED
            )

        tile_component_manager.stop_communicating()

        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.DISABLED
        )
        assert (
            tile_component_manager.communication_state == CommunicationStatus.DISABLED
        )

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
        communication_state_changed_callback: MockCallable,
        first_power_state: PowerState,
        second_power_state: PowerState,
    ) -> None:
        """
        Test handling of notifications of TPM power mode changes from the subrack.

        :param tile_component_manager: the tile component manager
            under test
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param first_power_state: the power mode of the initial event
        :param second_power_state: the power mode of the subsequent event
        """
        assert (
            tile_component_manager.communication_state == CommunicationStatus.DISABLED
        )

        tile_component_manager.start_communicating()

        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )

        assert (
            tile_component_manager.communication_state
            == CommunicationStatus.NOT_ESTABLISHED
        )

        tile_component_manager._tpm_power_state_changed(first_power_state)

        if first_power_state == PowerState.ON:
            communication_state_changed_callback.assert_next_call(
                CommunicationStatus.ESTABLISHED
            )
        else:
            communication_state_changed_callback.assert_not_called()

        tile_component_manager._tpm_power_state_changed(second_power_state)

        if first_power_state != PowerState.ON and second_power_state == PowerState.ON:
            communication_state_changed_callback.assert_next_call(
                CommunicationStatus.ESTABLISHED
            )
        else:
            communication_state_changed_callback.assert_not_called()

    def test_off_on(
        self: TestTileComponentManager,
        tile_component_manager: TileComponentManager,
        communication_state_changed_callback: MockCallable,
        subrack_tpm_id: int,
        mock_subrack_device_proxy: unittest.mock.Mock,
    ) -> None:
        """
        Test that we can turn the TPM on and off when the subrack is on.

        :param tile_component_manager: the tile component manager
            under test
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param subrack_tpm_id: This tile's position in its subrack
        :param mock_subrack_device_proxy: a mock device proxy to a
            subrack device.
        """
        tile_component_manager.start_communicating()

        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )

        tile_component_manager._tpm_power_state_changed(PowerState.OFF)

        tile_component_manager.on()
        mock_subrack_device_proxy.PowerOnTpm.assert_next_call(subrack_tpm_id)
        tile_component_manager._tpm_power_state_changed(PowerState.ON)

        tile_component_manager.off()
        mock_subrack_device_proxy.PowerOffTpm.assert_next_call(subrack_tpm_id)
        tile_component_manager._tpm_power_state_changed(PowerState.OFF)

    def test_eventual_consistency_of_on_command(
        self: TestTileComponentManager,
        tile_component_manager: TileComponentManager,
        communication_state_changed_callback: MockCallable,
        subrack_tpm_id: int,
        mock_subrack_device_proxy: unittest.mock.Mock,
        mock_task_callback: MockCallable,
    ) -> None:  # noqa: DAR401
        """
        Test that eventual consistency semantics of the on command.

        This test tells the tile component manager to turn on, in
        circumstances in which it cannot possibly do so (the subrack is
        turned off). Instead of failing, it waits for the subrack to
        turn on, and then executes the on command.

        :param tile_component_manager: the tile component manager
            under test
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param subrack_tpm_id: This tile's position in its subrack
        :param mock_subrack_device_proxy: a mock device proxy to a
            subrack device.
        :param mock_task_callback: callback for tasks
        """
        tile_component_manager.on(task_callback=mock_task_callback)
        mock_task_callback.assert_next_call(status=TaskStatus.QUEUED)

        # For some reason we cannot compare the equality of the Exception
        # objects directly.
        # mock_task_callback.assert_next_call(
        #    status=TaskStatus.FAILED,
        #    exception=ConnectionError("TPM cannot be turned off / on "
        #    "when not online."))
        time.sleep(0.1)
        _, kwargs = mock_task_callback.get_next_call()
        assert kwargs["status"] == TaskStatus.IN_PROGRESS

        _, kwargs = mock_task_callback.get_next_call()
        assert kwargs["status"] == TaskStatus.FAILED

        with pytest.raises(
            ConnectionError, match="TPM cannot be turned off / on when not online."
        ):
            raise kwargs["exception"]

        tile_component_manager.start_communicating()

        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )

        communication_state_changed_callback.assert_not_called()

        # mock an event from subrack announcing it to be turned off
        tile_component_manager._tpm_power_state_changed(PowerState.NO_SUPPLY)

        mock_subrack_device_proxy.PowerOnTpm.assert_not_called()

        result_code, message = tile_component_manager.on()
        assert result_code == TaskStatus.QUEUED
        assert message == "Task queued"

        # no action taken initially because the subrack is switched off
        mock_subrack_device_proxy.PowerOnTpm.assert_not_called()

        # mock an event from subrack announcing it to be turned on
        tile_component_manager._tpm_power_state_changed(PowerState.OFF)

        # now that the tile has been notified that the subrack is on,
        # it tells it to turn on its TPM
        mock_subrack_device_proxy.PowerOnTpm.assert_next_call(subrack_tpm_id)


class TestStaticSimulatorCommon:
    """
    Class for testing commands common to several component manager layers.

    Because the TileComponentManager is designed to pass commands
    through to the TPM simulator or driver that it is driving, many
    commands are common to multiple classes. Here we test the flow of
    commands to the simulator. Tests in this class are tested against:

    * the StaticTpmSimulator
    * the StaticTpmSimulatorComponentManager,
    * the SwitchingTpmComponentManager (in simulation and test mode)
    * the TileComponentManager (in simulation and test mode and turned
      on)
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

    @pytest.fixture(
        params=[
            "static_tpm_simulator",
            "static_tpm_simulator_component_manager",
            "switching_tpm_component_manager",
            "tile_component_manager",
        ]
    )
    def tile(
        self: TestStaticSimulatorCommon,
        static_tpm_simulator: StaticTpmSimulator,
        static_tpm_simulator_component_manager: StaticTpmSimulatorComponentManager,
        switching_tpm_component_manager: SwitchingTpmComponentManager,
        tile_component_manager: TileComponentManager,
        communication_state_changed_callback: MockCallable,
        request: SubRequest,
    ) -> Union[
        StaticTpmSimulator,
        StaticTpmSimulatorComponentManager,
        SwitchingTpmComponentManager,
        TileComponentManager,
    ]:
        """
        Return the tile component under test.

        This is parametrised to return

        * a static TPM simulator,

        * a static TPM simulator component manager,

        * a component manager that can switch between TPM driver and
          simulators.

        * a Tile component manager (in simulation and test mode and
          turned on)

        So any test that relies on this fixture will be run four times:
        once for each of the above classes.

        :param static_tpm_simulator: the static TPM simulator to return
        :param static_tpm_simulator_component_manager: the static TPM
            simulator component manager to return
        :param switching_tpm_component_manager: the component manager
            that switches between TPM simulator and TPM driver to return
        :param tile_component_manager: the tile component manager (in
            simulation mode) to return
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param request: A pytest object giving access to the requesting test
            context.

        :raises ValueError:if fixture is parametrized with unrecognised
            option

        :return: the tile class object under test
        """
        self.tile_name = request.param
        if request.param == "static_tpm_simulator":
            return static_tpm_simulator
        elif request.param == "static_tpm_simulator_component_manager":
            static_tpm_simulator_component_manager.start_communicating()
            return static_tpm_simulator_component_manager
        elif request.param == "switching_tpm_component_manager":
            switching_tpm_component_manager.start_communicating()
            return switching_tpm_component_manager
        elif request.param == "tile_component_manager":
            tile_component_manager.start_communicating()
            communication_state_changed_callback.assert_next_call(
                CommunicationStatus.NOT_ESTABLISHED
            )
            time.sleep(0.1)
            # With the update to v0.13 of the base classes the logic to change the
            # power_state of a device has been moved from the component manager to
            # the device itself.
            # This means that during component manager tests we cannot change the
            # power state or other attributes "naturally" and thus this workaround
            # is used where we assert the callback was called as we would expect
            # and then manually set the attribute.
            callback = tile_component_manager._component_state_changed_callback
            callback.assert_next_call_with_keys({"power_state": PowerState.ON})
            tile_component_manager.power_state = PowerState.ON
            return tile_component_manager
        raise ValueError("Tile fixture parametrized with unrecognised option")

    @pytest.mark.parametrize(
        ("attribute_name", "expected_value"),
        (
            ("current", StaticTpmSimulator.CURRENT),
            ("voltage", StaticTpmSimulator.VOLTAGE),
            ("board_temperature", StaticTpmSimulator.BOARD_TEMPERATURE),
            ("fpga1_temperature", StaticTpmSimulator.FPGA1_TEMPERATURE),
            ("fpga2_temperature", StaticTpmSimulator.FPGA2_TEMPERATURE),
            ("adc_rms", StaticTpmSimulator.ADC_RMS),
            ("fpgas_time", StaticTpmSimulator.FPGAS_TIME),
            (
                "current_tile_beamformer_frame",
                StaticTpmSimulator.CURRENT_TILE_BEAMFORMER_FRAME,
            ),
            ("pps_delay", StaticTpmSimulator.PPS_DELAY),
            ("firmware_available", StaticTpmSimulator.FIRMWARE_AVAILABLE),
            ("register_list", list(StaticTpmSimulator.REGISTER_MAP[0].keys())),
        ),
    )
    def test_read_attribute(
        self: TestStaticSimulatorCommon,
        tile: Union[
            StaticTpmSimulator,
            StaticTpmSimulatorComponentManager,
            SwitchingTpmComponentManager,
            TileComponentManager,
        ],
        attribute_name: str,
        expected_value: Any,
    ) -> None:
        """
        Tests that read-only attributes take certain known initial values.

        This is a weak test; over time we should find ways to more thoroughly
        test each of these independently.

        :param tile: the tile class object under test.
        :param attribute_name: the name of the attribute under test
        :param expected_value: the expected value of the attribute. This
            can be any type, but the test of the attribute is a single
            "==" equality test.
        """
        # With the update to v0.13 of the base classes the logic to change the
        # power_state of a device has been moved from the component manager to
        # the device itself.
        # This means that during component manager tests we cannot change the
        # power state or other attributes "naturally" and thus this workaround
        # is used where we assert the callback was called as we would expect and
        # then manually set the attribute.
        # We exclude the StaticTpmSimulator as it does not have this callback.
        if not isinstance(tile, StaticTpmSimulator):
            tile._component_state_changed_callback.assert_next_call_with_keys(
                {"power_state": PowerState.ON}
            )
            tile.power_state = PowerState.ON
        assert getattr(tile, attribute_name) == expected_value

    @pytest.mark.parametrize(
        ("attribute_name", "initial_value", "values_to_write"),
        (
            (
                "phase_terminal_count",
                StaticTpmSimulator.PHASE_TERMINAL_COUNT,
                [1, 2],
            ),
        ),
    )
    def test_write_attribute(
        self: TestStaticSimulatorCommon,
        tile: Union[
            StaticTpmSimulator,
            StaticTpmSimulatorComponentManager,
            SwitchingTpmComponentManager,
            TileComponentManager,
        ],
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
        """
        # With the update to v0.13 of the base classes the logic to change the
        # power_state of a device has been moved from the component manager to
        # the device itself.
        # This means that during component manager tests we cannot change the
        # power state or other attributes "naturally" and thus this workaround
        # is used where we assert the callback was called as we would expect and
        # then manually set the attribute.
        # We exclude the StaticTpmSimulator as it does not have this callback.
        if not isinstance(tile, StaticTpmSimulator):
            tile._component_state_changed_callback.assert_next_call_with_keys(
                {"power_state": PowerState.ON}
            )
            tile.power_state = PowerState.ON

        assert getattr(tile, attribute_name) == initial_value

        for value in values_to_write:
            setattr(tile, attribute_name, value)
            assert getattr(tile, attribute_name) == value

    @pytest.mark.parametrize(
        ("command_name", "num_args"),
        (
            ("get_arp_table", 0),
            ("cpld_flash_write", 1),
            ("set_channeliser_truncation", 1),
            ("set_beamformer_regions", 1),
            ("initialise_beamformer", 4),
            ("set_lmc_download", 1),
            ("switch_calibration_bank", 0),
            ("load_beam_angle", 1),
            ("load_calibration_coefficients", 2),
            ("load_calibration_curve", 3),
            ("load_antenna_tapering", 2),
            ("load_pointing_delay", 1),
            ("set_pointing_delay", 2),
            ("configure_integrated_channel_data", 3),
            ("configure_integrated_beam_data", 3),
            ("stop_integrated_data", 0),
            ("send_raw_data", 0),
            ("send_channelised_data", 0),
            ("send_channelised_data", 1),
            ("send_beam_data", 0),
            ("stop_data_transmission", 0),
            ("compute_calibration_coefficients", 0),
            ("start_acquisition", 2),
            ("set_time_delays", 1),
            ("set_csp_rounding", 1),
            ("set_lmc_integrated_download", 3),
            ("send_channelised_data_narrowband", 2),
            ("tweak_transceivers", 0),
            ("post_synchronisation", 0),
            ("sync_fpgas", 0),
            ("check_pending_data_requests", 0),
        ),
    )
    def test_command(
        self: TestStaticSimulatorCommon,
        tile: Union[
            StaticTpmSimulator,
            StaticTpmSimulatorComponentManager,
            SwitchingTpmComponentManager,
            TileComponentManager,
        ],
        mocker: pytest_mock.MockerFixture,
        command_name: str,
        num_args: int,
    ) -> None:
        """
        Test of commands that aren't implemented yet.

        Since the commands don't really do
        anything, these tests simply check that the command can be called.

        :param mocker: fixture that wraps unittest.mock
        :param tile: the tile class object under test.
        :param command_name: the name of the command under test
        :param num_args: the number of args the command takes
        """
        lrc_list = [
            "cpld_flash_write",
            "get_arp_table",
            "start_acquisition",
            "post_synchronisation",
            "sync_fpgas",
        ]
        args = [mocker.Mock()] * num_args
        if command_name in lrc_list and self.tile_name == "tile_component_manager":
            command_name = "_" + command_name
        # With the update to v0.13 of the base classes the logic to change
        # the power_state of a device has been moved from the component manager
        # to the device itself.
        # This means that during component manager tests we cannot change the
        # power state or other attributes "naturally" and thus this workaround
        # is used where we assert the callback was called as we would expect and
        # then manually set the attribute. We exclude the StaticTpmSimulator as
        # it does not have this callback.
        if not isinstance(tile, StaticTpmSimulator):
            tile._component_state_changed_callback.assert_next_call_with_keys(
                {"power_state": PowerState.ON}
            )
            tile.power_state = PowerState.ON
        with pytest.raises(NotImplementedError):
            getattr(tile, command_name)(*args)

    def test_initialise(
        self: TestStaticSimulatorCommon,
        tile: Union[
            StaticTpmSimulator,
            StaticTpmSimulatorComponentManager,
            SwitchingTpmComponentManager,
            TileComponentManager,
        ],
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
        tile: Union[
            StaticTpmSimulator,
            StaticTpmSimulatorComponentManager,
            SwitchingTpmComponentManager,
            TileComponentManager,
        ],
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

    @pytest.mark.parametrize("device", (1,))
    @pytest.mark.parametrize("register", [f"test-reg{i}" for i in (1, 4)])
    @pytest.mark.parametrize("read_offset", (2,))
    @pytest.mark.parametrize("read_length", (4,))
    @pytest.mark.parametrize("write_offset", (3,))
    @pytest.mark.parametrize("write_values", ([], [1], [2, 2]), ids=(0, 1, 2))
    def test_read_and_write_register(
        self: TestStaticSimulatorCommon,
        tile: Union[
            StaticTpmSimulator,
            StaticTpmSimulatorComponentManager,
            SwitchingTpmComponentManager,
            TileComponentManager,
        ],
        device: int,
        register: str,
        read_offset: int,
        read_length: int,
        write_offset: int,
        write_values: list[int],
    ) -> None:
        """
        Test read and write registers.

        Test the:
        * read_register command
        * write_register command

        :param tile: the tile class object under test.
        :param device: which FPGA is being addressed
        :param register: which register is being addressed
        :param read_offset: offset to start read at
        :param read_length: length of read
        :param write_offset: offset to start write at
        :param write_values: values to write to the register
        """
        buffer_size = max(read_offset + read_length, write_offset + len(write_values))
        buffer = [0] * buffer_size
        for (index, value) in enumerate(write_values):
            buffer[write_offset + index] = value
        expected_read = buffer[read_offset : (read_offset + read_length)]
        tile.write_register(register, write_values, write_offset, device)
        assert (
            tile.read_register(register, read_length, read_offset, device)
            == expected_read
        )

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
        tile: Union[
            StaticTpmSimulator,
            StaticTpmSimulatorComponentManager,
            SwitchingTpmComponentManager,
            TileComponentManager,
        ],
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
        expected_read = list(buffer[buffer_slice(read_address, read_length)])

        tile.write_address(write_address, write_values)
        assert tile.read_address(read_address, read_length) == expected_read

    def test_start_stop_beamformer(
        self: TestStaticSimulatorCommon,
        tile: Union[
            StaticTpmSimulator,
            StaticTpmSimulatorComponentManager,
            SwitchingTpmComponentManager,
            TileComponentManager,
        ],
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

    def test_40g_configuration(
        self: TestStaticSimulatorCommon,
        tile: Union[
            StaticTpmSimulator,
            StaticTpmSimulatorComponentManager,
            SwitchingTpmComponentManager,
            TileComponentManager,
        ],
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
            2,
            1,
            "mock_src_mac",
            "mock_src_ip",
            8888,
            "mock_dst_ip",
            3333,
        )

        expected = {
            "core_id": 2,
            "arp_table_entry": 1,
            "src_mac": "mock_src_mac",
            "src_ip": "mock_src_ip",
            "src_port": 8888,
            "dst_ip": "mock_dst_ip",
            "dst_port": 3333,
        }

        assert tile.get_40g_configuration(-1, 0) == [expected]
        assert tile.get_40g_configuration(2) == [expected]
        assert tile.get_40g_configuration(10) == []

    def test_test_mode(
        self: TestDriverCommon,
        mock_tile_component_manager_with_tpm_manager_fixture: TileComponentManager,
        switching_tpm_component_manager: SwitchingTpmComponentManager,
    ) -> None:
        """
        Test that when we changes to the test mode on the tile are propagated to TPM.

        :param mock_tile_component_manager_with_tpm_manager_fixture: the
            mocked tile with a mocked tpm_component manager injected.
        :param switching_tpm_component_manager: the mocked tpm injected.

        Test that:
        * Test that when we set test mode on the TileComponentManager this is
        propagated to the TPMComponentManager.
        """
        mock_tile_component_manager_with_tpm_manager_fixture.test_mode = TestMode.TEST
        assert getattr(switching_tpm_component_manager, "test_mode") == TestMode.TEST
        assert (
            mock_tile_component_manager_with_tpm_manager_fixture.test_mode
            == TestMode.TEST
        )

        mock_tile_component_manager_with_tpm_manager_fixture.test_mode = TestMode.NONE
        assert getattr(switching_tpm_component_manager, "test_mode") == TestMode.NONE
        assert (
            mock_tile_component_manager_with_tpm_manager_fixture.test_mode
            == TestMode.NONE
        )

    def test_start_tpm_connection(
        self: TestDriverCommon,
        mock_tile_component_manager_with_tpm_manager_fixture: TileComponentManager,
        switching_tpm_component_manager: SwitchingTpmComponentManager,
        communication_state_changed_callback: unittest.mock.Mock,
        component_state_changed_callback: unittest.mock.Mock,
    ) -> None:
        """
        Test the start tpm_connection.

        :param mock_tile_component_manager_with_tpm_manager_fixture: the
            mocked tile with a mocked tpm_component manager injected.
        :param switching_tpm_component_manager: the mocked tpm injected.
        :param communication_state_changed_callback: the mocked communication callback.
        :param component_state_changed_callback: the mocked state callback.

        Test that:
        * when the tile orchestrator commands the tile to connect to the
        TPM with the correct states assumed, a connection is ESTABLISHED
        * when the tile orchestrator command the tile to stop communicating
        the power state is none and fault is none
        """
        # tile orchestrator requests to connect to TPM
        # mock_tile_component_manager_with_tpm_manager_fixture._tile_orchestrator._start_communicating_with_tpm()

        # sanity check of initial conditions
        assert switching_tpm_component_manager.simulation_mode == SimulationMode.TRUE
        assert switching_tpm_component_manager.test_mode == TestMode.TEST
        assert (
            switching_tpm_component_manager._communication_state
            == CommunicationStatus.DISABLED
        )
        # tile orchestrator requests to connect to TPM
        tile_orchestrator = (
            mock_tile_component_manager_with_tpm_manager_fixture._tile_orchestrator
        )
        tile_orchestrator._start_communicating_with_tpm()
        # we check that we have established a connection
        communication_state_changed_callback.assert_last_call(
            CommunicationStatus.ESTABLISHED
        )

        tile_orchestrator._stop_communicating_with_tpm()
        # we check that we have established a connection
        component_state_changed_callback.assert_last_call(
            {"power_state": None, "fault": None}
        )


class TestDynamicSimulatorCommon:
    """
    Class for testing commands common to several component manager layers.

    Because the TileComponentManager is designed to pass commands
    through to the TPM simulator or driver that it is driving, many
    commands are common to multiple classes. Here we test the flow of
    commands to the dynamic TPM simulator. Tests in this class are
    tested against:

    * the DynamicTpmSimulator
    * the DynamicTpmSimulatorComponentManager,
    * the SwitchingTpmComponentManager (in simulation mode, test mode off)
    * the TileComponentManager (in simulation mode, test mode off, and
      turned on)
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

    @pytest.fixture(
        params=[
            "dynamic_tpm_simulator_component_manager",
            "switching_tpm_component_manager",
            "tile_component_manager",
        ]
    )
    def tile(
        self: TestDynamicSimulatorCommon,
        dynamic_tpm_simulator_component_manager: DynamicTpmSimulatorComponentManager,
        switching_tpm_component_manager: SwitchingTpmComponentManager,
        tile_component_manager: TileComponentManager,
        request: SubRequest,
    ) -> Union[
        DynamicTpmSimulatorComponentManager,
        SwitchingTpmComponentManager,
        TileComponentManager,
    ]:
        """
        Return the tile component under test.

        This is parametrised to return

        * a dynamic TPM simulator component manager,

        * a component manager that can switch between TPM driver and
          simulators.

        * a Tile component manager (in simulation and test mode and
          turned on)

        So any test that relies on this fixture will be run three times:
        once for each of the above classes.

        :param dynamic_tpm_simulator_component_manager: the dynamic TPM
            simulator component manager to return
        :param switching_tpm_component_manager: the component manager
            that switches between TPM simulator and TPM driver to return
        :param tile_component_manager: the tile component manager (in
            simulation mode) to return
        :param request: A pytest object giving access to the requesting test
            context.

        :raises ValueError: if parametrized with an unrecognised option

        :return: the tile class object under test
        """
        if request.param == "dynamic_tpm_simulator_component_manager":
            dynamic_tpm_simulator_component_manager.start_communicating()
            return dynamic_tpm_simulator_component_manager
        elif request.param == "switching_tpm_component_manager":
            switching_tpm_component_manager.start_communicating()
            return switching_tpm_component_manager
        elif request.param == "tile_component_manager":
            tile_component_manager.start_communicating()
            time.sleep(0.1)
            # With the update to v0.13 of the base classes the logic to change
            # the power_state of a device has been moved from the component manager
            # to the device itself.
            # This means that during component manager tests we cannot change the
            # power state or other attributes "naturally" and thus this workaround
            # is used where we assert the callback was called as we would expect and
            # then manually set the attribute.
            callback = tile_component_manager._component_state_changed_callback
            callback.assert_next_call_with_keys({"power_state": PowerState.ON})
            tile_component_manager.power_state = PowerState.ON
            return tile_component_manager
        raise ValueError("Tile fixture parametrized with unrecognised option")

    @pytest.mark.parametrize(
        "attribute_name",
        (
            "current",
            "voltage",
            "board_temperature",
            "fpga1_temperature",
            "fpga2_temperature",
        ),
    )
    def test_dynamic_attribute(
        self: TestDynamicSimulatorCommon,
        tile: Union[
            DynamicTpmSimulatorComponentManager,
            SwitchingTpmComponentManager,
            TileComponentManager,
        ],
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
        time.sleep(1.1)
        new_attribute_value = getattr(tile, attribute_name)
        assert new_attribute_value is not None
        assert new_attribute_value != attribute_value

    @pytest.mark.parametrize(
        ("attribute_name", "expected_value"),
        (
            ("adc_rms", DynamicTpmSimulator.ADC_RMS),
            ("fpgas_time", DynamicTpmSimulator.FPGAS_TIME),
            (
                "current_tile_beamformer_frame",
                DynamicTpmSimulator.CURRENT_TILE_BEAMFORMER_FRAME,
            ),
            ("pps_delay", DynamicTpmSimulator.PPS_DELAY),
            ("firmware_available", DynamicTpmSimulator.FIRMWARE_AVAILABLE),
            (
                "register_list",
                list(DynamicTpmSimulator.REGISTER_MAP[0].keys()),
            ),
        ),
    )
    def test_read_static_attribute(
        self: TestDynamicSimulatorCommon,
        tile: Union[
            DynamicTpmSimulatorComponentManager,
            SwitchingTpmComponentManager,
            TileComponentManager,
        ],
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
        # With the update to v0.13 of the base classes the logic to change the
        # power_state of a device has been moved from the component manager to
        # the device itself.
        # This means that during component manager tests we cannot change the
        # power state or other attributes "naturally" and thus this workaround
        # is used where we assert the callback was called as we would expect and
        # then manually set the attribute.
        # tile._component_state_changed_callback.assert_next_call_with_keys(
        # {"power_state": PowerState.ON})
        # tile.power_state = PowerState.ON
        assert getattr(tile, attribute_name) == expected_value


class TestDriverCommon:
    """
    Class for testing commands common to several component manager layers.

    Because the TileComponentManager is designed to pass commands
    through to the TpmSimulator or TpmDriver that it is driving, many
    commands are common to multiple classes. Here we test the flow of
    commands to the driver. Tests in this class are deployed to:

    * the TpmDriver,
    * the SwitchingTpmComponentManager (in driver mode)
    * the TileComponentManager (in driver mode)
    """

    @pytest.fixture()
    def simulation_mode(self: TestDriverCommon) -> SimulationMode:
        """
        Return the simulation mode.

        To be used when initialising the tile class object
        under test.

        :return: the simulation mode to be used when initialising the
            tile class object under test.
        """
        return SimulationMode.FALSE

    @pytest.fixture()
    def hardware_tile_mock(self: TestDriverCommon) -> unittest.mock.Mock:
        """
        Provide a mock for the hardware tile.

        :return: An hardware tile mock
        """
        return unittest.mock.Mock()

    class PatchedTpmDriver(TpmDriver):
        """Patched TpmDriver class."""

        def __init__(
            self: TestDriverCommon.PatchedTpmDriver,
            logger: logging.Logger,
            max_workers: int,
            tile_id: int,
            ip: str,
            port: int,
            tpm_version: str,
            communication_state_changed_callback: Callable[[CommunicationStatus], None],
            component_state_changed_callback: Callable[[bool], None],
            aavs_tile: unittest.mock.Mock,
        ) -> None:
            """
            Initialise a new patched TPM driver instance.

            :param logger: a logger for this simulator to use
            :param max_workers: nos of worker threads
            :param tile_id: the unique ID for the tile
            :param ip: IP address for hardware tile
            :param port: IP address for hardware tile control
            :param tpm_version: TPM version: "tpm_v1_2" or "tpm_v1_6"
            :param communication_state_changed_callback: callback to be
                called when the status of the communications channel between
                the component manager and its component changes
            :param component_state_changed_callback: callback to be called when the
                component faults (or stops faulting)
            :param aavs_tile: a mock of the hardware tile
            """
            super().__init__(
                logger,
                max_workers,
                tile_id,
                ip,
                port,
                tpm_version,
                communication_state_changed_callback,
                component_state_changed_callback,
            )
            self.tile = aavs_tile

    @pytest.fixture()
    def patched_tpm_driver(
        self: TestDriverCommon,
        logger: logging.Logger,
        max_workers: int,
        tile_id: int,
        tpm_ip: str,
        tpm_cpld_port: int,
        tpm_version: str,
        communication_state_changed_callback: MockCallable,
        component_state_changed_callback: MockCallable,
        hardware_tile_mock: unittest.mock.Mock,
    ) -> PatchedTpmDriver:
        """
        Return a patched TPM driver.

        :param logger: the logger to be used by this object
        :param max_workers: nos of worker threads
        :param tile_id: the unique ID for the tile
        :param tpm_ip: the IP address of the tile
        :param tpm_cpld_port: the port at which the tile is accessed for control
        :param tpm_version: TPM version: "tpm_v1_2" or "tpm_v1_6"
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be called when the
            component faults (or stops faulting)
        :param hardware_tile_mock: a mock of the hardware tile

        :return: a patched TPM driver
        """
        return self.PatchedTpmDriver(
            logger,
            max_workers,
            tile_id,
            tpm_ip,
            tpm_cpld_port,
            tpm_version,
            communication_state_changed_callback,
            component_state_changed_callback,
            hardware_tile_mock,
        )

    def test_communication_fails(
        self: TestDriverCommon,
        patched_tpm_driver: PatchedTpmDriver,
        hardware_tile_mock: unittest.mock.Mock,
    ) -> None:
        """
        Test we can create the driver but not start communication with the component.

        We can create the tile class object under test, but will not be
        able to use it to establish communication with the component
        (which is a hardware TPM that does not exist in this test
        harness).

        :param patched_tpm_driver: the patched tpm driver under test.
        :param hardware_tile_mock: An hardware tile mock
        """
        hardware_tile_mock.tpm = None
        assert patched_tpm_driver.communication_state == CommunicationStatus.DISABLED
        patched_tpm_driver.start_communicating()
        assert (
            patched_tpm_driver.communication_state
            == CommunicationStatus.NOT_ESTABLISHED
        )
        # Wait for the message to execute
        # then check that the connect has been called
        # but the component is still unconnected
        time.sleep(0.3)
        hardware_tile_mock.connect.assert_called_with()
        assert (
            patched_tpm_driver.communication_state
            == CommunicationStatus.NOT_ESTABLISHED
        )

    def test_communication(
        self: TestDriverCommon,
        patched_tpm_driver: PatchedTpmDriver,
        hardware_tile_mock: unittest.mock.Mock,
    ) -> None:
        """
        Test we can create the driver and start communication with the component.

        We can create the tile class object under test, and we will mock
        the underlying component (which is a hardware TPM that does not exist
        in this test harness).

        :param patched_tpm_driver: the patched tpm driver under test.
        :param hardware_tile_mock: An hardware tile mock
        """
        hardware_tile_mock.tpm = True
        assert patched_tpm_driver.communication_state == CommunicationStatus.DISABLED
        patched_tpm_driver.start_communicating()
        assert (
            patched_tpm_driver.communication_state
            == CommunicationStatus.NOT_ESTABLISHED
        )

        # Wait for the message to execute
        time.sleep(1)
        hardware_tile_mock.connect.assert_called_once()
        # assert "_ConnectToTile" in patched_tpm_driver._queue_manager._task_result[0]
        # assert patched_tpm_driver._queue_manager._task_result[1] == str(
        #    ResultCode.OK.value
        # )

        # assert patched_tpm_driver._queue_manager._task_result[2] ==
        # "Connected to Tile"
        assert patched_tpm_driver.communication_state == CommunicationStatus.ESTABLISHED

        # assert getattr(switching_tpm_component_manager, "test_mode")
        # #== TestMode.TEST
        # assert mock_tile_component_manager_with_tpm_manager_fixture.test_mode
        # #== TestMode.TEST

        # mock_tile_component_manager_with_tpm_manager_fixture.test_mode
        # # = TestMode.NONE
        # assert getattr(switching_tpm_component_manager, "test_mode")
        # # == TestMode.NONE
        # assert mock_tile_component_manager_with_tpm_manager_fixture.test_mode
        # # == TestMode.NONE
