# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
This module contains functional tests of the MCCS subrack Tango device.

These tests are targetted at real hardware. Currently all available
subracks cannot be programmatically powered off and on. Therefore these
tests do not cover these cases. They assume the subrack to be always on,
and test its functionality.
"""
from __future__ import annotations

import enum
import json

import pytest
import tango
from pytest_bdd import given, parsers, scenario, then, when
from ska_control_model import AdminMode, PowerState
from ska_tango_testing.context import TangoContextProtocol
from ska_tango_testing.mock.placeholders import Anything, OneOf
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup

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

    MANUAL = 1
    AUTO = 2


@pytest.fixture(name="subrack_device", scope="module")
def subrack_device_fixture(
    tango_harness: TangoContextProtocol,
    subrack_name: str,
) -> tango.DeviceProxy:
    """
    Return the subrack device under test.

    :param tango_harness: a test harness for Tango devices.
    :param subrack_name: name of the subrack Tango device.

    :return: the subrack Tango device under test.
    """
    return tango_harness.get_device(subrack_name)


@scenario("features/subrack.feature", "Monitor and control subrack fan speed")
def test_monitor_and_control_subrack_fan_speed() -> None:
    """
    Run a test scenario that monitors and controls a subrack fan's speed.

    Any code in this scenario function is run at the *end* of the
    scenario.
    """


@scenario("features/subrack.feature", "Turn on a TPM")
def test_turn_on_tpm() -> None:
    """
    Run a test scenario that tells a subrack to turn on a TPM.

    Any code in this scenario function is run at the *end* of the
    scenario.
    """


@scenario("features/subrack.feature", "Turn off all TPMs")
def test_turn_off_tpms() -> None:
    """
    Run a test scenario that tells a subrack to turn off all TPMs.

    Any code in this scenario function is run at the *end* of the
    scenario.
    """


@given("a subrack that is online and on")
def check_subrack_is_online_and_on(
    subrack_device: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Check that the subrack is online and on.

    :param subrack_device: the subrack Tango device under test.
    :param change_event_callbacks: dictionary of Tango change event
        callbacks with asynchrony support.
    """
    admin_mode = subrack_device.adminMode
    print(f"Subrack device is in admin_mode {admin_mode.name}")
    assert admin_mode in [AdminMode.OFFLINE, AdminMode.ONLINE, AdminMode.MAINTENANCE]

    subrack_device.subscribe_event(
        "state",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["subrack_state"],
    )

    # Test can run in ONLINE or MAINTENANCE admin mode,
    # so we only need to act if the admin mode is OFFLINE
    if admin_mode == AdminMode.OFFLINE:
        change_event_callbacks.assert_change_event(
            "subrack_state", tango.DevState.DISABLE
        )
        print("Subrack device is in DISABLE state.")
        print("Putting subrack device ONLINE...")
        subrack_device.adminMode = AdminMode.ONLINE
        change_event_callbacks.assert_change_event(
            "subrack_state", tango.DevState.UNKNOWN
        )
        print("Subrack device is in UNKNOWN state.")

    change_event_callbacks.assert_change_event(
        "subrack_state",
        OneOf(tango.DevState.OFF, tango.DevState.ON),
    )
    state = subrack_device.state()

    if state == tango.DevState.OFF:
        print("Subrack device is in OFF state.")
        print("Turning subrack device on...")
        subrack_device.On()

        change_event_callbacks.assert_change_event(
            "subrack_state",
            tango.DevState.UNKNOWN,
        )
        print("Subrack device is in UNKNOWN state.")

        change_event_callbacks.assert_change_event(
            "subrack_state",
            tango.DevState.ON,
        )

    assert subrack_device.state() == tango.DevState.ON
    print("Subrack device is in ON state.")


@given("a choice of subrack fan", target_fixture="fan_number")
def choose_a_fan() -> int:
    """
    Return a fan number.

    :return: a fan number.
    """
    return 1


@given("a choice of TPM", target_fixture="tpm_number")
def choose_a_tpm() -> int:
    """
    Return a TPM number.

    :return: a TPM number.
    """
    return 5


