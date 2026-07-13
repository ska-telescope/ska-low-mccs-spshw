# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""Tests of the prototype (component-manager-free) subrack Tango device.

These are black-box tests: the prototype device is driven entirely through a
:py:class:`tango.DeviceProxy`, exactly as a real client would, and monitored
against a running subrack simulator. They assert that the prototype exposes the
same monitoring/command surface as ``MccsSubrack`` and that its PyTango inbuilt
attribute polling refreshes the hardware cache and emits events.
"""
from __future__ import annotations

import gc
import time
from typing import Callable, Iterator

import pytest
from ska_control_model import AdminMode, HealthState, PowerState, ResultCode
from tango import AttrQuality, DeviceProxy, DevState

from ska_low_mccs_spshw import MccsSubrackPrototype
from ska_low_mccs_spshw.subrack import SubrackSimulator
from tests.harness import SpsTangoTestHarness, SpsTangoTestHarnessContext
from tests.test_tools import execute_lrc_to_completion

# TODO: Weird hang-at-garbage-collection bug (see test_subrack_device.py).
gc.disable()

# The monitoring attributes that must be present and refreshed by polling.
MONITORING_ATTRIBUTES = (
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
    "tpmVoltages",
    "subrackBoardInfo",
)

# The long running commands that must be present.
EXPECTED_COMMANDS = (
    "PowerOnTpm",
    "PowerOffTpm",
    "PowerUpTpms",
    "PowerDownTpms",
    "SetSubrackFanSpeed",
    "SetSubrackFanMode",
    "SetPowerSupplyFanSpeed",
    "ScheduleOn",
    "ScheduleOff",
    "UpdateHealthAttributes",
    # On/Off power the subrack's OWN PduPorts (deliberate deviation from the
    # production subrack, which powers arbitrary PDU ports). No Standby.
    "On",
    "Off",
)

# The TPM bays that the simulator reports as present/populated (1-based).
PRESENT_TPM_BAYS = (2, 5)


@pytest.fixture(name="test_context")
def test_context_fixture(
    subrack_id: int,
    subrack_simulator: SubrackSimulator,
) -> Iterator[SpsTangoTestHarnessContext]:
    """
    Return a context with a subrack simulator and prototype Tango device running.

    :param subrack_id: the ID of the subrack under test.
    :param subrack_simulator: the backend simulator that the Tango device will
        monitor and control.

    :yields: a test context.
    """
    harness = SpsTangoTestHarness()
    harness.add_subrack_simulator(subrack_id, subrack_simulator)
    harness.add_subrack_device(
        subrack_id,
        device_class=MccsSubrackPrototype,
        define_parent_trl=False,
    )
    with harness as context:
        # HealthRecorder.__init__ (ska_low_mccs_common) spawns a background
        # thread that opens its own proxy back to this device and subscribes
        # to its change events. If the harness tears the device server down
        # while that thread is still connecting, the whole process crashes
        # with "Tango is not initialised !!!" rather than failing the test
        # normally. There is no safe way to poll for that thread's readiness
        # from here (state()/ping() already succeed immediately, and
        # reaching into the live servant from this thread to check requires
        # unguarded access to Tango's server-side Util singleton, which
        # triggers the same crash) so we give it a moment to settle instead.
        time.sleep(1)

        yield context


@pytest.fixture(name="subrack_device")
def subrack_device_fixture(
    test_context: SpsTangoTestHarnessContext,
    subrack_id: int,
) -> Iterator[DeviceProxy]:
    """
    Return the prototype subrack Tango device under test.

    :param test_context: a running test context.
    :param subrack_id: ID of the subrack.

    :yield: the prototype subrack Tango device under test.
    """
    yield test_context.get_subrack_device(subrack_id)


def _wait_until(predicate: Callable[[], bool], timeout: float = 20.0) -> None:
    """
    Poll ``predicate`` until it is true, or raise once ``timeout`` elapses.

    :param predicate: a zero-argument callable returning ``True`` once the
        awaited condition holds.
    :param timeout: seconds to wait before giving up.

    :raises TimeoutError: if ``predicate`` has not returned ``True`` within
        ``timeout`` seconds.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.2)
    raise TimeoutError(f"Condition not met within {timeout} seconds.")


def _go_online(device: DeviceProxy, timeout: float = 20.0) -> None:
    """
    Put the device online and wait until it establishes communication.

    :param device: the device proxy under test.
    :param timeout: seconds to wait for the ON state.

    :raises TimeoutError: if the device does not reach ON within ``timeout``.
    """
    device.adminMode = AdminMode.ONLINE
    deadline = time.time() + timeout
    while time.time() < deadline:
        if device.state() == DevState.ON:
            return
        time.sleep(0.2)
    raise TimeoutError(f"Device did not reach ON (state={device.state()}).")


