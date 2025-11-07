# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains pytest-specific test harness for SPSHW functional tests."""
from __future__ import annotations

import json
import os
import queue
import re
import time
import warnings
from datetime import datetime
from time import sleep
from typing import Any, Iterator
from unittest.mock import patch

import _pytest
import pytest
import tango
from ska_control_model import AdminMode
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup

from tests.harness import (
    DEFAULT_STATION_LABEL,
    SpsTangoTestHarness,
    SpsTangoTestHarnessContext,
    get_sps_station_name,
)

from ..test_tools import AttributeWaiter

RFC_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


# TODO: https://github.com/pytest-dev/pytest-forked/issues/67
# We're stuck on pytest 6.2 until this gets fixed, and this version of
# pytest is not fully typehinted
def pytest_addoption(
    parser: _pytest.config.argparsing.Parser,  # type: ignore[name-defined]
) -> None:
    """
    Add a command line option to pytest.

    This is a pytest hook, here implemented to add the `--true-context`
    option, used to indicate that a true Tango subsystem is available,
    so there is no need for the test harness to spin up a Tango test
    context.

    :param parser: the command line options parser
    """
    parser.addoption(
        "--true-context",
        action="store_true",
        default=False,
        help=(
            "Tell pytest that you have a true Tango context and don't "
            "need to spin up a Tango test context"
        ),
    )
    parser.addoption(
        "--hw-deployment",
        action="store_true",
        default=False,
        help=(
            "Tell pytest that you have a true Tango context against HW and can "
            "run HW only tests"
        ),
    )


@pytest.fixture(name="stations_devices_exported")
def station_devices_exported_fixture(
    station_tiles: list[tango.DeviceProxy],
    station_subracks: list[tango.DeviceProxy],
    station: tango.DeviceProxy,
    station_daqs: list[tango.DeviceProxy],
) -> list[tango.DeviceProxy]:
    """
    Fixture containing a DeviceProxy for all station devices.

    :param station_tiles: A list containing the ``tango.DeviceProxy``
        of the station tiles. Or Empty list if no devices found.
    :param station_subracks: A list containing the ``tango.DeviceProxy``
        of the stations subracks. Or Empty list if no devices found.
    :param station: A ``tango.DeviceProxy`` to the stations under test.
    :param station_daqs: A list containing the ``tango.DeviceProxy``
         of the stations daqs. Or Empty list if no devices found.

    :returns: A list of DeviceProxy for available station devices.
    """
    stations = [station] if station is not None else []
    return station_tiles + station_subracks + stations + station_daqs


@pytest.fixture(name="station")
def station_fixture(
    station_label: str | None, true_context: bool
) -> tango.DeviceProxy | None:
    """
    Fixture containing a proxy to the station under test.

    :param station_label: the names of the station we are testing against.
    :param true_context: Whether we are testing against a real deployment.

    :returns: a proxy to the station under test.
    """
    if not true_context:
        return None
    if not station_label:
        station_label = DEFAULT_STATION_LABEL
    return tango.DeviceProxy(get_sps_station_name(station_label))


@pytest.fixture(name="sps_devices_exported")
def sps_devices_exported_fixture(
    exported_tiles: list[tango.DeviceProxy],
    exported_subracks: list[tango.DeviceProxy],
    exported_stations: list[tango.DeviceProxy],
    exported_daqs: list[tango.DeviceProxy],
    exported_pdus: list[tango.DeviceProxy],
) -> list[tango.DeviceProxy]:
    """
    Fixture containing a DeviceProxy for all sps devices.

    :param exported_tiles: A list containing the ``tango.DeviceProxy``
        of the exported tiles. Or Empty list if no devices exported.
    :param exported_subracks: A list containing the ``tango.DeviceProxy``
        of the exported subracks. Or Empty list if no devices exported.
    :param exported_stations: A list containing the ``tango.DeviceProxy``
        of the exported stations. Or Empty list if no devices exported.
    :param exported_daqs: A list containing the ``tango.DeviceProxy``
         of the exported daqs. Or Empty list if no devices exported.
    :param exported_pdus: A list containing the ``tango.DeviceProxy``
         of the exported pdus. Or Empty list if no devices exported.

    :returns: A list of DeviceProxy for exported sps devices.
    """
    return (
        exported_tiles
        + exported_subracks
        + exported_stations
        + exported_daqs
        + exported_pdus
    )


