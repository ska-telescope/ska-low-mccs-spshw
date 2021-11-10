# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
#########################################################################
"""This module contains the tests of the tile component manage."""
from __future__ import annotations

from enum import IntEnum
import time
from typing import Any, Union
import unittest.mock

import pytest
import pytest_mock
from _pytest.fixtures import SubRequest
import tango

from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import PowerMode, SimulationMode, TestMode

from ska_low_mccs.component import CommunicationStatus
from ska_low_mccs.tile import (
    DynamicTpmSimulator,
    StaticTpmSimulator,
    TpmDriver,
    DynamicTpmSimulatorComponentManager,
    StaticTpmSimulatorComponentManager,
    SwitchingTpmComponentManager,
    TileComponentManager,
)
from ska_low_mccs.tile.tile_component_manager import _SubrackProxy

from ska_low_mccs.testing.mock import MockCallable


class TestTileSubrackProxy:
    """Tests of the _SubrackProxy class."""

    def test_communication(
        self: TestTileSubrackProxy,
        tile_subrack_proxy: _SubrackProxy,
        communication_status_changed_callback: MockCallable,
    ) -> None:
        """
        Test this tile subrack proxy's communication with the tile.

        :param tile_subrack_proxy: a proxy to the tile's subrack device.
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        """
        assert tile_subrack_proxy.communication_status == CommunicationStatus.DISABLED
        tile_subrack_proxy.start_communicating()
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.ESTABLISHED
        )
        assert (
            tile_subrack_proxy.communication_status == CommunicationStatus.ESTABLISHED
        )

        tile_subrack_proxy.stop_communicating()
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.DISABLED
        )
        assert tile_subrack_proxy.communication_status == CommunicationStatus.DISABLED

    def test_power_command(
        self: TestTileSubrackProxy,
        tile_subrack_proxy: _SubrackProxy,
        mock_subrack_device_proxy: unittest.mock.Mock,
        subrack_tpm_id: int,
    ) -> None:
        """
        Test that this tile subrack proxy can control the power mode of the tile.

        :param tile_subrack_proxy: a proxy to the tile's subrack device.
        :param mock_subrack_device_proxy: a mock device proxy to an subrack
            device.
        :param subrack_tpm_id: the id of the tile in its subrack
            device.
        """
        with pytest.raises(
            ConnectionError,
            match="Not connected",
        ):
            tile_subrack_proxy.on()

        assert tile_subrack_proxy.power_mode is None

        tile_subrack_proxy.start_communicating()
        time.sleep(0.1)
        # communication_status is ESTABLISHED because MccsSubrack's
        # state is OFF, from which it can be inferred that the tile
        # itself is powered off.
        assert tile_subrack_proxy.power_mode == PowerMode.OFF
        assert tile_subrack_proxy.tpm_power_mode is None

        tile_subrack_proxy.on()
        mock_subrack_device_proxy.On.assert_next_call()

        # Fake an event that tells this proxy that the subrack has been turned on.
        tile_subrack_proxy._device_state_changed(
            "state", tango.DevState.ON, tango.AttrQuality.ATTR_VALID
        )
        assert tile_subrack_proxy.power_mode == PowerMode.ON
        assert tile_subrack_proxy.tpm_power_mode is None

        time.sleep(0.1)
        assert tile_subrack_proxy.power_on() == ResultCode.QUEUED
        mock_subrack_device_proxy.PowerOnTpm.assert_next_call(subrack_tpm_id)

        # The tile power mode won't update until an event confirms that the tile is on.
        assert tile_subrack_proxy.tpm_power_mode == PowerMode.OFF

        # Fake an event that tells this proxy that the tile is now on as requested
        tile_subrack_proxy._tpm_power_mode_changed(
            "areTpmsOn", [True, True, True], tango.AttrQuality.ATTR_VALID
        )
        assert tile_subrack_proxy.tpm_power_mode == PowerMode.ON

        assert tile_subrack_proxy.power_on() is None
        mock_subrack_device_proxy.PowerOnTpm.assert_not_called()
        assert tile_subrack_proxy.tpm_power_mode == PowerMode.ON

        assert tile_subrack_proxy.power_off() == ResultCode.QUEUED
        mock_subrack_device_proxy.PowerOffTpm.assert_next_call(subrack_tpm_id)

        # The power mode won't update until an event confirms that the tile is on.
        assert tile_subrack_proxy.tpm_power_mode == PowerMode.ON

        # Fake an event that tells this proxy that the tile is now off as requested
        tile_subrack_proxy._tpm_power_mode_changed(
            "areTpmsOn", [False, True, True], tango.AttrQuality.ATTR_VALID
        )
        assert tile_subrack_proxy.tpm_power_mode == PowerMode.OFF

        assert tile_subrack_proxy.power_off() is None
        mock_subrack_device_proxy.PowerOffTpm.assert_not_called()
        assert tile_subrack_proxy.tpm_power_mode == PowerMode.OFF


