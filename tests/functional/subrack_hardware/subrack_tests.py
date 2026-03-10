# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This file contains a test for the subrack hardware."""
import json

import pytest
from ska_low_mccs_common.component import WebHardwareClient

if not "":
    pytest.skip("skipping windows-only tests", allow_module_level=True)


def assert_with_context(
    value: int | str | bool, expected: tuple | list | str | int | bool, context: str
) -> None:
    """
    Run assert for different types of values.

    Conditional assert that uses different logic based on 'expected' input

    if expected is a tuple, it will be treated as a min/max pair of values.
    if expected is a list, it will be treated as a list of fixed values
    else: expected is treated as the only valid value.

    :param value: value to test
    :param expected: expected value
    :param context: assert message
    """
    if isinstance(expected, tuple):
        assert expected[0] <= value <= expected[1], context
    elif isinstance(expected, list):
        assert value in expected, context
    else:
        assert expected == value, context


class TestSubrackHardwareAPI:
    """Dedicated hardware tests for the subrack API."""

    def test_get_health_status(
        self,
        subrack_client: WebHardwareClient,
        expected_health_status: dict,
    ) -> None:
        """
        Verify the health_status parameters.

        This test compares the

        :param subrack_client: http client used to talk to the subrack
        :param expected_health_status: the expected values and value ranges.
        """
        result = subrack_client.execute_command("get_health_status", "")
        assert result["status"] == "OK"
        assert result["command"] == "get_health_status"
        assert result["retvalue"] is not None
        retvalue = json.loads(result["retvalue"])

        assert expected_health_status["iso_datetime"] in retvalue["iso_datetime"]

        for key in ["SMM", "internal_voltages", "pings", "plls", "temperatures"]:
            for item_id, value in retvalue[key].items():
                assert_with_context(
                    value,
                    expected_health_status[key][item_id],
                    f"Test for {key}:{item_id}",
                )

        for group in ["fans", "psus", "slots"]:
            for key, collection in retvalue[group].items():
                for item_id, value in collection.items():
                    assert_with_context(
                        value,
                        expected_health_status[group][key][item_id],
                        f"Test for {group}:{key}:{item_id}",
                    )

    @pytest.mark.parametrize(
        ("attribute", "fixture_name"),
        [
            ("backplane_temperatures", "BKPLN"),
            ("board_temperatures", "SMM"),
        ],
    )
    def test_temperature_attributes(
        self,
        subrack_client: WebHardwareClient,
        attribute: str,
        fixture_name: str,
        expected_health_status: dict,
    ) -> None:
        """
        Verify the temperature related attributes.

        :param subrack_client: http client used to talk to the subrack
        :param attribute: the attribute name used in the client call
        :param fixture_name: the correspodning key in expected health status
        :param expected_health_status: the expected values and value ranges.
        """
        result = subrack_client.get_attribute(attribute)
        assert result["status"] == "OK"
        assert result["attribute"] == attribute
        temps = expected_health_status["temperatures"]
        value = result["value"]
        assert value is not None
        for i, val in enumerate(json.loads(value)):
            assert_with_context(
                val, temps[f"{fixture_name}{i+1}"], f"{fixture_name}: {i}"
            )

    @pytest.mark.parametrize(
        ("attribute", "fixture_name"),
        [
            ("subrack_fan_speeds", "speed"),
            ("subrack_fan_speeds_percent", "pwm_duty"),
            ("subrack_fan_mode", "mode"),
        ],
    )
    def test_subrack_fan_attributes(
        self,
        subrack_client: WebHardwareClient,
        attribute: str,
        fixture_name: str,
        expected_health_status: dict,
    ) -> None:
        """
        Verify the fan related attributes.

        :param subrack_client: http client used to talk to the subrack
        :param attribute: the attribute name used in the client call
        :param fixture_name: the corresponding key in expected health status
        :param expected_health_status: the expected values and value ranges.
        """
        result = subrack_client.get_attribute(attribute)
        assert result["status"] == "OK"
        assert result["attribute"] == attribute
        fans = expected_health_status["fans"]
        value = result["value"]
        assert value is not None
        for i, val in enumerate(json.loads(value)):
            assert_with_context(
                val, fans[fixture_name][f"FAN{i+1}"], f"{fixture_name}: FAN_{i+1}"
            )

    @pytest.mark.parametrize(
        ("attribute", "fixture_name"),
        [
            ("power_supply_fan_speeds", "fan_speed"),
            ("power_supply_currents", "currents"),
            ("power_supply_powers", "power_out"),
            ("power_supply_voltages", "voltage_out"),
        ],
    )
    def test_power_supply_attributes(
        self,
        subrack_client: WebHardwareClient,
        attribute: str,
        fixture_name: str,
        psus: dict,
    ) -> None:
        """
        Verify the Power Supply related attributes.

        :param subrack_client: http client used to talk to the subrack
        :param attribute: the attribute name used in the client call
        :param fixture_name: the correspodning key in expected health status
        :param psus: the expected values and value ranges.
        """
        result = subrack_client.get_attribute(attribute)
        assert result["status"] == "OK"
        assert result["attribute"] == attribute
        value = result["value"]
        assert value is not None
        for i, val in enumerate(json.loads(value)):
            assert_with_context(
                val, psus[fixture_name][f"PSU{i+1}"], f"{fixture_name}: PSU_{i+1}"
            )

    @pytest.mark.parametrize(
        ("attribute", "fixture_name"),
        [
            ("tpm_voltages", "voltages"),
            ("tpm_currents", "currents"),
            ("tpm_powers", "powers"),
            ("tpm_present", "presence"),
            ("tpm_supply_fault", "supply_fault"),
            ("tpm_on_off", "on"),
        ],
    )
    def test_tpm_attributes(
        self,
        subrack_client: WebHardwareClient,
        attribute: str,
        fixture_name: str,
        tpms: dict,
    ) -> None:
        """
        Verify the TPM related attributes.

        :param subrack_client: http client used to talk to the subrack
        :param attribute: the attribute name used in the client call
        :param fixture_name: the correspodning key in expected health status
        :param tpms: the expected values and value ranges.
        """
        result = subrack_client.get_attribute(attribute)
        assert result["status"] == "OK"
        assert result["attribute"] == attribute
        value = result["value"]
        assert value is not None
        for i, val in enumerate(json.loads(value)):
            assert_with_context(
                val, tpms[fixture_name][f"SLOT{i+1}"], f"{fixture_name}: SLOT_{i+1}"
            )

    @pytest.mark.parametrize(
        ("attribute", "expected_value"),
        [
            ("cpld_pll_locked", True),
            ("subrack_pll_locked", True),
            # ("api_version", '2.8.0 (v2.7.0-86-gdfb95e5)
            # [WARNING minimum SMM OS_rev required 0.11.0]'),
            # ("subrack_timestamp", 100),
        ],
    )
    def test_attributes_fixed(
        self, subrack_client: WebHardwareClient, attribute: str, expected_value: bool
    ) -> None:
        """
        Verify attributes.

        :param subrack_client: http client used to talk to the subrack
        :param attribute: the attribute name used in the client call
        :param expected_value: the expected result.
        """
        result = subrack_client.get_attribute(attribute)
        assert result["status"] == "OK"
        assert result["attribute"] == attribute
        assert result["value"] == expected_value

    @pytest.mark.parametrize(("attribute"), ["tpm_ips", "assigned_tpm_ip_adds"])
    def test_tpm_ips(
        self, subrack_client: WebHardwareClient, attribute: str, tpm_ips: dict
    ) -> None:
        """
        Verify ip addresses of tpms.

        :param subrack_client: http client used to talk to the subrack
        :param attribute: the attribute name used in the client call
        :param tpm_ips: fixture containing tpm ips.
        """
        result = subrack_client.get_attribute(attribute)
        assert result["status"] == "OK"
        assert result["attribute"] == attribute
        assert result["value"] == tpm_ips
