# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests of the subrack component manager."""
from typing import Any

import pytest
from ska_control_model import CommunicationStatus, PowerState
from ska_low_mccs_common.component import StatusCode
from ska_tango_testing.mock import MockCallableGroup

from ska_low_mccs_spshw.subrack import (
    FanMode,
    SubrackData,
    SubrackDriver,
    SubrackSimulator,
)


def test_attribute_reads(
    subrack_driver: SubrackDriver,
    subrack_simulator_attribute_values: dict[str, Any],
    callbacks: MockCallableGroup,
) -> None:
    """
    Test that the subrack driver pushes a full set of attribute values.

    :param subrack_driver: the subrack driver under test
    :param subrack_simulator_attribute_values: key-value dictionary of
        the expected subrack simulator attribute values
    :param callbacks: dictionary of driver callbacks.
    """
    callbacks["communication_status"].assert_not_called()
    callbacks["component_state"].assert_not_called()

    subrack_driver.start_communicating()

    callbacks["communication_status"].assert_call(CommunicationStatus.NOT_ESTABLISHED)
    callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)
    callbacks["communication_status"].assert_not_called()

    callbacks["component_state"].assert_call(power=PowerState.ON, fault=False)
    callbacks["component_state"].assert_call(**subrack_simulator_attribute_values)
    callbacks["component_state"].assert_not_called()

    subrack_driver.stop_communicating()

    callbacks["communication_status"].assert_call(CommunicationStatus.DISABLED)
    callbacks["communication_status"].assert_not_called()

    callbacks["component_state"].assert_call(
        fault=None,
        **{name: None for name in subrack_simulator_attribute_values},
    )
    callbacks["component_state"].assert_call(power=PowerState.UNKNOWN)
    callbacks["component_state"].assert_not_called()


