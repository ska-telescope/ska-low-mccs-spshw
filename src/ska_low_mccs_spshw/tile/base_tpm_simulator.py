#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""An implementation of a TPM simulator."""

from __future__ import annotations  # allow forward references in type hints

import copy
import logging
import random
import threading
import time
from typing import Any, Callable, Final, Optional

import numpy as np
from ska_control_model import CommunicationStatus, TaskStatus

from .tile_data import TileData
from .tpm_status import TpmStatus

__all__ = ["BaseTpmSimulator"]


# pylint: disable=too-many-lines,too-many-instance-attributes,too-many-public-methods
class BaseTpmSimulator:
    """
    A mock TPMDriver for testing tile_component_manager.

    :todo: The current TPM driver has a wrapper to make it consistent
        with the interface of this simulator. It would be more better if
        we updated this simulator's interface to better reflect the
        natural interface of the driver that it is simulating.
    :todo: The initialiser for this class accepts a component fault
        callback, but at present there is nothing implemented to allow
        this simulator to simulate a fault state that would warrant the
        callback being called.
    """

    ADC_RMS = tuple(float(i) for i in range(32))
    FPGAS_TIME = [1, 2]
    CURRENT_TILE_BEAMFORMER_FRAME: Final = 23
    PPS_DELAY: Final = 12
    PHASE_TERMINAL_COUNT: Final = 0
    FIRMWARE_NAME: Final = "itpm_v1_6.bit"
    FIRMWARE_AVAILABLE: dict[str, dict[str, str | int]] = {
        "itpm_v1_6.bit": {"design": "model1", "major": 2, "minor": 3},
        "itpm_v1_5.bit": {"design": "model2", "major": 3, "minor": 7},
        "itpm_v1_2.bit": {"design": "model3", "major": 2, "minor": 6},
    }

    REGISTER_MAP: dict[str, list[int]] = {
        "test-reg1": [0] * 4,
        "test-reg2": [0],
        "test-reg3": [0],
        "test-reg4": [0],
    }
    _GLOBAL_STATUS_ALARMS: dict[str, int] = {
        "I2C_access_alm": 0,
        "temperature_alm": 0,
        "voltage_alm": 0,
        "SEM_wd": 0,
        "MCU_wd": 0,
    }
    # ARP resolution table
    # Values are consistent with unit test test_MccsTile
    #
    ARP_MAP = {
        "10.0.23.56": 0x10FEFA060B99,
        "10.0.98.3": 0x10FEED080B59,
        "10.0.98.4": 0x10FEED080B57,
        "10.0.99.3": 0x10FEED080A58,
        "10.0.99.4": 0x10FEED080A56,
    }
    # Matches tests.unit.tile.test_tile_device.TestMccsTileCommands.test_get_arp_table
    ARP_TABLE = {0: [0, 1], 1: [1]}
    # TPM version: "tpm_v1_2" or "tpm_v1_6"
    TPM_VERSION = 120
    CLOCK_SIGNALS_OK = True
    STATIC_DELAYS = [0.0] * 32
    CSP_ROUNDING = [3] * 384
    PREADU_LEVELS = [16.0] * 32
    CHANNELISER_TRUNCATION = [4] * 512

    def _arp(self: BaseTpmSimulator, ip: str) -> str:
        """
        Return MAC address from ARP resolution table Private method for the simulator.

        :param ip: IP address in dot decimal format

        :return: MAC address in xx:xx:xx:xx:xx:xx format
        """
        if ip in self.ARP_MAP:
            mac = self.ARP_MAP[ip]
            mac_str = f"{mac:012x}"
            arp = ":".join(mac_str[i : (i + 2)] for i in range(0, 12, 2))
            return arp
        return "ff:ff:ff:ff:ff:ff"

    def __init__(
        self: BaseTpmSimulator,
        logger: logging.Logger,
        communication_state_changed: Optional[Callable[..., None]] = None,
        component_state_changed_callback: Optional[Callable[..., None]] = None,
    ) -> None:
        """
        Initialise a new TPM simulator instance.

        :param logger: a logger for this simulator to use
        :param communication_state_changed: callback to be called
            when the communication state changes.
        :param component_state_changed_callback: callback to be
            called when the component state changes
        """
        self.logger = logger
        self._component_state_changed_callback = component_state_changed_callback
        self._communication_state_changed = communication_state_changed
        self._is_programmed = False
        self._tpm_status = TpmStatus.UNPROGRAMMED
        self._is_beamformer_running = False
        self._phase_terminal_count = self.PHASE_TERMINAL_COUNT
        self._station_id = 0
        self._tile_id = 0

        self._tile_health_structure: dict[Any, Any] = copy.deepcopy(
            TileData.TILE_MONITORING_POINTS
        )
        self._adc_rms = tuple(self.ADC_RMS)
        self._current_tile_beamformer_frame = self.CURRENT_TILE_BEAMFORMER_FRAME
        self._pps_delay = self.PPS_DELAY
        self._pps_delay_correction = 0
        self._firmware_name = self.FIRMWARE_NAME
        self._firmware_available = copy.deepcopy(self.FIRMWARE_AVAILABLE)
        self._arp_table = copy.deepcopy(self.ARP_TABLE)
        self._fpgas_time = copy.deepcopy(self.FPGAS_TIME)

        self._address_map: dict[str, int] = {}
        self._forty_gb_core_list: list[dict[str, Any]] = []
        self._register_map = copy.deepcopy(self.REGISTER_MAP)
        self._test_generator_active = False
        self._pending_data_requests = False
        self._fpga_current_frame = 0
        self._fpga_reference_time = 0
        self._phase_terminal_count = self.PHASE_TERMINAL_COUNT
        self._pps_present = self.CLOCK_SIGNALS_OK
        self._clock_present = self.CLOCK_SIGNALS_OK
        self._sysref_present = self.CLOCK_SIGNALS_OK
        self._pll_locked = self.CLOCK_SIGNALS_OK
        # Configuration table cache
        self._beamformer_table = [[0, 0, 0, 0, 0, 0, 0]] * 48  # empty beamformer table
        self._static_delays = self.STATIC_DELAYS
        self._csp_rounding = self.CSP_ROUNDING
        self._preadu_levels: list[float] = self.PREADU_LEVELS
        self._channeliser_truncation = self.CHANNELISER_TRUNCATION
        self._is_last: bool
        self._is_first: bool
        self.communication_state = CommunicationStatus.NOT_ESTABLISHED
        self._mocked_communication_failure = False
        self._global_status_alarm = self._GLOBAL_STATUS_ALARMS
        self.frame_time = "1970-01-01T00:00:00.000000Z"
        self._formatted_fpga_reference_time = "1970-01-01T00:00:00.000000Z"
        self.power_locked = False

    def ping(self: BaseTpmSimulator) -> None:
        """
        Check we can connect to the TPM.

        :raises ConnectionError: when we fail to connect to the TPM.
        """
        if self._mocked_communication_failure:
            raise ConnectionError("Failed to connect")

    def check_global_status_alarms(self: BaseTpmSimulator) -> dict:
        """
        Check global status alarms.

        :return: a dictionary with global health alarms.

        :raises ConnectionError: when we fail to connect to the TPM.
        """
        if self._mocked_communication_failure:
            raise ConnectionError("Failed to connect")
        return self._global_status_alarm

    def connect(self: BaseTpmSimulator) -> None:
        """
        Check we can connect to the TPM.

        :raises ConnectionError: when we fail to connect to the TPM.
        """
        if self._mocked_communication_failure:
            raise ConnectionError("Failed to connect")

    def get_health_status(self: BaseTpmSimulator) -> dict[str, Any]:
        """
        Get the health status from TPM.

        :return: a dictionary containing multiple monitoring points.
        """
        return self._tile_health_structure

    def get_station_id(self: BaseTpmSimulator) -> int:
        """
        Return the station id.

        :return: the station id
        """
        return self._station_id

    def get_beamformer_table(self: BaseTpmSimulator) -> list[list[int]]:
        """
        Return the beamformer table.

        :return: the beamformer table
        """
        return self._beamformer_table

    @property
    def firmware_available(
        self: BaseTpmSimulator,
    ) -> dict[str, dict[str, Any]]:
        """
        Return the firmware list for this TPM simulator.

        :return: the firmware list
        """
        self.logger.debug("TpmSimulator: firmware_available")
        return copy.deepcopy(self._firmware_available)

    @property
    def firmware_name(self: BaseTpmSimulator) -> str:
        """
        Return the name of the firmware that this TPM simulator is running.

        :return: firmware name
        """
        self.logger.debug("TpmSimulator: firmware_name")
        return self._firmware_name

    @firmware_name.setter
    def firmware_name(self: BaseTpmSimulator, value: str) -> None:
        """
        Set firmware name.

        :param value: assigned default firmware name. Can be overriden by
            parameter of download_firmware
        """
        self._firmware_name = value

    @property
    def firmware_version(self: BaseTpmSimulator) -> str:
        """
        Return the name of the firmware that this TPM simulator is running.

        :return: firmware version (major.minor)
        """
        self.logger.debug("TpmSimulator: firmware_version")
        firmware = self._firmware_available[self._firmware_name]
        return f"{firmware['major']}.{firmware['minor']}"

    @property
    def is_programmed(self: BaseTpmSimulator) -> bool:
        """
        Return whether this TPM is programmed (ie. firmware has been downloaded to it).

        :return: whether this TPM is programmed
        """
        self.logger.debug(f"TpmSimulator: is_programmed {self._is_programmed}")
        return self._is_programmed

    def mock_on(self: BaseTpmSimulator) -> None:
        """Simulate an ON TPM."""
        self.logger.error("Mocking on")
        if not self.power_locked:
            self._mocked_communication_failure = False

    def mock_off(self: BaseTpmSimulator) -> None:
        """Simulatean ON TPM."""
        self.logger.error("Mocking off")
        if not self.power_locked:
            self._mocked_communication_failure = True

    def frame_from_utc_time(self: BaseTpmSimulator, utc_time: str) -> int:
        """
        Return the frame from utc time.

        :param utc_time: the time in UTC format

        :returns: the from from utc time.
        """
        return 4

    @property
    def hardware_version(self: BaseTpmSimulator) -> int:
        """
        Return whether this TPM is 1.2 or 1.6.

        :return: TPM hardware version. 120 or 160
        """
        return self.TPM_VERSION

    def download_firmware(
        self: BaseTpmSimulator,
        bitfile: str,
        task_callback: Optional[Callable] = None,
    ) -> None:
        """
        Download the provided firmware bitfile onto the TPM.

        :param bitfile: the bitfile to be downloaded
        :param task_callback: A callback to call with updates of the
            command progress.
        """
        if task_callback:
            task_callback(status=TaskStatus.QUEUED)
            task_callback(status=TaskStatus.IN_PROGRESS)
        self.logger.debug("TpmSimulator: download_firmware")
        self._firmware_name = bitfile
        self._is_programmed = True
        self._set_tpm_status(TpmStatus.PROGRAMMED)
        if task_callback:
            task_callback(
                status=TaskStatus.COMPLETED,
                result="Firmware successfully downloaded",
            )

    def erase_fpga(self: BaseTpmSimulator) -> None:
        """Erase the firmware form the FPGA, to reduce power."""
        self.logger.debug("TpmSimulator: erase_fpga")
        self._is_programmed = False
        self._set_tpm_status(TpmStatus.UNPROGRAMMED)

    def get_arp_table(self: BaseTpmSimulator) -> None:
        """
        Get the arp table.

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: get_arp_table")
        raise NotImplementedError

    def initialise(
        self: BaseTpmSimulator,
        program_fpga: bool,
        pps_delay_correction: int,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Real TPM driver performs connectivity checks, programs and initialises the TPM.

        The simulator will emulate programming the firmware.

        :param program_fpga: True if we want to program the fpga.
        :param pps_delay_correction: the delay correction to
            apply to the pps signal.
        :param task_callback: A callback to call with updates of the
            command progress.
        :param task_abort_event: Check for abort, defaults to None
        """
        if task_callback:
            task_callback(status=TaskStatus.QUEUED)
            task_callback(status=TaskStatus.IN_PROGRESS)
        # self._tile_id = tile_id
        self.download_firmware(self._firmware_name)
        self._set_tpm_status(TpmStatus.PROGRAMMED)
        self._set_tpm_status(TpmStatus.INITIALISED)
        time.sleep(random.randint(1, 4))
        if task_callback:
            task_callback(
                status=TaskStatus.COMPLETED,
                result="The initialisation task has completed",
            )

    #
    # Properties
    #
    @property
    def tpm_status(self: BaseTpmSimulator) -> TpmStatus:
        """
        Get the tpm status.

        :return: tpm status
        """
        return self._tpm_status

    @tpm_status.setter
    def tpm_status(self: BaseTpmSimulator, new_status: TpmStatus) -> None:
        """
        Set the TPM status local attribute and call the callback if changed.

        :param new_status: the new value for the _tpm_status
        """
        self._set_tpm_status(new_status)

    def _set_tpm_status(self: BaseTpmSimulator, new_status: TpmStatus) -> None:
        """
        Set the TPM status local attribute and call the callback if changed.

        :param new_status: the new value for the _tpm_status
        """
        self.logger.debug(f"set tpm status - old:{self._tpm_status} new:{new_status}")
        if new_status != self._tpm_status:
            self._tpm_status = new_status
            if self._component_state_changed_callback is not None:
                self._component_state_changed_callback(programming_state=new_status)

    @property
    def tile_id(self: BaseTpmSimulator) -> int:
        """
        Tile ID.

        :return: assigned tile Id value
        """
        return self._tile_id

    @tile_id.setter
    def tile_id(self: BaseTpmSimulator, value: int) -> None:
        """
        Set Tile ID.

        :param value: assigned tile Id value
        """
        self._tile_id = value

    @property
    def station_id(self: BaseTpmSimulator) -> int:
        """
        Station ID.

        :return: assigned station Id value
        """
        return self._station_id

    @station_id.setter
    def station_id(self: BaseTpmSimulator, value: int) -> None:
        """
        Set Station ID.

        :param value: assigned station Id value
        """
        self._station_id = value

    @property
    def board_temperature(self: BaseTpmSimulator) -> float:
        """
        Return the temperature of the TPM.

        :raises NotImplementedError: if this method has not been
            implemented by a subclass
        """
        raise NotImplementedError(
            "BaseTpmSimulator is abstract; property 'board_temperature' must be "
            "implemented in a subclass."
        )

    @property
    def voltage_mon(self: BaseTpmSimulator) -> float:
        """
        Return the internal 5V supply of the TPM.

        :raises NotImplementedError: if this method has not been
            implemented by a subclass
        """
        raise NotImplementedError(
            "BaseTpmSimulator is abstract; property 'voltage_mon' must be "
            "implemented in a subclass."
        )

    @property
    def fpga1_temperature(self: BaseTpmSimulator) -> float:
        """
        Return the temperature of FPGA 1.

        :raises NotImplementedError: if this method has not been
            implemented by a subclass
        """
        raise NotImplementedError(
            "BaseTpmSimulator is abstract; property 'fpga1_temperature' must be "
            "implemented in a subclass."
        )

    @property
    def fpga2_temperature(self: BaseTpmSimulator) -> float:
        """
        Return the temperature of FPGA 2.

        :raises NotImplementedError: if this method has not been
            implemented by a subclass
        """
        raise NotImplementedError(
            "BaseTpmSimulator is abstract; property 'fpga2_temperature' must be "
            "implemented in a subclass."
        )

    @property
    def adc_rms(self: BaseTpmSimulator) -> tuple[float, ...]:
        """
        Return the RMS power of the TPM's analog-to-digital converter.

        :return: the RMS power of the TPM's ADC
        """
        self.logger.debug("TpmSimulator: adc_rms")
        return self._adc_rms

    @property
    def fpgas_time(self: BaseTpmSimulator) -> list[int]:
        """
        Return the FPGAs clock time.

        Useful for detecting clock skew, propagation delays, contamination delays, etc.

        :return: the FPGAs clock time
        """
        self.logger.debug("TpmSimulator: fpgas_time")
        # self._fpgas_time[0] = int(time.time())
        # self._fpgas_time[1] = self._fpgas_time[0]
        return self._fpgas_time

    @property
    def pps_delay(self: BaseTpmSimulator) -> float:
        """
        Return the PPS delay of the TPM.

        :return: PPS delay
        """
        self.logger.debug("TpmSimulator: get_pps_delay")
        return self._pps_delay

    @property
    def pps_delay_correction(self: BaseTpmSimulator) -> int:
        """
        Return last measured ppsdelay correction.

        :return: PPS delay correction in nanoseconds. Rounded to 1.25 ns units
        """
        return self._pps_delay_correction

    @property
    def register_list(self: BaseTpmSimulator) -> list[str]:
        """
        Return a list of registers available on each device.

        :return: list of registers
        """
        return list(self._register_map.keys())

    @property
    def pps_present(self: BaseTpmSimulator) -> bool:
        """
        Check if PPS signal is present.

        :return: True if PPS is present. Checked in poll loop, cached
        """
        return self._pps_present

    @property
    def clock_present(self: BaseTpmSimulator) -> bool:
        """
        Check if 10 MHz clock signal is present.

        :return: True if 10 MHz clock is present. Checked in poll loop, cached
        """
        return self._clock_present

    @property
    def sysref_present(self: BaseTpmSimulator) -> bool:
        """
        Check if SYSREF signal is present.

        :return: True if SYSREF is present. Checked in poll loop, cached
        """
        return self._sysref_present

    @property
    def pll_locked(self: BaseTpmSimulator) -> bool:
        """
        Check if ADC clock PLL is locked.

        :return: True if PLL is locked. Checked in poll loop, cached
        """
        return self._pll_locked

    @property
    def channeliser_truncation(self: BaseTpmSimulator) -> list[int]:
        """
        Read the cached value for the channeliser truncation.

        :return: cached value for the channeliser truncation
        """
        return copy.deepcopy(self._channeliser_truncation)

    @channeliser_truncation.setter
    def channeliser_truncation(
        self: BaseTpmSimulator, truncation: int | list[int]
    ) -> None:
        """
        Set the channeliser truncation.

        :param truncation: number of LS bits discarded after channelisation.
            Either a signle value or a list of one value per physical frequency channel
            0 means no bits discarded, up to 7. 3 is the correct value for a uniform
            white noise.
        """
        if isinstance(truncation, int):
            self._channeliser_truncation = [
                truncation
            ] * TileData.NUM_FREQUENCY_CHANNELS
        else:  # list or numpy.ndarray
            self._channeliser_truncation = list(truncation)

    @property
    def static_delays(self: BaseTpmSimulator) -> list[float]:
        """
        Read the cached value for the static delays, in sample.

        :return: static delay, in samples one per TPM input
        """
        return copy.deepcopy(self._static_delays)

    @static_delays.setter
    def static_delays(self: BaseTpmSimulator, delays: list[float]) -> None:
        """
        Set the static delays.

        :param delays: Delay in nanoseconds, nominal = 0, positive delay adds
            delay to the signal stream

        :param delays: Static zenith delays, one per input channel
        """
        self._static_delays = delays

    @property
    def csp_rounding(self: BaseTpmSimulator) -> list[int]:
        """
        Read the cached value for the final rounding in the CSP samples.

        Need to be specfied only for the last tile
        :return: Final rounding for the CSP samples. Up to 384 values
        """
        return copy.deepcopy(self._csp_rounding)

    @csp_rounding.setter
    def csp_rounding(self: BaseTpmSimulator, rounding: list[int] | int) -> None:
        """
        Set the final rounding in the CSP samples, one value per beamformer channel.

        :param rounding: Number of bits rounded in final 8 bit requantization to CSP
        """
        if isinstance(rounding, int):
            self._csp_rounding = [rounding] * TileData.NUM_BEAMFORMER_CHANNELS
        else:
            self._csp_rounding = rounding

    @property
    def preadu_levels(self: BaseTpmSimulator) -> list[float]:
        """
        Get preadu levels in dB.

        :return: cached values of Preadu attenuation level in dB
        """
        return copy.deepcopy(self._preadu_levels)

    @preadu_levels.setter
    def preadu_levels(self: BaseTpmSimulator, levels: list[float]) -> None:
        """
        Set preadu levels in dB.

        :param levels: Preadu attenuation levels in dB
        """
        self._preadu_levels = levels

    def read_register(
        self: BaseTpmSimulator,
        register_name: str,
    ) -> Optional[list[int]]:
        """
        Read the values in a register.

        :param register_name: name of the register

        :return: values read from the register
        """
        values = self._register_map.get(register_name)
        return values

    def write_register(
        self: BaseTpmSimulator,
        register_name: str,
        values: list[int],
    ) -> None:
        """
        Read the values in a register.

        :param register_name: name of the register
        :param values: values to write
        """
        if register_name != "" or register_name != "unknown":
            self._register_map.update({register_name: values})

    def read_address(
        self: BaseTpmSimulator, address: int, nvalues: int = 1
    ) -> list[int]:
        """
        Return a list of values from a given address.

        :param address: address of start of read
        :param nvalues: number of values to read

        :return: values at the address
        """
        values = []
        for i in range(nvalues):
            key = str(address + i)
            values.append(self._address_map.get(key, 0))
        return values

    def write_address(self: BaseTpmSimulator, address: int, values: list[int]) -> None:
        """
        Write a list of values to a given address.

        :param address: address of start of read
        :param values: values to write
        """
        for i, value in enumerate(values):
            key = str(address + i)
            self._address_map.update({key: value})

    # pylint: disable=too-many-arguments
    def configure_40g_core(
        self: BaseTpmSimulator,
        core_id: int = 0,
        arp_table_entry: int = 0,
        src_mac: Optional[int] = None,
        src_ip: Optional[str] = None,
        src_port: Optional[int] = None,
        dst_ip: Optional[str] = None,
        dst_port: Optional[int] = None,
        rx_port_filter: Optional[int] = None,
        netmask: Optional[int] = None,
        gateway_ip: Optional[int] = None,
    ) -> None:
        """
        Configure the 40G code.

        The dst_mac parameter is ignored in true 40G core (ARP resolution used instead)

        :param core_id: id of the core
        :param arp_table_entry: ARP table entry to use
        :param src_mac: MAC address of the source
        :param src_ip: IP address of the source
        :param src_port: port of the source
        :param dst_ip: IP address of the destination
        :param dst_port: port of the destination
        :param rx_port_filter: Filter for incoming packets
        :param netmask: Netmask
        :param gateway_ip: Gateway IP

        :raises ValueError: Invalid core or ARP table entry
        """
        core_dict = {
            "core_id": core_id,
            "arp_table_entry": arp_table_entry,
            "src_mac": src_mac,
            "src_ip": src_ip,
            "src_port": src_port,
            "dst_ip": dst_ip,
            "dst_port": dst_port,
            "rx_port_filter": rx_port_filter,
            "netmask": netmask,
            "gateway_ip": gateway_ip,
        }
        if core_id not in [0, 1] or arp_table_entry not in range(8):
            raise ValueError("Invalid core or ARP table entry")

        self._forty_gb_core_list.append(core_dict)

    def get_40g_configuration(
        self: BaseTpmSimulator,
        core_id: int = -1,
        arp_table_entry: int = 0,
    ) -> dict | list[dict] | None:
        """
        Return a 40G configuration.

        :param core_id: id of the core for which a configuration is to
            be return. Defaults to -1, in which case all cores
            configurations are returned, defaults to -1
        :param arp_table_entry: ARP table entry to use

        :return: core configuration or list of core configurations
        """
        if core_id == -1:
            return self._forty_gb_core_list
        for item in self._forty_gb_core_list:
            if item.get("core_id") == core_id:
                return [item]
        return []

    @property
    def arp_table(self: BaseTpmSimulator) -> dict[int, list[int]]:
        """
        Check that ARP table has been populated in for all used cores.

        40G interfaces use cores 0 (fpga0) and 1(fpga1) and ARP ID 0 for beamformer,
        1 for LMC. 10G interfaces use cores 0,1 (fpga0) and 4,5 (fpga1) for
        beamforming, and 2, 6 for LMC with only one ARP.

        :return: dictionary containing coreID and populated arpID
        """
        self.logger.debug("TpmSimulator: arp_table")
        return copy.deepcopy(self._arp_table)

    @property
    def fpga_reference_time(self: BaseTpmSimulator) -> int:
        """
        Return reference time for timestamp.

        :return: reference time
        """
        return self._fpga_reference_time

    @property
    def fpga_current_frame(self: BaseTpmSimulator) -> int:
        """
        Return current frame from timestamp.

        :return: current frame
        """
        if self._fpga_reference_time == 0:
            return 0
        # return int(
        #    (time.time()-self._fpga_reference_time)/(TileData.FRAME_PERIOD))
        # TODO Modify testbenches to expect realistic time from the TPM
        return 1000000

    @property
    def fpga_frame_time(self: BaseTpmSimulator) -> str:
        """
        Return current frame from timestamp.

        :return: current frame
        """
        return self.frame_time

    @property
    def formatted_fpga_reference_time(self: BaseTpmSimulator) -> str:
        """
        Return formatted frame time.

        :return: current frame
        """
        return self._formatted_fpga_reference_time

    # pylint: disable=too-many-arguments
    def set_lmc_download(
        self: BaseTpmSimulator,
        mode: str,
        payload_length: int = 1024,
        dst_ip: Optional[str] = None,
        src_port: int = 0xF0D0,
        dst_port: int = 4660,
    ) -> None:
        """
        Specify whether control data will be transmitted over 1G or 40G networks.

        :param mode: "1G" or "10G"
        :param payload_length: SPEAD payload length for integrated
            channel data, defaults to 1024
        :param dst_ip: destination IP, defaults to None
        :param src_port: sourced port, defaults to 0xF0D0
        :param dst_port: destination port, defaults to 4660
        """
        self.logger.debug("TpmSimulator: set_lmc_download")
        if dst_ip is None:
            dst_ip = "0.0.0.0"
        for core in (0, 1):
            self.configure_40g_core(
                core,
                1,
                src_ip="0.0.0.0",
                src_mac=0x600001000000,
                dst_ip=dst_ip,
                src_port=src_port,
                dst_port=dst_port,
            )

    # pylint: disable=too-many-arguments
    def send_data_samples(
        self: BaseTpmSimulator,
        data_type: str = "",
        timestamp: int = 0,
        seconds: float = 0.2,
        n_samples: int = 1024,
        sync: bool = False,
        first_channel: int = 0,
        last_channel: int = 511,
        channel_id: int = 128,
        frequency: float = 150.0e6,
        round_bits: int = 3,
    ) -> None:
        """
        Front end for send_xxx_data methods.

        :param data_type: sample type. "raw", "channel", "channel_continuous",
                "narrowband", "beam"
        :param timestamp: Timestamp for start sending data. Default 0 start now
        :param seconds: Delay if timestamp is not specified. Default 0.2 seconds
        :param n_samples: number of samples to send per packet
        :param sync: (raw) send synchronised antenna samples, vs. round robin
        :param first_channel: (channel) first channel to send, default 0
        :param last_channel: (channel) last channel to send, default 511
        :param channel_id: (channel_continuous) channel to send
        :param frequency: (narrowband) Sky frequency for band centre, in Hz
        :param round_bits: (narrowband) how many bits to round

        :raises ValueError: if values wrong
        """
        # Check for type of data to be sent to LMC
        if data_type == "channel_continuous":
            self._pending_data_requests = True
        else:
            self._pending_data_requests = False
        if data_type not in [
            "raw",
            "channel",
            "channel_continuous",
            "narrowband",
            "beam",
        ]:
            raise ValueError(f"Unknown sample type: {data_type}")

    def set_beamformer_regions(
        self: BaseTpmSimulator, regions: list[list[int]]
    ) -> None:
        """
        Set the frequency regions to be beamformed into a single beam.

        :param regions: a list encoding up to 48 regions, with each region containing:

            * start_channel - (int) region starting channel, must be even in
                range 0 to 510
            * num_channels - (int) size of the region, must be a multiple of 8
            * beam_index - (int) beam used for this region with range 0 to 47
            * subarray_id - (int) Subarray
            * subarray_logical_channel - (int) logical channel # in the subarray
            * subarray_beam_id - (int) ID of the subarray beam
            * substation_id - (int) Substation
            * aperture_id:  ID of the aperture (station*100+substation?)
        """
        self.logger.debug("TpmSimulator: set_beamformer_regions")
        for block in range(48):
            self._beamformer_table[block] = [0, 0, 0, 0, 0, 0, 0]
        block = 0
        for region in regions:
            num_blocks = int(np.ceil(region[1] / 8.0))
            channel = region[0]
            logical_channel = region[4]
            for i in range(num_blocks):
                table_entry = region[1:8]
                table_entry[0] = channel
                table_entry[3] = logical_channel
                self._beamformer_table[block] = table_entry
                channel = channel + 8
                logical_channel = logical_channel + 8
                block = block + 1

    def initialise_beamformer(
        self: BaseTpmSimulator,
        start_channel: int,
        nof_channels: int,
        is_first: bool,
        is_last: bool,
    ) -> None:
        """
        Initialise the beamformer.

        :param start_channel: the start channel
        :param nof_channels: number of channels
        :param is_first: whether this is the first (?)
        :param is_last: whether this is the last (?)
        """
        self.logger.debug("TpmSimulator: initialise_beamformer")
        self._is_first = is_first
        self._is_last = is_last
        if nof_channels > 0:
            self.set_beamformer_regions(
                [[start_channel, nof_channels, 0, 0, 0, 0, 0, 0]]
            )

    @property
    def beamformer_table(self: BaseTpmSimulator) -> list[list[int]]:
        """
        Fetch internal beamformer table.

        Fetch table used by the hardware beamformer to define beams and logical bands
        :return: bidimensional table, with 48 entries, one every 8 channels

            * start physical channel
            * tile hardware beam
            * subarray ID
            * subarray start logical channel
            * subarray_beam_id - (int) ID of the subarray beam
            * substation_id - (int) Substation
            * aperture_id:  ID of the aperture (station*100+substation?)
        """
        return copy.deepcopy(self._beamformer_table)

    def load_calibration_coefficients(
        self: BaseTpmSimulator,
        antenna: int,
        calibration_coefficients: list[int],
    ) -> None:
        """
        Load calibration coefficients.

        These may include any rotation matrix (e.g. the
        parallactic angle), but do not include the geometric delay.

        :param antenna: the antenna to which the coefficients apply
        :param calibration_coefficients: a bidirectional complex array of
            coefficients, flattened into a list

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: load_calibration_coefficients")
        raise NotImplementedError

    def apply_calibration(self: BaseTpmSimulator, switch_time: int = 0) -> None:
        """
        Switch the calibration bank.

        (i.e. apply the calibration coefficients previously loaded by
        :py:meth:`load_calibration_coefficients`).

        :param switch_time: an optional time at which to perform the
            switch

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: apply_calibration")
        raise NotImplementedError

    def load_pointing_delays(
        self: BaseTpmSimulator, delay_array: list[float], beam_index: int
    ) -> None:
        """
        Specify the delay in seconds and the delay rate in seconds/second.

        The delay_array specifies the delay and delay rate for each antenna.
        beam_index specifies which beam is desired (range 0-7)

        :param delay_array: delay in seconds, and delay rate in seconds/second
        :param beam_index: the beam to which the pointing delay should
            be applied

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: set_pointing_delay")
        raise NotImplementedError

    def apply_pointing_delays(
        self: BaseTpmSimulator, load_time: Optional[int] = 0
    ) -> None:
        """
        Load the pointing delay at a specified time.

        :param load_time: time at which to load the pointing delay

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: load_pointing_delay")
        raise NotImplementedError

    def start_beamformer(
        self: BaseTpmSimulator,
        start_time: int = 0,
        duration: int = -1,
        subarray_beam_id: int = 1,
        scan_id: int = 0,
    ) -> None:
        """
        Start the beamformer at the specified time.

        :param start_time: time at which to start the beamformer,
            defaults to 0
        :param duration: duration for which to run the beamformer,
            defaults to -1 (run forever)
        :param subarray_beam_id: ID of the subarray beam to start. Default = -1, all
        :param scan_id: ID of the scan which is started.
        """
        self.logger.debug("TpmSimulator: Start beamformer")
        self._is_beamformer_running = True

    def stop_beamformer(self: BaseTpmSimulator) -> None:
        """Stop the beamformer."""
        self.logger.debug("TpmSimulator: Stop beamformer")
        self._is_beamformer_running = False

    def configure_integrated_channel_data(
        self: BaseTpmSimulator,
        integration_time: float = 0.5,
        first_channel: int = 0,
        last_channel: int = 511,
    ) -> None:
        """
        Configure the integrated channel data with the provided integration time.

        :param integration_time: integration time in seconds, defaults to 0.5
        :param first_channel: first channel
        :param last_channel: last channel

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: configure_integrated_channel_data")
        raise NotImplementedError

    def configure_integrated_beam_data(
        self: BaseTpmSimulator,
        integration_time: float = 0.5,
        first_channel: int = 0,
        last_channel: int = 191,
    ) -> None:
        """
        Configure the integrated beam data with the provided integration time.

        :param integration_time: integration time in seconds, defaults to 0.5
        :param first_channel: first channel
        :param last_channel: last channel

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: configure_integrated_beam_data")
        raise NotImplementedError

    def stop_integrated_data(self: BaseTpmSimulator) -> None:
        """
        Stop the integrated data.

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: Stop integrated data")
        raise NotImplementedError

    def stop_data_transmission(self: BaseTpmSimulator) -> None:
        """Stop data transmission."""
        self.logger.debug("TpmSimulator: stop_data_transmission")
        self._pending_data_requests = False

    def start_acquisition(
        self: BaseTpmSimulator,
        start_time: Optional[str] = None,
        delay: Optional[int] = 2,
        task_callback: Optional[Callable] = None,
    ) -> None:
        """
        Start data acquisition.

        :param start_time: the time at which to start data acquisition,
            defaults to None
        :param delay: delay start, defaults to 2
        :param task_callback: Update task state, defaults to None

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator:Start acquisition")
        self._set_tpm_status(TpmStatus.SYNCHRONISED)
        self._fpga_reference_time = int(time.time())
        raise NotImplementedError

    # pylint: disable=too-many-arguments
    def set_lmc_integrated_download(
        self: BaseTpmSimulator,
        mode: str,
        channel_payload_length: int,
        beam_payload_length: int,
        dst_ip: Optional[str] = None,
        src_port: int = 0xF0D0,
        dst_port: int = 4660,
    ) -> None:
        """
        Configure link and size of control data.

        :param mode: '1G' or '10G'
        :param channel_payload_length: SPEAD payload length for
            integrated channel data
        :param beam_payload_length: SPEAD payload length for integrated
            beam data
        :param dst_ip: Destination IP, defaults to None
        :param src_port: source port, defaults to 0xF0D0
        :param dst_port: destination port, defaults to 4660

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: set_lmc_integrated_download")
        raise NotImplementedError

    @property
    def current_tile_beamformer_frame(self: BaseTpmSimulator) -> int:
        """
        Return current frame, in units of 256 ADC frames.

        :return: current tile beamformer frame
        """
        self.logger.debug("TpmSimulator: current_tile_beamformer_frame")
        return self._current_tile_beamformer_frame

    @property
    def is_beamformer_running(self: BaseTpmSimulator) -> bool:
        """
        Whether the beamformer is currently running.

        :return: whether the beamformer is currently running
        """
        self.logger.debug("TpmSimulator: beamformer_is_running")
        return self._is_beamformer_running

    @property
    def pending_data_requests(self: BaseTpmSimulator) -> bool:
        """
        Check for pending data requests.

        :return: whether there are pending send data requests
        """
        self.logger.debug("TpmSimulator: pending_data_requests")
        return self._pending_data_requests

    @property
    def phase_terminal_count(self: BaseTpmSimulator) -> int:
        """
        Return the phase terminal count.

        :return: the phase terminal count
        """
        self.logger.debug("TpmSimulator: get_phase_terminal_count")
        return self._phase_terminal_count

    @phase_terminal_count.setter
    def phase_terminal_count(self: BaseTpmSimulator, value: int) -> None:
        """
        Set the phase terminal count.

        :param value: the phase terminal count
        """
        self.logger.debug("TpmSimulator: set_phase_terminal_count")
        self._phase_terminal_count = value

    def post_synchronisation(self: BaseTpmSimulator) -> None:
        """
        Perform post tile configuration synchronization.

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: post_synchronisation")
        raise NotImplementedError

    def sync_fpgas(self: BaseTpmSimulator) -> None:
        """
        Synchronise the FPGAs.

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: sync_fpgas")
        raise NotImplementedError

    # pylint: disable=too-many-arguments
    def configure_test_generator(
        self: BaseTpmSimulator,
        frequency0: float,
        amplitude0: float,
        frequency1: float,
        amplitude1: float,
        amplitude_noise: float,
        pulse_code: int,
        amplitude_pulse: float,
        load_time: int = 0,
    ) -> None:
        """
        Test generator configuration.

        :param frequency0: Tone frequency in Hz of DDC 0
        :param amplitude0: Tone peak amplitude, normalized to 31.875 ADC units,
            resolution 0.125 ADU
        :param frequency1: Tone frequency in Hz of DDC 1
        :param amplitude1: Tone peak amplitude, normalized to 31.875 ADC units,
            resolution 0.125 ADU
        :param amplitude_noise: Amplitude of pseudorandom noise
            normalized to 26.03 ADC units, resolution 0.102 ADU
        :param pulse_code: Code for pulse frequency.
            Range 0 to 7: 16,12,8,6,4,3,2 times frame frequency
        :param amplitude_pulse: pulse peak amplitude, normalized
            to 127.5 ADC units, resolution 0.5 ADU
        :param load_time: Time to start the tone.
        """
        amplitude_adu = round(amplitude0 * 255) / 8.0
        self.logger.debug(
            "TpmSimulator: set_test_generator tone(0):"
            + str(frequency0)
            + "Hz, "
            + str(amplitude_adu)
            + " ADUs @"
            + str(load_time)
        )
        amplitude_adu = round(amplitude1 * 255) / 8.0
        self.logger.debug(
            "TpmSimulator: test_generator set_tone(1):"
            + str(frequency1)
            + "Hz, "
            + str(amplitude_adu)
            + " ADUs @"
            + str(load_time)
        )
        amplitude_adu = round(amplitude_noise * 255) * 0.102
        self.logger.debug(
            "TpmSimulator: set_test_generator noise: "
            + str(amplitude_adu)
            + " ADUs @"
            + str(load_time)
        )
        freqs = [16, 12, 8, 6, 4, 3, 2, 1]
        frequency = 0.925925 * freqs[pulse_code]
        amplitude_adu = round(amplitude_pulse * 255) * 0.25
        self.logger.debug(
            "TpmSimulator: set_test_generator pulse: "
            + str(frequency)
            + "Hz, "
            + str(amplitude_adu)
            + " ADUs"
        )

    def test_generator_input_select(self: BaseTpmSimulator, bit_mask: int) -> None:
        """
        Specify ADC inputs which are substitute to test signal.

        Specified using a 32 bit mask, with LSB for ADC input 0.

        :param bit_mask: Bit mask of inputs using test signal
        """
        self.logger.debug(
            "TpmSimulator: test_generator_input_select: " + str(hex(bit_mask))
        )
        self._test_generator_active = bit_mask != 0

    @property
    def test_generator_active(self: BaseTpmSimulator) -> bool:
        """
        Check if the test generator is active.

        :return: whether the test generator is active
        """
        return self._test_generator_active

    @test_generator_active.setter
    def test_generator_active(self: BaseTpmSimulator, active: bool) -> None:
        """
        Set the test generator active flag.

        :param active: True if the generator has been activated
        """
        self._test_generator_active = active
