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
import time
from typing import Any, Iterator

import pytest
from ska_control_model import AdminMode, PowerState, ResultCode
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup
from tango import DeviceProxy, DevState, EventType

from ska_low_mccs_spshw.subrack import (
    FanMode,
    MccsSubrack,
    SubrackData,
    SubrackSimulator,
)
from tests.harness import SpsTangoTestHarness, SpsTangoTestHarnessContext

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
        # "tpmTemperatures",  # Not implemented on SMB
        "tpmVoltages",
        "adminMode",
        timeout=20.0,
        assert_no_error=False,
    )


@pytest.fixture(name="test_context")
def test_context_fixture(
    subrack_id: int,
    subrack_simulator: SubrackSimulator,
) -> Iterator[SpsTangoTestHarnessContext]:
    """
    Return a test context in which both subrack simulator and Tango device are running.

    :param subrack_id: the ID of the subrack under test
    :param subrack_simulator: the backend simulator that the Tango
        device will monitor and control

    :yields: a test context.
    """
    harness = SpsTangoTestHarness()
    harness.add_subrack_simulator(subrack_id, subrack_simulator)
    harness.add_subrack_device(subrack_id)

    with harness as context:
        yield context


@pytest.fixture(name="subrack_device")
def subrack_device_fixture(
    test_context: SpsTangoTestHarnessContext,
    subrack_id: int,
) -> DeviceProxy:
    """
    Fixture that returns the subrack Tango device under test.

    :param test_context: a test context in which both
        subrack simulator and subrack Tango device are running.
    :param subrack_id: ID of the subrack.

    :yield: the subrack Tango device under test.
    """
    yield test_context.get_subrack_device(subrack_id)


