#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""A file containing subrack api values for each version."""
from __future__ import annotations

import itertools
from typing import Any, Callable, Final, Optional, TypedDict

from .subrack_data import FanMode, SubrackData

# https://github.com/python/typing/issues/182
JsonSerializable = Any


class AttributeMetadataType(TypedDict):
    """Type for attribute metadata dictionary."""

    length: Optional[int]
    default: JsonSerializable
    writable: bool


DEFAULT_ATTRIBUTE_METADATA: Final[dict[str, AttributeMetadataType]] = {
    "tpm_present": {
        "length": SubrackData.TPM_BAY_COUNT,
        "default": [True] + ([False] * (SubrackData.TPM_BAY_COUNT - 1)),
        "writable": False,
    },
    "tpm_on_off": {
        "length": SubrackData.TPM_BAY_COUNT,
        "default": [True] + ([False] * (SubrackData.TPM_BAY_COUNT - 1)),
        "writable": False,
    },
    "backplane_temperatures": {
        "length": 2,
        "default": itertools.cycle([[38.0, 39.0], [38.5, 39.5]]),
        "writable": False,
    },
    "board_temperatures": {
        "length": 2,
        "default": [39.0, 40.0],
        "writable": False,
    },
    "board_current": {
        "length": None,
        "default": 1.1,
        "writable": False,
    },
    "cpld_pll_locked": {
        "length": None,
        "default": False,
        "writable": False,
    },
    "power_supply_fan_speeds": {
        "length": 2,
        "default": [93.0, 94.0],
        "writable": False,
    },
    "power_supply_currents": {
        "length": 2,
        "default": [2.2, 2.4],
        "writable": False,
    },
    "power_supply_voltages": {
        "length": 2,
        "default": [12.0, 12.1],
        "writable": False,
    },
    "subrack_fan_speeds_percent": {
        "length": 4,
        "default": [95.0, 96.0, 97.0, 98.0],
        "writable": False,
    },
    "subrack_fan_speeds": {
        "length": 4,
        "default": [
            0.95 * SubrackData.MAX_SUBRACK_FAN_SPEED,
            0.96 * SubrackData.MAX_SUBRACK_FAN_SPEED,
            0.97 * SubrackData.MAX_SUBRACK_FAN_SPEED,
            0.98 * SubrackData.MAX_SUBRACK_FAN_SPEED,
        ],
        "writable": False,
    },
    "subrack_fan_mode": {
        "length": 4,
        "default": [FanMode.AUTO, FanMode.AUTO, FanMode.AUTO, FanMode.AUTO],
        "writable": False,
    },
    "subrack_pll_locked": {
        "length": None,
        "default": False,
        "writable": False,
    },
    "subrack_timestamp": {
        "length": None,
        "default": 1234567890,
        "writable": False,
    },
    "tpm_currents": {
        "length": 8,
        "default": [0.4] * 8,
        "writable": True,
    },
    # "tpm_temperatures": {  # Not implemented on SMB
    #     "length": 8,
    #     "default": [40.0] * 8,
    #     "writable": False,
    # },
    "tpm_voltages": {
        "length": 8,
        "default": [12.0] * 8,
        "writable": True,
    },
    "board_info": {
        "length": None,
        "default": {
            "SMM": {
                "EXT_LABEL_SN": "",
                "EXT_LABEL_PN": "",
                "SN": "",
                "PN": "SMB",
                "SMB_UPS_SN": "",
                "HARDWARE_REV": "v1.2.4 ",
                "BOARD_MODE": "SUBRACK",
                "bios": "v1.6.0",
                "bios_cpld": "",
                "bios_mcu": "",
                "bios_uboot": "",
                "bios_krn": "",
                "OS": "Debian GNU/Linux 10",
                "OS_rev": "",
                "OS_root": "",
                "BOOT_SEL_KRN": 0,
                "BOOT_SEL_FS": 0,
                "CPLD_ip_address": "",
                "CPLD_netmask": "",
                "CPLD_gateway": "",
                "CPLD_ip_address_eep": "",
                "CPLD_netmask_eep": "",
                "CPLD_gateway_eep": "",
                "CPLD_MAC": "",
                "CPU_ip_address": "",
                "CPU_netmask": "",
                "CPU_MAC": "",
            },
            "SUBRACK": {
                "EXT_LABEL": "",
                "SN": "",
                "PN": "BACKPLANE",
                "HARDWARE_REV": "v1.2.2",
                "CPLD_ip_address_eep": "",
                "CPLD_netmask_eep": "",
                "CPLD_gateway_eep": "",
            },
            "PSM": {"EXT_LABEL": "", "SN": "", "PN": "", "HARDWARE_REV": ""},
        },
        "writable": False,
    },
}

DEFAULT_COMMANDS: Final = (
    "abort_command",
    "command_completed",
    "get_health_status",
    "list_commands",
    "set_fan_mode",
    "set_power_supply_fan_speed",
    "set_subrack_fan_speed",
    "turn_off_tpm",
    "turn_off_tpms",
    "turn_on_tpm",
    "turn_on_tpms",
)