@given("the fan mode is manual")
def ensure_subrack_fan_mode(
    subrack_device: tango.DeviceProxy,
    fan_number: int,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Ensure that the fan is in manual mode.

    :param subrack_device: the subrack Tango device under test.
    :param fan_number: number of the subrack fan being exercised by this
        test.
    :param change_event_callbacks: dictionary of Tango change event
        callbacks with asynchrony support.
    """
    fan_modes = subrack_device.subrackFanModes
    if fan_modes is not None:
        fan_modes = list(fan_modes)  # from numpy

    subrack_device.subscribe_event(
        "subrackFanModes",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["subrack_fan_mode"],
    )
    change_event_callbacks.assert_change_event(
        "subrack_fan_mode",
        fan_modes,
    )

    if fan_modes is None:
        # We only just put it online / turned it on,
        # so let's wait for a poll to return a real value
        change_event_callbacks.assert_change_event("subrack_fan_mode", Anything)
    fan_modes = subrack_device.subrackFanModes
    assert fan_modes is not None

    expected_fan_modes = list(fan_modes)
    if expected_fan_modes[fan_number - 1] == FanMode.AUTO:
        expected_fan_modes[fan_number - 1] = FanMode.MANUAL

        encoded_arg = json.dumps({"fan_id": fan_number, "mode": int(FanMode.MANUAL)})
        subrack_device.SetSubrackFanMode(encoded_arg)

        change_event_callbacks.assert_change_event(
            "subrack_fan_mode",
            expected_fan_modes,
        )


@given("the fan's speed setting is 90%")
def ensure_subrack_fan_speeds_percent(
    subrack_device: tango.DeviceProxy,
    fan_number: int,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Ensure that the fan is set to 90% speed.

    :param subrack_device: the subrack Tango device under test.
    :param fan_number: number of the subrack fan being exercised by this
        test.
    :param change_event_callbacks: dictionary of Tango change event
        callbacks with asynchrony support.
    """
    fan_speeds_percent = list(subrack_device.subrackFanSpeedsPercent)
    expected_fan_speeds_percent = [pytest.approx(s) for s in fan_speeds_percent]

    subrack_device.subscribe_event(
        "subrackFanSpeedsPercent",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["subrack_fan_speeds_percent"],
    )
    change_event_callbacks.assert_change_event(
        "subrack_fan_speeds_percent",
        expected_fan_speeds_percent,
    )

    speed_percent = fan_speeds_percent[fan_number - 1]
    if speed_percent != pytest.approx(90.0):
        encoded_arg = json.dumps({"subrack_fan_id": fan_number, "speed_percent": 90.0})
        subrack_device.SetSubrackFanSpeed(encoded_arg)
        expected_fan_speeds_percent[fan_number - 1] = pytest.approx(90.0)
        change_event_callbacks.assert_change_event(
            "subrack_fan_speeds_percent", expected_fan_speeds_percent
        )


@given("the fan's speed is approximately 90% of its maximum")
def ensure_subrack_fan_speed(
    subrack_device: tango.DeviceProxy,
    fan_number: int,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Ensure that the fan's speed is about 90% of its maximum.

    :param subrack_device: the subrack Tango device under test.
    :param fan_number: number of the subrack fan being exercised by this
        test.
    :param change_event_callbacks: dictionary of Tango change event
        callbacks with asynchrony support.
    """
    fan_speeds_percent = list(subrack_device.subrackFanSpeedsPercent)
    assert fan_speeds_percent[fan_number - 1] == pytest.approx(90.0)  # just checkin'

    expected_fan_speeds = [
        pytest.approx(p * MAX_SUBRACK_FAN_SPEED / 100.0) for p in fan_speeds_percent
    ]

    subrack_device.subscribe_event(
        "subrackFanSpeeds",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["subrack_fan_speeds"],
    )
    change_event_callbacks.assert_change_event(
        "subrack_fan_speeds", expected_fan_speeds
    )


@given(parsers.parse("the TPM is {target_power}"))
def ensure_tpm_power_state(
    subrack_device: tango.DeviceProxy,
    tpm_number: int,
    change_event_callbacks: MockTangoEventCallbackGroup,
    target_power: str,
) -> None:
    """
    Ensure that the TPM's power state is as expected.

    :param subrack_device: the subrack Tango device under test.
    :param tpm_number: number of the TPM being exercised by this test.
    :param change_event_callbacks: dictionary of Tango change event
        callbacks with asynchrony support.
    :param target_power: name of the target power to check
    """
    subrack_device.subscribe_event(
        f"tpm{tpm_number}PowerState",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["subrack_tpm_power_state"],
    )
    change_event_callbacks["subrack_tpm_power_state"].assert_change_event(
        OneOf(PowerState.UNKNOWN, PowerState.OFF, PowerState.ON)
    )
    tpm_power_state = getattr(subrack_device, f"tpm{tpm_number}PowerState")
    if tpm_power_state == PowerState.UNKNOWN:
        # We've just turned it on and haven't received poll results yet
        print("TPM power state is still unknown. Waiting for next event...")
        change_event_callbacks["subrack_tpm_power_state"].assert_change_event(
            OneOf(PowerState.OFF, PowerState.ON)
        )

    tpm_power_state = getattr(subrack_device, f"tpm{tpm_number}PowerState")
    print(f"TPM power state is now {tpm_power_state}")

    if target_power == "off" and tpm_power_state == PowerState.ON:
        print("TPM is on. Powering it off...")
        subrack_device.PowerOffTpm(tpm_number)

        change_event_callbacks["subrack_tpm_power_state"].assert_change_event(
            PowerState.OFF
        )
        print("TPM is off.")
    elif target_power == "on" and tpm_power_state == PowerState.OFF:
        print("TPM is off. Powering it on...")
        subrack_device.PowerOnTpm(tpm_number)

        change_event_callbacks["subrack_tpm_power_state"].assert_change_event(
            PowerState.ON
        )
        print("TPM is on.")


@when("I set the fan speed to 100%")
def set_subrack_fan_speed(
    subrack_device: tango.DeviceProxy,
    fan_number: int,
) -> None:
    """
    Set the subrack's fan speed to 100%.

    :param subrack_device: the subrack Tango device under test.
    :param fan_number: number of the subrack fan being exercised by this
        test.
    """
    encoded_arg = json.dumps({"subrack_fan_id": fan_number, "speed_percent": 100.0})
    subrack_device.SetSubrackFanSpeed(encoded_arg)


@when("I tell the subrack to turn on the TPM")
def turn_on_tpm(
    subrack_device: tango.DeviceProxy,
    tpm_number: int,
) -> None:
    """
    Tell the subrack to turn on the TPM.

    :param subrack_device: the subrack Tango device under test.
    :param tpm_number: number of the TPM being exercised by this test.
    """
    print(f"Turning on TPM {tpm_number}...")
    subrack_device.PowerOnTpm(tpm_number)


@when("I tell the subrack to turn off all TPMs")
def turn_off_all_tpms(
    subrack_device: tango.DeviceProxy,
) -> None:
    """
    Tell the subrack to turn off all TPMs.

    :param subrack_device: the subrack Tango device under test.
    """
    print("Powering down all TPMs...")
    subrack_device.PowerDownTpms()


@then("the fan's speed setting becomes 100%")
def check_subrack_fan_speed_setting(
    subrack_device: tango.DeviceProxy,
    fan_number: int,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Check that the fan's speed setting becomes 100%.

    :param subrack_device: the subrack Tango device under test.
    :param fan_number: number of the subrack fan being exercised by this
        test.
    :param change_event_callbacks: dictionary of Tango change event
        callbacks with asynchrony support.
    """
    fan_speeds_percent = list(subrack_device.subrackFanSpeedsPercent)
    expected_fan_speeds_percent = [pytest.approx(p) for p in fan_speeds_percent]
    expected_fan_speeds_percent[fan_number - 1] = pytest.approx(100.0)

    change_event_callbacks["subrack_fan_speeds_percent"].assert_change_event(
        expected_fan_speeds_percent
    )


@then("the fan's speed becomes approximately 100% of its maximum")
def check_subrack_fan_speed(
    subrack_device: tango.DeviceProxy,
    fan_number: int,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Check that the fan's speed becomes approximately 100% of its maximum.

    :param subrack_device: the subrack Tango device under test.
    :param fan_number: number of the subrack fan being exercised by this
        test.
    :param change_event_callbacks: dictionary of Tango change event
        callbacks with asynchrony support.
    """
    fan_speeds_percent = list(subrack_device.subrackFanSpeedsPercent)
    assert fan_speeds_percent[fan_number - 1] == pytest.approx(100.0)  # just checkin'

    expected_fan_speeds = [
        pytest.approx(p * MAX_SUBRACK_FAN_SPEED / 100.0) for p in fan_speeds_percent
    ]
    change_event_callbacks.assert_change_event(
        "subrack_fan_speeds", expected_fan_speeds
    )


@then(parsers.parse("the subrack reports that the TPM is {target_power}"))
def check_tpm_power_state(
    change_event_callbacks: MockTangoEventCallbackGroup,
    target_power: str,
) -> None:
    """
    Check that the chosen TPM has a given power state.

    :param change_event_callbacks: dictionary of Tango change event
        callbacks with asynchrony support.
    :param target_power: name of the target power to check
    """
    assert target_power in ["off", "on"]

    if target_power == "off":
        change_event_callbacks["subrack_tpm_power_state"].assert_change_event(
            PowerState.OFF
        )
        print("TPM is off as expected.")
    else:
        change_event_callbacks["subrack_tpm_power_state"].assert_change_event(
            PowerState.ON
        )
        print("TPM is off as expected.")
