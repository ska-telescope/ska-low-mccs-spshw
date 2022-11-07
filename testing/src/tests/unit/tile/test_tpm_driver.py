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
from typing import Any, Callable
from pyfabil.base.definitions import LibraryError
import pytest


from ska_control_model import (
    CommunicationStatus,
    SimulationMode,

)
from ska_low_mccs_common.testing.mock import MockCallable

from ska_low_mccs.tile import TpmDriver, StaticTpmDriverSimulator
from ska_low_mccs.tile.base_tpm_simulator import BaseTpmSimulator

# from .static_tpm_driver_simulator import StaticTpmDriverSimulator
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
            static_tpm_driver_simulator: StaticTpmDriverSimulator,
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
            self.tile = static_tpm_driver_simulator
    
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
        static_tpm_driver_simulator: StaticTpmDriverSimulator,
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
            static_tpm_driver_simulator
        )
    
    
    
    
    def test_communication(
        self: TestTPMDriver,
        patched_tpm_driver: PatchedTpmDriver,
        static_tpm_driver_simulator: StaticTpmDriverSimulator,
    ) -> None:
        """
        Test we can create the driver and start communication with the component.

        We can create the tile class object under test, and we will mock
        the underlying component.

        :param patched_tpm_driver: the patched tpm driver under test.
        :param static_tpm_driver_simulator: An hardware tile mock
        """

        assert patched_tpm_driver.communication_state == CommunicationStatus.DISABLED
        patched_tpm_driver.start_communicating()
        assert (
            patched_tpm_driver.communication_state
            == CommunicationStatus.NOT_ESTABLISHED
        )

        # Wait for the message to execute
        time.sleep(1)
        assert static_tpm_driver_simulator.tpm
        
        # assert "_ConnectToTile" in patched_tpm_driver._queue_manager._task_result[0]
        # assert patched_tpm_driver._queue_manager._task_result[1] == str(
        #    ResultCode.OK.value
        # )

        # assert patched_tpm_driver._queue_manager._task_result[2] ==
        # "Connected to Tile"
        assert patched_tpm_driver.communication_state == CommunicationStatus.ESTABLISHED

        #call again to check None returns
        assert patched_tpm_driver.start_communicating() == None

        patched_tpm_driver.stop_communicating()
        assert (
            patched_tpm_driver.communication_state
            == CommunicationStatus.ESTABLISHED
        )

        time.sleep(1)
        assert static_tpm_driver_simulator.tpm == None
        assert patched_tpm_driver.communication_state == CommunicationStatus.NOT_ESTABLISHED

        #check that when we call stop communicating with communication disabled
        patched_tpm_driver.update_communication_state(CommunicationStatus.DISABLED)
        assert patched_tpm_driver.stop_communicating() == None


    def test_write_read_registers(
        self: TestTPMDriver,
        patched_tpm_driver: PatchedTpmDriver,
        static_tpm_driver_simulator: StaticTpmDriverSimulator,
    ) -> None:
        '''
        Test we can write values to a register.

        In this case we are using a static_tpm_driver_simulator to mock the functionality 
        of writing to a register

        :param patched_tpm_driver: The patched tpm driver under test.
        :param static_tpm_driver_simulator: The mocked tile
        '''
        #No UDP connection are used here. Simply the static_tpm_driver_simulator constructs a mocked TPM
        #Therefore the tile will have access to the TPM after connect().
        static_tpm_driver_simulator.connect()
        static_tpm_driver_simulator.tpm.write_register("fpga1.1" , 3)
        static_tpm_driver_simulator.tpm.write_register("fpga2.2" , 2)
        static_tpm_driver_simulator.tpm.write_register("fpga1.dsp_regfile.stream_status.channelizer_vld" , 2)


        #write to fpga1
        #write_register(register_name, values, offset, device)
        patched_tpm_driver.write_register("1", 17, 1, 1)
        read_value = patched_tpm_driver.read_register("1", 13, 0, 1)
        assert read_value == [17]

        #test write to unknown register
        patched_tpm_driver.write_register("unknown", 17, 1, 1)
        read_value = patched_tpm_driver.read_register("unknown", 13, 0, 1)
        assert read_value == []

        #write to fpga2
        patched_tpm_driver.write_register("2", 17, 1, 2)
        read_value = patched_tpm_driver.read_register("2", 13, 0, 2)
        assert read_value == [17]

        #test write to unknown register
        patched_tpm_driver.write_register("unknown", 17, 1, 2)
        read_value = patched_tpm_driver.read_register("unknown", 13, 0, 2)
        assert read_value == []

        #write to register with no associated device
        patched_tpm_driver.write_register("fpga1.dsp_regfile.stream_status.channelizer_vld", 17, 1, "")
        read_value = patched_tpm_driver.read_register("fpga1.dsp_regfile.stream_status.channelizer_vld", 13, 0, "")
        assert read_value == [17]

        #test write to unknown register
        patched_tpm_driver.write_register("unknown", 17, 1, "")
        read_value = patched_tpm_driver.read_register("unknown", 13, 0, "")
        assert read_value == []

        #test register that returns list
        read_value = patched_tpm_driver.read_register("mocked_list", 13, 0, "")
        assert read_value == []

    def test_write_read_address(
        self: TestTPMDriver,
        patched_tpm_driver: PatchedTpmDriver,
        static_tpm_driver_simulator: StaticTpmDriverSimulator,
    ) -> None:
        '''
        Test we can write and read addresses on the static_tpm_driver_simulator.

        :param patched_tpm_driver: The patched tpm driver under test.
        :param static_tpm_driver_simulator: The mocked tile
        '''
        #No UDP connection are used here. Simply the static_tpm_driver_simulator constructs a mocked TPM
        #Therefore the tile will have access to the TPM after connect().
        static_tpm_driver_simulator.connect()

        #write_address(address, values)
        patched_tpm_driver.write_address(4, [2,3,4,5])
        read_value = patched_tpm_driver.read_address(4, 4)
        assert read_value == [2,3,4,5]

        #mock a failed write by trying to write them no tpm attacked
        static_tpm_driver_simulator.tpm = None
        patched_tpm_driver.write_address(4, [2,3,4,5])


    def test_updating_attributes(
        self: TestTPMDriver,
        patched_tpm_driver: PatchedTpmDriver,
        static_tpm_driver_simulator: unittest.mock.Mock,
    ) -> None:
        """
        Test we can update attributes.

        :param patched_tpm_driver: The patched tpm driver under test.
        :param static_tpm_driver_simulator: The mocked tile
        """
        #No UDP connection are used here. Simply the static_tpm_driver_simulator constructs a mocked TPM
        #Therefore the tile will have access to the TPM after connect().
        static_tpm_driver_simulator.connect()

        #the tile must be programmed to update attributes, therefore we mock that
        static_tpm_driver_simulator.is_programmed = unittest.mock.Mock(return_value=True)

        patched_tpm_driver.updating_attributes()

        #check that they are updated
        assert patched_tpm_driver._fpga1_temperature == StaticTpmDriverSimulator.FPGA1_TEMPERATURE
        assert patched_tpm_driver._fpga2_temperature == StaticTpmDriverSimulator.FPGA2_TEMPERATURE
        assert patched_tpm_driver._board_temperature == StaticTpmDriverSimulator.BOARD_TEMPERATURE
        assert patched_tpm_driver._voltage == StaticTpmDriverSimulator.VOLTAGE

        #Check value not updated if we have a failure
        static_tpm_driver_simulator.tpm._voltage = 2.2
        mock_get_fpga0_temperature_fail = unittest.mock.Mock(side_effect=Exception("get_fpga0_temperature mocked to fail"))
        static_tpm_driver_simulator.get_voltage  = unittest.mock.MagicMock(side_effect= mock_get_fpga0_temperature_fail)
        patched_tpm_driver.updating_attributes()
        assert patched_tpm_driver._voltage != static_tpm_driver_simulator.tpm._voltage 
    
    def test_read_tile_attributes(
        self: TestTPMDriver,
        patched_tpm_driver: PatchedTpmDriver,
        static_tpm_driver_simulator: StaticTpmDriverSimulator,
    ) -> None:
        '''
        Test that tpm_driver can read attributes from tile.

        :param patched_tpm_driver: The patched tpm driver under test.
        :param static_tpm_driver_simulator: The mocked tile 
        '''
        #No UDP connection are used here. Simply the static_tpm_driver_simulator constructs a mocked TPM
        #Therefore the tile will have access to the TPM after connect().
        static_tpm_driver_simulator.connect()
        static_tpm_driver_simulator.fpga_time = 2
        static_tpm_driver_simulator["fpga1.pps_manager.sync_time_val"] = 0.4
        static_tpm_driver_simulator.tpm._fpga_current_frame = 2
        
        board_temperature =  getattr(patched_tpm_driver,"board_temperature")
        voltage =  getattr(patched_tpm_driver, "voltage")
        fpga1_temperature =  getattr(patched_tpm_driver,"fpga1_temperature")
        fpga2_temperature =  getattr(patched_tpm_driver,"fpga2_temperature")
        adc_rms =  getattr(patched_tpm_driver,"adc_rms")
        get_fpga_time =  getattr(patched_tpm_driver,"fpgas_time")
        get_pps_delay =  getattr(patched_tpm_driver,"pps_delay")
        get_fpgs_sync_time =  getattr(patched_tpm_driver,"fpga_sync_time")
        get_fpga_current_frame =  getattr(patched_tpm_driver,"fpga_current_frame")

        assert board_temperature == StaticTpmDriverSimulator.BOARD_TEMPERATURE
        assert voltage == StaticTpmDriverSimulator.VOLTAGE
        assert fpga1_temperature == StaticTpmDriverSimulator.FPGA1_TEMPERATURE
        assert fpga2_temperature  == StaticTpmDriverSimulator.FPGA2_TEMPERATURE
        assert adc_rms == list(StaticTpmDriverSimulator.ADC_RMS)
        assert get_fpga_time == [2,2]
        assert get_pps_delay ==  StaticTpmDriverSimulator.PPS_DELAY
        assert get_fpgs_sync_time == 0.4


    def test_read_mocked_to_fail_tile_attributes(
        self: TestTPMDriver,
        patched_tpm_driver: PatchedTpmDriver,
        static_tpm_driver_simulator: StaticTpmDriverSimulator,
    ) -> None:
        '''
        Test that is a failure occurs during a attribute read we get expected response.

        :param patched_tpm_driver: The patched tpm driver under test.
        :param static_tpm_driver_simulator: The mocked tile 
        '''
        #No UDP connection are used here. Simply the static_tpm_driver_simulator constructs a mocked TPM
        #Therefore the tile will have access to the TPM after connect().
        static_tpm_driver_simulator.connect()

        #mock all read attributes to fail
        mock_tile_connect_to_fail = unittest.mock.Mock(side_effect=Exception("attribute mocked to fail"))
        static_tpm_driver_simulator.get_temperature  = unittest.mock.MagicMock(side_effect= mock_tile_connect_to_fail)
        static_tpm_driver_simulator.get_voltage  = unittest.mock.MagicMock(side_effect= mock_tile_connect_to_fail)
        static_tpm_driver_simulator.get_fpga0_temperature  = unittest.mock.MagicMock(side_effect= mock_tile_connect_to_fail)
        static_tpm_driver_simulator.get_fpga1_temperature  = unittest.mock.MagicMock(side_effect= mock_tile_connect_to_fail)
        static_tpm_driver_simulator.get_adc_rms  = unittest.mock.MagicMock(side_effect= mock_tile_connect_to_fail)
        static_tpm_driver_simulator.get_fpga_time  = unittest.mock.MagicMock(side_effect= mock_tile_connect_to_fail)
        static_tpm_driver_simulator.get_pps_delay  = unittest.mock.MagicMock(side_effect= mock_tile_connect_to_fail)
        

        board_temperature =  getattr(patched_tpm_driver,"board_temperature")
        voltage =  getattr(patched_tpm_driver, "voltage")
        with pytest.raises(ConnectionError, match="Cannot read time from FPGA"):
            getattr(patched_tpm_driver,"fpgas_time")
        fpga1_temperature =  getattr(patched_tpm_driver,"fpga1_temperature")
        fpga2_temperature =  getattr(patched_tpm_driver,"fpga2_temperature")
        adc_rms =  getattr(patched_tpm_driver,"adc_rms")
        get_pps_delay =  getattr(patched_tpm_driver,"pps_delay")

        #assert that the values are the same as the initialised values
        assert board_temperature == patched_tpm_driver.BOARD_TEMPERATURE
        assert voltage == patched_tpm_driver.VOLTAGE
        assert fpga1_temperature  == patched_tpm_driver.FPGA1_TEMPERATURE
        assert fpga2_temperature  == patched_tpm_driver.FPGA2_TEMPERATURE
        assert adc_rms == list(patched_tpm_driver.ADC_RMS)
        assert get_pps_delay ==  BaseTpmSimulator.PPS_DELAY


    def test_polling_loop(        
        self: TestTPMDriver,
        patched_tpm_driver: PatchedTpmDriver,
        static_tpm_driver_simulator: StaticTpmDriverSimulator,
    ) -> None:
        '''
        Test the polling loop works as expected.

        The polling loop is run on a thread so to unit test here is tricky.
        The start communicating function unblocks the polling loop, allows the polling
        loop to be tested.

        :param patched_tpm_driver: The patched tpm driver under test.
        :param static_tpm_driver_simulator: The mocked tile 
        '''
        #No UDP connection are used here. Simply the static_tpm_driver_simulator constructs a mocked TPM
        #Therefore the tile will have access to the TPM after connect().
        assert not static_tpm_driver_simulator.tpm
        static_tpm_driver_simulator.connect()
        assert static_tpm_driver_simulator.tpm

        #start communicating unblocks the polling loop therefore starting it
        assert patched_tpm_driver.communication_state ==CommunicationStatus.DISABLED
        patched_tpm_driver.start_communicating()
        assert (
            patched_tpm_driver.communication_state
            == CommunicationStatus.NOT_ESTABLISHED
        )
        #allow time to run a few poll loops
        time.sleep(0.1)
 
        #trigger the stop polling loop should disconnect the tpm and 
        #set communication state to NOT_ESTABLISHED
        patched_tpm_driver._stop_polling_event.set()
        #allow time to poll complete poll
        time.sleep(0.1)
        assert patched_tpm_driver._is_programmed == False
        assert patched_tpm_driver.communication_state == CommunicationStatus.NOT_ESTABLISHED
        assert patched_tpm_driver._tpm_status == TpmStatus.UNCONNECTED
        assert not static_tpm_driver_simulator.tpm

        #restart the polling loop. Since the connection state is ESTABLISHED the loop will
        #attempt to poll the tpm to check communication. 
        #However the connection is now lost
        assert not static_tpm_driver_simulator.tpm
        #restart polling loop
        patched_tpm_driver.update_communication_state(CommunicationStatus.ESTABLISHED)
        patched_tpm_driver._stop_polling_event.clear()
        patched_tpm_driver._start_polling_event.set()

        #give sufficient time to give up an connecting and return fault
        time.sleep(1)

        assert patched_tpm_driver._faulty
        assert patched_tpm_driver.communication_state == CommunicationStatus.NOT_ESTABLISHED
        assert patched_tpm_driver._tpm_status == TpmStatus.UNCONNECTED

        #the connection should attempt to restart given enough time
        time.sleep(6)
        assert static_tpm_driver_simulator.tpm
        assert patched_tpm_driver.communication_state == CommunicationStatus.ESTABLISHED



    def test_tpm_status(        
        self: TestTPMDriver,
        patched_tpm_driver: PatchedTpmDriver,
        static_tpm_driver_simulator: StaticTpmDriverSimulator,
    ) -> None:
        '''
        Test that the tpm status reports as expected

        :param patched_tpm_driver: The patched tpm driver under test.
        :param static_tpm_driver_simulator: The mocked tile 
        '''
        getattr(patched_tpm_driver, "tpm_status")
        assert patched_tpm_driver._tpm_status == TpmStatus.UNCONNECTED

        static_tpm_driver_simulator.connect()
        patched_tpm_driver.update_communication_state(CommunicationStatus.ESTABLISHED)
        getattr(patched_tpm_driver, "tpm_status")
        assert patched_tpm_driver._tpm_status == TpmStatus.UNPROGRAMMED

        #reset with connection to TPM
        static_tpm_driver_simulator.tpm._is_programmed = True
        patched_tpm_driver._tpm_status = TpmStatus.UNCONNECTED
        getattr(patched_tpm_driver, "tpm_status")
        assert patched_tpm_driver._tpm_status == TpmStatus.PROGRAMMED

        #reset tpm_status.
        #set tile_id of hardware mock to be same as software
        static_tpm_driver_simulator["fpga1.regfile.tpm_id"] = patched_tpm_driver._tile_id
        patched_tpm_driver._tpm_status = TpmStatus.UNCONNECTED
        getattr(patched_tpm_driver, "tpm_status")
        
        #self._check_channeliser_started() does not exist and is throwing a exception for the wrong reason.



    def test_get_tile_id(        
        self: TestTPMDriver,
        patched_tpm_driver: PatchedTpmDriver,
        static_tpm_driver_simulator: StaticTpmDriverSimulator,
    ) -> None:
        '''
        Test that we can get the tile_id from the mocked Tile

        :param patched_tpm_driver: The patched tpm driver under test.
        :param static_tpm_driver_simulator: The mocked tile 
        '''
        #No UDP connection are used here. Simply the static_tpm_driver_simulator constructs a mocked TPM
        #Therefore the tile will have access to the TPM after connect().
        static_tpm_driver_simulator.connect()
        static_tpm_driver_simulator.tpm._tile_id = 5
        assert static_tpm_driver_simulator.tpm
        tile_id = getattr(patched_tpm_driver, "get_tile_id")()
        assert tile_id == 5

        #mocked error case
        mock_libraryerror = unittest.mock.Mock(side_effect=LibraryError("attribute mocked to fail"))
        static_tpm_driver_simulator.get_tile_id  = unittest.mock.MagicMock(side_effect= mock_libraryerror)
        assert getattr(patched_tpm_driver, "get_tile_id")() == 0

    def test_start_acquisition(        
        self: TestTPMDriver,
        patched_tpm_driver: PatchedTpmDriver,
        static_tpm_driver_simulator: StaticTpmDriverSimulator,
    ) -> None:
        '''
        Test that start acquisition writes to mocked registers on the mocked tile.

        :param patched_tpm_driver: The patched tpm driver under test.
        :param static_tpm_driver_simulator: The mocked tile 
        '''
        #No UDP connection are used here. Simply the static_tpm_driver_simulator constructs a mocked TPM
        #Therefore the tile will have access to the TPM after connect().
        static_tpm_driver_simulator.connect()

        getattr(patched_tpm_driver, "start_acquisition")()
        assert patched_tpm_driver.tile._tpm_status == TpmStatus.SYNCHRONISED

        #start_acquisition with failure should return false and not start
        mock_error = unittest.mock.Mock(side_effect=Exception("mocked to fail"))
        static_tpm_driver_simulator.check_arp_table  = unittest.mock.MagicMock(side_effect= mock_error)
        assert getattr(patched_tpm_driver, "start_acquisition")() == False

    def test_set_time_delays(        
        self: TestTPMDriver,
        patched_tpm_driver: PatchedTpmDriver,
        static_tpm_driver_simulator: StaticTpmDriverSimulator,
    ) -> None:
        '''
        Test that we can set the delays to the tile hardware mock.

        :param patched_tpm_driver: The patched tpm driver under test.
        :param static_tpm_driver_simulator: The mocked tile 
        '''
        #No UDP connection are used here. Simply the static_tpm_driver_simulator constructs a mocked TPM
        #Therefore the tile will have access to the TPM after connect().
        static_tpm_driver_simulator.connect()
        #mocked register return
        expected_delay_written = [344.0, 200.7]
        static_tpm_driver_simulator["fpga1.test_generator.delay_0"] = expected_delay_written
        static_tpm_driver_simulator["fpga2.test_generator.delay_0"] = expected_delay_written

        getattr(patched_tpm_driver, "set_time_delays")(expected_delay_written)

        #assert both fpgas have that delay
        assert static_tpm_driver_simulator["fpga1.test_generator.delay_0"] == expected_delay_written
        assert static_tpm_driver_simulator["fpga2.test_generator.delay_0"] == expected_delay_written

        #check set_time_delay failure
        expected_delay_written = [43.0, 98.2]
        mock_error = unittest.mock.Mock(side_effect=Exception("mocked to fail"))
        static_tpm_driver_simulator.set_time_delays  = unittest.mock.MagicMock(side_effect= mock_error)
        getattr(patched_tpm_driver, "set_time_delays")(expected_delay_written)
    
        assert static_tpm_driver_simulator["fpga1.test_generator.delay_0"] != expected_delay_written
        assert static_tpm_driver_simulator["fpga2.test_generator.delay_0"] != expected_delay_written

    def test_read_write_address(
        self: TestTPMDriver,
        patched_tpm_driver: PatchedTpmDriver,
        static_tpm_driver_simulator: StaticTpmDriverSimulator,
    ) -> None:
        """
        Test we can create the driver and start communication with the component.

        We can create the tile class object under test, and we will mock
        the underlying component (which is a hardware TPM that does not exist
        in this test harness).

        :param patched_tpm_driver: the patched tpm driver under test.
        :param hardware_tile_mock: An hardware tile mock
        """


        assert static_tpm_driver_simulator.tpm == False
        assert patched_tpm_driver.communication_state == CommunicationStatus.DISABLED
        patched_tpm_driver.start_communicating()
        assert (
            patched_tpm_driver.communication_state
            == CommunicationStatus.NOT_ESTABLISHED
        )

        # Wait for the message to execute
        time.sleep(1)
        assert static_tpm_driver_simulator.tpm

        expected_read = [2,3,3]
        patched_tpm_driver.write_address(4, expected_read)
        assert patched_tpm_driver.read_address(4, len(expected_read)) == expected_read
    
    def test_configure_40g_core(
        self: TestTPMDriver,
        patched_tpm_driver: PatchedTpmDriver,
        static_tpm_driver_simulator: StaticTpmDriverSimulator,
    ) -> None:
        static_tpm_driver_simulator.connect()

        core_dict = {
            "core_id": 2,
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
            "dst_ip": "3221226219",
            "dst_port": 9000,
        }
        patched_tpm_driver.configure_40g_core(**core_dict)

        configuration = patched_tpm_driver.get_40g_configuration(core_id=core_dict.get("core_id"))

        assert configuration == [core_dict]

        #request the configuration without a core_id
        patched_tpm_driver.configure_40g_core(**core_dict2)
        configuration = patched_tpm_driver.get_40g_configuration()
        assert configuration == [core_dict2,core_dict2]