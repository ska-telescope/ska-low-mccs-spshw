# pylint: disable=too-many-lines
#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
The Tango attributes of the prototype subrack device, and what feeds them.

Each value the device reports needs one signal and one attribute built from it.
:py:class:`SubrackAttributes` declares both. The tables here say which polled
key, or which path into the health status, feeds each signal, and which few
values are converted on the way. The device mixes the class in and holds all
the behaviour.
"""
from __future__ import annotations

import json
from typing import Any, Final

from ska_control_model import PowerState
from ska_tango_base.software_bus import AttrSignal, attribute_from_signal

from ..subrack.subrack_data import SubrackData
from .constants import HEALTH_STATUS_KEY, DerivedKey, ReadKey

__all__ = [
    "ALL_SIGNALS",
    "HEALTH_ATTRIBUTES",
    "HEALTH_ATTRIBUTES_FROM_1_8_0",
    "HEALTH_PATH_TO_SIGNAL",
    "HEALTH_PATHS_TO_SPECTRUM_SIGNAL",
    "READ_KEY_TO_SIGNAL",
    "VALUE_CONVERTERS",
    "TPM_POWER_STATE_SIGNALS",
    "SubrackAttributes",
    "health_attributes",
]


# Poll value key to the name of the signal that carries it. Keyed off the
# enums rather than string literals, so a renamed key is a type error rather
# than an attribute that silently stops updating. The TPM on off flags have no
# signal of their own, because only the TPM power states report them.
READ_KEY_TO_SIGNAL: Final[dict[str, str]] = {
    ReadKey.TPM_PRESENT.value: "_tpm_present",
    ReadKey.BACKPLANE_TEMPERATURES.value: "_backplane_temperatures",
    ReadKey.BOARD_TEMPERATURES.value: "_board_temperatures",
    ReadKey.BOARD_CURRENT.value: "_board_current",
    ReadKey.CPLD_PLL_LOCKED.value: "_cpld_pll_locked",
    ReadKey.POWER_SUPPLY_CURRENTS.value: "_power_supply_currents",
    ReadKey.POWER_SUPPLY_FAN_SPEEDS.value: "_power_supply_fan_speeds",
    ReadKey.POWER_SUPPLY_POWERS.value: "_power_supply_powers",
    ReadKey.POWER_SUPPLY_VOLTAGES.value: "_power_supply_voltages",
    ReadKey.SUBRACK_FAN_SPEEDS.value: "_subrack_fan_speeds",
    ReadKey.SUBRACK_FAN_SPEEDS_PERCENT.value: "_subrack_fan_speeds_percent",
    ReadKey.SUBRACK_FAN_MODE.value: "_subrack_fan_modes",
    ReadKey.SUBRACK_PLL_LOCKED.value: "_subrack_pll_locked",
    ReadKey.SUBRACK_TIMESTAMP.value: "_subrack_timestamp",
    ReadKey.TPM_CURRENTS.value: "_tpm_currents",
    ReadKey.TPM_POWERS.value: "_tpm_powers",
    ReadKey.TPM_VOLTAGES.value: "_tpm_voltages",
    ReadKey.BOARD_INFO.value: "_subrack_board_info",
    DerivedKey.SUBRACK_MAX_FAN_SPEEDS.value: "_subrack_max_fan_speeds",
    DerivedKey.PSU_DEAD_COUNT.value: "_psu_dead_count",
    DerivedKey.TPM_COUNT.value: "_tpm_count",
    DerivedKey.PSU1_LOAD.value: "_psu1_load",
    DerivedKey.PSU2_LOAD.value: "_psu2_load",
    HEALTH_STATUS_KEY: "_health_status",
}

# Signal name to its path inside the polled health status dictionary.
HEALTH_PATH_TO_SIGNAL: Final[dict[str, tuple[str, ...]]] = {
    "_internal_voltages_1v1": ("internal_voltages", "V_1V1"),
    "_internal_voltages_1v5": ("internal_voltages", "V_1V5"),
    "_internal_voltages_2v5": ("internal_voltages", "V_2V5"),
    "_internal_voltages_2v8": ("internal_voltages", "V_2V8"),
    "_internal_voltages_3v": ("internal_voltages", "V_3V"),
    "_internal_voltages_3v3": ("internal_voltages", "V_3V3"),
    "_internal_voltages_5v": ("internal_voltages", "V_5V"),
    "_internal_voltages_arm": ("internal_voltages", "V_ARM"),
    "_internal_voltages_core": ("internal_voltages", "V_CORE"),
    "_internal_voltages_ddr": ("internal_voltages", "V_DDR"),
    "_internal_voltages_powerin": ("internal_voltages", "V_POWERIN"),
    "_internal_voltages_soc": ("internal_voltages", "V_SOC"),
    "_psu1_present": ("psus", "present", "PSU1"),
    "_psu2_present": ("psus", "present", "PSU2"),
    "_psu1_power_in": ("psus", "power_in", "PSU1"),
    "_psu2_power_in": ("psus", "power_in", "PSU2"),
    "_psu1_power_out": ("psus", "power_out", "PSU1"),
    "_psu2_power_out": ("psus", "power_out", "PSU2"),
    "_psu1_voltage_in": ("psus", "voltage_in", "PSU1"),
    "_psu2_voltage_in": ("psus", "voltage_in", "PSU2"),
    "_psu1_voltage_out": ("psus", "voltage_out", "PSU1"),
    "_psu2_voltage_out": ("psus", "voltage_out", "PSU2"),
    "_internal_voltages_powerin_min": ("internal_voltages", "V_POWERIN_MIN"),
    "_internal_voltages_powerin_max": ("internal_voltages", "V_POWERIN_MAX"),
    "_backplane_power_good": ("internal_voltages", "BkplnPowerGood"),
    "_board_apll_unlock_count": ("plls", "BoardApllUnlockCount"),
    "_board_dpll_unlock_count": ("plls", "BoardDpllUnlockCount"),
    "_board_sysclk_event_count": ("plls", "BoardSysclkEventCount"),
    "_pll_source": ("plls", "PllSource"),
    "_pps_present": ("plls", "PPS"),
    "_pps_fault_count": ("plls", "PPSFaultCount"),
    "_pps_phase": ("plls", "PPSPhase"),
    "_pps_phase_stdev": ("plls", "PPSPhaseStdev"),
    "_pps_phase_outliers": ("plls", "PPSPhaseOutliers"),
    "_ref_present": ("plls", "REF"),
    "_ref_fault_count": ("plls", "REFFaultCount"),
    "_cpld_pings": ("pings", "pings_CPLD"),
    "_board_power": ("SMM", "power"),
    "_board_max_power": ("SMM", "power_max"),
    "_board_pll_temperature": ("temperatures", "SMM_PLL"),
}


def _each(
    group: str, point: str, names: tuple[str, ...]
) -> tuple[tuple[str, ...], ...]:
    """
    Return the health status path of one monitoring point for each name.

    :param group: the outermost key, such as ``slots``.
    :param point: the monitoring point within the group, such as ``faults``.
    :param names: the innermost keys, one for each element.

    :return: one path for each name, in the order given.
    """
    return tuple((group, point, name) for name in names)


_PSUS: Final = ("PSU1", "PSU2")
_SLOTS: Final = tuple(f"SLOT{n}" for n in range(1, SubrackData.TPM_BAY_COUNT + 1))

# Spectrum signal name to the health status path of each of its elements.
HEALTH_PATHS_TO_SPECTRUM_SIGNAL: Final[dict[str, tuple[tuple[str, ...], ...]]] = {
    "_power_supply_fan_speeds_rpm": _each("psus", "fan_speed", _PSUS),
    "_power_supply_fet_temperatures": _each("psus", "temp_fet", _PSUS),
    "_power_supply_inlet_temperatures": _each("psus", "temp_inlet", _PSUS),
    "_power_supply_busy": _each("psus", "busy", _PSUS),
    "_power_supply_off": _each("psus", "off", _PSUS),
    "_power_supply_power_good": _each("psus", "pwr_gd", _PSUS),
    "_power_supply_cml_faults": _each("psus", "cml_fault", _PSUS),
    "_power_supply_fan_faults": _each("psus", "fan_fault", _PSUS),
    "_power_supply_input_faults": _each("psus", "input_fault", _PSUS),
    "_power_supply_iout_faults": _each("psus", "iout_fault", _PSUS),
    "_power_supply_iout_oc_faults": _each("psus", "iout_oc_fault", _PSUS),
    "_power_supply_temp_faults": _each("psus", "temp_fault", _PSUS),
    "_power_supply_vin_uv_faults": _each("psus", "vin_uv_fault", _PSUS),
    "_power_supply_vout_faults": _each("psus", "vout_fault", _PSUS),
    "_power_supply_vout_ov_faults": _each("psus", "vout_ov_fault", _PSUS),
    "_power_supply_other_faults": _each("psus", "other", _PSUS),
    "_power_supply_unknown_faults": _each("psus", "unknown", _PSUS),
    "_tpm_min_voltages": _each("slots", "voltages_min", _SLOTS),
    "_tpm_max_voltages": _each("slots", "voltages_max", _SLOTS),
    "_tpm_max_powers": _each("slots", "powers_max", _SLOTS),
    "_tpm_faults": _each("slots", "faults", _SLOTS),
    "_tpm_pings": _each("slots", "pings", _SLOTS),
    "_tpm_singlewire": _each("slots", "singlewire", _SLOTS),
}

# The signal for each bay's TPM power state, in bay order. These are derived
# from the polled TPM on off flags rather than read. They are left out of
# ALL_SIGNALS because they behave as they do on MccsSubrack. A lost board makes
# them UNKNOWN rather than invalid.
TPM_POWER_STATE_SIGNALS: Final[tuple[str, ...]] = tuple(
    f"_tpm{bay}_power_state" for bay in range(1, SubrackData.TPM_BAY_COUNT + 1)
)

# Every signal this device emits, so that a lost board can invalidate all
# of them.
ALL_SIGNALS: Final[tuple[str, ...]] = (
    tuple(READ_KEY_TO_SIGNAL.values())
    + tuple(HEALTH_PATH_TO_SIGNAL)
    + tuple(HEALTH_PATHS_TO_SPECTRUM_SIGNAL)
)


# The attributes whose quality decides the health of the device. The health
# recorder subscribes to these. The others are left out because their quality
# says nothing about the subrack, or because they have no alarm thresholds.
HEALTH_ATTRIBUTES: Final[tuple[str, ...]] = (
    "backplaneTemperatures",
    "boardTemperatures",
    "powerSupplyPowers",
    "powerSupplyVoltages",
    "subrackFanSpeeds",
    "subrackFanSpeedsPercent",
    "subrackMaxFanSpeeds",
    "tpmPowers",
    "tpmVoltages",
    "psuDeadCount",
    "internalVoltages1V1",
    "internalVoltages1V5",
    "internalVoltages2V5",
    "internalVoltages2V8",
    "internalVoltages3V",
    "internalVoltages3V3",
    "internalVoltages5V",
    "internalVoltagesARM",
    "internalVoltagesCORE",
    "internalVoltagesDDR",
    "internalVoltagesPOWERIN",
    "internalVoltagesSOC",
    "psu1Present",
    "psu2Present",
    "psu1PowerIn",
    "psu2PowerIn",
    "psu1PowerOut",
    "psu2PowerOut",
    "psu1VoltageIn",
    "psu2VoltageIn",
    "psu1VoltageOut",
    "psu2VoltageOut",
    "internalVoltagesPOWERINMIN",
    "internalVoltagesPOWERINMAX",
    "boardApllUnlockCount",
    "boardDpllUnlockCount",
    "boardSysclkEventCount",
    "boardPower",
    "boardMaxPower",
    "boardPllTemperature",
    "powerSupplyFanSpeedsRpm",
    "powerSupplyFetTemperatures",
    "powerSupplyInletTemperatures",
    "tpmMinVoltages",
    "tpmMaxVoltages",
    "tpmMaxPowers",
)

# The health attributes that only API 1.8.0 and later report. An older board
# leaves their points out of the health status, so they would always be
# invalid, and an invalid attribute fails the health.
HEALTH_ATTRIBUTES_FROM_1_8_0: Final[tuple[str, ...]] = (
    "internalVoltagesPOWERINMIN",
    "internalVoltagesPOWERINMAX",
    "boardApllUnlockCount",
    "boardDpllUnlockCount",
    "boardSysclkEventCount",
    "tpmMinVoltages",
    "tpmMaxVoltages",
    "tpmMaxPowers",
)


def health_attributes(board_info: dict) -> list[str]:
    """
    Return the health attributes that a board with this board info reports.

    :param board_info: the board info that the subrack reported.

    :return: the attributes whose quality decides the health, in the order of
        ``HEALTH_ATTRIBUTES``.
    """
    if SubrackData.bios_version(board_info) >= [1, 8, 0]:
        return list(HEALTH_ATTRIBUTES)
    return [
        name for name in HEALTH_ATTRIBUTES if name not in HEALTH_ATTRIBUTES_FROM_1_8_0
    ]


def _as_spectrum(value: Any) -> list[Any]:
    """
    Wrap a scalar the board reports into the one element list Tango wants.

    :param value: the value the board reported.

    :return: the value as a list.
    """
    return list(value) if isinstance(value, (list, tuple)) else [value]


# The few signals whose board value is not already what the attribute expects.
VALUE_CONVERTERS: Final[dict[str, Any]] = {
    # The board reports these as nested dictionaries, and the attributes are
    # JSON strings.
    "_subrack_board_info": json.dumps,
    "_health_status": json.dumps,
    # The board reports a single total, and the attribute is a one element
    # spectrum.
    "_board_current": _as_spectrum,
}


class SubrackAttributes:  # pylint: disable=too-few-public-methods
    """
    The signals and Tango attributes of the prototype subrack device.

    Mixed into the device, which supplies every behaviour. Nothing here depends
    on the device, because the poll callbacks reach a signal by the name the
    tables above give rather than by referring to it directly. A signal must
    still be declared before the attribute that is built from it.
    """

    # =====================================================================
    # Attribute declarations
    #
    # These sit below the logic because they are boilerplate. Each value the
    # device reports needs one signal and one attribute built from it, and the
    # two are declared in the same order throughout. Nothing above depends on
    # where they appear, because the poll callbacks reach a signal by the name
    # the mapping tables give, not by referring to it directly. A signal must
    # still be declared before the attribute that is built from it.
    # =====================================================================

    # ---------------------------
    # Signals for the board reads
    # ---------------------------
    _tpm_present: AttrSignal[list[bool]] = AttrSignal[list[bool]]()
    _tpm_count: AttrSignal[int] = AttrSignal[int]()
    _backplane_temperatures: AttrSignal[list[float]] = AttrSignal[list[float]]()
    _board_temperatures: AttrSignal[list[float]] = AttrSignal[list[float]]()
    _board_current: AttrSignal[list[float]] = AttrSignal[list[float]]()
    _cpld_pll_locked: AttrSignal[bool] = AttrSignal[bool]()
    _power_supply_currents: AttrSignal[list[float]] = AttrSignal[list[float]]()
    _power_supply_fan_speeds: AttrSignal[list[float]] = AttrSignal[list[float]]()
    _power_supply_powers: AttrSignal[list[float]] = AttrSignal[list[float]]()
    _power_supply_voltages: AttrSignal[list[float]] = AttrSignal[list[float]]()
    _subrack_fan_speeds: AttrSignal[list[float]] = AttrSignal[list[float]]()
    _subrack_fan_speeds_percent: AttrSignal[list[float]] = AttrSignal[list[float]]()
    _subrack_fan_modes: AttrSignal[list[int]] = AttrSignal[list[int]]()
    _subrack_max_fan_speeds: AttrSignal[list[float]] = AttrSignal[list[float]]()
    _subrack_pll_locked: AttrSignal[bool] = AttrSignal[bool]()
    _subrack_timestamp: AttrSignal[int] = AttrSignal[int]()
    _tpm_currents: AttrSignal[list[float]] = AttrSignal[list[float]]()
    _tpm_powers: AttrSignal[list[float]] = AttrSignal[list[float]]()
    _tpm_voltages: AttrSignal[list[float]] = AttrSignal[list[float]]()
    _subrack_board_info: AttrSignal[str] = AttrSignal[str]()

    # ---------------------------------
    # Signals for the TPM power states
    # ---------------------------------
    _tpm1_power_state: AttrSignal[PowerState] = AttrSignal[PowerState]()
    _tpm2_power_state: AttrSignal[PowerState] = AttrSignal[PowerState]()
    _tpm3_power_state: AttrSignal[PowerState] = AttrSignal[PowerState]()
    _tpm4_power_state: AttrSignal[PowerState] = AttrSignal[PowerState]()
    _tpm5_power_state: AttrSignal[PowerState] = AttrSignal[PowerState]()
    _tpm6_power_state: AttrSignal[PowerState] = AttrSignal[PowerState]()
    _tpm7_power_state: AttrSignal[PowerState] = AttrSignal[PowerState]()
    _tpm8_power_state: AttrSignal[PowerState] = AttrSignal[PowerState]()

    # -----------------------------
    # Signals for the health status
    # -----------------------------
    _internal_voltages_1v1: AttrSignal[float] = AttrSignal[float]()
    _internal_voltages_1v5: AttrSignal[float] = AttrSignal[float]()
    _internal_voltages_2v5: AttrSignal[float] = AttrSignal[float]()
    _internal_voltages_2v8: AttrSignal[float] = AttrSignal[float]()
    _internal_voltages_3v: AttrSignal[float] = AttrSignal[float]()
    _internal_voltages_3v3: AttrSignal[float] = AttrSignal[float]()
    _internal_voltages_5v: AttrSignal[float] = AttrSignal[float]()
    _internal_voltages_arm: AttrSignal[float] = AttrSignal[float]()
    _internal_voltages_core: AttrSignal[float] = AttrSignal[float]()
    _internal_voltages_ddr: AttrSignal[float] = AttrSignal[float]()
    _internal_voltages_powerin: AttrSignal[float] = AttrSignal[float]()
    _internal_voltages_soc: AttrSignal[float] = AttrSignal[float]()
    _psu1_present: AttrSignal[bool] = AttrSignal[bool]()
    _psu2_present: AttrSignal[bool] = AttrSignal[bool]()
    _psu1_power_in: AttrSignal[float] = AttrSignal[float]()
    _psu2_power_in: AttrSignal[float] = AttrSignal[float]()
    _psu1_power_out: AttrSignal[float] = AttrSignal[float]()
    _psu2_power_out: AttrSignal[float] = AttrSignal[float]()
    _psu1_voltage_in: AttrSignal[float] = AttrSignal[float]()
    _psu2_voltage_in: AttrSignal[float] = AttrSignal[float]()
    _psu1_voltage_out: AttrSignal[float] = AttrSignal[float]()
    _psu2_voltage_out: AttrSignal[float] = AttrSignal[float]()
    _psu_dead_count: AttrSignal[int] = AttrSignal[int]()
    _psu1_load: AttrSignal[float] = AttrSignal[float]()
    _psu2_load: AttrSignal[float] = AttrSignal[float]()
    _internal_voltages_powerin_min: AttrSignal[float] = AttrSignal[float]()
    _internal_voltages_powerin_max: AttrSignal[float] = AttrSignal[float]()
    _backplane_power_good: AttrSignal[bool] = AttrSignal[bool]()
    _board_apll_unlock_count: AttrSignal[int] = AttrSignal[int]()
    _board_dpll_unlock_count: AttrSignal[int] = AttrSignal[int]()
    _board_sysclk_event_count: AttrSignal[int] = AttrSignal[int]()
    _pll_source: AttrSignal[str] = AttrSignal[str]()
    _pps_present: AttrSignal[bool] = AttrSignal[bool]()
    _pps_fault_count: AttrSignal[int] = AttrSignal[int]()
    _pps_phase: AttrSignal[float] = AttrSignal[float]()
    _pps_phase_stdev: AttrSignal[float] = AttrSignal[float]()
    _pps_phase_outliers: AttrSignal[int] = AttrSignal[int]()
    _ref_present: AttrSignal[bool] = AttrSignal[bool]()
    _ref_fault_count: AttrSignal[int] = AttrSignal[int]()
    _cpld_pings: AttrSignal[bool] = AttrSignal[bool]()
    _board_power: AttrSignal[float] = AttrSignal[float]()
    _board_max_power: AttrSignal[float] = AttrSignal[float]()
    _board_pll_temperature: AttrSignal[float] = AttrSignal[float]()
    _power_supply_fan_speeds_rpm: AttrSignal[list[float]] = AttrSignal[list[float]]()
    _power_supply_fet_temperatures: AttrSignal[list[float]] = AttrSignal[list[float]]()
    _power_supply_inlet_temperatures: AttrSignal[list[float]] = AttrSignal[
        list[float]
    ]()
    _power_supply_busy: AttrSignal[list[bool]] = AttrSignal[list[bool]]()
    _power_supply_off: AttrSignal[list[bool]] = AttrSignal[list[bool]]()
    _power_supply_power_good: AttrSignal[list[bool]] = AttrSignal[list[bool]]()
    _power_supply_cml_faults: AttrSignal[list[bool]] = AttrSignal[list[bool]]()
    _power_supply_fan_faults: AttrSignal[list[bool]] = AttrSignal[list[bool]]()
    _power_supply_input_faults: AttrSignal[list[bool]] = AttrSignal[list[bool]]()
    _power_supply_iout_faults: AttrSignal[list[bool]] = AttrSignal[list[bool]]()
    _power_supply_iout_oc_faults: AttrSignal[list[bool]] = AttrSignal[list[bool]]()
    _power_supply_temp_faults: AttrSignal[list[bool]] = AttrSignal[list[bool]]()
    _power_supply_vin_uv_faults: AttrSignal[list[bool]] = AttrSignal[list[bool]]()
    _power_supply_vout_faults: AttrSignal[list[bool]] = AttrSignal[list[bool]]()
    _power_supply_vout_ov_faults: AttrSignal[list[bool]] = AttrSignal[list[bool]]()
    _power_supply_other_faults: AttrSignal[list[bool]] = AttrSignal[list[bool]]()
    _power_supply_unknown_faults: AttrSignal[list[bool]] = AttrSignal[list[bool]]()
    _tpm_min_voltages: AttrSignal[list[float]] = AttrSignal[list[float]]()
    _tpm_max_voltages: AttrSignal[list[float]] = AttrSignal[list[float]]()
    _tpm_max_powers: AttrSignal[list[float]] = AttrSignal[list[float]]()
    _tpm_faults: AttrSignal[list[bool]] = AttrSignal[list[bool]]()
    _tpm_pings: AttrSignal[list[bool]] = AttrSignal[list[bool]]()
    _tpm_singlewire: AttrSignal[list[bool]] = AttrSignal[list[bool]]()
    _health_status: AttrSignal[str] = AttrSignal[str]()

    # ------------------------------
    # Signal for the health recorder
    # ------------------------------
    _health_report: AttrSignal[str] = AttrSignal[str]()

    # ---------------------------
    # Attributes for board reads
    # ---------------------------
    tpmPresent = attribute_from_signal(
        _tpm_present,
        dtype=(bool,),
        max_dim_x=SubrackData.TPM_BAY_COUNT,
        label="TPM present",
        doc="Whether each TPM bay is occupied.",
    )

    tpmCount = attribute_from_signal(
        _tpm_count,
        dtype="DevShort",
        label="TPM Count",
        abs_change=1,
        archive_abs_change=1,
        doc="The number of TPM bays that are occupied.",
    )

    backplaneTemperatures = attribute_from_signal(
        _backplane_temperatures,
        dtype=("DevFloat",),
        max_dim_x=2,
        label="Backplane temperatures",
        unit="Celsius",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Backplane temperatures in degrees Celsius.",
    )

    boardTemperatures = attribute_from_signal(
        _board_temperatures,
        dtype=("DevFloat",),
        max_dim_x=2,
        label="Subrack board temperatures",
        unit="Celsius",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Management board temperatures in degrees Celsius.",
    )

    boardCurrent = attribute_from_signal(
        _board_current,
        dtype=("DevFloat",),
        max_dim_x=1,
        label="Board current",
        unit="Ampere",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Management board current in Amperes.",
    )

    cpldPllLocked = attribute_from_signal(
        _cpld_pll_locked,
        dtype=bool,
        label="CPLD PLL locked",
        doc="Whether the CPLD PLL is locked.",
    )

    powerSupplyCurrents = attribute_from_signal(
        _power_supply_currents,
        dtype=("DevFloat",),
        max_dim_x=2,
        label="power supply currents",
        unit="Ampere",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Power supply output currents in Amperes.",
    )

    powerSupplyFanSpeeds = attribute_from_signal(
        _power_supply_fan_speeds,
        dtype=("DevFloat",),
        max_dim_x=3,
        label="power supply fan speeds",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Power supply fan speeds, as a percentage of the maximum.",
    )

    powerSupplyPowers = attribute_from_signal(
        _power_supply_powers,
        dtype=("DevFloat",),
        max_dim_x=2,
        label="power supply powers",
        unit="Watt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Power supply output powers in Watts.",
    )

    powerSupplyVoltages = attribute_from_signal(
        _power_supply_voltages,
        dtype=("DevFloat",),
        max_dim_x=2,
        label="power supply voltages",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Power supply output voltages in Volts.",
    )

    subrackFanSpeeds = attribute_from_signal(
        _subrack_fan_speeds,
        dtype=("DevFloat",),
        max_dim_x=SubrackData.FAN_COUNT,
        label="subrack fan speeds",
        unit="rpm",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Measured subrack fan speeds in rpm.",
    )

    subrackFanSpeedsPercent = attribute_from_signal(
        _subrack_fan_speeds_percent,
        dtype=("DevFloat",),
        max_dim_x=SubrackData.FAN_COUNT,
        label="subrack fan speeds (%)",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack fan pwm duty cycle setpoints, as a percentage.",
    )

    # This is (int,) rather than (FanMode,) because of pytango issue 483, which
    # prevents an enumerated spectrum attribute from working.
    subrackFanModes = attribute_from_signal(
        _subrack_fan_modes,
        dtype=(int,),
        max_dim_x=SubrackData.FAN_COUNT,
        label="subrack fan modes",
        abs_change=1,
        archive_abs_change=1,
        doc="Subrack fan modes, 0 for manual and 1 for automatic.",
    )

    subrackMaxFanSpeeds = attribute_from_signal(
        _subrack_max_fan_speeds,
        dtype=("DevFloat",),
        max_dim_x=SubrackData.FAN_COUNT,
        label="expected fan speeds at 100% pwm duty",
        unit="rpm",
        max_alarm=9750,  # 150%
        max_warning=8125,  # 125%
        min_alarm="Not specified",  # ignore faults on RAL
        min_warning="Not specified",  # ignore faults on RAL
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack fan speeds estimated at 100% pwm duty, in rpm.",
    )

    subrackPllLocked = attribute_from_signal(
        _subrack_pll_locked,
        dtype=bool,
        label="PLL locked",
        doc="Whether the subrack PLL is locked.",
    )

    subrackTimestamp = attribute_from_signal(
        _subrack_timestamp,
        dtype="DevLong",
        label="Timestamp",
        abs_change=1,
        archive_abs_change=1,
        doc="The subrack board timestamp.",
    )

    tpmCurrents = attribute_from_signal(
        _tpm_currents,
        dtype=("DevFloat",),
        max_dim_x=SubrackData.TPM_BAY_COUNT,
        label="TPM currents",
        unit="Ampere",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Per bay TPM currents in Amperes.",
    )

    tpmPowers = attribute_from_signal(
        _tpm_powers,
        dtype=("DevFloat",),
        max_dim_x=SubrackData.TPM_BAY_COUNT,
        label="TPM powers",
        unit="Watt",
        max_alarm=120.0,
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Per bay TPM powers in Watts.",
    )

    tpmVoltages = attribute_from_signal(
        _tpm_voltages,
        dtype=("DevFloat",),
        max_dim_x=SubrackData.TPM_BAY_COUNT,
        label="TPM voltages",
        unit="Volt",
        min_alarm=11.4,
        max_alarm=12.6,
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Per bay TPM voltages in Volts.",
    )

    subrackBoardInfo = attribute_from_signal(
        _subrack_board_info,
        dtype=str,
        label="Subrack Board Info",
        doc="The subrack board information, as a JSON string.",
    )

    # ---------------------------------
    # Attributes for the TPM power states
    # ---------------------------------
    tpm1PowerState = attribute_from_signal(
        _tpm1_power_state,
        dtype=PowerState,
        label="TPM 1 power state",
        doc="The power state of the TPM in bay 1.",
    )

    tpm2PowerState = attribute_from_signal(
        _tpm2_power_state,
        dtype=PowerState,
        label="TPM 2 power state",
        doc="The power state of the TPM in bay 2.",
    )

    tpm3PowerState = attribute_from_signal(
        _tpm3_power_state,
        dtype=PowerState,
        label="TPM 3 power state",
        doc="The power state of the TPM in bay 3.",
    )

    tpm4PowerState = attribute_from_signal(
        _tpm4_power_state,
        dtype=PowerState,
        label="TPM 4 power state",
        doc="The power state of the TPM in bay 4.",
    )

    tpm5PowerState = attribute_from_signal(
        _tpm5_power_state,
        dtype=PowerState,
        label="TPM 5 power state",
        doc="The power state of the TPM in bay 5.",
    )

    tpm6PowerState = attribute_from_signal(
        _tpm6_power_state,
        dtype=PowerState,
        label="TPM 6 power state",
        doc="The power state of the TPM in bay 6.",
    )

    tpm7PowerState = attribute_from_signal(
        _tpm7_power_state,
        dtype=PowerState,
        label="TPM 7 power state",
        doc="The power state of the TPM in bay 7.",
    )

    tpm8PowerState = attribute_from_signal(
        _tpm8_power_state,
        dtype=PowerState,
        label="TPM 8 power state",
        doc="The power state of the TPM in bay 8.",
    )

    # -------------------------------
    # Attributes for the health status
    # -------------------------------
    internalVoltages1V1 = attribute_from_signal(
        _internal_voltages_1v1,
        dtype="DevDouble",
        label="V_1V1",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack internal 1V1 supply voltage in Volts.",
    )

    internalVoltages1V5 = attribute_from_signal(
        _internal_voltages_1v5,
        dtype="DevDouble",
        label="V_1V5",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack internal 1V5 supply voltage in Volts.",
    )

    internalVoltages2V5 = attribute_from_signal(
        _internal_voltages_2v5,
        dtype="DevDouble",
        label="V_2V5",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack internal 2V5 supply voltage in Volts.",
    )

    internalVoltages2V8 = attribute_from_signal(
        _internal_voltages_2v8,
        dtype="DevDouble",
        label="V_2V8",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack internal 2V8 supply voltage in Volts.",
    )

    internalVoltages3V = attribute_from_signal(
        _internal_voltages_3v,
        dtype="DevDouble",
        label="V_3V",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack internal 3V supply voltage in Volts.",
    )

    internalVoltages3V3 = attribute_from_signal(
        _internal_voltages_3v3,
        dtype="DevDouble",
        label="V_3V3",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack internal 3V3 supply voltage in Volts.",
    )

    internalVoltages5V = attribute_from_signal(
        _internal_voltages_5v,
        dtype="DevDouble",
        label="V_5V",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack internal 5V supply voltage in Volts.",
    )

    internalVoltagesARM = attribute_from_signal(
        _internal_voltages_arm,
        dtype="DevDouble",
        label="V_ARM",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack internal ARM supply voltage in Volts.",
    )

    internalVoltagesCORE = attribute_from_signal(
        _internal_voltages_core,
        dtype="DevDouble",
        label="V_CORE",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack internal CORE supply voltage in Volts.",
    )

    internalVoltagesDDR = attribute_from_signal(
        _internal_voltages_ddr,
        dtype="DevDouble",
        label="V_DDR",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack internal DDR supply voltage in Volts.",
    )

    internalVoltagesPOWERIN = attribute_from_signal(
        _internal_voltages_powerin,
        dtype="DevDouble",
        label="V_POWERIN",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack power input voltage in Volts.",
    )

    internalVoltagesSOC = attribute_from_signal(
        _internal_voltages_soc,
        dtype="DevDouble",
        label="V_SOC",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack internal SOC supply voltage in Volts.",
    )

    psu1Present = attribute_from_signal(
        _psu1_present,
        dtype=bool,
        label="Psu1 Present",
        doc="Presence of PSU1.",
    )

    psu2Present = attribute_from_signal(
        _psu2_present,
        dtype=bool,
        label="Psu2 Present",
        doc="Presence of PSU2.",
    )

    psu1PowerIn = attribute_from_signal(
        _psu1_power_in,
        dtype="DevDouble",
        label="PSU1 Input Power",
        unit="Watt",
        max_alarm=600.0,
        max_warning=575.0,
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="PSU1 input power in Watts.",
    )

    psu2PowerIn = attribute_from_signal(
        _psu2_power_in,
        dtype="DevDouble",
        label="PSU2 Input Power",
        unit="Watt",
        max_alarm=600.0,
        max_warning=575.0,
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="PSU2 input power in Watts.",
    )

    psu1PowerOut = attribute_from_signal(
        _psu1_power_out,
        dtype="DevDouble",
        label="PSU1 Output Power",
        unit="Watt",
        max_alarm=1140.0,
        max_warning=600.0,
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="PSU1 output power in Watts.",
    )

    psu2PowerOut = attribute_from_signal(
        _psu2_power_out,
        dtype="DevDouble",
        label="PSU2 Output Power",
        unit="Watt",
        max_alarm=1140.0,
        max_warning=600.0,
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="PSU2 output power in Watts.",
    )

    psu1VoltageIn = attribute_from_signal(
        _psu1_voltage_in,
        dtype="DevDouble",
        label="PSU1 Input Voltage",
        unit="Volt",
        max_alarm=253.00,
        max_warning=240.0,
        min_warning=215.0,
        min_alarm=207.0,
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="PSU1 input voltage in Volts.",
    )

    psu2VoltageIn = attribute_from_signal(
        _psu2_voltage_in,
        dtype="DevDouble",
        label="PSU2 Input Voltage",
        unit="Volt",
        max_alarm=253.00,
        max_warning=240.0,
        min_warning=215.0,
        min_alarm=207.0,
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="PSU2 input voltage in Volts.",
    )

    psu1VoltageOut = attribute_from_signal(
        _psu1_voltage_out,
        dtype="DevDouble",
        label="PSU1 Output Voltage",
        unit="Volt",
        max_alarm=14.0,
        max_warning=13.0,
        min_warning=11.0,
        min_alarm=10.0,
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="PSU1 output voltage in Volts.",
    )

    psu2VoltageOut = attribute_from_signal(
        _psu2_voltage_out,
        dtype="DevDouble",
        label="PSU2 Output Voltage",
        unit="Volt",
        max_alarm=14.0,
        max_warning=13.0,
        min_warning=11.0,
        min_alarm=10.0,
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="PSU2 output voltage in Volts.",
    )

    psuDeadCount = attribute_from_signal(
        _psu_dead_count,
        dtype="DevShort",
        label="Dead PSU Count",
        max_warning=1,
        max_alarm=2,
        abs_change=1,
        archive_abs_change=1,
        doc=(
            "Count of PSUs that are present and receive input voltage but "
            "supply no output voltage."
        ),
    )

    psu1Load = attribute_from_signal(
        _psu1_load,
        dtype="DevDouble",
        label="PSU 1 Load",
        abs_change=0.001,
        archive_abs_change=0.001,
        doc="The load on PSU1, as a fraction of its maximum power.",
    )

    psu2Load = attribute_from_signal(
        _psu2_load,
        dtype="DevDouble",
        label="PSU 2 Load",
        abs_change=0.001,
        archive_abs_change=0.001,
        doc="The load on PSU2, as a fraction of its maximum power.",
    )

    internalVoltagesPOWERINMIN = attribute_from_signal(
        _internal_voltages_powerin_min,
        dtype="DevDouble",
        label="V_POWERIN_MIN",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Lowest input supply voltage since the last poll, in Volts.",
    )

    internalVoltagesPOWERINMAX = attribute_from_signal(
        _internal_voltages_powerin_max,
        dtype="DevDouble",
        label="V_POWERIN_MAX",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Highest input supply voltage since the last poll, in Volts.",
    )

    backplanePowerGood = attribute_from_signal(
        _backplane_power_good,
        dtype=bool,
        label="Backplane power good",
        doc="Whether the backplane reports its power as good.",
    )

    boardApllUnlockCount = attribute_from_signal(
        _board_apll_unlock_count,
        dtype="DevLong",
        label="Board APLL unlock count",
        abs_change=1,
        archive_abs_change=1,
        doc="How many times the board APLL has lost lock.",
    )

    boardDpllUnlockCount = attribute_from_signal(
        _board_dpll_unlock_count,
        dtype="DevLong",
        label="Board DPLL unlock count",
        abs_change=1,
        archive_abs_change=1,
        doc="How many times the board DPLL has lost lock.",
    )

    boardSysclkEventCount = attribute_from_signal(
        _board_sysclk_event_count,
        dtype="DevLong",
        label="Board SYSCLK event count",
        abs_change=1,
        archive_abs_change=1,
        doc="How many SYSCLK events the board has counted.",
    )

    pllSource = attribute_from_signal(
        _pll_source,
        dtype=str,
        label="PLL source",
        doc="The reference that the board PLL locks to.",
    )

    ppsPresent = attribute_from_signal(
        _pps_present,
        dtype=bool,
        label="PPS present",
        doc="Whether the board detects the PPS input.",
    )

    ppsFaultCount = attribute_from_signal(
        _pps_fault_count,
        dtype="DevLong",
        label="PPS fault count",
        abs_change=1,
        archive_abs_change=1,
        doc="How many PPS faults the board has counted since the last poll.",
    )

    ppsPhase = attribute_from_signal(
        _pps_phase,
        dtype="DevDouble",
        label="PPS phase",
        unit="ps",
        abs_change=1,
        archive_abs_change=1,
        doc="Mean PPS phase over the PPS phase window, in picoseconds.",
    )

    ppsPhaseStdev = attribute_from_signal(
        _pps_phase_stdev,
        dtype="DevDouble",
        label="PPS phase standard deviation",
        unit="ps",
        abs_change=1,
        archive_abs_change=1,
        doc=(
            "Standard deviation of the PPS phase over the PPS phase window, in "
            "picoseconds. It is invalid when the window holds one sample."
        ),
    )

    ppsPhaseOutliers = attribute_from_signal(
        _pps_phase_outliers,
        dtype="DevLong",
        label="PPS phase outliers",
        abs_change=1,
        archive_abs_change=1,
        doc="How many PPS phase samples the board counted as outliers.",
    )

    refPresent = attribute_from_signal(
        _ref_present,
        dtype=bool,
        label="REF present",
        doc="Whether the board detects the reference clock input.",
    )

    refFaultCount = attribute_from_signal(
        _ref_fault_count,
        dtype="DevLong",
        label="REF fault count",
        abs_change=1,
        archive_abs_change=1,
        doc=(
            "How many reference clock faults the board has counted since the "
            "last poll."
        ),
    )

    cpldPings = attribute_from_signal(
        _cpld_pings,
        dtype=bool,
        label="CPLD pings",
        doc="Whether the CPLD answers a ping.",
    )

    boardPower = attribute_from_signal(
        _board_power,
        dtype="DevDouble",
        label="Board power",
        unit="Watt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Management board power in Watts.",
    )

    boardMaxPower = attribute_from_signal(
        _board_max_power,
        dtype="DevDouble",
        label="Board max power",
        unit="Watt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Highest management board power since the last poll, in Watts.",
    )

    boardPllTemperature = attribute_from_signal(
        _board_pll_temperature,
        dtype="DevDouble",
        label="Board PLL temperature",
        unit="Celsius",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Management board PLL temperature in degrees Celsius.",
    )

    powerSupplyFanSpeedsRpm = attribute_from_signal(
        _power_supply_fan_speeds_rpm,
        dtype=("DevDouble",),
        max_dim_x=len(_PSUS),
        label="power supply fan speeds",
        unit="rpm",
        abs_change=1,
        archive_abs_change=1,
        doc="Power supply fan speeds in RPM.",
    )

    powerSupplyFetTemperatures = attribute_from_signal(
        _power_supply_fet_temperatures,
        dtype=("DevDouble",),
        max_dim_x=len(_PSUS),
        label="power supply FET temperatures",
        unit="Celsius",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Power supply FET temperatures in degrees Celsius.",
    )

    powerSupplyInletTemperatures = attribute_from_signal(
        _power_supply_inlet_temperatures,
        dtype=("DevDouble",),
        max_dim_x=len(_PSUS),
        label="power supply inlet temperatures",
        unit="Celsius",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Power supply inlet temperatures in degrees Celsius.",
    )

    powerSupplyBusy = attribute_from_signal(
        _power_supply_busy,
        dtype=(bool,),
        max_dim_x=len(_PSUS),
        label="power supply busy",
        doc="Whether each power supply reports that it is busy.",
    )

    powerSupplyOff = attribute_from_signal(
        _power_supply_off,
        dtype=(bool,),
        max_dim_x=len(_PSUS),
        label="power supply off",
        doc="Whether each power supply reports that it is off.",
    )

    powerSupplyPowerGood = attribute_from_signal(
        _power_supply_power_good,
        dtype=(bool,),
        max_dim_x=len(_PSUS),
        label="power supply power good",
        doc="Whether each power supply reports its power as good.",
    )

    powerSupplyCmlFaults = attribute_from_signal(
        _power_supply_cml_faults,
        dtype=(bool,),
        max_dim_x=len(_PSUS),
        label="power supply CML faults",
        doc="Whether each power supply reports a communication, memory or logic fault.",
    )

    powerSupplyFanFaults = attribute_from_signal(
        _power_supply_fan_faults,
        dtype=(bool,),
        max_dim_x=len(_PSUS),
        label="power supply fan faults",
        doc="Whether each power supply reports a fan fault.",
    )

    powerSupplyInputFaults = attribute_from_signal(
        _power_supply_input_faults,
        dtype=(bool,),
        max_dim_x=len(_PSUS),
        label="power supply input faults",
        doc="Whether each power supply reports an input fault.",
    )

    powerSupplyIoutFaults = attribute_from_signal(
        _power_supply_iout_faults,
        dtype=(bool,),
        max_dim_x=len(_PSUS),
        label="power supply output current faults",
        doc="Whether each power supply reports an output current fault.",
    )

    powerSupplyIoutOcFaults = attribute_from_signal(
        _power_supply_iout_oc_faults,
        dtype=(bool,),
        max_dim_x=len(_PSUS),
        label="power supply output overcurrent faults",
        doc="Whether each power supply reports an output overcurrent fault.",
    )

    powerSupplyTempFaults = attribute_from_signal(
        _power_supply_temp_faults,
        dtype=(bool,),
        max_dim_x=len(_PSUS),
        label="power supply temperature faults",
        doc="Whether each power supply reports a temperature fault.",
    )

    powerSupplyVinUvFaults = attribute_from_signal(
        _power_supply_vin_uv_faults,
        dtype=(bool,),
        max_dim_x=len(_PSUS),
        label="power supply input undervoltage faults",
        doc="Whether each power supply reports an input undervoltage fault.",
    )

    powerSupplyVoutFaults = attribute_from_signal(
        _power_supply_vout_faults,
        dtype=(bool,),
        max_dim_x=len(_PSUS),
        label="power supply output voltage faults",
        doc="Whether each power supply reports an output voltage fault.",
    )

    powerSupplyVoutOvFaults = attribute_from_signal(
        _power_supply_vout_ov_faults,
        dtype=(bool,),
        max_dim_x=len(_PSUS),
        label="power supply output overvoltage faults",
        doc="Whether each power supply reports an output overvoltage fault.",
    )

    powerSupplyOtherFaults = attribute_from_signal(
        _power_supply_other_faults,
        dtype=(bool,),
        max_dim_x=len(_PSUS),
        label="power supply other faults",
        doc="Whether each power supply reports a fault of another kind.",
    )

    powerSupplyUnknownFaults = attribute_from_signal(
        _power_supply_unknown_faults,
        dtype=(bool,),
        max_dim_x=len(_PSUS),
        label="power supply unknown faults",
        doc="Whether each power supply reports a fault of an unknown kind.",
    )

    tpmMinVoltages = attribute_from_signal(
        _tpm_min_voltages,
        dtype=("DevDouble",),
        max_dim_x=SubrackData.TPM_BAY_COUNT,
        label="TPM min voltages",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Lowest voltage of each TPM bay since the last poll, in Volts.",
    )

    tpmMaxVoltages = attribute_from_signal(
        _tpm_max_voltages,
        dtype=("DevDouble",),
        max_dim_x=SubrackData.TPM_BAY_COUNT,
        label="TPM max voltages",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Highest voltage of each TPM bay since the last poll, in Volts.",
    )

    tpmMaxPowers = attribute_from_signal(
        _tpm_max_powers,
        dtype=("DevDouble",),
        max_dim_x=SubrackData.TPM_BAY_COUNT,
        label="TPM max powers",
        unit="Watt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Highest power of each TPM bay since the last poll, in Watts.",
    )

    tpmFaults = attribute_from_signal(
        _tpm_faults,
        dtype=(bool,),
        max_dim_x=SubrackData.TPM_BAY_COUNT,
        label="TPM faults",
        doc="Whether each TPM bay reports a fault.",
    )

    tpmPings = attribute_from_signal(
        _tpm_pings,
        dtype=(bool,),
        max_dim_x=SubrackData.TPM_BAY_COUNT,
        label="TPM pings",
        doc="Whether the TPM in each bay answers a ping.",
    )

    tpmSinglewire = attribute_from_signal(
        _tpm_singlewire,
        dtype=(bool,),
        max_dim_x=SubrackData.TPM_BAY_COUNT,
        label="TPM singlewire",
        doc="The singlewire status the board reports for each TPM bay.",
    )

    healthStatus = attribute_from_signal(
        _health_status,
        dtype=str,
        label="Health Status Dictionary",
        doc="Every subrack monitoring point in the health status, as JSON.",
    )

    # ---------------------------------
    # Attribute for the health recorder
    # ---------------------------------
    healthReport = attribute_from_signal(
        _health_report,
        dtype=str,
        label="Health Report",
        doc=(
            "The reasons for the current health, one on each line, or "
            "'Health is OK.'."
        ),
    )
