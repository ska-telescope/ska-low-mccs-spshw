# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests of the subrack Tango device."""
from __future__ import annotations

import gc
import json
from typing import Any, Generator

import pytest
from ska_control_model import AdminMode, PowerState, ResultCode
from ska_tango_testing.context import (
    TangoContextProtocol,
    ThreadedTestTangoContextManager,
)
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup
from tango import DeviceProxy, DevState, EventType

from ska_low_mccs_spshw.subrack import (
    FanMode,
    MccsSubrack,
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


@pytest.fixture(name="tango_harness")
def tango_harness_fixture(
    subrack_name: str,
    subrack_address: tuple[str, int],
) -> Generator[TangoContextProtocol, None, None]:
    """
    Return a Tango harness against which to run tests of the deployment.

    :param subrack_name: the name of the subrack Tango device
    :param subrack_address: the host and port of the subrack

    :yields: a tango context.
    """
    subrack_ip, subrack_port = subrack_address

    context_manager = ThreadedTestTangoContextManager()
    context_manager.add_device(
        subrack_name,
        "ska_low_mccs_spshw.MccsSubrack",
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
) -> DeviceProxy:
    """
    Fixture that returns the subrack Tango device under test.

    :param tango_harness: a test harness for Tango devices.
    :param subrack_name: name of the subrack Tango device.

    :yield: the subrack Tango device under test.
    """
    yield tango_harness.get_device(subrack_name)


def test_off_on(
    subrack_device: MccsSubrack,
    subrack_device_attribute_values: dict[str, Any],
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Test our ability to turn the subrack device off and back on.

    Since all our current facilities with a real hardware subrack do not
    yet provide the ability to turn the subrack off and on, the subrack
    tango device currently simulates an upstream power supply for the
    subrack, and this is on by default.

    Therefore when the tango device first connects to the subrack in
    this test, it will find it to be on. The test will switch it off,
    then back on again.

    :param subrack_device: the subrack Tango device under test.
    :param subrack_device_attribute_values: key-value dictionary of
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

    # There are heaps of attribute we can subscribe to here.
    # We'll subscribe to all of them in the next test.
    # Here, let's just subscribe to one, just to satisfy ourself that
    # things are really working.
    subrack_device.subscribe_event(
        "boardCurrent",
        EventType.CHANGE_EVENT,
        change_event_callbacks["boardCurrent"],
    )
    change_event_callbacks["boardCurrent"].assert_change_event(None)
    change_event_callbacks["boardCurrent"].assert_not_called()

    # Now let's put the device online
    subrack_device.adminMode = AdminMode.ONLINE  # type: ignore[assignment]
    change_event_callbacks["state"].assert_change_event(DevState.UNKNOWN)
    change_event_callbacks["state"].assert_change_event(DevState.ON)
    change_event_callbacks["state"].assert_not_called()

    change_event_callbacks["boardCurrent"].assert_change_event(
        subrack_device_attribute_values["boardCurrent"],
    )

    # It's on, so let's turn it off.
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

    ([result_code], [off_command_id]) = subrack_device.Off()
    assert result_code == ResultCode.QUEUED

    change_event_callbacks["command_status"].assert_change_event(
        (off_command_id, "QUEUED")
    )
    change_event_callbacks["command_status"].assert_change_event(
        (off_command_id, "IN_PROGRESS")
    )
    change_event_callbacks["state"].assert_change_event(DevState.OFF)
    change_event_callbacks["state"].assert_not_called()

    assert subrack_device.state() == DevState.OFF

    change_event_callbacks["command_result"].assert_change_event(
        (
            off_command_id,
            json.dumps([int(ResultCode.OK), "Command completed"]),
        ),
    )
    change_event_callbacks["command_status"].assert_change_event(
        (off_command_id, "COMPLETED")
    )

    change_event_callbacks["boardCurrent"].assert_change_event([])
    assert subrack_device.boardCurrent is None

    # Okay, let's turn it back on again,
    # but we can't be bothered tracking the command status this time.
    _ = subrack_device.On()

    change_event_callbacks["state"].assert_change_event(DevState.UNKNOWN)
    change_event_callbacks["state"].assert_change_event(DevState.ON)
    change_event_callbacks["state"].assert_not_called()

    assert subrack_device.state() == DevState.ON

    change_event_callbacks["boardCurrent"].assert_change_event(
        subrack_device_attribute_values["boardCurrent"],
    )


def test_monitoring_and_control(  # pylint: disable=too-many-locals, too-many-statements
    subrack_device: MccsSubrack,
    subrack_simulator: SubrackSimulator,
    subrack_device_attribute_values: dict[str, Any],
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
    :param subrack_device_attribute_values: key-value dictionary of
        the expected subrack device attribute values
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

    for attribute_name, expected_initial_value in [
        ("tpmPresent", None),
        ("tpmCount", 0),
        ("tpm1PowerState", PowerState.UNKNOWN),
        ("tpm2PowerState", PowerState.UNKNOWN),
        ("tpm3PowerState", PowerState.UNKNOWN),
        ("tpm4PowerState", PowerState.UNKNOWN),
        ("tpm5PowerState", PowerState.UNKNOWN),
        ("tpm6PowerState", PowerState.UNKNOWN),
        ("tpm7PowerState", PowerState.UNKNOWN),
        ("tpm8PowerState", PowerState.UNKNOWN),
        ("backplaneTemperatures", None),
        ("boardTemperatures", None),
        ("boardCurrent", None),
        ("powerSupplyCurrents", None),
        ("powerSupplyFanSpeeds", None),
        ("powerSupplyPowers", None),
        ("powerSupplyVoltages", None),
        ("subrackFanSpeeds", None),
        ("subrackFanSpeedsPercent", None),
        ("subrackFanModes", None),
        ("tpmCurrents", None),
        ("tpmPowers", None),
        ("tpmTemperatures", None),
        ("tpmVoltages", None),
    ]:
        subrack_device.subscribe_event(
            attribute_name,
            EventType.CHANGE_EVENT,
            change_event_callbacks[attribute_name],
        )
        change_event_callbacks[attribute_name].assert_change_event(
            expected_initial_value
        )
        change_event_callbacks[attribute_name].assert_not_called()

    # Now let's put the device online
    subrack_device.adminMode = AdminMode.ONLINE  # type: ignore[assignment]
    change_event_callbacks["state"].assert_change_event(DevState.UNKNOWN)
    change_event_callbacks["state"].assert_change_event(DevState.ON)
    change_event_callbacks["state"].assert_not_called()

    change_event_callbacks["tpmCount"].assert_change_event(
        subrack_device_attribute_values["tpmPresent"].count(True)
    )
    for tpm_number in range(1, SubrackData.TPM_BAY_COUNT + 1):
        expected_is_on = subrack_device_attribute_values["tpmOnOff"][tpm_number - 1]
        expected_power_state = PowerState.ON if expected_is_on else PowerState.OFF
        change_event_callbacks[f"tpm{tpm_number}PowerState"].assert_change_event(
            expected_power_state
        )

    change_event_callbacks["boardCurrent"].assert_change_event(
        subrack_device_attribute_values["boardCurrent"]
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
        change_event_callbacks[attribute_name].assert_change_event(
            subrack_device_attribute_values[attribute_name]
        )

    # Let's change a value in the simulator and check that a change event is pushed.
    subrack_simulator.simulate_attribute("board_current", 0.7)
    change_event_callbacks["boardCurrent"].assert_change_event([pytest.approx(0.7)])

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
    percent_to_set = 99.0
    power_supply_fan_speeds = subrack_device.powerSupplyFanSpeeds
    expected_speeds = [pytest.approx(i) for i in power_supply_fan_speeds]
    expected_speeds[fan_to_change - 1] = pytest.approx(percent_to_set)

    json_kwargs = json.dumps(
        {"power_supply_fan_id": fan_to_change, "speed_percent": percent_to_set}
    )
    _ = subrack_device.SetPowerSupplyFanSpeed(json_kwargs)
    change_event_callbacks["powerSupplyFanSpeeds"].assert_change_event(expected_speeds)

    fan_to_change = 2
    percent_to_set = 49.0
    subrack_fan_speeds_percent = subrack_device.subrackFanSpeedsPercent
    expected_speeds_percent = [pytest.approx(i) for i in subrack_fan_speeds_percent]
    expected_speeds_percent[fan_to_change - 1] = pytest.approx(percent_to_set)

    subrack_fan_speeds = subrack_device.subrackFanSpeeds
    expected_speeds = [pytest.approx(i) for i in subrack_fan_speeds]
    expected_speeds[fan_to_change - 1] = pytest.approx(
        percent_to_set * SubrackData.MAX_SUBRACK_FAN_SPEED / 100.0
    )

    json_kwargs = json.dumps(
        {"subrack_fan_id": fan_to_change, "speed_percent": percent_to_set}
    )
    _ = subrack_device.SetSubrackFanSpeed(json_kwargs)

    change_event_callbacks["subrackFanSpeedsPercent"].assert_change_event(
        expected_speeds_percent
    )
    change_event_callbacks["subrackFanSpeeds"].assert_change_event(expected_speeds)

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

    change_event_callbacks["subrackFanModes"].assert_change_event(expected_modes)
