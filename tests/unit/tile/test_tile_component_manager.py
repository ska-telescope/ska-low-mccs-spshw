# pylint: disable=too-many-lines
# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests of the tile component manage."""
from __future__ import annotations

import datetime
import logging
import time
import unittest.mock
from typing import Any

import numpy as np
import pytest
import pytest_mock
import tango
from pyfabil.base.definitions import LibraryError
from ska_control_model import (
    CommunicationStatus,
    PowerState,
    ResultCode,
    SimulationMode,
    TaskStatus,
    TestMode,
)
from ska_tango_testing.mock import MockCallableGroup
from ska_tango_testing.mock.placeholders import Anything

from ska_low_mccs_spshw.tile import (
    DynamicTileSimulator,
    MockTpm,
    TileComponentManager,
    TileSimulator,
    TpmStatus,
)

RFC_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


class TestTileComponentManager:
    """
    Class for testing the tile component manager.

    Many of its methods and properties map to the underlying TPM
    simulator or driver, and these are tested in the class below. Here,
    we just perform tests of functionality in the tile component manager
    itself.
    """

    # pylint: disable=too-many-arguments
    @pytest.mark.parametrize("power_state", PowerState)
    def test_communication_when_tpm_not_reachable(
        self: TestTileComponentManager,
        tile_component_manager: TileComponentManager,
        callbacks: MockCallableGroup,
        power_state: PowerState,
        tile_id: int,
        mock_subrack_device_proxy: unittest.mock.Mock,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Test communication with a unreachable TPM.

        :param tile_component_manager: the tile component manager
            under test
        :param callbacks: dictionary of driver callbacks.
        :param power_state: the power mode of the TPM when we break off
            comms
        :param mock_subrack_device_proxy: a mock device proxy to a
            subrack device.
        :param tile_simulator: the backend simulator.
        :param tile_id: the logical tile id
        """
        tile_simulator.mock_off(lock=True)

        assert (
            tile_component_manager.communication_state == CommunicationStatus.DISABLED
        )
        # takes the component out of DISABLED. Connects with subrack (NOT with TPM)

        # Dynamically configure mock return
        mock_subrack_device_proxy.configure_mock(tpm1PowerState=power_state)

        tile_component_manager.start_communicating()
        callbacks["communication_status"].assert_call(
            CommunicationStatus.NOT_ESTABLISHED
        )

        match power_state:
            case PowerState.ON:
                callbacks["component_state"].assert_call(power=power_state)
                callbacks["component_state"].assert_call(
                    programming_state=TpmStatus.UNCONNECTED.pretty_name()
                )
                callbacks["component_state"].assert_not_called()
            case PowerState.UNKNOWN:
                callbacks["component_state"].assert_not_called()
            case _:
                # OFF, NO_SUPPLY, STANDBY
                callbacks["component_state"].assert_call(power=power_state, lookahead=2)
                callbacks["component_state"].assert_call(
                    programming_state=TpmStatus.OFF.pretty_name(), lookahead=2
                )
                callbacks["component_state"].assert_not_called()

        callbacks["communication_status"].assert_not_called()
        tile_component_manager.stop_communicating()

        callbacks["communication_status"].assert_call(CommunicationStatus.DISABLED)
        assert (
            tile_component_manager.communication_state == CommunicationStatus.DISABLED
        )

    # pylint: disable=too-many-arguments
    @pytest.mark.parametrize("power_state", PowerState)
    def test_communication_when_tpm_reachable(
        self: TestTileComponentManager,
        tile_component_manager: TileComponentManager,
        callbacks: MockCallableGroup,
        power_state: PowerState,
        tile_id: int,
        mock_subrack_device_proxy: unittest.mock.Mock,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Test communication with a reachable TPM.

        :param tile_component_manager: the tile component manager
            under test
        :param callbacks: dictionary of driver callbacks.
        :param power_state: the power mode of the TPM when we break off
            comms
        :param mock_subrack_device_proxy: a mock device proxy to a
            subrack device.
        :param tile_simulator: the backend simulator.
        :param tile_id: the logical tile id
        """
        # Mock the Tpm to be unconnectable and the subrack to return select POWER
        tile_simulator.mock_on(lock=True)

        mock_subrack_device_proxy.configure_mock(tpm1PowerState=power_state)

        assert (
            tile_component_manager.communication_state == CommunicationStatus.DISABLED
        )
        # takes the component out of DISABLED. Connects with subrack (NOT with TPM)

        # Dynamically configure mock return
        mock_subrack_device_proxy.configure_mock(tpm1PowerState=power_state)

        tile_component_manager.start_communicating()
        callbacks["communication_status"].assert_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)
        match power_state:
            case PowerState.ON:
                callbacks["component_state"].assert_call(
                    **{
                        "global_status_alarms": {
                            "I2C_access_alm": 0,
                            "temperature_alm": 0,
                            "voltage_alm": 0,
                            "SEM_wd": 0,
                            "MCU_wd": 0,
                        }
                    },
                    lookahead=3,
                )
                callbacks["component_state"].assert_call(power=power_state, lookahead=3)
                callbacks["component_state"].assert_call(
                    programming_state=TpmStatus.UNPROGRAMMED.pretty_name(), lookahead=3
                )
            case PowerState.UNKNOWN:
                # We start in UNKNOWN so no need to assert
                callbacks["component_state"].assert_call(
                    **{
                        "global_status_alarms": {
                            "I2C_access_alm": 0,
                            "temperature_alm": 0,
                            "voltage_alm": 0,
                            "SEM_wd": 0,
                            "MCU_wd": 0,
                        }
                    },
                    lookahead=3,
                )
                callbacks["component_state"].assert_call(
                    power=PowerState.ON, lookahead=3
                )
                callbacks["component_state"].assert_call(
                    programming_state=TpmStatus.UNPROGRAMMED.pretty_name(), lookahead=3
                )

            case _:
                # OFF, NO_SUPPLY, STANDBY
                # We start in UNKNOWN so no need to assert

                callbacks["component_state"].assert_call(
                    **{
                        "global_status_alarms": {
                            "I2C_access_alm": 0,
                            "temperature_alm": 0,
                            "voltage_alm": 0,
                            "SEM_wd": 0,
                            "MCU_wd": 0,
                        }
                    },
                    lookahead=3,
                )
                callbacks["component_state"].assert_call(
                    power=PowerState.ON, lookahead=3
                )
                callbacks["component_state"].assert_call(
                    programming_state=TpmStatus.UNPROGRAMMED.pretty_name(), lookahead=3
                )

        tile_component_manager.stop_communicating()

        callbacks["communication_status"].assert_call(CommunicationStatus.DISABLED)
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
        callbacks: MockCallableGroup,
        first_power_state: PowerState,
        second_power_state: PowerState,
        mock_subrack_device_proxy: unittest.mock.Mock,
        tile_id: int,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Test handling of notifications of TPM power mode changes from the subrack.

        :param tile_component_manager: the tile component manager
            under test
        :param callbacks: dictionary of driver callbacks.
        :param first_power_state: the power mode of the initial event
        :param second_power_state: the power mode of the subsequent event
        :param tile_id: the logical tile id
        :param mock_subrack_device_proxy: a mock device proxy to a
            subrack device.
        :param tile_simulator: a mock tpm to test
        """
        if first_power_state == PowerState.ON:
            tile_simulator.mock_on()
        else:
            tile_simulator.mock_off()
        mock_subrack_device_proxy.configure_mock(tpm1PowerState=first_power_state)
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

        if first_power_state == PowerState.ON:
            callbacks["communication_status"].assert_call(
                CommunicationStatus.ESTABLISHED
            )
        else:
            callbacks["communication_status"].assert_not_called()

        if second_power_state == PowerState.ON:
            tile_simulator.mock_on()
        else:
            tile_simulator.mock_off()
        tile_component_manager._subrack_says_tpm_power_changed(
            f"tpm{tile_id}powerstate",
            second_power_state,
            tango.EventType.CHANGE_EVENT,
        )
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
        tile_id: int,
    ) -> None:
        """
        Test that we can turn the TPM on and off when the subrack is on.

        :param tile_component_manager: the tile component manager
            under test
        :param callbacks: dictionary of driver callbacks.
        :param subrack_tpm_id: This tile's position in its subrack
        :param mock_subrack_device_proxy: a mock device proxy to a
            subrack device.
        :param tile_id: the logical tile id
        """
        mock_subrack_device_proxy.configure_mock(tpm1PowerState=PowerState.OFF)
        tile_component_manager.start_communicating()

        callbacks["communication_status"].assert_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        callbacks["component_state"].assert_call(power=PowerState.OFF)
        callbacks["component_state"].assert_call(
            programming_state=TpmStatus.OFF.pretty_name()
        )

        callbacks["component_state"].assert_not_called()

        tile_component_manager.on()
        # Manually report the Subrack turning on
        tile_component_manager._subrack_says_tpm_power_changed(
            f"tpm{tile_id}powerstate",
            PowerState.ON,
            tango.EventType.CHANGE_EVENT,
        )
        # If we are on we can ESTABLISH a connection
        callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)
        callbacks["component_state"].assert_call(power=PowerState.ON, lookahead=2)

        tile_component_manager.off()
        # Manually report the Subrack turning on
        tile_component_manager._subrack_says_tpm_power_changed(
            f"tpm{tile_id}powerstate",
            PowerState.OFF,
            tango.EventType.CHANGE_EVENT,
        )
        callbacks["component_state"].assert_call(
            power=PowerState.OFF, lookahead=10, consume_nonmatches=True
        )
        callbacks["component_state"].assert_call(
            programming_state=TpmStatus.OFF.pretty_name()
        )

    def test_eventual_consistency_of_on_command(
        self: TestTileComponentManager,
        tile_component_manager: TileComponentManager,
        subrack_tpm_id: int,
        mock_subrack_device_proxy: unittest.mock.Mock,
        callbacks: MockCallableGroup,
        tile_simulator: TileSimulator,
        tile_id: int,
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
        :param tile_simulator: the backend simulator.
        :param tile_id: the logical tile id
        """
        tile_simulator.mock_off()
        with pytest.raises(AssertionError):
            tile_component_manager.on(task_callback=callbacks["task"])
        callbacks["task"].assert_call(
            status=TaskStatus.REJECTED,
            result=(ResultCode.REJECTED, "No request provider"),
        )

        callbacks["task"].assert_not_called()

        tile_component_manager.start_communicating()

        callbacks["communication_status"].assert_call(
            CommunicationStatus.NOT_ESTABLISHED
        )

        callbacks["communication_status"].assert_not_called()

        # mock an event from subrack announcing it to be turned off
        tile_component_manager._subrack_says_tpm_power_changed(
            f"tpm{tile_id}powerstate",
            PowerState.NO_SUPPLY,
            tango.EventType.CHANGE_EVENT,
        )
        mock_subrack_device_proxy.PowerOnTpm.assert_not_called()

        result_code, message = tile_component_manager.on(callbacks["task"])
        assert result_code == TaskStatus.QUEUED
        assert message == "Task staged"
        time.sleep(0.2)

        # We initially submit the on command to the Subrack and place a
        # Initialise command in the queue.
        mock_subrack_device_proxy.PowerOnTpm.assert_last_call()

        # mock an event from subrack announcing it to be turned on
        tile_component_manager._subrack_says_tpm_power_changed(
            f"tpm{tile_id}powerstate",
            PowerState.ON,
            tango.EventType.CHANGE_EVENT,
        )
        callbacks["task"].assert_call(status=TaskStatus.QUEUED)
        callbacks["task"].assert_call(status=TaskStatus.IN_PROGRESS)
        callbacks["task"].assert_call(
            status=TaskStatus.COMPLETED,
            result=(ResultCode.OK, "Command executed to completion."),
        )


