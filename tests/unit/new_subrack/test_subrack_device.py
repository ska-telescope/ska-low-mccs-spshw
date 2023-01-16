# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests of the subrack Tangod device."""
from __future__ import annotations

import gc
import json
from typing import Any, Generator

import pytest
from ska_control_model import AdminMode, PowerState, ResultCode
from ska_low_mccs_common import MccsDeviceProxy
from ska_tango_testing.context import (
    TangoContextProtocol,
    ThreadedTestTangoContextManager,
)
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup
from tango import AttrQuality, DevState, EventType

from ska_low_mccs_spshw.subrack import (
    FanMode,
    NewSubrackDevice,
    SubrackData,
    SubrackSimulator,
)

# TODO: Weird hang-at-garbage-collection bug
gc.disable()


@pytest.fixture(name="change_event_callbacks")
def change_event_callbacks_fixture() -> MockTangoEventCallbackGroup:
    """
    Return a dictionary of callables to be used as Tango change event callbacks.

    :return: a dictionary of callables to be used as tango change event
        callbacks.
    """
    return MockTangoEventCallbackGroup(
        "state",
        "command_status",
        "command_result",
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
        "powerSupplyCurrents",
        "powerSupplyFanSpeeds",
        "powerSupplyPowers",
        "powerSupplyVoltages",
        "subrackFanSpeeds",
        "subrackFanSpeedsPercent",
        "subrackFanModes",
        "tpmCurrents",
        "tpmPowers",
        "tpmTemperatures",
        "tpmVoltages",
        timeout=2.0,
    )


@pytest.fixture(name="subrack_name")
def subrack_name_fixture() -> str:
    """
    Return the name of the subrack Tango device.

    :return: the name of the subrack Tango device.
    """
    return "low-mccs/subrack/01"


@pytest.fixture(name="tango_harness")
def tango_harness_fixture(
    subrack_name: str,
    subrack_ip: str,
    subrack_port: int,
) -> Generator[TangoContextProtocol, None, None]:
    """
    Return a Tango harness against which to run tests of the deployment.

    :param subrack_name: the name of the subrack Tango device
    :param subrack_ip: the hostname or IP address of the subrack
        management board web server
    :param subrack_port: the port of the subrack management board web
        server

    :yields: a tango context.
    """
    context_manager = ThreadedTestTangoContextManager()
    context_manager.add_device(
        subrack_name,
        "ska_low_mccs_spshw.NewSubrackDevice",
        SubrackIp=subrack_ip,
        SubrackPort=subrack_port,
        UpdateRate=1.0,
        LoggingLevelDefault=5,
    )
    with context_manager as context:
        yield context


@pytest.fixture(name="subrack_device")
def subrack_device_fixture(
    tango_harness: TangoContextProtocol,
    subrack_name: str,
) -> MccsDeviceProxy:
    """
    Fixture that returns the subrack Tango device under test.

    :param tango_harness: a test harness for Tango devices.
    :param subrack_name: name of the subrack Tango device.

    :return: the subrack Tango device under test.
    """
    return tango_harness.get_device(subrack_name)


