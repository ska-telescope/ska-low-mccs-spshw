#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements the MCCS Tile device."""
# pylint: disable=too-many-arguments
from __future__ import annotations

import functools
import importlib  # allow forward references in type hints
import json
import os.path
import re
import sys
import threading
from collections import defaultdict
from dataclasses import dataclass
from functools import reduce, wraps
from ipaddress import IPv4Address
from operator import getitem
from typing import Any, Callable, Final, NoReturn, Optional, cast

import numpy as np
import ska_tango_base as stb
import tango
from ska_control_model import (
    AdminMode,
    CommunicationStatus,
    HealthState,
    PowerState,
    ResultCode,
    SimulationMode,
    TaskStatus,
    TestMode,
)
from ska_low_mccs_common import MccsBaseDevice
from ska_tango_base.software_bus import AttrSignal, attribute_from_signal
from tango.server import attribute, command, device_property

from .attribute_converters import (
    NumpyEncoder,
    adc_pll_to_list,
    adc_to_list,
    clock_managers_count,
    clock_managers_status,
    clocks_to_list,
    flatten_list,
    lane_error_to_array,
    serialise_np_object,
    serialise_object,
    udp_error_count_to_list,
)
from .attribute_managers import (
    AlwaysPushAttributeManager,
    AttributeManager,
    BoolAttributeManager,
    NpArrayAttributeManager,
)
from .firmware_threshold_interface import (
    CURRENT_KEYS,
    TEMPERATURE_KEYS,
    VOLTAGE_KEYS,
    FirmwareThresholds,
    FirmwareThresholdsDbAdapter,
)
from .tile_component_manager import TileComponentManager
from .tile_health_model import TileHealthModel
from .tile_health_recorder import TileHealthRecorder
from .tpm_status import TpmStatus

__all__ = ["MccsTile", "main"]

DevVarLongStringArrayType = tuple[list[ResultCode], list[str]]


def merge(d: dict[str, Any], u: dict[str, Any]) -> None:
    """
    Deep merge dictionary u into dictionary d.

    :param d: dictionary to merge into
    :param u: dictionary to merge from
    """
    for k, v in u.items():
        if isinstance(v, dict) and isinstance(d.get(k), dict):
            merge(d[k], v)
        else:
            d[k] = v


def is_v1(version_str: str) -> bool:
    """
    Return True if version is v1.x.x?, False if v2.x.x?.

    :param version_str: version string to check.
    :return: True if v1.x.x? (or empty string), False if v2.x.x?.
    :raises ValueError: if version_str is not valid.
    """
    # Allow empty string (treat as v2 by default)
    if version_str == "":
        return False

    match = re.fullmatch(r"v([12])\.\d+\.\d+[a-z]?", version_str)
    if not match:
        raise ValueError(f"Invalid version format: '{version_str}'")

    return match.group(1) == "1"