@pytest.fixture(name="exported_tiles")
def exported_tiles_fixture(true_context: bool) -> list[tango.DeviceProxy]:
    """
    Return a list with a DeviceProxy to the tiles under test.

    :param true_context: whether to test against an existing Tango deployment

    :return: A list containing the ``tango.DeviceProxy`` of the exported tiles.
        Or Empty list if no devices exported.
    """
    if true_context:
        return [
            tango.DeviceProxy(trl)
            for trl in tango.Database().get_device_exported("low-mccs/tile/*")
        ]
    return []


@pytest.fixture(name="station_tiles")
def available_station_tiles(
    true_context: bool, station_label: str | None
) -> list[tango.DeviceProxy]:
    """
    Return a list with a DeviceProxy to the tiles in station.

    :param true_context: whether to test against an existing Tango deployment
    :param station_label: the label of the station we are testing against.

    :return: A list containing the ``tango.DeviceProxy`` of the tiles in station.
        Or Empty list if no devices available
    """
    if not station_label:
        station_label = DEFAULT_STATION_LABEL

    tile_pattern = rf"low-mccs/tile/{re.escape(station_label)}-tpm(?P<number>\d{{2}})"

    if true_context:
        _available_station_tiles = []
        for exported_tile_trl in tango.Database().get_device_exported(
            f"low-mccs/tile/{station_label}*"
        ):
            match = re.match(tile_pattern, exported_tile_trl)
            if match:
                try:
                    exported_tile = tango.DeviceProxy(exported_tile_trl)
                    exported_tile.ping()
                    _available_station_tiles.append(exported_tile)
                except tango.DevFailed:
                    pass

        return _available_station_tiles

    warnings.warn("This fixture does not yet support a simulated context.")
    return []


@pytest.fixture(name="exported_pdus")
def exported_pdus_fixture(true_context: bool) -> list[tango.DeviceProxy]:
    """
    Return a list with a DeviceProxy to the pdus under test.

    :param true_context: whether to test against an existing Tango deployment

    :return: A list containing the ``tango.DeviceProxy`` of the exported PDU'.
        Or Empty list if no devices exported.
    """
    if true_context:
        return [
            tango.DeviceProxy(trl)
            for trl in tango.Database().get_device_exported("low-mccs/pdu/*")
        ]
    return []


@pytest.fixture(name="exported_subracks")
def exported_subracks_fixture(true_context: bool) -> list[tango.DeviceProxy]:
    """
    Return a list with a DeviceProxy to the subracks under test.

    :param true_context: whether to test against an existing Tango deployment

    :return: A list containing the ``tango.DeviceProxy`` of the exported subracks.
        Or Empty list if no devices exported.
    """
    if true_context:
        return [
            tango.DeviceProxy(trl)
            for trl in tango.Database().get_device_exported("low-mccs/subrack/*")
        ]
    return []


@pytest.fixture(name="station_subracks")
def available_station_subracks(
    true_context: bool, station_label: str | None
) -> list[tango.DeviceProxy]:
    """
    Return a list with a DeviceProxy to the subracks in station.

    :param true_context: whether to test against an existing Tango deployment
    :param station_label: the label of the station we are testing against.

    :return: A list containing the ``tango.DeviceProxy`` of the subracks in station.
        Or Empty list if no devices available
    """
    if not station_label:
        station_label = DEFAULT_STATION_LABEL

    subrack_pattern = (
        rf"low-mccs/subrack/{re.escape(station_label)}-sr(?P<number>\d{{2}})"
    )

    if true_context:
        _available_station_subracks = []
        for exported_subrack_trl in tango.Database().get_device_exported(
            "low-mccs/subrack/*"
        ):
            match = re.match(subrack_pattern, exported_subrack_trl)
            if match:
                try:
                    exported_subrack = tango.DeviceProxy(exported_subrack_trl)
                    exported_subrack.ping()
                    _available_station_subracks.append(exported_subrack)
                except tango.DevFailed:
                    pass

        return _available_station_subracks

    warnings.warn("This fixture does not yet support a simulated context.")
    return []


