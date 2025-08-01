#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests of the tile component manage."""
from __future__ import annotations

import copy
import ipaddress
import json
import logging
import random
import unittest.mock
from typing import Iterator

import numpy as np
import pytest
import tango
from ska_control_model import (
    CommunicationStatus,
    HealthState,
    PowerState,
    ResultCode,
    TaskStatus,
)
from ska_low_mccs_common.device_proxy import MccsDeviceProxy
from ska_tango_testing.mock import MockCallableGroup

from ska_low_mccs_spshw.station import (
    SpsStationComponentManager,
    SpsStationSelfCheckManager,
)
from tests.harness import (
    SpsTangoTestHarness,
    get_bandpass_daq_name,
    get_lmc_daq_name,
    get_subrack_name,
    get_tile_name,
)


@pytest.fixture(name="num_tiles_to_add")
def num_tiles_to_add_fixture() -> int:
    """
    Return number of tiles to add to test.

    :return: Number of tiles to add to harness.
    """
    return 4


# pylint: disable = too-many-arguments
@pytest.fixture(name="test_context")
def fixture_test_context(
    subrack_id: int,
    mock_subrack_device_proxy: unittest.mock.Mock,
    tile_id: int,
    mock_tile_device_proxy: unittest.mock.Mock,
    daq_id: int,
    num_tiles_to_add: int,
) -> Iterator[None]:
    """
    Yield into a context in which Tango is running, with mock devices.

    The station component manager acts as a Tango client to the subrack
    and tile Tango device. In these unit tests, the subrack and tile
    Tango devices are mocked out, but since the station component
    manager uses tango to talk to them, we still need some semblance of
    a tango subsystem in place. Here, we assume that the station has
    only one subrack and four tiles.

    :param subrack_id: ID of the subrack Tango device to be mocked
    :param mock_subrack_device_proxy: a mock subrack device proxy
        that has been configured with the required subrack behaviours.
    :param tile_id: ID of the tile Tango device to be mocked
    :param mock_tile_device_proxy: a mock tile device proxy
        that has been configured with the required subrack behaviours.
    :param daq_id: the ID number of the DAQ receiver.
    :param num_tiles_to_add: Number of tiles to add.

    :yields: into a context in which Tango is running, with a mock
        subrack device.
    """
    harness = SpsTangoTestHarness()
    harness.add_mock_subrack_device(subrack_id, mock_subrack_device_proxy)
    harness.add_mock_subrack_device(subrack_id + 1, mock_subrack_device_proxy)
    # Add 4 tiles.
    for i in range(0, num_tiles_to_add):
        harness.add_mock_tile_device(tile_id + i, mock_tile_device_proxy)
    harness.set_daq_instance(receiver_ip="172.17.0.230")
    harness.set_daq_instance(receiver_ip="172.17.0.231")
    harness.set_lmc_daq_device(daq_id=daq_id, address=None)
    harness.set_bandpass_daq_device(daq_id=daq_id, address=None)
    with harness:
        yield


@pytest.fixture(name="callbacks")
def callbacks_fixture() -> MockCallableGroup:
    """
    Return a dictionary of callables to be used as callbacks.

    :return: a dictionary of callables to be used as callbacks.
    """
    return MockCallableGroup(
        "communication_status",
        "component_state",
        "task",
        "tile_health",
        "subrack_health",
        timeout=15.0,
    )


@pytest.fixture(name="station_label")
def station_label_fixture() -> str:
    """
    Station label for use in testing.

    :returns: a station label for use in testing.
    """
    return "ci-1"


@pytest.fixture(name="mock_tile_proxy")
def mock_tile_proxy_fixture(
    tile_id: int, station_label: str, logger: logging.Logger
) -> MccsDeviceProxy:
    """
    Proxy to the device which the component manager has been given.

    :param tile_id: the id of the tile which the component manager has been given.
    :param station_label: the label of the station.
    :param logger: a logger for use in testing.

    :returns: A proxy to the device which the component manager has been given.
    """
    return MccsDeviceProxy(get_tile_name(tile_id, station_label), logger)


