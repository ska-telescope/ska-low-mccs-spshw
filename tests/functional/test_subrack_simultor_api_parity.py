# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
Tests of the subrack web API.

These tests check the responses of a subrack web API against what the
API is expected to provide. They do not know whether they are talking to
a real subrack or to the subrack simulator, so they can be used to check
that the simulator behaves like the API.

They are deselected unless given a target::

    pytest tests/functional/test_subrack_simultor_api_parity.py \
        --subrack-api=HOST:PORT

The tests choose their expectations from the subrack's SMM BIOS version,
in its ``board_info`` attribute. ``--subrack-api=simulator[:VERSION]``
starts a subrack simulator locally instead, emulating VERSION (by
default 1.6.0).
"""
from __future__ import annotations

import fcntl
import re
import tempfile
import time
from pathlib import Path
from typing import Any, Final, Iterator

import pytest
import requests

pytestmark = pytest.mark.subrack_api

# ----------------------------------------------------------------------
# What the subrack web API is expected to provide.
#
# Taken from the registrations in ska-low-sps-smm-api
# (web_server/subrack_hardware.py, HardwareBaseClass.py and
# HardwareThreadedClass.py). "1.6.0" is the API before 1.8.0.
# ----------------------------------------------------------------------

# The expectations are keyed by SMM BIOS version, like the simulator's API
# versions. A subrack gets those of the highest key not newer than its BIOS,
# so BIOS 1.7.0 gets "1.6.0". The ``api_version`` attribute is not used: its
# number is not always bumped (v2.7.0 of the API reports 2.6.0).

_DEFAULT_COMMANDS: Final = frozenset(
    {
        "abort_command",
        "are_tpms_on",
        "command_completed",
        "get_all_attributes",
        "get_default_pll_source",
        "get_default_ps_redundancy",
        "get_health_dictionary",
        "get_health_status",
        "is_tpm_on",
        "list_attributes",
        "list_commands",
        "poweroff_subrack",
        "re_init_pll",
        "set_default_pll_source",
        "set_default_ps_redundancy",
        "set_fan_mode",
        "set_power_supply_fan_speed",
        "set_subrack_fan_speed",
        "tpm_info",
        "turn_off_tpm",
        "turn_off_tpms",
        "turn_on_tpm",
        "turn_on_tpms",
    }
)
"""The commands of the API before 1.8.0, which later versions edit."""

API_COMMANDS: Final[dict[str, frozenset[str]]] = {
    "1.6.0": _DEFAULT_COMMANDS,
    "1.8.0": (
        _DEFAULT_COMMANDS
        - {
            "set_power_supply_fan_speed",
            "tpm_info",
        }
    )
    | {
        "get_pll_phase_offset",
        "get_pps_phase_window",
        "set_pll_phase_offset",
        "set_pps_phase_window",
        "set_watchdog_enabled",
        "set_watchdog_timeout_minutes",
    },
}

_DEFAULT_ATTRIBUTES: Final = frozenset(
    {
        "api_version",
        "assigned_tpm_ip_adds",
        "backplane_temperatures",
        "board_current",
        "board_info",
        "board_temperatures",
        "cpld_pll_locked",
        "power_supply_currents",
        "power_supply_fan_speeds",
        "power_supply_powers",
        "power_supply_voltages",
        "subrack_fan_mode",
        "subrack_fan_speeds",
        "subrack_fan_speeds_percent",
        "subrack_pll_locked",
        "subrack_timestamp",
        "tpm_currents",
        "tpm_ips",
        "tpm_on_off",
        "tpm_powers",
        "tpm_present",
        "tpm_supply_fault",
        "tpm_voltages",
        # Also registered, but unavailable: see UNAVAILABLE_ATTRIBUTES.
    }
)
"""The attributes of the API before 1.8.0, which later versions edit."""

API_ATTRIBUTES: Final[dict[str, frozenset[str]]] = {
    "1.6.0": _DEFAULT_ATTRIBUTES,
    "1.8.0": (_DEFAULT_ATTRIBUTES - {"tpm_currents"}) | {"get_watchdog_status"},
}

UNAVAILABLE_ATTRIBUTES: Final[dict[str, frozenset[str]]] = {
    "1.6.0": frozenset(
        {
            "tpm_mcu_temperatures",
            "tpms_temp_alarms",
            "tpms_temperatures",
            "tpms_voltage_alarms",
        }
    ),
    "1.8.0": frozenset(),
}
"""
Attributes that a version registers but cannot answer, so are not tested.

