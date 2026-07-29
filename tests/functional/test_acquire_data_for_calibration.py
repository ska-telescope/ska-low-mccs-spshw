# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the bdd test steps for AcquireDataForCalibration.

These tests exercise the ``SpsStation.AcquireDataForCalibration`` command
end-to-end against real hardware. We do not care about the contents of the
correlator files produced, only that the acquisition machinery
(station -> tiles -> DAQ correlator) yields one correlator file per requested
channel.
"""
from __future__ import annotations

import json
import time
from typing import Any, Callable, Generator, TypeVar

import pytest
import tango
from pytest_bdd import given, parsers, scenarios, then, when
from ska_control_model import AdminMode, ResultCode
from ska_tango_testing.mock.placeholders import Anything
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup

from tests.functional.conftest import poll_until_state_change
from tests.harness import get_lmc_daq_name, get_sps_station_name
from tests.test_tools import (
    AttributeWaiter,
    get_lrc_executing,
    get_lrc_finished,
    get_lrc_queued,
    retry_communication,
    wait_for_condition,
    wait_for_lrc_result,
)

scenarios("./features/acquire_data_for_calibration.feature")

# The acquisition is a long running command that has to configure the station,
# start the DAQ correlator, send channelised data from every tile and wait for
# a correlator file per channel. Give it plenty of headroom on real hardware.
ACQUIRE_TIMEOUT = 180

# How long to allow a command submitted mid-acquisition to finish. It forwards to
# every tile, so it is not instant, but it must not have to wait out the
# acquisition.
CONCURRENT_COMMAND_TIMEOUT = 90

# The acquisition stops TPM transmission as it tears down, so pendingDataRequests
# should clear on every tile shortly after it reports itself finished.
TRANSMISSION_DRAIN_TIMEOUT = 60

# How long to allow the acquisition to show up in lrcExecuting. The station reports
# its long running commands through eventually-consistent attributes: the task is
# only marked IN_PROGRESS once its worker thread has read tileProgrammingState, and
# the attribute itself is fed by the signal bus's background thread. A command that
# has just returned QUEUED is therefore not yet in lrcExecuting.
ACQUISITION_START_TIMEOUT = 30

# How long to let a still-running acquisition finish by itself during teardown
# before aborting it. It gives up ~10 seconds after data stops arriving, so a
# healthy acquisition either completes or bails out well inside this.
ACQUISITION_TEARDOWN_GRACE = 60

# How often to re-read the station's LRC attributes while waiting on a command.
# Each poll reads two of them, so keep it coarse: nothing here needs to notice a
# transition promptly, it just needs to notice it.
_POLL_INTERVAL = 0.5

# What the thing being waited for evaluates to once it has happened.
_Found = TypeVar("_Found")


@given(
    parsers.cfparse("this test is running against station {expected_station}."),
    target_fixture="station_name",
)
def station_context_fixture(
    expected_station: str,
    available_stations: list[str],
    true_context: bool,
) -> str:
    """
    Return the name of the station under test.

    :param expected_station: the name of the station to test against.
    :param available_stations: a list of available stations in the context
        the test is running.
    :param true_context: whether to test against an existing Tango deployment.

    :return: the name of the station under test.
    """
    if not true_context:
        pytest.skip("This needs to be run in a true-context")
    if expected_station not in available_stations:
        pytest.skip(
            f"This test is designed for station {expected_station}. "
            f"This is not one of the {available_stations=}."
        )
    return expected_station


@pytest.fixture(name="station")
def station_fixture(station_name: str) -> tango.DeviceProxy:
    """
    Return a ``tango.DeviceProxy`` to the SpsStation under test.

    :param station_name: the name of the station under test.

    :return: a ``tango.DeviceProxy`` to the SpsStation under test.
    """
    return tango.DeviceProxy(get_sps_station_name(station_name))


@given("the DAQ is available", target_fixture="daq_device")
def daq_device_fixture(station_name: str) -> tango.DeviceProxy:
    """
    Return a ``tango.DeviceProxy`` to the DAQ device under test.

    :param station_name: the name of the station under test.

    :return: a ``tango.DeviceProxy`` to the DAQ device under test.
    """
    daq_device = tango.DeviceProxy(get_lmc_daq_name(station_name))
    if daq_device.state() != tango.DevState.ON:
        retry_communication(daq_device)
        poll_until_state_change(daq_device, tango.DevState.ON, 5)
    return daq_device


@given("the SpsStation is synchronised")
def station_is_synchronised(
    station: tango.DeviceProxy,
    station_tiles: list[tango.DeviceProxy],
    wait_for_lrcs_to_finish: Callable,
) -> None:
    """
    Ensure the SpsStation is ON with all tiles synchronised.

    ``AcquireDataForCalibration`` is rejected unless every tile is
    ``Synchronised``, so drive the station there before acquiring.

    :param station: A 'tango.DeviceProxy' to the SpsStation device.
    :param station_tiles: the Tile devices belonging to the station under test.
    :param wait_for_lrcs_to_finish: callable that waits for LRCs on devices.
    """
    if station.adminMode not in [AdminMode.ONLINE, AdminMode.ENGINEERING]:
        station.adminMode = AdminMode.ONLINE
        AttributeWaiter(timeout=300).wait_for_value(
            station, "state", tango.DevState.ON, lookahead=5
        )
    wait_for_lrcs_to_finish(station_tiles + [station], timeout=300)

    if not all(status == "Synchronised" for status in station.tileProgrammingState):
        # Cycle STANDBY -> ON to (re)synchronise the tiles.
        station.standby()
        AttributeWaiter(timeout=300).wait_for_value(
            station, "state", tango.DevState.STANDBY
        )
        station.on()
        try:
            AttributeWaiter(timeout=300).wait_for_value(
                station, "state", tango.DevState.ON
            )
        except AssertionError:
            # Hardware can settle in ALARM, that is fine for this test.
            assert station.state() in [tango.DevState.ON, tango.DevState.ALARM]
        for tile in station_tiles:
            AttributeWaiter(timeout=300).wait_for_value(
                tile, "tileProgrammingState", "Synchronised", lookahead=10
            )

    if not all(status == "Synchronised" for status in station.tileProgrammingState):
        pytest.fail(f"Not all tiles are Synchronised: {station.tileProgrammingState}")


@when(
    parsers.parse(
        "I acquire calibration data for channels {first_channel:d} to {last_channel:d}"
    ),
    target_fixture="acquisition",
)
def acquire_data_for_calibration(
    station: tango.DeviceProxy,
    daq_device: tango.DeviceProxy,
    first_channel: int,
    last_channel: int,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> Generator[dict[str, Any], None, None]:
    """
    Command the station to acquire calibration data for a range of channels.

    Subscribes to the DAQ ``dataReceivedResult`` attribute before issuing the
    command so that the correlator file events emitted during acquisition are
    captured for the assertion step.

    An acquisition owns the LMC DAQ and keeps every TPM transmitting for as long
    as it runs, so one left behind by a scenario that failed part way through
    reconfigures the DAQ out from under whatever test runs next. This therefore
    cleans up after itself rather than relying on the scenario's ``then`` steps
    having waited for the acquisition to finish.

    :param station: A 'tango.DeviceProxy' to the SpsStation device.
    :param daq_device: A 'tango.DeviceProxy' to the DAQ device.
    :param first_channel: the first channel to acquire data for.
    :param last_channel: the last channel to acquire data for.
    :param change_event_callbacks: a dictionary of callables to be used as
        tango change event callbacks.

    :yields: details of the submitted acquisition, for the assertion step.
    """
    daq_device.subscribe_event(
        "dataReceivedResult",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["data_received_callback"],
    )
    # Consume the initial (subscription) event.
    change_event_callbacks["data_received_callback"].assert_change_event(Anything)

    [result_code], [command_id] = station.AcquireDataForCalibration(
        json.dumps({"first_channel": first_channel, "last_channel": last_channel})
    )
    assert ResultCode(result_code) == ResultCode.QUEUED

    yield {
        "command_id": command_id,
        "requested_channels": list(range(first_channel, last_channel + 1)),
    }

    if get_lrc_finished(station, command_id):
        return
    print(f"Acquisition {command_id} is still running; waiting for it to finish.")
    if wait_for_condition(
        lambda: bool(get_lrc_finished(station, command_id)),
        timeout=ACQUISITION_TEARDOWN_GRACE,
    ):
        return
    print(f"Acquisition {command_id} did not finish; aborting it.")
    station.Abort()
    assert wait_for_condition(
        lambda: not get_lrc_executing(station, command_id)
        and not get_lrc_queued(station, command_id),
        timeout=CONCURRENT_COMMAND_TIMEOUT,
    ), f"Acquisition {command_id} is still running after being aborted."


def _await_while_acquiring(
    station: tango.DeviceProxy,
    acquisition_id: str,
    wanted: Callable[[], _Found],
    *,
    waiting_for: str,
    timeout: float,
) -> _Found:
    """
    Wait for something to happen, while the acquisition is still running.

    Everything this scenario waits for is only meaningful for as long as the
    acquisition is executing, so the acquisition reaching ``lrcFinished`` is a
    failure rather than something to keep waiting through: whatever we were
    waiting for has not been shown to overlap with the acquisition. Stop and say
    so, instead of timing out with no explanation.

    Polls rather than subscribing to change events, so this works for attributes
    the station reports on demand as well as for its LRC attributes.

    :param station: A 'tango.DeviceProxy' to the SpsStation device.
    :param acquisition_id: the acquisition that must still be running.
    :param wanted: returns something truthy once the wait is over, such as the
        LRC entry being waited for, and something falsy until then.
    :param waiting_for: what is being waited for, for failure messages.
    :param timeout: how long to wait, in seconds.

    :return: whatever ``wanted`` returned once it was truthy.
    """
    deadline = time.time() + timeout
    while True:
        found = wanted()
        if found:
            return found
        acquisition = get_lrc_finished(station, acquisition_id)
        if acquisition:
            pytest.fail(
                f"The acquisition finished while waiting for {waiting_for}, so the "
                f"two were not shown to overlap. Acquisition: {acquisition}"
            )
        if time.time() > deadline:
            pytest.fail(
                f"Timed out after {timeout} seconds waiting for {waiting_for}. "
                f"lrcQueue={station.lrcQueue}, lrcExecuting={station.lrcExecuting}"
            )
        time.sleep(_POLL_INTERVAL)


def _await_lrc_during_acquisition(
    station: tango.DeviceProxy,
    command_id: str,
    acquisition_id: str,
    description: str,
) -> dict[str, Any]:
    """
    Wait for a command submitted mid-acquisition, failing if it was queued behind.

    Whichever of the two commands reaches ``lrcFinished`` first tells us whether
    they really executed concurrently: if the acquisition gets there first, the
    other command was waiting for it rather than running alongside it.

    :param station: A 'tango.DeviceProxy' to the SpsStation device.
    :param command_id: the command to wait for.
    :param acquisition_id: the acquisition it should not have waited for.
    :param description: what the command is, for failure messages.

    :return: the command's ``lrcFinished`` entry.
    """
    return _await_while_acquiring(
        station,
        acquisition_id,
        lambda: get_lrc_finished(station, command_id),
        waiting_for=f"{description} to finish",
        timeout=CONCURRENT_COMMAND_TIMEOUT,
    )


@when(
    "I start and stop the beamformer while the acquisition is still running",
    target_fixture="beamformer_run",
)
def start_and_stop_beamformer_during_acquisition(
    station: tango.DeviceProxy,
    acquisition: dict[str, Any],
) -> dict[str, Any]:
    """
    Run the beamformer up and down again while calibration data is coming in.

    This is the scan half of an observation, exercised against a station that is
    mid-acquisition. The TPMs can transmit beamformed and channelised data at the
    same time, so both should proceed: ``StartBeamformer`` and
    ``StopBeamformerForChannels`` are ordinary long running commands on the general
    lane, and would have sat in the queue until the acquisition finished before
    ``AcquireDataForCalibration`` was given a lane of its own.

    :param station: A 'tango.DeviceProxy' to the SpsStation device.
    :param acquisition: details of the submitted acquisition.

    :return: what was observed while the beamformer ran, for the assertion step.
    """
    acquisition_id = acquisition["command_id"]
    # AcquireDataForCalibration returns as soon as it has been queued on the
    # calibration lane, so wait for the station to report it executing rather than
    # assuming it already does.
    _await_while_acquiring(
        station,
        acquisition_id,
        lambda: get_lrc_executing(station, acquisition_id),
        waiting_for="the acquisition to start executing",
        timeout=ACQUISITION_START_TIMEOUT,
    )

    # Hardware may arrive with the beamformer already running, in which case
    # starting it proves nothing. Put it in a known state first.
    if station.isBeamformerRunning:
        [result_code], [command_id] = station.StopBeamformerForChannels(json.dumps({}))
        assert ResultCode(result_code) == ResultCode.QUEUED
        _await_lrc_during_acquisition(
            station, command_id, acquisition_id, "the initial StopBeamformer"
        )
        _await_while_acquiring(
            station,
            acquisition_id,
            lambda: not station.isBeamformerRunning,
            waiting_for="the beamformer to stop",
            timeout=CONCURRENT_COMMAND_TIMEOUT,
        )

    observed: dict[str, Any] = {}

    [start_code], [start_id] = station.StartBeamformer(json.dumps({"duration": -1}))
    assert ResultCode(start_code) == ResultCode.QUEUED
    observed["start"] = _await_lrc_during_acquisition(
        station, start_id, acquisition_id, "StartBeamformer"
    )
    _await_while_acquiring(
        station,
        acquisition_id,
        lambda: station.isBeamformerRunning,
        waiting_for="the beamformer to start",
        timeout=CONCURRENT_COMMAND_TIMEOUT,
    )
    observed["acquiring_while_beamforming"] = bool(
        get_lrc_executing(station, acquisition_id)
    )

    [stop_code], [stop_id] = station.StopBeamformerForChannels(json.dumps({}))
    assert ResultCode(stop_code) == ResultCode.QUEUED
    observed["stop"] = _await_lrc_during_acquisition(
        station, stop_id, acquisition_id, "StopBeamformerForChannels"
    )
    _await_while_acquiring(
        station,
        acquisition_id,
        lambda: not station.isBeamformerRunning,
        waiting_for="the beamformer to stop",
        timeout=CONCURRENT_COMMAND_TIMEOUT,
    )
    observed["acquiring_after_beamforming"] = bool(
        get_lrc_executing(station, acquisition_id)
    )
    return observed


@then("the beamformer ran while calibration data was still being acquired")
def check_beamformer_ran_during_acquisition(beamformer_run: dict[str, Any]) -> None:
    """
    Confirm the beamformer started and stopped without the acquisition ending.

    :param beamformer_run: what was observed while the beamformer ran.
    """
    assert (
        beamformer_run["start"]["status"] == "COMPLETED"
    ), f"StartBeamformer did not complete: {beamformer_run['start']}"
    assert (
        beamformer_run["stop"]["status"] == "COMPLETED"
    ), f"StopBeamformerForChannels did not complete: {beamformer_run['stop']}"
    assert beamformer_run["acquiring_while_beamforming"], (
        "The acquisition was no longer executing by the time the beamformer was "
        "running, so the two were not shown to overlap."
    )
    assert beamformer_run["acquiring_after_beamforming"], (
        "The acquisition finished while the beamformer was being stopped, so the "
        "scan was not shown to complete within the acquisition."
    )


@then("the requested number of correlator files are produced")
def check_requested_correlator_files_produced(
    station: tango.DeviceProxy,
    acquisition: dict[str, Any],
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Confirm a correlator file was produced for every requested channel.

    Two independent signals are checked:

    * the DAQ emits one ``("tc_correlator", ...)`` ``dataReceivedResult`` event per
      correlator file it writes, and
    * the command reports which requested channels failed to yield a correlator
      file via the ``dropped_channels`` field of its result.

    :param station: A 'tango.DeviceProxy' to the SpsStation device.
    :param acquisition: details of the submitted acquisition.
    :param change_event_callbacks: a dictionary of callables to be used as
        tango change event callbacks.
    """
    command_id = acquisition["command_id"]
    requested_channels = acquisition["requested_channels"]

    # Waits for the LRC queue to drain and asserts it completed with OK.
    wait_for_lrc_result(station, command_id, ResultCode.OK, ACQUIRE_TIMEOUT)

    # One dataReceivedResult "correlator" event should have been pushed by the
    # DAQ for each requested channel's correlator file.
    data_received = change_event_callbacks["data_received_callback"]
    for _ in requested_channels:
        data_received.assert_change_event(
            ("tc_correlator", Anything), consume_nonmatches=True
        )

    # Cross-check against the command's own accounting: no requested channel
    # should have been dropped, i.e. every requested correlator file was made.
    finished = get_lrc_finished(station, command_id)
    _, payload = finished["result"]
    dropped_channels = payload["dropped_channels"]
    received_count = len(requested_channels) - len(dropped_channels)
    assert received_count == len(requested_channels), (
        f"Expected {len(requested_channels)} correlator files, "
        f"got {received_count}. Dropped channels: {dropped_channels}"
    )


@then("no tile is left transmitting data samples")
def check_no_pending_data_requests(station_tiles: list[tango.DeviceProxy]) -> None:
    """
    Confirm every tile has finished the data request the acquisition made.

    The acquisition stops transmission on its way out, whichever way it exits, so
    ``pendingDataRequests`` should fall back to False on every tile once it
    reports itself finished. Checking that here confirms the teardown really
    happened, and stops a finished acquisition from transmitting into whatever
    runs next.

    :param station_tiles: the Tile devices belonging to the station under test.
    """
    assert station_tiles, "No tile devices were found for this station."
    for tile in station_tiles:
        AttributeWaiter(timeout=TRANSMISSION_DRAIN_TIMEOUT).wait_for_value(
            tile, "pendingDataRequests", False, lookahead=5
        )