def engineering_mode_required(func: Callable) -> Callable:
    """
    Return a decorator for engineering only commands.

    :param func: the command which is engineering mode only.

    :returns: decorator to check for engineering mode before running command.
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> DevVarLongStringArrayType:
        device: MccsBaseDevice = args[0]
        if device._admin_mode != AdminMode.ENGINEERING:
            return (
                [ResultCode.REJECTED],
                [
                    f"Device in adminmode {device._admin_mode.name}, "
                    "this command requires engineering."
                ],
            )
        return func(*args, **kwargs)

    return wrapper


@dataclass
class TileAttribute:
    """Class representing the internal state of a Tile attribute."""

    value: Any
    quality: tango.AttrQuality
    timestamp: float


# pylint: disable=too-many-lines, too-many-public-methods, too-many-instance-attributes
# pylint: disable=too-many-ancestors
class MccsTile(MccsBaseDevice[TileComponentManager]):
    """An implementation of a Tile Tango device for MCCS."""

    InitCommand = None  # type: ignore[assignment]

    # -------
    # Signals
    # -------
    board_temperature_signal: AttrSignal[float] = AttrSignal[float]()
    fpga1_temperature_signal: AttrSignal[float] = AttrSignal[float]()
    fpga2_temperature_signal: AttrSignal[float] = AttrSignal[float]()
    temperature_adc0_signal: AttrSignal[float] = AttrSignal[float]()
    temperature_adc1_signal: AttrSignal[float] = AttrSignal[float]()
    temperature_adc2_signal: AttrSignal[float] = AttrSignal[float]()
    temperature_adc3_signal: AttrSignal[float] = AttrSignal[float]()
    temperature_adc4_signal: AttrSignal[float] = AttrSignal[float]()
    temperature_adc5_signal: AttrSignal[float] = AttrSignal[float]()
    temperature_adc6_signal: AttrSignal[float] = AttrSignal[float]()
    temperature_adc7_signal: AttrSignal[float] = AttrSignal[float]()
    temperature_adc8_signal: AttrSignal[float] = AttrSignal[float]()
    temperature_adc9_signal: AttrSignal[float] = AttrSignal[float]()
    temperature_adc10_signal: AttrSignal[float] = AttrSignal[float]()
    temperature_adc11_signal: AttrSignal[float] = AttrSignal[float]()
    temperature_adc12_signal: AttrSignal[float] = AttrSignal[float]()
    temperature_adc13_signal: AttrSignal[float] = AttrSignal[float]()
    temperature_adc14_signal: AttrSignal[float] = AttrSignal[float]()
    temperature_adc15_signal: AttrSignal[float] = AttrSignal[float]()
    current_fe0_signal: AttrSignal[float] = AttrSignal[float]()
    current_fe1_signal: AttrSignal[float] = AttrSignal[float]()
    voltage_avdd3_signal: AttrSignal[float] = AttrSignal[float]()
    voltage_vref_ddr0_signal: AttrSignal[float] = AttrSignal[float]()
    voltage_vref_ddr1_signal: AttrSignal[float] = AttrSignal[float]()
    voltage_man1v2_signal: AttrSignal[float] = AttrSignal[float]()
    voltage_mgt_avcc_signal: AttrSignal[float] = AttrSignal[float]()
    voltage_mgt_avtt_signal: AttrSignal[float] = AttrSignal[float]()
    voltage_mon5v0_signal: AttrSignal[float] = AttrSignal[float]()
    voltage_mon3v3_signal: AttrSignal[float] = AttrSignal[float]()
    voltage_mon1v8_signal: AttrSignal[float] = AttrSignal[float]()
    voltage_sw_avdd1_signal: AttrSignal[float] = AttrSignal[float]()
    voltage_sw_avdd2_signal: AttrSignal[float] = AttrSignal[float]()
    voltage_vin_signal: AttrSignal[float] = AttrSignal[float]()
    voltage_vm_agp0_signal: AttrSignal[float] = AttrSignal[float]()
    voltage_vm_agp1_signal: AttrSignal[float] = AttrSignal[float]()
    voltage_vm_agp2_signal: AttrSignal[float] = AttrSignal[float]()
    voltage_vm_agp3_signal: AttrSignal[float] = AttrSignal[float]()
    voltage_vm_agp4_signal: AttrSignal[float] = AttrSignal[float]()
    voltage_vm_agp5_signal: AttrSignal[float] = AttrSignal[float]()
    voltage_vm_agp6_signal: AttrSignal[float] = AttrSignal[float]()
    voltage_vm_agp7_signal: AttrSignal[float] = AttrSignal[float]()
    voltage_vm_clk0b_signal: AttrSignal[float] = AttrSignal[float]()
    voltage_vm_clk1b_signal: AttrSignal[float] = AttrSignal[float]()
    voltage_vm_ddr0_vtt_signal: AttrSignal[float] = AttrSignal[float]()
    voltage_vm_ddr1_vdd_signal: AttrSignal[float] = AttrSignal[float]()
    voltage_vm_ddr1_vtt_signal: AttrSignal[float] = AttrSignal[float]()
    voltage_vm_drvdd_signal: AttrSignal[float] = AttrSignal[float]()
    voltage_vm_dvdd_signal: AttrSignal[float] = AttrSignal[float]()
    voltage_vm_fe0_signal: AttrSignal[float] = AttrSignal[float]()
    voltage_vm_fe1_signal: AttrSignal[float] = AttrSignal[float]()
    voltage_vm_mgt0_aux_signal: AttrSignal[float] = AttrSignal[float]()
    voltage_vm_mgt1_aux_signal: AttrSignal[float] = AttrSignal[float]()
    voltage_vm_pll_signal: AttrSignal[float] = AttrSignal[float]()
    voltage_vm_sw_amp_signal: AttrSignal[float] = AttrSignal[float]()

    # Maps each signal-backed attribute that needs alarm shutdown handling
    # to its Tango attribute name.
    _ALARM_SIGNAL_ATTRIBUTES: dict[AttrSignal, str] = {
        board_temperature_signal: "boardTemperature",
        fpga1_temperature_signal: "fpga1Temperature",
        fpga2_temperature_signal: "fpga2Temperature",
    }

    # Maps each health-monitoring attribute name to its signal attribute name,
    # used by update_tile_health_attributes to route updates generically.
    _HEALTH_SIGNAL_MAP: dict[str, str] = {
        "boardTemperature": "board_temperature_signal",
        "fpga1Temperature": "fpga1_temperature_signal",
        "fpga2Temperature": "fpga2_temperature_signal",
        "temperatureADC0": "temperature_adc0_signal",
        "temperatureADC1": "temperature_adc1_signal",
        "temperatureADC2": "temperature_adc2_signal",
        "temperatureADC3": "temperature_adc3_signal",
        "temperatureADC4": "temperature_adc4_signal",
        "temperatureADC5": "temperature_adc5_signal",
        "temperatureADC6": "temperature_adc6_signal",
        "temperatureADC7": "temperature_adc7_signal",
        "temperatureADC8": "temperature_adc8_signal",
        "temperatureADC9": "temperature_adc9_signal",
        "temperatureADC10": "temperature_adc10_signal",
        "temperatureADC11": "temperature_adc11_signal",
        "temperatureADC12": "temperature_adc12_signal",
        "temperatureADC13": "temperature_adc13_signal",
        "temperatureADC14": "temperature_adc14_signal",
        "temperatureADC15": "temperature_adc15_signal",
        "currentFE0": "current_fe0_signal",
        "currentFE1": "current_fe1_signal",
        "voltageAVDD3": "voltage_avdd3_signal",
        "voltageVrefDDR0": "voltage_vref_ddr0_signal",
        "voltageVrefDDR1": "voltage_vref_ddr1_signal",
        "voltageMan1V2": "voltage_man1v2_signal",
        "voltageMGT_AVCC": "voltage_mgt_avcc_signal",
        "voltageMGT_AVTT": "voltage_mgt_avtt_signal",
        "voltageMon5V0": "voltage_mon5v0_signal",
        "voltageMon3V3": "voltage_mon3v3_signal",
        "voltageMon1V8": "voltage_mon1v8_signal",
        "voltageSW_AVDD1": "voltage_sw_avdd1_signal",
        "voltageSW_AVDD2": "voltage_sw_avdd2_signal",
        "voltageVIN": "voltage_vin_signal",
        "voltageVM_AGP0": "voltage_vm_agp0_signal",
        "voltageVM_AGP1": "voltage_vm_agp1_signal",
        "voltageVM_AGP2": "voltage_vm_agp2_signal",
        "voltageVM_AGP3": "voltage_vm_agp3_signal",
        "voltageVM_AGP4": "voltage_vm_agp4_signal",
        "voltageVM_AGP5": "voltage_vm_agp5_signal",
        "voltageVM_AGP6": "voltage_vm_agp6_signal",
        "voltageVM_AGP7": "voltage_vm_agp7_signal",
        "voltageVM_CLK0B": "voltage_vm_clk0b_signal",
        "voltageVM_CLK1B": "voltage_vm_clk1b_signal",
        "voltageVM_DDR0_VTT": "voltage_vm_ddr0_vtt_signal",
        "voltageVM_DDR1_VDD": "voltage_vm_ddr1_vdd_signal",
        "voltageVM_DDR1_VTT": "voltage_vm_ddr1_vtt_signal",
        "voltageVM_DRVDD": "voltage_vm_drvdd_signal",
        "voltageVM_DVDD": "voltage_vm_dvdd_signal",
        "voltageVM_FE0": "voltage_vm_fe0_signal",
        "voltageVM_FE1": "voltage_vm_fe1_signal",
        "voltageVM_MGT0_AUX": "voltage_vm_mgt0_aux_signal",
        "voltageVM_MGT1_AUX": "voltage_vm_mgt1_aux_signal",
        "voltageVM_PLL": "voltage_vm_pll_signal",
        "voltageVM_SW_AMP": "voltage_vm_sw_amp_signal",
    }

    # -----------------
    # Device Properties
    # -----------------
    SimulationConfig = device_property(dtype=int, default_value=SimulationMode.FALSE)
    TestConfig = device_property(dtype=int, default_value=TestMode.NONE)
    PollRate = device_property(dtype=float, default_value=0.4)

    AntennasPerTile = device_property(dtype=int, default_value=16)

    SubrackFQDN = device_property(dtype=str)
    SubrackBay = device_property(dtype=int)  # position of TPM in subrack

    TileId = device_property(dtype=int, default_value=1)  # Tile ID must be nonzero
    StationID = device_property(dtype=int, default_value=1)
    TpmIp = device_property(dtype=str, default_value="0.0.0.0")
    TpmCpldPort = device_property(dtype=int, default_value=10000)
    # TODO: This is defining the hardware configuration
    # can be exported to TmData.
    PreAduFitted = device_property(
        dtype=(bool,),
        default_value=[True] * 2,
        doc=(
            "Represents the presence of the 2 preAdus. "
            "Index 0 -> FE0_mVA. Index 1 -> FE1_mVA"
        ),
    )
    # ====================================================================
    # TpmVersion and HardwareVersion are similar in concept.
    # TpmVersion is deprecated, preferring HardwareVersion. New property
    # defined for retrocompatibility reasons.

    # TODO: TpmVersion is deprecated, remove at an appropriate time.
    # TODO: HardwareVersion and BiosVersion should be mandatory.
    TpmVersion = device_property(dtype=str, default_value="tpm_v1_6")
    HardwareVersion = device_property(
        dtype=str,
        default_value="",
        doc=(
            "The HARDWARE_REV (e.g. v1.6.7a). "
            "If not defined ADC0 -> ADC15 temperature "
            "attributes are not evaluated in health"
        ),
    )
    BiosVersion = device_property(
        dtype=str,
        default_value="",
        doc=(
            "The bios version (e.g. 0.5.0). "
            "If not defined pll_40g attribute "
            "is not evaluated in health"
        ),
    )
    # ====================================================================

    PreaduAttenuation = device_property(dtype=(float,), default_value=[])
    StaticDelays = device_property(
        dtype=(float,),
        default_value=[0.0] * 32,  # Default no offsets
        doc="Delays in nanoseconds to account for static delay missmatches.",
    )

    DefaultLockTimeout = device_property(dtype=float, default_value=0.4)
    PollLockTimeout = device_property(
        doc="The time a poll waits to claim a lock before giving up.",
        dtype=float,
        default_value=6.0,
    )
    PowerCallbackLockTimeout = device_property(
        doc=(
            "The time a power callback waits to claim a lock. "
            "This is used to connect if not already "
            "to determine if initialisation is required."
        ),
        dtype=float,
        default_value=6.0,
    )
    VerifyEvents = device_property(dtype=bool, default_value=True)
    UseAttributesForHealth = device_property(
        doc="Use the attribute quality factor in health. ADR-115.",
        dtype=bool,
        default_value=True,
    )

    # The CommandName_SCHEMA naming scheme relies on an implementation detail
    # so we also specify them in the decorator for clarity.
    WriteRegister_SCHEMA: Final = json.loads(
        importlib.resources.read_text(
            "ska_low_mccs_spshw.schemas.tile",
            "MccsTile_WriteRegister.json",
        )
    )

    Configure40GCore_SCHEMA: Final = json.loads(
        importlib.resources.read_text(
            "ska_low_mccs_spshw.schemas.tile",
            "MccsTile_Configure40gCore.json",
        )
    )

    Get40GCoreConfiguration_SCHEMA: Final = json.loads(
        importlib.resources.read_text(
            "ska_low_mccs_spshw.schemas.tile",
            "MccsTile_Get40gCoreConfiguration.json",
        )
    )

    SetLmcDownload_SCHEMA: Final = json.loads(
        importlib.resources.read_text(
            "ska_low_mccs_spshw.schemas.tile",
            "MccsTile_SetLmcDownload.json",
        )
    )

    SetLmcIntegratedDownload_SCHEMA: Final = json.loads(
        importlib.resources.read_text(
            "ska_low_mccs_spshw.schemas.tile",
            "MccsTile_SetLmcIntegratedDownload.json",
        )
    )

    SetCspDownload_SCHEMA: Final = json.loads(
        importlib.resources.read_text(
            "ska_low_mccs_spshw.schemas.tile",
            "MccsTile_SetCspDownload.json",
        )
    )

    ConfigureStationBeamformer_SCHEMA: Final = json.loads(
        importlib.resources.read_text(
            "ska_low_mccs_spshw.schemas.tile",
            "MccsTile_ConfigureStationBeamformer.json",
        )
    )

    BeamformerRunning_SCHEMA: Final = json.loads(
        importlib.resources.read_text(
            "ska_low_mccs_spshw.schemas.tile",
            "MccsTile_BeamformerRunningForChannels.json",
        )
    )

    StartBeamformer_SCHEMA: Final = json.loads(
        importlib.resources.read_text(
            "ska_low_mccs_spshw.schemas.tile",
            "MccsTile_StartBeamformer.json",
        )
    )

    StopBeamformer_SCHEMA: Final = json.loads(
        importlib.resources.read_text(
            "ska_low_mccs_spshw.schemas.tile",
            "MccsTile_StopBeamformer.json",
        )
    )

    ConfigureIntegratedChannelData_SCHEMA: Final = json.loads(
        importlib.resources.read_text(
            "ska_low_mccs_spshw.schemas.tile",
            "MccsTile_ConfigureIntegratedChannelData.json",
        )
    )

    ConfigureIntegratedBeamData_SCHEMA: Final = json.loads(
        importlib.resources.read_text(
            "ska_low_mccs_spshw.schemas.tile",
            "MccsTile_ConfigureIntegratedBeamData.json",
        )
    )

    SendDataSamples_SCHEMA: Final = json.loads(
        importlib.resources.read_text(
            "ska_low_mccs_spshw.schemas.tile", "MccsTile_SendDataSamples.json"
        )
    )

    StartAcquisition_SCHEMA: Final = json.loads(
        importlib.resources.read_text(
            "ska_low_mccs_spshw.schemas.tile",
            "MccsTile_StartAcquisition.json",
        )
    )

    ConfigureTestGenerator_SCHEMA: Final = json.loads(
        importlib.resources.read_text(
            "ska_low_mccs_spshw.schemas.tile",
            "MccsTile_ConfigureTestGenerator.json",
        )
    )

    ConfigurePatternGenerator_SCHEMA: Final = json.loads(
        importlib.resources.read_text(
            "ska_low_mccs_spshw.schemas.tile",
            "MccsTile_ConfigurePatternGenerator.json",
        )
    )

    SetUpAntennaBuffer_SCHEMA: Final = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {
            "ddr_start_byte_address": {"type": "integer", "minimum": 0},
            "max_ddr_byte_size": {"type": "integer"},
            "mode": {"type": "string"},
        },
    }

    # ---------------
    # Initialisation
    # ---------------
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Initialise this device object.

        :param args: positional args to the init
        :param kwargs: keyword args to the init
        """
        # We aren't supposed to define initialisation methods for Tango
        # devices; we are only supposed to define an `init_device` method. But
        # we insist on doing so here, just so that we can define some
        # attributes, thereby stopping the linters from complaining about
        # "attribute-defined-outside-init" etc. We still need to make sure that
        # `init_device` re-initialises any values defined in here.
        super().__init__(*args, **kwargs)
        self._health_state: HealthState = HealthState.UNKNOWN
        self._health_model: TileHealthModel
        self.tile_health_structure: dict[str, dict[str, Any]] = {}
        self._antenna_ids: list[int] = []
        self._info: dict[str, Any] = {}
        self.component_manager: TileComponentManager
        self._stopping: bool
        self._health_recorder: TileHealthRecorder | None
        self._health_report = ""
        self.hw_firmware_thresholds: FirmwareThresholds
        self.db_firmware_thresholds: FirmwareThresholds
        self.db_configuration_fault: tuple[bool | None, str] = (
            None,
            "No information gathered",
        )
        self.component_manager_fault: bool | None = None
        self.power_state: PowerState | None = None
        self.status_information: dict[str, str] = {}

        self._intermediate_healths: dict[str, HealthState] = {
            "temperatures": HealthState.UNKNOWN,
            "currents": HealthState.UNKNOWN,
            "dsp": HealthState.UNKNOWN,
            "voltages": HealthState.UNKNOWN,
            "io": HealthState.UNKNOWN,
            "timing": HealthState.UNKNOWN,
            "adcs": HealthState.UNKNOWN,
            "alarms": HealthState.UNKNOWN,
        }
        self._intermediate_attrs: dict[str, list[str]]
        self._csp_destination_ip = ""
        self._csp_destination_mac = ""
        self._csp_destination_port = 0

    def delete_device(self: MccsTile) -> None:
        """
        Prepare to delete the device.

        This method must be done explicitly, else polling
        threads are not cleaned up after init_device().
        """
        # We do not want to raise a exception here
        # This can cause a segfault.
        self._stopping = True
        if self._health_recorder is not None:
            self._health_recorder.cleanup()
            self._health_recorder = None

        super().delete_device()

        # ============================================================
        # Temporary workaround for THORN-466
        #
        # A segmentation fault was observed after upgrading PyTango.
        # Until the root cause is fixed, we explicitly mark attributes
        # as INVALID when they have a value. This prevents the crash
        # and allows SPSHW releases to proceed.
        #
        # Track progress and removal of this workaround in THORN-466.
        # ============================================================

        device_attrs = self.get_device_attr()

        for attr_name, attr_state in self._attribute_state.items():
            if attr_state.read() is None:
                continue

            device_attrs.get_attr_by_name(attr_name).set_quality(
                tango.AttrQuality.ATTR_INVALID
            )
        for t in threading.enumerate():
            self.logger.info(
                f"Threads open at end of DELETE DEVICE "
                f"Threads: {t.name}, ID: {t.ident}, Daemon: {t.daemon}"
            )

    def init_device(self: MccsTile) -> None:
        """
        Initialise the device.

        :raises TypeError: when attributes have a converter
            that is not callable.
        """
        self._stopping = False
        # Pre-compute absolute signal names for alarm handling in notify_emission.
        self._alarm_signal_map: dict[str, str] = {
            sig._absolute_name_for(self): tango_attr_name
            for sig, tango_attr_name in MccsTile._ALARM_SIGNAL_ATTRIBUTES.items()
        }
        # Map from name used by TileComponentManager to the
        # name of the Tango Attribute.
        self.attr_map = {
            "pending_data_requests": "pendingDataRequests",
            "fpga_reference_time": "fpgaReferenceTime",
            "I2C_access_alm": "I2C_access_alm",
            "temperature_alm": "temperature_alm",
            "voltage_alm": "voltage_alm",
            "SEM_wd": "SEM_wd",
            "MCU_wd": "MCU_wd",
            "programming_state": "tileProgrammingState",
            "adc_rms": "adcPower",
            "static_delays": "staticTimeDelays",
            "preadu_levels": "preaduLevels",
            "csp_rounding": "cspRounding",
            "channeliser_rounding": "channeliserRounding",
            "pll_locked": "pllLocked",
            "pps_delay": "ppsDelay",
            "pps_drift": "ppsDrift",
            "pps_delay_correction": "ppsDelayCorrection",
            "phase_terminal_count": "phaseTerminalCount",
            "beamformer_running": "isBeamformerRunning",
            "is_programmed": "isProgrammed",
            "beamformer_table": "beamformerTable",
            "beamformer_regions": "beamformerRegions",
            "io": "io",
            "dsp": "dsp",
            "voltages": "voltages",
            "temperatures": "temperatures",
            "adcs": "adcs",
            "timing": "timing",
            "currents": "currents",
            "tile_id": "logicalTileId",
            "station_id": "stationId",
            "tile_beamformer_frame": "currentTileBeamformerFrame",
            "tile_info": "tile_info",
            "adc_pll_lock_status": "adc_pll_lock_status",
            "fpga0_qpll_status": "fpga0_qpll_status",
            "fpga0_qpll_counter": "fpga0_qpll_counter",
            "fpga1_qpll_status": "fpga1_qpll_status",
            "fpga1_qpll_counter": "fpga1_qpll_counter",
            "f2f_pll_lock_status": "f2f_pll_lock_status",
            "f2f_pll_counter": "f2f_pll_counter",
            "f2f_soft_errors": "f2f_soft_errors",
            "f2f_hard_errors": "f2f_hard_errors",
            "timing_pll_lock_status": "timing_pll_lock_status",
            "timing_pll_count": "timing_pll_count",
            "timing_pll_40g_lock_status": "timing_pll_40g_lock_status",
            "timing_pll_40g_count": "timing_pll_40g_count",
            "adc_sysref_timing_requirements": "adc_sysref_timing_requirements",
            "adc_sysref_counter": "adc_sysref_counter",
            "fpga0_clocks": "fpga0_clocks",
            "fpga1_clocks": "fpga1_clocks",
            "fpga0_clock_managers_count": "fpga0_clock_managers_count",
            "fpga0_clock_managers_status": "fpga0_clock_managers_status",
            "fpga1_clock_managers_count": "fpga1_clock_managers_count",
            "fpga1_clock_managers_status": "fpga1_clock_managers_status",
            "fpga0_lane_error_count": "fpga0_lane_error_count",
            "fpga1_lane_error_count": "fpga1_lane_error_count",
            "fpga0_resync_count": "fpga0_resync_count",
            "fpga1_resync_count": "fpga1_resync_count",
            "ddr_initialisation": "ddr_initialisation",
            "fpga0_ddr_reset_counter": "fpga0_ddr_reset_counter",
            "fpga1_ddr_reset_counter": "fpga1_ddr_reset_counter",
            # "ddr_rd_cnt": "ddr_rd_cnt",
            # "ddr_wr_cnt": "ddr_wr_cnt",
            # "ddr_rd_dat_cnt": "ddr_rd_dat_cnt",
            "fpga0_crc_error_count": "fpga0_crc_error_count",
            "fpga1_crc_error_count": "fpga1_crc_error_count",
            "fpga0_bip_error_count": "fpga0_bip_error_count",
            "fpga0_decode_error_count": "fpga0_decode_error_count",
            "fpga1_bip_error_count": "fpga1_bip_error_count",
            "fpga1_decode_error_count": "fpga1_decode_error_count",
            "fpga0_linkup_loss_count": "fpga0_linkup_loss_count",
            "fpga1_linkup_loss_count": "fpga1_linkup_loss_count",
            "fpga0_data_router_status": "fpga0_data_router_status",
            "fpga1_data_router_status": "fpga1_data_router_status",
            "data_router_discarded_packets": "data_router_discarded_packets",
            "tile_beamformer_status": "tile_beamformer_status",
            "station_beamformer_status": "station_beamformer_status",
            "fpga0_station_beamformer_error_count": (
                "fpga0_station_beamformer_error_count"
            ),
            "fpga1_station_beamformer_error_count": (
                "fpga1_station_beamformer_error_count"
            ),
            "fpga0_station_beamformer_flagged_count": (
                "fpga0_station_beamformer_flagged_count"
            ),
            "fpga1_station_beamformer_flagged_count": (
                "fpga1_station_beamformer_flagged_count"
            ),
            "core_communication": "coreCommunicationStatus",
            "is_station_beam_flagging_enabled": "stationBeamFlagEnabled",
            "rfi_count": "rfiCount",
            "antenna_buffer_mode": "antennaBufferMode",
            "data_transmission_mode": "dataTransmissionMode",
            "integrated_data_transmission_mode": "integratedDataTransmissionMode",
            "pfb_version": "pfbVersion",
            "rfi_blanking_enabled_antennas": "rfiBlankingEnabledAntennas",
            "broadband_rfi_factor": "broadbandRfiFactor",
            "40g_packet_count": "fortyGPacketCount",
            "pointing_delays": "pointingDelays",
        }

        attribute_converters: dict[str, Any] = {
            "adc_pll_lock_status": adc_pll_to_list,
            "fpga0_bip_error_count": udp_error_count_to_list,
            "fpga0_decode_error_count": udp_error_count_to_list,
            "fpga1_bip_error_count": udp_error_count_to_list,
            "fpga1_decode_error_count": udp_error_count_to_list,
            "fpga0_lane_error_count": lane_error_to_array,
            "fpga1_lane_error_count": lane_error_to_array,
            "fpga0_clock_managers_count": clock_managers_count,
            "fpga0_clock_managers_status": clock_managers_status,
            "fpga1_clock_managers_count": clock_managers_count,
            "fpga1_clock_managers_status": clock_managers_status,
            "fpga0_clocks": clocks_to_list,
            "fpga1_clocks": clocks_to_list,
            "adc_sysref_counter": adc_to_list,
            "adc_sysref_timing_requirements": adc_to_list,
            "timing_pll_lock_status": lambda val: (
                int(val[0]) if val[0] is not None else None
            ),
            "timing_pll_40g_lock_status": lambda val: (
                int(val[0]) if val[0] is not None else None
            ),
            "fpga0_qpll_status": lambda val: (
                int(val[0]) if val[0] is not None else None
            ),
            "fpga1_qpll_status": lambda val: (
                int(val[0]) if val[0] is not None else None
            ),
            "f2f_pll_lock_status": lambda val: (
                int(val[0]) if val[0] is not None else None
            ),
            "timing_pll_count": lambda val: int(val[1]) if val[1] is not None else None,
            "f2f_pll_counter": lambda val: int(val[1]) if val[1] is not None else None,
            "timing_pll_40g_count": lambda val: (
                int(val[1]) if val[1] is not None else None
            ),
            "fpga0_qpll_counter": lambda val: (
                int(val[1]) if val[1] is not None else None
            ),
            "fpga1_qpll_counter": lambda val: (
                int(val[1]) if val[1] is not None else None
            ),
            "coreCommunicationStatus": serialise_object,
            "voltages": serialise_object,
            "temperatures": serialise_object,
            "currents": serialise_object,
            "timing": serialise_object,
            "io": serialise_object,
            "dsp": serialise_np_object,
            "data_router_discarded_packets": serialise_object,
            "adcs": serialise_object,
            "beamformerTable": flatten_list,
            "beamformerRegions": flatten_list,
        }

        # A dictionary mapping the Tango Attribute name to its AttributeManager.
        self._attribute_state: dict[str, AttributeManager] = {}

        # generic attributes
        for attr_name in self.attr_map.values():
            converter = attribute_converters.get(attr_name)
            if converter is not None and not callable(converter):
                raise TypeError(f"The converter for '{attr_name}' is not callable.")
            self._attribute_state[attr_name] = AttributeManager(
                functools.partial(self.post_change_event, attr_name),
                converter=converter,
            )

        # Specialised attributes.
        # - ppsPresent: tango does not have good ALARMs for Boolean
        # - tileProgrammingState: TODO: is this state information ?
        # Should we move into the _component_state_changed callback?
        # - Temperature: defining a alarm handler to shutdown TPM on ALARM.
        # - rfiCount: np.ndarray needs a different truth comparison.
        # We have a specific handler for this attribute.
        self._attribute_state.update(
            {
                "ppsPresent": BoolAttributeManager(
                    functools.partial(self.post_change_event, "ppsPresent"),
                    alarm_flag="LOW",
                ),
                "station_beamformer_status": BoolAttributeManager(
                    functools.partial(
                        self.post_change_event, "station_beamformer_status"
                    ),
                    alarm_flag="LOW",
                ),
                "tile_beamformer_status": BoolAttributeManager(
                    functools.partial(self.post_change_event, "tile_beamformer_status"),
                    alarm_flag="LOW",
                ),
                "arp": BoolAttributeManager(
                    functools.partial(self.post_change_event, "arp"),
                    alarm_flag="LOW",
                ),
                "udp_status": BoolAttributeManager(
                    functools.partial(self.post_change_event, "udp_status"),
                    alarm_flag="LOW",
                ),
                "ddr_initialisation": BoolAttributeManager(
                    functools.partial(self.post_change_event, "ddr_initialisation"),
                    alarm_flag="LOW",
                ),
                "lane_status": BoolAttributeManager(
                    functools.partial(self.post_change_event, "lane_status"),
                    alarm_flag="LOW",
                ),
                "link_status": BoolAttributeManager(
                    functools.partial(self.post_change_event, "link_status"),
                    alarm_flag="LOW",
                ),
                "tileProgrammingState": AttributeManager(
                    functools.partial(self.post_change_event, "tileProgrammingState"),
                    initial_value=TpmStatus.UNKNOWN.pretty_name(),
                ),
                "rfiCount": NpArrayAttributeManager(
                    functools.partial(self.post_change_event, "rfiCount")
                ),
                "fortyGPacketCount": AttributeManager(
                    functools.partial(self.post_change_event, "fortyGPacketCount")
                ),
                "pointingDelays": AlwaysPushAttributeManager(
                    functools.partial(self.post_change_event, "pointingDelays")
                ),
            }
        )

        self.__alarm_attribute_map: dict[str, str] = {
            "I2C_access_alm": "I2C_access_alm",
            "temperature_alm": "temperature_alm",
            "voltage_alm": "voltage_alm",
            "SEM_wd": "SEM_wd",
            "MCU_wd": "MCU_wd",
        }

        self.attribute_monitoring_point_map: dict[str, list[str]] = {
            "ppsPresent": ["timing", "pps", "status"],
            "fpga1Temperature": ["temperatures", "FPGA0"],
            "fpga2Temperature": ["temperatures", "FPGA1"],
            "boardTemperature": ["temperatures", "board"],
            "io": ["io"],
            "dsp": ["dsp"],
            "voltages": ["voltages"],
            "temperatures": ["temperatures"],
            "temperatureADC0": ["temperatures", "ADC0"],
            "temperatureADC1": ["temperatures", "ADC1"],
            "temperatureADC2": ["temperatures", "ADC2"],
            "temperatureADC3": ["temperatures", "ADC3"],
            "temperatureADC4": ["temperatures", "ADC4"],
            "temperatureADC5": ["temperatures", "ADC5"],
            "temperatureADC6": ["temperatures", "ADC6"],
            "temperatureADC7": ["temperatures", "ADC7"],
            "temperatureADC8": ["temperatures", "ADC8"],
            "temperatureADC9": ["temperatures", "ADC9"],
            "temperatureADC10": ["temperatures", "ADC10"],
            "temperatureADC11": ["temperatures", "ADC11"],
            "temperatureADC12": ["temperatures", "ADC12"],
            "temperatureADC13": ["temperatures", "ADC13"],
            "temperatureADC14": ["temperatures", "ADC14"],
            "temperatureADC15": ["temperatures", "ADC15"],
            "adcs": ["adcs"],
            "timing": ["timing"],
            "currents": ["currents"],
            "currentFE0": ["currents", "FE0_mVA"],
            "currentFE1": ["currents", "FE1_mVA"],
            "voltageAVDD3": ["voltages", "AVDD3"],
            "voltageVrefDDR0": ["voltages", "DDR0_VREF"],
            "voltageVrefDDR1": ["voltages", "DDR1_VREF"],
            # "voltageVref2V5": ["voltages", "VREF_2V5"],
            "voltageMan1V2": ["voltages", "MAN_1V2"],
            "voltageMGT_AVCC": ["voltages", "MGT_AVCC"],
            "voltageMGT_AVTT": ["voltages", "MGT_AVTT"],
            "voltageMon5V0": ["voltages", "MON_5V0"],
            "voltageMon3V3": ["voltages", "MON_3V3"],
            "voltageMon1V8": ["voltages", "MON_1V8"],
            "voltageSW_AVDD1": ["voltages", "SW_AVDD1"],
            "voltageSW_AVDD2": ["voltages", "SW_AVDD2"],
            "voltageVIN": ["voltages", "VIN"],
            "voltageVM_AGP0": ["voltages", "VM_AGP0"],
            "voltageVM_AGP1": ["voltages", "VM_AGP1"],
            "voltageVM_AGP2": ["voltages", "VM_AGP2"],
            "voltageVM_AGP3": ["voltages", "VM_AGP3"],
            "voltageVM_AGP4": ["voltages", "VM_AGP4"],
            "voltageVM_AGP5": ["voltages", "VM_AGP5"],
            "voltageVM_AGP6": ["voltages", "VM_AGP6"],
            "voltageVM_AGP7": ["voltages", "VM_AGP7"],
            "voltageVM_CLK0B": ["voltages", "VM_CLK0B"],
            "voltageVM_CLK1B": ["voltages", "VM_CLK1B"],
            "voltageVM_DDR0_VTT": ["voltages", "VM_DDR0_VTT"],
            "voltageVM_DDR1_VDD": ["voltages", "VM_DDR1_VDD"],
            "voltageVM_DDR1_VTT": ["voltages", "VM_DDR1_VTT"],
            "voltageVM_DRVDD": ["voltages", "VM_DRVDD"],
            "voltageVM_DVDD": ["voltages", "VM_DVDD"],
            "voltageVM_FE0": ["voltages", "VM_FE0"],
            "voltageVM_FE1": ["voltages", "VM_FE1"],
            "voltageVM_MGT0_AUX": ["voltages", "VM_MGT0_AUX"],
            "voltageVM_MGT1_AUX": ["voltages", "VM_MGT1_AUX"],
            "voltageVM_PLL": ["voltages", "VM_PLL"],
            "voltageVM_SW_AMP": ["voltages", "VM_SW_AMP"],
            "adc_pll_lock_status": ["adcs", "pll_status"],
            # qpll_status is a tuple, extracting status and
            # conuter in different attributes
            "fpga0_qpll_status": ["io", "jesd_interface", "qpll_status", "FPGA0"],
            "fpga0_qpll_counter": ["io", "jesd_interface", "qpll_status", "FPGA0"],
            "fpga1_qpll_status": ["io", "jesd_interface", "qpll_status", "FPGA1"],
            "fpga1_qpll_counter": ["io", "jesd_interface", "qpll_status", "FPGA1"],
            # Extracting status and count in different attributes
            # by use of converters.
            "f2f_pll_lock_status": ["io", "f2f_interface", "pll_status"],
            "f2f_pll_counter": ["io", "f2f_interface", "pll_status"],
            "f2f_soft_errors": ["io", "f2f_interface", "soft_error"],
            "f2f_hard_errors": ["io", "f2f_interface", "hard_error"],
            # Extracting status and count in different attributes
            # by use of converters.
            "timing_pll_lock_status": ["timing", "pll"],
            "timing_pll_count": ["timing", "pll"],
            # Extracting status and count in different attributes
            # by use of converters.
            "timing_pll_40g_lock_status": ["timing", "pll_40g"],
            "timing_pll_40g_count": ["timing", "pll_40g"],
            "adc_sysref_timing_requirements": ["adcs", "sysref_timing_requirements"],
            "adc_sysref_counter": ["adcs", "sysref_counter"],
            "fpga0_clocks": ["timing", "clocks", "FPGA0"],
            "fpga1_clocks": ["timing", "clocks", "FPGA1"],
            # Extracting status and count in different attributes
            # by use of converters.
            "fpga0_clock_managers_count": ["timing", "clock_managers", "FPGA0"],
            "fpga0_clock_managers_status": ["timing", "clock_managers", "FPGA0"],
            "fpga1_clock_managers_count": ["timing", "clock_managers", "FPGA1"],
            "fpga1_clock_managers_status": ["timing", "clock_managers", "FPGA1"],
            # "ddr_rd_cnt": ["io", "ddr_interface", "rd_cnt"],
            # "ddr_wr_cnt": ["io", "ddr_interface", "wr_cnt"],
            # "ddr_rd_dat_cnt": ["io", "ddr_interface", "rd_dat_cnt"],
            "fpga0_lane_error_count": [
                "io",
                "jesd_interface",
                "lane_error_count",
                "FPGA0",
            ],
            "fpga1_lane_error_count": [
                "io",
                "jesd_interface",
                "lane_error_count",
                "FPGA1",
            ],
            "lane_status": ["io", "jesd_interface", "lane_status"],
            "link_status": ["io", "jesd_interface", "link_status"],
            "fpga0_resync_count": ["io", "jesd_interface", "resync_count", "FPGA0"],
            "fpga1_resync_count": ["io", "jesd_interface", "resync_count", "FPGA1"],
            "ddr_initialisation": ["io", "ddr_interface", "initialisation"],
            "fpga0_ddr_reset_counter": [
                "io",
                "ddr_interface",
                "reset_counter",
                "FPGA0",
            ],
            "fpga1_ddr_reset_counter": [
                "io",
                "ddr_interface",
                "reset_counter",
                "FPGA1",
            ],
            "arp": ["io", "udp_interface", "arp"],
            "udp_status": ["io", "udp_interface", "status"],
            "fpga0_crc_error_count": [
                "io",
                "udp_interface",
                "crc_error_count",
                "FPGA0",
            ],
            "fpga1_crc_error_count": [
                "io",
                "udp_interface",
                "crc_error_count",
                "FPGA1",
            ],
            "fpga0_bip_error_count": [
                "io",
                "udp_interface",
                "bip_error_count",
                "FPGA0",
            ],
            "fpga0_decode_error_count": [
                "io",
                "udp_interface",
                "decode_error_count",
                "FPGA0",
            ],
            "fpga1_bip_error_count": [
                "io",
                "udp_interface",
                "bip_error_count",
                "FPGA1",
            ],
            "fpga1_decode_error_count": [
                "io",
                "udp_interface",
                "decode_error_count",
                "FPGA1",
            ],
            "fpga0_linkup_loss_count": [
                "io",
                "udp_interface",
                "linkup_loss_count",
                "FPGA0",
            ],
            "fpga1_linkup_loss_count": [
                "io",
                "udp_interface",
                "linkup_loss_count",
                "FPGA1",
            ],
            "fpga0_data_router_status": ["io", "data_router", "status", "FPGA0"],
            "fpga1_data_router_status": ["io", "data_router", "status", "FPGA1"],
            "data_router_discarded_packets": ["io", "data_router", "discarded_packets"],
            "tile_beamformer_status": ["dsp", "tile_beamf"],
            "station_beamformer_status": ["dsp", "station_beamf", "status"],
            "fpga0_station_beamformer_error_count": [
                "dsp",
                "station_beamf",
                "ddr_parity_error_count",
                "FPGA0",
            ],
            "fpga1_station_beamformer_error_count": [
                "dsp",
                "station_beamf",
                "ddr_parity_error_count",
                "FPGA1",
            ],
            "fpga0_station_beamformer_flagged_count": [
                "dsp",
                "station_beamf",
                "discarded_or_flagged_packet_count",
                "FPGA0",
            ],
            "fpga1_station_beamformer_flagged_count": [
                "dsp",
                "station_beamf",
                "discarded_or_flagged_packet_count",
                "FPGA1",
            ],
        }
        self._intermediate_attrs = defaultdict(list)
        for attr, path in self.attribute_monitoring_point_map.items():
            if not path:
                continue
            self._intermediate_attrs[path[0]].append(attr.lower())

        super().init_device()  # Must be before we try to use the logger.

        self.db_firmware_thresholds = FirmwareThresholds()
        self.hw_firmware_thresholds = FirmwareThresholds()
        self.firmware_threshold_db_interface = FirmwareThresholdsDbAdapter(
            device_name=self.get_name(),
            thresholds=self.db_firmware_thresholds,
            logger=self.logger,
        )

        self._build_state = sys.modules["ska_low_mccs_spshw"].__version_info__
        self._version_id = sys.modules["ska_low_mccs_spshw"].__version__
        device_name = f'{str(self.__class__).rsplit(".", maxsplit=1)[-1][0:-2]}'
        version = f"{device_name} Software Version: {self._version_id}"
        properties = (
            f"Initialised {device_name} device with properties:\n"
            f"\tSubrackFQDN: {self.SubrackFQDN}\n"
            f"\tSubrackBay: {self.SubrackBay}\n"
            f"\tTileId: {self.TileId}\n"
            f"\tStationId: {self.StationID}\n"
            f"\tTpmIp: {self.TpmIp}\n"
            f"\tTpmCpldPort: {self.TpmCpldPort}\n"
            f"\tTpmVersion (deprecated by HardwareVersion): {self.TpmVersion}\n"
            f"\tHardwareVersion: {self.HardwareVersion}\n"
            f"\tBiosVersion: {self.BiosVersion}\n"
            f"\tAntennasPerTile: {self.AntennasPerTile}\n"
            f"\tPreAduFitted: {self.PreAduFitted}\n"
            f"\tSimulationConfig: {self.SimulationConfig}\n"
            f"\tTestConfig: {self.TestConfig}\n"
            f"\tPollRate: {self.PollRate}\n"
            f"\tPreaduAttenuation: {self.PreaduAttenuation}\n"
            f"\tStaticDelays: {self.StaticDelays}\n"
            f"\tUseAttributesForHealth: {self.UseAttributesForHealth}\n"
        )
        self.logger.info(
            "\n%s\n%s\n%s", str(self.GetVersionInfo()), version, properties
        )

        for attr_name in self._attribute_state:
            verify_events = (
                False if attr_name == "pointingDelays" else self.VerifyEvents
            )
            self.set_change_event(attr_name, True, verify_events)
            self.set_archive_event(attr_name, True, verify_events)

        for attr_name in [
            "firmwareVoltageThresholds",
            "firmwareCurrentThresholds",
            "firmwareTemperatureThresholds",
        ]:
            self.set_change_event(attr_name, True, self.VerifyEvents)
            self.set_archive_event(attr_name, True, self.VerifyEvents)
        self.init_completed()

    def _health_changed_new(
        self: MccsTile, health: HealthState, health_report: str
    ) -> None:
        """
        Handle change in health from new health Model.

        :param health: the new health value
        :param health_report: the health report
        """
        if self._stopping:
            return
        if self.UseAttributesForHealth:
            self._health_report = health_report

            if self._health_state != health:
                self.logger.info(f"Health changed ==> {health=}, {health_report=}")
                self._health_state = health

    def _intermediate_health_changed(
        self: MccsTile,
        group: str,
        health: HealthState,
    ) -> None:
        if self._stopping:
            return

        if self.UseAttributesForHealth:
            if self._intermediate_healths[group] != health:
                self.logger.info(
                    "Intermediate Health changed ==> " f"{group=} {health=}"
                )
                self._intermediate_healths[group] = health

    def _attr_conf_changed(self: MccsTile, attribute_name: str) -> None:
        """
        Handle change in attribute configuration.

        This is a workaround as if you configure an attribute
        which is not alarming to have alarm/warning thresholds
        such that it would be alarming, Tango does not push an event
        until the attribute value changes.

        :param attribute_name: the name of the attribute whose
            configuration has changed.
        """
        if self._stopping:
            return
        if self.UseAttributesForHealth:
            if attribute_name in self._attribute_state:
                value_cache = self._attribute_state[attribute_name].read()
                if value_cache is not None:
                    self.push_change_event(attribute_name, value_cache[0])
                    self.push_archive_event(attribute_name, value_cache[0])
            else:
                # Signal-backed attributes store their last value in the SignalBusMixin
                # cache. Re-pushing without explicit quality lets Tango recompute it
                # against the newly configured thresholds.
                signal_cache = self._SignalBusMixin__attr_values.get(attribute_name)
                if signal_cache is not None:
                    self.push_change_event(attribute_name, signal_cache.value)
                    self.push_archive_event(attribute_name, signal_cache.value)

    def _init_state_model(self: MccsTile) -> None:
        super()._init_state_model()
        self._health_state = HealthState.UNKNOWN  # InitCommand.do() does this too late.

        self.set_change_event("healthState", True, self.VerifyEvents)
        self.set_archive_event("healthState", True, self.VerifyEvents)

        if self.UseAttributesForHealth:
            healthful_attrs = set(self._attribute_state.keys())
            # Add signal-backed attributes that are not in _attribute_state.
            healthful_attrs |= set(MccsTile._HEALTH_SIGNAL_MAP.keys())

            healthful_attrs = healthful_attrs - {
                "dataTransmissionMode",
                "tileProgrammingState",
                "integratedDataTransmissionMode",
                "antennaBufferMode",
                "coreCommunicationStatus",
                # Pointing delay readback is operational metadata, not a health signal.
                # It can be unavailable in valid startup/runtime windows.
                "pointingDelays",
            }

            if is_v1(self.HardwareVersion):
                # Older tiles do not have ADC temperature sensors.
                for idx in range(16):
                    healthful_attrs.discard(f"temperatureADC{idx}")

            if self.BiosVersion == "0.5.0":
                # This monitoring point was introduced in 0.6.0.
                # If we are bios 0.5.0 we ignore it.
                healthful_attrs.discard("timing_pll_40g_count")

            self._health_recorder = TileHealthRecorder(
                self.get_name(),
                logger=self.logger,
                attributes=list(healthful_attrs),
                health_callback=self._health_changed_new,
                attr_conf_callback=self._attr_conf_changed,
                intermediate_health_callback=self._intermediate_health_changed,
                health_groups=self._intermediate_attrs,
            )
        else:
            self._health_model = TileHealthModel(
                self._health_changed,
                self.HardwareVersion,
                self.BiosVersion,
                self.PreAduFitted,
            )
            self._health_recorder = None

    def create_component_manager(
        self: MccsTile,
    ) -> TileComponentManager:
        """
        Create and return a component manager for this device.

        :return: a component manager for this device.
        """
        return TileComponentManager(
            self.SimulationConfig,
            self.TestConfig,
            self.logger,
            self.PollRate,
            self.TileId,
            self.StationID,
            self.TpmIp,
            self.TpmCpldPort,
            self.PreaduAttenuation,
            self.StaticDelays,
            self.SubrackFQDN,
            self.SubrackBay,
            self.PreAduFitted,
            self._communication_state_changed,
            self._component_state_changed,
            self._update_attribute_callback,
            event_serialiser=self._event_serialiser,
            default_lock_timeout=self.DefaultLockTimeout,
            poll_timeout=self.PollLockTimeout,
            power_callback_timeout=self.PowerCallbackLockTimeout,
        )

    # ----------
    # Callbacks
    # ----------
    def _communication_state_changed(
        self: MccsTile, communication_state: CommunicationStatus
    ) -> None:
        """
        Handle change in communications status between component manager and component.

        This is a callback hook, called by the component manager when
        the communications status changes. It is implemented here to
        drive the op_state.

        :param communication_state: the status of communications
            between the component manager and its component.
        """
        super()._communication_state_changed(communication_state)
        if not self.UseAttributesForHealth:
            self._health_model.update_state(
                communicating=(communication_state == CommunicationStatus.ESTABLISHED)
            )

    def _handle_firmware_read(self: MccsTile) -> None:
        """Handle a firmware read by pushing appropriate attribute events."""
        hw_threshold_cache = self.hw_firmware_thresholds.to_device_property_dict()

        for group, attr_value in hw_threshold_cache.items():
            group_attribute_map = {
                "voltages": "firmwareVoltageThresholds",
                "currents": "firmwareCurrentThresholds",
                "temperatures": "firmwareTemperatureThresholds",
            }
            serialised_value = json.dumps(attr_value)
            self.push_change_event(group_attribute_map[group], serialised_value)
            self.push_archive_event(group_attribute_map[group], serialised_value)

    # pylint: disable=too-many-branches
    def _check_database_match(self: MccsTile) -> bool:
        """
        Compare firmware thresholds from the database against read values.

        Ignores any thresholds marked as 'Undefined' in the database.

        :returns: True if all defined DB values match the read values, else False.
        """
        db_thresholds_cache = self.db_firmware_thresholds.to_device_property_dict()
        hw_threshold_cache = self.hw_firmware_thresholds.to_device_property_dict()

        self.logger.debug(f"{db_thresholds_cache=}")
        self.logger.debug(f"{hw_threshold_cache=}")

        error_msgs: list[str] = []

        for group, db_thresholds in db_thresholds_cache.items():
            read_threshold_group = hw_threshold_cache.get(group, {})

            for threshold, db_value in db_thresholds.items():
                if db_value == "Undefined":
                    continue  # Skip undefined thresholds in db

                read_value = read_threshold_group.get(threshold)
                if read_value is None or db_value != read_value:
                    error_msgs.append(
                        f"[{group}.{threshold}] DB={db_value!r}, HW={read_value!r}"
                    )

        if error_msgs:
            joined_msg = "; ".join(error_msgs)
            self.logger.error(f"Database mismatch detected: {joined_msg}")
            self._component_state_changed(
                db_configuration_fault=(True, f"Configuration mismatch: {joined_msg}")
            )
            return False

        self._component_state_changed(
            db_configuration_fault=(False, "Configuration match")
        )
        return True

    def _update_attribute_callback(
        self: MccsTile,
        mark_invalid: bool = False,
        **state_change: Any,
    ) -> None:
        for attribute_name, attribute_value in state_change.items():
            if attribute_name == "tile_health_structure":
                if mark_invalid:
                    self.tile_health_structure = {}
                elif attribute_value is None:
                    pass
                else:
                    merge(self.tile_health_structure, attribute_value)
                if not self.UseAttributesForHealth:
                    self._health_model.update_state(
                        tile_health_structure=self.tile_health_structure
                    )
                self.update_tile_health_attributes(mark_invalid=mark_invalid)
            elif attribute_name == "firmware_thresholds":
                self.logger.debug(
                    "hw read thresholds reporting "
                    f"{attribute_value.to_device_property_dict()}"
                )
                self.hw_firmware_thresholds = attribute_value
                self._check_database_match()
                self._handle_firmware_read()

            elif attribute_name == "global_status_alarms":
                self.unpack_alarms(attribute_value, mark_invalid=mark_invalid)
            else:
                try:
                    tango_name = self.attr_map[attribute_name]
                    if mark_invalid:
                        self._attribute_state[tango_name].mark_stale()
                    else:
                        self._attribute_state[tango_name].update(attribute_value)

                except KeyError as e:
                    self.logger.error(f"Key Error {repr(e)}")
                except Exception as e:  # pylint: disable=broad-except
                    self.logger.error(
                        f"Caught unexpected exception {attribute_name=}: {repr(e)}"
                    )

    # TODO: Upstream this interface change to SKABaseDevice
    # pylint: disable-next=arguments-differ
    def _component_state_changed(  # type: ignore[override]
        self: MccsTile,
        *,
        fault: bool | None = None,
        power: PowerState | None = None,
        db_configuration_fault: tuple[bool, str] | None = None,
        **state_change: Any,
    ) -> None:
        """
        Handle change in the state of the component.

        This is a callback hook, called by the component manager when
        the state of the component changes.

        :param fault: whether the component is in fault or not
        :param power: the power state of the component
        :param state_change: other state updates
        :param db_configuration_fault: a tuple with status and information
            about whether we are experiencing a configuration fault.
        """
        if power is not None:
            self.power_state = power
        if fault is not None:
            self.component_manager_fault = fault
        if db_configuration_fault is not None:
            self.db_configuration_fault = db_configuration_fault

        # Propagate power state to base implementation
        super()._component_state_changed(power=power)

        if power in (PowerState.OFF, PowerState.UNKNOWN):
            for attr in self._attribute_state.values():
                try:
                    attr.mark_stale()
                except Exception as exc:  # pylint: disable=broad-except
                    self.logger.warning(
                        "Failed to mark %r as stale: %s",
                        attr,
                        exc,
                        exc_info=True,
                    )
            for signal in self._HEALTH_SIGNAL_MAP.values():
                setattr(self, signal, None)
        # Only evaluate and propagate fault if the tile is ON
        if self.power_state == PowerState.ON:
            super()._component_state_changed(
                fault=self._evaluate_fault(
                    db_configuration_fault=db_configuration_fault, polling_fault=fault
                )
            )

        if not self.UseAttributesForHealth:
            if power is not None:
                self._health_model.update_state(fault=fault, power=power)
            else:
                self._health_model.update_state(fault=fault)

    def _evaluate_fault(
        self: MccsTile,
        db_configuration_fault: tuple[bool, str] | None = None,
        polling_fault: bool | None = None,
    ) -> bool | None:
        if polling_fault is not None:
            self.component_manager_fault = polling_fault
            self.status_information["polling_fault"] = (
                "No fault"
                if self.component_manager_fault is False
                else "Reported power from subrack in dissagreement with polling"
            )

        if db_configuration_fault is not None:
            self.db_configuration_fault = db_configuration_fault
            self.status_information[
                "firmware_configuration_status"
            ] = self.db_configuration_fault[1]

        # Extract current effective flags
        cm_fault = self.component_manager_fault
        db_fault_flag = (
            self.db_configuration_fault[0] if self.db_configuration_fault else None
        )
        # Fault evaluation logic.
        # Case 1: Both None → insufficient info
        if cm_fault is None and db_fault_flag is None:
            self.logger.debug(
                f"Incomplete fault information: "
                f"{self.db_configuration_fault=}, {self.component_manager_fault=}"
            )
            has_fault = None
        # Case 2: Any True → overall True
        elif cm_fault is True or db_fault_flag is True:
            has_fault = True
        # Case 3: Both explicitly False → overall False
        elif cm_fault is False and db_fault_flag is False:
            has_fault = False
        # Case 4: One None, one False → still uncertain → None
        else:
            has_fault = None

        # Log and update component status if a fault is detected
        if has_fault is True:
            fault_json = json.dumps(self.status_information)
            self.logger.error(f"Fault detected: {fault_json}")
            self.set_status(status=fault_json)

        return has_fault

    def unpack_alarms(
        self: MccsTile,
        alarms: dict[str, int],
        mark_invalid: bool = False,
    ) -> None:
        """
        Unpack a dictionary of alarms.

        :param alarms: The alarms we want to unpack.
        :param mark_invalid: mark attribute as invalid.
        """
        if mark_invalid or alarms is None:
            for alarm_name, _ in self.__alarm_attribute_map.items():
                self.logger.warning(
                    f"Unable to read {alarm_name}, logging as invalid. "
                    "However, attribute value is "
                    f"last known value: {self._attribute_state[alarm_name].read()}"
                )
        else:
            for alarm_name, alarm_path in self.__alarm_attribute_map.items():
                alarm_value = alarms.get(alarm_path)
                self._attribute_state[alarm_name].update(alarm_value)

    def update_tile_health_attributes(
        self: MccsTile, mark_invalid: bool = False
    ) -> None:
        """
        Update TANGO attributes from the tile health structure dictionary.

        :param mark_invalid: True when values being reported are not valid.
        """
        for (
            attribute_name,
            dictionary_path,
        ) in self.attribute_monitoring_point_map.items():
            if mark_invalid:
                if attribute_name in self._attribute_state:
                    self._attribute_state[attribute_name].mark_stale()
                elif attribute_name in self._HEALTH_SIGNAL_MAP:
                    setattr(self, self._HEALTH_SIGNAL_MAP[attribute_name], None)
                else:
                    self.logger.warning(f"Attribute {attribute_name} not found.")
                continue

            try:
                attribute_value = reduce(
                    getitem, dictionary_path, self.tile_health_structure
                )
            except KeyError:
                self.logger.debug(
                    f"Failed to find attribute {attribute_name}, "
                    "likely it hasn't been polled yet."
                )
                attribute_value = None

            try:
                if attribute_name in self._attribute_state:
                    self._attribute_state[attribute_name].update(attribute_value)
                elif attribute_name in self._HEALTH_SIGNAL_MAP:
                    setattr(
                        self,
                        self._HEALTH_SIGNAL_MAP[attribute_name],
                        attribute_value,
                    )
                else:
                    self.logger.warning(f"Attribute {attribute_name} not found.")
            except Exception as e:  # pylint: disable=broad-except
                # Note: attribute converters were removed in
                # https://gitlab.com/ska-telescope/mccs/ska-low-mccs-spshw/-/merge_requests/297
                # These converters added in skb-520 can be implemented
                # now that skb-609 is fixed.
                self.logger.error(
                    f"Caught unexpected exception {attribute_name=}: {repr(e)}"
                )

    def _health_changed(self: MccsTile, health: HealthState) -> None:
        """
        Handle change in this device's health state.

        This is a callback hook, called whenever the HealthModel's
        evaluated health state changes. It is responsible for updating
        the tango side of things i.e. making sure the attribute is up to
        date, and events are pushed.

        :param health: the new health value
        """
        if self._stopping:
            return
        if self._health_state != health:
            self._health_state = health

    def shutdown_on_max_alarm(self: MccsTile, attr_name: str) -> None:
        """
        Turn off TPM when attribute in question is in max_alarm state.

        :param attr_name: the name of the attribute causing the shutdown.
        """
        # ============================================
        # Only shutdown if we are not already stopping
        # ============================================
        if not self._stopping:
            try:
                attr = self.get_device_attr().get_attr_by_name(attr_name)
                attr_mgr = self._attribute_state.get(attr_name)
                attr_value = attr_mgr.read() if attr_mgr is not None else "N/A"
                if attr.is_max_alarm():
                    self.logger.warning(
                        f"Attribute {attr_name} changed to {attr_value}, "
                        "this is above maximum alarm, Shutting down TPM."
                    )
                    self.component_manager.off()
            except Exception as e:  # pylint: disable=broad-except
                self.logger.error(
                    f"Unable to read shutdown attribute ALARM status : {repr(e)}, "
                    "Shutting down TPM."
                )
                self.component_manager.off()

    def notify_emission(self: MccsTile, signal: str, value: Any) -> None:
        """
        Handle signal emissions, pushing tango events and checking alarms.

        Overrides the base class to trigger alarm checking for signal-based
        attributes after their tango events have been pushed.

        :param signal: the absolute name of the signal that was emitted
        :param value: the emitted value
        """
        super().notify_emission(signal, value)
        if value is None or signal not in self._alarm_signal_map:
            return
        tango_attr_name = self._alarm_signal_map[signal]
        # on_emission only calls push_change_event; set_value + check_alarm are
        # needed so that Tango's internal alarm state (is_max_alarm()) is updated,
        # mirroring what post_change_event does for AttributeManager-backed attrs.
        self.get_device_attr().get_attr_by_name(tango_attr_name).set_value(
            cast(float, value)
        )
        self.get_device_attr().check_alarm(tango_attr_name)
        self.shutdown_on_max_alarm(tango_attr_name)

    def post_change_event(
        self: MccsTile,
        name: str,
        attr_value: Any,
        attr_time: float,
        attr_quality: tango.AttrQuality,
    ) -> None:
        """
        Post a Archive and Change TANGO event.

        :param name: the name of the TANGO attribute to push
        :param attr_value: The value of the attribute.
        :param attr_time: A parameter specifying the
            time the attribute was updated.
        :param attr_quality: A paramter specifying the
            quality factor of the attribute.
        """
        if attr_value is None:
            self.get_device_attr().get_attr_by_name(name).set_quality(
                tango.AttrQuality.ATTR_INVALID, True
            )
            return
        if isinstance(attr_value, dict):
            attr_value = json.dumps(attr_value)
        if attr_quality == tango.AttrQuality.ATTR_INVALID:
            self.logger.debug(f"{name} -> {tango.AttrQuality.ATTR_INVALID.name}")
        else:
            self.logger.debug(f"{name} = {attr_value}")
        self.push_archive_event(name, attr_value, attr_time, attr_quality)
        self.push_change_event(name, attr_value, attr_time, attr_quality)

        if self._stopping:
            # ===============================================
            # Calling multi_attr methods on teardown causes segfault
            # during startup, yes startup (check_alarm) during
            # subscriptions, event thought we are joining this thread
            # from delete_device. Figure that!
            # Tango::Attribute::general_check_alarm<short>
            # (Tango::AttrQuality const&, short const&, short const&) ()
            # returning here appears to remove segfault, alternativly a
            # large sleep of 30 seconds during startup will remove the
            # occurance of a segfault. This issues was identified in
            # skb-1079, but the root issues lies in cpptango.
            # During investigation the following ticket was created
            # https://gitlab.com/tango-controls/cppTango/-/issues/1585
            # was raised. Available in pytango 10.3.0 release.
            # ===============================================
            return
        # https://gitlab.com/tango-controls/pytango/-/issues/615
        # set_value must be called after push_change_event.
        # it seems that fire_change_event will consume the
        # value set meaning a check_alarm has a nullptr.
        self.get_device_attr().get_attr_by_name(name).set_value(attr_value)
        try:
            # Update the attribute ALARM status.
            self.get_device_attr().check_alarm(name)
        except tango.DevFailed:
            # no alarm defined
            pass

    def _convert_ip_to_str(self: MccsTile, nested_dict: dict[str, Any]) -> None:
        """
        Convert IPAddresses to str in (possibly nested) dict.

        :param nested_dict: A (possibly nested) dict with IPAddresses to convert.
        """
        for k, v in nested_dict.items():
            if isinstance(v, IPv4Address):
                nested_dict[k] = str(v)
            elif isinstance(v, dict):
                self._convert_ip_to_str(v)

    # ----------
    # Attributes
    # ----------
    boardTemperature = attribute_from_signal(  # noqa: N815
        board_temperature_signal,
        dtype="DevDouble",
        abs_change=0.1,
        archive_abs_change=0.1,
        min_value=15.0,
        max_value=70.0,
        min_alarm=15.0,
        max_alarm=70.0,
        min_warning=16.0,
        max_warning=65.0,
        doc="Board temperature in degrees Celsius.",
    )

    @attribute(
        dtype=(("DevShort",),),
        max_dim_x=16,
        max_dim_y=2,
        label="adc_pll_lock_status",
        min_alarm=0,
        abs_change=1,
        archive_abs_change=1,
    )
    def adc_pll_lock_status(self: MccsTile) -> np.ndarray:
        """
        Return the pll status of all 16 ADCs.

        The first list represents the pll status of the ADCs in order.
        The second list represents the lock lost counter for ADCs in order.

        Expected: `1` if PLL locked and loss of lock flag is low
            (lock has not fallen).

        :example:
            >>> tile.adc_pll_lock_status
            [[1]*16,[1]*16]

        :return: the pll status of all ADCs
        """
        return self._attribute_state["adc_pll_lock_status"].read()

    @attribute(dtype="DevBoolean", label="tile_beamformer_status")
    def tile_beamformer_status(self: MccsTile) -> bool:
        """
        Return the status of the tile beamformer.

        Expected: `True` if status OK.

        :example:
            >>> tile.tile_beamformer_status
            True


        :return: the status of the tile beamformer.
        """
        return self._attribute_state["tile_beamformer_status"].read()

    @attribute(dtype="DevBoolean", label="station_beamformer_status")
    def station_beamformer_status(self: MccsTile) -> bool:
        """
        Return the status of the station beamformer.

        Expected: `True` if status OK.

        :example:
            >>> tile.station_beamformer_status
            True

        :return: the status of the station beamformer.
        """
        return self._attribute_state["station_beamformer_status"].read()

    @attribute(
        dtype="DevShort",
        label="fpga0_station_beamformer_error_count",
        max_alarm=1,
        abs_change=1,
        archive_abs_change=1,
    )
    def fpga0_station_beamformer_error_count(self: MccsTile) -> int:
        """
        Return the station beamformer error count for FPGA0.

        Expected: 0 if no parity errors detected.

        :example:
            >>> tile.fpga0_station_beamformer_error_count
            0

        :return: the station beamformer error count for FPGA0.
        """
        return self._attribute_state["fpga0_station_beamformer_error_count"].read()

    @attribute(
        dtype="DevShort",
        label="fpga1_station_beamformer_error_count",
        max_alarm=1,
        abs_change=1,
        archive_abs_change=1,
    )
    def fpga1_station_beamformer_error_count(self: MccsTile) -> int:
        """
        Return the station beamformer error count for FPGA1.

        Expected: 0 if no parity errors detected.

        :example:
            >>> tile.fpga1_station_beamformer_error_count
            0

        :return: the station beamformer error count for FPGA1.
        """
        return self._attribute_state["fpga1_station_beamformer_error_count"].read()

    @attribute(
        dtype="DevShort",
        label="fpga0_station_beamformer_flagged_count",
        max_alarm=1,
        abs_change=1,
        archive_abs_change=1,
    )
    def fpga0_station_beamformer_flagged_count(self: MccsTile) -> int:
        """
        Return the station beamformer error count for FPGA0.

        Note: When station beam flagging is enabled,
        this returns a count of packets flagged,
        but when station beam flagging is disabled,
        this instead returns a count of packets discarded/dropped

        Expected: 0 if no parity errors detected.

        :example:
            >>> tile.fpga0_station_beamformer_flagged_count
            0

        :return: the station beamformer error count for FPGA0.
        """
        return self._attribute_state["fpga0_station_beamformer_flagged_count"].read()

    @attribute(
        dtype="DevShort",
        label="fpga1_station_beamformer_flagged_count",
        max_alarm=1,
        abs_change=1,
        archive_abs_change=1,
    )
    def fpga1_station_beamformer_flagged_count(self: MccsTile) -> int:
        """
        Return the station beamformer error count for FPGA1.

        Note: When station beam flagging is enabled,
        this returns a count of packets flagged,
        but when station beam flagging is disabled,
        this instead returns a count of packets discarded/dropped

        Expected: 0 if no parity errors detected.

        :example:
            >>> tile.fpga1_station_beamformer_flagged_count
            0

        :return: the station beamformer error count for FPGA1.
        """
        return self._attribute_state["fpga1_station_beamformer_flagged_count"].read()

    @attribute(
        dtype="DevShort",
        label="fpga0_crc_error_count",
        max_alarm=1,
        abs_change=1,
        archive_abs_change=1,
    )
    def fpga0_crc_error_count(self: MccsTile) -> int:
        """
        Return the crc error count for FPGA0.

        Expected: 0 if no Cyclic Redundancy Check (CRC) errors detected.

        :example:
            >>> tile.fpga0_crc_error_count
            0

        :return: the crc error count for FPGA0.
        """
        return self._attribute_state["fpga0_crc_error_count"].read()

    @attribute(
        dtype="DevShort",
        label="fpga1_crc_error_count",
        max_alarm=1,
        abs_change=1,
        archive_abs_change=1,
    )
    def fpga1_crc_error_count(self: MccsTile) -> int:
        """
        Return the crc error count for FPGA1.

        Expected: 0 if no Cyclic Redundancy Check (CRC) errors detected.

        :example:
            >>> tile.fpga1_crc_error_count
            0

        :return: the crc error count for FPGA0.
        """
        return self._attribute_state["fpga1_crc_error_count"].read()

    @attribute(
        dtype=("DevShort",),
        max_dim_x=4,
        label="fpga0_bip_error_count",
        max_alarm=1,
        abs_change=1,
        archive_abs_change=1,
    )
    def fpga0_bip_error_count(self: MccsTile) -> list[int]:
        """
        Return the bip error count for FPGA0.

        Expected: 0 if no bit-interleaved parity (BIP) errors detected.

        :example:
            >>> tile.fpga0_bip_error_count
            [0, 0, 0, 0]

        :return: the bip error count for FPGA0.
        """
        return self._attribute_state["fpga0_bip_error_count"].read()

    @attribute(
        dtype=("DevShort",),
        max_dim_x=4,
        label="fpga1_bip_error_count",
        max_alarm=1,
        abs_change=1,
        archive_abs_change=1,
    )
    def fpga1_bip_error_count(self: MccsTile) -> list[int]:
        """
        Return the bip error count for FPGA1.

        Expected: 0 if no bit-interleaved parity (BIP) errors detected.

        :example:
            >>> tile.fpga1_bip_error_count
            [0, 0, 0, 0]

        :return: the bip error count for FPGA1.
        """
        return self._attribute_state["fpga1_bip_error_count"].read()

    @attribute(
        dtype=("DevShort",),
        max_dim_x=4,
        label="fpga1_decode_error_count",
        max_alarm=1,
        abs_change=1,
        archive_abs_change=1,
    )
    def fpga1_decode_error_count(self: MccsTile) -> list[int]:
        """
        Return the decode error count per FPGA.

        Expected: 0 if errors have not been detected.
            Note: This counter increments when at least one error is
            detected in a clock cycle.

        :example:
            >>> tile.fpga1_decode_error_count
            [0, 0, 0, 0]

        :return: the decode error count per FPGA.
        """
        return self._attribute_state["fpga1_decode_error_count"].read()

    @attribute(
        dtype=("DevShort",),
        max_dim_x=4,
        label="fpga0_decode_error_count",
        max_alarm=1,
        abs_change=1,
        archive_abs_change=1,
    )
    def fpga0_decode_error_count(self: MccsTile) -> list[int]:
        """
        Return the decode error count per FPGA.

        Expected: 0 if errors have not been detected.
            Note: This counter increments when at least one error is
            detected in a clock cycle.

        :example:
            >>> tile.fpga0_decode_error_count
            [0, 0, 0, 0]

        :return: the decode error count per FPGA.
        """
        return self._attribute_state["fpga0_decode_error_count"].read()

    @attribute(
        dtype="DevShort",
        label="fpga0_linkup_loss_count",
        max_alarm=1,
        abs_change=1,
        archive_abs_change=1,
    )
    def fpga0_linkup_loss_count(self: MccsTile) -> int:
        """
        Return the linkup loss count.

        Expected: 0 if no link loss events are detected.

        :example:
            >>> tile.fpga0_linkup_loss_count
            0

        :return: the linkup loss count.
        """
        return self._attribute_state["fpga0_linkup_loss_count"].read()

    @attribute(
        dtype="DevShort",
        label="fpga1_linkup_loss_count",
        max_alarm=1,
        abs_change=1,
        archive_abs_change=1,
    )
    def fpga1_linkup_loss_count(self: MccsTile) -> int:
        """
        Return the linkup loss count.

        Expected: 0 if no link loss events are detected.

        :example:
            >>> tile.fpga1_linkup_loss_count
            0

        :return: the linkup loss count.
        """
        return self._attribute_state["fpga1_linkup_loss_count"].read()

    @attribute(
        dtype="DevShort",
        label="fpga0_data_router_status",
        max_alarm=1,
        abs_change=1,
        archive_abs_change=1,
    )
    def fpga0_data_router_status(self: MccsTile) -> int:
        """
        Return the status of the data router.

        Expected: 0 if no status OK.

        :example:
            >>> tile.fpga0_data_router_status
            0

        :return: the linkup loss count per FPGA.
        """
        return self._attribute_state["fpga0_data_router_status"].read()

    @attribute(
        dtype="DevShort",
        label="fpga1_data_router_status",
        max_alarm=1,
        abs_change=1,
        archive_abs_change=1,
    )
    def fpga1_data_router_status(self: MccsTile) -> int:
        """
        Return the status of the data router.

        Expected: 0 if no status OK.

        :example:
            >>> tile.fpga1_data_router_status
            0

        :return: the linkup loss count per FPGA.
        """
        return self._attribute_state["fpga1_data_router_status"].read()

    @attribute(
        dtype="DevString",
        label="data_router_discarded_packets",
    )
    def data_router_discarded_packets(self: MccsTile) -> str:
        """
        Return the number of discarded packets.

        Expected: 0 if no packets are discarded.

        :example:
            >>> tile.data_router_discarded_packets
            '{"FPGA0": [0, 0], "FPGA1": [0, 0]}'

        :return: the linkup loss count per FPGA.
        """
        # NOTE: This is not implemented in ska-low-sps-tpm-api. it will
        # always return '{"FPGA0": [0, 0], "FPGA1": [0, 0]}'.
        return self._attribute_state["data_router_discarded_packets"].read()

    @attribute(
        dtype="DevBoolean",
        label="arp",
    )
    def arp(self: MccsTile) -> bool:
        """
        Return the arp status.

        Expected: `True` if table entries are valid and resolved.

        :example:
            >>> tile.arp
            True

        :return: the arp status.
        """
        return self._attribute_state["arp"].read()

    @attribute(
        dtype="DevBoolean",
        label="udp_status",
    )
    def udp_status(self: MccsTile) -> bool:
        """
        Return the UDP status.

        Expected: `True` if virtual lanes aligned and no BIP or CRC errors.

        :example:
            >>> tile.udp_status
            False

        :return: the UDP status.
        """
        return self._attribute_state["udp_status"].read()

    @attribute(
        dtype="DevBoolean",
        label="ddr_initialisation",
    )
    def ddr_initialisation(self: MccsTile) -> bool:
        """
        Return the ddr initialisation status.

        Expected: True if DDR interface was successfully initialised.

        :example:
            >>> tile.ddr_initialisation
            True

        :return: the ddr initialisation status.
        """
        return self._attribute_state["ddr_initialisation"].read()

    @attribute(
        dtype="DevShort",
        label="fpga0_ddr_reset_counter",
        max_alarm=1,
        abs_change=1,
        archive_abs_change=1,
    )
    def fpga0_ddr_reset_counter(self: MccsTile) -> int:
        """
        Return the ddr reset count.

        Expected: 0 if no reset events have occurred.

        :example:
            >>> tile.fpga0_ddr_reset_counter
            0

        :return: the ddr reset count.
        """
        return self._attribute_state["fpga0_ddr_reset_counter"].read()

    @attribute(
        dtype="DevShort",
        label="fpga1_ddr_reset_counter",
        max_alarm=1,
        abs_change=1,
        archive_abs_change=1,
    )
    def fpga1_ddr_reset_counter(self: MccsTile) -> int:
        """
        Return the ddr reset count.

        Expected: 0 if no reset events have occurred.

        :example:
            >>> tile.fpga1_ddr_reset_counter
            0

        :return: the ddr reset count.
        """
        return self._attribute_state["fpga1_ddr_reset_counter"].read()

    @attribute(
        dtype="DevShort",
        label="f2f_soft_errors",
        max_alarm=1,
        min_alarm=-1,
        abs_change=1,
        archive_abs_change=1,
    )
    def f2f_soft_errors(self: MccsTile) -> int:
        """
        Return the f2f interface soft error count.

        Expected: 0 if no soft errors detected in FPGA-to-FPGA interface.

        :example:
            tile.f2f_soft_errors
            0

        :return: the f2f interface soft error count.
        """
        return self._attribute_state["f2f_soft_errors"].read()

    @attribute(
        dtype="DevShort",
        label="f2f_hard_errors",
        max_alarm=1,
        min_alarm=-1,
        abs_change=1,
        archive_abs_change=1,
    )
    def f2f_hard_errors(self: MccsTile) -> int:
        """
        Return the f2f interface hard error count.

        Expected: 0 if no hard errors detected in FPGA-to-FPGA interface.
            Hard errors require the interface to be reset. This likely means
            reinitialising the TPM entirely due to the impact on beamformers.

        :example:
            >>> tile.f2f_hard_errors
            0

        :return: the f2f interface hard error count.
        """
        return self._attribute_state["f2f_hard_errors"].read()

    @attribute(
        dtype="DevShort",
        label="fpga0_resync_count",
        max_alarm=1,
        abs_change=1,
        archive_abs_change=1,
    )
    def fpga0_resync_count(self: MccsTile) -> int:
        """
        Return the resync count.

        Expected: 0 if no resync events have ocurred.

        :example:
            >>> tile.fpga0_resync_count
            0

        :return: the resync count
        """
        return self._attribute_state["fpga0_resync_count"].read()

    @attribute(
        dtype="DevShort",
        label="fpga1_resync_count",
        max_alarm=1,
        abs_change=1,
        archive_abs_change=1,
    )
    def fpga1_resync_count(self: MccsTile) -> int:
        """
        Return the resync count.

        Expected: 0 if no resync events have ocurred.

        :example:
            >>> tile.fpga1_resync_count
            0

        :return: the resync count
        """
        return self._attribute_state["fpga1_resync_count"].read()

    @attribute(
        dtype="DevBoolean",
        label="lane_status",
    )
    def lane_status(self: MccsTile) -> bool:
        """
        Return the lane status.

        Expected: `True` if no errors detected on any lane.

        :example:
            >>> tile.lane_status
            True

        :return: the lane status.
        """
        return self._attribute_state["lane_status"].read()

    @attribute(
        dtype="DevBoolean",
        label="link_status",
    )
    def link_status(self: MccsTile) -> bool:
        """
        Return the jesd link status.

        Expected: `True` if link up and synchronised.

        :example:
            >>> tile.link_status
            True

        :return: the link status.
        """
        return self._attribute_state["link_status"].read()

    @attribute(
        dtype=(("DevShort",),),
        max_dim_x=8,  # lane
        max_dim_y=2,  # core
        label="fpga1_lane_error_count",
        max_alarm=1,
        abs_change=1,
        archive_abs_change=1,
    )
    def fpga1_lane_error_count(self: MccsTile) -> list[int]:
        """
        Return the error count per lane, per core.

        Expected: 0 for all lanes.

        :example:
            >>> tile.fpga1_lane_error_count
            [ [0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0] ]

        :return: the error count per lane, per core
            [[Core0],[Core1]]
        """
        return self._attribute_state["fpga1_lane_error_count"].read()

    @attribute(
        dtype=(("DevShort",),),
        max_dim_x=8,  # lane
        max_dim_y=2,  # core
        label="fpga0_lane_error_count",
        max_alarm=1,
        abs_change=1,
        archive_abs_change=1,
    )
    def fpga0_lane_error_count(self: MccsTile) -> list[int]:
        """
        Return the error count per lane, per core.

        Expected: 0 for all lanes.

        :example:
            >>> tile.fpga0_lane_error_count
            [ [0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0] ]


        :return: the error count per lane, per core
            [[Core0lanes],[Core1lanes]]
        """
        return self._attribute_state["fpga0_lane_error_count"].read()

    @attribute(
        dtype=("DevShort",),
        max_dim_x=3,  # fpga
        label="fpga0_clock_managers_count",
        max_alarm=1,
        abs_change=1,
        archive_abs_change=1,
    )
    def fpga0_clock_managers_count(self: MccsTile) -> list[int]:
        """
        Return the PLL lock loss counter for C2C, JESD and DSP.

        Expected: `0` per interface if no lock loss events.

        :example:
            >>> tile.fpga0_clock_managers_count
            [0, 0, 0]

        3 rows → one for each MMCM type: ["C2C_MMCM", "JESD_MMCM", "DSP_MMCM"]

        :return: the lock loss counter for ["C2C_MMCM", "JESD_MMCM", "DSP_MMCM"].
        """
        return self._attribute_state["fpga0_clock_managers_count"].read()

    @attribute(
        dtype=("DevShort",),
        max_dim_x=3,  # clock_managers
        label="fpga0_clock_managers_status",
        min_alarm=0,
        abs_change=1,
        archive_abs_change=1,
    )
    def fpga0_clock_managers_status(self: MccsTile) -> list[int]:
        """
        Return the PLL lock status C2C, JESD and DSP.

        Expected: `1` if MMCM clock locked `0` otherwise

        :example:
            >>> tile.fpga0_clock_managers_status
            [0, 0, 0]


        3 rows → one for each MMCM type: ["C2C_MMCM", "JESD_MMCM", "DSP_MMCM"]

        :return: the clock status for ["C2C_MMCM", "JESD_MMCM", "DSP_MMCM"].
        """
        return self._attribute_state["fpga0_clock_managers_status"].read()

    @attribute(
        dtype=("DevShort",),
        max_dim_x=3,  # clock_managers
        label="fpga1_clock_managers_count",
        max_alarm=1,
        abs_change=1,
        archive_abs_change=1,
    )
    def fpga1_clock_managers_count(self: MccsTile) -> list[int]:
        """
        Return the PLL lock loss counter for C2C, JESD and DSP.

        Expected: `0` per interface if no lock loss events.

        :example:
            >>> tile.fpga1_clock_managers_count
            [0, 0, 0]

        3 rows → one for each MMCM type: ["C2C_MMCM", "JESD_MMCM", "DSP_MMCM"]

        :return: the lock loss counter for ["C2C_MMCM", "JESD_MMCM", "DSP_MMCM"].
        """
        return self._attribute_state["fpga1_clock_managers_count"].read()

    @attribute(
        dtype=("DevShort",),
        max_dim_x=3,  # clock_managers
        label="fpga1_clock_managers_status",
        min_alarm=0,
        abs_change=1,
        archive_abs_change=1,
    )
    def fpga1_clock_managers_status(self: MccsTile) -> list[int]:
        """
        Return the PLL lock status for C2C, JESD and DSP.

        Expected: `1` if MMCM clock locked `0` otherwise

        :example:
            >>> tile.fpga1_clock_managers_status
            [0, 0, 0]


        3 rows → one for each MMCM type: ["C2C_MMCM", "JESD_MMCM", "DSP_MMCM"]

        :return: the clock status for ["C2C_MMCM", "JESD_MMCM", "DSP_MMCM"].
        """
        return self._attribute_state["fpga1_clock_managers_status"].read()

    @attribute(
        dtype="DevLong",
        label="ddr_write_size",
    )
    def ddr_write_size(self: MccsTile) -> int:
        """
        Return the ddr write size obtained from running start_antenna_buffer.

        :example:
            >>> tile.ddr_write_size

        :return: ddr write size of a frame
        """
        return self.component_manager.ddr_write_size

    # @attribute(
    #     dtype="DevString",
    #     label="ddr_rd_cnt",
    # )
    # def ddr_rd_cnt(self: MccsTile) -> str:
    #     """
    #     Return the read counter of the ddr interface.

    #     Expected: `integer` number of times ddr interface has been read.

    #     :example:
    #         >>> tile.ddr_rd_cnt
    #         '{"FPGA0": 0,
    #         "FPGA1": 0}'

    #     :return: number of times ddr interface has been read.
    #     """
    #     return self._attribute_state["ddr_rd_cnt"].read())

    # @attribute(
    #     dtype="DevString",
    #     label="ddr_wr_cnt",
    # )
    # def ddr_wr_cnt(self: MccsTile) -> str:
    #     """
    #     Return the write counter of the ddr interface.

    #     Expected: `integer` number of times ddr interface has been written to.

    #     :example:
    #         >>> tile.ddr_wr_cnt
    #         '{"FPGA0": 0,
    #         "FPGA1": 0}'

    #     :return: number of times ddr interface has been written to.
    #     """
    #     return self._attribute_state["ddr_wr_cnt"].read())

    # @attribute(
    #     dtype="DevString",
    #     label="ddr_rd_dat_cnt",
    # )
    # def ddr_rd_dat_cnt(self: MccsTile) -> str:
    #     """
    #     Return the read valid counter of the ddr interface.

    #     Expected: `integer` number of times ddr interface has responded to a read
    #     with valid data.

    #     :example:
    #         >>> tile.ddr_rd_dat_cnt
    #         '{"FPGA0": 0,
    #         "FPGA1": 0}'

    #     :return: number of times ddr interface
    #       has responded to a read with valid data.
    #     """
    #     return self._attribute_state["ddr_rd_dat_cnt"].read())

    @attribute(
        dtype=("DevShort",),
        max_dim_x=3,  # clocks
        label="fpga0_clocks",
        min_alarm=0,
        abs_change=1,
        archive_abs_change=1,
    )
    def fpga0_clocks(self: MccsTile) -> list[int]:
        """
        Return the status of clocks for the interfaces of FPGA0.

        Expected: `1` per interface if status is OK. `0` if
        not OK.

        :example:
            >>> tile.fpga0_clocks
            [1, 1, 1]

        :return: the status of clocks for the interfaces of FPGA0.
            [1, 1, 1] == [JESD, DDR, UDP]
        """
        return self._attribute_state["fpga0_clocks"].read()

    @attribute(
        dtype=("DevShort",),
        max_dim_x=3,  # clocks
        label="fpga1_clocks",
        min_alarm=0,
        abs_change=1,
        archive_abs_change=1,
    )
    def fpga1_clocks(self: MccsTile) -> str:
        """
        Return the status of clocks for the interfaces of FPGA1.

        Expected: `1` per interface if status is OK. `0` if
        not OK.

        :example:
            >>> tile.fpga1_clocks
            [1, 1, 1]

        :return: the status of clocks for the interfaces of FPGA1.
            [1, 1, 1] == [JESD, DDR, UDP]
        """
        return self._attribute_state["fpga1_clocks"].read()

    @attribute(
        dtype=("DevShort",),
        max_dim_x=16,  # ADC Channels
        label="adc_sysref_counter",
        min_alarm=0,  # SYSREF not present
        abs_change=1,
        archive_abs_change=1,
    )
    def adc_sysref_counter(self: MccsTile) -> str:
        """
        Return the sysref_counter of all ADCs.

        Expected: `1` if SYSREF counter is incrementing (SYSREF is present),
        `0` if not present.

        :example:
            >>> tile.adc_sysref_counter
            [1] * 16

        :return: the sysref_counter of all ADCs
            idx0->ADC0, idx1->ADC1, ... idx15->ADC15
        """
        return self._attribute_state["adc_sysref_counter"].read()

    @attribute(
        dtype=("DevShort",),
        max_dim_x=16,  # ADC Channels
        label="adc_sysref_timing_requirements",
        min_alarm=0,  # requirements not met
        abs_change=1,
        archive_abs_change=1,
    )
    def adc_sysref_timing_requirements(self: MccsTile) -> str:
        """
        Return the sysref_timing_requirements of all ADCs.

        Expected: `1` if setup and hold requirements for SYSREF are met,
        else return `0`.

        :example:
            >>> tile.adc_sysref_timing_requirements
            [1] * 16

        :return: the sysref_timing_requirements of all ADCs
            idx0->ADC0, idx1->ADC1, ... idx15->ADC15
        """
        return self._attribute_state["adc_sysref_timing_requirements"].read()

    @attribute(
        dtype="DevShort",
        label="fpga0_qpll_status",
        min_alarm=0,
        abs_change=1,
        archive_abs_change=1,
    )
    def fpga0_qpll_status(self: MccsTile) -> int:
        """
        Return the QPLL lock status.

        Expected: `1` if QPLL locked.

        :example:
            >>> tile.fpga0_qpll_status
            1

        :return: the QPLL lock status and lock loss counter.
        """
        return self._attribute_state["fpga0_qpll_status"].read()

    @attribute(
        dtype="DevShort",
        label="fpga0_qpll_counter",
        max_alarm=1,
        abs_change=1,
        archive_abs_change=1,
    )
    def fpga0_qpll_counter(self: MccsTile) -> int:
        """
        Return the QPLL lock loss counter.

        Expected: `0` if no lock loss events detected.
        Increments for each lock loss event.

        :example:
            >>> tile.fpga0_qpll_counter
            0

        :return: the QPLL lock loss counter.
        """
        return self._attribute_state["fpga0_qpll_counter"].read()

    @attribute(
        dtype="DevShort",
        label="fpga1_qpll_status",
        min_alarm=0,
        abs_change=1,
        archive_abs_change=1,
    )
    def fpga1_qpll_status(self: MccsTile) -> int:
        """
        Return the QPLL lock status.

        Expected: `1` if QPLL locked.

        :example:
            >>> tile.fpga1_qpll_status
            '1'

        :return: the QPLL lock status.
        """
        return self._attribute_state["fpga1_qpll_status"].read()

    @attribute(
        dtype="DevShort",
        label="fpga1_qpll_counter",
        max_alarm=1,
        abs_change=1,
        archive_abs_change=1,
    )
    def fpga1_qpll_counter(self: MccsTile) -> int:
        """
        Return the QPLL lock loss counter.

        Expected: `0` if no lock loss events detected.
        Increments for each lock loss event.

        :example:
            >>> tile.fpga1_qpll_counter
            0

        :return: the QPLL lock loss counter.
        """
        return self._attribute_state["fpga1_qpll_counter"].read()

    @attribute(
        dtype="DevShort",
        label="f2f_pll_lock_status",
        min_alarm=0,
        abs_change=1,
        max_value=2,
        min_value=-1,
        archive_abs_change=1,
    )
    def f2f_pll_lock_status(self: MccsTile) -> int:
        """
        Return the PLL lock status.

        Expected: `1` if PLL locked, `0` otherwise.

        :example:
            >>> tile.f2f_pll_lock_status
            '1'

        :return: the PLL lock status.
        """
        return self._attribute_state["f2f_pll_lock_status"].read()

    @attribute(
        dtype="DevShort",
        label="f2f_pll_counter",
        max_alarm=1,
        abs_change=1,
        archive_abs_change=1,
    )
    def f2f_pll_counter(self: MccsTile) -> int:
        """
        Return the PLL lock loss counter.

        Expected: `0` if no PLL lock loss events detected.
        Increments for each lock loss event.

        :example:
            >>> tile.f2f_pll_counter
            '0'

        :return: the PLL lock loss counter.
        """
        return self._attribute_state["f2f_pll_counter"].read()

    @attribute(
        dtype="DevShort",
        label="timing_pll_lock_status",
        min_alarm=0,
        max_value=2,
        min_value=-1,
        abs_change=1,
        archive_abs_change=1,
    )
    def timing_pll_lock_status(self: MccsTile) -> int:
        """
        Return the PLL lock status and lock loss counter.

        Expected: `1` if PLL locked, `0` otherwise.

        :example:
            >>> tile.timing_pll_lock_status
            1

        :return: the PLL lock status.
        """
        return self._attribute_state["timing_pll_lock_status"].read()

    @attribute(
        dtype="DevShort",
        label="timing_pll_count",
        max_alarm=1,
        abs_change=1,
        archive_abs_change=1,
    )
    def timing_pll_count(self: MccsTile) -> int:
        """
        Return the PLL lock loss counter.

        Expected: `0` if no lock loss events detected.
        Increments for each lock loss event.
        These are combined readings for both PLLs within the AD9528.

        :example:
            >>> tile.timing_pll_count
            '0'

        :return: the lock loss counter.
        """
        return self._attribute_state["timing_pll_count"].read()

    @attribute(
        dtype="DevShort",
        label="timing_pll_40g_lock_status",
        min_alarm=0,
        abs_change=1,
        max_value=2,
        min_value=-1,
        archive_abs_change=1,
    )
    def timing_pll_40g_lock_status(self: MccsTile) -> int:
        """
        Return the PLL 40G lock status.

        Expected: `1` if PLL 40G locked.

        :example:
            >>> tile.timing_pll_40g_lock_status
            '1`

        :return: the PLL lock status and lock loss counter.
        """
        return self._attribute_state["timing_pll_40g_lock_status"].read()

    @attribute(
        dtype="DevShort",
        label="timing_pll_40g_count",
        max_alarm=1,
        abs_change=1,
        archive_abs_change=1,
    )
    def timing_pll_40g_count(self: MccsTile) -> int:
        """
        Return the PLL 40G lock loss counter.

        Expected: `0` if PLL 40G has no lock loss events detected.
        Increments for each lock loss event.
        These are combined readings for both PLLs within the AD9528.

        :example:
            >>> tile.timing_pll_40g_count
            '0'

        :return: the PLL lock loss counter.
        """
        return self._attribute_state["timing_pll_40g_count"].read()

    @attribute(dtype="DevString", label="tile_info", fisallowed="_is_programmed")
    def tile_info(self: MccsTile) -> str:
        """
        Return all the tile info available.

        :example:
            >>> tile.tile_info
            '{"hardware": {"ip_address_eep": "10.0.10.2",
            "netmask_eep": "255.255.255.0", "gateway_eep": "255.255.255.255",
            "SN": "0850423050008", "PN": "iTPM_ADU_2.0",
            "bios": "v0.6.0 (CPLD_0x23092511-MCU_0xb000011a_0x20230209_0x0)",
            "BOARD_MODE": "NO-ADA", "EXT_LABEL": "00291;163-010013;2.0;36240080",
            "HARDWARE_REV": "v2.0.1a", "DDR_SIZE_GB": "4"},
            "fpga_firmware": {"design": "tpm_test", "build": "2004",
            "compile_time": "2024-05-29 02:00:36.158315",
            "compile_user": "gitlab-runner (created by john holden)", "compile_host":
            "te7nelson linux-4.18.0-553.44.1.el8_10.x86_64-x86_64-with-glibc2.28",
            "git_branch": "detached head", "git_commit":
            "a22da05fe4cc7078c966 merge branch 'rel-2069-release-v-6-3-0' into 'main'",
            "version": "6.3.0"},
            "network": {"1g_ip_address": "10.132.0.46",
            "1g_mac_address": "fc:0f:e7:e6:43:6c", "1g_netmask": "255.255.255.0",
            "1g_gateway": "10.132.0.254", "40g_ip_address_p1": "10.130.0.108",
            "40g_mac_address_p1": "62:00:0A:82:00:6C", "40g_gateway_p1": "10.130.0.126",
            "40g_netmask_p1": "255.255.255.128", "40g_ip_address_p2": "0.0.0.0",
            "40g_mac_address_p2": "02:00:00:00:00:00",
            "40g_gateway_p2": "10.130.0.126", "40g_netmask_p2": "255.255.255.128"}}'

        :return: info available
        """
        self._info = self.component_manager.tile_info()
        self._convert_ip_to_str(self._info)
        info: dict[str, Any] = self._info
        if info != {}:
            # Prints out a nice table to the logs if populated.
            self.logger.info(str(self))
        return json.dumps(info)

    @attribute(
        dtype="DevString",
        label="voltages",
    )
    def voltages(self: MccsTile) -> str:
        """
        Return all the voltage values available.

        :return: voltages available
        """
        return self._attribute_state["voltages"].read()

    @attribute(
        dtype="DevString",
        label="temperatures",
    )
    def temperatures(self: MccsTile) -> str:
        """
        Return all the temperatures values available.

        :return: temperatures available
        """
        return self._attribute_state["temperatures"].read()

    @attribute(
        dtype="DevBoolean",
        label="useAttributesForHealth",
    )
    def useAttributesForHealth(self: MccsTile) -> bool:
        """
        Return if adr115 is in use.

        :return: True if attributes quality is
            being evaluated in health.
        """
        return self.UseAttributesForHealth

    temperatureADC0 = attribute_from_signal(  # noqa: N815
        temperature_adc0_signal,
        dtype="DevDouble",
        label="ADC 0",
        unit="Celsius",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=90.0,
        min_alarm=10.0,
        doc="ADC 0 temperature in degrees Celsius.",
    )

    temperatureADC1 = attribute_from_signal(  # noqa: N815
        temperature_adc1_signal,
        dtype="DevDouble",
        label="ADC 1",
        unit="Celsius",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=90.0,
        min_alarm=10.0,
        doc="ADC 1 temperature in degrees Celsius.",
    )

    temperatureADC2 = attribute_from_signal(  # noqa: N815
        temperature_adc2_signal,
        dtype="DevDouble",
        label="ADC 2",
        unit="Celsius",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=90.0,
        min_alarm=10.0,
        doc="ADC 2 temperature in degrees Celsius.",
    )

    temperatureADC3 = attribute_from_signal(  # noqa: N815
        temperature_adc3_signal,
        dtype="DevDouble",
        label="ADC 3",
        unit="Celsius",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=90.0,
        min_alarm=10.0,
        doc="ADC 3 temperature in degrees Celsius.",
    )

    temperatureADC4 = attribute_from_signal(  # noqa: N815
        temperature_adc4_signal,
        dtype="DevDouble",
        label="ADC 4",
        unit="Celsius",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=90.0,
        min_alarm=10.0,
        doc="ADC 4 temperature in degrees Celsius.",
    )

    temperatureADC5 = attribute_from_signal(  # noqa: N815
        temperature_adc5_signal,
        dtype="DevDouble",
        label="ADC 5",
        unit="Celsius",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=90.0,
        min_alarm=10.0,
        doc="ADC 5 temperature in degrees Celsius.",
    )

    temperatureADC6 = attribute_from_signal(  # noqa: N815
        temperature_adc6_signal,
        dtype="DevDouble",
        label="ADC 6",
        unit="Celsius",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=90.0,
        min_alarm=10.0,
        doc="ADC 6 temperature in degrees Celsius.",
    )

    temperatureADC7 = attribute_from_signal(  # noqa: N815
        temperature_adc7_signal,
        dtype="DevDouble",
        label="ADC 7",
        unit="Celsius",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=90.0,
        min_alarm=10.0,
        doc="ADC 7 temperature in degrees Celsius.",
    )

    temperatureADC8 = attribute_from_signal(  # noqa: N815
        temperature_adc8_signal,
        dtype="DevDouble",
        label="ADC 8",
        unit="Celsius",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=90.0,
        min_alarm=10.0,
        doc="ADC 8 temperature in degrees Celsius.",
    )

    temperatureADC9 = attribute_from_signal(  # noqa: N815
        temperature_adc9_signal,
        dtype="DevDouble",
        label="ADC 9",
        unit="Celsius",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=90.0,
        min_alarm=10.0,
        doc="ADC 9 temperature in degrees Celsius.",
    )

    temperatureADC10 = attribute_from_signal(  # noqa: N815
        temperature_adc10_signal,
        dtype="DevDouble",
        label="ADC 10",
        unit="Celsius",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=90.0,
        min_alarm=10.0,
        doc="ADC 10 temperature in degrees Celsius.",
    )

    temperatureADC11 = attribute_from_signal(  # noqa: N815
        temperature_adc11_signal,
        dtype="DevDouble",
        label="ADC 11",
        unit="Celsius",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=90.0,
        min_alarm=10.0,
        doc="ADC 11 temperature in degrees Celsius.",
    )

    temperatureADC12 = attribute_from_signal(  # noqa: N815
        temperature_adc12_signal,
        dtype="DevDouble",
        label="ADC 12",
        unit="Celsius",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=90.0,
        min_alarm=10.0,
        doc="ADC 12 temperature in degrees Celsius.",
    )

    temperatureADC13 = attribute_from_signal(  # noqa: N815
        temperature_adc13_signal,
        dtype="DevDouble",
        label="ADC 13",
        unit="Celsius",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=90.0,
        min_alarm=10.0,
        doc="ADC 13 temperature in degrees Celsius.",
    )

    temperatureADC14 = attribute_from_signal(  # noqa: N815
        temperature_adc14_signal,
        dtype="DevDouble",
        label="ADC 14",
        unit="Celsius",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=90.0,
        min_alarm=10.0,
        doc="ADC 14 temperature in degrees Celsius.",
    )

    temperatureADC15 = attribute_from_signal(  # noqa: N815
        temperature_adc15_signal,
        dtype="DevDouble",
        label="ADC 15",
        unit="Celsius",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=90.0,
        min_alarm=10.0,
        doc="ADC 15 temperature in degrees Celsius.",
    )

    @attribute(
        dtype="DevString",
        label="currents",
    )
    def currents(self: MccsTile) -> str:
        """
        Return all the currents values available.

        :return: currents available
        """
        return self._attribute_state["currents"].read()

    @attribute(
        dtype="DevString",
        label="timing",
    )
    def timing(self: MccsTile) -> str:
        """
        Return a dictionary of the timing signals status.

        :return: timing signals status
        """
        return self._attribute_state["timing"].read()

    @attribute(
        dtype="DevString",
        label="io",
    )
    def io(self: MccsTile) -> str:
        """
        Return a dictionary of I/O interfaces status available.

        :return: I/O interfaces status
        """
        return self._attribute_state["io"].read()

    @attribute(
        dtype="DevString",
        label="dsp",
    )
    def dsp(self: MccsTile) -> str:
        """
        Return the tile beamformer and station beamformer status.

        :return: the tile beamformer and station beamformer status
        """
        return self._attribute_state["dsp"].read()

    @attribute(
        dtype="DevString",
        label="adcs",
    )
    def adcs(self: MccsTile) -> str:
        """
        Return the ADC status.

        :return: the ADC status
        """
        return self._attribute_state["adcs"].read()

    @attribute(
        dtype="DevShort",
        max_warning=1,
        max_alarm=2,
        abs_change=1,
        archive_abs_change=1,
    )
    def I2C_access_alm(
        self: MccsTile,
    ) -> int | None:
        """
        Return the I2C alarm reading.

        0 -> OK
        1 -> WARN
        2 -> ALARM

        :return: The alarm state for I2C.
        """
        return self._attribute_state["I2C_access_alm"].read()

    @attribute(
        dtype="DevShort",
        max_warning=1,
        max_alarm=2,
        abs_change=1,
        archive_abs_change=1,
    )
    def temperature_alm(
        self: MccsTile,
    ) -> int | None:
        """
        Return the Temperature alarm reading.

        0 -> OK
        1 -> WARN
        2 -> ALARM

        :return: The alarm state for temperature.
        """
        return self._attribute_state["temperature_alm"].read()

    @attribute(
        dtype="DevShort", max_warning=1, max_alarm=2, abs_change=1, archive_abs_change=1
    )
    def voltage_alm(
        self: MccsTile,
    ) -> int | None:
        """
        Return the Voltage alarm reading.

        0 -> OK
        1 -> WARN
        2 -> ALARM

        :return: The alarm state for voltage.
        """
        return self._attribute_state["voltage_alm"].read()

    @attribute(
        dtype="DevShort",
        max_warning=1,
        max_alarm=2,
        abs_change=1,
        archive_abs_change=1,
    )
    def SEM_wd(
        self: MccsTile,
    ) -> int | None:
        """
        Return the SEMwd alarm reading.

        0 -> OK
        1 -> WARN
        2 -> ALARM

        :return: The alarm state for SEMwd.
        """
        return self._attribute_state["SEM_wd"].read()

    @attribute(
        dtype="DevShort",
        max_warning=1,
        max_alarm=2,
        abs_change=1,
        archive_abs_change=1,
    )
    def MCU_wd(
        self: MccsTile,
    ) -> int | None:
        """
        Return the MCUwd alarm reading.

        0 -> OK
        1 -> WARN
        2 -> ALARM

        :return: The alarm state for MCUwd.
        """
        return self._attribute_state["MCU_wd"].read()

    @attribute(
        dtype="DevString",
        label="cspDestinationIp",
    )
    def cspDestinationIp(self: MccsTile) -> str:
        """
        Return the cspDestinationIp attribute.

        :return: the IP address of the csp destination
        """
        return self._csp_destination_ip

    @attribute(
        dtype="DevString",
        label="cspDestinationMac",
    )
    def cspDestinationMac(self: MccsTile) -> str:
        """
        Return the cspDestinationMac attribute.

        :return: the MAC address of the csp destination
        """
        return self._csp_destination_mac

    @attribute(
        dtype="DevLong", label="cspDestinationPort", abs_change=1, archive_abs_change=1
    )
    def cspDestinationPort(self: MccsTile) -> int:
        """
        Return the cspDestinationMac attribute.

        :return: the port of the csp destination
        """
        return self._csp_destination_port

    @attribute(
        dtype=SimulationMode,
        memorized=True,
        hw_memorized=True,
        abs_change=1,
        archive_abs_change=1,
    )
    def simulationMode(self: MccsTile) -> int:
        """
        Report the simulation mode of the device.

        :return: Return the current simulation mode
        """
        return self.SimulationConfig

    @simulationMode.write  # type: ignore[no-redef]
    def simulationMode(self: MccsTile, value: SimulationMode) -> None:
        """
        Set the simulation mode.

        Writing this attribute is deliberately unimplemented. The
        simulation mode should instead be set by setting the device's
        `SimulationConfig` property at launch.

        :param value: The simulation mode, as a SimulationMode value
        """
        self.logger.warning(
            "MccsTile's simulationMode attribute is currently unimplemented. "
            "To change the simulation mode, relaunch the device with the"
            "'SimulationConfig' property set as desired. "
        )

    @attribute(
        dtype=TestMode,
        memorized=True,
        hw_memorized=True,
        abs_change=1,
        archive_abs_change=1,
    )
    def testMode(self: MccsTile) -> int:
        """
        Report the test mode of the device.

        :return: the current test mode
        """
        return self.TestConfig

    @testMode.write  # type: ignore[no-redef]
    def testMode(self: MccsTile, value: int) -> None:
        """
        Set the test mode.

        Writing this attribute is deliberately unimplemented. The test
        mode should instead be set by setting the device's `TestConfig`
        property at launch.

        :param value: The test mode, as a TestMode value
        """
        self.logger.warning(
            "Changing MccsTile's testMode attribute is currently "
            "unimplemented. To change the test mode, relaunch the device with "
            "the 'TestConfig' property set as desired."
        )

    @attribute(
        dtype="DevLong", abs_change=1, archive_abs_change=1, min_value=0, max_value=15
    )
    def logicalTileId(self: MccsTile) -> int:
        """
        Return the logical tile id.

        The logical tile id is the id of the tile in the station.

        :return: the logical tile id
        """
        return self._attribute_state["logicalTileId"].read()

    @logicalTileId.write  # type: ignore[no-redef]
    def logicalTileId(self: MccsTile, value: int) -> None:
        """
        Set the logicalTileId attribute.

        The logical tile id is the id of the tile in the station.

        :param value: the new logical tile id
        """
        self.component_manager.set_tile_id(value)

    @attribute(dtype="DevString")
    def tileProgrammingState(self: MccsTile) -> str | None:
        """
        Get the tile programming state.

        :return: a string describing the programming state of the tile
        """
        return self._attribute_state["tileProgrammingState"].read()

    @attribute(dtype="DevLong", abs_change=1, archive_abs_change=1)
    def stationId(self: MccsTile) -> int:
        """
        Return the id of the station to which this tile is assigned.

        :return: the id of the station to which this tile is assigned
        """
        station = self._attribute_state["stationId"].read()
        message = f"stationId: read value = {station}"
        self.logger.info(message)
        return station

    @stationId.write  # type: ignore[no-redef]
    def stationId(self: MccsTile, value: int) -> None:
        """
        Set the id of the station to which this tile is assigned.

        :param value: the station id
        """
        message = f"stationId: write value = {value}"
        self.logger.info(message)
        self.component_manager.set_station_id(value)

    @attribute(dtype="DevString", fisallowed="is_firmware_threshold_allowed")
    def firmwareTemperatureThresholds(
        self: MccsTile,
    ) -> str | dict[str, float]:
        """
        Return the temperature thresholds set in firmware.

        :return: A serialised dictionary containing the thresholds.
            or a null string.
        """
        hw_temperatures: str = json.dumps(
            self.hw_firmware_thresholds.to_device_property_dict().get(
                "temperatures", {}
            )
        )
        return hw_temperatures

    @firmwareTemperatureThresholds.write  # type: ignore[no-redef]
    def firmwareTemperatureThresholds(self: MccsTile, value: str) -> None:
        """
        Write the temperature thresholds in firmware.

        :param value: A json serialised string with the thresholds.
        """
        temperature_keys: list[str] = TEMPERATURE_KEYS

        thresholds: dict[str, Any] = json.loads(value)

        arg_map = {
            "board": "max_board_alarm_threshold",
            "fpga1": "max_fpga1_alarm_threshold",
            "fpga2": "max_fpga2_alarm_threshold",
        }

        for temp in temperature_keys:
            thr_name = f"{temp}_alarm_threshold"
            thr_val = thresholds.get(thr_name)

            # Skip missing values
            if thr_val is None:
                continue

            # Handle undefined threshold
            if thr_val == "Undefined":
                self.logger.debug(f"{temp}: threshold explicitly undefined")
                setattr(self.db_firmware_thresholds, thr_name, "Undefined")
                continue

            # Apply to firmware
            self.logger.debug(f"Setting {temp}: threshold={thr_val}")
            set_values = self.component_manager.set_tpm_temperature_thresholds(
                **{arg_map[temp]: thr_val}
            )

            if not set_values:
                self.logger.error(f"{temp}: no temperature threshold values returned")
                continue

            # Update caches
            for target in (self.hw_firmware_thresholds, self.db_firmware_thresholds):
                setattr(target, thr_name, set_values[thr_name])

        # Commit changes and validate
        self.firmware_threshold_db_interface.write_threshold_to_db()
        self._check_database_match()
        self._handle_firmware_read()

    @attribute(dtype="DevString", fisallowed="is_firmware_threshold_allowed")
    def firmwareVoltageThresholds(
        self: MccsTile,
    ) -> str | dict[str, float]:
        """
        Return the voltage thresholds set in firmware.

        :return: A serialised dictionary containing the thresholds.
            or a null string.
        """
        hw_voltages: str = json.dumps(
            self.hw_firmware_thresholds.to_device_property_dict().get("voltages", {})
        )
        return hw_voltages

    @firmwareVoltageThresholds.write  # type: ignore[no-redef]
    def firmwareVoltageThresholds(self: MccsTile, value: str) -> None:
        """
        Set the voltage thresholds in the firmware.

        :param value: A json serialised string with the thresholds.

        :raises ValueError: When only one threshold is defined,
            you must define min and max.
        """
        voltage_keys: list[str] = VOLTAGE_KEYS

        # Flatten allowed voltage keys into full threshold names
        allowed_keys = {f"{v}_min_alarm_threshold" for v in voltage_keys} | {
            f"{v}_max_alarm_threshold" for v in voltage_keys
        }

        thresholds: dict[str, Any] = json.loads(value)

        # Validate threshold keys
        for key in thresholds.keys():
            if key not in allowed_keys:
                raise ValueError(
                    f"Invalid threshold key: {key}. "
                    f"Must be one of {sorted(allowed_keys)}"
                )

        for voltage in voltage_keys:
            min_name = f"{voltage}_min_alarm_threshold"
            max_name = f"{voltage}_max_alarm_threshold"
            min_val = thresholds.get(min_name)
            max_val = thresholds.get(max_name)

            # Validate consistency
            if (min_val is None) ^ (max_val is None):  # only one defined
                raise ValueError(
                    f"Inconsistent voltage thresholds for {voltage}: "
                    f"min={min_val}, max={max_val}. Both must be defined or both None."
                )

            # Skip undefined voltages
            if min_val is None:
                continue

            # Handle "Undefined" explicitly
            if min_val == "Undefined" or max_val == "Undefined":
                self.logger.debug(f"{voltage}: thresholds explicitly undefined")

                if min_val == "Undefined":
                    setattr(self.db_firmware_thresholds, min_name, "Undefined")

                if max_val == "Undefined":
                    setattr(self.db_firmware_thresholds, max_name, "Undefined")

                continue

            # Set thresholds in firmware and caches
            self.logger.debug(f"Setting {voltage}: min={min_val}, max={max_val}")
            set_values = self.component_manager.set_voltage_warning_thresholds(
                voltage=voltage.upper(),
                min_thr=min_val,
                max_thr=max_val,
            )

            if not set_values:
                self.logger.error(
                    f"{voltage}: no threshold values returned from firmware"
                )
                continue

            # Update firmware and DB caches
            for name, src, val_key in (
                (min_name, self.hw_firmware_thresholds, "min"),
                (max_name, self.hw_firmware_thresholds, "max"),
            ):
                setattr(src, name, set_values[val_key])
                setattr(self.db_firmware_thresholds, name, thresholds[name])

        # Commit updates
        self.firmware_threshold_db_interface.write_threshold_to_db()
        self._check_database_match()
        self._handle_firmware_read()

    @attribute(dtype="DevString", fisallowed="is_firmware_threshold_allowed")
    def firmwareCurrentThresholds(
        self: MccsTile,
    ) -> str | dict[str, float]:
        """
        Return the current thresholds set in firmware.

        :return: A serialised dictionary containing the thresholds.
            or a null string.
        """
        hw_currents = json.dumps(
            self.hw_firmware_thresholds.to_device_property_dict().get("currents", {})
        )
        return hw_currents

    @firmwareCurrentThresholds.write  # type: ignore[no-redef]
    def firmwareCurrentThresholds(self: MccsTile, value: str) -> None:
        """
        Set the Current thresholds in firmware.

        :param value: A json serialised string with the thresholds.

        :raises ValueError: When only one threshold is defined,
            you must define min and max.
        """
        current_keys = CURRENT_KEYS
        thresholds: dict[str, Any] = json.loads(value)

        # Build the set of valid threshold keys
        valid_keys = {f"{current}_min_alarm_threshold" for current in current_keys} | {
            f"{current}_max_alarm_threshold" for current in current_keys
        }

        # Check for invalid keys in the input
        invalid_keys = set(thresholds.keys()) - valid_keys
        if invalid_keys:
            raise ValueError(f"Invalid threshold keys provided: {invalid_keys}")

        for current in current_keys:
            min_key = f"{current}_min_alarm_threshold"
            max_key = f"{current}_max_alarm_threshold"
            min_val = thresholds.get(min_key)
            max_val = thresholds.get(max_key)

            # Validate completeness
            if (min_val is None) ^ (max_val is None):
                raise ValueError(
                    f"Inconsistent current thresholds for {current}: "
                    f"min={min_val}, max={max_val}. Both must be defined or both None."
                )

            if min_val is None:  # skip undefined
                continue

            # Handle "Undefined"
            if min_val == "Undefined" or max_val == "Undefined":
                self.logger.debug(f"{current}: thresholds explicitly undefined")

                if min_val == "Undefined":
                    setattr(self.db_firmware_thresholds, min_key, "Undefined")

                if max_val == "Undefined":
                    setattr(self.db_firmware_thresholds, max_key, "Undefined")

                continue

            # Apply thresholds to firmware
            self.logger.debug(f"Setting {current}: min={min_val}, max={max_val}")
            set_values = self.component_manager.set_current_warning_thresholds(
                current=current,
                min_thr=min_val,
                max_thr=max_val,
            )

            if not set_values:
                self.logger.error(
                    f"{current}: firmware did not return threshold values"
                )
                continue

            # Update caches
            for name, src, val_key in (
                (min_key, self.hw_firmware_thresholds, "min"),
                (max_key, self.hw_firmware_thresholds, "max"),
            ):
                setattr(src, name, set_values[val_key])
                setattr(self.db_firmware_thresholds, name, thresholds[name])

        self.firmware_threshold_db_interface.write_threshold_to_db()
        self._check_database_match()
        self._handle_firmware_read()

    @attribute(dtype="DevString")
    def firmwareName(self: MccsTile) -> str:
        """
        Return the firmware name.

        :return: firmware name
        """
        return self.component_manager.firmware_name

    @firmwareName.write  # type: ignore[no-redef]
    def firmwareName(self: MccsTile, value: str) -> None:
        """
        Set the firmware name.

        :param value: firmware name
        """
        self.component_manager.firmware_name = value

    @attribute(dtype="DevString")
    def firmwareVersion(self: MccsTile) -> str:
        """
        Return the firmware version.

        :return: firmware version
        """
        return self.component_manager.firmware_version

    @firmwareVersion.write  # type: ignore[no-redef]
    def firmwareVersion(self: MccsTile, value: str) -> None:
        """
        Set the firmware version.

        :param value: firmware version
        """
        self.component_manager.firmware_version = value

    @attribute(dtype="DevBoolean")
    def isProgrammed(self: MccsTile) -> bool:
        """
        Return a flag indicating whether of not the board is programmed.

        :return: whether of not the board is programmed
        """
        return self.component_manager.is_programmed

    def _is_programmed(self: MccsTile, *args: Any) -> bool:
        """
        Return a flag representing whether we are programmed or not.

        :param args: The tango.AttReqType.

        :return: True if Tile is in Programmed, Initialised or Synchronised states.
        """
        prog_state = self._attribute_state["tileProgrammingState"].read()[0]
        if prog_state in ["Programmed", "Initialised", "Synchronised"]:
            return True
        reason = "CommandNotAllowed"
        msg = (
            "To execute this command we must be in state "
            "'Programmed', 'Initialised' or 'Synchronised'! "
            f"Tile is currently in state {prog_state}"
        )
        tango.Except.throw_exception(reason, msg, self.get_name())
        return False

    def is_engineering(self: MccsTile) -> bool:
        """
        Return a flag representing whether we are in Engineering mode.

        :return: True if Tile is in Engineering Mode.
        """
        is_engineering = self._admin_mode == AdminMode.ENGINEERING
        if not is_engineering:
            reason = "CommandNotAllowed"
            msg = (
                "To execute this command we must be in adminMode Engineering "
                f"Tile is currently in adminMode {AdminMode(self._admin_mode).name}"
            )
            tango.Except.throw_exception(reason, msg, self.get_name())

        return is_engineering

    def is_firmware_threshold_allowed(
        self: MccsTile, req_type: tango.AttReqType
    ) -> bool:
        """
        Return a flag representing whether we are allowed to access the attribute.

        :param req_type: the request type

        :return: True if access is allowed.
        """
        if req_type == tango.AttReqType.READ_REQ:
            return True
        if self.component_manager._initialise_executing is True:
            reason = "CommandNotAllowed"
            msg = "Cannot execute this command while initialise is executing!"
            tango.Except.throw_exception(reason, msg, self.get_name())
            return False
        is_engineering = self._admin_mode == AdminMode.ENGINEERING
        if not is_engineering:
            reason = "CommandNotAllowed"
            msg = (
                "To execute this command we must be in adminMode Engineering "
                f"Tile is currently in adminMode {AdminMode(self._admin_mode).name}"
            )
            tango.Except.throw_exception(reason, msg, self.get_name())
            return False
        return True

    def _check_initialised_for_write(
        self: MccsTile, req_type: tango.AttReqType
    ) -> bool:
        """
        Return a flag representing whether we are allowed to access the attribute.

        :param req_type: the request type

        :return: True if access is allowed.
        """
        if req_type == tango.AttReqType.READ_REQ:
            return True
        return self._is_initialised(req_type)

    def _is_initialised(self: MccsTile, *args: Any) -> bool:
        """
        Return a flag representing whether we are in Initialised state.

        :param args: The tango.AttReqType.

        :return: True if Tile is in Initialised state.
        """
        if self.component_manager._initialise_executing:
            reason = "CommandNotAllowed"
            msg = "Cannot execute this command while initialise is executing!"
            tango.Except.throw_exception(reason, msg, self.get_name())
            return False

        prog_state = self._attribute_state["tileProgrammingState"].read()[0]
        if prog_state in ["Initialised", "Synchronised"]:
            return True
        reason = "CommandNotAllowed"
        msg = (
            "To execute this command we must be in state "
            "'Initialised' or 'Synchronised'! "
            f"Tile is currently in state {prog_state}"
        )
        tango.Except.throw_exception(reason, msg, self.get_name())
        return False

    fpga1Temperature = attribute_from_signal(  # noqa: N815
        fpga1_temperature_signal,
        dtype="DevDouble",
        abs_change=0.1,
        archive_abs_change=0.1,
        min_alarm=10.0,
        max_alarm=95.0,
        doc="Temperature of FPGA 1 in degrees Celsius.",
    )

    fpga2Temperature = attribute_from_signal(  # noqa: N815
        fpga2_temperature_signal,
        dtype="DevDouble",
        abs_change=0.2,
        archive_abs_change=0.2,
        min_alarm=10.0,
        max_alarm=95.0,
        doc="Temperature of FPGA 2 in degrees Celsius.",
    )

    @attribute(
        dtype=("DevLong",),
        max_dim_x=2,
        abs_change=1,
        archive_abs_change=1,
        fisallowed="_check_initialised_for_write",
    )
    def fpgasUnixTime(self: MccsTile) -> list[int]:
        """
        Return the time for FPGAs.

        :return: the time for FPGAs
        """
        return self.component_manager.fpgas_time

    @attribute(dtype="DevString", fisallowed="_is_initialised")
    def fpgaTime(self: MccsTile) -> str:
        """
        Return the FPGA internal time.

        :return: the FPGA time, in UTC format
        """
        return self.component_manager.fpga_time

    @attribute(dtype="DevString", fisallowed="_is_initialised")
    def fpgaReferenceTime(self: MccsTile) -> str:
        """
        Return the FPGA synchronization timestamp.

        :return: the FPGA timestamp, in UTC format
        """
        return self.component_manager.formatted_fpga_reference_time

    @attribute(dtype="DevString", fisallowed="_is_initialised")
    def fpgaFrameTime(self: MccsTile) -> str:
        """
        Return the FPGA synchronization timestamp.

        :return: the FPGA timestamp, in UTC format
        """
        return self.component_manager.fpga_frame_time

    @attribute(
        dtype=("DevLong",),
        max_dim_x=16,
        abs_change=1,
        archive_abs_change=1,
        label="Antenna ID's",
    )
    def antennaIds(self: MccsTile) -> list[int]:
        """
        Return the antenna IDs.

        :return: the antenna IDs
        """
        return self._antenna_ids

    @antennaIds.write  # type: ignore[no-redef]
    def antennaIds(self: MccsTile, antenna_ids: list[int]) -> None:
        """
        Set the antenna IDs.

        :param antenna_ids: the antenna IDs
        """
        self._antenna_ids = list(antenna_ids)

    @attribute(dtype=("DevString",), max_dim_x=16, fisallowed="_is_initialised")
    def fortyGbDestinationIps(self: MccsTile) -> list[str]:
        """
        Return the destination IPs for all 40Gb ports on the tile.

        :return: IP addresses
        """
        return [
            item["dst_ip"] for item in self.component_manager.get_40g_configuration()
        ]

    @attribute(
        dtype=("DevLong",),
        max_dim_x=16,
        abs_change=1,
        archive_abs_change=1,
        fisallowed="_is_initialised",
    )
    def fortyGbDestinationPorts(self: MccsTile) -> list[int]:
        """
        Return the destination ports for all 40Gb ports on the tile.

        :return: ports
        """
        return [
            item["dst_port"] for item in self.component_manager.get_40g_configuration()
        ]

    @attribute(
        dtype=("DevDouble",), max_dim_x=32, abs_change=0.1, archive_abs_change=0.1
    )
    def adcPower(self: MccsTile) -> list[float] | None:
        """
        Return the RMS power of every ADC signal.

        so a TPM processes 16 antennas, this should return 32 RMS value.

        :return: RMP power of ADC signals
        """
        return self._attribute_state["adcPower"].read()

    @attribute(
        dtype="DevLong",
        fisallowed="_is_initialised",
        abs_change=1,
        archive_abs_change=1,
    )
    def currentTileBeamformerFrame(self: MccsTile) -> int:
        """
        Return current frame.

        in units of 256 ADC frames (276,48 us) Currently this is
        required, not sure if it will remain so.

        :return: current frame
        """
        try:
            return self.component_manager.current_tile_beamformer_frame
        except TimeoutError as e:
            self.logger.warning(
                f"{repr(e)}, " "Reading cached value for currentTileBeamformerFrame"
            )
        return self._attribute_state["currentTileBeamformerFrame"].read()

    @attribute(dtype="DevString")
    def coreCommunicationStatus(self: MccsTile) -> str | None:
        """
        Return status of connection to TPM, CPLD and FPGAs.

        Return True if communication is OK else False

        :example:

        >>> core_communication_status = tile_proxy.coreCommunicationStatus
        >>> print(core_communication_status)
        >>> {'CPLD': True, 'FPGA0': True, 'FPGA1': True}

        :return: dictionary containing if the CPLD and FPGAs are
            connectable or None if not yet polled.
        """
        return self._attribute_state["coreCommunicationStatus"].read()

    @attribute(
        dtype="DevLong",
        abs_change=1,
        archive_abs_change=1,
        fisallowed="_is_initialised",
    )
    def currentFrame(self: MccsTile) -> int:
        """
        Return current frame.

        in units of 256 ADC frames (276,48 us) Currently this is
        required, not sure if it will remain so.

        :return: current frame
        """
        return self.component_manager.fpga_current_frame

    @attribute(dtype="DevBoolean", fisallowed="_is_initialised")
    def pendingDataRequests(self: MccsTile) -> bool | None:
        """
        Check for pending data requests.

        :return: whether there are data requests pending
        """
        return self.component_manager.pending_data_requests

    @attribute(dtype="DevBoolean", fisallowed="_is_initialised")
    def isBeamformerRunning(self: MccsTile) -> bool | None:
        """
        Check if beamformer is running.

        :return: whether the beamformer is running
        """
        return self.component_manager.is_beamformer_running

    @attribute(
        dtype="DevLong",
        abs_change=1,
        archive_abs_change=1,
        fisallowed="_check_initialised_for_write",
    )
    def phaseTerminalCount(self: MccsTile) -> int:
        """
        Get phase terminal count.

        :return: phase terminal count
        """
        return self._attribute_state["phaseTerminalCount"].read()

    @phaseTerminalCount.write  # type: ignore[no-redef]
    def phaseTerminalCount(self: MccsTile, value: int) -> None:
        """
        Set the phase terminal count.

        :param value: the phase terminal count
        """
        self.component_manager.set_phase_terminal_count(value)

    @attribute(
        dtype="DevLong",
        abs_change=1,
        archive_abs_change=1,
        fisallowed="_is_initialised",
    )
    def ppsDelay(self: MccsTile) -> int | None:
        """
        Return the delay between PPS and 10 MHz clock.

        :return: Return the PPS delay in 1.25ns units.
        """
        if self._attribute_state["ppsDelay"].read() is None:
            pps_delay = self.component_manager.pps_delay
            # Post an event so health tracking can recover from stale/invalid state.
            self._attribute_state["ppsDelay"].update(pps_delay)
        return self._attribute_state["ppsDelay"].read()

    @attribute(
        dtype="DevLong",
        archive_abs_change=1,
        abs_change=1,
        max_alarm=10,
        max_warning=4,
    )
    def ppsDrift(self: MccsTile) -> int:
        """
        Return the observed drift in the ppsDelay of this Tile.

        :return: Return the pps delay drift in 1.25ns units or `None` if not initialised
        """
        return self._attribute_state["ppsDrift"].read()

    @attribute(dtype="DevLong", archive_abs_change=1, abs_change=1)
    def ppsDelayCorrection(self: MccsTile) -> int | None:
        """
        Return the correction made to the pps delay.

        :return: Return the PPS delay in 1.25ns units.
        """
        return self._attribute_state["ppsDelayCorrection"].read()

    @ppsDelayCorrection.write  # type: ignore[no-redef]
    def ppsDelayCorrection(self: MccsTile, pps_delay_correction: int) -> None:
        """
        Set a correction to make to the pps delay.

        Note: will be applied during next initialisation.

        :param pps_delay_correction: a correction to apply to the pps_delay.
        """
        self.component_manager.set_pps_delay_correction(pps_delay_correction)

    @attribute(dtype="DevBoolean")
    def testGeneratorActive(self: MccsTile) -> bool:
        """
        Report if the test generator is used for some channels.

        :return: test generator status
        """
        return self.component_manager.test_generator_active

    @attribute(dtype="DevBoolean")
    def ppsPresent(self: MccsTile) -> tuple[bool | None, float, tango.AttrQuality]:
        """
        Report if PPS signal is present at the TPM input.

        :return: a tuple with attribute_value, time, quality
        """
        return self._attribute_state["ppsPresent"].read()

    def dev_state(self) -> tango.DevState:
        """
        Calculate this device state.

        The base device offers some automatic state discovery.
        However we have some attributes that require explicit
        analysis as to whether they are in ALARM or not,

        e.g. DevBoolean

        :return: the 'tango.DevState' calculated
        """
        automatic_state_analysis: tango.DevState = super().dev_state()
        force_alarm: bool = False
        for _, attr_manager in self._attribute_state.items():
            if isinstance(attr_manager, BoolAttributeManager):
                value = attr_manager.read()
                if (
                    value is not None
                    and isinstance(value, (list, tuple))
                    and len(value) > 0
                ):
                    if value[0] is False:
                        force_alarm = True
        if force_alarm:
            return tango.DevState.ALARM
        return automatic_state_analysis

    @attribute(dtype="DevBoolean")
    def clockPresent(self: MccsTile) -> NoReturn:
        """
        Report if 10 MHz clock signal is present at the TPM input.

        :raises NotImplementedError: not implemented in ska-low-sps-tpm-api.
        """
        raise NotImplementedError(
            "method clockPresent not yet implemented in ska-low-sps-tpm-api"
        )

    @attribute(dtype="DevBoolean")
    def sysrefPresent(self: MccsTile) -> NoReturn:
        """
        Report if SYSREF signal is present at the FPGA.

        :raises NotImplementedError: not implemented in ska-low-sps-tpm-api.
        """
        raise NotImplementedError(
            "method sysrefPresent not yet implemented in ska-low-sps-tpm-api"
        )

    @attribute(dtype="DevBoolean")
    def pllLocked(self: MccsTile) -> bool | None:
        """
        Report if ADC clock PLL is in locked state.

        :return: PLL lock state
        """
        return self._attribute_state["pllLocked"].read()

    @attribute(
        dtype=("DevLong",),
        max_dim_x=512,
        archive_abs_change=1,
        abs_change=1,
        fisallowed="_is_initialised",
    )
    def channeliserRounding(self: MccsTile) -> list[int]:
        """
        Channeliser rounding.

        Number of LS bits dropped in each channeliser frequency channel.
        Valid values 0-7 Same value applies to all antennas and
        polarizations

        :returns: list of 512 values, one per channel.
        """
        if self._attribute_state["channeliserRounding"].read() is None:
            rounding = self.component_manager.channeliser_truncation
            self._attribute_state["channeliserRounding"].update(rounding, post=False)
        return self._attribute_state["channeliserRounding"].read()

    @channeliserRounding.write  # type: ignore[no-redef]
    def channeliserRounding(self: MccsTile, truncation: list[int]) -> None:
        """
        Set channeliser rounding.

        :param truncation: List with either a single value (applies to all channels)
            or a list of 512 values. Range 0 (no truncation) to 7
        """
        self.component_manager.channeliser_truncation = truncation

    @attribute(
        dtype=("DevDouble",),
        max_dim_x=32,
        archive_abs_change=1,
        abs_change=1,
        fisallowed="_check_initialised_for_write",
    )
    def staticTimeDelays(self: MccsTile) -> list[int]:
        """
        Get static time delay correction.

        Array of one value per antenna/polarization (32 per tile), in range +/-124.
        Delay in nanoseconds (positive = increase the signal delay) to correct for
        static delay mismathces, e.g. cable length.

        :return: Array of one value per antenna/polarization (32 per tile)
        """
        return self._attribute_state["staticTimeDelays"].read()

    @staticTimeDelays.write  # type: ignore[no-redef]
    def staticTimeDelays(self: MccsTile, delays: list[float]) -> None:
        """
        Set static time delay.

        :param delays: Delay in nanoseconds (positive = increase the signal delay)
             to correct for static delay mismathces, e.g. cable length.
        """
        self.component_manager.set_static_delays(delays)

    @attribute(
        dtype=("DevLong",),
        max_dim_x=384,
        archive_abs_change=1,
        abs_change=1,
        fisallowed="_check_initialised_for_write",
    )
    def cspRounding(self: MccsTile) -> np.ndarray | None:
        """
        CSP formatter rounding.

        Rounding from 16 to 8 bits in final stage of the
        station beamformer, before sending data to CSP.
        Array of (up to) 384 values, one for each logical channel.
        Range 0 to 7, as number of discarded LS bits.

        :return: CSP formatter rounding for each logical channel.
        """
        return self._attribute_state["cspRounding"].read()

    @cspRounding.write  # type: ignore[no-redef]
    def cspRounding(self: MccsTile, rounding: np.ndarray) -> None:
        """
        Set CSP formatter rounding.

        :param rounding: list of up to 384 values in the range 0-7.
            Current hardware supports only a single value, thus oly 1st value is used
        """
        self.component_manager.csp_rounding = rounding

    @attribute(dtype="DevString")
    def globalReferenceTime(self: MccsTile) -> str:
        """
        Return the global FPGA synchronization time.

        :return: the global synchronization time, in UTC format
        """
        return self.component_manager.global_reference_time

    @globalReferenceTime.write  # type: ignore[no-redef]
    def globalReferenceTime(self: MccsTile, reference_time: str) -> None:
        """
        Set the global global synchronization timestamp.

        :param reference_time: the synchronization time, in ISO9660 format, or ""
        """
        self.component_manager.global_reference_time = reference_time

    @attribute(
        dtype=(float,),
        max_dim_x=32,
        abs_change=0.1,
        archive_abs_change=0.1,
        fisallowed="_check_initialised_for_write",
    )
    def preaduLevels(self: MccsTile) -> list[float]:
        """
        Get attenuator level of preADU channels, one per input channel.

        :return: Array of one value per antenna/polarization (32 per tile)
        """
        return self._attribute_state["preaduLevels"].read()

    @preaduLevels.write  # type: ignore[no-redef]
    def preaduLevels(self: MccsTile, levels: np.ndarray) -> None:
        """
        Set attenuator level of preADU channels, one per input channel.

        :param levels: ttenuator level of preADU channels, one per input channel, in dB
        """
        self.component_manager.set_preadu_levels(levels)

    @attribute(dtype=("DevLong",), max_dim_x=336, archive_abs_change=1, abs_change=1)
    def beamformerTable(self: MccsTile) -> list[int] | None:
        """
        Get beamformer region table.

        Bidimensional array of one row for each 8 channels, with elements:
        0. start physical channel
        1. beam number
        2. subarray ID
        3. subarray_logical_channel
        4. subarray_beam_id
        5. substation_id
        6. aperture_id

        Each row is a set of 7 consecutive elements in the list.

        :return: list of up to 7*48 values
        """
        return self._attribute_state["beamformerTable"].read()

    @attribute(dtype=("DevLong",), max_dim_x=384, archive_abs_change=1, abs_change=1)
    def beamformerRegions(self: MccsTile) -> list[int] | None:
        """
        Get beamformer region table.

        Bidimensional array of one row for each 8 channels, with elements:
        0. start physical channel
        1. number of channels
        2. beam index
        3. subarray ID
        4. subarray_logical_channel
        5. subarray_beam_id
        6. substation_id
        8. aperture_id

        Each row is a set of 8 consecutive elements in the list.

        :return: list of up to 8*48 values
        """
        return self._attribute_state["beamformerRegions"].read()

    @attribute(
        dtype="DevString",
        format="%s",
    )
    def healthModelParams(self: MccsTile) -> str:
        """
        Get the health params from the health model.

        :return: the health params
        """
        if self.UseAttributesForHealth:
            return ""
        return json.dumps(self._health_model.health_params)

    @healthModelParams.write  # type: ignore[no-redef]
    def healthModelParams(self: MccsTile, argin: str) -> None:
        """
        Set the params for health transition rules.

        :param argin: JSON-string of dictionary of health states

        :raises NotImplementedError: If UseAttributesForHealth
            if True
        """
        if self.UseAttributesForHealth:
            raise NotImplementedError("")
        self._health_model.health_params = json.loads(argin)
        self._health_model.update_health()

    @attribute(dtype=HealthState)
    def temperatureHealth(self: MccsTile) -> HealthState:
        """
        Read the temperature Health State of the device.

        This is an aggregated quantity representing if any of the temperature
        monitoring points are outside of their thresholds. This is used to compute
        the overall healthState of the tile.

        :return: temperature Health State of the device
        """
        if self.UseAttributesForHealth:
            return self._intermediate_healths["temperatures"]
        return self._health_model.intermediate_healths["temperatures"][0]

    @attribute(dtype=HealthState)
    def voltageHealth(self: MccsTile) -> HealthState:
        """
        Read the voltage Health State of the device.

        This is an aggregated quantity representing if any of the voltage
        monitoring points are outside of their thresholds. This is used to compute
        the overall healthState of the tile.

        :return: voltage Health State of the device
        """
        if self.UseAttributesForHealth:
            return self._intermediate_healths["voltages"]
        return self._health_model.intermediate_healths["voltages"][0]

    @attribute(dtype=HealthState)
    def currentHealth(self: MccsTile) -> HealthState:
        """
        Read the current Health State of the device.

        This is an aggregated quantity representing if any of the current
        monitoring points are outside of their thresholds. This is used to compute
        the overall healthState of the tile.

        :return: current Health State of the device
        """
        if self.UseAttributesForHealth:
            return self._intermediate_healths["currents"]
        return self._health_model.intermediate_healths["currents"][0]

    @attribute(dtype=HealthState)
    def alarmHealth(self: MccsTile) -> HealthState:
        """
        Read the alarm Health State of the device.

        This is an aggregated quantity representing if any of the alarm
        monitoring points are outside of their thresholds. This is used to compute
        the overall healthState of the tile.

        :return: alarm Health State of the device
        """
        if self.UseAttributesForHealth:
            return self._intermediate_healths["alarms"]
        return self._health_model.intermediate_healths["alarms"][0]

    @attribute(dtype=HealthState)
    def adcHealth(self: MccsTile) -> HealthState:
        """
        Read the ADC Health State of the device.

        This is an aggregated quantity representing if any of the ADC
        monitoring points are outside of their thresholds. This is used to compute
        the overall healthState of the tile.

        :return: ADC Health State of the device
        """
        if self.UseAttributesForHealth:
            return self._intermediate_healths["adcs"]
        return self._health_model.intermediate_healths["adcs"][0]

    @attribute(dtype=HealthState)
    def timingHealth(self: MccsTile) -> HealthState:
        """
        Read the timing Health State of the device.

        This is an aggregated quantity representing if any of the timing
        monitoring points do not have a permitted value. This is used to compute
        the overall healthState of the tile.

        :return: timing Health State of the device
        """
        if self.UseAttributesForHealth:
            return self._intermediate_healths["timing"]
        return self._health_model.intermediate_healths["timing"][0]

    @attribute(dtype=HealthState)
    def ioHealth(self: MccsTile) -> HealthState:
        """
        Read the io Health State of the device.

        This is an aggregated quantity representing if any of the io
        monitoring points do not have a permitted value. This is used to compute
        the overall healthState of the tile.

        :return: io Health State of the device
        """
        if self.UseAttributesForHealth:
            return self._intermediate_healths["io"]
        return self._health_model.intermediate_healths["io"][0]

    @attribute(dtype=HealthState)
    def dspHealth(self: MccsTile) -> HealthState:
        """
        Read the dsp Health State of the device.

        This is an aggregated quantity representing if any of the dsp
        monitoring points do not have a permitted value. This is used to compute
        the overall healthState of the tile.

        :return: dsp Health State of the device
        """
        if self.UseAttributesForHealth:
            return self._intermediate_healths["dsp"]
        return self._health_model.intermediate_healths["dsp"][0]

    @attribute(dtype="DevString")
    def healthReport(self: MccsTile) -> str:
        """
        Get the health report.

        :return: the health report.
        """
        if self.UseAttributesForHealth:
            return self._health_report
        self._health_model.set_logger(self.logger)
        return self._health_model.health_report

    @attribute(dtype="DevString")
    def faultReport(self: MccsTile) -> str:
        """
        Get the fault report.

        :return: the fault report.
        """
        return json.dumps(self.status_information)

    @attribute(dtype="DevString")
    def srcip40gfpga1(self: MccsTile) -> str:
        """
        Return source IP for FPGA1, to be set by SpsStation.

        :return: source IP for FPGA1.
        """
        if self.component_manager.src_ip_40g_fpga1 is not None:
            return self.component_manager.src_ip_40g_fpga1
        self.logger.warning("Source IP for FPGA1 not set")
        return ""

    @srcip40gfpga1.write  # type: ignore[no-redef]
    def srcip40gfpga1(self: MccsTile, argin: str) -> None:
        """
        Set source IP for FPGA1.

        :param argin: source IP for FPGA1
        """
        self.component_manager.src_ip_40g_fpga1 = argin

    @attribute(dtype="DevString")
    def srcip40gfpga2(self: MccsTile) -> str:
        """
        Return source IP for FPGA2, to be set by SpsStation.

        :return: source IP for FPGA2.
        """
        if self.component_manager.src_ip_40g_fpga2 is not None:
            return self.component_manager.src_ip_40g_fpga2
        self.logger.warning("Source IP for FPGA2 not set")
        return ""

    @srcip40gfpga2.write  # type: ignore[no-redef]
    def srcip40gfpga2(self: MccsTile, argin: str) -> None:
        """
        Set source IP for FPGA2.

        :param argin: source IP for FPGA2
        """
        self.component_manager.src_ip_40g_fpga2 = argin

    @attribute(
        dtype="DevString",
        label="cspSpeadFormat",
        fisallowed="_check_initialised_for_write",
    )
    def cspSpeadFormat(self: MccsTile) -> str:
        """
        Get CSP SPEAD format.

        CSP format is: AAVS for the format used in AAVS2-AAVS3 system,
        using a reference Unix time specified in the header.
        SKA for the format defined in SPS-CBF ICD, based on TAI2000 epoch.

        :return: CSP Spead format. AAVS or SKA
        """
        return self.component_manager.csp_spead_format

    @cspSpeadFormat.write  # type: ignore[no-redef]
    def cspSpeadFormat(self: MccsTile, spead_format: str) -> None:
        """
        Set CSP SPEAD format.

        CSP format is: AAVS for the format used in AAVS2-AAVS3 system,
        using a reference Unix time specified in the header.
        SKA for the format defined in SPS-CBF ICD, based on TAI2000 epoch.

        :param spead_format: format used in CBF SPEAD header: "AAVS" or "SKA"
        """
        if spead_format not in ["AAVS", "SKA"]:
            self.logger.warning(
                "Invalid CSP SPEAD format: should be AAVS|SKA. Using AAVS"
            )
            spead_format = "AAVS"
        if spead_format in ["AAVS", "SKA"]:
            self.component_manager.csp_spead_format = spead_format
        else:
            self.logger.error("Invalid SPEAD format: should be AAVS or SKA")

    @attribute(
        dtype=(("DevFloat",),),
        max_dim_x=2,  # [Delay, delay rate]
        max_dim_y=16,  # channel (same for x and y)
    )
    def lastPointingDelays(self: MccsTile) -> list[list]:
        """
        Return last pointing delays applied to the tile.

        Values are initialised to 0.0 if they haven't been set.
        These values are in channel order, with each pair corresponding to
        a delay and delay rate.

        :returns: last pointing delays applied to the tile.
        """
        return self.component_manager.last_pointing_delays

    @attribute(
        dtype=(("DevLong",),),
        max_dim_x=2,  # pol
        max_dim_y=16,  # antenna
        abs_change=1,
        archive_abs_change=1,
        fisallowed="_is_initialised",
    )
    def rfiCount(self: MccsTile) -> list[list]:
        """
        Return the RFI count per antenna/pol.

        :returns: the RFI count per antenna/pol.
        """
        return self._attribute_state["rfiCount"].read()

    @attribute(
        dtype=("DevBoolean",), max_dim_x=2, fisallowed="_is_initialised"
    )  # fpgas
    def stationBeamFlagEnabled(
        self: MccsTile,
    ) -> list[bool]:
        """
        Return True if station beam data flagging is enabled.

        :return: a list of bool values corresponding to the fpgas
        """
        return self.component_manager.is_station_beam_flagging_enabled

    @attribute(dtype="DevString")
    def antennaBufferMode(
        self: MccsTile,
    ) -> str:
        """
        Return if antenna buffer is sending over SDN or NSDN.

        :return: string of SND or NSDN
        """
        return self.component_manager.antenna_buffer_mode

    @attribute(dtype="DevString")
    def dataTransmissionMode(
        self: MccsTile,
    ) -> str:
        """
        Return if we're sending data through 1G or 10G port.

        :return: Either 1G or 10G string
        """
        return self.component_manager.data_transmission_mode

    @attribute(dtype="DevString")
    def integratedDataTransmissionMode(
        self: MccsTile,
    ) -> str:
        """
        Return if we're sending integrated data through 1G or 10G port.

        :return: Either 1G or 10G string
        """
        return self.component_manager.integrated_data_transmission_mode

    @attribute(dtype=("DevBoolean",), max_dim_x=48, fisallowed="_is_initialised")
    def runningBeams(self: MccsTile) -> list[bool]:
        """
        List running status for each SubarrayBeam.

        :return: list of hardware beam running states
        """
        return self.component_manager.running_beams

    currentFE0 = attribute_from_signal(  # noqa: N815
        current_fe0_signal,
        dtype="DevDouble",
        label="FE0 current",
        unit="Amp",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=2.62,
        max_warning=2.60,
        doc="FE0 current in Amps.",
    )

    currentFE1 = attribute_from_signal(  # noqa: N815
        current_fe1_signal,
        dtype="DevDouble",
        label="FE1 current",
        unit="Amp",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=2.62,
        max_warning=2.60,
        doc="FE1 current in Amps.",
    )

    voltageAVDD3 = attribute_from_signal(  # noqa: N815
        voltage_avdd3_signal,
        dtype="DevDouble",
        label="Analog 2.5 V",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=2.62,
        max_warning=2.57,
        min_warning=2.40,
        min_alarm=2.37,
        doc="Analog 2.5 V voltage in Volts.",
    )

    voltageVrefDDR0 = attribute_from_signal(  # noqa: N815
        voltage_vref_ddr0_signal,
        dtype="DevDouble",
        label="Vref voltage for DDR0",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=0.63,
        min_alarm=0.57,
        doc="Vref voltage for DDR0 in Volts.",
    )

    voltageVrefDDR1 = attribute_from_signal(  # noqa: N815
        voltage_vref_ddr1_signal,
        dtype="DevDouble",
        label="Vref voltage for DDR1",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=0.63,
        min_alarm=0.57,
        doc="Vref voltage for DDR1 in Volts.",
    )

    # TODO: add back when available in BIOS.
    # @attribute(dtype="DevDouble", label="voltage VREF_2V5")
    # def voltageVref2V5(self: MccsTile) -> float | None:
    #     """
    #     Handle a Tango attribute read of the Vref 2.5 V voltage.

    #     :return: Vref 2.5 V voltage
    #     """
    #     return self._attribute_state["voltageVref2V5"].read()

    voltageMan1V2 = attribute_from_signal(  # noqa: N815
        voltage_man1v2_signal,
        dtype="DevDouble",
        label="Management 1.2V",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=1.26,
        min_alarm=1.14,
        doc="Management 1.2V voltage in Volts.",
    )

    voltageMGT_AVCC = attribute_from_signal(  # noqa: N815
        voltage_mgt_avcc_signal,
        dtype="DevDouble",
        label="FPGA MGT AV",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=0.97,
        min_alarm=0.83,
        doc="FPGA MGT AV voltage in Volts.",
    )

    voltageMGT_AVTT = attribute_from_signal(  # noqa: N815
        voltage_mgt_avtt_signal,
        dtype="DevDouble",
        label="FPGA MGT AVTT",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=1.26,
        min_alarm=1.104,
        doc="FPGA MGT AVTT voltage in Volts.",
    )

    voltageMon5V0 = attribute_from_signal(  # noqa: N815
        voltage_mon5v0_signal,
        dtype="DevDouble",
        label="Management 5V0",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=5.19,
        min_alarm=4.69,
        doc="Management 5V supply of the TPM in Volts.",
    )

    voltageMon3V3 = attribute_from_signal(  # noqa: N815
        voltage_mon3v3_signal,
        dtype="DevDouble",
        label="Management 3V3",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=3.88,
        min_alarm=3.51,
        doc="Management 3.3 V supply of the TPM in Volts.",
    )

    voltageMon1V8 = attribute_from_signal(  # noqa: N815
        voltage_mon1v8_signal,
        dtype="DevDouble",
        label="Management 1V8",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=2.10,
        min_alarm=1.90,
        doc="Management 1.8 V supply of the TPM in Volts.",
    )

    voltageSW_AVDD1 = attribute_from_signal(  # noqa: N815
        voltage_sw_avdd1_signal,
        dtype="DevDouble",
        label="SW Analog 1.1 V",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=1.16,
        min_alarm=1.04,
        doc="SW Analog 1.1 V voltage in Volts.",
    )

    voltageSW_AVDD2 = attribute_from_signal(  # noqa: N815
        voltage_sw_avdd2_signal,
        dtype="DevDouble",
        label="SW Analog 2.3 V",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=2.42,
        min_alarm=2.18,
        doc="SW Analog 2.3 V voltage in Volts.",
    )

    voltageVIN = attribute_from_signal(  # noqa: N815
        voltage_vin_signal,
        dtype="DevDouble",
        label="input supply",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=12.6,
        min_alarm=11.4,
        doc="Input supply voltage in Volts.",
    )

    voltageVM_AGP0 = attribute_from_signal(  # noqa: N815
        voltage_vm_agp0_signal,
        dtype="DevDouble",
        label="AD AGP group 0",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=0.99,
        min_alarm=0.84,
        doc="AD AGP group 0 voltage in Volts.",
    )

    voltageVM_AGP1 = attribute_from_signal(  # noqa: N815
        voltage_vm_agp1_signal,
        dtype="DevDouble",
        label="AD AGP group 1",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=0.99,
        min_alarm=0.84,
        doc="AD AGP group 1 voltage in Volts.",
    )

    voltageVM_AGP2 = attribute_from_signal(  # noqa: N815
        voltage_vm_agp2_signal,
        dtype="DevDouble",
        label="AD AGP group 2",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=0.99,
        min_alarm=0.84,
        doc="AD AGP group 2 voltage in Volts.",
    )

    voltageVM_AGP3 = attribute_from_signal(  # noqa: N815
        voltage_vm_agp3_signal,
        dtype="DevDouble",
        label="AD AGP group 3",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=0.99,
        min_alarm=0.84,
        doc="AD AGP group 3 voltage in Volts.",
    )

    voltageVM_AGP4 = attribute_from_signal(  # noqa: N815
        voltage_vm_agp4_signal,
        dtype="DevDouble",
        label="AD AGP group 4",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=0.99,
        min_alarm=0.84,
        doc="AD AGP group 4 voltage in Volts.",
    )

    voltageVM_AGP5 = attribute_from_signal(  # noqa: N815
        voltage_vm_agp5_signal,
        dtype="DevDouble",
        label="AD AGP group 5",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=0.99,
        min_alarm=0.84,
        doc="AD AGP group 5 voltage in Volts.",
    )

    voltageVM_AGP6 = attribute_from_signal(  # noqa: N815
        voltage_vm_agp6_signal,
        dtype="DevDouble",
        label="AD AGP group 6",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=0.99,
        min_alarm=0.84,
        doc="AD AGP group 6 voltage in Volts.",
    )

    voltageVM_AGP7 = attribute_from_signal(  # noqa: N815
        voltage_vm_agp7_signal,
        dtype="DevDouble",
        label="AD AGP group 7",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=0.99,
        min_alarm=0.84,
        doc="AD AGP group 7 voltage in Volts.",
    )

    voltageVM_CLK0B = attribute_from_signal(  # noqa: N815
        voltage_vm_clk0b_signal,
        dtype="DevDouble",
        label="Clock Buffer0 3.3V",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=3.56,
        min_alarm=3.04,
        doc="Clock Buffer0 3.3V voltage in Volts.",
    )

    voltageVM_CLK1B = attribute_from_signal(  # noqa: N815
        voltage_vm_clk1b_signal,
        dtype="DevDouble",
        label="Clock Buffer1 3.3V",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=3.56,
        min_alarm=3.04,
        doc="Clock Buffer1 3.3V voltage in Volts.",
    )

    voltageVM_DDR0_VTT = attribute_from_signal(  # noqa: N815
        voltage_vm_ddr0_vtt_signal,
        dtype="DevDouble",
        label="DDR FPGA0 Vtt",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=0.65,
        min_alarm=0.55,
        doc="DDR FPGA0 Vtt voltage in Volts.",
    )

    voltageVM_DDR1_VDD = attribute_from_signal(  # noqa: N815
        voltage_vm_ddr1_vdd_signal,
        dtype="DevDouble",
        label="DDR4",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=1.30,
        min_alarm=1.10,
        doc="DDR4 voltage in Volts.",
    )

    voltageVM_DDR1_VTT = attribute_from_signal(  # noqa: N815
        voltage_vm_ddr1_vtt_signal,
        dtype="DevDouble",
        label="DDR FPGA1 Vtt",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=0.65,
        min_alarm=0.55,
        doc="DDR FPGA1 Vtt voltage in Volts.",
    )

    voltageVM_DRVDD = attribute_from_signal(  # noqa: N815
        voltage_vm_drvdd_signal,
        dtype="DevDouble",
        label="SW DRVDD 1.8V",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=1.89,
        min_alarm=1.71,
        doc="SW DRVDD 1.8V voltage in Volts.",
    )

    voltageVM_DVDD = attribute_from_signal(  # noqa: N815
        voltage_vm_dvdd_signal,
        dtype="DevDouble",
        label="AD DVDD",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=1.19,
        min_alarm=1.01,
        doc="AD DVDD voltage in Volts.",
    )

    voltageVM_FE0 = attribute_from_signal(  # noqa: N815
        voltage_vm_fe0_signal,
        dtype="DevDouble",
        label="FE0",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=3.78,
        min_alarm=3.22,
        doc="FE0 voltage in Volts. PreADU must be on.",
    )

    voltageVM_FE1 = attribute_from_signal(  # noqa: N815
        voltage_vm_fe1_signal,
        dtype="DevDouble",
        label="FE1",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=3.78,
        min_alarm=3.22,
        doc="FE1 voltage in Volts. PreADU must be on.",
    )

    voltageVM_MGT0_AUX = attribute_from_signal(  # noqa: N815
        voltage_vm_mgt0_aux_signal,
        dtype="DevDouble",
        label="FPGA MGT0 AUX",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=1.94,
        min_alarm=1.66,
        doc="FPGA MGT0 AUX voltage in Volts.",
    )

    voltageVM_MGT1_AUX = attribute_from_signal(  # noqa: N815
        voltage_vm_mgt1_aux_signal,
        dtype="DevDouble",
        label="FPGA MGT1 AUX",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=1.94,
        min_alarm=1.66,
        doc="FPGA MGT1 AUX voltage in Volts.",
    )

    voltageVM_PLL = attribute_from_signal(  # noqa: N815
        voltage_vm_pll_signal,
        dtype="DevDouble",
        label="ANALOG PLL",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=3.56,
        min_alarm=3.04,
        doc="ANALOG PLL voltage in Volts.",
    )

    voltageVM_SW_AMP = attribute_from_signal(  # noqa: N815
        voltage_vm_sw_amp_signal,
        dtype="DevDouble",
        label="VGA DC-DC",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        max_alarm=3.78,
        min_alarm=3.22,
        doc="VGA DC-DC voltage in Volts.",
    )

    @attribute(dtype="DevString", label="Polyphase Filter Version")
    def pfbVersion(self: MccsTile) -> str:
        """
        Return the version of the polyphase filter firmware.

        :return: the version of the polyphase filter firmware
        """
        return self._attribute_state["pfbVersion"].read()

    @attribute(
        dtype=("DevLong",),
        max_dim_x=16,
        label="RFI Blanking-enabled Antennas",
        abs_change=1,
        archive_abs_change=1,
    )
    def rfiBlankingEnabledAntennas(self: MccsTile) -> list[int]:
        """
        Get the list of antennas for broadband RFI blanking is currently enabled.

        :return: list of antennas with RFI blanking enabled
        :rtype: list(int)
        """
        return self._attribute_state["rfiBlankingEnabledAntennas"].read()

    @attribute(
        dtype="DevFloat",
        label="Broadband RFI Factor",
        abs_change=0.00000001,  # Below resolution of DevFloat
        archive_abs_change=0.00000001,  # Below resolution of DevFloat
    )
    def broadbandRfiFactor(self: MccsTile) -> float:
        """
        Get the RFI factor for broadband RFI detection.

        Note: Only the RFI factor of FPGA1 is read,
            since the same value is loaded into all FPGAs.

        :return: rfi_factor: the sensitivity value for the RFI detection
        :rtype: float
        """
        return self._attribute_state["broadbandRfiFactor"].read()

    @attribute(
        dtype="DevString",
        label="40G Packet Count",
        fisallowed="_is_initialised",
    )
    def fortyGPacketCount(self: MccsTile) -> str:
        """
        Get 40G packet counts.

        The return value depends on how many 40G cores are active.
        Typically, only one core is active.

        Example::

            # 0 cores active
            {}

            # 1 core active
            {
                'FPGA0': {
                    'rx_received': 2921,
                    'rx_forwarded': 0,
                    'tx_transmitted': 6973024
                }
            }

            # 2 cores active
            {
                'FPGA0': {
                    'rx_received': 3881,
                    'rx_forwarded': 0,
                    'tx_transmitted': 7321460
                },
                'FPGA1': {
                    'rx_received': 1,
                    'rx_forwarded': 0,
                    'tx_transmitted': 3122
                }
            }

        :return: Packet counts per active 40G core. Returns an empty dictionary
                if no 40G cores are active.
        """
        return json.dumps(self._attribute_state["fortyGPacketCount"].read())

    @attribute(
        dtype="DevString",
        label="All Staged Calibration Coefficients",
    )
    def allStagedCal(self: MccsTile) -> str:
        """
        Read all staged calibration coefficients.

        :return: JSON string of all staged calibration coefficients.
        """
        return json.dumps(
            self.component_manager.read_all_staged_calibration_coefficients(),
            cls=NumpyEncoder,
        )

    @attribute(
        dtype="DevString",
        label="All Live Calibration Coefficients",
    )
    def allLiveCal(self: MccsTile) -> str:
        """
        Read all live calibration coefficients.

        :return: JSON string of all live calibration coefficients.
        """
        return json.dumps(
            self.component_manager.read_all_live_calibration_coefficients(),
            cls=NumpyEncoder,
        )

    @attribute(
        dtype=(("DevFloat",),),
        max_dim_x=32,  # Channels
        max_dim_y=8,  # Antennas
        label="Pointing Delays",
        rel_change=0.01,
        archive_rel_change=0.01,
    )
    def pointingDelays(self: MccsTile) -> list[float]:
        """
        Get the pointing delays for beam 0.

        :return: list of pointing delays for beam 0
        """
        return self._attribute_state["pointingDelays"].read()

    # --------
    # Commands
    # --------

    @command(dtype_in="DevString")
    @stb.validators.validate_json_args
    def Configure(
        self: MccsTile,
        antenna_ids: Optional[list[int]] = None,
        fixed_delays: Optional[list[float]] = None,
    ) -> None:
        """
        Configure the tile device attributes.

        A json string with the keywords:

        :param antenna_ids: list of antenna ids to configure, indexed from 1.
            If not provided, all antennas will be configured.
        :param fixed_delays: list of fixed delay values to apply to each channel
            If not provided, no static delays will be applied.
        """

        def apply_if_valid(attr: Any, default: Any) -> Any:
            if isinstance(attr, type(default)):
                return attr
            return default

        self._antenna_ids = apply_if_valid(antenna_ids, self._antenna_ids)
        if fixed_delays is not None:
            self.component_manager.set_static_delays(fixed_delays)

    @stb.long_running_commands.long_running_command
    def Initialise(self: MccsTile) -> stb.type_hints.TaskFunctionType:
        """
        Perform all required initialisation.

        (switches on on-board devices, locks PLL,
        performs synchronisation and other operations required to start configuring the
        signal processing functions of the firmware, such as channelisation and
        beamforming)

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("Initialise")
        """

        def task(
            task_callback: stb.type_hints.TaskCallbackType,
            task_abort_event: threading.Event,
        ) -> None:
            self.component_manager.initialise(
                task_callback=task_callback,
            )

        return task

    @command(dtype_out="DevBoolean", fisallowed="is_engineering")
    def UpdateThresholdCache(self: MccsTile) -> bool:
        """
        Re-sync the threshold caches.

        Re-sync the db thresholds and the firmware thresholds
        and compare the two, transitioning to fault when they do not match.

        NOTE: this command is deprecated, it has been put in to alleviate
        potential issues with ADR-115 firmware threshold work, in the case
        of bugs.

        :return: True if the database matches the firmware, False otherwise.
        """
        self.logger.warning(
            "UpdateThresholdCache command is deprecated, it has "
            "been put in to alleviate potential issues with ADR-115 "
            "firmware threshold work, in the case of bugs."
        )
        # Update db firmware threshold cache from database.
        self.firmware_threshold_db_interface.resync_with_db()

        # Update hw firmware threshold cache from read.
        self.hw_firmware_thresholds = self.component_manager.read_firmware_thresholds()
        self._handle_firmware_read()
        is_match: bool = self._check_database_match()
        return is_match

    @command(dtype_out="DevBoolean", fisallowed="is_engineering")
    def EvaluateTileProgrammingState(self: MccsTile) -> bool:
        """
        Re-evaluate the TileProgrammingState.

        Evaluate and update the TileProgrammingState.
        Return True is the re-evaluation returned a different value to
        the value from automatic detection.
        (A value of True could signify a race condition,
        or that there is a bug in the automatic evaluation.)

        :return: True is the re-evaluation of TpmStatus returns a different value.
        """
        return self.component_manager.reevaluate_tpm_status()

    @command(dtype_out="DevString", fisallowed="_is_programmed")
    def GetFirmwareAvailable(self: MccsTile) -> str:
        """
        Get available firmware.

        Return a dictionary containing the following information for
        each firmware stored on the board (such as in Flash memory).

        For each firmware, a dictionary containing the following keys
        with their respective values should be provided: ‘design’, which
        is a textual name for the firmware, ‘major’, which is the major
        version number, and ‘minor’.

        :return: a JSON-encoded dictionary of firmware details

        :example:
            >>> dp = tango.DeviceProxy("mccs/tile/01")
            >>> jstr = dp.command_inout("GetFirmwareAvailable")
            >>> dict = json.load(jstr)
            {
            "firmware1": {"design": "model1", "major": 2, "minor": 3},
            "firmware2": {"design": "model2", "major": 3, "minor": 7},
            "firmware3": {"design": "model3", "major": 2, "minor": 6},
            }
        """
        return json.dumps(self.component_manager.firmware_available)

    @stb.long_running_commands.long_running_command
    def DownloadFirmware(self: MccsTile, argin: str) -> stb.type_hints.TaskFunctionType:
        """
        Download the firmware contained in bitfile to all FPGAs on the board.

        This should also update the internal register mapping, such that registers
        become available for use.

        :param argin: can either be the design name returned from
            :py:meth:`.GetFirmwareAvailable` command, or a path to a
            file

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("DownloadFirmware", "/tmp/firmware/bitfile")
        """

        def task(
            task_callback: stb.type_hints.TaskCallbackType,
            task_abort_event: threading.Event,
        ) -> None:
            if not os.path.isfile(argin):
                self.logger.error(f"Bitfile: `{argin}` doesn't exist")
                task_callback(TaskStatus.FAILED, result=f"{argin} doesn't exist")
                return
            self.component_manager.download_firmware(
                argin,
                task_callback=task_callback,
            )

        return task

    @command(dtype_out=("DevString",))
    def GetRegisterList(self: MccsTile) -> list[str]:
        """
        Return a list of descriptions of the exposed firmware (and CPLD) registers.

        :return: a list of register names

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> reglist = dp.command_inout("GetRegisterList")
        """
        return self.component_manager.register_list

    @command(dtype_in="DevString", dtype_out="DevVarULongArray")
    def ReadRegister(self: MccsTile, register_name: str) -> list[int]:
        """
        Return the value(s) of the specified register.

        :param register_name: full hyerarchic register name
        :return: a list of register values

        :example:

        >>> dp = tango.DeviceProxy("fpga1./tile/01")
        >>> values = dp.command_inout("ReadRegister", "test-reg1")
        """
        return self.component_manager.read_register(register_name)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    @stb.validators.validate_json_args(schema=WriteRegister_SCHEMA)
    def WriteRegister(
        self: MccsTile, register_name: str, values: list[int]
    ) -> stb.type_hints.DevVarLongStringArrayType:
        """
        Write values to the specified register.

        A json dictionary with mandatory keywords:

        :param register_name: (string) register fully qualified string representation
        :param values: (list) is a list containing the 32-bit values to write

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"register_name": "test-reg1", "values": values,
                    "offset": 0}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("WriteRegister", jstr)
        """
        return self.component_manager.write_register(
            register_name,
            values,
        )

    @command(dtype_in="DevVarLongArray", dtype_out="DevVarULongArray")
    def ReadAddress(self: MccsTile, argin: list[int]) -> list[int]:
        """
        Read n 32-bit values from address.

        :param argin: [0] = address to read from
                      [1] = number of values to read, default 1

        :return: list of values

        :raises ValueError: if no address is provided,
            or if more than 2 parameters are provided

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> reglist = dp.command_inout("ReadAddress", [address, nvalues])
        """
        if len(argin) < 1:
            self.logger.error("At least one parameter is required")
            raise ValueError("One or two parameters are required")
        if len(argin) == 1:
            nvalues = 1
        else:
            nvalues = argin[1]
        address = argin[0]
        return self.component_manager.read_address(address, nvalues)

    @command(dtype_in="DevVarULongArray", dtype_out="DevVarLongStringArray")
    def WriteAddress(
        self: MccsTile, argin: list[int]
    ) -> stb.type_hints.DevVarLongStringArrayType:
        """
        Write list of values at address.

        :param argin: [0] = address to write to
                      [1..n] = list of values to write

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :raises ValueError: if less than 2 parameters are provided

        :example:

        >>> values = [.....]
        >>> address = 0xfff
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("WriteAddress", [address, values])
        """
        if len(argin) < 2:
            self.logger.error("A minimum of two parameters are required")
            raise ValueError("A minimum of two parameters are required")
        return self.component_manager.write_address(argin[0], argin[1:])

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    @stb.validators.validate_json_args(schema=Configure40GCore_SCHEMA)
    def Configure40GCore(
        self: MccsTile,
        core_id: int = 0,
        arp_table_entry: int = 0,
        source_mac: Optional[int] = None,
        source_ip: Optional[str] = None,
        source_port: Optional[int] = None,
        destination_ip: Optional[str] = None,
        destination_port: Optional[int] = None,
        rx_port_filter: Optional[int] = None,
        netmask: Optional[str] = None,
        gateway_ip: Optional[str] = None,
    ) -> stb.type_hints.DevVarLongStringArrayType:
        """
        Configure 40g core_id with specified parameters.

        A json dictionary with only optional keywords:

        :param core_id: (int) core id
        :param arp_table_entry: (int) ARP table entry ID
        :param source_mac: (int) mac address
        :param source_ip: (string) IP dot notation.
        :param source_port: (int) source port
        :param destination_ip: (string) IP dot notation
        :param destination_port: (int) destination port
        :param rx_port_filter: (int) Filter for incoming packets
        :param netmask: (string) 40g (science data) subnet mask
        :param gateway_ip: (string) IP address of 40g (science) subnet gateway

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"core_id":2, "arp_table_entry":0, "source_mac":0x62000a0a01c9,
                    "source_ip":"10.0.99.3", "source_port":4000,
                    "destination_ip":"10.0.99.3", "destination_port":5000}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("Configure40GCore", jstr)
        """
        return self.component_manager.configure_40g_core(
            core_id,
            arp_table_entry,
            source_mac,
            source_ip,
            source_port,
            destination_ip,
            destination_port,
            rx_port_filter,
            netmask,
            gateway_ip,
        )

    @command(dtype_in="DevString", dtype_out="DevString")
    @stb.validators.validate_json_args(schema=Get40GCoreConfiguration_SCHEMA)
    def Get40GCoreConfiguration(
        self: MccsTile, core_id: int = -1, arp_table_entry: int = 0
    ) -> str:
        """
        Get 40g core configuration for core_id.

        This is required to chain up TPMs to form a station.

        A json dictionary with optional keywords:

        :param core_id: (int) core id
        :param arp_table_entry: (int) ARP table entry ID to use

        :return: the configuration is a json string describilg a list (possibly empty)
                 Each list entry comprising:
                 core_id, arp_table_entry, source_mac, source_ip, source_port,
                 destination_ip, destination_port, netmask, gateway_ip

        :raises ValueError: if no configuration is found for the specified
            core_id and arp_table_entry

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> core_id = 2
        >>> arp_table_entry = 0
        >>> argout = dp.command_inout(Get40GCoreConfiguration, core_id, arp_table_entry)
        >>> params = json.loads(argout)
        """
        item_list = self.component_manager.get_40g_configuration(
            core_id=core_id, arp_table_entry=arp_table_entry
        )
        item_new = []
        for item in item_list:
            item_new.append(
                {
                    "core_id": item.get("core_id", None),
                    "arp_table_entry": item.get("arp_table_entry", None),
                    "source_mac": item.get("src_mac", None),
                    "source_ip": item.get("src_ip", None),
                    "source_port": item.get("src_port", None),
                    "destination_ip": item.get("dst_ip", None),
                    "destination_port": item.get("dst_port", None),
                    "netmask": item.get("netmask", None),
                    "gateway_ip": item.get("gateway_ip", None),
                }
            )
        if len(item_new) == 0:
            raise ValueError("Invalid core id or arp table id specified")
        if len(item_new) == 1:
            return json.dumps(item_new[0])
        return json.dumps(item_new)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    @stb.validators.validate_json_args(schema=SetLmcDownload_SCHEMA)
    def SetLmcDownload(
        self: MccsTile,
        mode: str,
        payload_length: int = 1024,
        destination_ip: str = "10.0.10.1",
        source_port: Optional[int] = 0xF0D0,
        destination_port: Optional[int] = 4660,
        netmask_40g: str | None = None,
        gateway_40g: str | None = None,
    ) -> stb.type_hints.DevVarLongStringArrayType:
        """
        Specify whether control data will be transmitted over 1G or 40G networks.

        A json dictionary with optional keywords:

        :param mode: (string) '1G' or '10G' (Mandatory) (use '10G' for 40G also)
        :param payload_length: (int) SPEAD payload length for channel data
        :param destination_ip: (string) Destination IP.
        :param source_port: (int) Source port for integrated data streams
        :param destination_port: (int) Destination port for integrated data streams
        :param netmask_40g: (string) 40g (science data) subnet mask
        :param gateway_40g: (string) IP address of 40g (science) subnet gateway

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >> dp = tango.DeviceProxy("mccs/tile/01")
        >> dict = {"mode": "1G", "payload_length": 4, "destination_ip": "10.0.1.23"}
        >> jstr = json.dumps(dict)
        >> dp.command_inout("SetLmcDownload", jstr)
        """
        return self.component_manager.set_lmc_download(
            mode=mode,
            payload_length=payload_length,
            dst_ip=destination_ip,
            src_port=source_port,
            dst_port=destination_port,
            netmask_40g=netmask_40g,
            gateway_40g=gateway_40g,
        )

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    @stb.validators.validate_json_args(schema=SetLmcIntegratedDownload_SCHEMA)
    def SetLmcIntegratedDownload(
        self: MccsTile,
        mode: str,
        channel_payload_length: int = 1024,
        beam_payload_length: int = 1024,
        destination_ip: str = "10.0.10.1",
        source_port: int = 0xF0D0,
        destination_port: int = 4660,
        netmask_40g: str | None = None,
        gateway_40g: str | None = None,
    ) -> stb.type_hints.DevVarLongStringArrayType:
        """
        Configure link and size of control data.

        A json dictionary with optional keywords:

        :param mode: (string) '1G' or '10G' (Mandatory)
        :param channel_payload_length: (int) SPEAD payload length for integrated
                channel data
        :param beam_payload_length: (int) SPEAD payload length for integrated beam data
        :param destination_ip: (string) Destination IP
        :param source_port: (int) Source port for integrated data streams
        :param destination_port: (int) Destination port for integrated data streams
        :param netmask_40g: (string) 40g (science data) subnet mask
        :param gateway_40g: (string) IP address of 40g (science) subnet gateway

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"mode": "1G", "channel_payload_length":4,
                    "beam_payload_length": 1024, "destination_ip": "10.0.1.23"}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SetLmcIntegratedDownload", jstr)
        """
        self.component_manager.set_lmc_integrated_download(
            mode,
            channel_payload_length,
            beam_payload_length,
            dst_ip=destination_ip,
            src_port=source_port,
            dst_port=destination_port,
            netmask_40g=netmask_40g,
            gateway_40g=gateway_40g,
        )
        return ([ResultCode.OK], ["SetLmcIntegratedDownload command completed OK"])

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    @stb.validators.validate_json_args(schema=SetCspDownload_SCHEMA)
    def SetCspDownload(
        self: MccsTile,
        destination_ip_1: str,
        destination_ip_2: str,
        is_last: bool,
        destination_port: int | None = None,
        source_port: int | None = None,
        netmask: str | None = None,
        gateway: str | None = None,
    ) -> stb.type_hints.DevVarLongStringArrayType:
        """
        Set CSP Destination per tile.

        A json dictionary with optional keywords:

        :param source_port: Source port
        :param destination_ip_1: Destination IP FPGA1
        :param destination_ip_2:  Destination IP FPGA2
        :param destination_port: Destination port
        :param is_last: True for last tile in beamforming chain
        :param netmask: Netmask
        :param gateway: Gateway IP

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"source_port": 4661, "destination_ip_1": "10.0.10.2",
                    "destination_ip_2": "10.0.10.3", "destination_port": 4660,
                    "is_last": False, "netmask": "255.255.255.0",
                    "gateway": "10.0.10.1"}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SetCspDownload", jstr)
        """
        return self.component_manager.set_csp_download(
            source_port,
            destination_ip_1,
            destination_ip_2,
            destination_port,
            is_last,
            netmask,
            gateway,
        )

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def SetAttributeThresholds(
        self: MccsTile, argin: str
    ) -> stb.type_hints.DevVarLongStringArrayType:
        """
        Set the ALARM and WARNING thresholds on attributes.

        :return: A tuple containing ResultCode and a message.

        :example:

            >>> thresholds = {"boardTemperature" : {
                >>>         "max_alarm": "79"
                >>>         "min_alarm": "25"
                >>>         "max_warning": "74"
                >>>         "min_warning": "27"
                >>>         },
                >>>     }
            >>> tile_proxy.SetAttributeThresholds(json.dumps(thresholds))

        :param argin: a serialised dictionary containing attribute names and
            threshold limits.
        """
        attribute_threshold = json.loads(argin)
        message = ""
        multi_attr = self.get_device_attr()
        for attribute_name, thresholds in attribute_threshold.items():
            try:
                attr = multi_attr.get_attr_by_name(attribute_name)
                max_alarm = thresholds.get("max_alarm")
                min_alarm = thresholds.get("min_alarm")
                max_warning = thresholds.get("max_warning")
                min_warning = thresholds.get("min_warning")

                information_message = f"Updated {attribute_name} thresholds: \n"
                if max_alarm is not None:
                    attr.set_max_alarm(max_alarm)
                    information_message += f"\t{max_alarm=}\n"
                if min_alarm is not None:
                    attr.set_min_alarm(min_alarm)
                    information_message += f"\t{min_alarm=}\n"
                if max_warning is not None:
                    attr.set_max_warning(max_warning)
                    information_message += f"\t{max_warning=}\n"
                if min_warning is not None:
                    attr.set_min_warning(min_warning)
                    information_message += f"\t{min_warning=}\n"
                self.logger.info(information_message)
            except Exception as e:  # pylint: disable=broad-except
                self.logger.error(
                    f"Failed to update thresholds for {attribute_name} " f"{repr(e)}"
                )
                message += f"Attribute {attribute_name} failed to update {e}"

        if message != "":
            return ([ResultCode.FAILED], [message])

        return ([ResultCode.OK], [message])

    @command(dtype_out="DevString")
    def GetArpTable(self: MccsTile) -> str:
        """
        Return a dictionary with populated ARP table for all used cores.

        40G interfaces use cores 0 (fpga0) and 1(fpga1) and
        ARP ID 0 for beamformer, 1 for LMC.
        10G interfaces use cores 0,1 (fpga0) and 4,5 (fpga1) for beamforming,
        and 2, 6 for LMC with only one ARP.

        :return: a JSON-encoded dictionary of coreId and populated arpID table

        :example:

        >>> argout = dp.command_inout("GetArpTable")
        >>> dict = json.loads(argout)
        >>>    {
        >>>    "core_id0": [0, 1],
        >>>    "core_id1": [0],
        >>>    "core_id3": [],
        >>>    }
        """
        return json.dumps(self.component_manager.arp_table)

    @command(dtype_in="DevVarLongArray", dtype_out="DevVarLongStringArray")
    def SetBeamFormerRegions(
        self: MccsTile, argin: list[int]
    ) -> stb.type_hints.DevVarLongStringArrayType:
        """
        Set the frequency regions which are going to be beamformed into each beam.

        region_array is defined as a flattened 2D array, for a maximum of 48 regions.
        Total number of channels must be <= 384.

        :param argin: list of regions. Each region comprises:

        * start_channel - (int) region starting channel, must be even in range 0 to 510
        * num_channels - (int) size of the region, must be a multiple of 8
        * beam_index - (int) beam used for this region with range 0 to 47
        * subarray_id - (int) Subarray
        * subarray_logical_channel - (int) logical channel # in the subarray
        * subarray_beam_id - (int) ID of the subarray beam
        * substation_id - (int) Substation
        * aperture_id:  ID of the aperture (station*100+substation?)

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :raises ValueError: when the inputs are invalid

        :example:

        >>> regions = [[4, 24, 0, 0, 0, 3, 1, 101], [26, 40, 1, 0, 24, 4, 2, 102]]
        >>> input = list(itertools.chain.from_iterable(regions))
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("SetBeamFormerRegions", input)
        """
        if len(argin) < 8:
            self.logger.error("Insufficient parameters specified")
            raise ValueError("Insufficient parameters specified")
        if len(argin) > (48 * 8):
            self.logger.error("Too many regions specified")
            raise ValueError("Too many regions specified")
        if len(argin) % 8 != 0:
            self.logger.error(
                "Incomplete specification of region. Regions specified by 8 values"
            )
            raise ValueError("Incomplete specification of region")
        regions = []
        total_chan = 0
        for i in range(0, len(argin), 8):
            region = argin[i : i + 8]  # noqa: E203
            start_channel = region[0]
            if start_channel % 2 != 0:
                self.logger.error("Start channel in region must be even")
                raise ValueError("Start channel in region must be even")
            nchannels = region[1]
            if nchannels % 8 != 0:
                self.logger.error("Nos. of channels in region must be multiple of 8")
                raise ValueError("Nos. of channels in region must be multiple of 8")
            beam_index = region[2]
            if beam_index < 0 or beam_index > 47:
                self.logger.error("Beam_index is out side of range 0-47")
                raise ValueError("Beam_index is out side of range 0-47")
            total_chan += nchannels
            if total_chan > 384:
                self.logger.error("Too many channels specified > 384")
                raise ValueError("Too many channels specified > 384")
            regions.append(region)

        if total_chan < 8:
            self.logger.error("No channels specified")
            raise ValueError("No channels specified")
        nof_blocks = 0
        for region in regions:
            nof_blocks += region[1] // 8
        if nof_blocks == 0:
            self.logger.error("No valid beamformer regions specified")
            raise ValueError("Empty channel table")
        return self.component_manager.set_beamformer_regions(regions)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    @stb.validators.validate_json_args(schema=ConfigureStationBeamformer_SCHEMA)
    def ConfigureStationBeamformer(
        self: MccsTile,
        start_channel: int = 192,
        n_channels: int = 8,
        is_first: bool = False,
        is_last: bool = False,
    ) -> stb.type_hints.DevVarLongStringArrayType:
        """
        Initialise and start the station beamformer.

        Initial configuration of the tile-station beamformer.
        Optionally set the observed region, Default is 6.25 MHz starting at 150 MHz,
        and set whether the tile is the first or last in the beamformer chain.

        A json dictionary with mandatory keywords:

        :param start_channel: (int) start channel of the observed region
            default = 192 (150 MHz)
        :param n_channels: (int) is the number of channels in the observed region
            default = 8 (6.25 MHz)
        :param is_first: (bool) whether the tile is the first one in the station
            default False
        :param is_last: (bool) whether the tile is the last one in the station
            default False

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :raises ValueError: when the specified observed region is invalid

        :example:

        >> dp = tango.DeviceProxy("mccs/tile/01")
        >> dict = {"start_channel":64, "n_channels":10, "is_first":True,
        >>         "is_last:True}
        >> jstr = json.dumps(dict)
        >> dp.command_inout("ConfigureStationBeamformer", jstr)
        """
        if start_channel + n_channels > 511:
            self.logger.error("Invalid specified observed region")
            raise ValueError("Invalid specified observed region")
        self.component_manager.initialise_beamformer(
            start_channel, n_channels, is_first, is_last
        )
        return ([ResultCode.OK], ["ConfigureStationBeamformer command completed OK"])

    @command(dtype_in="DevVarDoubleArray", dtype_out="DevVarLongStringArray")
    def LoadCalibrationCoefficients(
        self: MccsTile, argin: list[float]
    ) -> stb.type_hints.DevVarLongStringArrayType:
        """
        Load the calibration coefficients, but does not apply them.

        This is performed by apply_calibration.
        The calibration coefficients may include any rotation
        matrix (e.g. the parallactic angle), but do not include the geometric delay.

        :param argin: list comprises:

        * antenna - (int) is the antenna to which the coefficients will be applied.
        * calibration_coefficients - [array] a bidimensional complex array comprising
            calibration_coefficients[channel, polarization], with each element
            representing a normalized coefficient, with (1.0, 0.0) being the
            normal, expected response for an ideal antenna.

            * channel - (int) channel is the index specifying the channels at the
                              beamformer output, i.e. considering only those channels
                              actually processed and beam assignments.
            * polarization index ranges from 0 to 3.

                * 0: X polarization direct element
                * 1: X->Y polarization cross element
                * 2: Y->X polarization cross element
                * 3: Y polarization direct element

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :raises ValueError: when the inputs are invalid

        :example:

        >>> antenna = 2
        >>> complex_coefficients = [[complex(3.4, 1.2), complex(2.3, 4.1),
        >>>            complex(4.6, 8.2), complex(6.8, 2.4)]]*5
        >>> inp = list(itertools.chain.from_iterable(complex_coefficients))
        >>> out = ([v.real, v.imag] for v in inp]
        >>> coefficients = list(itertools.chain.from_iterable(out))
        >>> coefficients.insert(0, float(antenna))
        >>> input = list(itertools.chain.from_iterable(coefficients))
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("LoadCalibrationCoefficients", input)
        """
        if len(argin) < 9:
            self.logger.error("Insufficient calibration coefficients")
            raise ValueError("Insufficient calibration coefficients")
        if len(argin[1:]) % 8 != 0:
            self.logger.error(
                "Incomplete specification of coefficient. "
                "Needs 8 values (4 complex Jones) per channel"
            )
            raise ValueError("Incomplete specification of coefficient")
        antenna = int(argin[0])
        calibration_coefficients = [
            [
                complex(argin[i], argin[i + 1]),
                complex(argin[i + 2], argin[i + 3]),
                complex(argin[i + 4], argin[i + 5]),
                complex(argin[i + 6], argin[i + 7]),
            ]
            for i in range(1, len(argin), 8)
        ]

        return self.component_manager.load_calibration_coefficients(
            antenna, calibration_coefficients
        )

    @command(dtype_in="DevVarDoubleArray", dtype_out="DevVarLongStringArray")
    def LoadCalibrationCoefficientsForChannels(
        self: MccsTile, argin: list[float]
    ) -> stb.type_hints.DevVarLongStringArrayType:
        """
        Load the calibration coefficients, but does not apply them.

        This is performed by apply_calibration.
        The calibration coefficients may include any rotation
        matrix (e.g. the parallactic angle), but do not include the geometric delay.

        :param argin: list comprises:

        * start_channel - (int) is the first channel to which the coefficients
            will be applied.
        * calibration_coefficients - [array] a tridimensional complex array comprising
            calibration_coefficients[channel, antenna, polarization], with each element
            representing a normalized coefficient, with (1.0, 0.0) being the
            normal, expected response for an ideal antenna.

            * channel - (int) channel is the index specifying the channels at the
                              beamformer output, i.e. considering only those channels
                              actually processed and beam assignments.
            * antenna - index ranging 0 to 16, for the 16 antennas managed by the tile
            * polarization index ranges from 0 to 3.

                * 0: X polarization direct element
                * 1: X->Y polarization cross element
                * 2: Y->X polarization cross element
                * 3: Y polarization direct element

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :raises ValueError: when the inputs are invalid

        :example:

        >>> start_channel = 2
        >>> complex_coefficients =[[[complex(3.4, 1.2), complex(2.3, 4.1),
        >>>            complex(4.6, 8.2), complex(6.8, 2.4)]]*16]*4
        >>> inp = list(itertools.chain.from_iterable(complex_coefficients))
        >>> out = ([v.real, v.imag] for v in inp]
        >>> coefficients = list(itertools.chain.from_iterable(out))
        >>> coefficients.insert(0, float(start_channel))
        >>> input = list(itertools.chain.from_iterable(coefficients))
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("LoadCalibrationCoefficientsForChannels", input)
        """
        if len(argin) < 129:
            self.logger.error("Insufficient calibration coefficients")
            raise ValueError("Insufficient calibration coefficients")
        if len(argin[1:]) % 128 != 0:
            self.logger.error(
                "Incomplete specification of coefficient. "
                "Needs 8 values (4 complex Jones) per channeli per antenna"
            )
            raise ValueError("Incomplete specification of coefficient")
        start_channel = int(argin[0])
        if (start_channel < 0) or (start_channel > 383):
            raise ValueError("Start channel outside of range 0-383")
        calibration_coefficients = [
            [
                [
                    complex(argin[ant + i], argin[ant + i + 1]),
                    complex(argin[ant + i + 2], argin[ant + i + 3]),
                    complex(argin[ant + i + 4], argin[ant + i + 5]),
                    complex(argin[ant + i + 6], argin[ant + i + 7]),
                ]
                for ant in range(0, 128, 8)
            ]
            for i in range(1, len(argin), 128)
        ]

        return self.component_manager.load_calibration_coefficients_for_channels(
            start_channel, calibration_coefficients
        )

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def ApplyCalibration(
        self: MccsTile, switch_time: str
    ) -> stb.type_hints.DevVarLongStringArrayType:
        """
        Load the calibration coefficients at the specified time delay.

        :param switch_time: switch time, in ISO formatted time

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("ApplyCalibration", "")
        """
        return self.component_manager.apply_calibration(switch_time)

    @command(dtype_in="DevVarDoubleArray", dtype_out="DevVarLongStringArray")
    def LoadPointingDelays(
        self: MccsTile, argin: list[float]
    ) -> stb.type_hints.DevVarLongStringArrayType:
        """
        Specify the delay in seconds and the delay rate in seconds/second.

        The delay_array specifies the delay and delay rate for each antenna. beam_index
        specifies which beam is desired (range 0-7)

        :param argin: An array containing: beam index,
            the delay in seconds and the delay rate in
            seconds/second, for each antenna.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :raises ValueError: If the number of parameters is insufficient or
            if the beam index is invalid.

        :example:

        >>> # example delays: 16 values from -2 to +2 ns, rates = 0
        >>> delays = [step * 0.25e-9 for step in list(range(-8, 8))]
        >>> rates = [0.0]*16
        >>> beam = 0.0
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> arg = [beam]
        >>> for i in range(16):
        >>>   arg.append(delays[i])
        >>>   arg.append(rates[i])
        >>> dp.command_inout("LoadPointingDelays", arg)
        """
        if len(argin) < self.AntennasPerTile * 2 + 1:
            self.logger.error("Insufficient parameters")
            raise ValueError("Insufficient parameters")
        beam_index = int(argin[0])
        if beam_index < 0 or beam_index > 7:
            self.logger.error("Invalid beam index")
            raise ValueError("Invalid beam index")
        delay_array = []
        for i in range(self.AntennasPerTile):
            delay_array.append([argin[i * 2 + 1], argin[i * 2 + 2]])

        return self.component_manager.load_pointing_delays(delay_array, beam_index)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def ApplyPointingDelays(
        self: MccsTile, start_time: str
    ) -> stb.type_hints.DevVarLongStringArrayType:
        """
        Apply the pointing delays at the specified time delay.

        :param start_time: time for applying the delays (default = 0)

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("ApplyPointingDelays", "")
        """
        return self.component_manager.apply_pointing_delays(start_time)

    @stb.long_running_commands.long_running_command
    @stb.validators.validate_json_args(schema=StartBeamformer_SCHEMA)
    def StartBeamformer(
        self: MccsTile,
        start_time: Optional[str] = None,
        duration: int = -1,
        channel_groups: Optional[list[int]] = None,
        scan_id: int = 0,
    ) -> stb.type_hints.TaskFunctionType:
        """
        Start the beamformer at the specified time delay.

        :param start_time: Start time as ISO formatted time
        :param duration: Scan duration, in frames, default "forever"
        :param channel_groups: Channel groups to be started
                Command affects only beamformed channels for given groups
                Default: all channels
        :param scan_id: ID of the scan to be started. Default 0

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"StartTime":10, "Duration":20, "channel_groups": [0,1,4] }
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("StartBeamformer", jstr)
        """

        def task(
            task_callback: stb.type_hints.TaskCallbackType,
            task_abort_event: threading.Event,
        ) -> None:
            self.component_manager.start_beamformer(
                start_time=start_time,
                duration=duration,
                channel_groups=channel_groups,
                scan_id=scan_id,
                task_callback=task_callback,
            )

        return task

    @stb.long_running_commands.long_running_command
    @stb.validators.validate_json_args(schema=StopBeamformer_SCHEMA)
    def StopBeamformer(
        self: MccsTile, channel_groups: Optional[list[int]] = None
    ) -> stb.type_hints.TaskFunctionType:
        """
        Stop the beamformer.

        :param channel_groups: list of channel groups to be stopped
                Command affects only beamformed channels for given groups
                Default: all channels

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"channel_groups": [0,1,4] }
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("StopBeamformer", jstr)
        """

        def task(
            task_callback: stb.type_hints.TaskCallbackType,
            task_abort_event: threading.Event,
        ) -> None:
            self.component_manager.stop_beamformer(
                channel_groups=channel_groups,
                task_callback=task_callback,
            )

        return task

    @command(dtype_in="DevString", dtype_out="DevBoolean")
    @stb.validators.validate_json_args(schema=BeamformerRunning_SCHEMA)
    def BeamformerRunningForChannels(
        self: MccsTile, channel_groups: list[int] | None = None
    ) -> bool:
        """
        Check whether the beamformer is running for the given channel groups.

        A json dictionary with optional keywords:

        :param channel_groups: (list) List of channel groups

        :return: Whether the beamformer is running

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"channel_groups": [0,1,4,5]}
        >>> jstr = json.dumps(dict)
        >>> running = dp.command_inout("BeamformerRunningForChannels", jstr)
        """
        return self.component_manager.beamformer_running_for_channels(channel_groups)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    @stb.validators.validate_json_args(schema=ConfigureIntegratedChannelData_SCHEMA)
    def ConfigureIntegratedChannelData(
        self: MccsTile,
        integration_time: float = 0.5,
        first_channel: int = 0,
        last_channel: int = 511,
    ) -> stb.type_hints.DevVarLongStringArrayType:
        """
        Configure and start the transmission of integrated channel data.

        Using the provided integration time, first channel and last channel.
        Data are sent continuously until the StopIntegratedData command is run.

        A json dictionary with optional keywords:

        :param integration_time: (float) in seconds (default = 0.5)
        :param first_channel: (int) default 0
        :param last_channel: (int) default 511

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"integration_time": 0.2, "first_channel":0, "last_channel": 191}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("ConfigureIntegratedChannelData", jstr)
        """
        return self.component_manager.configure_integrated_channel_data(
            integration_time, first_channel, last_channel
        )

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    @stb.validators.validate_json_args(schema=ConfigureIntegratedBeamData_SCHEMA)
    def ConfigureIntegratedBeamData(
        self: MccsTile,
        integration_time: float = 0.5,
        first_channel: int = 0,
        last_channel: int = 191,
    ) -> stb.type_hints.DevVarLongStringArrayType:
        """
        Configure the transmission of integrated beam data.

        Using the provided integration time, the first channel and the last channel.
        The data are sent continuously until the StopIntegratedData command is run.

        A json dictionary with optional keywords:

        :param integration_time: (float) in seconds (default = 0.5)
        :param first_channel: (int) default 0
        :param last_channel: (int) default 191

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"integration_time": 0.2, "first_channel":0, "last_channel": 191}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("ConfigureIntegratedBeamData", jstr)
        """
        return self.component_manager.configure_integrated_beam_data(
            integration_time, first_channel, last_channel
        )

    @command(dtype_out="DevVarLongStringArray")
    def StopIntegratedData(self: MccsTile) -> stb.type_hints.DevVarLongStringArrayType:
        """
        Stop the integrated data.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        return self.component_manager.stop_integrated_data()

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    @stb.validators.validate_json_args(schema=SendDataSamples_SCHEMA)
    def SendDataSamples(
        self: MccsTile,
        **kwargs: Optional[Any],
    ) -> stb.type_hints.DevVarLongStringArrayType:
        """
        Transmit a snapshot containing raw antenna data.

        :param kwargs: json dictionary with optional keywords:

        * data_type - type of snapshot data (mandatory): "raw", "channel",
                    "channel_continuous", "narrowband", "beam"
        * start_time - Time (UTC string) to start sending data. Default immediately
        * seconds - (float) Delay if timestamp is not specified. Default 0.2 seconds

        Depending on the data type:
        raw:

        * sync: bool: send synchronised samples for all antennas, vs. round robin
                larger snapshot from each antenna

        channel:

        * n_samples: Number of samples per channel, default 1024
        * first_channel - (int) first channel to send, default 0
        * last_channel - (int) last channel to send, default 511

        channel_continuous

        * channel_id - (int) channel_id (Mandatory)
        * n_samples -  (int) number of samples to send per packet, default 128

        narrowband:

        * frequency - (int) Sky frequency for band centre, in Hz (Mandatory)
        * round_bits - (int)  Specify how many bits to round
        * n_samples -  (int) number of spectra to send

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :raises ValueError: if the provided arguments are invalid

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"data_type": "raw", "Sync":True, "Seconds": 0.2}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SendDataSamples", jstr)
        """
        data_type = kwargs["data_type"]
        if data_type == "channel":
            first_ch = kwargs.get("first_channel", 0)
            last_ch = kwargs.get("last_channel", 511)
            if last_ch < first_ch:  # type: ignore[operator]
                err = (
                    f"last channel ({last_ch}) cannot be less than first "
                    f"channel ({first_ch})."
                )
                self.logger.error(err)
                raise ValueError(err)

        if data_type in ["channel", "narrowband"]:
            kwargs.setdefault("n_samples", 1024)
        elif data_type == "channel_continuous":
            kwargs.setdefault("n_samples", 128)
        else:
            kwargs.setdefault("n_samples", None)

        self.component_manager.send_data_samples(**kwargs)  # type: ignore[arg-type]
        return ([ResultCode.OK], ["SendDataSamples command completed OK"])

    @command(dtype_out="DevVarLongStringArray")
    def StopDataTransmission(
        self: MccsTile,
    ) -> stb.type_hints.DevVarLongStringArrayType:
        """
        Stop data transmission from board.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("StopDataTransmission")
        """
        return self.component_manager.stop_data_transmission()

    @stb.long_running_commands.long_running_command
    @stb.validators.validate_json_args(schema=StartAcquisition_SCHEMA)
    def StartAcquisition(
        self: MccsTile,
        start_time: Optional[str] = None,
        global_reference_time: Optional[str] = None,
        delay: Optional[int] = 2,
    ) -> stb.type_hints.TaskFunctionType:
        """
        Start data acquisition.

        json dictionary with optional keywords:

        :param start_time: the acquisition start time
        :param delay: a delay to the acquisition start (default 2s)
        :param global_reference_time: the start time assumed for starting the timestamp

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"start_time":"2021-11-22, "delay":20}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("StartAcquisition", jstr)
        """

        def task(
            task_callback: stb.type_hints.TaskCallbackType,
            task_abort_event: threading.Event,
        ) -> None:
            self.component_manager.start_acquisition(
                start_time=start_time,
                global_reference_time=global_reference_time,
                delay=delay if delay is not None else 2,
                task_callback=task_callback,
            )

        return task

    def is_ConfigureTestGenerator_allowed(self: MccsTile) -> bool:
        """
        Check if command is allowed.

        It is allowed only in engineering mode.

        :returns: whether the command is allowed
        """
        return self.admin_mode_model.admin_mode == AdminMode.ENGINEERING

    # pylint: disable=too-many-locals
    @engineering_mode_required
    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    @stb.validators.validate_json_args(schema=ConfigureTestGenerator_SCHEMA)
    def ConfigureTestGenerator(
        self: MccsTile,
        set_time: Optional[str] = None,
        tone_frequency: Optional[float] = None,
        tone_amplitude: Optional[float] = None,
        tone_2_frequency: Optional[float] = None,
        tone_2_amplitude: Optional[float] = None,
        noise_amplitude: Optional[float] = None,
        pulse_frequency: Optional[int] = None,
        pulse_amplitude: Optional[float] = None,
        adc_channels: Optional[list[int]] = None,
        **kwargs: Optional[Any],
    ) -> stb.type_hints.DevVarLongStringArrayType:
        """
        Set the test signal generator.

        A json dictionary with keywords:

        :param tone_frequency: first tone frequency, in Hz. The frequency
            is rounded to the resolution of the generator. If this
            is not specified, the tone generator is disabled.
        :param tone_amplitude: peak tone amplitude, normalized to 31.875 ADC
            units. The amplitude is rounded to 1/8 ADC unit. Default
            is 1.0. A value of -1.0 keeps the previously set value.
        :param tone_2_frequency: frequency for the second tone. Same
            as ToneFrequency.
        :param tone_2_amplitude: peak tone amplitude for the second tone.
            Same as ToneAmplitude.
        :param noise_amplitude: RMS amplitude of the pseudorandom Gaussian
            white noise, normalized to 26.03 ADC units.
        :param pulse_frequency: frequency of the periodic pulse. A code
            in the range 0 to 7, corresponding to (16, 12, 8, 6, 4, 3, 2)
            times the ADC frame frequency.
        :param pulse_amplitude: peak amplitude of the periodic pulse, normalized
            to 127 ADC units. Default is 1.0. A value of -1.0 keeps the
            previously set value.
        :param set_time: time at which the generator is set, for synchronization
            among different TPMs. In UTC ISO format (string)
        :param adc_channels: list of adc channels which will be substituted with
            the generated signal. It is a 32 integer, with each bit representing
            an input channel. Default: all if at least q source is specified,
            none otherwises.
        :param kwargs: optional keyword arguments:
            Currently supports: delays

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"tone_frequency": 150e6, "tone_amplitude": 0.1,
                "noise_amplitude": 0.9, "pulse_frequency": 7,
                "set_time": "2022-08-09T12:34:56.7Z"}
        >>> jstr = json.dumps(dict)
        >>> values = dp.command_inout("ConfigureTestGenerator", jstr)
        """
        active = False
        if tone_frequency is not None:
            frequency0 = tone_frequency
            amplitude0 = tone_amplitude if tone_amplitude is not None else 1.0
            active = True
        else:
            frequency0 = 0.0
            amplitude0 = 0.0

        if tone_2_frequency is not None:
            frequency1 = tone_2_frequency
            amplitude1 = tone_2_amplitude if tone_2_amplitude is not None else 1.0
            active = True
        else:
            frequency1 = 0.0
            amplitude1 = 0.0

        if noise_amplitude is not None:
            amplitude_noise = noise_amplitude
            active = True
        else:
            amplitude_noise = 0.0

        if pulse_frequency is not None:
            pulse_code = pulse_frequency
            amplitude_pulse = pulse_amplitude if pulse_amplitude is not None else 1.0
            active = True
        else:
            pulse_code = 7
            amplitude_pulse = 0.0

        self.component_manager.configure_test_generator(
            frequency0,
            amplitude0,
            frequency1,
            amplitude1,
            amplitude_noise,
            pulse_code,
            amplitude_pulse,
            kwargs.get("delays", None),
            set_time,
        )

        chans = adc_channels
        inputs = 0
        if chans is None:
            if active:
                inputs = 0xFFFFFFFF
        else:
            for channel in chans:
                inputs = inputs | (1 << channel)
        self.component_manager.test_generator_input_select(inputs)
        self.component_manager.test_generator_active = active
        return ([ResultCode.OK], ["ConfigureTestGenerator command completed OK"])

    @engineering_mode_required
    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    @stb.validators.validate_json_args(schema=ConfigurePatternGenerator_SCHEMA)
    def ConfigurePatternGenerator(
        self: MccsTile,
        stage: str,
        pattern: list[int],
        adders: list[int],
        start: bool = False,
        shift: int = 0,
        zero: int = 0,
        ramp1: dict[str, int] | None = None,
        ramp2: dict[str, int] | None = None,
    ) -> stb.type_hints.DevVarLongStringArrayType:
        """
        Set the test pattern generator using the provided configuration.

        A JSON dictionary with the following keywords:

        :param stage: The stage in the signal chain where the pattern is injected.
            Options are: 'jesd' (output of ADCs), 'channel' (output of the
            channelizer), or 'beamf' (output of the tile beamformer).
        :param pattern: The data pattern in time order. Must be an array of length 1
            to 1024. Represents values in time order, not for antennas or
            polarizations.
        :param adders: A list of 32 integers that expands the pattern to cover 16
            antennas and 2 polarizations. The adders map the pattern to hardware
            signals.
        :param start: Boolean flag to indicate whether to start the pattern
            immediately. If False, the pattern can be started manually later.
        :param shift: Optional bit shift (divides by 2^shift). Must not be used in
            'beamf' stage, where it is always overridden to 4.
        :param zero: Integer (0-65535) used as a mask to disable the pattern on
            specific antennas and polarizations. Applied to both FPGAs, supports
            up to 8 antennas and 2 polarizations.
        :param ramp1: An optional ramp1 applied after pattern.
            polarisation: The polarisation to apply the ramp for.
            This must be 0, 1 or -1 to use all stages.
        :param ramp2: An optional ramp2 applied after pattern.
            (note: ramp2 = ramp1 + 1234)
            polarisation: The polarisation to apply the ramp for.
            This must be 0, 1 or -1 to use all stages.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> test_pattern = list(range(1024))
        >>> for n in range(1024):
                if n % 2 == 0:
                    test_pattern[n] = n
                else:
                    test_pattern[n] = random.randrange(0, 255, 1)
        >>> test_adders = list(range(32))
        >>> config = {"stage": "jesd", "pattern": test_pattern, "adders":
                      test_adders, "start": True}
        >>> jstr = json.dumps(config)
        >>> values = dp.command_inout("ConfigurePatternGenerator", jstr)
        """
        self.component_manager.configure_pattern_generator(
            stage, pattern, adders, start, shift, zero, ramp1, ramp2
        )
        return ([ResultCode.OK], ["ConfigurePatternGenerator command completed OK"])

    @engineering_mode_required
    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def StopPatternGenerator(
        self: MccsTile, stage: str
    ) -> stb.type_hints.DevVarLongStringArrayType:
        """
        Stop the pattern generator at the specified stage.

        The stage can be the output of the JESD, the channelizer, or the beamformer.

        :param stage: A positional string argument specifying the stage in the signal
            chain where the pattern was injected. Options are: 'jesd' (output of ADCs),
            'channel' (output of channelizer), 'beamf' (output of tile beamformer),
            or 'all' for all stages.

        :return: A tuple containing a return code and a string message
            indicating status. The message is for information purposes only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("StopPatternGenerator", "jesd")
        """
        self.component_manager.stop_pattern_generator(stage)
        return ([ResultCode.OK], ["StopPatternGenerator command completed OK"])

    @engineering_mode_required
    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def StartPatternGenerator(
        self: MccsTile, stage: str
    ) -> stb.type_hints.DevVarLongStringArrayType:
        """
        Start the pattern generator at the specified stage.

        The stage can be the output of the JESD, the channelizer, or the beamformer.

        :param stage: A positional string argument specifying the stage in the signal
            chain where the pattern was injected. Options are: 'jesd' (output of ADCs),
            'channel' (output of channelizer), 'beamf' (output of tile beamformer),
            or 'all' for all stages.

        :return: A tuple containing a return code and a string message
            indicating status. The message is for information purposes only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("StartPatternGenerator", "channel")
        """
        self.component_manager.start_pattern_generator(stage)
        return ([ResultCode.OK], ["StartPatternGenerator command completed OK"])

    @engineering_mode_required
    @command(dtype_out="DevVarLongStringArray")
    def StartADCs(self: MccsTile) -> stb.type_hints.DevVarLongStringArrayType:
        """
        Start the ADCs.

        :return: A tuple containing a return code and a string message
            indicating status. The message is for information purposes only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("StartADCs")
        """
        self.component_manager.start_adcs()
        return ([ResultCode.OK], ["StartAdcs command completed OK"])

    @engineering_mode_required
    @command(dtype_out="DevVarLongStringArray")
    def StopADCs(self: MccsTile) -> stb.type_hints.DevVarLongStringArrayType:
        """
        Stop the ADCs.

        :return: A tuple containing a return code and a string message
            indicating status. The message is for information purposes only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("StopADCs")
        """
        self.component_manager.stop_adcs()
        return ([ResultCode.OK], ["StopAdcs command completed OK"])

    @command(dtype_out="DevVarLongStringArray")
    def EnableStationBeamFlagging(
        self: MccsTile,
    ) -> stb.type_hints.DevVarLongStringArrayType:
        """
        Enable station beam flagging.

        :return: A tuple containing a return code and a string message
            indicating status. The message is for information purposes only.

        TODO THORN-68: Currently we can't verify if the flag has been set correctly,
        this functionality will get added later

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("EnableStationBeamFlagging")
        """
        self.component_manager.enable_station_beam_flagging()
        beam_flag_values = self.component_manager.is_station_beam_flagging_enabled

        if all(value for value in beam_flag_values):
            return ([ResultCode.OK], ["EnableStationBeamFlagging command completed OK"])
        return ([ResultCode.FAILED], ["EnableStationBeamFlagging failed to execute"])

    @command(dtype_out="DevVarLongStringArray")
    def DisableStationBeamFlagging(
        self: MccsTile,
    ) -> stb.type_hints.DevVarLongStringArrayType:
        """
        Disable station beam flagging.

        :return: A tuple containing a return code and a string message
            indicating status. The message is for information purposes only.

        TODO THORN-68: Currently we can't verify if the flag has been set correctly,
        this functionality will get added later

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("DisableStationBeamFlagging")
        """
        self.component_manager.disable_station_beam_flagging()
        beam_flag_values = self.component_manager.is_station_beam_flagging_enabled

        if all(not value for value in beam_flag_values):
            return (
                [ResultCode.OK],
                ["DisableStationBeamFlagging command completed OK"],
            )
        return ([ResultCode.FAILED], ["DisableStationBeamFlagging failed to execute"])

    def __str__(self: MccsTile) -> str:
        """
        Produce list of tile information.

        :return: Information string
        :rtype: str
        """
        info = self._info
        return (
            f"\nTile Processing Module {info['hardware']['HARDWARE_REV']} "
            f"Serial Number: {info['hardware']['SN']} \n"
            f"{'_'*90} \n"
            f"{' '*29}| \n"
            f"Classification               | "
            f"{info['hardware']['PN']}-{info['hardware']['BOARD_MODE']} \n"
            f"Hardware Revision            | {info['hardware']['HARDWARE_REV']} \n"
            f"Serial Number                | {info['hardware']['SN']} \n"
            f"BIOS Revision                | {info['hardware']['bios']} \n"
            f"Board External Label         | {info['hardware']['EXT_LABEL']} \n"
            f"DDR Memory Capacity          | {info['hardware']['DDR_SIZE_GB']} "
            f"GB per FPGA \n"
            f"{'_'*29}|{'_'*60} \n"
            f"{' '*29}| \n"
            f"FPGA Firmware Design         | {info['fpga_firmware']['design']} \n"
            f"FPGA Firmware Revision       | {info['fpga_firmware']['build']} \n"
            f"FPGA Firmware Compile Time   | {info['fpga_firmware']['compile_time']} "
            f"UTC \n"
            f"FPGA Firmware Compile User   | {info['fpga_firmware']['compile_user']} "
            f" \n"
            f"FPGA Firmware Compile Host   | {info['fpga_firmware']['compile_host']} \n"
            f"FPGA Firmware Git Branch     | {info['fpga_firmware']['git_branch']} \n"
            f"FPGA Firmware Git Commit     | {info['fpga_firmware']['git_commit']} \n"
            f"{'_'*29}|{'_'*60} \n"
            f"{' '*29}| \n"
            f"1G (MGMT) IP Address         | {str(info['network']['1g_ip_address'])} \n"
            f"1G (MGMT) MAC Address        | {info['network']['1g_mac_address']} \n"
            f"1G (MGMT) Netmask            | {str(info['network']['1g_netmask'])} \n"
            f"1G (MGMT) Gateway IP         | {str(info['network']['1g_gateway'])} \n"
            f"EEP IP Address               | {str(info['hardware']['ip_address_eep'])}"
            f" \n"
            f"EEP Netmask                  | {str(info['hardware']['netmask_eep'])} \n"
            f"EEP Gateway IP               | {str(info['hardware']['gateway_eep'])} \n"
            f"40G Port 1 IP Address        | "
            f"{str(info['network']['40g_ip_address_p1'])} \n"
            f"40G Port 1 MAC Address       | "
            f"{str(info['network']['40g_mac_address_p1'])} \n"
            f"40G Port 1 Netmask           | {str(info['network']['40g_netmask_p1'])}"
            f" \n"
            f"40G Port 1 Gateway IP        | {str(info['network']['40g_gateway_p1'])}"
            f" \n"
            f"40G Port 2 IP Address        | "
            f"{str(info['network']['40g_ip_address_p2'])} \n"
            f"40G Port 2 MAC Address       | "
            f"{str(info['network']['40g_mac_address_p2'])} \n"
            f"40G Port 2 Netmask           | {str(info['network']['40g_netmask_p2'])}"
            f" \n"
            f"40G Port 2 Gateway IP        | {str(info['network']['40g_gateway_p2'])}"
            f" \n"
        )

    # -------------
    # AntennaBuffer
    # -------------

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    @stb.validators.validate_json_args
    def SetUpAntennaBuffer(
        self: MccsTile,
        mode: str = "SDN",
        ddr_start_byte_address: int = 512 * 1024**2,
        max_ddr_byte_size: int | None = None,
    ) -> stb.type_hints.DevVarLongStringArrayType:
        """Set up the antenna buffer.

        A json serialised dictionary containing the following keys:

        :param mode: network to transmit antenna buffer data to. Options: 'SDN'
            (Science Data Network) and 'NSDN' (Non-Science Data Network)
        :param ddr_start_byte_address: first address in the DDR for antenna buffer
            data to be written in (in bytes).
        :param max_ddr_byte_size: last address for writing antenna buffer data
            (in bytes). If 'None' is chosen, the method will assume the last
            address to be the final address of the DDR chip

        :return: A tuple containing a return code and a string message indicating
            status. The message is for information purpose only.
        """
        if self.component_manager.set_up_antenna_buffer(
            mode, ddr_start_byte_address, max_ddr_byte_size
        ):
            result = self.component_manager.tile._antenna_buffer_tile_attribute
            return ([ResultCode.OK], [str(result)])
        return ([ResultCode.FAILED], ["SetUpAntennaBuffer command failed to complete"])

    @stb.long_running_commands.long_running_command
    @stb.validators.validate_json_args
    def StartAntennaBuffer(
        self: MccsTile,
        antennas: list[int],
        start_time: int = -1,
        timestamp_capture_duration: int = 75,
        continuous_mode: bool = False,
    ) -> stb.type_hints.TaskFunctionType:
        """
        Start recording to the antenna buffer.

        :param antennas: a list of antenna IDs to be used by the buffer, from 0 to 15.
            One or two antennas can be used for each FPGA, or 1 to 4 per buffer.
        :param start_time: the first time stamp that will be written into the DDR.
            When set to -1, the buffer will begin writing as soon as possible.
        :param timestamp_capture_duration: the capture duration in timestamps.
            Timestamps are in units of 256 ADC samples (256*1.08us).
        :param continuous_mode: "True" for continous capture. If enabled, time capture
            durations is ignored

        :return: A tuple containing a return code and a string message indicating
            status. The message is for information purpose only.

        """

        def task(
            task_callback: stb.type_hints.TaskCallbackType,
            task_abort_event: threading.Event,
        ) -> None:
            self.component_manager.start_antenna_buffer(
                antennas=antennas,
                start_time=start_time,
                timestamp_capture_duration=timestamp_capture_duration,
                continuous_mode=continuous_mode,
                task_callback=task_callback,
            )

        return task

    @stb.long_running_commands.long_running_command
    def ReadAntennaBuffer(self: MccsTile) -> stb.type_hints.TaskFunctionType:
        """
        Read the data from the antenna buffer.

        :return: A tuple containing a return code and a string message indicating
            status. The message is for information purpose only.
        """

        def task(
            task_callback: stb.type_hints.TaskCallbackType,
            task_abort_event: threading.Event,
        ) -> None:
            self.component_manager.read_antenna_buffer(
                task_callback=task_callback,
            )

        return task

    @command(dtype_out="DevVarLongStringArray")
    def StopAntennaBuffer(self: MccsTile) -> stb.type_hints.DevVarLongStringArrayType:
        """
        Stop writting to the antenna buffer.

        :return: A tuple containing a return code and a string message indicating
            status. The message is for information purpose only.
        """
        if self.component_manager.stop_antenna_buffer():
            return ([ResultCode.OK], ["StopAntennaBuffer command completed OK"])
        return ([ResultCode.FAILED], ["StopAntennaBuffer command failed to complete"])

    # ---------------
    # On/Off commands
    # ---------------

    def execute_Off(self: MccsTile) -> DevVarLongStringArrayType:
        """
        Turn the device off.

        To modify behaviour for this command, modify the do() method of
        the command class.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        if not self.UseAttributesForHealth:
            self._health_model._ignore_power_state = True
        return super().execute_Off()

    def execute_On(self: MccsTile) -> DevVarLongStringArrayType:
        """
        Turn device on.

        To modify behaviour for this command, modify the do() method of
        the command class.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        if self.get_state() == tango.DevState.ON:
            return ([ResultCode.REJECTED], ["Device is already in ON state."])

        if not self.UseAttributesForHealth:
            self._health_model._ignore_power_state = False
        return super().execute_On()

    @command(dtype_in="DevVarLongArray", dtype_out="DevVarLongStringArray")
    def EnableBroadbandRfiBlanking(
        self: MccsTile, argin: list[int]
    ) -> stb.type_hints.DevVarLongStringArrayType:
        """
        Enable broadband RFI blanking on specified antennas.

        :param argin: List of antenna IDs to enable blanking on (0-15).
        :return: A tuple containing a return code and a string message
            indicating status. The message is for information purposes only.
        """
        if len(argin) > 16:
            return ([ResultCode.REJECTED], ["Cannot specify more than 16 antennas"])
        if max(argin) > 15 or min(argin) < 0:
            return ([ResultCode.REJECTED], ["Antenna IDs must be between 0 and 15"])
        self.component_manager.enable_broadband_rfi_blanking(argin)
        return ([ResultCode.OK], ["EnableBroadbandRfiBlanking command completed OK"])

    @command(dtype_in="DevVarLongArray", dtype_out="DevVarLongStringArray")
    def DisableBroadbandRfiBlanking(
        self: MccsTile, argin: list[int]
    ) -> stb.type_hints.DevVarLongStringArrayType:
        """
        Disable broadband RFI blanking on specified antennas.

        :param argin: List of antenna IDs to disable blanking on (0-15).
        :return: A tuple containing a return code and a string message
            indicating status. The message is for information purposes only.
        """
        if len(argin) > 16:
            return ([ResultCode.REJECTED], ["Cannot specify more than 16 antennas"])
        if max(argin) > 15 or min(argin) < 0:
            return ([ResultCode.REJECTED], ["Antenna IDs must be between 0 and 15"])
        self.component_manager.disable_broadband_rfi_blanking(argin)
        return ([ResultCode.OK], ["DisableBroadbandRfiBlanking command completed OK"])

    @command(dtype_in="DevFloat", dtype_out="DevVarLongStringArray")
    def SetBroadbandRfiFactor(
        self: MccsTile, rfi_factor: float
    ) -> stb.type_hints.DevVarLongStringArrayType:
        """
        Set the RFI factor for broadband RFI detection.

        The higher the RFI factor, the less RFI is detected/flagged.
        This is because data is flagged if the short term power is greater than
        the long term power * RFI factor * 32/27

        :param rfi_factor: the sensitivity value for the RFI detection

        :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
        """
        self.component_manager.set_broadband_rfi_factor(rfi_factor)
        return ([ResultCode.OK], ["SetBroadbandRfiFactor command completed OK"])

    @command(
        dtype_in="DevVarLongArray",
        dtype_out="DevVarLongArray",
    )
    def ReadBroadbandRfi(self: MccsTile, argin: list[int]) -> list[int]:
        """
        Read out the broadband RFI counters for the specified antennas.

        :param argin: list antennas of which RFI counters to read
        :return: RFI counters per pol flattened as a 1D list

        :raises ValueError: if input arguments are invalid
        """
        if len(argin) > 16:
            raise ValueError("Cannot specify more than 16 antennas")
        if max(argin) > 15 or min(argin) < 0:
            raise ValueError("Antenna IDs must be between 0 and 15")
        return self.component_manager.read_broadband_rfi(argin).flatten().tolist()

    @command(dtype_in="DevVarLongArray", dtype_out="DevLong")
    def MaxBroadbandRfi(self: MccsTile, argin: list[int]) -> int:
        """
        Get max of RFI counts of specified antennas.

        This returns the RFI count of the antenna with the maximum RFI count.

        :param argin: list antennas whose RFI counters to read
        :return: Maximum RFI counts
        :rtype: int

        :raises ValueError: if input arguments are invalid
        """
        if len(argin) > 16:
            raise ValueError("Cannot specify more than 16 antennas")
        if max(argin) > 15 or min(argin) < 0:
            raise ValueError("Antenna IDs must be between 0 and 15")
        return self.component_manager.max_broadband_rfi(argin)

    @command(dtype_out="DevVarLongStringArray")
    def ClearBroadbandRfi(self: MccsTile) -> stb.type_hints.DevVarLongStringArrayType:
        """
        Clear all RFI counts registers.

        :return: A tuple containing a return code and a string message
            indicating status. The message is for information purposes only.
        """
        self.component_manager.clear_broadband_rfi()
        return ([ResultCode.OK], ["ClearBroadbandRfi command completed OK"])


# ----------
# Run server
# ----------
def main(*args: str, **kwargs: str) -> int:  # pragma: no cover
    """
    Entry point for module.

    :param args: positional arguments
    :param kwargs: named arguments

    :return: exit code
    """
    return MccsTile.run_server(args=args or None, **kwargs)


if __name__ == "__main__":
    main()