Before 1.8.0, reading these always raises after the response headers
have been sent, so the client gets HTTP 200 with an empty body. 1.8.0
removed them, so it must refuse them.
"""

ALL_ATTRIBUTES: Final = frozenset().union(
    *API_ATTRIBUTES.values(), *UNAVAILABLE_ATTRIBUTES.values()
)
"""Every attribute of every API version."""

UNAVAILABLE_COMMANDS: Final[dict[str, frozenset[str]]] = {
    "1.6.0": frozenset({"get_all_attributes", "tpm_info"}),
    "1.8.0": frozenset(),
}
"""
Commands that a version registers but cannot run, so are not tested.

Before 1.8.0, ``tpm_info`` calls a deprecated method, and
``get_all_attributes`` reads attributes that always fail, so both always
answer with an error. Unlike unavailable attributes, they stay in
``API_COMMANDS``, which must match what ``list_commands`` reports.
"""

ALL_COMMANDS: Final = frozenset().union(*API_COMMANDS.values())
"""Every command of every API version."""

SAFE_COMMANDS: Final[dict[str, str]] = {
    "are_tpms_on": "",
    "command_completed": "",
    "get_all_attributes": "",
    "get_default_pll_source": "",
    "get_default_ps_redundancy": "",
    "get_health_dictionary": "",
    "get_health_status": "",
    "get_pll_phase_offset": "",
    "get_pps_phase_window": "",
    "is_tpm_on": "1",
    "list_attributes": "",
    "list_commands": "",
    "tpm_info": "1",
}
"""
The commands that do not change the subrack, with the argument to send.

These are the only commands that the tests send. Any other command could
change the hardware, so it is never sent, not even to a version that is
expected to reject it: if that expectation were wrong, the subrack would
run the command. Whether those commands exist is checked through
``list_commands`` instead.

