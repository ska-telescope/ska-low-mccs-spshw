#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests of the tile component manage."""
from __future__ import annotations

import copy
import logging
import random
import unittest.mock
from typing import Iterator

import numpy as np
import pytest
from ska_control_model import CommunicationStatus
from ska_low_mccs_common.device_proxy import MccsDeviceProxy
from ska_tango_testing.mock import MockCallableGroup

from ska_low_mccs_spshw.station import SpsStationComponentManager
from tests.harness import SpsTangoTestHarness, get_subrack_name, get_tile_name


@pytest.fixture(name="test_context")
def test_context_fixture(
    subrack_id: int,
    mock_subrack_device_proxy: unittest.mock.Mock,
    tile_id: int,
    mock_tile_device_proxy: unittest.mock.Mock,
    daq_id: int,
) -> Iterator[None]:
    """
    Yield into a context in which Tango is running, with mock devices.

    The station component manager acts as a Tango client to the subrack
    and tile Tango device. In these unit tests, the subrack and tile
    Tango devices are mocked out, but since the station component
    manager uses tango to talk to them, we still need some semblance of
    a tango subsystem in place. Here, we assume that the station has
    only one subrack and one tile.

    :param subrack_id: ID of the subrack Tango device to be mocked
    :param mock_subrack_device_proxy: a mock subrack device proxy
        that has been configured with the required subrack behaviours.
    :param tile_id: ID of the tile Tango device to be mocked
    :param mock_tile_device_proxy: a mock tile device proxy
        that has been configured with the required subrack behaviours.
    :param daq_id: the ID number of the DAQ receiver.

    :yields: into a context in which Tango is running, with a mock
        subrack device.
    """
    harness = SpsTangoTestHarness()
    harness.add_mock_subrack_device(subrack_id, mock_subrack_device_proxy)
    harness.add_mock_tile_device(tile_id, mock_tile_device_proxy)
    harness.set_daq_instance()
    harness.set_daq_device(daq_id=daq_id, address=None)
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
        timeout=5.0,
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
    daq_trl: str,
    logger: logging.Logger,
    callbacks: MockCallableGroup,
    antenna_uri: list[str],
) -> SpsStationComponentManager:
    """
    Return a station component manager.

    :param test_context: a Tango test context running the required
        mock subservient devices
    :param subrack_id: ID of the subservient subrack Tango device
    :param tile_id: ID of the subservient subrack Tango device
    :param daq_trl: Tango Resource Locator for this Station's DAQ instance.
    :param logger: a logger to be used by the commonent manager
    :param callbacks: callback group
    :param antenna_uri: Location of antenna configuration file.

    :return: a station component manager.
    """
    return SpsStationComponentManager(
        1,
        [get_subrack_name(subrack_id)],
        [get_tile_name(tile_id)],
        daq_trl,
        "10.0.0.0",
        antenna_uri,
        logger,
        1,
        callbacks["communication_status"],
        callbacks["component_state"],
        callbacks["tile_health"],
        callbacks["subrack_health"],
    )


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

    assert station_component_manager.preadu_levels == []

    station_component_manager._trigger_adc_equalisation()

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
    for tpm in range(1, 16 + 1):
        for channel in channels:
            station_component_manager._antenna_mapping[antenna_no] = {
                "tpm": tpm,
                "tpm_y_channel": channel * 2,
                "tpm_x_channel": channel * 2 + 1,
                "delays": 1,
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
    station_component_manager: SpsStationComponentManager, antenna_uri: list[str]
) -> None:
    """
    Test that `port_to_antenna_order` properly re-orders data.

    :param station_component_manager: the SPS station component manager
        under test
    :param antenna_uri: Location of antenna configuration file.
    """
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
    for i, antenna in enumerate(antenna_ordered_map):
        # Assert we're in antenna order (and convert from 0 to 1 based numbering)
        assert i + 1 == int(antenna)


def test_find_by_key(
    station_component_manager: SpsStationComponentManager, generic_nested_dict: dict
) -> None:
    """
    Check that the _find_by_key method is able to traverse a generic nested dictionary.

    :param station_component_manager: the SPS station component manager
        under test
    :param generic_nested_dict: generic nested dict for use in the test.
    """
    results = []
    for value in station_component_manager._find_by_key(generic_nested_dict, "key3"):
        results.append(value)
    assert results[0] == [1, 2, 3, 4, 5]
    assert results[1] == [6, 7, 8, 9, 10]

    assert (
        next(station_component_manager._find_by_key(generic_nested_dict, "key5"))
        == "some string"
    )

    assert next(
        station_component_manager._find_by_key(generic_nested_dict, "key2")
    ) == {"key3": [1, 2, 3, 4, 5]}

    assert next(
        station_component_manager._find_by_key(generic_nested_dict, "key4")
    ) == {"key5": "some string", "key6": ["string1", "string2"]}


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

    # First we need an example mapping for our antennas, we only have 1 tile in tests,
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
                "delays": antenna_no // 2,
            }
            antenna_no += 1

    static_delays = station_component_manager._update_static_delays()
    expected_static_delays = [0 for _ in range(32)]
    for antenna, antenna_config in station_component_manager._antenna_mapping.items():
        if int(antenna_config["tpm"]) == tile_id:
            expected_static_delays[antenna_config["tpm_y_channel"]] = antenna_config[
                "delays"
            ]
            expected_static_delays[antenna_config["tpm_x_channel"]] = antenna_config[
                "delays"
            ]
    assert static_delays == expected_static_delays