def test_attribute_updates(  # pylint: disable=too-many-locals
    subrack_simulator: SubrackSimulator,
    subrack_driver: SubrackDriver,
    subrack_simulator_attribute_values: dict[str, Any],
    callbacks: MockCallableGroup,
) -> None:
    """
    Test that the subrack driver receives updated values.

    :param subrack_simulator: the subrack simulator backend that the
        subrack driver drives through its server interface
    :param subrack_driver: the subrack driver under test
    :param subrack_simulator_attribute_values: key-value dictionary of
        the expected subrack simulator attribute values
    :param callbacks: dictionary of driver callbacks.
    """
    callbacks["communication_status"].assert_not_called()
    callbacks["component_state"].assert_not_called()

    subrack_driver.start_communicating()

    callbacks["communication_status"].assert_call(CommunicationStatus.NOT_ESTABLISHED)
    callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)
    callbacks["communication_status"].assert_not_called()

    callbacks["component_state"].assert_call(power=PowerState.ON, fault=False)
    callbacks["component_state"].assert_call(**subrack_simulator_attribute_values)
    callbacks["component_state"].assert_not_called()

    subrack_simulator.simulate_attribute("board_current", 0.7)
    callbacks["component_state"].assert_call(
        board_current=pytest.approx(0.7),
    )

    for name, values in [
        ("backplane_temperatures", [45.0, 46.0]),
        ("board_temperatures", [47.0, 48.0]),
        # Not implemented on SMB
        # ("tpm_temperatures", [41.1, 41.2, 41.3, 41.4, 41.5, 41.6, 41.7, 41.8]),
    ]:
        subrack_simulator.simulate_attribute(name, values)
        callbacks["component_state"].assert_call(
            **{name: [pytest.approx(v) for v in values]},
        )

    new_power_supply_fan_speeds = [7500.0, 7600.0]
    subrack_simulator.simulate_attribute(
        "power_supply_fan_speeds", new_power_supply_fan_speeds
    )
    callbacks["component_state"].assert_call(
        power_supply_fan_speeds=[pytest.approx(s) for s in new_power_supply_fan_speeds],
    )

    new_subrack_fan_speeds_percent = [82.0, 83.0, 84.0, 85.0]
    subrack_simulator.simulate_attribute(
        "subrack_fan_speeds_percent", new_subrack_fan_speeds_percent
    )
    callbacks["component_state"].assert_call(
        subrack_fan_speeds_percent=[
            pytest.approx(s) for s in new_subrack_fan_speeds_percent
        ],
        subrack_fan_speeds=[
            pytest.approx(p * SubrackData.MAX_SUBRACK_FAN_SPEED / 100.0)
            for p in new_subrack_fan_speeds_percent
        ],
    )

    power_supply_currents = subrack_simulator.get_attribute("power_supply_currents")
    new_power_supply_voltages = [13.1, 13.2]
    expected_power_supply_powers = [
        pytest.approx(i * v)
        for i, v in zip(power_supply_currents, new_power_supply_voltages)
    ]
    subrack_simulator.simulate_attribute(
        "power_supply_voltages", new_power_supply_voltages
    )
    callbacks["component_state"].assert_call(
        power_supply_voltages=[pytest.approx(v) for v in new_power_supply_voltages],
        power_supply_powers=expected_power_supply_powers,
    )

    new_power_supply_currents = [4.5, 4.6]
    expected_power_supply_powers = [
        pytest.approx(i * v)
        for i, v in zip(new_power_supply_currents, new_power_supply_voltages)
    ]
    subrack_simulator.simulate_attribute(
        "power_supply_currents", new_power_supply_currents
    )
    callbacks["component_state"].assert_call(
        power_supply_currents=[pytest.approx(i) for i in new_power_supply_currents],
        power_supply_powers=expected_power_supply_powers,
    )

    tpm_currents = subrack_simulator.get_attribute("tpm_currents")
    new_tpm_voltages = [12.2] * 8
    expected_tpm_powers = [
        pytest.approx(i * v) for i, v in zip(tpm_currents, new_tpm_voltages)
    ]
    subrack_simulator.simulate_attribute("tpm_voltages", new_tpm_voltages)
    callbacks["component_state"].assert_call(
        tpm_voltages=[pytest.approx(v) for v in new_tpm_voltages],
        tpm_powers=expected_tpm_powers,
    )

    new_tpm_currents = [0.45] * 8
    expected_tpm_powers = [
        pytest.approx(i * v) for i, v in zip(new_tpm_currents, new_tpm_voltages)
    ]
    subrack_simulator.simulate_attribute("tpm_currents", new_tpm_currents)
    callbacks["component_state"].assert_call(
        tpm_currents=[pytest.approx(i) for i in new_tpm_currents],
        tpm_powers=expected_tpm_powers,
    )

    subrack_simulator.simulate_attribute("cpld_pll_locked", False)
    callbacks["component_state"].assert_call(
        cpld_pll_locked=False,
    )
    subrack_simulator.simulate_attribute("subrack_pll_locked", False)
    callbacks["component_state"].assert_call(
        subrack_pll_locked=False,
    )

    new_timestamp = 1234567891
    subrack_simulator.simulate_attribute("subrack_timestamp", new_timestamp)
    callbacks["component_state"].assert_call(
        subrack_timestamp=new_timestamp,
    )