@pytest.fixture(name="exported_stations")
def exported_stations_fixture(true_context: bool) -> list[tango.DeviceProxy]:
    """
    Return the trls of the stations under test.

    :param true_context: whether to test against an existing Tango deployment

    :return: A list containing the ``tango.DeviceProxy`` of the exported stations.
        Or Empty list if no devices exported.
    """
    if true_context:
        return [
            tango.DeviceProxy(trl)
            for trl in tango.Database().get_device_exported("low-mccs/spsstation/*")
        ]
    return []


@pytest.fixture(name="exported_daqs")
def exported_daq_fixture(true_context: bool) -> list[tango.DeviceProxy]:
    """
    Return the trls of the daq under test.

    :param true_context: whether to test against an existing Tango deployment

    :return: A list containing the ``tango.DeviceProxy`` of the exported daqs.
        Or Empty list if no devices exported.
    """
    if true_context:
        return [
            tango.DeviceProxy(trl)
            for trl in tango.Database().get_device_exported("low-mccs/daqreceiver/*")
        ]
    return []


@pytest.fixture(name="station_daqs")
def available_station_daqs(
    true_context: bool, station_label: str | None
) -> list[tango.DeviceProxy]:
    """
    Return a list of ``tango.DeviceProxy`` to the daqs in station.

    :param true_context: whether to test against an existing Tango deployment
    :param station_label: the label of the station we are testing against.

    :return: A list containing the ``tango.DeviceProxy`` of the daqs in station.
        Or Empty list if no devices available
    """
    if not station_label:
        station_label = DEFAULT_STATION_LABEL

    daq_pattern = rf"low-mccs/daqreceiver/{re.escape(station_label)}(?:-bandpass)?"

    if true_context:
        _available_station_daqs = []
        for exported_daq_trl in tango.Database().get_device_exported(
            "low-mccs/daqreceiver/*"
        ):
            match = re.match(daq_pattern, exported_daq_trl)
            if match:
                try:
                    exported_daq = tango.DeviceProxy(exported_daq_trl)
                    exported_daq.ping()
                    _available_station_daqs.append(exported_daq)
                except tango.DevFailed:
                    pass

        return _available_station_daqs

    warnings.warn("This fixture does not yet support a simulated context.")
    return []


@pytest.fixture(name="available_stations")
def available_stations_fixture(true_context: bool) -> list[str]:
    """
    Return the name of all stations available in environment.

    When a True context this will return all exported stations
    that can be pinged.
    When in a test context we will simply return the default

    :param true_context: whether to test against an existing Tango deployment

    :return: the name of the station under test
    """
    if true_context:
        db = tango.Database()
        stations_exported = db.get_device_exported("low-mccs/spsstation/*")
        _available_stations = []
        for station in stations_exported:
            try:
                exp_station_instance = tango.DeviceProxy(station)
                # Ping to check that it is available.
                exp_station_instance.ping()
                _available_stations.append(station)
            except tango.DevFailed:
                pass
        return [
            str(station).rsplit("low-mccs/spsstation/", maxsplit=1)[-1]
            for station in _available_stations
        ]
    try:
        tango.DeviceProxy(get_sps_station_name()).ping()
        return [DEFAULT_STATION_LABEL]
    except tango.DevFailed:
        return []


@pytest.fixture(name="available_tiles")
def available_tiles_fixture(true_context: bool) -> list[str]:
    """
    Return the name of the tiles under test.

    :param true_context: whether to test against an existing Tango deployment

    :return: the name of the station under test
    """
    if true_context:
        db = tango.Database()
        tiles = db.get_device_exported("low-mccs/tile/*")
        return [str(tile).rsplit("low-mccs/tile/", maxsplit=1)[-1] for tile in tiles]
    return [DEFAULT_STATION_LABEL]