# pylint: disable=too-many-arguments
@pytest.fixture(name="station_component_manager")
def station_component_manager_fixture(
    test_context: None,
    subrack_id: int,
    tile_id: int,
    logger: logging.Logger,
    callbacks: MockCallableGroup,
    antenna_uri: list[str],
    station_self_check_manager: SpsStationSelfCheckManager,
    num_tiles_to_add: int,
) -> SpsStationComponentManager:
    """
    Return a station component manager.

    :param test_context: a Tango test context running the required
        mock subservient devices
    :param subrack_id: ID of the subservient subrack Tango device
    :param tile_id: ID of the subservient subrack Tango device
    :param logger: a logger to be used by the commonent manager
    :param callbacks: callback group
    :param antenna_uri: Location of antenna configuration file.
    :param station_self_check_manager: SpsStationSelfCheckManager with basic tests.
    :param num_tiles_to_add: Number of mock tiles to add.

    :return: a station component manager.
    """
    sps_station_component_manager = SpsStationComponentManager(
        1,
        [get_subrack_name(subrack_id), get_subrack_name(subrack_id + 1)],
        [get_tile_name(tile_id + i) for i in range(0, num_tiles_to_add)],
        get_lmc_daq_name(),
        get_bandpass_daq_name(),
        ipaddress.IPv4Interface("10.0.0.152/16"),  # sdn_first_interface
        None,  # sdn_gateway
        None,  # csp_ingest_ip
        None,  # channeliser_rounding
        4,  # csp_rounding
        antenna_uri,
        True,  # whether or not to start bandpasses in initialise
        5,  # Bandpass integration time
        logger,
        callbacks["communication_status"],
        callbacks["component_state"],
        callbacks["tile_health"],
        callbacks["subrack_health"],
    )
    # Patching through our self check manager basic tests.
    sps_station_component_manager.self_check_manager = station_self_check_manager
    return sps_station_component_manager


@pytest.fixture(name="generic_nested_dict")
def generic_nested_dict_fixture() -> dict:
    """
    Return fixture for generic nested dict.

    :returns: generic nested dict.
    """
    return {
        "key1": {"key2": {"key3": [1, 2, 3, 4, 5]}},
        "key4": {"key5": "some string", "key6": ["string1", "string2"]},
        "key3": [6, 7, 8, 9, 10],
    }


@pytest.mark.forked
def test_communication(
    station_component_manager: SpsStationComponentManager,
    callbacks: MockCallableGroup,
) -> None:
    """
    Test communication between the tile component manager and its tile.

    :param station_component_manager: the SPS station component manager
        under test
    :param callbacks: dictionary of driver callbacks.
    """
    assert station_component_manager.communication_state == CommunicationStatus.DISABLED

    # takes the component out of DISABLED. Connects with subrack (NOT with TPM)
    station_component_manager.start_communicating()
    callbacks["communication_status"].assert_call(CommunicationStatus.NOT_ESTABLISHED)
    callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)

    callbacks["communication_status"].assert_not_called()

    station_component_manager.stop_communicating()

    callbacks["communication_status"].assert_call(CommunicationStatus.NOT_ESTABLISHED)
    callbacks["communication_status"].assert_call(CommunicationStatus.DISABLED)

    callbacks["communication_status"].assert_not_called()


def test_trigger_adc_equalisation(
    station_component_manager: SpsStationComponentManager,
    callbacks: MockCallableGroup,
) -> None:
    """
    Test the adc triggering equalisation.

    :param station_component_manager: the SPS station component manager
        under test
    :param callbacks: dictionary of driver callbacks.
    """
    assert station_component_manager.communication_state == CommunicationStatus.DISABLED

    # takes the component out of DISABLED. Connects with subrack (NOT with TPM)
    station_component_manager.start_communicating()
    callbacks["communication_status"].assert_call(CommunicationStatus.NOT_ESTABLISHED)
    callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)

    expected_adc = 16.0
    expected_preadu = 8.0

    for proxy in station_component_manager._tile_proxies.values():
        proxy._proxy.adcPower = [expected_adc] * 32  # type: ignore
        proxy._proxy.preaduLevels = [expected_preadu] * 32  # type: ignore

    # Assertion fails, the preadu levels may be empty or containing something
    # in a non deterministic way
    # assert station_component_manager.preadu_levels == []

    station_component_manager._trigger_adc_equalisation()

    if station_component_manager._desired_preadu_levels is not None:
        for value in station_component_manager._desired_preadu_levels:
            assert value < expected_preadu + 1
            assert value > expected_preadu - 1