def _force_refresh(device: DeviceProxy) -> None:
    """
    Force an immediate hardware refresh by cycling adminMode off and back on.

    A board command (e.g. ``PowerOnTpm``) only tells the simulator to change
    state; the device only observes that change on its next batched hardware
    poll. That natural poll cadence is not reliably tied to ``UpdateRate`` in
    this test harness (it can take upwards of 15s to tick), so rather than
    waiting on it, we drop and re-establish control: ``change_control_level``
    performs an unconditional forced refresh as soon as control is regained.

    :param device: the device proxy under test.
    """
    device.adminMode = AdminMode.OFFLINE
    _wait_until(lambda: device.state() == DevState.DISABLE, timeout=10)
    _go_online(device)


def test_interface_parity(subrack_device: DeviceProxy) -> None:
    """
    The prototype exposes the expected monitoring attributes and commands.

    :param subrack_device: the prototype subrack Tango device under test.
    """
    _go_online(subrack_device)
    attributes = set(subrack_device.get_attribute_list())
    for name in MONITORING_ATTRIBUTES:
        assert name in attributes, f"missing attribute {name}"
    # The signal-backed internal voltage attributes.
    assert "internalVoltagesSOC" in attributes
    # The no-op interface-parity attributes have been dropped from the prototype.
    for name in ("simulationMode", "useAttributesForHealth", "healthModelParams"):
        assert name not in attributes, f"unexpected attribute {name}"

    commands = {c.cmd_name for c in subrack_device.command_list_query()}
    for name in EXPECTED_COMMANDS:
        assert name in commands, f"missing command {name}"
    # The prototype deliberately does NOT power arbitrary PDU ports, and has no
    # Standby: On/Off act only on the subrack's own PduPorts.
    for name in ("PowerPduPortOn", "PowerPduPortOff", "Standby"):
        assert name not in commands, f"unexpected command {name}"


def test_initial_state_is_disable(subrack_device: DeviceProxy) -> None:
    """
    The device starts in the DISABLE state (adminMode OFFLINE).

    :param subrack_device: the prototype subrack Tango device under test.
    """
    assert subrack_device.state() == DevState.DISABLE
    _go_online(subrack_device)
    assert subrack_device.state() == DevState.ON


def test_attributes_invalid_when_offline(subrack_device: DeviceProxy) -> None:
    """
    Hardware-backed attributes are invalid, and TPM state unknown, while offline.

    :param subrack_device: the prototype subrack Tango device under test.
    """
    attr = subrack_device.read_attribute("boardTemperatures")
    assert attr.quality == AttrQuality.ATTR_INVALID
    assert len(subrack_device.tpmPresent) == 0
    assert subrack_device.tpmCount == 0
    assert subrack_device.tpm1PowerState == PowerState.UNKNOWN


def test_online_monitoring(subrack_device: DeviceProxy) -> None:
    """
    Going online enables inbuilt polling and refreshes the hardware cache.

    :param subrack_device: the prototype subrack Tango device under test.
    """
    _go_online(subrack_device)

    # Inbuilt Tango attribute polling should be enabled at the update rate.
    assert subrack_device.is_attribute_polled("boardTemperatures")

    # The forced refresh on going online should have populated the cache,
    # with values matching the configured simulator backend.
    assert subrack_device.boardTemperatures is not None
    assert len(subrack_device.boardTemperatures) > 0
    assert list(subrack_device.tpmPresent) == [
        False,
        True,
        False,
        False,
        True,
        False,
        False,
        False,
    ]
    assert subrack_device.tpmCount == 2


def test_health_populates(subrack_device: DeviceProxy) -> None:
    """
    The HealthRecorder derives a (non-UNKNOWN) health once monitoring runs.

    :param subrack_device: the prototype subrack Tango device under test.
    """
    _go_online(subrack_device)
    _wait_until(lambda: subrack_device.healthState != HealthState.UNKNOWN)
    assert subrack_device.healthState in (
        HealthState.OK,
        HealthState.DEGRADED,
        HealthState.FAILED,
    )


def test_set_subrack_fan_speed(subrack_device: DeviceProxy) -> None:
    """
    The SetSubrackFanSpeed long running command completes successfully.

    :param subrack_device: the prototype subrack Tango device under test.
    """
    _go_online(subrack_device)
    execute_lrc_to_completion(
        subrack_device,
        "SetSubrackFanSpeed",
        '{"subrack_fan_id": 1, "speed_percent": 80}',
        timeout=20,
    )