def test(  # pylint: disable=too-many-locals, too-many-statements
    subrack_device: NewSubrackDevice,
    subrack_simulator: SubrackSimulator,
    subrack_simulator_attribute_values: dict[str, Any],
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Test the subrack device.

    This is a very long test that takes the device through its paces.
    It works by subscribing to change events of virtually all available
    attributes, then acting on the device and checking that the right
    change events are fired.

    The actions taken are:
    * subscribe to events
    * put it online
    * turn it on
    * make the simulator report new values

    :param subrack_device: the subrack Tango device under test.
    :param subrack_simulator: the subrack simulator backend that the
        subrack driver drives through its server interface
    :param subrack_simulator_attribute_values: key-value dictionary of
        the expected subrack simulator attribute values
    :param change_event_callbacks: dictionary of Tango change event
        callbacks with asynchrony support.
    """
    # First let's check the initial state
    assert subrack_device.adminMode == AdminMode.OFFLINE

    subrack_device.subscribe_event(
        "state",
        EventType.CHANGE_EVENT,
        change_event_callbacks["state"],
    )
    change_event_callbacks["state"].assert_change_event(DevState.DISABLE)
    change_event_callbacks["state"].assert_not_called()

    for attribute_name, expected_initial_value, expected_initial_quality in [
        ("tpmPresent", None, AttrQuality.ATTR_INVALID),
        ("tpmCount", None, AttrQuality.ATTR_INVALID),
        # TODO: https://gitlab.com/tango-controls/pytango/-/issues/498
        ("tpm1PowerState", PowerState.UNKNOWN, AttrQuality.ATTR_VALID),
        ("tpm2PowerState", PowerState.UNKNOWN, AttrQuality.ATTR_VALID),
        ("tpm3PowerState", PowerState.UNKNOWN, AttrQuality.ATTR_VALID),
        ("tpm4PowerState", PowerState.UNKNOWN, AttrQuality.ATTR_VALID),
        ("tpm5PowerState", PowerState.UNKNOWN, AttrQuality.ATTR_VALID),
        ("tpm6PowerState", PowerState.UNKNOWN, AttrQuality.ATTR_VALID),
        ("tpm7PowerState", PowerState.UNKNOWN, AttrQuality.ATTR_VALID),
        ("tpm8PowerState", PowerState.UNKNOWN, AttrQuality.ATTR_VALID),
        ("backplaneTemperatures", None, AttrQuality.ATTR_INVALID),
        ("boardTemperatures", None, AttrQuality.ATTR_INVALID),
        ("boardCurrent", None, AttrQuality.ATTR_INVALID),
        ("powerSupplyCurrents", None, AttrQuality.ATTR_INVALID),
        ("powerSupplyFanSpeeds", None, AttrQuality.ATTR_INVALID),
        ("powerSupplyPowers", None, AttrQuality.ATTR_INVALID),
        ("powerSupplyVoltages", None, AttrQuality.ATTR_INVALID),
        ("subrackFanSpeeds", None, AttrQuality.ATTR_INVALID),
        ("subrackFanSpeedsPercent", None, AttrQuality.ATTR_INVALID),
        ("subrackFanModes", None, AttrQuality.ATTR_INVALID),
        ("tpmCurrents", None, AttrQuality.ATTR_INVALID),
        ("tpmPowers", None, AttrQuality.ATTR_INVALID),
        ("tpmTemperatures", None, AttrQuality.ATTR_INVALID),
        ("tpmVoltages", None, AttrQuality.ATTR_INVALID),
    ]:
        subrack_device.subscribe_event(
            attribute_name,
            EventType.CHANGE_EVENT,
            change_event_callbacks[attribute_name],
        )
        change_event_callbacks[attribute_name].assert_against_call(
            attribute_value=expected_initial_value,
            attribute_quality=expected_initial_quality,
        )
        change_event_callbacks[attribute_name].assert_not_called()

    # Now let's put the device online
    subrack_device.adminMode = AdminMode.ONLINE  # type: ignore[assignment]
    change_event_callbacks["state"].assert_change_event(DevState.UNKNOWN)
    change_event_callbacks["state"].assert_change_event(DevState.OFF)
    change_event_callbacks["state"].assert_not_called()

    # It's off, so let's turn it on.
    subrack_device.subscribe_event(
        "longRunningCommandStatus",
        EventType.CHANGE_EVENT,
        change_event_callbacks["command_status"],
    )

    change_event_callbacks["command_status"].assert_change_event(None)

    subrack_device.subscribe_event(
        "longRunningCommandResult",
        EventType.CHANGE_EVENT,
        change_event_callbacks["command_result"],
    )
    change_event_callbacks["command_result"].assert_change_event(("", ""))

    ([result_code], [on_command_id]) = subrack_device.On()
    assert result_code == ResultCode.QUEUED

    change_event_callbacks["command_status"].assert_change_event(
        (on_command_id, "QUEUED")
    )
    change_event_callbacks["command_status"].assert_change_event(
        (on_command_id, "IN_PROGRESS")
    )
    change_event_callbacks["state"].assert_change_event(DevState.UNKNOWN)
    change_event_callbacks["state"].assert_change_event(DevState.ON)
    change_event_callbacks["state"].assert_not_called()

    assert subrack_device.state() == DevState.ON

    change_event_callbacks["command_result"].assert_change_event(
        (
            on_command_id,
            json.dumps([int(ResultCode.OK), "Command completed"]),
        ),
    )
    change_event_callbacks["command_status"].assert_change_event(
        (on_command_id, "COMPLETED")
    )

    change_event_callbacks["tpmCount"].assert_change_event(
        subrack_simulator_attribute_values["tpm_present"].count(True)
    )
    for tpm_number in range(1, SubrackData.TPM_BAY_COUNT + 1):
        expected_is_on = subrack_simulator_attribute_values["tpm_on_off"][
            tpm_number - 1
        ]
        expected_power_state = PowerState.ON if expected_is_on else PowerState.OFF
        change_event_callbacks[f"tpm{tpm_number}PowerState"].assert_change_event(
            expected_power_state
        )

    change_event_callbacks["boardCurrent"].assert_change_event(
        subrack_simulator_attribute_values["board_current"]
    )

    # TODO: Tango events provide array values as numpy arrays, and numpy
    # refuses to compare arrays using equality:
    #     "ValueError: The truth value of an array with more than one element
    #     is ambiguous. Use a.any() or a.all()"
    # ska-tango-testing v0.5.2 already provides support for this,
    # but we're not using ska-tango-testing yet.
    # For now, let's just assert that we'll receive _something_ valid for each
    # array attribute:
    for attribute_name in [
        "tpmPresent",
        "backplaneTemperatures",
        "boardTemperatures",
        "powerSupplyCurrents",
        "powerSupplyFanSpeeds",
        "powerSupplyPowers",
        "powerSupplyVoltages",
        "subrackFanSpeeds",
        "subrackFanSpeedsPercent",
        "subrackFanModes",
        "tpmCurrents",
        "tpmPowers",
        "tpmTemperatures",
        "tpmVoltages",
    ]:
        change_event_callbacks[attribute_name].assert_against_call(
            attribute_quality=AttrQuality.ATTR_VALID
        )

    # Let's change a value in the simulator and check that a change event is pushed.
    subrack_simulator.simulate_attribute("board_current", 0.7)
    change_event_callbacks["boardCurrent"].assert_change_event(pytest.approx(0.7))

    # Now let's try a command
    tpm_present = list(subrack_device.tpmPresent)
    tpm_to_power = tpm_present.index(True) + 1
    power_state = getattr(subrack_device, f"tpm{tpm_to_power}PowerState")
    if power_state == PowerState.OFF:
        expected_power_state = PowerState.ON
        _ = subrack_device.PowerOnTpm(tpm_to_power)
        change_event_callbacks[f"tpm{tpm_to_power}PowerState"].assert_change_event(
            PowerState.ON
        )

    _ = subrack_device.PowerDownTpms()
    # There may be many TPMs that power down,
    # but for now this test just checks that the one that it knows is on
    # gets turned off.
    change_event_callbacks[f"tpm{tpm_to_power}PowerState"].assert_change_event(
        PowerState.OFF
    )

    _ = subrack_device.PowerUpTpms()
    # Again, we just check that one TPM gets powered up.
    change_event_callbacks[f"tpm{tpm_to_power}PowerState"].assert_change_event(
        PowerState.ON
    )

    _ = subrack_device.PowerOffTpm(tpm_to_power)
    change_event_callbacks[f"tpm{tpm_to_power}PowerState"].assert_change_event(
        PowerState.OFF
    )

    fan_to_change = 1
    percent_to_set = 51.0
    power_supply_fan_speeds = subrack_device.powerSupplyFanSpeeds
    expected_speeds = [pytest.approx(i) for i in power_supply_fan_speeds]
    expected_speeds[fan_to_change - 1] = pytest.approx(percent_to_set)

    json_kwargs = json.dumps(
        {"power_supply_fan_id": fan_to_change, "speed_percent": percent_to_set}
    )
    _ = subrack_device.SetPowerSupplyFanSpeed(json_kwargs)

    # TODO: again with the numpy array attributes!
    call_details = change_event_callbacks["powerSupplyFanSpeeds"].assert_against_call()
    new_speeds = call_details["attribute_value"]
    assert list(new_speeds) == expected_speeds

    fan_to_change = 2
    percent_to_set = 49.0
    subrack_fan_speeds = subrack_device.subrackFanSpeeds
    expected_speeds = [pytest.approx(i) for i in subrack_fan_speeds]
    expected_speeds[fan_to_change - 1] = pytest.approx(percent_to_set)
    json_kwargs = json.dumps(
        {"subrack_fan_id": fan_to_change, "speed_percent": percent_to_set}
    )
    _ = subrack_device.SetSubrackFanSpeed(json_kwargs)

    # TODO: again with the numpy array attributes!
    call_details = change_event_callbacks["subrackFanSpeeds"].assert_against_call()
    new_speeds = call_details["attribute_value"]
    assert list(new_speeds) == expected_speeds

    fan_to_change = 3
    subrack_fan_modes = subrack_device.subrackFanModes
    if subrack_fan_modes[fan_to_change - 1] == FanMode.AUTO:
        mode_to_set = FanMode.MANUAL
    else:
        mode_to_set = FanMode.AUTO
    expected_modes = list(subrack_fan_modes)
    expected_modes[fan_to_change - 1] = mode_to_set
    json_kwargs = json.dumps({"fan_id": fan_to_change, "mode": int(mode_to_set)})
    _ = subrack_device.SetSubrackFanMode(json_kwargs)

    # TODO: again with the numpy array attributes!
    call_details = change_event_callbacks["subrackFanModes"].assert_against_call()
    new_modes = call_details["attribute_value"]
    assert list(new_modes) == expected_modes