def test_load_pointing_delays(
    station_component_manager: SpsStationComponentManager,
    mock_tile_proxy: MccsDeviceProxy,
    tile_id: int,
    callbacks: MockCallableGroup,
) -> None:
    """
    Test mapping in load pointing delays.

    :param station_component_manager: the SPS station component manager
        under test
    :param mock_tile_proxy: mock tile which the component manager has been given.
    :param tile_id: id of the tile which the component manager has been given.
    :param callbacks: dictionary of driver callbacks.
    """
    assert station_component_manager.communication_state == CommunicationStatus.DISABLED

    # takes the component out of DISABLED. Connects with subrack (NOT with TPM)
    station_component_manager.start_communicating()
    callbacks["communication_status"].assert_call(CommunicationStatus.NOT_ESTABLISHED)
    callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)

    # First we need an example mapping for our antennas, we only have 1 tile in tests,
    # but lets pretend we have a whole station
    channels = list(range(16))

    # Let's make sure we've got a random assignment of antennas to channels
    random.shuffle(channels)
    antenna_no = 1
    for tpm in range(16):
        for channel in channels:
            station_component_manager._antenna_mapping[antenna_no] = {
                "tpm": tpm + 1,  # tpm is 1 based
                "tpm_y_channel": channel * 2,
                "tpm_x_channel": channel * 2 + 1,
                "delay": 1,
            }
            antenna_no += 1

    # We have a mapping, lets give an argument, this arg
    # is un-realistic but useful for testing
    antenna_order_delays = [float(x) for x in range(513)]

    station_component_manager.load_pointing_delays(copy.deepcopy(antenna_order_delays))

    # The zero-th element should be the zero-th element of the original input
    expected_tile_arg = [antenna_order_delays[0]] + [0.0] * 32

    # The rest of the args should be pairs of (delay, delay_rate) for each channel
    for channel in range(16):
        for (
            antenna_no,
            antenna_config,
        ) in station_component_manager._antenna_mapping.items():
            tile_no = antenna_config["tpm"]
            y_channel = antenna_config["tpm_y_channel"]
            if tile_no == tile_id and int(y_channel / 2) == channel:
                delay, delay_rate = (
                    antenna_order_delays[antenna_no * 2 - 1],
                    antenna_order_delays[antenna_no * 2],
                )
        expected_tile_arg[2 * channel + 1] = delay
        expected_tile_arg[2 * channel + 2] = delay_rate

    mock_tile_proxy.LoadPointingDelays.assert_next_call(expected_tile_arg)


