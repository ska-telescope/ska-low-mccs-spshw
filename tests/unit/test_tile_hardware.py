#########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
#########################################################################
"""
This module contains the tests of the tile hardware, including the
TileHardwareManager class and the TpmSimulator. When we eventually have
a TpmDriver that drives real hardware, this module could also be used to
test that.
"""
import logging
from unittest.mock import Mock

import pytest

from ska.base.control_model import SimulationMode
from ska.low.mccs.tile import TileHardwareManager, TpmSimulator


@pytest.fixture()
def tpm_simulator():
    """
    Fixture that returns a TPM simulator

    :return: a TPM simulator
    :rtype: :py:class:`ska.low.mccs.tile.tpm_simulator.TpmSimulator`
    """
    return TpmSimulator(logger=logging.getLogger())


@pytest.fixture()
def tile_hardware_manager():
    """
    Fixture that returns a hardware manager for the MCCS tile device, in
    hardware simulation mode

    :return: a hardware manager for the MCCS tile device, in hardware
        simulation mode
    :rtype: TileHardwareManager
    """
    return TileHardwareManager(
        simulation_mode=SimulationMode.TRUE, logger=logging.getLogger()
    )


class TestTileHardwareManager:
    """
    Contains tests specific to TileHardwareManager
    """

    def test_init_simulation_mode(self):
        """
        Test that we can't create an hardware manager that isn't in
        simulation mode
        """
        with pytest.raises(
            NotImplementedError, match=("._create_driver method not implemented.")
        ):
            _ = TileHardwareManager(SimulationMode.FALSE, logger=logging.getLogger())

    def test_simulation_mode(self, tile_hardware_manager):
        """
        Test that we can't take the tile hardware manager out of
        simulation mode

        :param tile_hardware_manager: a manager for tile hardware
        :type tile_hardware_manager:
            :py:class:`~ska.low.mccs.tile.tile_hardware.TileHardwareManager`
        """
        with pytest.raises(
            NotImplementedError, match=("._create_driver method not implemented.")
        ):
            tile_hardware_manager.simulation_mode = SimulationMode.FALSE