@pytest.fixture(name="true_context", scope="session")
def true_context_fixture(request: pytest.FixtureRequest) -> bool:
    """
    Return whether to test against an existing Tango deployment.

    If True, then Tango is already deployed, and the tests will be run
    against that deployment.

    If False, then Tango is not deployed, so the test harness will stand
    up a test context and run the tests against that.

    :param request: A pytest object giving access to the requesting test
        context.

    :return: whether to test against an existing Tango deployment
    """
    if request.config.getoption("--true-context"):
        return True
    if os.getenv("TRUE_TANGO_CONTEXT", None):
        return True
    return False


@pytest.fixture(name="hw_context", scope="session")
def hw_context_fixture(request: pytest.FixtureRequest) -> bool:
    """
    Return whether to test against an real HW only.

    :param request: A pytest object giving access to the requesting test
        context.

    :return: whether to to test against an real HW only.
    """
    return request.config.getoption("--hw-deployment")


@pytest.fixture(name="subrack_address", scope="module")
def subrack_address_fixture() -> tuple[str, int] | None:
    """
    Return the address of a subrack.

    If a real hardware subrack is present, or there is a pre-existing
    simulator, then this fixture returns the subrack address as a
    (hostname, port) tuple. If there is no pre-existing subrack server,
    then this fixture returns None, indicating that the test harness
    should stand up a subrack simulator server itself.

    :return: the address of a subrack, or None if a subrack server is
        not yet running.
    """
    address_var = "SUBRACK_ADDRESS"
    if address_var in os.environ:
        [host, port_str] = os.environ[address_var].split(":")
        return host, int(port_str)
    return None


@pytest.fixture(name="station_label", scope="module")
def station_label_fixture() -> str | None:
    """
    Return the name of the station under test.

    :return: the name of the station under test.
    """
    return os.environ.get("STATION_LABEL")


# pylint: disable=too-many-arguments
@pytest.fixture(name="functional_test_context", scope="module")
def functional_test_context_fixture(
    true_context: bool,
    station_label: str | None,
    subrack_id: int,
    subrack_address: tuple[str, int] | None,
    daq_id: int,
    db_temperature_thresholds: dict[str, Any],
    db_voltage_thresholds: dict[str, Any],
    db_current_thresholds: dict[str, Any],
) -> Iterator[SpsTangoTestHarnessContext]:
    """
    Yield a Tango context containing the device/s under test.

    :param true_context: whether to test against an existing Tango
        deployment
    :param station_label: name of the station under test.
    :param subrack_id: ID of the subrack Tango device.
    :param subrack_address: the address of a subrack server if one is
        already running; otherwise None.
    :param daq_id: the ID of the daq receiver
    :param db_temperature_thresholds: fixture containing the mocked temperature
        thresholds in db at point of startup.
    :param db_voltage_thresholds: fixture containing the mocked voltage
        thresholds in db at point of startup.
    :param db_current_thresholds: fixture containing the mocked current
        thresholds in db at point of startup.

    :yields: a Tango context containing the devices under test
    """
    if not true_context:
        with patch(
            "ska_low_mccs_spshw.tile.firmware_threshold_interface.Database"
        ) as mock_tango_db:
            mock_tango_db.return_value.get_device_attribute_property.return_value = {
                "temperatures": db_temperature_thresholds,
                "voltages": db_voltage_thresholds,
                "currents": db_current_thresholds,
            }

            harness = SpsTangoTestHarness(station_label)
            if subrack_address is None:
                harness.add_subrack_simulator(subrack_id)
            harness.add_subrack_device(subrack_id, subrack_address)
            harness.add_tile_device(1)
            harness.set_sps_station_device(
                subrack_ids=range(1, 2), tile_ids=range(1, 2)
            )
            with harness as context:
                yield context
    else:
        harness = SpsTangoTestHarness(station_label)
        with harness as context:
            yield context


@pytest.fixture(name="change_event_callbacks")
def change_event_callbacks_fixture() -> MockTangoEventCallbackGroup:
    """
    Return a dictionary of callables to be used as Tango change event callbacks.

    :return: a dictionary of callables to be used as tango change event
        callbacks.
    """
    return MockTangoEventCallbackGroup(
        "pdu_state",
        "subrack_state",
        "subrack_fan_mode",
        "subrack_fan_speeds",
        "subrack_fan_speeds_percent",
        "subrack_tpm_power_state",
        "subrack_tpm_present",
        "daq_state",
        "daq_long_running_command_status",
        "daq_long_running_command_result",
        "daq_xPolBandpass",
        "daq_yPolBandpass",
        "data_received_callback",
        "tile_adminMode",
        "device_state",
        "device_adminmode",
        "tile_programming_state",
        timeout=30.0,
    )