def test_port_to_antenna_order(
    station_component_manager: SpsStationComponentManager,
    callbacks: MockCallableGroup,
) -> None:
    """
    Test that `port_to_antenna_order` properly re-orders data.

    :param station_component_manager: the SPS station component manager
        under test
    :param callbacks: dictionary of driver callbacks.
    """
    station_component_manager.start_communicating()
    callbacks["communication_status"].assert_call(CommunicationStatus.NOT_ESTABLISHED)
    callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)
    assert station_component_manager._antenna_mapping != {}

    tpm_x_mapping = np.zeros((16, 16))
    for antenna, antenna_info in station_component_manager._antenna_mapping.items():
        tpm = int(antenna_info["tpm"]) - 1
        x_port = antenna_info["tpm_x_channel"]
        # Create a simple dataset where map[tpm][port] = antenna_number
        # so that it's obvious if we've re-ordered it correctly or not.
        tpm_x_mapping[tpm][x_port // 2] = antenna

    reshaped_x_tpm_map = tpm_x_mapping.reshape((256, 1))

    antenna_ordered_map = station_component_manager._port_to_antenna_order(
        station_component_manager._antenna_mapping, reshaped_x_tpm_map
    )
    for i, antenna in enumerate(antenna_ordered_map, 1):  # Antenna number is 1-based.
        # Assert we're in antenna order
        assert i == int(antenna)


def test_find_by_key(
    station_component_manager: SpsStationComponentManager, generic_nested_dict: dict
) -> None:
    """
    Check that the _find_by_key method is able to traverse a generic nested dictionary.

    :param station_component_manager: the SPS station component manager
        under test
    :param generic_nested_dict: generic nested dict for use in the test.
    """
    result = station_component_manager._find_by_key(generic_nested_dict, "key3")
    assert result == [6, 7, 8, 9, 10]

    result = station_component_manager._find_by_key(generic_nested_dict, "key5")
    assert result == "some string"

    result = station_component_manager._find_by_key(generic_nested_dict, "key2")
    assert result == {"key3": [1, 2, 3, 4, 5]}

    result = station_component_manager._find_by_key(generic_nested_dict, "key4")
    assert result == {"key5": "some string", "key6": ["string1", "string2"]}


def test_get_static_delays(
    station_component_manager: SpsStationComponentManager,
    tile_id: int,
    callbacks: MockCallableGroup,
) -> None:
    """
    Test getting static delays from dummy TelModel.

    :param station_component_manager: the SPS station component manager
        under test
    :param tile_id: id of the tile which the component manager has been given.
    :param callbacks: dictionary of driver callbacks.
    """
    assert station_component_manager.communication_state == CommunicationStatus.DISABLED

    # takes the component out of DISABLED. Connects with subrack (NOT with TPM)
    station_component_manager.start_communicating()
    callbacks["communication_status"].assert_call(CommunicationStatus.NOT_ESTABLISHED)
    callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)

    # First we need an example mapping for our antennas, we have 4 tiles in tests,
    # but lets pretend we have a whole station
    channels = list(range(16))

    # Let's make sure we've got a random assignment of antennas to channels
    random.shuffle(channels)

    antenna_no = 1
    for tpm in range(1, 16 + 1):
        for channel in channels:
            station_component_manager._antenna_mapping[antenna_no] = {
                "tpm": tpm,
                "tpm_y_channel": channel * 2,
                "tpm_x_channel": channel * 2 + 1,
                "delay": antenna_no // 2,
            }
            antenna_no += 1

    static_delays = station_component_manager._update_static_delays()
    expected_static_delays = [
        0 for _ in range(station_component_manager._number_of_tiles * 2 * len(channels))
    ]
    for antenna, antenna_config in station_component_manager._antenna_mapping.items():
        if int(antenna_config["tpm"]) in [
            tile_id + i for i in range(0, station_component_manager._number_of_tiles)
        ]:
            expected_static_delays[
                ((antenna_config["tpm"] - 1) * 2 * len(channels))
                + antenna_config["tpm_y_channel"]
            ] = antenna_config["delay"]
            expected_static_delays[
                ((antenna_config["tpm"] - 1) * 2 * len(channels))
                + antenna_config["tpm_x_channel"]
            ] = antenna_config["delay"]
    assert static_delays == expected_static_delays


def test_self_check(
    station_component_manager: SpsStationComponentManager,
    callbacks: MockCallableGroup,
) -> None:
    """
    Test running a self_check with example tests.

    :param station_component_manager: the SPS station component manager
        under test
    :param callbacks: dictionary of driver callbacks.
    """
    assert station_component_manager.communication_state == CommunicationStatus.DISABLED

    # takes the component out of DISABLED. Connects with subrack (NOT with TPM)
    station_component_manager.start_communicating()
    callbacks["communication_status"].assert_call(CommunicationStatus.NOT_ESTABLISHED)
    callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)

    station_component_manager.self_check(task_callback=callbacks["task"])

    callbacks["task"].assert_call(status=TaskStatus.QUEUED)
    callbacks["task"].assert_call(status=TaskStatus.IN_PROGRESS)

    # This should fail as we have set up one FAIL test and one ERROR test.
    callbacks["task"].assert_call(
        status=TaskStatus.FAILED,
        result=(ResultCode.FAILED, "Not all tests passed or skipped, check report."),
    )