Two of these commands have side effects in 1.8.0, although they do not
change the hardware: ``get_health_status`` resets the peak-hold values
and counters it reports, and ``command_completed`` releases the block of
a command that has finished.
"""

_PSUS: Final = ("PSU1", "PSU2")
_SLOTS: Final = tuple(f"SLOT{number}" for number in range(1, 9))
_FANS: Final = tuple(f"FAN{number}" for number in range(1, 5))

_DEFAULT_HEALTH_STATUS_KEYS: Final[dict[str, Any]] = {
    "iso_datetime": None,
    "system": None,
    "SMM": ("power", "power_max"),
    "temperatures": ("BKPLN1", "BKPLN2", "SMM1", "SMM2", "SMM_PLL"),
    "plls": ("BoardPllLock", "CPLDPllLock", "PllSource"),
    "pings": ("pings_CPLD",),
    "internal_voltages": (
        "V_1V1",
        "V_1V5",
        "V_2V5",
        "V_2V8",
        "V_3V",
        "V_3V3",
        "V_5V",
        "V_ARM",
        "V_CORE",
        "V_DDR",
        "V_POWERIN",
        "V_SOC",
    ),
    "fans": {"mode": _FANS, "pwm_duty": _FANS, "speed": _FANS},
    "psus": {
        "busy": _PSUS,
        "cml_fault": _PSUS,
        "fan_fault": _PSUS,
        "fan_speed": _PSUS,
        "input_fault": _PSUS,
        "iout_fault": _PSUS,
        "iout_oc_fault": _PSUS,
        "off": _PSUS,
        "other": _PSUS,
        "power_in": _PSUS,
        "power_out": _PSUS,
        "present": _PSUS,
        "pwr_gd": _PSUS,
        "temp_fault": _PSUS,
        "temp_fet": _PSUS,
        "temp_inlet": _PSUS,
        "unknown": _PSUS,
        "vin_uv_fault": _PSUS,
        "voltage_in": _PSUS,
        "voltage_out": _PSUS,
        "vout_fault": _PSUS,
        "vout_ov_fault": _PSUS,
    },
    "slots": {
        "on": _SLOTS,
        "pings": _SLOTS,
        "powers": _SLOTS,
        "presence": _SLOTS,
        "singlewire": _SLOTS,
        "voltages": _SLOTS,
    },
}
"""The health status keys of the API before 1.8.0, which later versions edit."""

HEALTH_STATUS_KEYS: Final[dict[str, dict[str, Any]]] = {
    "1.6.0": _DEFAULT_HEALTH_STATUS_KEYS,
    "1.8.0": {
        **_DEFAULT_HEALTH_STATUS_KEYS,
        "plls": _DEFAULT_HEALTH_STATUS_KEYS["plls"]
        + (
            "BoardApllUnlockCount",
            "BoardDpllUnlockCount",
            "BoardSysclkEventCount",
            "PPS",
            "PPSFaultCount",
            "PPSPhase",
            "PPSPhaseOutliers",
            "PPSPhaseStdev",
            "REF",
            "REFFaultCount",
        ),
        "internal_voltages": _DEFAULT_HEALTH_STATUS_KEYS["internal_voltages"]
        + ("BkplnPowerGood", "V_POWERIN_MAX", "V_POWERIN_MIN"),
        "slots": {
            **_DEFAULT_HEALTH_STATUS_KEYS["slots"],
            "faults": _SLOTS,
            "powers_max": _SLOTS,
            "voltages_max": _SLOTS,
            "voltages_min": _SLOTS,
        },
    },
}
"""
The keys of the health status, from the monitoring point lookup
(subrack_mng_api/subrack_monitoring_point_lookup.py).

A tuple lists the keys under a key; None marks a key whose contents are
not checked, because they vary (``system`` is reported by the system
monitor, not the lookup).
"""

ATTRIBUTE_RESPONSE_KEYS: Final = frozenset({"status", "info", "attribute", "value"})
COMMAND_RESPONSE_KEYS: Final = frozenset({"status", "info", "command", "retvalue"})

EXTRA_COMMAND_RESPONSE_KEYS: Final[dict[str, dict[str, frozenset[str]]]] = {
    "1.6.0": {},
    "1.8.0": {"command_completed": frozenset({"failed"})},
}
"""Keys that a version adds to the response of particular commands."""

REJECTED_ATTRIBUTE_RESPONSE_KEYS: Final = frozenset(
    {"status", "info", "attribute", "retvalue"}
)
"""The API rejects an attribute it does not have with "retvalue", not "value"."""

ATTEMPTS: Final = 3
"""How many times to read an attribute that answers with an error."""

RETRY_INTERVAL: Final = 1.0
"""Seconds to wait between attempts."""

# ----------------------------------------------------------------------
# Connection to the subrack under test.
#
# This is the only part of the module that knows whether the target is
# the simulator.
# ----------------------------------------------------------------------

_SIMULATOR_GAPS_IN_EVERY_VERSION: Final[dict[str, str]] = {
    "test_rejected_attribute": (
        "simulator rejects an attribute with 'value', not 'retvalue'"
    ),
    "test_missing_type_is_rejected": (
        "simulator answers a missing type with {info, status: HTTP_ERROR}"
    ),
    "test_invalid_type_is_rejected": (
        "simulator answers an invalid type with {info, status: HTTP_ERROR}"
    ),
    "test_provided_attribute[assigned_tpm_ip_adds]": (
        "simulator has no assigned_tpm_ip_adds"
    ),
    "test_provided_attribute[tpm_ips]": "simulator has no tpm_ips",
    "test_provided_attribute[tpm_supply_fault]": "simulator has no tpm_supply_fault",
    "test_command_list": "simulator does not provide every command",
    "test_health_status": "simulator lacks some of the health status",
    **{
        f"test_provided_command[{name}]": f"simulator has no {name}"
        for name in (
            "are_tpms_on",
            "get_default_pll_source",
            "get_default_ps_redundancy",
            "get_health_dictionary",
            "is_tpm_on",
            "list_attributes",
        )
    },
}

SIMULATOR_KNOWN_GAPS: Final[dict[str, dict[str, str]]] = {
    "1.6.0": _SIMULATOR_GAPS_IN_EVERY_VERSION,
    "1.8.0": {
        **_SIMULATOR_GAPS_IN_EVERY_VERSION,
        "test_provided_command[command_completed]": (
            "simulator does not add 'failed' to command_completed"
        ),
        **{
            f"test_provided_command[{name}]": f"simulator has no {name}"
            for name in (
                "get_all_attributes",
                "get_pll_phase_offset",
                "get_pps_phase_window",
            )
        },
        "test_provided_attribute[get_watchdog_status]": (
            "simulator has no get_watchdog_status"
        ),
    },
}
"""
Where the simulator is known not to behave like the API.

