# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains tests of the TPM driver."""
from __future__ import annotations

import logging
import time
from typing import Union

import pytest
from pyaavs.tile import Tile as Tile12
from pyaavs.tile_wrapper import Tile as HwTile
from ska_control_model import CommunicationStatus
from ska_tango_testing.mock import MockCallableGroup

from ska_low_mccs_spshw.tile import TileSimulator, TpmDriver


@pytest.fixture(name="tpm_version")
def tpm_version_fixture() -> str:
    """
    Return the TPM version.

    :return: the TPM version
    """
    return "tpm_v1_6"


@pytest.fixture(name="tile_id")
def tile_id_fixture() -> int:
    """
    Return the tile id.

    :return: the tile id
    """
    return 1


@pytest.fixture(name="callbacks")
def callbacks_fixture() -> MockCallableGroup:
    """
    Return a dictionary of callables to be used as callbacks.

    :return: a dictionary of callables to be used as callbacks.
    """
    return MockCallableGroup(
        "communication_status",
        "component_state",
        "task",
        timeout=5.0,
    )


@pytest.fixture(name="is_simulation")
def is_simulation_fixture() -> bool:
    """
    Fixture used to define if we are talking to hardware or software.

    :return: true if we are using a software environment.
    """
    return True


@pytest.fixture(name="tpm_cpld_port")
def tpm_cpld_port_fixture() -> int:
    """
    Return the port at which the TPM can be controlled.

    :return: the port at which the TPM can be controlled.
    """
    return 10000


@pytest.fixture(name="tpm_ip")
def tpm_ip_fixture() -> str:
    """
    Return the IP address of the TPM.

    :return: the IP address of the TPM.
    """
    return "0.0.0.0"


@pytest.fixture(name="tile")
def tile_fixture(
    logger: logging.Logger,
    is_simulation: bool,
    tpm_version: str,
    tpm_cpld_port: int,
    tpm_ip: str,
) -> Union[TileSimulator, Tile12]:
    """
    Fixture for creating a tile simulator or a physical tile object.

    This fixture is responsible for creating a tile object for testing purposes.
    Depending on the value of `is_simulation`, it either creates a `TileSimulator`
    object or a `Tile12` object. The created tile object is returned for use in
    the test.

    :param logger: The logger object.
    :param is_simulation: Flag indicating whether to create
        a simulator or physical tile.
    :param tpm_version: The TPM version.
    :param tpm_cpld_port: The TPM CPLD port.
    :param tpm_ip: The TPM IP address.
    :return: The created tile object.
    """
    if is_simulation:
        return TileSimulator(logger)

    return HwTile(ip=tpm_ip, port=tpm_cpld_port, logger=logger, tpm_version=tpm_version)


@pytest.fixture(name="tpm_driver")
def tpm_driver_fixture(
    logger: logging.Logger,
    tile_id: int,
    tpm_version: str,
    callbacks: MockCallableGroup,
    tile: TileSimulator | Tile12,
) -> TpmDriver:
    """
    Return a TPMDriver using a tile.

    :param logger: a object that implements the standard logging
        interface of :py:class:`logging.Logger`
    :param tile_id: the unique ID for the tile
    :param tpm_version: TPM version: "tpm_v1_2" or "tpm_v1_6"
    :param callbacks: dictionary of driver callbacks.
    :param tile: The tile used by the TpmDriver.

    :return: a TpmDriver driving a simulated tile
    """
    return TpmDriver(
        logger,
        tile_id,
        tile,
        tpm_version,
        callbacks["communication_status"],
        callbacks["component_state"],
    )