def default_health_status(
    psu_currents: list[float], psu_voltages: list[float]
) -> dict[str, Any]:
    """
    Return the health status reported by the subrack.

    :param psu_currents: the current power supply currents.
    :param psu_voltages: the current power supply voltages.

    :return: the health status dictionary.
    """
    psu_powers = [
        current * voltage for current, voltage in zip(psu_currents, psu_voltages)
    ]

    return {
        "temperatures": {
            "SMM1": 40,
            "SMM2": 41,
            "BKPLN1": 39,
            "BKPLN2": 41,
        },
        "plls": {
            "BoardPllLock": True,
            "CPLDPllLock": True,
            "PllSource": None,
        },
        "psus": {
            "present": {
                "PSU1": True,
                "PSU2": True,
            },
            "busy": {
                "PSU1": None,
                "PSU2": None,
            },
            "off": {
                "PSU1": False,
                "PSU2": False,
            },
            "vout_ov_fault": {
                "PSU1": False,
                "PSU2": False,
            },
            "iout_oc_fault": {
                "PSU1": False,
                "PSU2": False,
            },
            "vin_uv_fault": {
                "PSU1": False,
                "PSU2": False,
            },
            "temp_fault": {
                "PSU1": False,
                "PSU2": False,
            },
            "cml_fault": {
                "PSU1": False,
                "PSU2": False,
            },
            "vout_fault": {
                "PSU1": False,
                "PSU2": False,
            },
            "iout_fault": {
                "PSU1": False,
                "PSU2": False,
            },
            "input_fault": {
                "PSU1": False,
                "PSU2": False,
            },
            "pwr_gd": {
                "PSU1": True,
                "PSU2": True,
            },
            "fan_fault": {
                "PSU1": False,
                "PSU2": False,
            },
            "other": {
                "PSU1": False,
                "PSU2": False,
            },
            "unknown": {
                "PSU1": False,
                "PSU2": False,
            },
            "voltage_out": {
                "PSU1": psu_voltages[0],
                "PSU2": psu_voltages[1],
            },
            "power_out": {
                "PSU1": psu_powers[0],
                "PSU2": psu_powers[1],
            },
            "voltage_in": {
                "PSU1": 230,
                "PSU2": 230,
            },
            "power_in": {
                "PSU1": 300,
                "PSU2": 300,
            },
            "fan_speed": {
                "PSU1": 90.0,
                "PSU2": 100.0,
            },
            "temp_inlet": {
                "PSU1": 20,
                "PSU2": 21,
            },
            "temp_fet": {
                "PSU1": 30,
                "PSU2": 31,
            },
        },
        "pings": {
            "pings_CPLD": True,
        },
        "slots": {
            "presence": {
                "SLOT1": False,
                "SLOT2": True,
                "SLOT3": False,
                "SLOT4": False,
                "SLOT5": True,
                "SLOT6": False,
                "SLOT7": False,
                "SLOT8": False,
            },
            "on": {
                "SLOT1": False,
                "SLOT2": False,
                "SLOT3": False,
                "SLOT4": False,
                "SLOT5": False,
                "SLOT6": False,
                "SLOT7": False,
                "SLOT8": False,
            },
            "voltages": {
                "SLOT1": 12.0,
                "SLOT2": 12.0,
                "SLOT3": 12.0,
                "SLOT4": 12.0,
                "SLOT5": 12.0,
                "SLOT6": 12.0,
                "SLOT7": 12.0,
                "SLOT8": 12.0,
            },
            "powers": {
                "SLOT1": 0.4 * 12.0,
                "SLOT2": 0.4 * 12.0,
                "SLOT3": 0.4 * 12.0,
                "SLOT4": 0.4 * 12.0,
                "SLOT5": 0.4 * 12.0,
                "SLOT6": 0.4 * 12.0,
                "SLOT7": 0.4 * 12.0,
                "SLOT8": 0.4 * 12.0,
            },
            "pings": {
                "SLOT1": True,
                "SLOT2": True,
                "SLOT3": True,
                "SLOT4": True,
                "SLOT5": True,
                "SLOT6": True,
                "SLOT7": True,
                "SLOT8": True,
            },
        },
        "internal_voltages": {
            "V_POWERIN": 12.0,
            "V_SOC": 1.35,
            "V_ARM": 1.35,
            "V_DDR": 1.35,
            "V_2V5": 2.5,
            "V_1V1": 1.1,
            "V_CORE": 1.2,
            "V_1V5": 1.5,
            "V_3V3": 3.3,
            "V_5V": 5.0,
            "V_3V": 3.0,
            "V_2V8": 2.8,
        },
        "fans": {
            "speed": {
                "FAN1": 1,
                "FAN2": 1,
                "FAN3": 1,
                "FAN4": 1,
            },
            "pwm_duty": {
                "FAN1": 95,
                "FAN2": 96,
                "FAN3": 97,
                "FAN4": 98,
            },
            "mode": {
                "FAN1": FanMode.AUTO,
                "FAN2": FanMode.AUTO,
                "FAN3": FanMode.AUTO,
                "FAN4": FanMode.AUTO,
            },
        },
    }


SUPPORTED_API_VERSIONS: Final = ("1.6.0", "1.8.0")

ATTRIBUTE_METADATA: Final[dict[str, dict[str, AttributeMetadataType]]] = {
    "1.6.0": DEFAULT_ATTRIBUTE_METADATA,
    "1.8.0": {
        name: metadata
        for name, metadata in DEFAULT_ATTRIBUTE_METADATA.items()
        if name not in ["tpm_currents"]
    },
}

COMMANDS: Final[dict[str, tuple[str, ...]]] = {
    "1.6.0": DEFAULT_COMMANDS,
    "1.8.0": tuple(
        command
        for command in DEFAULT_COMMANDS
        if command not in ["set_power_supply_fan_speed"]
    ),
}

HEALTH_STATUS: Final[
    dict[str, Callable[[list[float], list[float]], dict[str, Any]]]
] = {
    "1.6.0": default_health_status,
    "1.8.0": default_health_status,
}