class TestTileComponentManager:
    """
    Class for testing the tile component manager.

    Many of its methods and properties map to the underlying TPM
    simulator or driver, and these are tested in the class below. Here,
    we just perform tests of functionality in the tile component manager
    itself.
    """

    class Case(IntEnum):
        """Component manager states from which we might want to run test cases."""

        ONLINE = 1
        """The component manager is online, it doesn't yet know the subrack state."""

        SUBRACK_OFF = 2
        """The subrack is off."""

        SUBRACK_ON = 3
        """The subrack is on, but we don't yet know the state of the TPM."""

        TPM_OFF = 4
        """The subrack is on, the TPM is off."""

        TPM_ON = 5
        """The TPM is on."""

    @pytest.mark.parametrize("case", list(Case))
    def test_communication(
        self: TestTileComponentManager,
        tile_component_manager: TileComponentManager,
        communication_status_changed_callback: MockCallable,
        case: TestTileComponentManager.Case,
    ) -> None:
        """
        Test communication between the tile component manager and its tile.

        :param tile_component_manager: the tile component manager
            under test
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param case: a subcase of this test: a specific state for the
            tile component manager to be in when we take it offline
        """
        assert (
            tile_component_manager.communication_status == CommunicationStatus.DISABLED
        )

        tile_component_manager.start_communicating()

        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.ESTABLISHED
        )

        assert (
            tile_component_manager.communication_status
            == CommunicationStatus.ESTABLISHED
        )

        if case == TestTileComponentManager.Case.ONLINE:
            pass
        elif case == TestTileComponentManager.Case.SUBRACK_OFF:
            tile_component_manager._subrack_power_mode_changed(PowerMode.OFF)
        elif case == TestTileComponentManager.Case.SUBRACK_ON:
            tile_component_manager._subrack_power_mode_changed(PowerMode.ON)
        elif case == TestTileComponentManager.Case.TPM_OFF:
            tile_component_manager._subrack_power_mode_changed(PowerMode.ON)
            tile_component_manager.component_power_mode_changed(PowerMode.OFF)
        elif case == TestTileComponentManager.Case.TPM_ON:
            tile_component_manager._subrack_power_mode_changed(PowerMode.ON)
            tile_component_manager.component_power_mode_changed(PowerMode.ON)
            communication_status_changed_callback.assert_next_call(
                CommunicationStatus.NOT_ESTABLISHED
            )
            communication_status_changed_callback.assert_next_call(
                CommunicationStatus.ESTABLISHED
            )

        tile_component_manager.stop_communicating()

        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.DISABLED
        )
        assert (
            tile_component_manager.communication_status == CommunicationStatus.DISABLED
        )

    @pytest.mark.parametrize(
        "case",
        [
            Case.SUBRACK_ON,
            Case.TPM_OFF,
            Case.TPM_ON,
        ],
    )
    def test_subrack_off(
        self: TestTileComponentManager,
        tile_component_manager: TileComponentManager,
        communication_status_changed_callback: MockCallable,
        case: TestTileComponentManager.Case,
    ) -> None:
        """
        Test handling of notification that the subrack is off.

        :param tile_component_manager: the tile component manager
            under test
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param case: a subcase of this test: a specific state for the
            tile component manager to be in when it is notified that the
            subrack is off
        """
        assert (
            tile_component_manager.communication_status == CommunicationStatus.DISABLED
        )

        tile_component_manager.start_communicating()

        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.ESTABLISHED
        )

        assert (
            tile_component_manager.communication_status
            == CommunicationStatus.ESTABLISHED
        )

        tile_component_manager._subrack_power_mode_changed(PowerMode.ON)

        if case == TestTileComponentManager.Case.SUBRACK_ON:
            pass
        elif case == TestTileComponentManager.Case.TPM_OFF:
            tile_component_manager.component_power_mode_changed(PowerMode.OFF)
        elif case == TestTileComponentManager.Case.TPM_ON:
            tile_component_manager.component_power_mode_changed(PowerMode.ON)
            communication_status_changed_callback.assert_next_call(
                CommunicationStatus.NOT_ESTABLISHED
            )
            communication_status_changed_callback.assert_next_call(
                CommunicationStatus.ESTABLISHED
            )

        tile_component_manager._subrack_power_mode_changed(PowerMode.OFF)

    def test_off_on(
        self: TestTileComponentManager,
        tile_component_manager: TileComponentManager,
        communication_status_changed_callback: MockCallable,
        subrack_tpm_id: int,
        mock_subrack_device_proxy: unittest.mock.Mock,
    ) -> None:
        """
        Test that we can turn the TPM on and off when the subrack is on.

        :param tile_component_manager: the tile component manager
            under test
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param subrack_tpm_id: This tile's position in its subrack
        :param mock_subrack_device_proxy: a mock device proxy to a
            subrack device.
        """
        tile_component_manager.start_communicating()

        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.ESTABLISHED
        )

        tile_component_manager._subrack_power_mode_changed(PowerMode.ON)
        tile_component_manager.component_power_mode_changed(PowerMode.OFF)

        tile_component_manager.on()
        mock_subrack_device_proxy.PowerOnTpm.assert_next_call(subrack_tpm_id)
        tile_component_manager.component_power_mode_changed(PowerMode.ON)

        tile_component_manager.off()
        mock_subrack_device_proxy.PowerOffTpm.assert_next_call(subrack_tpm_id)
        tile_component_manager.component_power_mode_changed(PowerMode.OFF)

    def test_eventual_consistency_of_on_command(
        self: TestTileComponentManager,
        tile_component_manager: TileComponentManager,
        communication_status_changed_callback: MockCallable,
        subrack_tpm_id: int,
        mock_subrack_device_proxy: unittest.mock.Mock,
    ) -> None:
        """
        Test that eventual consistency semantics of the on command.

        This test tells the tile component manager to turn on, in
        circumstances in which it cannot possibly do so (the subrack is
        turned off). Instead of failing, it waits to the subrack to turn
        on, and then executes the on command.

        :param tile_component_manager: the tile component manager
            under test
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param subrack_tpm_id: This tile's position in its subrack
        :param mock_subrack_device_proxy: a mock device proxy to a
            subrack device.
        """
        with pytest.raises(ConnectionError, match="Not connected"):
            tile_component_manager.on()

        tile_component_manager.start_communicating()

        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.ESTABLISHED
        )

        assert tile_component_manager.on() == ResultCode.QUEUED

        # no action taken initialially because the subrack is switched off
        mock_subrack_device_proxy.PowerOnTpm.assert_not_called()

        tile_component_manager._subrack_power_mode_changed(PowerMode.ON)

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
    def initial_subrack_state(self: TestStaticSimulatorCommon) -> tango.DevState:
        """
        Return the state in which the mock subrack should start.

        Overridden here to put the subrack into ON state, so that we
        don't have to fiddle around with state change events to get the
        tile component manager communicating with its tile.

        :return: the state in which the mock subrack should start.
        """
        return tango.DevState.ON

    @pytest.fixture()
    def initial_tpm_power_mode(self: TestStaticSimulatorCommon) -> PowerMode:
        """
        Return the initial power mode of the TPM.

        Overridden here to put the TPM into ON state, so that we don't
        have to fiddle around with state change events to get the tile
        component manager communicating with its tile.

        :return: the initial power mode of the TPM.
        """
        return PowerMode.ON

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
        communication_status_changed_callback: MockCallable,
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
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param request: A pytest object giving access to the requesting test
            context.

        :raises ValueError:if fixture is parametrized with unrecognised
            option

        :return: the tile class object under test
        """
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
            communication_status_changed_callback.assert_next_call(
                CommunicationStatus.NOT_ESTABLISHED
            )
            communication_status_changed_callback.assert_next_call(
                CommunicationStatus.ESTABLISHED
            )
            time.sleep(0.1)
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
            ("arp_table", StaticTpmSimulator.ARP_TABLE),
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
        assert getattr(tile, attribute_name) == expected_value

    @pytest.mark.parametrize(
        ("attribute_name", "initial_value", "values_to_write"),
        (("phase_terminal_count", StaticTpmSimulator.PHASE_TERMINAL_COUNT, [1, 2]),),
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
        assert getattr(tile, attribute_name) == initial_value

        for value in values_to_write:
            setattr(tile, attribute_name, value)
            assert getattr(tile, attribute_name) == value

    @pytest.mark.parametrize(
        ("command_name", "num_args"),
        (
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
            ("start_acquisition", 0),
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
        mocker: pytest_mock.mocker,
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
        args = [mocker.Mock()] * num_args
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
        assert not tile.is_programmed
        tile.initialise()
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
        mocker: pytest_mock.mocker,
    ) -> None:
        """
        Test.

        Tests that:
        * the download_firmware command.
        * the is_programmed attribute

        :param tile: the tile class object under test.
        :param mocker: fixture that wraps unittest.mock
        """
        assert not tile.is_programmed
        mock_bitfile = mocker.Mock()
        tile.download_firmware(mock_bitfile)
        assert tile.is_programmed

    @pytest.mark.skip(reason="Overparametrized; takes forever for little benefit")
    @pytest.mark.parametrize("device", (0, 1))
    @pytest.mark.parametrize("register", [f"test-reg{i}" for i in (1, 4)])
    @pytest.mark.parametrize("read_offset", (0, 2))
    @pytest.mark.parametrize("read_length", (0, 4))
    @pytest.mark.parametrize("write_offset", (0, 3))
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

    @pytest.mark.skip(reason="Overparametrized; takes forever for little benefit")
    @pytest.mark.parametrize("write_address", [9, 11])
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
        assert tile.get_40g_configuration(9) is None

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
            "CoreID": 2,
            "ArpTableEntry": 1,
            "SrcMac": "mock_src_mac",
            "SrcIP": "mock_src_ip",
            "SrcPort": 8888,
            "DstIP": "mock_dst_ip",
            "DstPort": 3333,
        }

        assert tile.get_40g_configuration(-1, 0) == [expected]
        assert tile.get_40g_configuration(2) == expected
        assert tile.get_40g_configuration(10) is None


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
    def initial_subrack_state(self: TestDynamicSimulatorCommon) -> tango.DevState:
        """
        Return the state in which the mock subrack should start.

        Overridden here to put the subrack into ON state, so that we
        don't have to fiddle around with state change events to get the
        tile component manager communicating with its tile.

        :return: the state in which the mock subrack should start.
        """
        return tango.DevState.ON

    @pytest.fixture()
    def initial_tpm_power_mode(self: TestDynamicSimulatorCommon) -> PowerMode:
        """
        Return the initial power mode of the TPM.

        Overridden here to put the TPM into ON state, so that we don't
        have to fiddle around with state change events to get the tile
        component manager communicating with its tile.

        :return: the initial power mode of the TPM.
        """
        return PowerMode.ON

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
            ("arp_table", DynamicTpmSimulator.ARP_TABLE),
            ("register_list", list(DynamicTpmSimulator.REGISTER_MAP[0].keys())),
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

    @pytest.fixture(
        params=[
            "tpm_driver",
            "switching_tpm_component_manager",
        ]
    )
    def tile(
        self: TestDriverCommon,
        tpm_driver: TpmDriver,
        switching_tpm_component_manager: SwitchingTpmComponentManager,
        request: SubRequest,
    ) -> Union[TpmDriver, SwitchingTpmComponentManager]:
        """
        Return the tile component under test.

        This is parametrised to return

        * a TPM driver,

        * a component manager that can switch between TPM simulator and
          TPM driver.

        So any test that relies on this fixture will be run twice.

        :param tpm_driver: the TPM driver
        :param switching_tpm_component_manager: the component manager
            that switches between TPM simulator and TPM driver to return
        :param request: A pytest object giving access to the requesting test
            context.

        :raises ValueError: if parametrized with an unrecognised option

        :return: the tile class object under test
        """
        if request.param == "tpm_driver":
            return tpm_driver
        elif request.param == "switching_tpm_component_manager":
            return switching_tpm_component_manager
        raise ValueError("Tile fixture parametrized with unrecognised option")

    def test_communication_fails(
        self: TestDriverCommon, tile: Union[TpmDriver, SwitchingTpmComponentManager]
    ) -> None:
        """
        Test was can create the driver but not start communication with the component.

        We can create the tile class object under test, but will not be
        able to use it to establish communication with the component
        (which is a hardware TPM that does not exist in this test
        harness).

        :param tile: the tile class object under test.
        """
        assert tile.communication_status == CommunicationStatus.DISABLED
        tile.start_communicating()
        assert tile.communication_status == CommunicationStatus.NOT_ESTABLISHED
        time.sleep(0.1)
        assert tile.communication_status == CommunicationStatus.NOT_ESTABLISHED