@pytest.fixture(name="acquisition_duration", scope="session")
def acquisition_duration_fixture() -> int:
    """
    Return the duration of data capture in seconds.

    :return: Duration of data capture.
    """
    return 2


# pylint: disable=inconsistent-return-statements
def poll_until_consumer_running(
    daq: tango.DeviceProxy, wanted_consumer: str, no_of_iters: int = 10
) -> None:
    """
    Poll until a specific consumer is running.

    This function recursively calls itself up to `no_of_iters` times.

    :param daq: the DAQ receiver Tango device
    :param wanted_consumer: the consumer we're waiting for
    :param no_of_iters: number of times to iterate
    """
    status = json.loads(daq.DaqStatus())
    for consumer in status["Running Consumers"]:
        if wanted_consumer in consumer:
            return

    if no_of_iters == 1:
        pytest.fail(f"Wanted consumer: {wanted_consumer} not started.")

    sleep(2)  # Waiting for SKUID to timeout...
    return poll_until_consumer_running(daq, wanted_consumer, no_of_iters - 1)


def poll_until_consumers_running(
    daq: tango.DeviceProxy, wanted_consumer_list: list[str], no_of_iters: int = 5
) -> None:
    """
    Poll until a list of consumers are running.

    :param daq: the DAQ receiver Tango device
    :param wanted_consumer_list: the consumers we're waiting for
    :param no_of_iters: number of times to iterate
    """
    for consumer in wanted_consumer_list:
        poll_until_consumer_running(daq, consumer, no_of_iters)


# pylint: disable=inconsistent-return-statements
def poll_until_consumers_stopped(daq: tango.DeviceProxy, no_of_iters: int = 5) -> None:
    """
    Poll until device is in wanted state.

    This function recursively calls itself up to `no_of_iters` times.

    :param daq: the DAQ receiver Tango device
    :param no_of_iters: number of times to iterate
    """
    status = json.loads(daq.DaqStatus())
    if status["Running Consumers"] == []:
        return

    if no_of_iters == 1:
        msg = f'Consumers not stopped: {status["Running Consumers"]}.\n'
        msg += f"CommandResult: {daq.longRunningCommandResult}\n"
        msg += f"CommandQueue: {daq.longRunningCommandsInQueue}\n"
        pytest.fail(msg)

    sleep(2)
    return poll_until_consumers_stopped(daq, no_of_iters - 1)


def poll_until_command_result(
    device: tango.DeviceProxy, cmd_id: str, expected_result: str, no_of_iters: int = 5
) -> None:
    """
    Poll until command has reached state.

    This function recursively calls itself up to `no_of_iters` times.

    :param device: the TANGO device
    :param expected_result: the command state we're waiting for
    :param cmd_id: The command ID we're interested in.
    :param no_of_iters: number of times to iterate
    """
    lrc_result = None
    lrc_status = device.longRunningCommandStatus
    try:
        # Extract the result of the cmd_id.
        lrc_result = lrc_status[lrc_status.index(cmd_id) + 1]
    except ValueError as e:
        lrc_result = e
        # pass
    if lrc_result == expected_result:
        return
    if no_of_iters == 1:
        pytest.fail(
            f"Command {cmd_id} did not reach desired state: "
            f"{device.longRunningCommandStatus}\n"
            f"Result: {lrc_result}"
        )
    if lrc_result != expected_result:
        time.sleep(1)
        poll_until_command_result(device, cmd_id, expected_result, no_of_iters - 1)


