#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
Tests of the prototype subrack Tango device, against a mocked subrack.

The hardware client, the subrack and the poller are all injected through
:py:func:`subrack_factory`, and all three are mocks. So no board is reached, no
thread is started, and nothing is waited for. A test hands the device a
:py:class:`SubrackPollResponse` and asserts what the device does with it, which
leaves only the device's own code under test.
"""

from __future__ import annotations

import gc
import json
from typing import Any, Callable, Iterator
from unittest import mock

import pytest
import tango
from ska_control_model import AdminMode, HealthState
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup
from tango import DevState

from ska_low_mccs_spshw.prototype_subrack import (
    HttpError,
    RequestError,
    SubrackPollResponse,
)
from ska_low_mccs_spshw.prototype_subrack.prototype_subrack_device import (
    subrack_factory,
)
from tests.harness import SpsTangoTestHarness, SpsTangoTestHarnessContext

# TODO: gc.disable() works around a hang during garbage collection.
gc.disable()

SUBRACK_ID = 1
BOARD_HOST = "a-fake-board"
BOARD_PORT = 8081
UPDATE_RATE = 1.0
TIMESTAMP = 1700000000.0

# Distinguishes "the test did not say" from "the test said there was none".
_UNSET: Any = object()

# One row per attribute that a poll reports straight through: the Tango
# attribute, the key the subrack reports it under, and the value. Stating the
# pairing once is what tests it. Every value is distinct, so an attribute wired
# to the wrong key reports a value belonging to some other attribute and fails,
# and each sits inside its attribute's alarm range, so a correctly wired
# attribute reads back ATTR_VALID.
POLLED: list[tuple[str, str, Any]] = [
    (
        "tpmPresent",
        "tpm_present",
        [True, False, True, False, False, False, False, False],
    ),
    ("tpmOnOff", "tpm_on_off", [True, False, False, False, False, False, False, False]),
    ("backplaneTemperatures", "backplane_temperatures", [38.5, 39.5]),
    ("boardTemperatures", "board_temperatures", [40.5, 41.5]),
    ("cpldPllLocked", "cpld_pll_locked", True),
    ("powerSupplyCurrents", "power_supply_currents", [4.5, 5.5]),
    ("powerSupplyFanSpeeds", "power_supply_fan_speeds", [91.0, 92.0, 93.0]),
    ("powerSupplyPowers", "power_supply_powers", [54.0, 66.0]),
    ("powerSupplyVoltages", "power_supply_voltages", [12.2, 12.3]),
    ("subrackFanSpeeds", "subrack_fan_speeds", [6175.0, 6240.0, 6305.0, 6370.0]),
    ("subrackFanSpeedsPercent", "subrack_fan_speeds_percent", [95.0, 96.0, 97.0, 98.0]),
    ("subrackFanModes", "subrack_fan_mode", [1, 1, 0, 1]),
    ("subrackPllLocked", "subrack_pll_locked", True),
    ("subrackTimestamp", "subrack_timestamp", 1234567890),
    ("tpmCurrents", "tpm_currents", [0.41, 0.42, 0.43, 0.44, 0.45, 0.46, 0.47, 0.48]),
    ("tpmPowers", "tpm_powers", [4.9, 5.0, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6]),
    ("tpmVoltages", "tpm_voltages", [12.0, 12.1, 12.2, 12.3, 11.9, 11.8, 11.7, 11.6]),
    # The subrack computes this one and reports it alongside the raw reads.
    ("subrackMaxFanSpeeds", "subrack_max_fan_speeds", [6500.0] * 4),
]

# The two attributes the device converts on the way through, so what it reports
# differs from what the subrack reported. Attribute, key, reported, expected.
CONVERTED: list[tuple[str, str, Any, Any]] = [
    # The subrack reports a scalar, and the attribute is a one element spectrum.
    ("boardCurrent", "board_current", 1.25, [1.25]),
    # The subrack reports a nested dictionary, and the attribute is JSON.
    (
        "subrackBoardInfo",
        "board_info",
        {"SMM": {"PN": "SMB", "bios": "v1.6.0"}},
        '{"SMM": {"PN": "SMB", "bios": "v1.6.0"}}',
    ),
]

# One row per attribute the device unpacks from the health status: the Tango
# attribute, its path into the health status, and the value at that path.
HEALTH: list[tuple[str, tuple[str, ...], Any]] = [
    ("internalVoltages1V1", ("internal_voltages", "V_1V1"), 1.1),
    ("internalVoltages1V5", ("internal_voltages", "V_1V5"), 1.5),
    ("internalVoltages2V5", ("internal_voltages", "V_2V5"), 2.5),
    ("internalVoltages2V8", ("internal_voltages", "V_2V8"), 2.8),
    ("internalVoltages3V", ("internal_voltages", "V_3V"), 3.0),
    ("internalVoltages3V3", ("internal_voltages", "V_3V3"), 3.3),
    ("internalVoltages5V", ("internal_voltages", "V_5V"), 5.0),
    # Distinct, so a cross-wiring between these three is caught.
    ("internalVoltagesARM", ("internal_voltages", "V_ARM"), 1.35),
    ("internalVoltagesDDR", ("internal_voltages", "V_DDR"), 1.36),
    ("internalVoltagesSOC", ("internal_voltages", "V_SOC"), 1.37),
    ("internalVoltagesCORE", ("internal_voltages", "V_CORE"), 1.2),
    ("internalVoltagesPOWERIN", ("internal_voltages", "V_POWERIN"), 12.1),
    ("psu1Present", ("psus", "present", "PSU1"), True),
    ("psu2Present", ("psus", "present", "PSU2"), True),
    ("psu1PowerIn", ("psus", "power_in", "PSU1"), 301.0),
    ("psu2PowerIn", ("psus", "power_in", "PSU2"), 302.0),
    ("psu1PowerOut", ("psus", "power_out", "PSU1"), 303.0),
    ("psu2PowerOut", ("psus", "power_out", "PSU2"), 304.0),
    ("psu1VoltageIn", ("psus", "voltage_in", "PSU1"), 230.0),
    ("psu2VoltageIn", ("psus", "voltage_in", "PSU2"), 231.0),
    ("psu1VoltageOut", ("psus", "voltage_out", "PSU1"), 12.2),
    ("psu2VoltageOut", ("psus", "voltage_out", "PSU2"), 12.3),
]


def _nest(rows: list[tuple[str, tuple[str, ...], Any]]) -> dict[str, Any]:
    """
    Build the health status dictionary that puts each value at its path.

    :param rows: the attribute, path and value rows to build from.

    :return: the nested health status.
    """
    health_status: dict[str, Any] = {}
    for _, path, value in rows:
        node = health_status
        for key in path[:-1]:
            node = node.setdefault(key, {})
        node[path[-1]] = value
    return health_status


# What a poll reports, keyed as the subrack client keys it.
POLL_VALUES: dict[str, Any] = {key: value for _, key, value in POLLED}
POLL_VALUES.update({key: reported for _, key, reported, _ in CONVERTED})

HEALTH_STATUS: dict[str, Any] = _nest(HEALTH)

# psuDeadCount is computed by the device rather than read, so it has no row.
ALL_ATTRIBUTES: list[str] = (
    [attribute for attribute, _, _ in POLLED]
    + [attribute for attribute, _, _, _ in CONVERTED]
    + [attribute for attribute, _, _ in HEALTH]
    + ["psuDeadCount"]
)


@pytest.fixture(name="client_factory")
def client_factory_fixture() -> mock.Mock:
    """
    Return the hardware client factory to inject into the device.

    Nothing calls the client it hands out, because the subrack is mocked too.
    It is injected so that no real client is ever built, and so that the
    address the device asked for is recorded.

    :return: the factory.
    """
    return mock.Mock(name="client_factory")


@pytest.fixture(name="subrack_mock")
def subrack_mock_fixture() -> mock.Mock:
    """
    Return the subrack factory to inject into the device.

    The call it records carries the device's own poll callbacks, which is how
    the :py:func:`poll_succeeded` and :py:func:`poll_failed` fixtures reach
    them.

    :return: the factory.
    """
    return mock.Mock(name="subrack_factory")


@pytest.fixture(name="poller")
def poller_fixture() -> mock.Mock:
    """
    Return the poller factory to inject into the device.

    The poller it hands out starts no thread, so nothing polls on its own. It
    records ``start_polling``, ``stop_polling`` and ``kill_polling_thread``.

    :return: the factory.
    """
    return mock.Mock(name="poller_factory")


@pytest.fixture(name="device_class")
def device_class_fixture(
    client_factory: mock.Mock, subrack_mock: mock.Mock, poller: mock.Mock
) -> type:
    """
    Return the device class with everything below it mocked out.

    Mocks rather than functions, because a plain function assigned as a class
    attribute would be bound on access and would receive the device as its
    first argument.

    :param client_factory: the hardware client factory to inject.
    :param subrack_mock: the subrack factory to inject.
    :param poller: the poller factory to inject.

    :return: the device class to serve.
    """
    return subrack_factory(
        web_hardware_client=client_factory,
        subrack=subrack_mock,
        subrack_poller=poller,
    )


@pytest.fixture(name="poll_succeeded")
def poll_succeeded_fixture(subrack_mock: mock.Mock) -> Callable[..., None]:
    """
    Return a callable that hands the device one successful poll response.

    The omni thread is needed because the device pushes Tango events in
    response, just as the real poller wraps its polling loop in one.

    :param subrack_mock: the injected subrack factory, which carries the
        device's data callback.

    :return: a callable taking the values and health status to report.
    """

    def report(
        values: Any = _UNSET,
        health_status: Any = _UNSET,
    ) -> None:
        response = SubrackPollResponse(
            values=POLL_VALUES if values is _UNSET else values,
            health_status=(HEALTH_STATUS if health_status is _UNSET else health_status),
            timestamp=TIMESTAMP,
        )
        with tango.EnsureOmniThread():
            subrack_mock.call_args.kwargs["data_callback"](response)

    return report


@pytest.fixture(name="poll_failed")
def poll_failed_fixture(subrack_mock: mock.Mock) -> Callable[[Exception], None]:
    """
    Return a callable that hands the device one failed poll.

    :param subrack_mock: the injected subrack factory, which carries the
        device's error callback.

    :return: a callable taking the exception to report.
    """

    def report(exception: Exception) -> None:
        with tango.EnsureOmniThread():
            subrack_mock.call_args.kwargs["error_callback"](exception)

    return report


@pytest.fixture(name="test_context")
def test_context_fixture(device_class: type) -> Iterator[SpsTangoTestHarnessContext]:
    """
    Run a prototype subrack device with everything below it mocked out.

    :param device_class: the device class to serve.

    :yields: the running test harness context.
    """
    harness = SpsTangoTestHarness()
    harness.add_prototype_subrack_device(
        SUBRACK_ID,
        address=(BOARD_HOST, BOARD_PORT),
        update_rate=UPDATE_RATE,
        device_class=device_class,
    )
    with harness as context:
        yield context


@pytest.fixture(name="subrack_device")
def subrack_device_fixture(
    test_context: SpsTangoTestHarnessContext,
) -> tango.DeviceProxy:
    """
    Return a proxy to the prototype subrack device under test.

    :param test_context: the running test harness context.

    :return: a proxy to the device under test.
    """
    return test_context.get_prototype_subrack_device(SUBRACK_ID)


@pytest.fixture(name="change_event_callbacks")
def change_event_callbacks_fixture() -> MockTangoEventCallbackGroup:
    """
    Return the Tango change event callbacks the tests subscribe with.

    :return: a group of change event callbacks.
    """
    return MockTangoEventCallbackGroup(
        "state",
        "healthState",
        timeout=20.0,
        assert_no_error=False,
    )


@pytest.fixture(name="subscribed_device")
def subscribed_device_fixture(
    subrack_device: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> tango.DeviceProxy:
    """
    Return the device, subscribed to, with its initial events consumed.

    The device is still offline, so it reports nothing.

    :param subrack_device: the device under test.
    :param change_event_callbacks: the callbacks to subscribe with.

    :return: the device under test.
    """
    for attribute_name in ["state", "healthState"]:
        subrack_device.subscribe_event(
            attribute_name,
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks[attribute_name],
        )
    change_event_callbacks["state"].assert_change_event(DevState.DISABLE)
    change_event_callbacks["healthState"].assert_change_event(HealthState.FAILED)
    return subrack_device


@pytest.fixture(name="online_device")
def online_device_fixture(
    subscribed_device: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> tango.DeviceProxy:
    """
    Return the device, subscribed to and online, with nothing polled yet.

    Nothing has been reported, so the device sits in UNKNOWN and every
    attribute is still invalid.

    :param subscribed_device: the device under test, subscribed to.
    :param change_event_callbacks: the callbacks subscribed to the device.

    :return: the device under test.
    """
    subscribed_device.adminMode = AdminMode.ONLINE
    change_event_callbacks["state"].assert_change_event(DevState.UNKNOWN)
    change_event_callbacks["healthState"].assert_change_event(HealthState.FAILED)
    return subscribed_device


def _assert_reads(
    subrack_device: tango.DeviceProxy, attribute_name: str, expected: Any
) -> None:
    """
    Assert that one attribute reads back valid, with the expected value.

    :param subrack_device: the device under test.
    :param attribute_name: the attribute to read.
    :param expected: the value it should report.
    """
    value = subrack_device.read_attribute(attribute_name)
    assert value.quality == tango.AttrQuality.ATTR_VALID, attribute_name
    if isinstance(expected, list):
        assert list(value.value) == pytest.approx(expected), attribute_name
    else:
        assert value.value == pytest.approx(expected), attribute_name


def _assert_all_invalid(subrack_device: tango.DeviceProxy, why: str) -> None:
    """
    Assert that every attribute reads back with invalid quality.

    :param subrack_device: the device under test.
    :param why: what the assertion message should say about the situation.
    """
    for attribute_name in ALL_ATTRIBUTES:
        assert (
            subrack_device.read_attribute(attribute_name).quality
            == tango.AttrQuality.ATTR_INVALID
        ), f"{attribute_name} should be invalid {why}"


def test_device_has_no_commands(subrack_device: tango.DeviceProxy) -> None:
    """
    Test that this first version of the device exposes no commands of its own.

    ``BaseInterface`` only adds ``On``, ``Off``, ``Standby`` and ``Reset``
    when a subclass implements the matching ``execute_*`` method, and this
    device implements none of them.

    :param subrack_device: the device under test.
    """
    command_names = set(subrack_device.get_command_list())

    assert not command_names & {"On", "Off", "Standby", "Reset"}
    # Only the commands every Tango device and every SKA device carries.
    assert command_names <= {
        "Init",
        "State",
        "Status",
        "GetVersionInfo",
        "DebugDevice",
    }


def test_assembles_from_its_properties(
    subrack_device: tango.DeviceProxy,
    client_factory: mock.Mock,
    subrack_mock: mock.Mock,
    poller: mock.Mock,
) -> None:
    """
    Test that initialisation builds one of each, from the device properties.

    :param subrack_device: the device under test.
    :param client_factory: the injected hardware client factory.
    :param subrack_mock: the injected subrack factory.
    :param poller: the injected poller factory.
    """
    assert subrack_device.state() == DevState.DISABLE

    client_factory.assert_called_once_with(BOARD_HOST, BOARD_PORT)
    subrack_mock.assert_called_once()
    assert subrack_mock.call_args.args[0] is client_factory.return_value
    poller.assert_called_once_with(subrack_mock.return_value, UPDATE_RATE, mock.ANY)
    poller.return_value.start_polling.assert_not_called()


def test_starts_disabled(
    subscribed_device: tango.DeviceProxy,
) -> None:
    """
    Test that the device initialises offline, disabled and reporting nothing.

    :param subscribed_device: the device under test, subscribed to.
    """
    assert subscribed_device.adminMode == AdminMode.OFFLINE
    assert list(subscribed_device.healthInfo) == ["adminMode is OFFLINE."]
    _assert_all_invalid(subscribed_device, "before the device is online")


def test_online_starts_the_poller_and_waits(
    online_device: tango.DeviceProxy,
    poller: mock.Mock,
) -> None:
    """
    Test that going online starts the poller and reports nothing until a poll.

    :param online_device: the device under test, online and not yet polled.
    :param poller: the injected poller factory.
    """
    poller.return_value.start_polling.assert_called_once_with()
    assert list(online_device.healthInfo) == [
        "Establishing communication with the subrack."
    ]
    _assert_all_invalid(online_device, "until the first poll")


def test_poll_response_populates_attributes(
    online_device: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
    poll_succeeded: Callable[..., None],
) -> None:
    """
    Test that one poll response puts every polled value onto its attribute.

    :param online_device: the device under test, online and not yet polled.
    :param change_event_callbacks: the callbacks subscribed to the device.
    :param poll_succeeded: hands the device a successful poll response.
    """
    poll_succeeded()

    change_event_callbacks["state"].assert_change_event(DevState.ON)
    change_event_callbacks["healthState"].assert_change_event(HealthState.OK)
    assert not list(online_device.healthInfo)

    for attribute_name, _, expected in POLLED:
        _assert_reads(online_device, attribute_name, expected)

    # The two the device converts on the way through.
    for attribute_name, _, _, expected in CONVERTED:
        _assert_reads(online_device, attribute_name, expected)


def test_health_status_populates_attributes(
    online_device: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
    poll_succeeded: Callable[..., None],
) -> None:
    """
    Test that the values unpacked from the health status reach their attributes.

    :param online_device: the device under test, online and not yet polled.
    :param change_event_callbacks: the callbacks subscribed to the device.
    :param poll_succeeded: hands the device a successful poll response.
    """
    poll_succeeded()
    change_event_callbacks["healthState"].assert_change_event(HealthState.OK)

    for attribute_name, _, expected in HEALTH:
        _assert_reads(online_device, attribute_name, expected)

    # Both PSUs supply an output voltage, so neither counts as dead.
    _assert_reads(online_device, "psuDeadCount", 0)


def test_dead_psu_is_counted(
    online_device: tango.DeviceProxy,
    poll_succeeded: Callable[..., None],
) -> None:
    """
    Test that a PSU which is present and fed but supplying nothing is counted.

    :param online_device: the device under test, online and not yet polled.
    :param poll_succeeded: hands the device a successful poll response.
    """
    health_status = json.loads(json.dumps(HEALTH_STATUS))
    health_status["psus"]["voltage_out"]["PSU2"] = 0.0

    poll_succeeded(health_status=health_status)

    assert online_device.psuDeadCount == 1
    assert online_device.psu1VoltageOut == pytest.approx(12.2)


def test_unknown_value_is_invalid_but_the_poll_still_counts(
    online_device: tango.DeviceProxy,
    poll_succeeded: Callable[..., None],
) -> None:
    """
    Test that a value the subrack could not supply invalidates only its attribute.

    The subrack reports an unreadable key as ``None``, which is not a failed
    poll, so every other attribute takes its value and the device stays healthy.

    :param online_device: the device under test, online and not yet polled.
    :param poll_succeeded: hands the device a successful poll response.
    """
    values = dict(POLL_VALUES, board_temperatures=None)

    poll_succeeded(values=values)

    assert (
        online_device.read_attribute("boardTemperatures").quality
        == tango.AttrQuality.ATTR_INVALID
    )
    assert list(online_device.backplaneTemperatures) == pytest.approx([38.5, 39.5])
    assert online_device.state() == DevState.ON
    assert online_device.healthState == HealthState.OK


def test_missing_health_status_invalidates_only_its_attributes(
    online_device: tango.DeviceProxy,
    poll_succeeded: Callable[..., None],
) -> None:
    """
    Test that a poll which read no health status keeps the other attributes.

    :param online_device: the device under test, online and not yet polled.
    :param poll_succeeded: hands the device a successful poll response.
    """
    poll_succeeded(health_status=None)

    for attribute_name, _, _ in HEALTH:
        assert (
            online_device.read_attribute(attribute_name).quality
            == tango.AttrQuality.ATTR_INVALID
        ), attribute_name
    assert list(online_device.boardTemperatures) == pytest.approx([40.5, 41.5])
    assert online_device.healthState == HealthState.OK


def test_going_offline_stops_polling_and_invalidates(
    online_device: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
    poll_succeeded: Callable[..., None],
    poller: mock.Mock,
) -> None:
    """
    Test that taking the device offline stops polling and drops every value.

    A subrack the device is no longer talking to must not leave a stale value
    readable, so every attribute returns to invalid quality.

    :param online_device: the device under test, online and not yet polled.
    :param change_event_callbacks: the callbacks subscribed to the device.
    :param poll_succeeded: hands the device a successful poll response.
    :param poller: the injected poller factory.
    """
    poll_succeeded()
    change_event_callbacks["state"].assert_change_event(DevState.ON)
    change_event_callbacks["healthState"].assert_change_event(HealthState.OK)

    # Initialisation settles the device in DISABLE, which stops the poller it
    # has just built, so count the transition rather than the calls.
    stops_before = poller.return_value.stop_polling.call_count

    online_device.adminMode = AdminMode.OFFLINE

    change_event_callbacks["state"].assert_change_event(DevState.DISABLE)
    change_event_callbacks["healthState"].assert_change_event(HealthState.FAILED)
    assert list(online_device.healthInfo) == ["adminMode is OFFLINE."]
    assert poller.return_value.stop_polling.call_count == stops_before + 1
    _assert_all_invalid(online_device, "once the device is offline")


def test_unreachable_subrack_reports_unknown(
    online_device: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
    poll_succeeded: Callable[..., None],
    poll_failed: Callable[[Exception], None],
) -> None:
    """
    Test that a request which never reached the board leaves the state UNKNOWN.

    :param online_device: the device under test, online and not yet polled.
    :param change_event_callbacks: the callbacks subscribed to the device.
    :param poll_succeeded: hands the device a successful poll response.
    :param poll_failed: hands the device a failed poll.
    """
    poll_succeeded()
    change_event_callbacks["state"].assert_change_event(DevState.ON)
    change_event_callbacks["healthState"].assert_change_event(HealthState.OK)

    poll_failed(RequestError("Connection refused"))

    change_event_callbacks["state"].assert_change_event(DevState.UNKNOWN)
    change_event_callbacks["healthState"].assert_change_event(HealthState.FAILED)
    health_info = list(online_device.healthInfo)
    assert health_info[0].startswith("Poll failed with RequestError")
    assert "Connection refused" in health_info[0]
    _assert_all_invalid(online_device, "when the subrack is unreachable")


def test_board_error_reports_fault(
    online_device: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
    poll_succeeded: Callable[..., None],
    poll_failed: Callable[[Exception], None],
) -> None:
    """
    Test that a board which answers with an error faults, rather than UNKNOWN.

    :param online_device: the device under test, online and not yet polled.
    :param change_event_callbacks: the callbacks subscribed to the device.
    :param poll_succeeded: hands the device a successful poll response.
    :param poll_failed: hands the device a failed poll.
    """
    poll_succeeded()
    change_event_callbacks["state"].assert_change_event(DevState.ON)
    change_event_callbacks["healthState"].assert_change_event(HealthState.OK)

    poll_failed(HttpError("500 Server Error"))

    change_event_callbacks["state"].assert_change_event(DevState.FAULT)
    change_event_callbacks["healthState"].assert_change_event(HealthState.FAILED)
    assert list(online_device.healthInfo)[0].startswith("Poll failed with HttpError")


def test_recovers_after_a_failed_poll(
    online_device: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
    poll_succeeded: Callable[..., None],
    poll_failed: Callable[[Exception], None],
) -> None:
    """
    Test that the device recovers on the next poll that succeeds.

    :param online_device: the device under test, online and not yet polled.
    :param change_event_callbacks: the callbacks subscribed to the device.
    :param poll_succeeded: hands the device a successful poll response.
    :param poll_failed: hands the device a failed poll.
    """
    poll_failed(RequestError("Connection refused"))
    assert online_device.healthState == HealthState.FAILED

    poll_succeeded()

    change_event_callbacks["state"].assert_change_event(DevState.ON)
    change_event_callbacks["healthState"].assert_change_event(HealthState.OK)
    assert list(online_device.boardTemperatures) == pytest.approx([40.5, 41.5])


def test_init_rebuilds_everything(
    online_device: tango.DeviceProxy,
    poll_succeeded: Callable[..., None],
    client_factory: mock.Mock,
    subrack_mock: mock.Mock,
    poller: mock.Mock,
) -> None:
    """
    Test that re-initialising reclaims the old poller and builds another.

    ``Init()`` runs ``delete_device`` and then ``init_device``, so
    ``disassemble`` has to reclaim the first poller before ``assemble`` builds
    the second.

    :param online_device: the device under test, online and not yet polled.
    :param poll_succeeded: hands the device a successful poll response.
    :param client_factory: the injected hardware client factory.
    :param subrack_mock: the injected subrack factory.
    :param poller: the injected poller factory.
    """
    online_device.Init()

    poller.return_value.kill_polling_thread.assert_called_once_with()
    # Assembly builds all three, so re-initialising must build all three again.
    assert client_factory.call_count == 2, "Init did not build a second client"
    assert subrack_mock.call_count == 2, "Init did not build a second subrack"
    assert poller.call_count == 2, "Init did not build a second poller"
    assert subrack_mock.call_args.args[0] is client_factory.return_value
    assert poller.call_args.args[0] is subrack_mock.return_value

    # adminMode is memorized, so the device comes back online by itself, and the
    # new poller feeds the attributes.
    assert poller.return_value.start_polling.call_count == 2
    poll_succeeded()
    assert list(online_device.boardTemperatures) == pytest.approx([40.5, 41.5])


def test_board_error_before_any_poll_stays_unknown(
    online_device: tango.DeviceProxy,
    poll_failed: Callable[[Exception], None],
) -> None:
    """
    Test that a board error before the first successful poll stays UNKNOWN.

    Nothing has been read to say the subrack is there at all, so it cannot be
    reported as faulty. The operational state model has no transition from
    UNKNOWN into FAULT either, so reporting one would raise.

    The device is already FAILED from going online, so this pushes no
    healthState event. Only the reason it gives changes.

    :param online_device: the device under test, online and not yet polled.
    :param poll_failed: hands the device a failed poll.
    """
    poll_failed(HttpError("500 Server Error"))

    assert online_device.state() == DevState.UNKNOWN
    assert online_device.healthState == HealthState.FAILED
    assert list(online_device.healthInfo)[0].startswith("Poll failed with HttpError")


def test_recovers_from_a_fault(
    online_device: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
    poll_succeeded: Callable[..., None],
    poll_failed: Callable[[Exception], None],
) -> None:
    """
    Test that the device leaves FAULT once a poll succeeds again.

    ``component_on`` alone does not clear a fault, because the operational
    state model routes FAULT_ON back to FAULT_ON on it.

    :param online_device: the device under test, online and not yet polled.
    :param change_event_callbacks: the callbacks subscribed to the device.
    :param poll_succeeded: hands the device a successful poll response.
    :param poll_failed: hands the device a failed poll.
    """
    poll_succeeded()
    change_event_callbacks["state"].assert_change_event(DevState.ON)
    change_event_callbacks["healthState"].assert_change_event(HealthState.OK)

    poll_failed(HttpError("500 Server Error"))
    change_event_callbacks["state"].assert_change_event(DevState.FAULT)
    change_event_callbacks["healthState"].assert_change_event(HealthState.FAILED)

    poll_succeeded()

    change_event_callbacks["state"].assert_change_event(DevState.ON)
    change_event_callbacks["healthState"].assert_change_event(HealthState.OK)
    assert online_device.state() == DevState.ON
    _assert_reads(online_device, "boardTemperatures", [40.5, 41.5])
