# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
Shared constants and data for the prototype SPS subrack device.

This module holds the pure data (exception classes, attribute maps, timing
constants and JSON command schemas) used by the prototype subrack device and its
attribute/command mixins. It deliberately imports nothing from the rest of the
package so that it can be imported freely without risking an import cycle.
"""

from __future__ import annotations

import importlib.resources
import json
from typing import Final


class HttpError(Exception):
    """Exception class for HttpErrors."""


class RequestError(Exception):
    """Exception class for RequestExceptions."""


# The names of the SMB attributes that are batch-read every ``UpdateRate``.
BATCH_ATTRIBUTES: Final = (
    "tpm_present",
    "tpm_on_off",
    "backplane_temperatures",
    "board_temperatures",
    "board_current",
    "cpld_pll_locked",
    "power_supply_currents",
    "power_supply_fan_speeds",
    "power_supply_powers",
    "power_supply_voltages",
    "subrack_fan_speeds",
    "subrack_fan_speeds_percent",
    "subrack_fan_mode",
    "subrack_pll_locked",
    "subrack_timestamp",
    "tpm_currents",
    "tpm_powers",
    "tpm_voltages",
    "board_info",
)

# Maps each signal-backed internalVoltages attribute name to its signal name.
HEALTH_SIGNAL_MAP: dict[str, str] = {
    "internalVoltages1V1": "internal_voltages_1v1_signal",
    "internalVoltages1V5": "internal_voltages_1v5_signal",
    "internalVoltages2V5": "internal_voltages_2v5_signal",
    "internalVoltages2V8": "internal_voltages_2v8_signal",
    "internalVoltages3V": "internal_voltages_3v_signal",
    "internalVoltages3V3": "internal_voltages_3v3_signal",
    "internalVoltages5V": "internal_voltages_5v_signal",
    "internalVoltagesARM": "internal_voltages_arm_signal",
    "internalVoltagesCORE": "internal_voltages_core_signal",
    "internalVoltagesDDR": "internal_voltages_ddr_signal",
    "internalVoltagesPOWERIN": "internal_voltages_powerin_signal",
    "internalVoltagesSOC": "internal_voltages_soc_signal",
}

# A map from the hardware read key to the name of the Tango attribute.
# This only includes one-to-one mappings. It lets us boilerplate these cases.
# Attributes that don't map one-to-one are handled individually.
# For example, tpm_on_off is not included here because it unpacks into eight
# Tango attributes of the form tpm{N}PowerState.
ATTRIBUTE_MAP = {
    "backplane_temperatures": "backplaneTemperatures",
    "board_temperatures": "boardTemperatures",
    "board_current": "boardCurrent",
    "cpld_pll_locked": "cpldPllLocked",
    "power_supply_currents": "powerSupplyCurrents",
    "power_supply_powers": "powerSupplyPowers",
    "power_supply_voltages": "powerSupplyVoltages",
    "power_supply_fan_speeds": "powerSupplyFanSpeeds",
    "subrack_fan_speeds": "subrackFanSpeeds",
    "subrack_fan_speeds_percent": "subrackFanSpeedsPercent",
    "subrack_fan_mode": "subrackFanModes",
    "subrack_pll_locked": "subrackPllLocked",
    "subrack_timestamp": "subrackTimestamp",
    "tpm_currents": "tpmCurrents",
    "pdu_health": "pduHealth",
    "pdu_model": "pduModel",
    "pdu_port_states": "pduPortStates",
    "pdu_port_currents": "pduPortCurrents",
    "pdu_port_voltages": "pduPortVoltages",
    "tpm_powers": "tpmPowers",
    "tpm_voltages": "tpmVoltages",
    "board_info": "subrackBoardInfo",
}

# Used for mapping tango attributes to the corresponding value in the
# health_status dictionary that is polled from the subrack.
HEALTH_STATUS_MAP = {
    "internalVoltagesPOWERIN": ["internal_voltages", "V_POWERIN"],
    "internalVoltagesSOC": ["internal_voltages", "V_SOC"],
    "internalVoltagesARM": ["internal_voltages", "V_ARM"],
    "internalVoltagesDDR": ["internal_voltages", "V_DDR"],
    "internalVoltages2V5": ["internal_voltages", "V_2V5"],
    "internalVoltages1V1": ["internal_voltages", "V_1V1"],
    "internalVoltagesCORE": ["internal_voltages", "V_CORE"],
    "internalVoltages1V5": ["internal_voltages", "V_1V5"],
    "internalVoltages3V3": ["internal_voltages", "V_3V3"],
    "internalVoltages5V": ["internal_voltages", "V_5V"],
    "internalVoltages3V": ["internal_voltages", "V_3V"],
    "internalVoltages2V8": ["internal_voltages", "V_2V8"],
}

# The Tango attributes whose values come from the batched hardware read and
# which are refreshed via ``read_attr_hardware`` and emitted by Tango's own
# attribute-polling thread (change/archive events with detection enabled).
# The PDU attributes are deliberately excluded: they are read live from the
# PDU device proxy on demand.
POLLED_ATTRIBUTES: Final = (
    "tpmPresent",
    "tpmCount",
    "tpm1PowerState",
    "tpm2PowerState",
    "tpm3PowerState",
    "tpm4PowerState",
    "tpm5PowerState",
    "tpm6PowerState",
    "tpm7PowerState",
    "tpm8PowerState",
    "backplaneTemperatures",
    "boardTemperatures",
    "boardCurrent",
    "cpldPllLocked",
    "powerSupplyCurrents",
    "powerSupplyFanSpeeds",
    "powerSupplyPowers",
    "powerSupplyVoltages",
    "subrackFanSpeeds",
    "subrackFanSpeedsPercent",
    "subrackFanModes",
    "subrackPllLocked",
    "subrackTimestamp",
    "tpmCurrents",
    "tpmPowers",
    "tpmVoltages",
    "subrackBoardInfo",
)

# The Tango attribute names whose values are sourced from a hardware read (the
# batched attribute poll plus the health-status poll, which feeds the
# ``internalVoltages*`` signal attributes and ``healthStatus``). A read of any of
# these is what should trigger ``read_attr_hardware`` to refresh the cache; reads
# of purely-derived attributes (``healthState``, ``state``, ``adminMode``, the
# ``lrc*`` attributes, the live-proxied ``pdu*`` attributes, etc.) must NOT.
HW_BACKED_ATTRIBUTES: Final = (
    frozenset(POLLED_ATTRIBUTES) | frozenset(HEALTH_SIGNAL_MAP) | {"healthStatus"}
)

# The Tango attributes whose values come from the health-status poll rather
# than the batched attribute poll (``BATCH_ATTRIBUTES``).
HEALTH_BACKED_ATTRIBUTES: Final = frozenset(HEALTH_SIGNAL_MAP) | {"healthStatus"}

# Maps each ``BATCH_ATTRIBUTES``-backed Tango attribute name back to the
# hardware read key needed to refresh it, i.e. the reverse of ``ATTRIBUTE_MAP``
# (restricted to the polled, hardware-batch-sourced attributes; this excludes
# the live-proxied ``pdu*`` entries in ``ATTRIBUTE_MAP``) plus the attributes
# that don't map one-to-one: ``tpmPresent``/``tpmCount`` both come from
# ``tpm_present``, and every ``tpm{N}PowerState`` comes from ``tpm_on_off``.
# Used to resolve a ``read_attr_hardware`` attr_list down to just the hardware
# keys that actually need fetching.
HW_KEY_FOR_ATTRIBUTE: Final[dict[str, str]] = {
    **{name: key for key, name in ATTRIBUTE_MAP.items() if name in POLLED_ATTRIBUTES},
    "tpmPresent": "tpm_present",
    "tpmCount": "tpm_present",
    **{
        name: "tpm_on_off"
        for name in POLLED_ATTRIBUTES
        if name.startswith("tpm") and name.endswith("PowerState")
    },
}

# How often, in seconds, an in-progress asynchronous SMB command is polled
# for completion via the ``command_completed`` command.
COMMAND_POLL_INTERVAL: Final = 0.5
# Upper bound, in seconds, on how long we wait for an asynchronous SMB
# command to complete before giving up.
COMMAND_TIMEOUT: Final = 60.0

SetSubrackFanMode_SCHEMA: Final = json.loads(
    importlib.resources.read_text(
        "ska_low_mccs_spshw.schemas.subrack",
        "MccsSubrack_SetSubrackFanMode.json",
    )
)

SetPowerSupplyFanSpeed_SCHEMA: Final = json.loads(
    importlib.resources.read_text(
        "ska_low_mccs_spshw.schemas.subrack",
        "MccsSubrack_SetPowerSupplyFanSpeed.json",
    )
)

SetSubrackFanSpeed_SCHEMA: Final = json.loads(
    importlib.resources.read_text(
        "ska_low_mccs_spshw.schemas.subrack",
        "MccsSubrack_SetSubrackFanSpeed.json",
    )
)