@pytest.mark.parametrize(
    ("test_name"),
    [
        pytest.param("PassTest"),
        pytest.param("FailTest"),
        pytest.param("ErrorTest"),
        pytest.param("BadRequirementsTest"),
    ],
)
def test_run_test(
    station_component_manager: SpsStationComponentManager,
    callbacks: MockCallableGroup,
    test_name: str,
) -> None:
    """
    Test running a run_test with example tests.

    :param station_component_manager: the SPS station component manager
        under test
    :param callbacks: dictionary of driver callbacks.
    :param test_name: name of test to run.
    """
    assert station_component_manager.communication_state == CommunicationStatus.DISABLED

    # takes the component out of DISABLED. Connects with subrack (NOT with TPM)
    station_component_manager.start_communicating()
    callbacks["communication_status"].assert_call(CommunicationStatus.NOT_ESTABLISHED)
    callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)

    station_component_manager.run_test(
        task_callback=callbacks["task"], test_name=test_name, count=1
    )

    callbacks["task"].assert_call(status=TaskStatus.QUEUED)
    callbacks["task"].assert_call(status=TaskStatus.IN_PROGRESS)

    if test_name == "PassTest":
        callbacks["task"].assert_call(
            status=TaskStatus.COMPLETED,
            result=(ResultCode.OK, "Tests completed OK."),
        )
        return

    if test_name == "BadRequirementsTest":
        callbacks["task"].assert_call(
            status=TaskStatus.REJECTED,
            result=(ResultCode.REJECTED, "Tests requirements not met, check logs."),
        )
        return
    callbacks["task"].assert_call(
        status=TaskStatus.FAILED,
        result=(
            ResultCode.FAILED,
            "Not all tests passed, check report.",
        ),
    )


@pytest.mark.parametrize(
    [
        "command",
        "expected_station_result",
        "expected_tile_result",
    ],
    [
        pytest.param(
            "FailedCommand",
            ResultCode.FAILED,
            ResultCode.FAILED,
        ),
        pytest.param(
            "RejectedCommand",
            ResultCode.FAILED,
            ResultCode.REJECTED,
        ),
        pytest.param(
            "GoodCommand",
            ResultCode.OK,
            ResultCode.OK,
        ),
    ],
)
def test_async_commands(
    station_component_manager: SpsStationComponentManager,
    callbacks: MockCallableGroup,
    command: str,
    expected_station_result: ResultCode,
    expected_tile_result: ResultCode,
) -> None:
    """
    Test the method to run commands async.

    :param station_component_manager: the SPS station component manager
        under test
    :param callbacks: dictionary of driver callbacks.
    :param command: command to call on the tiles.
    :param expected_station_result: expected result from station.
    :param expected_tile_result: expected result from tiles.
    """
    # Before we establish connection, we shouldn't attempt these on any tiles.
    result, message = station_component_manager._execute_async_on_tiles(command)

    assert result[0] == ResultCode.REJECTED
    assert message[0] is not None
    assert f"{command} wouldn't be called on any MccsTiles" in message[0]

    assert station_component_manager.communication_state == CommunicationStatus.DISABLED

    # takes the component out of DISABLED. Connects with subrack (NOT with TPM)
    station_component_manager.start_communicating()
    callbacks["communication_status"].assert_call(CommunicationStatus.NOT_ESTABLISHED)
    callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)

    # Now we've established connection, we should be attempting.
    result, message = station_component_manager._execute_async_on_tiles(command)

    assert result[0] == expected_station_result
    assert message[0] is not None
    assert expected_tile_result.name in message[0]