def test_tpm_power_commands(
    subrack_simulator: SubrackSimulator,
    subrack_driver: SubrackDriver,
    subrack_simulator_attribute_values: dict[str, Any],
    callbacks: MockCallableGroup,
) -> None:
    """
    Test that the subrack driver pushes a full set of attribute values.

    :param subrack_simulator: the subrack simulator backend that the
        subrack driver drives through its server interface
    :param subrack_driver: the subrack driver under test
    :param subrack_simulator_attribute_values: key-value dictionary of
        the expected subrack simulator attribute values
    :param callbacks: dictionary of driver callbacks.
    """
    callbacks["communication_status"].assert_not_called()
    callbacks["component_state"].assert_not_called()

    subrack_driver.start_communicating()

    callbacks["communication_status"].assert_call(CommunicationStatus.NOT_ESTABLISHED)
    callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)
    callbacks["communication_status"].assert_not_called()

    callbacks["component_state"].assert_call(power=PowerState.ON, fault=False)
    callbacks["component_state"].assert_call(**subrack_simulator_attribute_values)
    callbacks["component_state"].assert_not_called()

    tpm_on_off = subrack_simulator.get_attribute("tpm_on_off")
    tpm_to_power = 3  # one-based

    turn_off_first = tpm_on_off[tpm_to_power - 1]

    if turn_off_first:
        subrack_driver.turn_off_tpm(tpm_to_power)
        tpm_on_off[tpm_to_power - 1] = False
        callbacks["component_state"].assert_call(tpm_on_off=tpm_on_off)
        # We know that at least one TPM is off.

    subrack_driver.turn_on_tpms()
    tpm_on_off = [True for _ in tpm_on_off]
    callbacks["component_state"].assert_call(tpm_on_off=tpm_on_off)

    subrack_driver.turn_off_tpm(tpm_to_power)
    tpm_on_off[tpm_to_power - 1] = False
    callbacks["component_state"].assert_call(tpm_on_off=tpm_on_off)

    subrack_driver.turn_off_tpms()
    tpm_on_off = [False for _ in tpm_on_off]
    callbacks["component_state"].assert_call(tpm_on_off=tpm_on_off)

    subrack_driver.turn_on_tpm(tpm_to_power)
    tpm_on_off[tpm_to_power - 1] = True
    callbacks["component_state"].assert_call(tpm_on_off=tpm_on_off)


def test_other_commands(
    subrack_simulator: SubrackSimulator,
    subrack_driver: SubrackDriver,
    subrack_simulator_attribute_values: dict[str, Any],
    callbacks: MockCallableGroup,
) -> None:
    """
    Test that the subrack driver pushes a full set of attribute values.

    :param subrack_simulator: the subrack simulator backend that the
        subrack driver drives through its server interface
    :param subrack_driver: the subrack driver under test
    :param subrack_simulator_attribute_values: key-value dictionary of
        the expected subrack simulator attribute values
    :param callbacks: dictionary of driver callbacks.
    """
    callbacks["communication_status"].assert_not_called()
    callbacks["component_state"].assert_not_called()

    subrack_driver.start_communicating()

    callbacks["communication_status"].assert_call(CommunicationStatus.NOT_ESTABLISHED)
    callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)
    callbacks["communication_status"].assert_not_called()

    callbacks["component_state"].assert_call(power=PowerState.ON, fault=False)
    callbacks["component_state"].assert_call(**subrack_simulator_attribute_values)
    callbacks["component_state"].assert_not_called()

    subrack_fan_speeds_percent = subrack_simulator.get_attribute(
        "subrack_fan_speeds_percent"
    )

    fan_to_set = 1  # one-based
    fan_speed_percent_setting = 51.0
    subrack_driver.set_subrack_fan_speed(fan_to_set, fan_speed_percent_setting)

    subrack_fan_speeds_percent[fan_to_set - 1] = fan_speed_percent_setting
    callbacks["component_state"].assert_call(
        subrack_fan_speeds_percent=[
            pytest.approx(s) for s in subrack_fan_speeds_percent
        ],
        subrack_fan_speeds=[
            pytest.approx(s * SubrackData.MAX_SUBRACK_FAN_SPEED / 100.0)
            for s in subrack_fan_speeds_percent
        ],
    )

    subrack_fan_mode = subrack_simulator.get_attribute("subrack_fan_mode")

    fan_to_set = 1  # one-based
    fan_speed_mode = (
        FanMode.AUTO
        if subrack_fan_mode[fan_to_set - 1] == FanMode.MANUAL
        else FanMode.MANUAL
    )
    subrack_driver.set_subrack_fan_mode(fan_to_set, fan_speed_mode)

    subrack_fan_mode[fan_to_set - 1] = fan_speed_mode
    callbacks["component_state"].assert_call(
        subrack_fan_mode=subrack_fan_mode,
    )

    power_supply_fan_speeds = subrack_simulator.get_attribute("power_supply_fan_speeds")

    fan_to_set = 2  # one-based
    fan_speed_setting = 7800.0
    subrack_driver.set_power_supply_fan_speed(fan_to_set, fan_speed_setting)

    power_supply_fan_speeds[fan_to_set - 1] = fan_speed_setting
    callbacks["component_state"].assert_call(
        power_supply_fan_speeds=[pytest.approx(s) for s in power_supply_fan_speeds],
    )