class TestTpmDriver:
    """
    Integration test class for the TPMDriver.

    This class contains integration tests designed to validate the functionality
    of the TPMDriver in both hardware and software-facing environments. The tests
    are aimed at ensuring the correct interaction and integration between the
    TPMDriver and its underlying components (TileSimulator or HwTile).


    Note: These integration tests may require proper hardware setup or hardware
    simulation environments to run successfully. For example the tpm needs to
    have power, be routable, ....
    """

    @pytest.mark.xfail(reason="This test has not been tested with HwTile")
    def test_communication(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile: Union[TileSimulator, HwTile],
        callbacks: MockCallableGroup,
    ) -> None:
        """
        Test the communication between the tpm_driver and object under test.

        This test verifies that the TPM driver can be successfully created and
        that it can establish communication with the underlying component. It
        involves creating an instance of the tile class object under test, which
        can be either a hardware tile mock (`TileSimulator`) or a physical hardware
        tile (`HwTile`). The callback dictionary is used as a hook for the
        tpm_driver to call.

        :param tpm_driver: The TPM driver instance being tested.
        :param tile: A mock object representing a hardware tile (`TileSimulator`) or
                    a physical hardware tile (`HwTile`).
        :param callbacks: A dictionary of driver callbacks used to mock the
                        underlying component's behavior.
        """
        assert tpm_driver.communication_state == CommunicationStatus.DISABLED

        # start communicating initialises a polling loop that should.
        # - start_connection with the component under test.
        # - update attributes in a polling loop.
        tpm_driver.start_communicating()

        callbacks["communication_status"].assert_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)
        time.sleep(3)
        assert tile.tpm is not None

        # Any subsequent calls to start communicating do not fire a change event
        tpm_driver.start_communicating()
        callbacks["communication_status"].assert_not_called()

        tpm_driver.stop_communicating()
        callbacks["communication_status"].assert_call(CommunicationStatus.DISABLED)
        assert tpm_driver.communication_state == CommunicationStatus.DISABLED

        # Any subsequent calls to stop communicating do not fire a change event
        tpm_driver.stop_communicating()
        callbacks["communication_status"].assert_not_called()
        assert tile.tpm is None

    @pytest.mark.xfail(reason="This test has not been tested with HwTile")
    def test_poll_update(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile: TileSimulator | HwTile,
        callbacks: MockCallableGroup,
    ) -> None:
        """
        Test we can create the driver and start communication with the component.

        We can create the tile class object under test, and we will mock
        the underlying component.

        :param tpm_driver: the tpm driver under test.
        :param tile: An hardware tile mock
        :param callbacks: dictionary of driver callbacks.
        """
        assert tpm_driver.communication_state == CommunicationStatus.DISABLED

        # start communicating initialises a polling loop that should.
        # - start_connection with the component under test.
        # - update attributes in a polling loop.
        pre_poll_temperature = tpm_driver._tile_health_structure["temperature"]["FPGA0"]

        tpm_driver.start_communicating()
        callbacks["communication_status"].assert_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)

        # Simulate a temperature change (only necessary for simulation)
        tile._fpga1_temperature = 41.0

        # Wait for 2 complete polls to ensure a poll has occurred
        poll_time = tpm_driver._poll_rate
        time.sleep(poll_time * 2 + 0.5)

        post_poll_temperature = tpm_driver._tile_health_structure["temperature"][
            "FPGA0"
        ]

        # Check that the temperature has changed
        assert pre_poll_temperature != post_poll_temperature

        pre_poll_temperature = tpm_driver._tile_health_structure["temperature"]["FPGA0"]

        # Stop communicating to stop the polling loop, ensuring static values
        tpm_driver.stop_communicating()

        # Simulate a temperature change (only necessary for simulation)
        tile._fpga1_temperature = (
            tpm_driver._tile_health_structure["temperature"]["FPGA0"] + 1
        )

        # Simulate a temperature change (only necessary for simulation)
        time.sleep(poll_time * 2 + 0.5)

        post_poll_temperature = tpm_driver._tile_health_structure["temperature"][
            "FPGA0"
        ]

        # Note: A pass in software is sufficient for this final assert.
        assert pre_poll_temperature == post_poll_temperature

    @pytest.mark.xfail(reason="This test has not been tested with HwTile")
    @pytest.mark.parametrize(
        ("attribute"),
        [
            ("voltages"),
            ("temperatures"),
            ("currents"),
            ("io"),
            ("dsp"),
            ("board_temperature"),
            ("voltage_mon"),
            ("fpga1_temperature"),
            ("fpga2_temperature"),
            ("register_list"),
            ("timing"),
            ("station_id"),
            ("tile_id"),
            ("is_programmed"),
            ("firmware_version"),
            ("firmware_name"),
            ("firmware_available"),
            ("hardware_version"),
            ("tpm_status"),
            ("adc_rms"),
            ("fpgas_time"),
            ("fpga_reference_time"),
            ("fpga_current_frame"),
            ("pps_delay"),
            ("arp_table"),
            ("channeliser_truncation"),
            ("static_delays"),
            ("csp_rounding"),
            ("preadu_levels"),
            ("pps_present"),
            ("clock_present"),
            ("sysref_present"),
            ("pll_locked"),
            ("beamformer_table"),
            ("current_tile_beamformer_frame"),
            ("is_beamformer_running"),
            ("pending_data_requests"),
            ("phase_terminal_count"),
            ("test_generator_active"),
        ],
    )
    def test_dumb_read(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        attribute: str,
    ) -> None:
        """
        Test the dumb read functionality.

        Validate that it can be called without error.

        :param tpm_driver: The TPM driver instance being tested.
        :param attribute: The attribute to be read.
        """
        _ = getattr(tpm_driver, attribute)

    @pytest.mark.xfail(reason="This test has not been tested with HwTile")
    def test_write_read_registers(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile: TileSimulator,
    ) -> None:
        """
        Test we can write values to a register.

        Using a tile to mock the functionality
        of writing to a register

        :param tpm_driver: The tpm driver under test.
        :param tile: The mocked tile
        """
        # No UDP connection are used here. The tile
        # constructs a mocked TPM
        # Therefore the tile will have access to the TPM after connect().
        tile.connect()
        assert tile.tpm is not None

        tile.tpm.write_register("fpga1.1", 3)
        tile.tpm.write_register("fpga2.2", 2)
        tile.tpm.write_register("fpga1.dsp_regfile.stream_status.channelizer_vld", 2)

        # write to fpga1
        # write_register(register_name, values, offset, device)
        tpm_driver.write_register("1", 17)
        read_value = tpm_driver.read_register("1")
        assert read_value == [17]

        # test write to unknown register
        tpm_driver.write_register("unknown", 17)
        read_value = tpm_driver.read_register("unknown")
        assert read_value == []

        # write to fpga2
        tpm_driver.write_register("2", 17)
        read_value = tpm_driver.read_register("2")
        assert read_value == [17]

        # test write to unknown register
        tpm_driver.write_register("unknown", 17)
        read_value = tpm_driver.read_register("unknown")
        assert read_value == []

        # write to register with no associated device
        tpm_driver.write_register(
            "fpga1.dsp_regfile.stream_status.channelizer_vld",
            17,
        )
        read_value = tpm_driver.read_register(
            "fpga1.dsp_regfile.stream_status.channelizer_vld"
        )
        assert read_value == [17]

        # test write to unknown register
        tpm_driver.write_register("unknown", 17)
        read_value = tpm_driver.read_register("unknown")
        assert read_value == []

        # test register that returns list
        read_value = tpm_driver.read_register("mocked_list")
        assert read_value == []