def test_power_on_off_tpm(subrack_device: DeviceProxy) -> None:
    """
    PowerOnTpm/PowerOffTpm drive the corresponding tpmNPowerState attribute.

    The command only tells the simulator to change ``tpm_on_off``; the device
    only observes that change on its next hardware poll, so we wait for the
    attribute to catch up rather than asserting immediately.

    :param subrack_device: the prototype subrack Tango device under test.
    """
    _go_online(subrack_device)
    bay = PRESENT_TPM_BAYS[0]

    execute_lrc_to_completion(subrack_device, "PowerOnTpm", bay, timeout=20)
    _force_refresh(subrack_device)
    assert getattr(subrack_device, f"tpm{bay}PowerState") == PowerState.ON

    execute_lrc_to_completion(subrack_device, "PowerOffTpm", bay, timeout=20)
    _force_refresh(subrack_device)
    assert getattr(subrack_device, f"tpm{bay}PowerState") == PowerState.OFF


def test_power_up_down_tpms(subrack_device: DeviceProxy) -> None:
    """
    PowerUpTpms/PowerDownTpms drive every tpmNPowerState attribute together.

    :param subrack_device: the prototype subrack Tango device under test.
    """
    _go_online(subrack_device)

    execute_lrc_to_completion(subrack_device, "PowerUpTpms", None, timeout=20)
    _force_refresh(subrack_device)
    assert all(
        getattr(subrack_device, f"tpm{bay}PowerState") == PowerState.ON
        for bay in range(1, 9)
    )

    execute_lrc_to_completion(subrack_device, "PowerDownTpms", None, timeout=20)
    _force_refresh(subrack_device)
    assert all(
        getattr(subrack_device, f"tpm{bay}PowerState") == PowerState.OFF
        for bay in range(1, 9)
    )


def test_update_health_attributes_command(subrack_device: DeviceProxy) -> None:
    """
    The UpdateHealthAttributes command forces an immediate health-status poll.

    :param subrack_device: the prototype subrack Tango device under test.
    """
    _go_online(subrack_device)
    execute_lrc_to_completion(
        subrack_device, "UpdateHealthAttributes", None, timeout=20
    )
    assert subrack_device.internalVoltagesSOC is not None


def test_schedule_on_off_without_marshaller(subrack_device: DeviceProxy) -> None:
    """
    ScheduleOn/ScheduleOff degrade gracefully with no power marshaller configured.

    :param subrack_device: the prototype subrack Tango device under test.
    """
    _go_online(subrack_device)
    execute_lrc_to_completion(subrack_device, "ScheduleOn", None, timeout=10)
    execute_lrc_to_completion(subrack_device, "ScheduleOff", None, timeout=10)


def test_on_off_without_reachable_pdu(subrack_device: DeviceProxy) -> None:
    """
    On()/Off() fail gracefully when there is no reachable PDU to power.

    The prototype's On/Off act only on the subrack's own PduPorts (see
    ``EXPECTED_COMMANDS``). With a simulated (unreachable) PDU there is
    nothing to command, so both must report FAILED without touching
    operational state.

    :param subrack_device: the prototype subrack Tango device under test.
    """
    _go_online(subrack_device)
    state_before = subrack_device.state()

    [[on_result], [on_message]] = subrack_device.On()
    assert on_result == ResultCode.FAILED
    assert "no reachable PDU" in on_message

    [[off_result], [off_message]] = subrack_device.Off()
    assert off_result == ResultCode.FAILED
    assert "no reachable PDU" in off_message

    assert subrack_device.state() == state_before


def test_offline_invalidates(subrack_device: DeviceProxy) -> None:
    """
    Going offline stops polling and returns the device to DISABLE.

    :param subrack_device: the prototype subrack Tango device under test.
    """
    _go_online(subrack_device)
    subrack_device.adminMode = AdminMode.OFFLINE
    _wait_until(lambda: subrack_device.state() == DevState.DISABLE, timeout=10)
    assert subrack_device.state() == DevState.DISABLE
    assert not subrack_device.is_attribute_polled("boardTemperatures")

    # The hardware cache is invalidated on the way offline, just as it was
    # before the device was ever brought online.
    attr = subrack_device.read_attribute("boardTemperatures")
    assert attr.quality == AttrQuality.ATTR_INVALID
    assert len(subrack_device.tpmPresent) == 0
    assert subrack_device.tpmCount == 0


