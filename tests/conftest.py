# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
This module contains pytest fixtures other test setups.

These are common to all ska-low-mccs tests: unit, integration and
functional (BDD).
"""
from __future__ import annotations

import enum
import logging
import os
from typing import Any

import pytest
import tango
from _pytest.python_api import ApproxBase

from tests.harness import get_bandpass_daq_name, get_lmc_daq_name

TPM_BAY_COUNT = 8
MAX_SUBRACK_FAN_SPEED = 8000.0


# TODO: [MCCS-1328] We don't want to import anything from ska-low-mccs-spshw here,
# but we need to know the meaning of 1 and 2 in the context of fan modes,
# so that the tests know how to drive the device. So for now we redefine it.
# The necessity of importing or redefining this is a code smell.
# We should change the SubrackDevice's interface to use string fan modes.
# e.g. subrack.SetSubrackFanMode("{'fan_id': 1, 'mode'; 'auto'}")
# which would be much more readable and self-describing.
class FanMode(enum.IntEnum):  # type: ignore[no-redef]
    """Redefinition of FanMode."""

    MANUAL = 0
    AUTO = 1


@pytest.fixture(name="db_temperature_thresholds", scope="module")
def db_temperature_thresholds_fixture() -> dict[str, tango.StdStringVector]:
    """
    Return a dictionary containing the db values.

    :returns: a dictionary containing the db values.
    """
    return {}


@pytest.fixture(name="db_voltage_thresholds", scope="module")
def db_voltage_thresholds_fixture() -> dict[str, tango.StdStringVector]:
    """
    Return a dictionary containing the db values.

    :returns: a dictionary containing the db values.
    """
    return {}


@pytest.fixture(name="db_current_thresholds", scope="module")
def db_current_thresholds_fixture() -> dict[str, tango.StdStringVector]:
    """
    Return a dictionary containing the db values.

    :returns: a dictionary containing the db values.
    """
    return {}


def pytest_sessionstart(session: pytest.Session) -> None:
    """
    Pytest hook; prints info about tango version.

    :param session: a pytest Session object
    """
    print(tango.utils.info())


@pytest.fixture(scope="session", name="logger")
def logger_fixture() -> logging.Logger:
    """
    Fixture that returns a default logger.

    :return: a logger
    """
    debug_logger = logging.getLogger()
    debug_logger.setLevel(logging.DEBUG)
    return debug_logger


@pytest.fixture(name="subrack_simulator_config", scope="session")
def subrack_simulator_config_fixture() -> dict[str, Any]:
    """
    Return attribute values with which the subrack simulator is configured.

    :return: a key-value dictionary of attribute values with which the
        subrack simulator is configured.
    """
    return {
        "tpm_present": [False, True, False, False, True, False, False, False],
        "tpm_on_off": [False, False, False, False, False, False, False, False],
        "backplane_temperatures": [39.0, 40.0],
        "board_temperatures": [40.0, 41.0],
        "board_current": 1.1,
        "cpld_pll_locked": True,
        "power_supply_currents": [4.2, 5.8],
        "power_supply_fan_speeds": [90.0, 100.0],
        "power_supply_voltages": [12.0, 12.1],
        "subrack_fan_speeds_percent": [95.0, 96.0, 97.0, 98.0],
        "subrack_fan_mode": [FanMode.AUTO, FanMode.AUTO, FanMode.AUTO, FanMode.AUTO],
        "subrack_pll_locked": True,
        "subrack_timestamp": 1234567890,
        "tpm_currents": [0.4] * 8,
        # "tpm_temperatures": [40.0] * 8,  # Not implemented on SMB
        "tpm_voltages": [12.0] * 8,
        "board_info": {
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
    }


@pytest.fixture(name="health_status", scope="session")
def health_status_fixture() -> dict[str, Any]:
    """
    Return attribute values with which the subrack simulator is configured.

    :return: a key-value dictionary of attribute values with which the
        subrack simulator is configured.
    """
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
                "PSU1": 12.0,
                "PSU2": 12.1,
            },
            "power_out": {
                "PSU1": 4.2 * 12,
                "PSU2": 5.8 * 12.1,
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


@pytest.fixture(name="subrack_simulator_attribute_values", scope="session")
def subrack_simulator_attribute_values_fixture(
    subrack_simulator_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Return attribute values that the subrack simulator is expected to report.

    :param subrack_simulator_config: attribute values with which the
        subrack simulator is configured.

    :return: a key-value dictionary of attribute values that the subrack
        simulator is expected to report.
    """

    def _approxify(list_of_floats: list[float]) -> list[ApproxBase]:
        return [pytest.approx(element) for element in list_of_floats]

    return {
        "tpm_present": subrack_simulator_config["tpm_present"],
        "tpm_on_off": subrack_simulator_config["tpm_on_off"],
        "backplane_temperatures": _approxify(
            subrack_simulator_config["backplane_temperatures"]
        ),
        "board_temperatures": _approxify(
            subrack_simulator_config["board_temperatures"]
        ),
        "board_current": pytest.approx(subrack_simulator_config["board_current"]),
        "cpld_pll_locked": subrack_simulator_config["cpld_pll_locked"],
        "power_supply_currents": _approxify(
            subrack_simulator_config["power_supply_currents"]
        ),
        "power_supply_fan_speeds": _approxify(
            subrack_simulator_config["power_supply_fan_speeds"]
        ),
        "power_supply_voltages": _approxify(
            subrack_simulator_config["power_supply_voltages"]
        ),
        "power_supply_powers": [
            pytest.approx(c * v)
            for c, v in zip(
                subrack_simulator_config["power_supply_currents"],
                subrack_simulator_config["power_supply_voltages"],
            )
        ],
        "subrack_fan_speeds_percent": _approxify(
            subrack_simulator_config["subrack_fan_speeds_percent"]
        ),
        "subrack_fan_speeds": [
            pytest.approx(p * MAX_SUBRACK_FAN_SPEED / 100.0)
            for p in subrack_simulator_config["subrack_fan_speeds_percent"]
        ],
        "subrack_fan_mode": subrack_simulator_config["subrack_fan_mode"],
        "subrack_pll_locked": subrack_simulator_config["subrack_pll_locked"],
        "subrack_timestamp": subrack_simulator_config["subrack_timestamp"],
        "tpm_currents": _approxify(subrack_simulator_config["tpm_currents"]),
        # Not implemented on SMB
        # "tpm_temperatures": _approxify(subrack_simulator_config["tpm_temperatures"]),
        "tpm_voltages": _approxify(subrack_simulator_config["tpm_voltages"]),
        "tpm_powers": [
            pytest.approx(c * v)
            for c, v in zip(
                subrack_simulator_config["tpm_currents"],
                subrack_simulator_config["tpm_voltages"],
            )
        ],
        "board_info": {
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
    }


@pytest.fixture(name="subrack_device_attribute_values", scope="session")
def subrack_device_attribute_values_fixture(
    subrack_simulator_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Return attribute values that the subrack device is expected to report.

    :param subrack_simulator_config: attribute values with which the
        subrack simulator is configured.

    :return: a key-value dictionary of attribute values that the subrack
        device is expected to report.
    """

    def _approxify(list_of_floats: list[float]) -> list[ApproxBase]:
        return [pytest.approx(element) for element in list_of_floats]

    return {
        "tpmPresent": subrack_simulator_config["tpm_present"],
        "tpmOnOff": subrack_simulator_config["tpm_on_off"],
        "backplaneTemperatures": _approxify(
            subrack_simulator_config["backplane_temperatures"]
        ),
        "boardTemperatures": _approxify(subrack_simulator_config["board_temperatures"]),
        "boardCurrent": [pytest.approx(subrack_simulator_config["board_current"])],
        "cpldPllLocked": subrack_simulator_config["cpld_pll_locked"],
        "powerSupplyCurrents": _approxify(
            subrack_simulator_config["power_supply_currents"]
        ),
        "powerSupplyFanSpeeds": _approxify(
            subrack_simulator_config["power_supply_fan_speeds"]
        ),
        "powerSupplyVoltages": _approxify(
            subrack_simulator_config["power_supply_voltages"]
        ),
        "powerSupplyPowers": [
            pytest.approx(c * v)
            for c, v in zip(
                subrack_simulator_config["power_supply_currents"],
                subrack_simulator_config["power_supply_voltages"],
            )
        ],
        "subrackFanSpeedsPercent": _approxify(
            subrack_simulator_config["subrack_fan_speeds_percent"]
        ),
        "subrackFanSpeeds": [
            pytest.approx(p * MAX_SUBRACK_FAN_SPEED / 100.0)
            for p in subrack_simulator_config["subrack_fan_speeds_percent"]
        ],
        "subrackFanModes": subrack_simulator_config["subrack_fan_mode"],
        "subrackPllLocked": subrack_simulator_config["subrack_pll_locked"],
        "subrackTimestamp": subrack_simulator_config["subrack_timestamp"],
        "tpmCurrents": _approxify(subrack_simulator_config["tpm_currents"]),
        # Not implemented on SMB
        # "tpmTemperatures": _approxify(subrack_simulator_config["tpm_temperatures"]),
        "tpmVoltages": _approxify(subrack_simulator_config["tpm_voltages"]),
        "tpmPowers": [
            pytest.approx(c * v)
            for c, v in zip(
                subrack_simulator_config["tpm_currents"],
                subrack_simulator_config["tpm_voltages"],
            )
        ],
        "subrackBoardInfo": "v1.6.0",
    }


@pytest.fixture(name="subrack_id", scope="session")
def subrack_id_fixture() -> int:
    """
    Return the id of the subrack under test.

    :return: the id of the subrack under test.
    """
    if os.getenv("STATION_LABEL") == "stfc-ral-2":
        # This is not the most elegant solution,
        # but, it is a single place we need to change.
        return 2
    return 1


@pytest.fixture(name="tile_id", scope="session")
def tile_id_fixture() -> int:
    """
    Return the id of the tile under test.

    :return: the id of the tile under test.
    """
    return 1


@pytest.fixture(name="station_id", scope="session")
def station_id_fixture() -> int:
    """
    Return the id of the station to which tile under test belongs.

    :return: the id of the station to which tile under test belongs.
    """
    return 1


@pytest.fixture(name="daq_id", scope="session")
def daq_id_fixture() -> int:
    """
    Return the daq id of this daq receiver.

    :return: the daq id of this daq receiver.
    """
    return 1


@pytest.fixture(name="lmc_daq_trl")
def lmc_daq_trl_fixture() -> str:
    """
    Return a DAQ TRL for testing purposes.

    :returns: A DAQ TRL.
    """
    return get_lmc_daq_name()


@pytest.fixture(name="bandpass_daq_trl")
def bandpass_daq_trl_fixture() -> str:
    """
    Return a DAQ TRL for testing purposes.

    :returns: A DAQ TRL.
    """
    return get_bandpass_daq_name()