class TestStaticSimulator:  # pylint: disable=too-many-public-methods
    """Class for testing TileComponentManger using the TileSimulator as a backend."""

    @pytest.fixture()
    def initial_tpm_power_state(
        self: TestStaticSimulator,
    ) -> PowerState:
        """
        Return the initial power mode of the TPM.

        Overridden here to put the TPM into ON state, so that we don't
        have to fiddle around with state change events to get the tile_component_manager
        component manager communicating with its tile_component_manager.

        :return: the initial power mode of the TPM.
        """
        return PowerState.ON

    @pytest.fixture()
    def tile_component_manager(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        callbacks: MockCallableGroup,
    ) -> TileComponentManager:
        """
        Return the tile_component_manager component under test.

        :param tile_component_manager: the tile_component_manager
            component manager (driving a TileSimulator)
        :param callbacks: dictionary of driver callbacks.

        :return: the tile_component_manager class object under test
        """
        # pylint: disable=attribute-defined-outside-init
        self.tile_name = "tile_component_manager"

        tile_component_manager.start_communicating()
        callbacks["communication_status"].assert_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)
        tile_component_manager.on(task_callback=callbacks["task"])
        callbacks["component_state"].assert_call(power=PowerState.ON, lookahead=2)

        callbacks["component_state"].assert_call(
            programming_state=TpmStatus.UNPROGRAMMED.pretty_name(), lookahead=2
        )
        callbacks["task"].assert_call(status=TaskStatus.QUEUED)
        callbacks["task"].assert_call(status=TaskStatus.IN_PROGRESS)
        callbacks["task"].assert_call(
            status=TaskStatus.COMPLETED,
            result=(ResultCode.OK, "Command executed to completion."),
        )

        return tile_component_manager

    @pytest.mark.parametrize(
        ("attribute_name", "expected_value"),
        (
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
            ("pending_data_requests", False),
        ),
    )
    def test_read_attribute(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        attribute_name: str,
        expected_value: Any,
    ) -> None:
        """
        Tests that read-only attributes take certain known initial values.

        This is a weak test; over time we should find ways to more thoroughly
        test each of these independently.

        :param tile_component_manager: the tile_component_manager class
            object under test.
        :param attribute_name: the name of the attribute under test
        :param expected_value: the expected value of the attribute. This
            can be any type, but the test of the attribute is a single
            "==" equality test.
        """
        assert getattr(tile_component_manager, attribute_name) == expected_value

    @pytest.mark.parametrize(
        ("attribute_name", "expected_value", "expected_component_value"),
        (
            ("formatted_fpga_reference_time", 0, "1970-01-01T00:00:00.000000Z"),
            ("fpga_frame_time", None, "1970-01-01T00:00:00.000000Z"),
        ),
    )
    def test_read_time_attribute(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        attribute_name: str,
        expected_value: Any,
        expected_component_value: Any,
    ) -> None:
        """
        Tests that read-only time attributes take known initial values.

        This is a weak test; over time we should find ways to more thoroughly
        test each of these independently.

        :param tile_component_manager: the tile_component_manager class
            object under test.
        :param attribute_name: the name of the attribute under test
        :param expected_value: the expected value of the attribute. This
            can be any type, but the test of the attribute is a single
            "==" equality test.
        :param expected_component_value: the expected value in the component
            manager, which is in different format wrt. the value in the
            underlying driver/simulator
        """
        if not isinstance(tile_component_manager, TileComponentManager):
            if expected_value is not None:
                assert getattr(tile_component_manager, attribute_name) == expected_value
        else:
            assert (
                getattr(tile_component_manager, attribute_name)
                == expected_component_value
            )

    @pytest.mark.parametrize(
        ("attribute_name", "initial_value", "values_to_write"),
        (
            (
                "csp_rounding",
                np.array(TileSimulator.CSP_ROUNDING),
                np.array([[1, 2, 3, 4] * 96]),
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
    def test_write_attribute(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
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

        :param tile_component_manager: the tile_component_manager class
            object under test.
        :param attribute_name: the name of the attribute under test
        :param initial_value: the expected initial value of the
            attribute. This can be any type, but the test of the
            attribute is a simple "==" equality test.
        :param values_to_write: a sequence of values to write, in order
            to check that the writes are sticking. The values can be of
            any type, but the test of the attribute is a simple "=="
            equality test.
        """
        if isinstance(initial_value, np.ndarray):
            assert (
                getattr(tile_component_manager, attribute_name) == initial_value
            ).all()
        else:
            assert getattr(tile_component_manager, attribute_name) == initial_value

        for value in values_to_write:
            setattr(tile_component_manager, attribute_name, value)
            if isinstance(value, np.ndarray):
                assert (getattr(tile_component_manager, attribute_name) == value).all()
            else:
                assert getattr(tile_component_manager, attribute_name) == value

    @pytest.mark.parametrize(
        ("command_name", "args"),
        (
            ("load_pointing_delays", [[2] * 32, 1]),
            ("configure_integrated_channel_data", []),
            ("configure_integrated_beam_data", []),
            ("stop_integrated_data", []),
            ("set_lmc_integrated_download", ["raw", 8190, 8190]),
        ),
    )
    def test_command(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        mocker: pytest_mock.MockerFixture,
        command_name: str,
        args: list,
    ) -> None:
        """
        Test of commands that aren't implemented yet.

        Since the commands don't really do
        anything, these tests simply check that the command can be called.

        :param mocker: fixture that wraps unittest.mock
        :param tile_component_manager: the tile_component_manager class
            object under test.
        :param command_name: the name of the command under test
        :param args: the args to pass to the command.
        """
        lrc_list = [
            "post_synchronisation",
        ]
        if command_name in lrc_list and self.tile_name == "tile_component_manager":
            command_name = "_" + command_name

        getattr(tile_component_manager, command_name)(*args)

    @pytest.mark.parametrize(
        ("command_name", "implemented"),
        (
            ("apply_calibration", True),
            ("apply_pointing_delays", True),
            ("start_beamformer", True),
        ),
    )
    def test_timed_command(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        command_name: str,
        implemented: bool,
    ) -> None:
        """
        Test of commands that require a UTC time.

        Since the commands don't really do
        anything, these tests simply check that the command can be called.

        :param tile_component_manager: the tile_component_manager class
            object under test.
        :param command_name: the name of the command under test
        :param implemented: the command is implemented, does not raise error
        """
        # Use ISO formatted time for component manager, numeric for drivers
        # Must also set FPGA sync time in driver
        #
        if self.tile_name == "tile_component_manager":
            args = "2022-11-10T12:34:56.0Z"
            dt = datetime.datetime.strptime(
                "2022-11-10T00:00:00.0Z", "%Y-%m-%dT%H:%M:%S.%fZ"
            )
            timestamp = int(dt.replace(tzinfo=datetime.timezone.utc).timestamp())
            # TODO: there is no fpga_sync_time method.
            # tile_component_manager.fpga_sync_time = timestamp
            # assert tile_component_manager.fpga_sync_time == timestamp
            tile_component_manager._tile_time.set_reference_time(timestamp)
        else:
            args = "123456"

        getattr(tile_component_manager, command_name)()
        getattr(tile_component_manager, command_name)(0)
        getattr(tile_component_manager, command_name)(args)

    def test_download_firmware(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
        mocker: pytest_mock.MockerFixture,
        callbacks: MockCallableGroup,
    ) -> None:
        """
        Test Downloadfirmware command completes.

        Tests that:
        * the download_firmware command can execute to completion.
        * the is_programmed attribute changes upon completion.

        :param tile_component_manager: the tile_component_manager class
            object under test.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        :param mocker: fixture that wraps unittest.mock
        :param callbacks: dictionary of driver callbacks.
        """
        tile_simulator.connect()
        assert tile_simulator.tpm
        tile_simulator.tpm._is_programmed = False
        assert not tile_component_manager.tile.is_programmed()
        mock_bitfile = mocker.Mock()
        tile_component_manager.download_firmware(mock_bitfile, callbacks["task_lrc"])

        callbacks["task_lrc"].assert_call(status=TaskStatus.QUEUED)
        callbacks["task_lrc"].assert_call(status=TaskStatus.IN_PROGRESS)
        callbacks["task_lrc"].assert_call(
            status=TaskStatus.COMPLETED,
            result=(ResultCode.OK, "Command executed to completion."),
        )
        assert tile_component_manager.tile.is_programmed()

    @pytest.mark.parametrize(
        "register", [f"fpga1.test_generator.delay_{i}" for i in (1, 4)]
    )
    @pytest.mark.parametrize("write_values", ([], [1], [2, 2]), ids=(0, 1, 2))
    def test_read_and_write_register(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        register: str,
        write_values: list[int],
    ) -> None:
        """
        Test we can write values to a register.

        Using a tile_simulator to mock the functionality
        of writing to a register

        :param tile_component_manager: the tile_component_manager class
            object under test.
        :param register: which register is being addressed
        :param write_values: values to write to the register
        """
        expected_read = write_values
        tile_component_manager.write_register(register, write_values)
        assert tile_component_manager.read_register(register) == expected_read

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
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
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

        :param tile_component_manager: the tile class object under test.
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
        tile_component_manager.write_address(write_address, write_values)
        assert (
            tile_component_manager.read_address(read_address, read_length)
            == expected_read
        )

    def test_start_stop_beamformer(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
    ) -> None:
        """
        Test start and stop beamformer.

        Test that:
        * the start_beamformer command.
        * the stop_beamformer command.
        * the is_beamformer_running attribute

        :param tile_component_manager: the tile_component_manager class
            object under test.
        """
        assert not tile_component_manager.is_beamformer_running
        tile_component_manager.start_beamformer()
        assert tile_component_manager.is_beamformer_running
        tile_component_manager.stop_beamformer()
        assert not tile_component_manager.is_beamformer_running

    def test_set_beamformer_regions(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
    ) -> None:
        """
        Test set_beamformer_regions.

        Test that:
        * the set_beamformer_regions accepts 2 regions
        * the beamformer table is correctly configured

        :param tile_component_manager: the tile_component_manager class
            object under test.
        """
        regions = [[64, 16, 2, 3, 8, 7, 8, 9], [140, 16, 4, 5, 32, 10, 11, 12]]
        tile_component_manager.set_beamformer_regions(regions)

        time.sleep(4.2)
        with tile_component_manager._hardware_lock:
            table = tile_component_manager.get_beamformer_table()
        expected = [
            [64, 2, 3, 8, 7, 8, 9],
            [72, 2, 3, 16, 7, 8, 9],
            [140, 4, 5, 32, 10, 11, 12],
            [148, 4, 5, 40, 10, 11, 12],
        ] + [[0, 0, 0, 0, 0, 0, 0]] * 44

        assert table == expected

    def test_40g_configuration(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
    ) -> None:
        """
        Test 40G configuration.

        Test that:
        * the configure_40g_core command
        * the get_40g_configuration command

        :param tile_component_manager: the tile_component_manager class
            object under test.
        """
        assert tile_component_manager.get_40g_configuration(-1, 0) == []
        assert tile_component_manager.get_40g_configuration(9) == []

        tile_component_manager.configure_40g_core(
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

        assert tile_component_manager.get_40g_configuration(-1, 0) == [expected]
        assert tile_component_manager.get_40g_configuration(1) == [expected]
        assert tile_component_manager.get_40g_configuration(10) == []

    def test_set_tile_id(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Test that we can get the tile_id from the mocked tile_component_manager.

        :param tile_component_manager: The tile_component_manager under test.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        """
        # Mock a connection to the TPM.
        tile_simulator.connect()

        # Update attributes and check driver updates
        assert tile_component_manager._station_id == tile_simulator._station_id
        tile_component_manager._tile_id = tile_simulator._tile_id

        # mock programmed state
        assert tile_component_manager.tile.is_programmed()

        # Set tile_id case
        tile_component_manager._station_id = 2
        tile_component_manager.tile_id = 5
        assert tile_simulator._station_id == 2
        assert tile_simulator._tile_id == 5

        # Set station_id case
        tile_component_manager._tile_id = 2
        tile_component_manager.station_id = 5
        assert tile_simulator._station_id == 5
        assert tile_simulator._tile_id == 2

        # Mocked to fail
        initial_tile_id = tile_component_manager._tile_id
        initial_station_id = tile_component_manager._station_id
        tile_simulator.set_station_id = unittest.mock.Mock(  # type: ignore[assignment]
            side_effect=LibraryError("attribute mocked to fail")
        )
        # set station_id with mocked failure
        tile_component_manager._tile_id = initial_tile_id + 1
        tile_component_manager.station_id = initial_station_id + 1
        assert tile_simulator._station_id == initial_station_id
        assert tile_simulator._tile_id == initial_tile_id

        # set tile_id with mocked failure
        tile_component_manager._station_id = initial_station_id + 1
        tile_component_manager.tile_id = initial_tile_id + 1
        assert tile_simulator._station_id == initial_station_id
        assert tile_simulator._tile_id == initial_tile_id

    def test_start_acquisition(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
        callbacks: MockCallableGroup,
    ) -> None:
        """
        Test the start acquisition function.

        :param tile_component_manager: The tile_component_manager under test.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        :param callbacks: dictionary of mock callbacks
        """
        # setup mocked tile_component_manager.
        tile_simulator.connect()
        assert tile_component_manager.tile.is_programmed()

        # -------------------------
        # First Initialse the tile_component_manager.
        # -------------------------
        # check the fpga time is not moving
        assert tile_component_manager.tpm_status == TpmStatus.INITIALISED
        assert tile_simulator.tpm
        tile_simulator.tpm._is_programmed = False
        assert tile_component_manager.tpm_status == TpmStatus.UNPROGRAMMED

        initial_time = tile_component_manager.fpgas_time
        time.sleep(1.5)
        final_time = tile_component_manager.fpgas_time
        assert initial_time == final_time

        # Act
        tile_component_manager.initialise(
            program_fpga=True, task_callback=callbacks["task"]
        )

        callbacks["task"].assert_call(status=TaskStatus.QUEUED)
        callbacks["task"].assert_call(status=TaskStatus.IN_PROGRESS)
        callbacks["task"].assert_call(
            status=TaskStatus.COMPLETED,
            result=(ResultCode.OK, "Command executed to completion."),
        )
        # Assert
        assert tile_component_manager.tpm_status == TpmStatus.INITIALISED

        # check the fpga time is moving
        initial_time1 = tile_component_manager.fpgas_time
        time.sleep(1.5)
        final_time1 = tile_component_manager.fpgas_time
        assert initial_time1 != final_time1

        # check the fpga timestamp is not moving
        initial_time2 = tile_component_manager.fpga_current_frame
        time.sleep(1.5)
        final_time2 = tile_component_manager.fpga_current_frame
        assert initial_time2 == final_time2
        # ---------------------------------------------------------
        # Call start_acquisition and check fpga_timestamp is moving
        # ---------------------------------------------------------
        future_time = 4.0
        start_time = int(time.time() + future_time)
        assert tile_component_manager.tpm_status == TpmStatus.INITIALISED
        tile_component_manager.start_acquisition(
            start_time=start_time, delay=1, task_callback=callbacks["task"]
        )
        callbacks["task"].assert_call(status=TaskStatus.QUEUED)
        time.sleep(future_time)
        callbacks["task"].assert_call(status=TaskStatus.IN_PROGRESS)
        callbacks["task"].assert_call(
            status=TaskStatus.COMPLETED,
            result=(ResultCode.OK, "Command executed to completion."),
        )

        # check the fpga timestamp is moving
        initial_time3 = tile_component_manager.fpga_current_frame
        time.sleep(1.5)
        final_time3 = tile_component_manager.fpga_current_frame
        assert initial_time3 != final_time3
        assert tile_component_manager.tpm_status == TpmStatus.SYNCHRONISED

        # Check that exceptions are handled.
        # Shorthand for linter line length
        tcm = tile_component_manager
        tcm._check_channeliser_started = (  # type: ignore[assignment]
            unittest.mock.Mock(side_effect=Exception("mocked exception"))
        )
        tile_component_manager.start_acquisition(
            start_time=start_time, delay=1, task_callback=callbacks["task"]
        )
        tile_simulator.start_acquisition = (  # type: ignore[assignment]
            unittest.mock.Mock(side_effect=Exception("mocked exception"))
        )
        tile_component_manager.start_acquisition(
            start_time=start_time, delay=1, task_callback=callbacks["task"]
        )

    def test_communication_when_connection_failed(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
        callbacks: MockCallableGroup,
    ) -> None:
        """
        Test the start_communication function in failure case.

        :param tile_component_manager: The TileComponentManager instance being tested.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        :param callbacks: A dictionary used to assert callbacks.
        """
        tile_simulator.mock_off()
        with pytest.raises(LibraryError):
            tile_component_manager.ping()

    def test_write_register(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Test the write register function.

        :param tile_component_manager: The TileComponentManager instance being tested.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        """
        # Arrange
        tile_simulator.connect()
        tile_simulator.tpm.write_register = unittest.mock.Mock()  # type: ignore

        # Act
        tile_component_manager.write_register(
            "fpga1.dsp_regfile.stream_status.channelizer_vld", 2
        )

        # Assert
        tile_simulator.tpm.write_register.assert_called_with(  # type: ignore
            "fpga1.dsp_regfile.stream_status.channelizer_vld", [2]
        )

        # Act
        tile_component_manager.write_register(
            "fpga1.dsp_regfile.stream_status.channelizer_vld", [4]
        )

        # Assert
        tile_simulator.tpm.write_register.assert_called_with(  # type: ignore
            "fpga1.dsp_regfile.stream_status.channelizer_vld", [4]
        )

    def test_write_unknown_register(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Test writing to a unknown register.

        :param tile_component_manager: The TileComponentManager instance being tested.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        """
        # Arrange
        tile_simulator.connect()
        tile_simulator.tpm.write_register = unittest.mock.Mock()  # type: ignore

        # Act
        tile_component_manager.write_register("unknown", 17)

        # Assert: We should not be able to write to a incorrect register
        tile_simulator.tpm.write_register.assert_not_called()  # type: ignore

    def test_write_register_failure(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Test the write register function under a failure.

        :param tile_component_manager: The TileComponentManager instance being tested.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        """
        # Arrange
        tile_simulator.connect()
        tile_simulator.tpm.write_register = unittest.mock.Mock(  # type: ignore
            side_effect=Exception("Mocked exception")
        )
        # Check that the exception is caught
        tile_component_manager.write_register(
            "fpga1.dsp_regfile.stream_status.channelizer_vld", 2
        )

    def test_read_register(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Test the read register function.

        :param tile_component_manager: The TileComponentManager instance being tested.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        """
        # Arrange
        tile_simulator.connect()
        tile_simulator.tpm.read_register = unittest.mock.Mock(  # type: ignore
            return_value=3
        )

        # Act
        value_read = tile_component_manager.read_register(
            "fpga1.dsp_regfile.stream_status.channelizer_vld"
        )

        # Assert
        tile_simulator.tpm.read_register.assert_called_with(  # type: ignore
            "fpga1.dsp_regfile.stream_status.channelizer_vld"
        )
        assert value_read == [3]

    def test_read_unknown_register(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Test reading a unknown register.

        :param tile_component_manager: The TileComponentManager instance being tested.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        """
        # Arrange
        tile_simulator.connect()
        tile_simulator.tpm.read_register = unittest.mock.Mock()  # type: ignore

        # Act
        value_read = tile_component_manager.read_register("unknown")

        # Assert: We should not be able to read to a incorrect register
        tile_simulator.tpm.read_register.assert_not_called()  # type: ignore
        assert value_read == []

    def test_read_register_failure(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Test the read register function under a failure.

        :param tile_component_manager: The TileComponentManager instance being tested.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        """
        # Arrange
        tile_simulator.connect()
        tile_simulator.tpm.read_register = unittest.mock.Mock(  # type: ignore
            side_effect=Exception("Mocked exception")
        )
        # Check that the exception is caught
        tile_component_manager.read_register(
            "fpga1.dsp_regfile.stream_status.channelizer_vld"
        )

    def test_write_read_address(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Test we can write and read addresses on the tile_simulator.

        :param tile_component_manager: The tile_component_manager under test.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        """
        # Arrange
        tile_simulator.connect()

        # Act
        tile_component_manager.write_address(4, [2, 3, 4, 5])
        read_value = tile_component_manager.read_address(4, 4)

        # Assert
        assert read_value == [2, 3, 4, 5]

        # Check exceptions are caught.
        tile_simulator.tpm = None
        tile_component_manager.write_address(4, [2, 3, 4, 5])

    def test_read_tile_attributes(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Test that tile can read attributes from tile_simulator.

        :param tile_component_manager: The tile_component_manager under test.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        """
        # Arrange
        tile_simulator.connect()
        assert tile_simulator.tpm is not None
        tile_simulator.tpm._is_programmed = True
        assert tile_component_manager.tpm_status == TpmStatus.INITIALISED
        mocked_sync_time = 2
        tile_simulator.tpm._register_map[
            "fpga1.pps_manager.sync_time_val"
        ] = mocked_sync_time

        # Assert values have been updated.
        assert tile_component_manager.pps_delay == tile_simulator._pps_delay
        assert tile_component_manager.fpga_reference_time == pytest.approx(
            mocked_sync_time
        )

    def test_dumb_read_tile_attributes(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Dumb test of attribute read.

        :param tile_component_manager: The tile_component_manager under test.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        """
        tile_simulator.connect()
        assert tile_simulator.tpm is not None

        _ = tile_component_manager.register_list
        _ = tile_component_manager.pps_present
        # _ = tile_component_manager._check_pps_present()
        with tile_component_manager._hardware_lock:
            _ = tile_component_manager.get_pll_locked()

        assert (
            tile_component_manager.is_beamformer_running
            == tile_simulator.tpm.beam1.is_running()
        )
        assert (
            tile_component_manager.pending_data_requests
            == tile_simulator._pending_data_requests
        )
        # This is a software attribute currently
        assert (
            tile_component_manager.test_generator_active
            == tile_component_manager._test_generator_active
        )

    def test_dumb_write_tile_attributes(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Dumb test of attribute write. Just check that the attributes can be written.

        :param tile_component_manager: The tile_component_manager under test.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        """
        tile_simulator.connect()
        tile_simulator.FPGAS_TIME = [2, 2]
        assert tile_simulator.tpm is not None
        tile_simulator._timestamp = 2

        tile_component_manager.channeliser_truncation = [4] * 512
        _ = tile_component_manager.channeliser_truncation
        tile_component_manager.set_static_delays([12.0] * 32)
        with tile_component_manager._hardware_lock:
            _ = tile_component_manager.get_static_delays()
        tile_component_manager.csp_rounding = [2] * 384
        _ = tile_component_manager.csp_rounding
        tile_component_manager.set_preadu_levels([12.0] * 32)

    def test_tpm_status(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Test that the tpm status reports as expected.

        :param tile_component_manager: The tile_component_manager under test.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        """
        tile_simulator.mock_off()
        assert tile_component_manager.tpm_status == TpmStatus.UNCONNECTED
        tile_simulator.mock_on()
        assert tile_component_manager.tpm_status == TpmStatus.INITIALISED
        tile_simulator.tpm._is_programmed = False
        assert tile_component_manager.tpm_status == TpmStatus.UNPROGRAMMED
        with tile_component_manager._hardware_lock:
            tile_component_manager._execute_initialise(
                program_fpga=True, pps_delay_correction=0
            )
        assert tile_component_manager.tpm_status == TpmStatus.INITIALISED
        with tile_component_manager._hardware_lock:
            tile_component_manager._start_acquisition()
        assert tile_component_manager.tpm_status == TpmStatus.SYNCHRONISED
        tile_simulator.tpm._is_programmed = False
        assert tile_component_manager.tpm_status == TpmStatus.UNPROGRAMMED

    def test_load_time_delays(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Test that we can set the delays to the tile hardware mock.

        :param tile_component_manager: The tile_component_manager under test.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        """
        # Arrange
        tile_simulator.connect()
        # mocked register return
        expected_delay_written: list[float] = list(range(32))

        programmed_delays = [0.0] * 32
        for i in range(32):
            programmed_delays[i] = expected_delay_written[i] * 1.25
        # No method static_time_delays.
        tile_component_manager.set_static_delays(programmed_delays)

        # assert both fpgas have the correct delay
        def check_time_delay(index: int) -> bool:
            if (
                tile_simulator[f"fpga1.test_generator.delay_{index}"]
                == expected_delay_written[index] + 128
                and tile_simulator[f"fpga2.test_generator.delay_{index}"]
                == expected_delay_written[index + 16] + 128
            ):
                return True

            return False

        indexes = list(range(16))
        assert all(map(check_time_delay, indexes)) is True

    def test_read_write_address(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Test read write address.

        The TileComponentManager can be used to write to an address,
        and read the value written.

        :param tile_component_manager: The tile_component_manager under test.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        """
        tile_simulator.connect()

        # Wait for the tile to poll
        time.sleep(1)
        assert tile_simulator.tpm

        expected_read = [2, 3, 3, 4]
        tile_component_manager.write_address(4, expected_read)
        assert (
            tile_component_manager.read_address(4, len(expected_read)) == expected_read
        )

    def test_firmware_avaliable(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Test that the we can get the firmware from the tile_component_manager.

        :param tile_component_manager: The tile_component_manager under test.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        """
        tile_simulator.connect()

        tile_simulator.get_firmware_list = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )

        _ = tile_component_manager.firmware_available
        tile_simulator.get_firmware_list.assert_called_once_with()

        # check that exceptions are caught.
        tile_simulator.get_firmware_list.side_effect = Exception("mocked exception")
        _ = tile_component_manager.firmware_available

    def test_initialise(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
        callbacks: MockCallableGroup,
    ) -> None:
        """
        When we initialise the tile the mockedTPM gets the correct calls.

        :param tile_component_manager: The tile_component_manager under test.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        :param callbacks: dictionary of mock callbacks

        Test cases:
        * Initialise called on a programmed TPM
        * Initialise called on a unprogrammed TPM
        """
        # setup mocked tile_component_manager.
        tile_simulator.connect()
        assert tile_simulator.tpm
        tile_simulator.tpm._is_programmed = False
        assert tile_component_manager.tpm_status == TpmStatus.UNPROGRAMMED

        # check the fpga time is not moving
        initial_time = tile_component_manager.fpgas_time
        time.sleep(1.5)
        final_time = tile_component_manager.fpgas_time
        assert initial_time == final_time

        # check the fpga timestamp is not moving
        initial_time1 = tile_component_manager.fpga_current_frame
        time.sleep(1)
        final_time1 = tile_component_manager.fpga_current_frame
        assert initial_time1 == final_time1

        tile_component_manager.initialise(
            program_fpga=True, task_callback=callbacks["task"]
        )

        callbacks["task"].assert_call(status=TaskStatus.QUEUED)
        callbacks["task"].assert_call(status=TaskStatus.IN_PROGRESS)
        callbacks["task"].assert_call(
            status=TaskStatus.COMPLETED,
            result=(ResultCode.OK, "Command executed to completion."),
        )

        # Assert
        assert tile_component_manager.tpm_status == TpmStatus.INITIALISED
        assert tile_component_manager.tpm_status.pretty_name() == "Initialised"
        assert tile_component_manager.firmware_name == "itpm_v1_6.bit"
        # check the fpga time is moving
        initial_time2 = tile_component_manager.fpgas_time
        time.sleep(1.5)
        final_time2 = tile_component_manager.fpgas_time
        assert initial_time2 != final_time2

        # check the fpga timestamp is not moving
        initial_time3 = tile_component_manager.fpga_current_frame
        time.sleep(1)
        final_time3 = tile_component_manager.fpga_current_frame
        assert initial_time3 == final_time3

        # -----------------------------------------
        # Initialise called with unprogrammable TPM
        # -----------------------------------------
        assert tile_simulator.tpm is not None  # for the type checker
        tile_simulator.tpm._is_programmed = False
        mocked_return = unittest.mock.MagicMock(  # type: ignore[assignment]
            side_effect=Exception("mocked exception")
        )
        tile_simulator.program_fpgas = mocked_return  # type: ignore

        # Act
        tile_component_manager.initialise(
            program_fpga=True,
            task_callback=callbacks["task"],
        )
        callbacks["task"].assert_call(status=TaskStatus.QUEUED)
        callbacks["task"].assert_call(status=TaskStatus.IN_PROGRESS)
        callbacks["task"].assert_call(
            status=TaskStatus.FAILED,
            result=Anything,
        )
        # Check TpmStatus is UNPROGRAMMED.
        assert tile_component_manager.tpm_status == TpmStatus.UNPROGRAMMED

    # pylint: disable=too-many-arguments
    @pytest.mark.parametrize(
        "tpm_version_to_test, expected_firmware_name",
        [("tpm_v1_2", "itpm_v1_2.bit"), ("tpm_v1_6", "itpm_v1_6.bit")],
    )
    def test_firmware_version(
        self: TestStaticSimulator,
        tpm_version_to_test: str,
        expected_firmware_name: str,
        logger: logging.Logger,
        tile_id: int,
        station_id: int,
        callbacks: MockCallableGroup,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Test that the TileComponentManager will get the correct firmware bitfile.

        :param tpm_version_to_test: TPM version: "tpm_v1_2" or "tpm_v1_6"
        :param expected_firmware_name: the expected value of firmware_name
        :param logger: a object that implements the standard logging
            interface of :py:class:`logging.Logger`
        :param tile_id: the unique ID for the tile
        :param station_id: the ID of the station to which the tile belongs.
        :param callbacks: dictionary of driver callbacks.
        :param tile_simulator: The tile used by the TileComponentManager.
        """
        driver = TileComponentManager(
            SimulationMode.TRUE,
            TestMode.TEST,
            logger,
            0.1,
            tile_id,
            station_id,
            "tpm_ip",
            2,
            tpm_version_to_test,
            "dsd",
            2,
            callbacks["communication_status"],
            callbacks["component_state"],
            unittest.mock.Mock(),
        )

        assert driver.firmware_name == expected_firmware_name

    def test_initialise_beamformer_with_invalid_input(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Test initialise with a invalid value.

        :param tile_component_manager: The TileComponentManager instance.
        :param tile_simulator: The tile simulator instance.
        """
        # Arrange
        tile_simulator.connect()
        tile_simulator.set_first_last_tile = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )
        assert tile_simulator.tpm
        start_channel = 1  # This must be multiple of 2
        nof_channels = 8
        is_first = True
        is_last = True

        # Act
        tile_component_manager.initialise_beamformer(
            start_channel, nof_channels, is_first, is_last
        )

        # Assert values not written
        station_bf_1 = tile_simulator.tpm.station_beamf[0]
        station_bf_2 = tile_simulator.tpm.station_beamf[1]

        for table in station_bf_1._channel_table:
            assert table[0] != start_channel
            assert table[1] != nof_channels
        for table in station_bf_2._channel_table:
            assert table[0] != start_channel
            assert table[1] != nof_channels

        # Arrange
        start_channel = 2
        nof_channels = 9  # This must be multiple of 8
        is_first = True
        is_last = True

        # Act
        tile_component_manager.initialise_beamformer(
            start_channel, nof_channels, is_first, is_last
        )

        # Assert values not written
        station_bf_1 = tile_simulator.tpm.station_beamf[0]
        station_bf_2 = tile_simulator.tpm.station_beamf[1]

        for table in station_bf_1._channel_table:
            assert table[0] != start_channel
            assert table[1] != nof_channels
        for table in station_bf_2._channel_table:
            assert table[0] != start_channel
            assert table[1] != nof_channels

        tile_simulator.set_first_last_tile.assert_not_called()

    def test_initialise_beamformer(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the initialise_beamformer function.

        :param tile_component_manager: The TileComponentManager instance.
        :param tile_simulator: The tile simulator instance.
        """
        # Arrange
        tile_simulator.connect()
        assert tile_simulator.tpm
        start_channel = 2
        nof_channels = 8
        is_first = True
        is_last = True

        # Act
        tile_component_manager.initialise_beamformer(
            start_channel, nof_channels, is_first, is_last
        )

        # Assert
        station_bf_1 = tile_simulator.tpm.station_beamf[0]
        station_bf_2 = tile_simulator.tpm.station_beamf[1]

        num_blocks = nof_channels // 8
        for block, table in enumerate(station_bf_1._channel_table[0:num_blocks]):
            assert table == [start_channel + block * 8, 0, 0, block * 8, 0, 0, 0]
            assert len(table) < 8
        for table in station_bf_1._channel_table[num_blocks:]:
            assert table == [0, 0, 0, 0, 0, 0, 0]
        for block, table in enumerate(station_bf_2._channel_table[0:num_blocks]):
            assert table == [start_channel + block * 8, 0, 0, block * 8, 0, 0, 0]
        for table in station_bf_2._channel_table[num_blocks:]:
            assert table == [0, 0, 0, 0, 0, 0, 0]

        assert tile_simulator._is_first == is_first
        assert tile_simulator._is_last == is_last

    @pytest.mark.xfail(
        reason="Only the first element is sent to the tile_component_manager."
    )
    def test_csp_rounding(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the csp_rounding function.

        :param tile_component_manager: The TileComponentManager instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()

        assert tile_component_manager.csp_rounding == TileComponentManager.CSP_ROUNDING

        # ----------------------
        # Case: set with Integer
        # ----------------------
        tile_component_manager.csp_rounding = 3  # type: ignore[assignment]
        assert tile_simulator.csp_rounding == 3

        # ----------------------
        # Case: set with Integer
        # ----------------------
        tile_component_manager.csp_rounding = -3  # type: ignore[assignment]
        assert tile_simulator.csp_rounding == 0

    def test_pre_adu_levels(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the pre_adu_levels method.

        :param tile_component_manager: The TileComponentManager instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()
        assert tile_simulator.tpm

        # Set preADU levels to 3 for all channels
        tile_component_manager.set_preadu_levels([3.0] * 32)
        # Read PyFABIL software preADU levels for preADU 1, channel 1
        assert tile_simulator.tpm.preadu[1].get_attenuation()[1] == 3.00
        # Set preADU levels to 3 for all channels
        tile_component_manager.set_preadu_levels([4.0] * 32)
        assert tile_simulator.tpm.preadu[1].get_attenuation()[1] == 4.00
        # Try to set more levels (33) than there are channels (32),
        # in order to check that the TileComponentManager swallows exceptions.
        # Possibly a bad idea?
        tile_component_manager.set_preadu_levels([3.0] * 33)

    def test_load_calibration_coefficients(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the load_calibration_coefficients function.

        :param tile_component_manager: The TileComponentManager instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()
        tile_simulator.load_calibration_coefficients = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )

        tile_component_manager.load_calibration_coefficients(
            3, [[complex(3, 3), complex(4, 4), complex(5, 5)]]
        )
        tile_simulator.load_calibration_coefficients.assert_called_with(
            3, [[complex(3, 3), complex(4, 4), complex(5, 5)]]
        )

        # Check that thrown exception are caught when thrown.
        tile_simulator.load_calibration_coefficients.side_effect = Exception(
            "mocked exception"
        )
        tile_component_manager.load_calibration_coefficients(
            3, [[complex(3, 3), complex(4, 4), complex(5, 5)]]
        )

    @pytest.mark.xfail(reason="The parameter passed in is overwritten with 0")
    def test_apply_calibration(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the apply_calibration function.

        :param tile_component_manager: The TileComponentManager instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()
        tile_simulator.switch_calibration_bank = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )
        iso_date = datetime.datetime.now().isoformat()
        tile_component_manager.apply_calibration(iso_date)
        tile_simulator.switch_calibration_bank.assert_called_with(iso_date)

        # Check that thrown exception are caught when thrown.
        tile_simulator.switch_calibration_bank.side_effect = Exception(
            "mocked exception"
        )
        tile_component_manager.apply_calibration(iso_date)

    # pylint: disable=too-many-arguments
    @pytest.mark.parametrize(
        "delay_array, beam_index, expected_delay",
        [
            ([[0.0, 0.0]] * 16, 3, [[0.0, 0.0]] * 16),
            ([[0.0, 0.0]] * 10, 4, [[0.0, 0.0]] * 16),
        ],
    )
    def test_load_pointing_delays(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
        delay_array: list[list[float]],
        beam_index: int,
        expected_delay: float,
    ) -> None:
        """
        Unit test for the load_pointing_delays function.

        :param tile_component_manager: The TileComponentManager instance.
        :param tile_simulator: The tile simulator instance.
        :param delay_array: The array of pointing delays.
        :param beam_index: The index of the beam.
        :param expected_delay: The expected delay for the given beam index.
        """
        tile_simulator.connect()
        tile_simulator.set_pointing_delay = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )

        tile_component_manager.load_pointing_delays(delay_array, beam_index)
        tile_simulator.set_pointing_delay.assert_called_with(expected_delay, beam_index)

        # Check that thrown exception are caught when thrown.
        tile_simulator.set_pointing_delay.side_effect = Exception("mocked exception")
        tile_component_manager.load_pointing_delays(delay_array, beam_index)

    def test_apply_pointing_delays(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the apply_pointing_delays function.

        :param tile_component_manager: The TileComponentManager instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()
        tile_simulator.load_pointing_delay = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )

        tile_component_manager._tile_time.set_reference_time(int(time.time()))

        start_time = datetime.datetime.strftime(
            datetime.datetime.fromtimestamp(time.time() + 2.5), RFC_FORMAT
        )
        tile_component_manager.apply_pointing_delays(start_time)
        tile_simulator.load_pointing_delay.assert_called_with(Anything)

        # Check that thrown exception are caught when thrown.
        tile_simulator.load_pointing_delay.side_effect = Exception("mocked exception")
        tile_component_manager.apply_pointing_delays(start_time)

    def test_start_beamformer(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the start_beamformer function.

        :param tile_component_manager: The TileComponentManager instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()
        assert tile_simulator.tpm
        tile_simulator.tpm._is_programmed = True
        assert not tile_component_manager.is_beamformer_running
        tile_component_manager._tile_time.set_reference_time(int(time.time()))

        start_time = datetime.datetime.strftime(
            datetime.datetime.fromtimestamp(time.time() + 0.5), RFC_FORMAT
        )

        tile_component_manager.start_beamformer(start_time, 4)

        assert tile_component_manager.is_beamformer_running

        tile_simulator.start_beamformer = (  # type: ignore[assignment]
            unittest.mock.Mock(side_effect=Exception("mocked exception"))
        )

        tile_component_manager.start_beamformer(start_time, 4)

    def test_stop_beamformer(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the stop_beamformer function.

        :param tile_component_manager: The TileComponentManager instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()
        tile_simulator.stop_beamformer = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )

        tile_component_manager.stop_beamformer()
        tile_simulator.stop_beamformer.assert_called()

        # Check that thrown exception are caught when thrown.
        tile_simulator.stop_beamformer.side_effect = Exception("mocked exception")
        tile_component_manager.stop_beamformer()

    def test_configure_integrated_channel_data(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the configure_integrated_channel_data function.

        :param tile_component_manager: The TileComponentManager instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()
        tile_simulator.configure_integrated_channel_data = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )

        tile_component_manager.configure_integrated_channel_data(0.5, 2, 520)
        tile_simulator.configure_integrated_channel_data.assert_called_with(0.5, 2, 520)

        # Check that thrown exception are caught when thrown.
        tile_simulator.configure_integrated_channel_data.side_effect = Exception(
            "mocked exception"
        )
        tile_component_manager.configure_integrated_channel_data(0.5, 2, 520)

    def test_configure_integrated_beam_data(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the configure_integrated_beam_data function.

        :param tile_component_manager: The TileComponentManager instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()
        tile_simulator.configure_integrated_beam_data = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )

        tile_component_manager.configure_integrated_beam_data(0.5, 2, 520)
        tile_simulator.configure_integrated_beam_data.assert_called_with(0.5, 2, 520)

        # Check that thrown exception are caught when thrown.
        tile_simulator.configure_integrated_beam_data.side_effect = Exception(
            "mocked exception"
        )
        tile_component_manager.configure_integrated_beam_data(0.5, 2, 520)

    def test_stop_integrated_data(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the stop_integrated_data function.

        :param tile_component_manager: The TileComponentManager instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()
        tile_simulator.stop_integrated_data = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )

        tile_component_manager.stop_integrated_data()
        tile_simulator.stop_integrated_data.assert_called()

        # This just checks that if a exception is raised it is caught
        tile_simulator.stop_integrated_data.side_effect = Exception("mocked exception")
        tile_component_manager.stop_integrated_data()

    @pytest.mark.xfail(reason="Uncaught exception when unknown data_type given.")
    def test_send_data_samples(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the send_data_samples function.

        This function raises an uncaught exception if:
        - start_acquisition has not been called.
        - the timestamp is not far enough in the future.
        - an unknown data type is passed.
        :param tile_component_manager: The TileComponentManager instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()
        assert tile_component_manager.tile.is_programmed()

        mocked_input_params: dict[str, Any] = {
            "timestamp": time.time() + 40,
            "seconds": 0.2,
            "n_samples": 1024,
            "sync": False,
            "first_channel": 0,
            "last_channel": 511,
            "channel_id": 128,
            "frequency": 150.0e6,
            "round_bits": 3,
        }

        tile_simulator.send_raw_data = unittest.mock.Mock()  # type: ignore[assignment]
        tile_simulator.send_channelised_data = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )
        tile_simulator.send_channelised_data_continuous = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )
        tile_simulator.send_channelised_data_narrowband = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )
        tile_simulator.send_beam_data = unittest.mock.Mock()  # type: ignore[assignment]

        # we require start_acquisition to have been called before send_data_samples
        with pytest.raises(
            ValueError, match="Cannot send data before StartAcquisition"
        ):
            tile_component_manager.send_data_samples("raw", **mocked_input_params)

        start_time = str(time.time() + 3.0)
        tile_component_manager.start_acquisition(start_time=start_time, delay=1)

        # we require timestamp to be in future
        with pytest.raises(ValueError, match="Time is too early"):
            tile_component_manager.send_data_samples("raw", timestamp=1)

        tile_component_manager.send_data_samples("raw", **mocked_input_params)
        tile_simulator.send_raw_data.assert_called_with(
            sync=False,
            timestamp=mocked_input_params["timestamp"],
            seconds=mocked_input_params["seconds"],
        )

        tile_component_manager.send_data_samples("channel", **mocked_input_params)
        tile_simulator.send_channelised_data.assert_called_with(
            number_of_samples=mocked_input_params["n_samples"],
            first_channel=mocked_input_params["first_channel"],
            last_channel=mocked_input_params["last_channel"],
            timestamp=mocked_input_params["timestamp"],
            seconds=mocked_input_params["seconds"],
        )

        tile_component_manager.send_data_samples(
            "channel_continuous", **mocked_input_params
        )
        tile_simulator.send_channelised_data_continuous.assert_called_with(
            mocked_input_params["channel_id"],
            number_of_samples=mocked_input_params["n_samples"],
            wait_seconds=0,
            timestamp=mocked_input_params["timestamp"],
            seconds=mocked_input_params["seconds"],
        )

        tile_component_manager.send_data_samples("narrowband", **mocked_input_params)
        tile_simulator.send_channelised_data_narrowband.assert_called_with(
            mocked_input_params["frequency"],
            mocked_input_params["round_bits"],
            mocked_input_params["n_samples"],
            0,
            mocked_input_params["timestamp"],
            mocked_input_params["seconds"],
        )

        tile_component_manager.send_data_samples("beam", **mocked_input_params)
        tile_simulator.send_beam_data.assert_called_with(
            timestamp=mocked_input_params["timestamp"],
            seconds=mocked_input_params["seconds"],
        )

        # try to send a unknown data type
        # data_type = "unknown"
        # with pytest.raises(ValueError, match=f"Unknown sample type: {data_type}"):
        tile_component_manager.send_data_samples("unknown", **mocked_input_params)

        # Check that exceptions are caught.
        # -------------------------------------
        tile_simulator.send_raw_data.side_effect = Exception("mocked exception")
        tile_simulator.send_channelised_data.side_effect = Exception
        tile_simulator.send_channelised_data_continuous.side_effect = Exception
        tile_simulator.send_channelised_data_narrowband.side_effect = Exception(
            "mocked exception"
        )
        tile_simulator.send_beam_data.side_effect = Exception("mocked exception")

        tile_component_manager.send_data_samples("raw")
        tile_component_manager.send_data_samples("channel")
        tile_component_manager.send_data_samples("channel_continuous")
        tile_component_manager.send_data_samples("narrowband")
        tile_component_manager.send_data_samples("beam")
        # -------------------------------------

    def test_stop_data_transmission(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the stop_data_transmission function.

        :param tile_component_manager: The TileComponentManager instance.
        :param tile_simulator: The tile simulator instance.
        """
        # Arrange
        tile_simulator.connect()
        tile_simulator.stop_data_transmission = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )
        # Act
        tile_component_manager.stop_data_transmission()

        # Assert
        tile_simulator.stop_data_transmission.assert_called()

        # Check that exceptions are caught.
        tile_simulator.stop_data_transmission.side_effect = Exception(
            "mocked exception"
        )
        tile_component_manager.stop_data_transmission()

    def test_set_lmc_integrated_download(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the set_lmc_integrated_download function.

        :param tile_component_manager: The TileComponentManager instance.
        :param tile_simulator: The tile simulator instance.
        """
        # Arrange
        tile_simulator.connect()
        tile_simulator.set_lmc_integrated_download = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )
        mocked_input_params: dict[str, Any] = {
            "mode": "mode_1",
            "channel_payload_length": 4,
            "beam_payload_length": 1024,
            "dst_ip": "10.0.20.30",
            "src_port": 0,
            "dst_port": 511,
        }

        # Act
        tile_component_manager.set_lmc_integrated_download(**mocked_input_params)

        # Assert
        tile_simulator.set_lmc_integrated_download.assert_called_with(
            mocked_input_params["mode"],
            mocked_input_params["channel_payload_length"],
            mocked_input_params["beam_payload_length"],
            mocked_input_params["dst_ip"],
            mocked_input_params["src_port"],
            mocked_input_params["dst_port"],
            netmask_40g=None,
            gateway_ip_40g=None,
        )

        # Check that exceptions are caught.
        tile_simulator.set_lmc_integrated_download.side_effect = Exception(
            "mocked exception"
        )
        tile_component_manager.set_lmc_integrated_download(**mocked_input_params)

    def test_current_tile_beamformer_frame(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the current_tile_beamformer_frame function.

        :param tile_component_manager: The TileComponentManager instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()
        tile_simulator.current_tile_beamformer_frame = (  # type: ignore[assignment]
            unittest.mock.Mock(return_value=4)
        )

        _ = tile_component_manager.current_tile_beamformer_frame

        tile_simulator.current_tile_beamformer_frame.assert_called()
        assert tile_component_manager.current_tile_beamformer_frame == 4

        tile_simulator.current_tile_beamformer_frame.side_effect = Exception(
            "mocked exception"
        )
        with pytest.raises(Exception, match="mocked exception"):
            _ = tile_component_manager.current_tile_beamformer_frame

    def test_test_generator_active(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the test_generator_active function.

        :param tile_component_manager: The TileComponentManager instance.
        :param tile_simulator: The tile simulator instance.
        """
        # Arrange
        tile_simulator.connect()
        initial_test_generator_active = tile_component_manager._test_generator_active
        assert isinstance(tile_component_manager._test_generator_active, bool)
        assert (
            tile_component_manager.test_generator_active
            == initial_test_generator_active
        )

        # Act
        set_test_generator_active = not initial_test_generator_active
        tile_component_manager.test_generator_active = set_test_generator_active

        # Assert
        assert (
            initial_test_generator_active
            != tile_component_manager.test_generator_active
        )
        assert tile_component_manager.test_generator_active == set_test_generator_active

    def test_configure_test_generator(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the configure_test_generator function.

        :param tile_component_manager: The TileComponentManager instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()
        tile_component_manager._tile_time.set_reference_time(int(time.time()))
        mocked_input_params: dict[str, Any] = {
            "frequency0": 0.4,
            "amplitude0": 0.8,
            "frequency1": 0.8,
            "amplitude1": 0.1,
            "amplitude_noise": 0.9,
            "pulse_code": 2,
            "amplitude_pulse": 0.7,
            "load_time": datetime.datetime.fromtimestamp(time.time() + 2).strftime(
                "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
        }

        tile_simulator.test_generator_set_tone = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )
        tile_simulator.test_generator_set_noise = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )
        tile_simulator.set_test_generator_pulse = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )

        tile_component_manager.configure_test_generator(**mocked_input_params)
        tile_simulator.test_generator_set_tone.assert_called_with(
            1,
            mocked_input_params["frequency1"],
            mocked_input_params["amplitude1"],
            0.0,
            Anything,
        )
        tile_simulator.test_generator_set_noise.assert_called_with(
            mocked_input_params["amplitude_noise"], Anything
        )
        tile_simulator.set_test_generator_pulse.assert_called_with(
            mocked_input_params["pulse_code"], mocked_input_params["amplitude_pulse"]
        )

        # Check that any exceptions thrown are caught.
        tile_simulator.test_generator_set_tone.side_effect = Exception(
            "mocked exception"
        )
        tile_component_manager.configure_test_generator(**mocked_input_params)

    def test_test_generator_input_select(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the test_generator_input_select function.

        :param tile_component_manager: The TileComponentManager instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()

        tile_simulator.test_generator_input_select = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )

        tile_component_manager.test_generator_input_select(5)
        tile_simulator.test_generator_input_select.assert_called_with(5)

        tile_simulator.test_generator_input_select.side_effect = Exception(
            "mocked exception"
        )
        with pytest.raises(Exception, match="mocked exception"):
            tile_component_manager.test_generator_input_select(5)

    def test_set_lmc_download(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the set_lmc_download function.

        :param tile_component_manager: The TileComponentManager instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()

        tile_simulator.set_lmc_download = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )
        mocked_input_params: dict[str, Any] = {
            "mode": "mode_1",
            "payload_length": 1024,
            "dst_ip": "10.2.2.14",
            "src_port": 4660,
            "dst_port": 4660,
        }
        tile_component_manager.set_lmc_download(**mocked_input_params)
        tile_simulator.set_lmc_download.assert_called_once_with(
            mocked_input_params["mode"],
            mocked_input_params["payload_length"],
            mocked_input_params["dst_ip"],
            mocked_input_params["src_port"],
            mocked_input_params["dst_port"],
            netmask_40g=None,
            gateway_ip_40g=None,
        )

        # Check that a raised exception is caught.
        tile_simulator.set_lmc_download.side_effect = Exception("Mocked exception")
        tile_component_manager.set_lmc_download(**mocked_input_params)

    def test_arp_table(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the arp_table function.

        :param tile_component_manager: The TileComponentManager instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()

        tile_simulator.get_arp_table = unittest.mock.Mock()  # type: ignore[assignment]

        _ = tile_component_manager.arp_table
        tile_simulator.get_arp_table.assert_called_once()

    def test_fpga_current_frame(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the fpga_current_frame function.

        :param tile_component_manager: The TileComponentManager instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()

        tile_simulator.get_fpga_timestamp = (  # type: ignore[assignment]
            unittest.mock.Mock(return_value=4)
        )

        _ = tile_component_manager.fpga_current_frame
        tile_simulator.get_fpga_timestamp.assert_called_once()
        assert tile_component_manager._fpga_current_frame == 4

        # Check that a exception is not caught.
        # TODO: validate this is expected behaviour
        tile_simulator.get_fpga_timestamp.return_value = 5
        tile_simulator.get_fpga_timestamp.side_effect = Exception("Mocked exception")
        with pytest.raises(ConnectionError, match="Cannot read time from FPGA"):
            _ = tile_component_manager.fpga_current_frame

        # check not updated if failed.
        assert tile_component_manager._fpga_current_frame != 5

    def test_configure_40g_core(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the configure_40g_core function.

        :param tile_component_manager: The TileComponentManager instance.
        :param tile_simulator: The tile simulator instance.
        """
        # mocked connection to the TPM simuator.
        tile_simulator.connect()

        tile_simulator.configure_40g_core = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )

        core_dict: dict[str, Any] = {
            "core_id": 0,
            "arp_table_entry": 1,
            "src_mac": 0x14109FD4041A,
            "src_ip": "3221226219",
            "src_port": 8080,
            "dst_ip": "3221226219",
            "dst_port": 9000,
            "rx_port_filter": None,
            "netmask": None,
            "gateway_ip": None,
        }

        tile_component_manager.configure_40g_core(**core_dict)
        tile_simulator.configure_40g_core.assert_called_once_with(
            core_dict["core_id"],
            core_dict["arp_table_entry"],
            core_dict["src_mac"],
            core_dict["src_ip"],
            core_dict["src_port"],
            core_dict["dst_ip"],
            core_dict["dst_port"],
            core_dict["rx_port_filter"],
            core_dict["netmask"],
            core_dict["gateway_ip"],
        )
        # Check that exceptions raised are caught.
        tile_simulator.configure_40g_core.side_effect = Exception("Mocked exception")
        tile_component_manager.configure_40g_core(**core_dict)

    @pytest.mark.xfail(
        reason="A default dictionary is returned even when exception is thrown"
    )
    def test_get_40g_configuration(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the get_40g_configuration function.

        :param tile_component_manager: The TileComponentManager instance.
        :param tile_simulator: The tile simulator instance.
        """
        core_dict: dict[str, Any] = {
            "core_id": 0,
            "arp_table_entry": 1,
            "src_mac": 0x14109FD4041A,
            "src_ip": "3221226219",
            "src_port": 8080,
            "dst_ip": "3221226219",
            "dst_port": 9000,
            "rx_port_filter": None,
            "netmask": None,
            "gateway_ip": None,
        }

        tile_simulator.connect()
        tile_simulator.get_40g_core_configuration = (  # type: ignore[assignment]
            unittest.mock.Mock(return_value=core_dict)
        )

        tile_component_manager.get_40g_configuration(
            core_id=core_dict["core_id"], arp_table_entry=core_dict["arp_table_entry"]
        )
        tile_simulator.get_40g_core_configuration.assert_called_once_with(
            core_dict["core_id"], core_dict["arp_table_entry"]
        )
        assert tile_component_manager._forty_gb_core_list == [core_dict]

        tile_component_manager.get_40g_configuration(core_id=-1, arp_table_entry=0)
        # We should get all the configurations for both cores and arp table entries
        # these are all mocked to return same thing.
        assert tile_component_manager._forty_gb_core_list == [
            core_dict,
            core_dict,
            core_dict,
            core_dict,
        ]

        # Check that exceptions raised are caught.
        tile_simulator.get_40g_core_configuration.return_value = None
        tile_simulator.get_40g_core_configuration.side_effect = Exception(
            "Mocked exception"
        )

        with pytest.raises(KeyError, match="src_ip"):
            tile_component_manager.get_40g_configuration(
                core_id=core_dict["core_id"],
                arp_table_entry=core_dict["arp_table_entry"],
            )

        assert tile_component_manager._forty_gb_core_list == [core_dict]

    def test_channeliser_truncation(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the channeliser_truncation function.

        :param tile_component_manager: The TileComponentManager instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()
        tile_simulator.set_channeliser_truncation = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )

        # call with a single value.
        tile_component_manager.channeliser_truncation = 2  # type: ignore
        assert tile_component_manager._channeliser_truncation == [2] * 512
        tile_simulator.set_channeliser_truncation.assert_called_with([2] * 512, 31)

        # call with a single value in a list.
        tile_component_manager.channeliser_truncation = [3]
        assert tile_component_manager._channeliser_truncation == [3] * 512
        tile_simulator.set_channeliser_truncation.assert_called_with([3] * 512, 31)

        # call with subset of values
        tile_component_manager.channeliser_truncation = [3] * 100
        assert tile_component_manager.channeliser_truncation == [3] * 100
        tile_simulator.set_channeliser_truncation.assert_called_with(
            [3] * 100 + [0] * 412, 31
        )

        # Check that expections are caught at this level.
        tile_simulator.set_channeliser_truncation.side_effect = Exception(
            "Mocked exception"
        )
        tile_component_manager.channeliser_truncation = [3] * 100

    @pytest.mark.xfail(reason="Uncaught exception")
    def test_fpgas_time(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the fpgas_time function.

        :param tile_component_manager: The TileComponentManager instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()

        tile_simulator.get_fpga_time = unittest.mock.Mock()  # type: ignore[assignment]

        # Try to get Fpga time without programmed
        tile_component_manager.tile._is_programmed = False
        tile_simulator.get_fpga_time.assert_not_called()
        assert tile_component_manager.fpgas_time == [0, 0]

        # Try to get Fpga time when programmed
        assert tile_component_manager.tile.is_programmed()
        _ = tile_component_manager.fpgas_time
        tile_simulator.get_fpga_time.assert_called()

        # Check no exception is thrown.
        tile_simulator.get_fpga_time.side_effect = Exception("Mocked exception")
        _ = tile_component_manager.fpgas_time

    @pytest.mark.parametrize(
        ("attribute"),
        [
            ("register_list"),
            ("station_id"),
            ("tile_id"),
            ("is_programmed"),
            ("firmware_version"),
            ("firmware_name"),
            ("firmware_available"),
            ("hardware_version"),
            ("tpm_status"),
            ("fpgas_time"),
            ("fpga_reference_time"),
            ("fpga_current_frame"),
            ("pps_delay"),
            ("arp_table"),
            ("channeliser_truncation"),
            ("get_static_delays"),
            ("csp_rounding"),
            ("pps_present"),
            ("current_tile_beamformer_frame"),
            ("is_beamformer_running"),
            ("pending_data_requests"),
            ("test_generator_active"),
        ],
    )
    def test_dumb_read(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
        attribute: str,
    ) -> None:
        """
        Test the dumb read functionality.

        Validate that it can be called without error.

        :param tile_simulator: An hardware tile_simulator mock
        :param tile_component_manager: The TileComponentManager instance being tested.
        :param attribute: The attribute to be read.
        """
        tile_simulator.connect()
        _ = getattr(tile_component_manager, attribute)

    def test_update_pending_data_requests(
        self: TestStaticSimulator,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
        callbacks: MockCallableGroup,
    ) -> None:
        """
        Test stopping data transmission updates the pending data requests.

        :param tile_component_manager: The tile_component_manager under test.
        :param tile_simulator: The mocked tile_simulator
        :param callbacks: dictionary of driver callbacks.
        """
        tile_simulator.connect()
        assert tile_simulator.tpm is not None
        assert tile_component_manager.tile.is_programmed()
        assert tile_component_manager.tpm_status == TpmStatus.INITIALISED
        tile_simulator.tpm._is_programmed = True
        tile_simulator._is_programmed = True

        assert tile_component_manager.pending_data_requests is False

        tile_simulator._pending_data_requests = True

        assert tile_component_manager.pending_data_requests is True

        tile_component_manager.stop_data_transmission()

        assert tile_component_manager.pending_data_requests is False


class TestDynamicSimulator:
    """Class for testing using the DynamicTileSimulator as a backend."""

    @pytest.fixture()
    def test_mode(self: TestDynamicSimulator) -> TestMode:
        """
        Return the test mode to be used when initialising the tile_component_manager.

        :return: the test mode to be used when initialising the tile_component_manager
            class object.
        """
        return TestMode.NONE

    @pytest.fixture()
    def initial_tpm_power_state(
        self: TestDynamicSimulator,
    ) -> PowerState:
        """
        Return the initial power mode of the TPM.

        Overridden here to put the TPM into ON state, so that we don't
        have to fiddle around with state change events to get the tile_component_manager
        component manager communicating with its tile_component_manager.

        :return: the initial power mode of the TPM.
        """
        return PowerState.ON

    @pytest.fixture()
    def tile_component_manager(
        self: TestDynamicSimulator,
        dynamic_tile_component_manager: TileComponentManager,
        callbacks: MockCallableGroup,
    ) -> TileComponentManager:
        """
        Return the tile_component_manager component under test.

        :param dynamic_tile_component_manager: the tile_component_manager
            component manager (Driving a DynamicTileSimulator)
        :param callbacks: dictionary of driver callbacks.

        :return: the tile_component_manager class object under test
        """
        # pylint: disable=attribute-defined-outside-init
        self.tile_name = "tile_component_manager"

        dynamic_tile_component_manager.start_communicating()
        callbacks["communication_status"].assert_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)
        dynamic_tile_component_manager.on(task_callback=callbacks["task"])
        callbacks["component_state"].assert_call(power=PowerState.ON, lookahead=2)

        callbacks["component_state"].assert_call(
            programming_state=TpmStatus.UNPROGRAMMED.pretty_name(), lookahead=2
        )
        callbacks["task"].assert_call(status=TaskStatus.QUEUED)
        callbacks["task"].assert_call(status=TaskStatus.IN_PROGRESS)
        callbacks["task"].assert_call(
            status=TaskStatus.COMPLETED,
            result=(ResultCode.OK, "Command executed to completion."),
        )
        callbacks["component_state"].assert_call(
            programming_state=TpmStatus.INITIALISED.pretty_name(), lookahead=2
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
        self: TestDynamicSimulator,
        tile_component_manager: TileComponentManager,
        attribute_name: str,
    ) -> None:
        """
        Tests that dynamic attributes can be read.

        Check that they are NOT equal to the
        static value assigned in the static dynamic simulator.

        :param tile_component_manager: the tile_component_manager
            class object under test.
        :param attribute_name: the name of the attribute under test
        """
        attribute_value = getattr(tile_component_manager, attribute_name)
        assert attribute_value is not None
        time.sleep(8.1)
        new_attribute_value = getattr(tile_component_manager, attribute_name)
        assert new_attribute_value is not None
        assert new_attribute_value != attribute_value

    @pytest.mark.parametrize(
        ("attribute_name", "expected_value"),
        (
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
        self: TestDynamicSimulator,
        tile_component_manager: TileComponentManager,
        attribute_name: str,
        expected_value: Any,
    ) -> None:
        """
        Tests that read-only attributes take certain known initial values.

        This test covers attributes that have not been made dynamic yet.

        :param tile_component_manager: the tile_component_manager class
            object under test.
        :param attribute_name: the name of the attribute under test
        :param expected_value: the expected value of the attribute. This
            can be any type, but the test of the attribute is a single
            "==" equality test.
        """
        time.sleep(0.1)
        assert getattr(tile_component_manager, attribute_name) == expected_value