def test_custom_poll_period_survives_offline_online_cycle(
    subrack_device: DeviceProxy,
) -> None:
    """
    A per-attribute poll period customisation is not reset by admin cycling.

    Going offline stops (and going online restarts) Tango's inbuilt polling,
    since a plain client read of a polled attribute is served from Tango's own
    polling buffer, which needs re-seeding on the way back online (see
    ``change_control_level``). That stop/start must not, as a side effect,
    silently reset a custom per-attribute polling period back to the
    ``UpdateRate`` default.

    :param subrack_device: the prototype subrack Tango device under test.
    """
    _go_online(subrack_device)

    custom_period_ms = 5000
    subrack_device.poll_attribute("boardTemperatures", custom_period_ms)
    assert (
        subrack_device.get_attribute_poll_period("boardTemperatures")
        == custom_period_ms
    )

    subrack_device.adminMode = AdminMode.OFFLINE
    _wait_until(lambda: subrack_device.state() == DevState.DISABLE, timeout=10)
    _go_online(subrack_device)

    assert (
        subrack_device.get_attribute_poll_period("boardTemperatures")
        == custom_period_ms
    )


def test_pdu_attributes_when_pdu_unconfigured(subrack_device: DeviceProxy) -> None:
    """
    The live-proxied ``pdu*`` attributes degrade gracefully with no PDU proxy.

    The test harness configures a simulated PDU, so the device never obtains a
    PDU device proxy; each ``pdu*`` attribute must therefore report ``None``
    rather than raising.

    :param subrack_device: the prototype subrack Tango device under test.
    """
    _go_online(subrack_device)
    assert subrack_device.pduHealth is None
    assert subrack_device.pduModel is None
    assert subrack_device.pduNumberPorts is None
    assert subrack_device.pduPortStates is None
    assert subrack_device.pduPortCurrents is None
    assert subrack_device.pduPortVoltages is None


def test_health_status_and_report_attributes(subrack_device: DeviceProxy) -> None:
    """
    The ``healthStatus`` and ``healthReport`` attributes are populated.

    :param subrack_device: the prototype subrack Tango device under test.
    """
    _go_online(subrack_device)
    _wait_until(lambda: subrack_device.healthState != HealthState.UNKNOWN)
    assert subrack_device.healthStatus
    assert isinstance(subrack_device.healthReport, str)


def test_attribute_error_status_invalidates_cache(
    subrack_device: DeviceProxy,
    subrack_simulator: SubrackSimulator,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A per-attribute ``ERROR`` status from the board invalidates the cache.

    Unlike a transport-level failure, an in-band error reported by the board
    (e.g. an unhandled exception in firmware) does not raise, so it must not
    disturb the device's operational state: only the affected attributes'
    cached values are cleared.

    :param subrack_device: the prototype subrack Tango device under test.
    :param subrack_simulator: the backend simulator.
    :param monkeypatch: pytest's monkeypatch fixture.
    """
    _go_online(subrack_device)
    assert subrack_device.read_attribute("boardTemperatures").quality == (
        AttrQuality.ATTR_VALID
    )

    def _raise(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated board error")

    monkeypatch.setattr(subrack_simulator, "get_attribute", _raise)
    _force_refresh(subrack_device)

    assert subrack_device.state() == DevState.ON
    attr = subrack_device.read_attribute("boardTemperatures")
    assert attr.quality == AttrQuality.ATTR_INVALID


@pytest.fixture(name="marshaller_test_context")
def marshaller_test_context_fixture(
    subrack_id: int,
    subrack_simulator: SubrackSimulator,
) -> Iterator[SpsTangoTestHarnessContext]:
    """
    Return a context with a subrack and a real (reachable) power marshaller.

    :param subrack_id: the ID of the subrack under test.
    :param subrack_simulator: the backend simulator that the Tango device will
        monitor and control.

    :yields: a test context.
    """
    harness = SpsTangoTestHarness()
    harness.add_subrack_simulator(subrack_id, subrack_simulator)
    harness.add_subrack_device(
        subrack_id,
        device_class=MccsSubrackPrototype,
        define_parent_trl=False,
    )
    harness.add_power_marshaller_device()
    with harness as context:
        time.sleep(1)
        yield context


def test_schedule_on_off_with_marshaller_configured(
    marshaller_test_context: SpsTangoTestHarnessContext, subrack_id: int
) -> None:
    """
    ScheduleOn/ScheduleOff complete successfully with a reachable marshaller.

    With a real power marshaller device registered, ``_get_marshaller_proxy``
    obtains and caches a real device proxy (rather than degrading gracefully
    on a ``DevFailed``, as in ``test_schedule_on_off_without_marshaller``).

    :param marshaller_test_context: a running test context with a power
        marshaller device.
    :param subrack_id: ID of the subrack.
    """
    subrack_device = marshaller_test_context.get_subrack_device(subrack_id)
    _go_online(subrack_device)
    execute_lrc_to_completion(subrack_device, "ScheduleOn", None, timeout=10)
    execute_lrc_to_completion(subrack_device, "ScheduleOff", None, timeout=10)