class TestCommon:
    """
    Because the TileHardwareManager is designed to pass commands through
    to the TpmSimulator or TpmDriver that it is driving, many commands
    are common to TileHardwareManager and TpmSimulator, and they will
    also be common to the TpmDriver when we eventually implement it.
    Therefore this class contains common tests, parametrised to test
    against each class
    """

    @pytest.fixture(params=["tpm_simulator", "tile_hardware_manager"])
    def hardware_under_test(self, tpm_simulator, tile_hardware_manager, request):
        """
        Return the hardware under test. This is parametrised to return
        both a TPM simulator and a tile hardware manager, so any test
        that relies on this fixture will be run twice: once for each
        hardware type.

        :param tpm_simulator: the TPM simulator to return
        :type tpm_simulator:
            :py:class:`~ska.low.mccs.tile.tpm_simulator.TpmSimulator`
        :param tile_hardware_manager: the tile hardware manager to
            return
        :type tile_hardware_manager:
            :py:class:`~ska.low.mccs.tile.tile_hardware.TileHardwareManager`
        :param request: A pytest object giving access to the requesting test
            context.
        :type request: :py:class:`_pytest.fixtures.SubRequest`

        :return: the hardware under test: a tile hardware manager or a
            TPM simulator
        :rtype: object
        """
        if request.param == "tpm_simulator":
            return tpm_simulator
        elif request.param == "tile_hardware_manager":
            return tile_hardware_manager
        # elif request.param == "tpm_driver":
        #     raise NotImplementedError

    @pytest.mark.parametrize(
        ("attribute_name", "expected_value"),
        (
            ("current", TpmSimulator.CURRENT),
            ("voltage", TpmSimulator.VOLTAGE),
            ("board_temperature", TpmSimulator.BOARD_TEMPERATURE),
            ("fpga1_temperature", TpmSimulator.FPGA1_TEMPERATURE),
            ("fpga2_temperature", TpmSimulator.FPGA2_TEMPERATURE),
            ("adc_rms", TpmSimulator.ADC_RMS),
            ("fpga1_time", TpmSimulator.FPGA1_TIME),
            ("fpga2_time", TpmSimulator.FPGA2_TIME),
            (
                "current_tile_beamformer_frame",
                TpmSimulator.CURRENT_TILE_BEAMFORMER_FRAME,
            ),
            ("pps_delay", TpmSimulator.PPS_DELAY),
            ("firmware_available", TpmSimulator.FIRMWARE_AVAILABLE),
            ("register_list", list(TpmSimulator.REGISTER_MAP[0].keys())),
        ),
    )
    def test_read_attribute(self, hardware_under_test, attribute_name, expected_value):
        """
        Tests that read-only attributes take certain known initial
        values. This is a weak test; over time we should find ways to
        more thoroughly test each of these independently.

        :param hardware_under_test: the hardware object under test. This
            could be a TpmSimulator, or a TileHardwareManager, or, when
            we eventually write it, a TpmDriver of an actual hardware
            TPM
        :type hardware_under_test: object
        :param attribute_name: the name of the attribute under test
        :type attribute_name: str
        :param expected_value: the expected value of the attribute. This
            can be any type, but the test of the attribute is a single
            "==" equality test.
        :type expected_value: any
        """
        assert getattr(hardware_under_test, attribute_name) == expected_value

    @pytest.mark.parametrize(
        ("attribute_name", "initial_value", "values_to_write"),
        (("phase_terminal_count", TpmSimulator.PHASE_TERMINAL_COUNT, [1, 2]),),
    )
    def test_write_attribute(
        self, hardware_under_test, attribute_name, initial_value, values_to_write
    ):
        """
        Tests that read-write attributes take certain known initial
        values, and that their values can be updated.

        This is a weak test; over time we should find ways to more
        thoroughly test each of these independently.

        :param hardware_under_test: the hardware object under test. This
            could be a TpmSimulator, or a TileHardwareManager, or, when
            we eventually write it, a TpmDriver of an actual hardware
            TPM
        :type hardware_under_test: object
        :param attribute_name: the name of the attribute under test
        :type attribute_name: str
        :param initial_value: the expected initial value of the
            attribute. This can be any type, but the test of the
            attribute is a simple "==" equality test.
        :type initial_value: any
        :param values_to_write: a sequence of values to write, in order
            to check that the writes are sticking. The values can be of
            any type, but the test of the attribute is a simple "=="
            equality test.
        :type values_to_write: list
        """
        assert getattr(hardware_under_test, attribute_name) == initial_value

        for value in values_to_write:
            setattr(hardware_under_test, attribute_name, value)
            assert getattr(hardware_under_test, attribute_name) == value

    @pytest.mark.parametrize(
        ("command_name", "num_args"),
        (
            ("cpld_flash_write", 1),
            ("initialise", 0),
            ("set_channeliser_truncation", 1),
            ("set_beamformer_regions", 1),
            ("initialise_beamformer", 4),
            ("set_lmc_download", 1),
            ("switch_calibration_bank", 0),
            ("load_beam_angle", 1),
            ("load_calibration_coefficients", 2),
            ("load_antenna_tapering", 1),
            ("load_pointing_delay", 1),
            ("set_pointing_delay", 2),
            ("configure_integrated_channel_data", 0),
            ("configure_integrated_beam_data", 0),
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
            ("send_raw_data_synchronised", 0),
            ("send_channelised_data_narrowband", 2),
            ("tweak_transceivers", 0),
            ("post_synchronisation", 0),
            ("sync_fpgas", 0),
            ("check_pending_data_requests", 0),
        ),
    )
    def test_command(self, hardware_under_test, command_name, num_args):
        """
        Test of commands that aren't implemented yet. Since the comands
        don't really do anything, these tests simply check that the
        command can be called.

        :param hardware_under_test: the hardware object under test. This
            could be a TpmSimulator, or a TileHardwareManager, or, when
            we eventually write it, a TpmDriver of an actual hardware
            TPM
        :type hardware_under_test: object
        :param command_name: the name of the command under test
        :type command_name: str
        :param num_args: the number of args the command takes
        :type num_args: int
        """
        args = [Mock()] * num_args
        with pytest.raises(NotImplementedError):
            getattr(hardware_under_test, command_name)(*args)

    def test_download_firmware(self, hardware_under_test, mocker):
        """
        Test of:
        * the download_firmware command.
        * the is_programmed attribute

        :param hardware_under_test: the hardware object under test. This
            could be a TpmSimulator, or a TileHardwareManager, or, when
            we eventually write it, a TpmDriver of an actual hardware
            TPM
        :type hardware_under_test: object
            :py:class:`~ska.low.mccs.tile.tile_hardware.TileHardwareManager`
        :param mocker: fixture that wraps unittest.mock
        :type mocker: wrapper for :py:mod:`unittest.mock`
        """
        assert not hardware_under_test.is_programmed
        mock_bitfile = mocker.Mock()
        hardware_under_test.download_firmware(mock_bitfile)
        assert hardware_under_test.is_programmed

    @pytest.mark.parametrize("device", (0, 1))
    @pytest.mark.parametrize("register", tuple(f"test-reg{i}" for i in (1, 4)))
    @pytest.mark.parametrize("read_offset", (0, 2))
    @pytest.mark.parametrize("read_length", (0, 4))
    @pytest.mark.parametrize("write_offset", (0, 3))
    @pytest.mark.parametrize("write_values", ((), (1,), (2, 2)), ids=(0, 1, 2))
    def test_read_and_write_register(
        self,
        hardware_under_test,
        device,
        register,
        read_offset,
        read_length,
        write_offset,
        write_values,
    ):
        """
        Test of

        * read_register command
        * write_register command

        :param hardware_under_test: the hardware object under test. This
            could be a TpmSimulator, or a TileHardwareManager, or, when
            we eventually write it, a TpmDriver of an actual hardware
            TPM
        :type hardware_under_test: object
        :param device: which FPGA is being addressed
        :type device: int
        :param register: which register is being addressed
        :type register: int
        :param read_offset: offset to start read at
        :type read_offset: int
        :param read_length: length of read
        :type read_length: int
        :param write_offset: offset to start write at
        :type write_offset: int
        :param write_values: values to write to the register
        :type write_values: array
        """
        buffer_size = max(read_offset + read_length, write_offset + len(write_values))
        buffer = [0] * buffer_size
        for (index, value) in enumerate(write_values):
            buffer[write_offset + index] = value
        expected_read = tuple(buffer[read_offset : (read_offset + read_length)])
        hardware_under_test.write_register(register, write_values, write_offset, device)
        assert (
            hardware_under_test.read_register(
                register, read_length, read_offset, device
            )
            == expected_read
        )

    @pytest.mark.parametrize("write_address", (9, 11))
    @pytest.mark.parametrize("write_values", ((), (1,), (2, 2)), ids=(0, 1, 2))
    @pytest.mark.parametrize("read_address", (10,))
    @pytest.mark.parametrize("read_length", (0, 4))
    def test_read_and_write_address(
        self,
        hardware_under_test,
        write_address,
        write_values,
        read_address,
        read_length,
    ):
        """
        Test of

        * read_address command
        * write_address command

        :param hardware_under_test: the hardware object under test. This
            could be a TpmSimulator, or a TileHardwareManager, or, when
            we eventually write it, a TpmDriver of an actual hardware
            TPM
        :type hardware_under_test: object
        :param write_address: address to write to
        :type write_address: int
        :param write_values: values to write
        :type write_values: tuple
        :param read_address: address to read from
        :type read_address: int
        :param read_length: length to read
        :type read_length: int
        """
        min_address = min(read_address, write_address)
        max_address = max(read_address + read_length, write_address + len(write_values))
        buffer = [0] * (max_address - min_address)

        def buffer_slice(address, length):
            """
            Helper function that returns a slice that tells you where to
            read from or write to the buffer

            :param address: the start address being read from or written
                to
            :type address: int
            :param length: the size of the write or read
            :type length: int

            :return: a buffer slice defining where in the buffer the
                read or write should be applied
            :rtype: :py:class:`slice`
            """
            return slice(address - min_address, address - min_address + length)

        buffer[buffer_slice(write_address, len(write_values))] = write_values
        expected_read = tuple(buffer[buffer_slice(read_address, read_length)])

        hardware_under_test.write_address(write_address, write_values)
        assert (
            hardware_under_test.read_address(read_address, read_length) == expected_read
        )

    def test_start_stop_beamformer(self, hardware_under_test, mocker):
        """
        Test of:
        * the start_beamformer command.
        * the stop_beamformer command.
        * the is_beamformer_running attribute

        :param hardware_under_test: the hardware object under test. This
            could be a TpmSimulator, or a TileHardwareManager, or, when
            we eventually write it, a TpmDriver of an actual hardware
            TPM
        :type hardware_under_test: object
        :param mocker: fixture that wraps unittest.mock
        :type mocker: wrapper for :py:mod:`unittest.mock`
        """
        assert not hardware_under_test.is_beamformer_running
        hardware_under_test.start_beamformer()
        assert hardware_under_test.is_beamformer_running
        hardware_under_test.stop_beamformer()
        assert not hardware_under_test.is_beamformer_running

    def test_40g_configuration(self, hardware_under_test):
        """
        Test of
        * the configure_40g_core command
        * the get_40g_configuration command

        :param hardware_under_test: the hardware object under test. This
            could be a TpmSimulator, or a TileHardwareManager, or, when
            we eventually write it, a TpmDriver of an actual hardware
            TPM
        :type hardware_under_test: object
        """

        assert hardware_under_test.get_40g_configuration(-1) == []
        assert hardware_under_test.get_40g_configuration("mock_core_id") is None

        hardware_under_test.configure_40g_core(
            "mock_core_id",
            "mock_src_mac",
            "mock_src_ip",
            "mock_src_port",
            "mock_dst_mac",
            "mock_dst_ip",
            "mock_dst_port",
        )

        expected = {
            "CoreID": "mock_core_id",
            "SrcMac": "mock_src_mac",
            "SrcIP": "mock_src_ip",
            "SrcPort": "mock_src_port",
            "DstMac": "mock_dst_mac",
            "DstIP": "mock_dst_ip",
            "DstPort": "mock_dst_port",
        }

        assert hardware_under_test.get_40g_configuration(-1) == [expected]
        assert hardware_under_test.get_40g_configuration("mock_core_id") == expected
        assert hardware_under_test.get_40g_configuration("another_core_id") is None