def test_failed_poll(
    subrack_driver: SubrackDriver,
    subrack_client: Any,
    subrack_simulator_attribute_values: dict[str, Any],
    failed_subrack_simulator_attribute_values: dict[str, Any],
    callbacks: MockCallableGroup,
) -> None:
    """
    Test that the subrack driver updates correctly with a failed poll.

    - When the client raises a HTTP_ERROR
        the driver is UNKNOWN since no attempt was made to contact it,
        The device is faulty since the request was not valid,
        (unsure if we are able to break this down further).
    - When a get_attribute response is not parsable, mark the attribute of interest
        as None (i.e UNKNOWN)
    - When the client raises RequestException
        the driver goes into UNKNOWN.
    - When client report StatusCode OK, we will return back to a ON state #
        and faults are wiped.

    :param subrack_client: A fixture with the server interface to
        allow mocking of exception codes easily.
    :param subrack_driver: the subrack driver under test
    :param subrack_simulator_attribute_values: key-value dictionary of
        the expected subrack simulator attribute values
    :param failed_subrack_simulator_attribute_values: key-value dictionary of
        the expected subrack simulator attribute values from a failed poll.
    :param callbacks: dictionary of driver callbacks.
    """
    callbacks["communication_status"].assert_not_called()
    callbacks["component_state"].assert_not_called()

    subrack_driver.start_communicating()

    callbacks["communication_status"].assert_call(CommunicationStatus.NOT_ESTABLISHED)
    callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)
    callbacks["communication_status"].assert_not_called()

    callbacks["component_state"].assert_call(power=PowerState.ON, fault=False)
    callbacks["component_state"].assert_call(**subrack_simulator_attribute_values)
    callbacks["component_state"].assert_not_called()

    subrack_client.get_attribute = lambda attr_name: {
        "status": StatusCode.HTTP_ERROR.name,
        "info": "Exception: " + str("mocked exception"),
        "attribute": attr_name,
        "value": None,
    }
    callbacks["component_state"].assert_call(fault=True)

    subrack_client.get_attribute = lambda attr_name: {
        "status": StatusCode.OK.name,
        "info": "",
        "attribute": attr_name,
        "value": subrack_simulator_attribute_values.get(attr_name),
    }
    callbacks["component_state"].assert_call(fault=False)

    subrack_client.get_attribute = lambda attr_name: {
        "status": StatusCode.REQUEST_EXCEPTION.name,
        "info": "Exception: " + str("mocked exception"),
        "attribute": attr_name,
        "value": None,
    }

    callbacks["component_state"].assert_call(power=PowerState.UNKNOWN)

    subrack_client.get_attribute = lambda attr_name: {
        "status": StatusCode.OK.name,
        "info": "",
        "attribute": attr_name,
        "value": subrack_simulator_attribute_values.get(attr_name),
    }
    callbacks["component_state"].assert_call(power=PowerState.ON)

    subrack_client.get_attribute = lambda attr_name: {
        "status": "invalid_response code",
        "info": "",
        "attribute": attr_name,
        "value": subrack_simulator_attribute_values.get(attr_name),
    }
    callbacks["component_state"].assert_call(fault=True)

    subrack_client.get_attribute = lambda attr_name: {
        "status": StatusCode.OK.name,
        "info": "",
        "attribute": attr_name,
        "value": subrack_simulator_attribute_values.get(attr_name),
    }
    callbacks["component_state"].assert_call(fault=False)

    subrack_client.get_attribute = lambda attr_name: {
        "status": StatusCode.JSON_DECODE_ERROR.name,
        "info": "Exception: " + str("mocked exception"),
        "attribute": attr_name,
        "value": None,
    }

    callbacks["component_state"].assert_call(
        **failed_subrack_simulator_attribute_values,
    )

    callbacks["component_state"].assert_not_called()