def test_send_data_samples(
    station_component_manager: SpsStationComponentManager,
    callbacks: MockCallableGroup,
    mock_tile_proxy: MccsDeviceProxy,
) -> None:
    """
    Test the method to run commands async.

    :param station_component_manager: the SPS station component manager
        under test
    :param callbacks: dictionary of driver callbacks.
    :param mock_tile_proxy: mock tile which the component manager has been given.
    """
    assert station_component_manager.communication_state == CommunicationStatus.DISABLED

    # takes the component out of DISABLED. Connects with subrack (NOT with TPM)
    station_component_manager.start_communicating()
    callbacks["communication_status"].assert_call(CommunicationStatus.NOT_ESTABLISHED)
    callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)

    mock_tile_proxy.tileProgrammingState = "Synchronised"
    mock_tile_proxy.pendingDataRequests = True
    [result], [msg] = station_component_manager.send_data_samples(
        json.dumps({"data_type": "raw"})
    )
    assert result == ResultCode.REJECTED

    [result], [msg] = station_component_manager.send_data_samples(
        json.dumps({"data_type": "raw"}), force=True
    )
    assert result == ResultCode.OK

    mock_tile_proxy.pendingDataRequests = False
    [result], [msg] = station_component_manager.send_data_samples(
        json.dumps({"data_type": "raw"})
    )
    assert result == ResultCode.OK


def test_power_state_transitions(
    station_component_manager: SpsStationComponentManager,
    callbacks: MockCallableGroup,
) -> None:
    """
    Test SpsStation's state transitions.

    :param station_component_manager: the SPS station component manager
        under test
    :param callbacks: dictionary of driver callbacks.
    """
    assert station_component_manager.communication_state == CommunicationStatus.DISABLED

    # takes the component out of DISABLED.
    station_component_manager.start_communicating()
    callbacks["communication_status"].assert_call(CommunicationStatus.NOT_ESTABLISHED)
    callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)

    for subrack in station_component_manager._subrack_proxies.values():
        assert subrack._proxy is not None
        assert subrack._proxy.state() == tango.DevState.ON
        callbacks["component_state"].assert_call(
            device_name=subrack._name,
            health=HealthState.OK,
            lookahead=20,
        )

    for tile in station_component_manager._tile_proxies.values():
        assert tile._proxy is not None
        assert tile._proxy.state() == tango.DevState.ON
        callbacks["component_state"].assert_call(
            device_name=tile._name,
            health=HealthState.OK,
            lookahead=20,
        )
        # Need to wait for this event to come through before we turn a tile OFF.
        callbacks["component_state"].assert_call(
            device_name=tile._name,
            power=PowerState.ON,
            lookahead=20,
        )
    callbacks["component_state"].assert_call(power=PowerState.ON, lookahead=10)
    assert station_component_manager._component_state["power"] == PowerState.ON

    tile_names = list(station_component_manager._tile_proxies.keys())
    subrack_names = list(station_component_manager._subrack_proxies.keys())
    # Start with all ON.
    # Any Tiles ON, Station should be ON
    station_component_manager._tile_state_changed(tile_names[0], power=PowerState.OFF)
    assert station_component_manager._component_state["power"] == PowerState.ON
    station_component_manager._tile_state_changed(tile_names[1], power=PowerState.OFF)
    assert station_component_manager._component_state["power"] == PowerState.ON
    station_component_manager._tile_state_changed(tile_names[2], power=PowerState.OFF)
    assert station_component_manager._component_state["power"] == PowerState.ON

    # Any Subrack ON, all Tiles OFF/NO_SUPP, Station should be STANDBY
    station_component_manager._tile_state_changed(
        tile_names[3], power=PowerState.NO_SUPPLY
    )
    assert station_component_manager._component_state["power"] == PowerState.STANDBY
    station_component_manager._subrack_state_changed(
        subrack_names[0], power=PowerState.OFF
    )
    assert station_component_manager._component_state["power"] == PowerState.STANDBY
    # All Subracks OFF, all Tiles OFF, Station should be OFF
    station_component_manager._subrack_state_changed(
        subrack_names[1], power=PowerState.NO_SUPPLY
    )
    assert station_component_manager._component_state["power"] == PowerState.OFF
    for subrack_name in subrack_names:
        station_component_manager._subrack_state_changed(
            subrack_name, power=PowerState.ON
        )
    # Subracks now ON, Station should be STANDBY again.
    assert station_component_manager._component_state["power"] == PowerState.STANDBY
    # All Tiles NO_SUPPLY, Subrack ON, Station should be STANDBY
    for tile_name in tile_names:
        station_component_manager._tile_state_changed(
            tile_name, power=PowerState.NO_SUPPLY
        )
    assert station_component_manager._component_state["power"] == PowerState.STANDBY
    # Turn a random Tile back ON, Station should be ON
    tile_num = random.randint(0, 3)
    station_component_manager._tile_state_changed(
        tile_names[tile_num], power=PowerState.ON
    )
    assert station_component_manager._component_state["power"] == PowerState.ON
    # Set all subracks and tiles to NO_SUPP, Station should be NO_SUPP
    for subrack_name in subrack_names:
        station_component_manager._subrack_state_changed(
            subrack_name, power=PowerState.NO_SUPPLY
        )
    for tile_name in tile_names:
        station_component_manager._tile_state_changed(
            tile_name, power=PowerState.NO_SUPPLY
        )
    assert station_component_manager._component_state["power"] == PowerState.NO_SUPPLY

    # Any subrack UNKNOWN AND no subrack ON, Station = UNKNOWN
    station_component_manager._subrack_state_changed(
        subrack_names[0], power=PowerState.UNKNOWN
    )
    assert station_component_manager._component_state["power"] == PowerState.UNKNOWN
    # Any tile UNKNOWN AND no tile ON, Station = UNKNOWN
    station_component_manager._subrack_state_changed(
        subrack_names[0], power=PowerState.NO_SUPPLY
    )
    station_component_manager._tile_state_changed(
        tile_names[0], power=PowerState.UNKNOWN
    )
    assert station_component_manager._component_state["power"] == PowerState.UNKNOWN