def test_fast_adminMode_switch(
    subrack_device: MccsSubrack,
    subrack_simulator: SubrackSimulator,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Test our ability to deal with a quick succession of communication commands.

    :param subrack_device: the subrack Tango device under test.
    :param subrack_simulator: the simulator for the backend
    :param change_event_callbacks: dictionary of Tango change event
        callbacks with asynchrony support.
    """
    subrack_device.loggingLevel = 4  # type: ignore[assignment]
    subrack_device.subscribe_event(
        "state",
        EventType.CHANGE_EVENT,
        change_event_callbacks["state"],
    )
    change_event_callbacks["state"].assert_change_event(DevState.DISABLE)
    subrack_device.subscribe_event(
        "adminMode",
        EventType.CHANGE_EVENT,
        change_event_callbacks["adminMode"],
    )

    for i in range(3):
        # run test using a variable network jitter.
        max_jitter: int = (i * 100) % 600  # milliseconds
        subrack_simulator.network_jitter_limits = (0, max_jitter)
        subrack_device.adminMode = AdminMode.ONLINE  # type: ignore[assignment]
        change_event_callbacks["state"].assert_change_event(DevState.UNKNOWN)
        change_event_callbacks["state"].assert_change_event(DevState.ON)

        subrack_device.adminmode = AdminMode.OFFLINE
        change_event_callbacks["state"].assert_change_event(DevState.DISABLE)

        subrack_device.adminmode = AdminMode.ONLINE
        change_event_callbacks["state"].assert_change_event(DevState.UNKNOWN)
        change_event_callbacks["state"].assert_change_event(DevState.ON)

        number_of_communication_cycles: int = 4

        change_event_callbacks["adminMode"].assert_change_event(AdminMode.OFFLINE)
        change_event_callbacks["adminMode"].assert_change_event(AdminMode.ONLINE)
        change_event_callbacks["adminMode"].assert_change_event(AdminMode.OFFLINE)
        change_event_callbacks["adminMode"].assert_change_event(AdminMode.ONLINE)

        for _ in range(number_of_communication_cycles):
            subrack_device.adminmode = AdminMode.OFFLINE
            subrack_device.adminmode = AdminMode.ONLINE

        # When cycling adminmode ONLINE n times we expect up to n
        # transitions to DevState.ON. The important point is that is end
        # up in a steady ON state.
        for _ in range(number_of_communication_cycles):
            change_event_callbacks["adminMode"].assert_change_event(AdminMode.OFFLINE)
            change_event_callbacks["adminMode"].assert_change_event(AdminMode.ONLINE)
            try:
                # lookahead of 3 since we allow UNKNOWN and DISABLE as
                # transient states.
                change_event_callbacks["state"].assert_change_event(
                    DevState.ON, lookahead=3, consume_nonmatches=True
                )
            except AssertionError:
                print("Transition state ON allowed to not occur.")

        change_event_callbacks["state"].assert_not_called()
        assert subrack_device.adminMode == AdminMode.ONLINE
        assert subrack_device.state() == DevState.ON

        subrack_device.adminmode = AdminMode.OFFLINE
        change_event_callbacks["state"].assert_change_event(DevState.DISABLE)
        print(f"Iteration {i}")


def test_failed_poll(
    subrack_device: MccsSubrack,
    subrack_simulator: SubrackSimulator,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Test our ability to handle a transient failure.

    A poll can fail for a number of reasons, namely:
      - A connection timeout
      - An unhandled exception raised in firmware (TODO MCCS-1329)
      - Other.. (TODO MCCS-1329)

    :param subrack_device: the subrack Tango device under test.
    :param subrack_simulator: the simulator for the backend
    :param change_event_callbacks: dictionary of Tango change event
        callbacks with asynchrony support.
    """
    subrack_device.subscribe_event(
        "state",
        EventType.CHANGE_EVENT,
        change_event_callbacks["state"],
    )
    change_event_callbacks["state"].assert_change_event(DevState.DISABLE)
    subrack_device.adminMode = AdminMode.ONLINE  # type: ignore[assignment]
    change_event_callbacks["state"].assert_change_event(DevState.UNKNOWN)
    change_event_callbacks["state"].assert_change_event(DevState.ON)
    # simulate a large network latency
    min_jitter: int = 10_000  # milliseconds
    max_jitter: int = 15_000  # milliseconds
    subrack_simulator.network_jitter_limits = (min_jitter, max_jitter)
    # sleep to allow timeout.
    time.sleep(min_jitter / 1000)
    change_event_callbacks["state"].assert_change_event(DevState.UNKNOWN)
    subrack_simulator.network_jitter_limits = (0, 0)
    change_event_callbacks["state"].assert_change_event(DevState.ON)
    change_event_callbacks["state"].assert_not_called()


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
    change_event_callbacks["boardCurrent"].assert_change_event([])
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

    change_event_callbacks["command_status"].assert_change_event(())

    subrack_device.subscribe_event(
        "longRunningCommandResult",
        EventType.CHANGE_EVENT,
        change_event_callbacks["command_result"],
    )
    change_event_callbacks["command_result"].assert_change_event(("", ""))

    ([result_code], [off_command_id]) = subrack_device.Off()
    assert result_code == ResultCode.QUEUED

    change_event_callbacks["command_status"].assert_change_event(
        (off_command_id, "STAGING")
    )
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
    assert not list(subrack_device.boardCurrent)

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
        ("tpmPresent", []),
        ("tpmCount", 0),
        ("tpm1PowerState", PowerState.UNKNOWN),
        ("tpm2PowerState", PowerState.UNKNOWN),
        ("tpm3PowerState", PowerState.UNKNOWN),
        ("tpm4PowerState", PowerState.UNKNOWN),
        ("tpm5PowerState", PowerState.UNKNOWN),
        ("tpm6PowerState", PowerState.UNKNOWN),
        ("tpm7PowerState", PowerState.UNKNOWN),
        ("tpm8PowerState", PowerState.UNKNOWN),
        ("backplaneTemperatures", []),
        ("boardTemperatures", []),
        ("boardCurrent", []),
        ("cpldPllLocked", None),
        ("powerSupplyCurrents", []),
        ("powerSupplyFanSpeeds", []),
        ("powerSupplyPowers", []),
        ("powerSupplyVoltages", []),
        ("subrackFanSpeeds", []),
        ("subrackFanSpeedsPercent", []),
        ("subrackFanModes", []),
        ("subrackPllLocked", None),
        ("subrackTimestamp", None),
        ("tpmCurrents", []),
        ("tpmPowers", []),
        # ("tpmTemperatures", []),  # Not implemented on SMB
        ("tpmVoltages", []),
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

    for attribute_name in [
        "boardCurrent",
        "cpldPllLocked",
        "subrackPllLocked",
        "subrackTimestamp",
    ]:
        change_event_callbacks[attribute_name].assert_change_event(
            subrack_device_attribute_values[attribute_name]
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
        # "tpmTemperatures",  # Not implemented on SMB
        "tpmVoltages",
    ]:
        change_event_callbacks[attribute_name].assert_change_event(
            subrack_device_attribute_values[attribute_name]
        )

    # Let's change a value in the simulator and check that a change event is pushed.
    subrack_simulator.simulate_attribute("board_current", 0.7)
    change_event_callbacks["boardCurrent"].assert_change_event([pytest.approx(0.7)])

    # Now let's try a command
    subrack_device.subscribe_event(
        "longRunningCommandStatus",
        EventType.CHANGE_EVENT,
        change_event_callbacks["command_status"],
    )

    change_event_callbacks["command_status"].assert_change_event(())

    subrack_device.subscribe_event(
        "longRunningCommandResult",
        EventType.CHANGE_EVENT,
        change_event_callbacks["command_result"],
    )
    change_event_callbacks["command_result"].assert_change_event(("", ""))

    tpm_present = list(subrack_device.tpmPresent)
    tpm_to_power = tpm_present.index(True) + 1
    power_state = getattr(subrack_device, f"tpm{tpm_to_power}PowerState")
    if power_state == PowerState.OFF:
        expected_power_state = PowerState.ON

        ([result_code], [tpm_on_command_id]) = subrack_device.PowerOnTpm(tpm_to_power)
        assert result_code == ResultCode.QUEUED

        change_event_callbacks["command_status"].assert_change_event(
            (tpm_on_command_id, "STAGING")
        )
        change_event_callbacks["command_status"].assert_change_event(
            (tpm_on_command_id, "QUEUED")
        )
        change_event_callbacks["command_status"].assert_change_event(
            (tpm_on_command_id, "IN_PROGRESS")
        )

        change_event_callbacks[f"tpm{tpm_to_power}PowerState"].assert_change_event(
            PowerState.ON
        )

        change_event_callbacks["command_result"].assert_change_event(
            (
                tpm_on_command_id,
                json.dumps([int(ResultCode.OK), "Command completed."]),
            ),
        )
        change_event_callbacks["command_status"].assert_change_event(
            (tpm_on_command_id, "COMPLETED")
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
    subrack_fan_mode = subrack_device.subrackFanModes
    if subrack_fan_mode[fan_to_change - 1] == FanMode.AUTO:
        mode_to_set = FanMode.MANUAL
    else:
        mode_to_set = FanMode.AUTO
    expected_modes = list(subrack_fan_mode)
    expected_modes[fan_to_change - 1] = mode_to_set
    json_kwargs = json.dumps({"fan_id": fan_to_change, "mode": int(mode_to_set)})
    _ = subrack_device.SetSubrackFanMode(json_kwargs)

    change_event_callbacks["subrackFanModes"].assert_change_event(expected_modes)


def test_subrack_connection_lost(
    subrack_device: MccsSubrack,
    subrack_simulator: SubrackSimulator,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Test our ability to rediscover attribute state after outage.

    :param subrack_device: the subrack Tango device under test.
    :param subrack_simulator: the simulator for the backend
    :param change_event_callbacks: dictionary of Tango change event
        callbacks with asynchrony support.
    """
    subrack_device.subscribe_event(
        "state",
        EventType.CHANGE_EVENT,
        change_event_callbacks["state"],
    )
    change_event_callbacks["state"].assert_change_event(DevState.DISABLE)
    subrack_device.subscribe_event(
        "tpm1PowerState",
        EventType.CHANGE_EVENT,
        change_event_callbacks["tpm1PowerState"],
    )
    change_event_callbacks["tpm1PowerState"].assert_change_event(PowerState.UNKNOWN)
    subrack_device.subscribe_event(
        "adminMode",
        EventType.CHANGE_EVENT,
        change_event_callbacks["adminMode"],
    )

    subrack_device.adminMode = AdminMode.ONLINE  # type: ignore[assignment]
    change_event_callbacks["state"].assert_change_event(
        DevState.UNKNOWN, lookahead=5, consume_nonmatches=True
    )
    change_event_callbacks["state"].assert_change_event(
        DevState.ON, lookahead=5, consume_nonmatches=True
    )

    change_event_callbacks["tpm1PowerState"].assert_change_event(PowerState.OFF)

    # simulate a drop out in connection
    subrack_simulator.network_jitter_limits = (10_000, 11_000)
    # change_event_callbacks["state"].assert_not_called()
    change_event_callbacks["state"].assert_change_event(
        DevState.UNKNOWN, lookahead=5, consume_nonmatches=True
    )
    change_event_callbacks["tpm1PowerState"].assert_change_event(PowerState.UNKNOWN)

    # simulate a connection resumed
    subrack_simulator.network_jitter_limits = (0, 1_000)
    change_event_callbacks["state"].assert_change_event(DevState.ON)

    # Check that attribute state rediscovered
    change_event_callbacks["tpm1PowerState"].assert_change_event(PowerState.OFF)
