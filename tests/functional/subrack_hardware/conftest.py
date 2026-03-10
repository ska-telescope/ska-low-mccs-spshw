# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains pytest-specific test harness for SPSHW functional tests."""
import _pytest
import pytest
from ska_low_mccs_common.component import WebHardwareClient


def pytest_addoption(
    parser: _pytest.config.argparsing.Parser,  # type: ignore[name-defined]
) -> None:
    """
    Read command line options.

    :param parser: pytest fixture
    """
    parser.addoption(
        "--test-context",
        action="store",
        default="minikube-ci",
        help="deployment context in which the test is ran",
    )


@pytest.fixture(name="subrack_id")
def subrack_id_fixture(request: pytest.FixtureRequest) -> str:
    """
    Return the correct subrack id.

    :param request: pytest fixture
    :return: a string id used for subrack values.
    """
    return request.config.getoption("--test-context")


@pytest.fixture(name="base_ip")
def base_ip_fixture(subrack_id: str) -> str:
    """
    Return the truncated start of the ip address.

    Currently this fixture uses placeholder values.

    :param subrack_id: which subrack is tested
    :return: the start of the ip address.
    """
    return {
        "ral_1": "127.0.0",
        "ral_2": "127.0.0",
        "ral_3": "127.0.0",
        "ral_4": "127.0.0",
        "ral_5": "127.0.0",
        "minikube-ci": "0.0.0",
    }[subrack_id]


@pytest.fixture(name="subrack_ip")
def subrack_ip_fixture(subrack_id: str, base_ip: str) -> str:
    """
    Fixture for the ip address of the subrack.

    TODO: get this from environment. Place holder values
    :param subrack_id: subrack id
    :param base_ip: truncated start of the ip
    :returns: correct ip address of the subrack
    """
    return {
        "ral_1": f"{base_ip}.14",
        "ral_2": f"{base_ip}.34",
        "ral_3": f"{base_ip}.54",
        "ral_4": f"{base_ip}.74",
        "ral_5": f"{base_ip}.94",
        "minikube-ci": f"{base_ip}.0",
    }[subrack_id]


@pytest.fixture(name="subrack_port")
def subrack_port_fixture(subrack_id: str) -> int:
    """
    Fixture for subrack port.

    :param subrack_id: subrack id
    :return: correct communication port for the subrack
    """
    return {
        "ral_1": 8081,
        "ral_2": 8081,
        "ral_3": 8081,
        "ral_4": 8081,
        "ral_5": 8081,
        "minikube-ci": 8081,
    }[subrack_id]


@pytest.fixture(name="fan_count")
def fan_count_fixture(subrack_id: str) -> int:
    """
    Fixture for the number of fans.

    :param subrack_id: subrack id
    :return: number of fans
    """
    return {
        "ral_1": 4,
        "ral_2": 4,
        "ral_3": 4,
        "ral_4": 4,
        "ral_5": 4,
        "minikube-ci": 4,
    }[subrack_id]


@pytest.fixture(name="tpm_count")
def tpm_count_fixture(subrack_id: str) -> int:
    """
    Fixture for the number of tpms.

    :param subrack_id: subrack id
    :return: number of tpms
    """
    return {
        "ral_1": 8,
        "ral_2": 8,
        "ral_3": 8,
        "ral_4": 8,
        "ral_5": 2,
        "minikube-ci": 8,
    }[subrack_id]


@pytest.fixture(name="psus_count")
def psu_count_fixture(subrack_id: str) -> int:
    """
    Fixture for the number of power supplies.

    :param subrack_id: subrack id
    :return: number of power supplies
    """
    return {
        "ral_1": 2,
        "ral_2": 2,
        "ral_3": 2,
        "ral_4": 2,
        "ral_5": 2,
        "minikube-ci": 2,
    }[subrack_id]


@pytest.fixture(name="internal_voltage")
def internal_voltage_fixture() -> dict:
    """
    Return the internal voltage limits.

    :return: dictionary containing the internal voltages as key-value pairs.
        Note: the key is meant to match the key from health status and the key
        is a tuple contain the low and high limits for the accepted range
    """
    return {
        "V_1V1": (1.07, 1.13),
        "V_1V5": (1.46, 1.54),
        "V_2V5": (2.38, 2.62),
        "V_2V8": (2.66, 2.94),
        "V_3V": (2.85, 3.15),
        "V_3V3": (3.13, 3.46),
        "V_5V": (4.75, 5.25),
        "V_ARM": (1.28, 1.42),
        "V_CORE": (1.16, 1.24),
        "V_DDR": (1.31, 19),
        "V_POWERIN": (11.40, 12.60),
        "V_SOC": (1.31, 1.39),
    }