def test_pps_delay_spread(
    station_component_manager: SpsStationComponentManager,
    callbacks: MockCallableGroup,
    mock_tile_proxy: MccsDeviceProxy,
    num_tiles_to_add: int,
) -> None:
    """
    Test the method to run commands async.

    :param station_component_manager: the SPS station component manager
        under test
    :param callbacks: dictionary of driver callbacks.
    :param mock_tile_proxy: mock tile which the component manager has been given.
    :param num_tiles_to_add: Number of tiles in the test.
    """
    assert station_component_manager.communication_state == CommunicationStatus.DISABLED
    assert station_component_manager._number_of_tiles >= 4  # Test assumes 4 tiles.
    # takes the component out of DISABLED.
    station_component_manager.start_communicating()
    callbacks["communication_status"].assert_call(CommunicationStatus.NOT_ESTABLISHED)
    callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)

    assert station_component_manager._pps_delays == [0] * 16
    assert station_component_manager._pps_delay_spread == 0

    # Set 1 Tile's ppsDelay to 4 for a delta of 4.
    station_component_manager._on_tile_attribute_change(
        logical_tile_id=1,
        attribute_name="ppsDelay",
        attribute_value=4,
        attribute_quality=tango.AttrQuality.ATTR_VALID,
    )
    assert station_component_manager._pps_delay_spread == 4

    # Set all tiles to a delay of 4 for a delta of 0.
    for tile_id in range(0, num_tiles_to_add):
        station_component_manager._on_tile_attribute_change(
            logical_tile_id=tile_id,
            attribute_name="ppsDelay",
            attribute_value=4,
            attribute_quality=tango.AttrQuality.ATTR_VALID,
        )
    assert station_component_manager._pps_delay_spread == 0

    # Set 1 Tile to ppsDelay of 16 for a delta of 12.
    station_component_manager._on_tile_attribute_change(
        logical_tile_id=3,
        attribute_name="ppsDelay",
        attribute_value=16,
        attribute_quality=tango.AttrQuality.ATTR_VALID,
    )
    assert station_component_manager._pps_delay_spread == 12