# pylint: disable=inconsistent-return-statements
def poll_until_state_change(
    device: tango.DeviceProxy, wanted_state: tango.DevState, no_of_iters: int = 5
) -> None:
    """
    Poll until device is in wanted state.

    This function recursively calls itself up to `no_of_iters` times.

    :param device: the TANGO device
    :param wanted_state: the state we're waiting for
    :param no_of_iters: number of times to iterate
    """
    if device.state() == wanted_state:
        return

    if no_of_iters == 1:
        print(f"{device.healthreport=}")
        pytest.fail(
            f"device not in desired state, \
        wanted: {wanted_state}, actual: {device.state()}"
        )

    sleep(2)
    return poll_until_state_change(device, wanted_state, no_of_iters - 1)


def expect_attribute(
    tango_device: tango.DeviceProxy,
    attr: str,
    value: Any,
    *,
    timeout: float = 60.0,
) -> bool:
    """
    Wait for Tango attribute to have a certain value using a subscription.

    Sets up a subscription to a Tango device attribute,
    waits for the attribute to have the provided value within a given time,
    then removes the subscription.

    :param tango_device: a DeviceProxy to a Tango device
    :param attr: the name of the attribute to be monitored
    :param value: the attribute value we're waiting for
    :param timeout: the maximum time to wait, in seconds
    :return: True if the attribute has the expected value within the given timeout
    """
    print(f"Expecting {tango_device.dev_name()}/{attr} == {value!r} within {timeout}s")
    _queue: queue.SimpleQueue[tango.EventData] = queue.SimpleQueue()
    subscription_id = tango_device.subscribe_event(
        attr,
        tango.EventType.CHANGE_EVENT,
        _queue.put,
    )
    deadline = time.time() + timeout
    try:
        while True:
            event = _queue.get(timeout=deadline - time.time())
            print(f"Got {tango_device.dev_name()}/{attr} == {event.attr_value.value!r}")
            if event.attr_value.value == value:
                return True
    finally:
        tango_device.unsubscribe_event(subscription_id)


def verify_bandpass_state(daq_device: tango.DeviceProxy, state: bool) -> None:
    """
    Verify that the bandpass monitor is in the desired state.

    :param daq_device: A 'tango.DeviceProxy' to the Daq device.
    :param state: the desired state of the bandpass monitor.
    """
    time_elapsed = 0
    timeout = 10
    while time_elapsed < timeout:
        daq_status = json.loads(daq_device.DaqStatus())
        if daq_status["Bandpass Monitor"] == state:
            break
        time.sleep(1)
        time_elapsed += 1
    assert daq_status["Bandpass Monitor"] == state


@pytest.fixture(name="synchronised_tile_device")
def synchronised_tile_device_fixture(
    tile_device: tango.DeviceProxy,
) -> Iterator[tango.DeviceProxy]:
    """
    Fixture that returns a DeviceProxy to a Synchronised TPM.

    :param tile_device: fixture that provides a
        :py:class:`tango.DeviceProxy` to the device under test, in a
        :py:class:`tango.test_context.DeviceTestContext`.

    :yield: a 'DeviceProxy' to the Synchronised tile.
    """
    if tile_device.adminMode != AdminMode.ONLINE:
        tile_device.adminMode = AdminMode.ONLINE
        AttributeWaiter(timeout=60).wait_for_value(
            tile_device,
            "tileProgrammingState",
            None,
            lookahead=5,
        )

    # Grab the previous GRT, used to return to this state in teardown.
    initial_grt = tile_device.globalreferenceTime

    if tile_device.tileProgrammingState != "Synchronised":
        if initial_grt == "":
            start_time = datetime.strftime(
                datetime.fromtimestamp(time.time() + 2), RFC_FORMAT
            )
            tile_device.globalreferenceTime = start_time
        if tile_device.state() in [tango.DevState.UNKNOWN]:
            # We are adminMode.ONLINE, we should discover state.
            AttributeWaiter(timeout=8).wait_for_value(
                tile_device,
                "tileProgrammingState",
                None,
            )
        if tile_device.state() == tango.DevState.OFF:
            tile_device.on()
        else:
            tile_device.initialise()

        AttributeWaiter(timeout=60).wait_for_value(
            tile_device,
            "tileProgrammingState",
            "Synchronised",
            lookahead=5,
        )

    yield tile_device

    # Restore the previous GRT
    tile_device.globalreferenceTime = initial_grt