Each entry is reported as a strict expected failure when testing the
simulator, so a gap that gets fixed shows up as a failure until its
entry is removed.
"""


@pytest.fixture(name="subrack_url")
def subrack_url_fixture(request: pytest.FixtureRequest) -> Iterator[str]:
    """
    Yield the URL of the subrack web API under test.

    :param request: the pytest request.

    :yields: the URL of the web API.
    """
    target = request.config.getoption("--subrack-api")
    if target is None:
        pytest.skip("needs --subrack-api")
    if not target.startswith("simulator"):
        yield f"http://{target}/get/json.htm"
        return

    # pylint: disable-next=import-outside-toplevel
    from ska_low_mccs_spshw.subrack import SubrackSimulator

    # pylint: disable-next=import-outside-toplevel
    from ska_low_mccs_spshw.subrack.subrack_simulator_server import (
        SubrackServerContextManager,
    )

    _, _, simulator_version = target.partition(":")
    simulator = SubrackSimulator(api_version=simulator_version or "1.6.0")
    with SubrackServerContextManager(simulator) as (host, port):
        url = f"http://{host}:{port}/get/json.htm"
        gaps = SIMULATOR_KNOWN_GAPS[_read_api_version(url)]
        gap = gaps.get(request.node.name) or gaps.get(request.node.originalname)
        if gap is not None:
            request.node.add_marker(pytest.mark.xfail(reason=gap, strict=True))
        yield url


@pytest.fixture(name="api_version")
def api_version_fixture(subrack_url: str) -> str:
    """
    Return which expectations apply to the subrack web API under test.

    :param subrack_url: the URL of the web API.

    :return: the key of the expectations, e.g. "1.8.0".
    """
    return _read_api_version(subrack_url)


def _read_api_version(subrack_url: str) -> str:
    """
    Read the subrack's BIOS version, and return which expectations apply.

    :param subrack_url: the URL of the web API.

    :return: the key of the expectations, e.g. "1.8.0".
    """
    response = _request(subrack_url, type="getattribute", param="board_info")
    if response["status"] != "OK":
        pytest.fail(f"Cannot read the subrack's board_info: {response}")
    bios = str(response["value"]["SMM"]["bios"])
    match = re.match(r"v?(\d+)\.(\d+)\.(\d+)", bios)
    if match is None:
        pytest.fail(f"Cannot parse the subrack's BIOS version {bios!r}")
    bios_version = tuple(int(part) for part in match.groups())
    applicable = [
        version
        for version in API_ATTRIBUTES
        if tuple(int(part) for part in version.split(".")) <= bios_version
    ]
    if not applicable:
        pytest.fail(f"No expectations for BIOS version {bios}")
    return max(applicable, key=lambda version: tuple(map(int, version.split("."))))


_REQUEST_LOCK_PATH: Final = Path(tempfile.gettempdir()) / "subrack_web_api_tests.lock"


def _request(subrack_url: str, **params: str) -> dict[str, Any]:
    """
    Send a request to the subrack web API.

    The subrack's web server answers one request at a time, so requests
    are serialised across every test process, however many there are.

    :param subrack_url: the URL of the web API.
    :param params: the query parameters.

    :return: the decoded JSON response.
    """
    with open(_REQUEST_LOCK_PATH, "a", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        response = requests.get(subrack_url, params=params, timeout=10)
    response.raise_for_status()
    assert response.text, f"Empty response to {params}"
    return response.json()


def _request_until_ok(subrack_url: str, **params: str) -> dict[str, Any]:
    """
    Send a request, retrying while the subrack answers with an error.

    :param subrack_url: the URL of the web API.
    :param params: the query parameters.

    :return: the decoded JSON response of the last attempt.
    """
    for _ in range(ATTEMPTS - 1):
        response = _request(subrack_url, **params)
        if response.get("status") != "ERROR":
            return response
        time.sleep(RETRY_INTERVAL)
    return _request(subrack_url, **params)


def _health_status_paths(keys: dict[str, Any], prefix: str = "") -> set[str]:
    """
    Return the dotted paths of the health status keys that are checked.

    :param keys: the expected keys, as in ``HEALTH_STATUS_KEYS``.
    :param prefix: the path of ``keys`` itself.

    :return: the dotted path of every key with no keys checked under it.
    """
    paths = set()
    for key, below in keys.items():
        path = f"{prefix}{key}"
        if below is None:
            paths.add(path)
        elif isinstance(below, tuple):
            paths.update(f"{path}.{name}" for name in below)
        else:
            paths.update(_health_status_paths(below, f"{path}."))
    return paths


def _reported_paths(
    health: dict[str, Any], expected: set[str], prefix: str = ""
) -> set[str]:
    """
    Return the dotted paths of a health status, down to the expected keys.

    :param health: the health status, or part of it.
    :param expected: the expected paths, below which nothing is collected.
    :param prefix: the path of ``health`` itself.

    :return: the dotted paths.
    """
    paths = set()
    for key, value in health.items():
        path = f"{prefix}{key}"
        if path in expected or not isinstance(value, dict):
            paths.add(path)
        else:
            paths.update(_reported_paths(value, expected, f"{path}."))
    return paths


# ----------------------------------------------------------------------
# Malformed requests
# ----------------------------------------------------------------------


def test_missing_type_is_rejected(subrack_url: str) -> None:
    """
    Test that a request without a type is rejected.

    :param subrack_url: the URL of the web API.
    """
    response = _request(subrack_url, param="list_commands")
    assert response == {
        "status": "ERROR",
        "info": "Missing keyword: type",
        "command": "list_commands",
        "retvalue": "",
    }


def test_invalid_type_is_rejected(subrack_url: str) -> None:
    """
    Test that a request with a type that does not exist is rejected.

    :param subrack_url: the URL of the web API.
    """
    response = _request(subrack_url, type="no_such_type", param="list_commands")
    assert response == {
        "status": "ERROR",
        "info": "Invalid type: no_such_type",
        "command": "list_commands",
        "retvalue": "",
    }


# ----------------------------------------------------------------------
# Attributes provided
# ----------------------------------------------------------------------


@pytest.mark.parametrize("attribute_name", sorted(ALL_ATTRIBUTES))
def test_provided_attribute(
    subrack_url: str, api_version: str, attribute_name: str
) -> None:
    """
    Test that an attribute of the API version can be read.

    :param subrack_url: the URL of the web API.
    :param api_version: the API version under test.
    :param attribute_name: the attribute to read.
    """
    if attribute_name not in API_ATTRIBUTES[api_version]:
        pytest.skip(f"{attribute_name} is not an attribute of this API version")

    response = _request_until_ok(subrack_url, type="getattribute", param=attribute_name)
    assert set(response) == ATTRIBUTE_RESPONSE_KEYS, response
    assert response["status"] == "OK", response


@pytest.mark.parametrize("attribute_name", sorted(ALL_ATTRIBUTES))
def test_rejected_attribute(
    subrack_url: str, api_version: str, attribute_name: str
) -> None:
    """
    Test that an attribute of another API version is rejected.

    :param subrack_url: the URL of the web API.
    :param api_version: the API version under test.
    :param attribute_name: the attribute to read.
    """
    if attribute_name in API_ATTRIBUTES[api_version]:
        pytest.skip(f"{attribute_name} is an attribute of this API version")
    if attribute_name in UNAVAILABLE_ATTRIBUTES[api_version]:
        pytest.skip(f"{attribute_name} is unavailable in this API version")

    response = _request(subrack_url, type="getattribute", param=attribute_name)
    assert set(response) == REJECTED_ATTRIBUTE_RESPONSE_KEYS, response
    assert response["status"] == "ERROR", response
    assert response["info"] == f"Attribute {attribute_name} not present", response


# ----------------------------------------------------------------------
# Commands
# ----------------------------------------------------------------------


def test_command_list(subrack_url: str, api_version: str) -> None:
    """
    Test that the subrack lists exactly the commands of the API version.

    This also covers the commands that are never sent.

    :param subrack_url: the URL of the web API.
    :param api_version: the API version under test.
    """
    response = _request_until_ok(
        subrack_url, type="command", param="list_commands", value=""
    )
    assert response["status"] == "OK", response
    listed = set(response["retvalue"])
    expected = API_COMMANDS[api_version]
    assert listed == expected, (
        f"missing: {sorted(expected - listed)}, "
        f"unexpected: {sorted(listed - expected)}"
    )


@pytest.mark.parametrize("command_name", sorted(ALL_COMMANDS))
def test_provided_command(
    subrack_url: str, api_version: str, command_name: str
) -> None:
    """
    Test that a safe command of the API version runs.

    :param subrack_url: the URL of the web API.
    :param api_version: the API version under test.
    :param command_name: the command to run.
    """
    if command_name not in API_COMMANDS[api_version]:
        pytest.skip(f"{command_name} is not a command of this API version")
    if command_name not in SAFE_COMMANDS:
        pytest.skip(f"{command_name} is never sent: it changes the subrack")
    if command_name in UNAVAILABLE_COMMANDS[api_version]:
        pytest.skip(f"{command_name} is unavailable in this API version")
    if command_name == "get_health_status":
        pytest.skip("get_health_status is tested by test_health_status")

    response = _request_until_ok(
        subrack_url,
        type="command",
        param=command_name,
        value=SAFE_COMMANDS[command_name],
    )
    expected_keys = COMMAND_RESPONSE_KEYS | EXTRA_COMMAND_RESPONSE_KEYS[
        api_version
    ].get(command_name, frozenset())
    assert set(response) == expected_keys, response
    assert response["status"] == "OK", response


@pytest.mark.parametrize("command_name", sorted(ALL_COMMANDS))
def test_rejected_command(
    subrack_url: str, api_version: str, command_name: str
) -> None:
    """
    Test that a safe command of another API version is rejected.

    :param subrack_url: the URL of the web API.
    :param api_version: the API version under test.
    :param command_name: the command to send.
    """
    if command_name in API_COMMANDS[api_version]:
        pytest.skip(f"{command_name} is a command of this API version")
    if command_name not in SAFE_COMMANDS:
        pytest.skip(f"{command_name} is never sent: it changes the subrack")

    response = _request(
        subrack_url,
        type="command",
        param=command_name,
        value=SAFE_COMMANDS[command_name],
    )
    assert response == {
        "status": "ERROR",
        "info": f"Command {command_name} not implemented",
        "command": command_name,
        "retvalue": "",
    }


def test_health_status(subrack_url: str, api_version: str) -> None:
    """
    Test that the health status has exactly the keys of the API version.

    :param subrack_url: the URL of the web API.
    :param api_version: the API version under test.
    """
    response = _request_until_ok(
        subrack_url, type="command", param="get_health_status", value=""
    )
    assert set(response) == COMMAND_RESPONSE_KEYS, response
    assert response["status"] == "OK", response

    expected = _health_status_paths(HEALTH_STATUS_KEYS[api_version])
    reported = _reported_paths(response["retvalue"], expected)
    assert reported == expected, (
        f"missing: {sorted(expected - reported)}, "
        f"unexpected: {sorted(reported - expected)}"
    )
