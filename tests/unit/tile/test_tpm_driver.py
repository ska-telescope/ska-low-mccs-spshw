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
from typing import Callable

import pytest
from pyfabil.base.definitions import LibraryError
from ska_control_model import CommunicationStatus, SimulationMode, TaskStatus
from ska_low_mccs_common.testing.mock import MockCallable

from ska_low_mccs.tile import StaticTileSimulator, TpmDriver

# from .static_tile_simulator import StaticTileSimulator
from ska_low_mccs.tile.tpm_status import TpmStatus


class TestTPMDriver:
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
    def simulation_mode(self: TestTPMDriver) -> SimulationMode:
        """
        Return the simulation mode.

        To be used when initialising the tile class object
        under test.

        :return: the simulation mode to be used when initialising the
            tile class object under test.
        """
        return SimulationMode.FALSE

    @pytest.fixture()
    def hardware_tile_mock(self: TestTPMDriver) -> unittest.mock.Mock:
        """
        Provide a mock for the hardware tile.

        :return: An hardware tile mock
        """
        tpm = {}

        def get_item(item):
            return tpm[item]

        def set_item(item, value):
            tpm[item] = value

        tile_mock = unittest.mock.MagicMock()
        tile_mock.__getitem__.side_effect = get_item
        tile_mock.__setitem__.side_effect = set_item
        return tile_mock

    class PatchedTpmDriver(TpmDriver):
        """Patched TpmDriver class."""

        def __init__(
            self: TestTPMDriver.PatchedTpmDriver,
            logger: logging.Logger,
            max_workers: int,
            tile_id: int,
            ip: str,
            port: int,
            tpm_version: str,
            communication_state_changed_callback: Callable[[CommunicationStatus], None],
            component_state_changed_callback: Callable[[bool], None],
            static_tile_simulator: StaticTileSimulator,
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
            :param static_tile_simulator: a mock of the tpm_driver
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
            # overwrite the tile with mock
            self.tile = static_tile_simulator

    @pytest.fixture()
    def patched_tpm_driver(
        self: TestTPMDriver,
        logger: logging.Logger,
        max_workers: int,
        tile_id: int,
        tpm_ip: str,
        tpm_cpld_port: int,
        tpm_version: str,
        communication_state_changed_callback: MockCallable,
        component_state_changed_callback: MockCallable,
        static_tile_simulator: StaticTileSimulator,
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
        :param static_tile_simulator: a mock of the tpm_driver

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
            static_tile_simulator,
        )

    def test_communication(
        self: TestTPMDriver,
        patched_tpm_driver: PatchedTpmDriver,
        static_tile_simulator: StaticTileSimulator,
        mock_task_callback: MockCallable,
    ) -> None:
        """
        Test we can create the driver and start communication with the component.

        We can create the tile class object under test, and we will mock
        the underlying component.

        :param mock_task_callback: A mocked callable
        :param patched_tpm_driver: the patched tpm driver under test.
        :param static_tile_simulator: An hardware tile mock
        """
        assert patched_tpm_driver.communication_state == CommunicationStatus.DISABLED
        patched_tpm_driver.start_communicating()
        assert (
            patched_tpm_driver.communication_state
            == CommunicationStatus.NOT_ESTABLISHED
        )

        # Wait for the message to execute
        time.sleep(1)
        assert static_tile_simulator.tpm

        # assert "_ConnectToTile" in patched_tpm_driver._queue_manager._task_result[0]
        # assert patched_tpm_driver._queue_manager._task_result[1] == str(
        #    ResultCode.OK.value
        # )

        # assert patched_tpm_driver._queue_manager._task_result[2] ==
        # "Connected to Tile"
        assert patched_tpm_driver.communication_state == CommunicationStatus.ESTABLISHED

        # call again to check None returns
        assert patched_tpm_driver.start_communicating() is None

        patched_tpm_driver.stop_communicating()
        assert patched_tpm_driver.communication_state == CommunicationStatus.ESTABLISHED

        time.sleep(1)
        assert static_tile_simulator.tpm is None
        assert (
            patched_tpm_driver.communication_state
            == CommunicationStatus.NOT_ESTABLISHED
        )

        # check that when we call stop communicating with communication disabled
        patched_tpm_driver.update_communication_state(CommunicationStatus.DISABLED)
        assert patched_tpm_driver.stop_communicating() is None

        # check start communicate where connect raises failure
        assert not static_tile_simulator.tpm

        mock_task_callback.side_effect = LibraryError("attribute mocked to fail")
        static_tile_simulator.connect = mock_task_callback

        # start communicating unblocks the polling loop therefore starting it
        assert patched_tpm_driver.communication_state == CommunicationStatus.DISABLED
        patched_tpm_driver.start_communicating()
        assert (
            patched_tpm_driver.communication_state
            == CommunicationStatus.NOT_ESTABLISHED
        )
        # allow time to run a few poll loops
        time.sleep(8)
        assert not patched_tpm_driver.tile.tpm
        assert patched_tpm_driver._tpm_status == TpmStatus.UNCONNECTED
        assert patched_tpm_driver._faulty

    def test_write_read_registers(
        self: TestTPMDriver,
        patched_tpm_driver: PatchedTpmDriver,
        static_tile_simulator: StaticTileSimulator,
    ) -> None:
        """
        Test we can write values to a register.

        Using a static_tile_simulator to mock the functionality
        of writing to a register

        :param patched_tpm_driver: The patched tpm driver under test.
        :param static_tile_simulator: The mocked tile
        """
        # No UDP connection are used here. The static_tile_simulator
        # constructs a mocked TPM
        # Therefore the tile will have access to the TPM after connect().
        static_tile_simulator.connect()
        static_tile_simulator.tpm.write_register("fpga1.1", 3)
        static_tile_simulator.tpm.write_register("fpga2.2", 2)
        static_tile_simulator.tpm.write_register(
            "fpga1.dsp_regfile.stream_status.channelizer_vld", 2
        )

        # write to fpga1
        # write_register(register_name, values, offset, device)
        patched_tpm_driver.write_register("1", 17, 1, 1)
        read_value = patched_tpm_driver.read_register("1", 13, 0, 1)
        assert read_value == [17]

        # test write to unknown register
        patched_tpm_driver.write_register("unknown", 17, 1, 1)
        read_value = patched_tpm_driver.read_register("unknown", 13, 0, 1)
        assert read_value == []

        # write to fpga2
        patched_tpm_driver.write_register("2", 17, 1, 2)
        read_value = patched_tpm_driver.read_register("2", 13, 0, 2)
        assert read_value == [17]

        # test write to unknown register
        patched_tpm_driver.write_register("unknown", 17, 1, 2)
        read_value = patched_tpm_driver.read_register("unknown", 13, 0, 2)
        assert read_value == []

        # write to register with no associated device
        patched_tpm_driver.write_register(
            "fpga1.dsp_regfile.stream_status.channelizer_vld", 17, 1, ""
        )
        read_value = patched_tpm_driver.read_register(
            "fpga1.dsp_regfile.stream_status.channelizer_vld", 13, 0, ""
        )
        assert read_value == [17]

        # test write to unknown register
        patched_tpm_driver.write_register("unknown", 17, 1, "")
        read_value = patched_tpm_driver.read_register("unknown", 13, 0, "")
        assert read_value == []

        # test register that returns list
        read_value = patched_tpm_driver.read_register("mocked_list", 13, 0, "")
        assert read_value == []

    def test_write_read_address(
        self: TestTPMDriver,
        patched_tpm_driver: PatchedTpmDriver,
        static_tile_simulator: StaticTileSimulator,
    ) -> None:
        """
        Test we can write and read addresses on the static_tile_simulator.

        :param patched_tpm_driver: The patched tpm driver under test.
        :param static_tile_simulator: The mocked tile
        """
        # No UDP connection are used here. The static_tile_simulator
        # constructs a mocked TPM
        # Therefore the tile will have access to the TPM after connect().
        static_tile_simulator.connect()

        # write_address(address, values)
        patched_tpm_driver.write_address(4, [2, 3, 4, 5])
        read_value = patched_tpm_driver.read_address(4, 4)
        assert read_value == [2, 3, 4, 5]

        # mock a failed write by trying to write them no tpm attacked
        static_tile_simulator.tpm = None
        patched_tpm_driver.write_address(4, [2, 3, 4, 5])

    def test_updating_attributes(
        self: TestTPMDriver,
        patched_tpm_driver: PatchedTpmDriver,
        static_tile_simulator: unittest.mock.Mock,
        mock_task_callback: MockCallable,
    ) -> None:
        """
        Test we can update attributes.

        :param mock_task_callback: A mocked callable
        :param patched_tpm_driver: The patched tpm driver under test.
        :param static_tile_simulator: The mocked tile
        """
        # No UDP connection are used here. The static_tile_simulator
        # constructs a mocked TPM
        # Therefore the tile will have access to the TPM after connect().
        static_tile_simulator.connect()

        # the tile must be programmed to update attributes, therefore we mock that
        static_tile_simulator.is_programmed = unittest.mock.Mock(return_value=True)
        # updated values
        fpga1_temp = 2
        fpga2_temp = 32
        board_temp = 4
        voltage = 1

        static_tile_simulator.tpm._fpga1_temperature = fpga1_temp
        static_tile_simulator.tpm._fpga2_temperature = fpga2_temp
        static_tile_simulator.tpm._board_temperature = board_temp
        static_tile_simulator.tpm._voltage = voltage

        patched_tpm_driver.updating_attributes()

        # check that they are updated
        assert patched_tpm_driver._fpga1_temperature == fpga1_temp
        assert patched_tpm_driver._fpga2_temperature == fpga2_temp
        assert patched_tpm_driver._board_temperature == board_temp
        assert patched_tpm_driver._voltage == voltage

        # Check value not updated if we have a failure
        static_tile_simulator.tpm._voltage = 2.2

        mock_task_callback.side_effect = LibraryError("attribute mocked to fail")
        static_tile_simulator.get_voltage = mock_task_callback

        patched_tpm_driver.updating_attributes()
        assert patched_tpm_driver._voltage != static_tile_simulator.tpm._voltage

    def test_read_tile_attributes(
        self: TestTPMDriver,
        patched_tpm_driver: PatchedTpmDriver,
        static_tile_simulator: StaticTileSimulator,
    ) -> None:
        """
        Test that tpm_driver can read attributes from tile.

        :param patched_tpm_driver: The patched tpm driver under test.
        :param static_tile_simulator: The mocked tile
        """
        # No UDP connection are used here. The static_tile_simulator
        # constructs a mocked TPM
        # Therefore the tile will have access to the TPM after connect().
        static_tile_simulator.connect()
        static_tile_simulator.fpga_time = 2
        static_tile_simulator["fpga1.pps_manager.sync_time_val"] = 0.4
        static_tile_simulator.tpm._fpga_current_frame = 2

        board_temperature = patched_tpm_driver.board_temperature
        voltage = patched_tpm_driver.voltage
        fpga1_temperature = patched_tpm_driver.fpga1_temperature
        fpga2_temperature = patched_tpm_driver.fpga2_temperature
        adc_rms = patched_tpm_driver.adc_rms
        get_fpga_time = patched_tpm_driver.fpgas_time
        get_pps_delay = patched_tpm_driver.pps_delay
        get_fpgs_sync_time = patched_tpm_driver.fpga_sync_time

        assert board_temperature == StaticTileSimulator.BOARD_TEMPERATURE
        assert voltage == StaticTileSimulator.VOLTAGE
        assert fpga1_temperature == StaticTileSimulator.FPGA1_TEMPERATURE
        assert fpga2_temperature == StaticTileSimulator.FPGA2_TEMPERATURE
        assert adc_rms == list(StaticTileSimulator.ADC_RMS)
        assert get_fpga_time == [2, 2]
        assert get_pps_delay == StaticTileSimulator.PPS_DELAY
        assert get_fpgs_sync_time == 0.4

    def test_polling_loop(
        self: TestTPMDriver,
        patched_tpm_driver: PatchedTpmDriver,
        static_tile_simulator: StaticTileSimulator,
    ) -> None:
        """
        Test the polling loop works as expected.

        The polling loop is run on a thread so to unit test here is tricky.
        The start communicating function unblocks the polling loop, allows the polling
        loop to be tested.

        :param patched_tpm_driver: The patched tpm driver under test.
        :param static_tile_simulator: The mocked tile
        """
        # No UDP connection are used here. The static_tile_simulator
        # constructs a mocked TPM
        # Therefore the tile will have access to the TPM after connect().
        assert not static_tile_simulator.tpm
        static_tile_simulator.connect()
        assert static_tile_simulator.tpm

        # start communicating unblocks the polling loop therefore starting it
        assert patched_tpm_driver.communication_state == CommunicationStatus.DISABLED
        patched_tpm_driver.start_communicating()
        assert (
            patched_tpm_driver.communication_state
            == CommunicationStatus.NOT_ESTABLISHED
        )
        # allow time to run a few poll loops
        time.sleep(0.1)

        # trigger the stop polling loop should disconnect the tpm and
        # set communication state to NOT_ESTABLISHED
        patched_tpm_driver._stop_polling_event.set()
        # allow time to poll complete poll
        time.sleep(0.1)
        assert patched_tpm_driver._is_programmed is False
        assert (
            patched_tpm_driver.communication_state
            == CommunicationStatus.NOT_ESTABLISHED
        )
        assert patched_tpm_driver._tpm_status == TpmStatus.UNCONNECTED
        assert static_tile_simulator.tpm is None

        # restart the polling loop. Since the connection state
        # is ESTABLISHED the loop will
        # attempt to poll the tpm to check communication.
        # However the connection is now lost
        assert not static_tile_simulator.tpm
        # restart polling loop
        patched_tpm_driver.update_communication_state(CommunicationStatus.ESTABLISHED)
        patched_tpm_driver._stop_polling_event.clear()
        patched_tpm_driver._start_polling_event.set()

        # give sufficient time to give up an connecting and return fault
        time.sleep(1)

        assert patched_tpm_driver._faulty
        assert (
            patched_tpm_driver.communication_state
            == CommunicationStatus.NOT_ESTABLISHED
        )
        assert patched_tpm_driver._tpm_status == TpmStatus.UNCONNECTED

        # the connection should attempt to restart given enough time
        time.sleep(6)
        assert static_tile_simulator.tpm
        assert patched_tpm_driver.communication_state == CommunicationStatus.ESTABLISHED

    def test_tpm_status(
        self: TestTPMDriver,
        patched_tpm_driver: PatchedTpmDriver,
        static_tile_simulator: StaticTileSimulator,
    ) -> None:
        """
        Test that the tpm status reports as expected.

        :param patched_tpm_driver: The patched tpm driver under test.
        :param static_tile_simulator: The mocked tile
        """
        assert patched_tpm_driver._tpm_status == TpmStatus.UNKNOWN
        # just used to call update_tpm_status and cover the tpm_status property in test

        assert patched_tpm_driver.tpm_status == TpmStatus.UNCONNECTED

        static_tile_simulator.connect()
        patched_tpm_driver.update_communication_state(CommunicationStatus.ESTABLISHED)

        assert patched_tpm_driver.tpm_status == TpmStatus.UNPROGRAMMED

        # reset with connection to TPM
        static_tile_simulator.tpm._is_programmed = True
        patched_tpm_driver._tpm_status = TpmStatus.UNCONNECTED

        assert patched_tpm_driver.tpm_status == TpmStatus.PROGRAMMED

    def test_get_tile_id(
        self: TestTPMDriver,
        patched_tpm_driver: PatchedTpmDriver,
        static_tile_simulator: StaticTileSimulator,
    ) -> None:
        """
        Test that we can get the tile_id from the mocked Tile.

        :param patched_tpm_driver: The patched tpm driver under test.
        :param static_tile_simulator: The mocked tile
        """
        # No UDP connection are used here. The static_tile_simulator
        # constructs a mocked TPM
        # Therefore the tile will have access to the TPM after connect().
        static_tile_simulator.connect()
        static_tile_simulator.tpm._tile_id = 5
        assert static_tile_simulator.tpm
        tile_id = patched_tpm_driver.get_tile_id()
        assert tile_id == 5

        # mocked error case
        mock_libraryerror = unittest.mock.Mock(
            side_effect=LibraryError("attribute mocked to fail")
        )
        static_tile_simulator.get_tile_id = unittest.mock.MagicMock(
            side_effect=mock_libraryerror
        )
        assert patched_tpm_driver.get_tile_id() == 0

    def test_start_acquisition(
        self: TestTPMDriver,
        patched_tpm_driver: PatchedTpmDriver,
        static_tile_simulator: StaticTileSimulator,
    ) -> None:
        """
        Test that start acquisition writes to mocked registers on the mocked tile.

        :param patched_tpm_driver: The patched tpm driver under test.
        :param static_tile_simulator: The mocked tile
        """
        # No UDP connection are used here. The static_tile_simulator
        # constructs a mocked TPM
        # Therefore the tile will have access to the TPM after connect().
        static_tile_simulator.connect()

        # get_arp_table is mocked to fail, so start_acquisition should
        # return false.
        assert patched_tpm_driver.start_acquisition() is False

        static_tile_simulator.check_arp_table = unittest.mock.MagicMock(
            return_value=True
        )
        static_tile_simulator.start_acquisition = unittest.mock.MagicMock(
            return_value=True
        )
        # mocked response from one register other will fail
        static_tile_simulator["fpga1.dsp_regfile.stream_status.channelizer_vld"] = 1
        assert patched_tpm_driver.start_acquisition() is False
        assert patched_tpm_driver._tpm_status == TpmStatus.UNKNOWN

        # mocked response from both register
        static_tile_simulator["fpga1.dsp_regfile.stream_status.channelizer_vld"] = 1
        static_tile_simulator["fpga2.dsp_regfile.stream_status.channelizer_vld"] = 1

        assert patched_tpm_driver.start_acquisition() is True
        assert patched_tpm_driver._tpm_status == TpmStatus.SYNCHRONISED

    def test_set_time_delays(
        self: TestTPMDriver,
        patched_tpm_driver: PatchedTpmDriver,
        static_tile_simulator: StaticTileSimulator,
    ) -> None:
        """
        Test that we can set the delays to the tile hardware mock.

        :param patched_tpm_driver: The patched tpm driver under test.
        :param static_tile_simulator: The mocked tile
        """
        # No UDP connection are used here. The static_tile_simulator
        # constructs a mocked TPM
        # Therefore the tile will have access to the TPM after connect().
        static_tile_simulator.connect()
        # mocked register return
        expected_delay_written = [344.0, 200.7]
        static_tile_simulator["fpga1.test_generator.delay_0"] = expected_delay_written
        static_tile_simulator["fpga2.test_generator.delay_0"] = expected_delay_written

        patched_tpm_driver.set_time_delays(expected_delay_written)

        # assert both fpgas have that delay
        assert (
            static_tile_simulator["fpga1.test_generator.delay_0"]
            == expected_delay_written
        )
        assert (
            static_tile_simulator["fpga2.test_generator.delay_0"]
            == expected_delay_written
        )

        # check set_time_delay failure
        expected_delay_written = [43.0, 98.2]
        mock_error = unittest.mock.Mock(side_effect=Exception("mocked to fail"))
        static_tile_simulator.set_time_delays = unittest.mock.MagicMock(
            side_effect=mock_error
        )
        patched_tpm_driver.set_time_delays(expected_delay_written)

        assert (
            static_tile_simulator["fpga1.test_generator.delay_0"]
            != expected_delay_written
        )
        assert (
            static_tile_simulator["fpga2.test_generator.delay_0"]
            != expected_delay_written
        )

    def test_read_write_address(
        self: TestTPMDriver,
        patched_tpm_driver: PatchedTpmDriver,
        static_tile_simulator: StaticTileSimulator,
    ) -> None:
        """
        Test read write address.

        Test that when we write to a address on the tpm_driver, That value is written to
        the TPM_simulator.

        :param patched_tpm_driver: The patched tpm driver under test.
        :param static_tile_simulator: The mocked tile

        Test that:
        * we can write to a address
        * we can read that same value from that address.
        """
        assert static_tile_simulator.tpm is None
        assert patched_tpm_driver.communication_state == CommunicationStatus.DISABLED
        patched_tpm_driver.start_communicating()
        assert (
            patched_tpm_driver.communication_state
            == CommunicationStatus.NOT_ESTABLISHED
        )

        # Wait for the message to execute
        time.sleep(1)
        assert static_tile_simulator.tpm

        expected_read = [2, 3, 3]
        patched_tpm_driver.write_address(4, expected_read)
        assert patched_tpm_driver.read_address(4, len(expected_read)) == expected_read

    @pytest.mark.xfail
    def test_error_configure_40g_core(
        self: TestTPMDriver,
        patched_tpm_driver: PatchedTpmDriver,
        static_tile_simulator: StaticTileSimulator,
    ) -> None:
        """
        Test that configuration is checked and raises errors.

        :param patched_tpm_driver: The patched tpm driver under test.
        :param static_tile_simulator: The mocked tile

        Test that:
        * The core_id is 0 or 1
        * The arp table entries are (0-7) for each core
        """
        static_tile_simulator.connect()

        # core_id must be 0,1
        core_dict = {
            "core_id": 2,
            "arp_table_entry": 1,
            "src_mac": 0x14109FD4041A,
            "src_ip": "3221226219",
            "src_port": 8080,
            "dst_ip": "3221226219",
            "dst_port": 9000,
        }
        # arp_table_entry must be 0-7
        core_dict2 = {
            "core_id": 1,
            "arp_table_entry": 8,
            "src_mac": 0x14109FD4041A,
            "src_ip": "3221226219",
            "src_port": 8080,
            "dst_ip": "3221222219",
            "dst_port": 9000,
        }

        with pytest.raises(
            ValueError, match=f'cannot configure core {core_dict["core_id"]}'
        ):
            patched_tpm_driver.configure_40g_core(**core_dict)

        with pytest.raises(
            ValueError,
            match=f'cannot configure arp_table_entry {core_dict2["arp_table_entry"]}',
        ):
            patched_tpm_driver.configure_40g_core(**core_dict2)

    def test_configure_40g_core(
        self: TestTPMDriver,
        patched_tpm_driver: PatchedTpmDriver,
        static_tile_simulator: StaticTileSimulator,
    ) -> None:
        """
        Test that we can configure the 40g core.

        :param patched_tpm_driver: The patched tpm driver under test.
        :param static_tile_simulator: The mocked tile

        Test that:
        * we can configure and get that configuration with core_id specified
        * when no core_id is specified we gather all the cores with core_id 0 or one
        """
        # mocked connection to the TPM simuator.
        static_tile_simulator.connect()

        core_dict = {
            "core_id": 0,
            "arp_table_entry": 1,
            "src_mac": 0x14109FD4041A,
            "src_ip": "3221226219",
            "src_port": 8080,
            "dst_ip": "3221226219",
            "dst_port": 9000,
        }
        core_dict2 = {
            "core_id": 1,
            "arp_table_entry": 1,
            "src_mac": 0x14109FD4041A,
            "src_ip": "3221226219",
            "src_port": 8080,
            "dst_ip": "3221222219",
            "dst_port": 9000,
        }
        patched_tpm_driver.configure_40g_core(**core_dict)

        configurations = patched_tpm_driver.get_40g_configuration(
            core_id=core_dict.get("core_id"),
            arp_table_entry=core_dict.get("arp_table_entry"),
        )

        assert configurations == [core_dict]

        # request the configuration without a core_id, returns all.
        patched_tpm_driver.configure_40g_core(**core_dict2)
        configurations = patched_tpm_driver.get_40g_configuration()

        assert configurations == [core_dict, core_dict2]

    def test_firmware_avaliable(
        self: TestTPMDriver,
        patched_tpm_driver: PatchedTpmDriver,
        static_tile_simulator: StaticTileSimulator,
    ) -> None:
        """
        Test that the we can get the firmware from the tpm_driver.

        :param patched_tpm_driver: The patched tpm driver under test.
        :param static_tile_simulator: The mocked tile
        """
        firmware = patched_tpm_driver.firmware_available

        assert firmware == static_tile_simulator.FIRMWARE_LIST
        firmware_version = patched_tpm_driver.firmware_version
        assert firmware_version == "Ver.1.2 build 0:"

    def test_check_programmed(
        self: TestTPMDriver,
        patched_tpm_driver: PatchedTpmDriver,
        static_tile_simulator: StaticTileSimulator,
    ) -> None:
        """
        Test to ensure the tpm_driver can check the TPM programmed state.

        Test to ensure the tpm_driver can read the _check_programmed() method
        correctly if the mocked TPM is programmed.

        :param patched_tpm_driver: The patched tpm driver under test.
        :param static_tile_simulator: The mocked tile
        """
        assert patched_tpm_driver._check_programmed() is False
        static_tile_simulator.connect()
        static_tile_simulator.tpm._is_programmed = True
        assert patched_tpm_driver._check_programmed() is True

    def test_initialise(
        self: TestTPMDriver,
        patched_tpm_driver: PatchedTpmDriver,
        static_tile_simulator: StaticTileSimulator,
    ) -> None:
        """
        When we initialise the tpm_driver the mockedTPM gets the correct calls.

        :param patched_tpm_driver: The patched tpm driver under test.
        :param static_tile_simulator: The mocked tile

        Test cases:
        * programfpga succeeds to programm the fpga
        * programfpga fails to programm the fpga
        """
        # establish connection to the TPM
        static_tile_simulator.connect()
        initialise_task_callback = MockCallable()
        patched_tpm_driver.initialise(task_callback=initialise_task_callback)
        assert static_tile_simulator.is_programmed() is False

        time.sleep(0.1)
        _, kwargs = initialise_task_callback.get_next_call()
        assert kwargs["status"] == TaskStatus.QUEUED

        time.sleep(0.1)
        _, kwargs = initialise_task_callback.get_next_call()
        assert kwargs["status"] == TaskStatus.IN_PROGRESS

        assert static_tile_simulator.is_programmed() is True
        assert patched_tpm_driver._is_programmed is True
        assert patched_tpm_driver._tpm_status == TpmStatus.INITIALISED
        static_tile_simulator.tpm._tpm_status = TpmStatus.PROGRAMMED

        assert static_tile_simulator["fpga1.dsp_regfile.config_id.station_id"] == 0
        assert static_tile_simulator["fpga1.dsp_regfile.config_id.tile_id"] == 0

        _, kwargs = initialise_task_callback.get_next_call()
        assert kwargs["status"] == TaskStatus.COMPLETED
        assert kwargs["result"] == "The initialisation task has completed"

        # The FPGA is mocked to not be programmed after the program_fpga command.
        # check that the initialisation process has failed.
        static_tile_simulator.tpm._is_programmed = False
        static_tile_simulator.program_fpgas = unittest.mock.MagicMock(
            return_value=False
        )
        patched_tpm_driver.initialise(task_callback=initialise_task_callback)
        time.sleep(0.1)
        _, kwargs = initialise_task_callback.get_next_call()
        assert kwargs["status"] == TaskStatus.QUEUED

        time.sleep(0.1)
        _, kwargs = initialise_task_callback.get_next_call()
        assert kwargs["status"] == TaskStatus.IN_PROGRESS
        time.sleep(0.1)
        _, kwargs = initialise_task_callback.get_next_call()
        assert kwargs["status"] == TaskStatus.COMPLETED
        assert kwargs["result"] == "The initialisation task has failed"