@pytest.fixture(name="tpm_ips")
def tpm_ips_fixture(base_ip: str, subrack_id: str, tpm_count: int) -> list:
    """
    Fixture for the tpm ip addresses.

    :param subrack_id: subrack id
    :param base_ip: truncated start of the ip
    :param tpm_count: number of tpms

    :return: a list of available tpm ips.
    """
    sub_ip = {
        "ral_1": "2",
        "ral_2": "4",
        "ral_3": "6",
        "ral_4": "8",
        "ral_5": "10",
        "minikube-ci": "2",
    }[subrack_id]
    return [f"{base_ip}.{sub_ip}" + str(x + 1) for x in range(tpm_count)]


@pytest.fixture(name="smm")
def smm_fixture() -> dict:
    """
    Return the subrack motherboard monitoring points.

    :return: dictionary with the expected values as key-value pairs.
        Note: the key is meant to match the key from health status.
    """
    return {
        "power": None,
        "power_max": None,
    }


@pytest.fixture(name="psus")
def psus_fixture(psus_count: int) -> dict:
    """
    Return the expected values for the power supply monitoring points.

    :param psus_count: number of power supplies

    :return: a dictionary with monitoring points as key-value pairs.
        Note: the key is meant to match the key from health status and the value
        is either a tuple contain the low and high limits for the accepted range
        or the exact expected value.
    """
    return {
        key: {f"PSU{x+1}": value for x in range(psus_count)}
        for key, value in {
            "fan_speed": (5000, 10000),
            "power_in": (450, 600),
            "power_out": (450, 600),
            "busy": False,
            "cml_fault": False,
            "fan_fault": False,
            "input_fault": False,
            "iout_fault": False,
            "iout_oc_fault": False,
            "off": False,
            "other": False,
            "present": True,
            "pwr_gd": True,
            "temp_fault": False,
            "temp_fet": (15, 40),
            "temp_inlet": (15, 45),
            "unknown": False,
            "vin_uv_fault": False,
            "voltage_in": (220, 240),
            "voltage_out": (11.4, 12.6),
            "vout_fault": False,
            "vout_ov_fault": False,
            "currents": (0, 50),
        }.items()
    }


@pytest.fixture(name="tpms")
def tpms_fixture(tpm_count: int) -> dict:
    """
    Return the expected values for the tpm monitoring points.

    :param tpm_count: number of tpms

    :return: a dictionary with monitoring points as key-value pairs.
        Note: the key is meant to match the key from health status and the value
        is either a tuple contain the low and high limits for the accepted range
        or the exact expected value.
    """
    return {
        key: {f"SLOT{x+1}": value for x in range(tpm_count)}
        for key, value in {
            "on": True,
            "pings": True,
            "powers": (0, 120),
            "presence": True,
            "singlewire": True,
            "voltages": (11.4, 12.6),
            "currents": (0, 10),
            "supply_fault": False,
        }.items()
    }


@pytest.fixture(name="expected_health_status")
def expected_health_status_fixture(
    fan_count: int, internal_voltage: dict, smm: dict, psus: dict, tpms: dict
) -> dict:
    """
    Return the expected values of the health status.

    :param fan_count: number of fans
    :param internal_voltage: internal_voltage values
    :param smm: smm values
    :param psus: power supply values
    :param tpms: tpm values

    :return: a dictionary matching the structure of the response of the health status
        command.
    """
    return {
        "SMM": smm,
        "fans": {
            "mode": {f"FAN{i+1}": 1 for i in range(fan_count)},
            "pwm_duty": {f"FAN{i+1}": (0, 100) for i in range(fan_count)},
            "speed": {f"FAN{i+1}": (4000, 10_000) for i in range(fan_count)},
        },
        "internal_voltages": internal_voltage,
        "iso_datetime": "2026-02",
        "pings": {
            "pings_CPLD": True,
        },
        "plls": {
            "BoardPllLock": True,
            "CPLDPllLock": True,
            "DefaultPllSource": "external",
            "PllSource": "external",
        },
        "psus": psus,
        "slots": tpms,
        # "system": {}, # System values require a different test method
        "temperatures": {
            "BKPLN1": (10, 50),
            "BKPLN2": (10, 50),
            "SMM1": (10, 50),
            "SMM2": (10, 50),
            "SMM_PLL": (10, 50),
        },
    }


@pytest.fixture(name="subrack_client")
def subrack_interface_fixture(subrack_ip: str, subrack_port: int) -> WebHardwareClient:
    """
    Subrack client to facilitate communication.

    :param subrack_ip: ip address
    :param subrack_port: port
    :return: A WebHardwareClient for subrack communication
    """
    client = WebHardwareClient(subrack_ip, subrack_port)
    return client
