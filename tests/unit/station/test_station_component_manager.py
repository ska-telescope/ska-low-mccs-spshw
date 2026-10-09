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
import threading
import time
import unittest.mock
from types import SimpleNamespace
from typing import Any, Final, Generator, Iterator, Optional

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
from ska_low_mccs_spshw.station import station_component_manager as station_cm
from ska_low_mccs_spshw.station.tests import BaseDaqTest
from ska_low_mccs_spshw.station.tests.base_tpm_test import TestResult
from tests.harness import SpsTangoTestHarness, get_subrack_name, get_tile_name
from tests.test_tools import FakeGroup as _FakeGroup
from tests.test_tools import FakeGroupReply as _FakeGroupReply

# pylint: disable=too-many-lines

ADC_CHANNELS: Final[int] = 32  # Number of ADC channels per tile, used in tests.


def _mock_group(name: str, tile_fqdns: list[str]) -> unittest.mock.Mock:
    """
    Build a tile group test double, for injection via ``tile_group=``.

    ``SpsStationComponentManager`` would otherwise build a real
    ``tango.Group``, which makes genuine Tango connections that don't
    exist in this mock-based harness. The mock returned here is spec'd
    against the real ``tango.Group`` (so a typo'd or removed method is
    caught) and wraps a ``_FakeGroup``, which fans calls out to the same
    registered mock tile devices the rest of the test suite uses.
    Individual tests can still override one method for one case, e.g.
    ``tile_group.write_attribute.side_effect = ...``.

    An injected group is trusted by ``SpsStationComponentManager`` to
    already contain every tile, so -- unlike when it builds a group
    itself -- it will not add these devices for us; we do it here
    instead.

    :param name: name of the group.
    :param tile_fqdns: FQDNs of the tiles to add to the group.

    :return: a mock tile group.
    """
    fake_group = _FakeGroup(name)
    for tile_fqdn in tile_fqdns:
        fake_group.add(tile_fqdn)
    return unittest.mock.Mock(spec=tango.Group, wraps=fake_group)


# pylint: disable = too-many-arguments
@pytest.fixture(name="test_context")
def fixture_test_context(
    subrack_id: int,
    mock_subrack_device_proxy: unittest.mock.Mock,
    tile_id: int,
    mock_tile_device_proxies: list[unittest.mock.Mock],
    daq_id: int,
    num_tiles: int,
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
    :param mock_tile_device_proxies: a mock tile device proxy
        that has been configured with the required subrack behaviours.
    :param daq_id: the ID number of the DAQ receiver.
    :param num_tiles: Number of tiles to add.

    :yields: into a context in which Tango is running, with a mock
        subrack device.
    """
    harness = SpsTangoTestHarness()
    harness.add_mock_subrack_device(subrack_id, mock_subrack_device_proxy)
    harness.add_mock_subrack_device(subrack_id + 1, mock_subrack_device_proxy)
    # Add 4 tiles.
    for i in range(num_tiles):
        harness.add_mock_tile_device(
            tile_id + i,
            mock_tile_device_proxies[i],
        )
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
        "wren_health",
        timeout=15.0,
    )


@pytest.fixture(name="station_label")
def station_label_fixture() -> str:
    """
    Station label for use in testing.

    :returns: a station label for use in testing.
    """
    return "ci-1"


@pytest.fixture(name="mock_tiles")
def mock_tiles_fixture(
    tile_id: int,
    num_tiles: int,
    station_label: str,
    logger: logging.Logger,
) -> list[MccsDeviceProxy]:
    """
    Return a proxy for each mock tile in the harness.

    :param tile_id: base tile ID used by the harness.
    :param num_tiles: number of mock tiles in the harness.
    :param station_label: station label used to build tile FQDNs.
    :param logger: logger for the proxy.

    :returns: list of proxies, one per mock tile.
    """
    return [
        MccsDeviceProxy(get_tile_name(tile_id + i, station_label), logger)
        for i in range(num_tiles)
    ]


# pylint: disable=too-many-arguments
@pytest.fixture(name="station_component_manager")
def station_component_manager_fixture(
    test_context: None,
    subrack_id: int,
    station_label: str,
    tile_id: int,
    logger: logging.Logger,
    callbacks: MockCallableGroup,
    antenna_uri: list[str],
    station_self_check_manager: SpsStationSelfCheckManager,
    num_tiles: int,
) -> SpsStationComponentManager:
    """
    Return a station component manager.

    :param test_context: a Tango test context running the required
        mock subservient devices
    :param subrack_id: ID of the subservient subrack Tango device
    :param station_label: name of the station.
    :param tile_id: ID of the subservient subrack Tango device
    :param logger: a logger to be used by the commonent manager
    :param callbacks: callback group
    :param antenna_uri: Location of antenna configuration file.
    :param station_self_check_manager: SpsStationSelfCheckManager with basic tests.
    :param num_tiles: Number of mock tiles to add.

    :return: a station component manager.
    """
    tile_fqdns = [get_tile_name(tile_id + i) for i in range(0, num_tiles)]
    sps_station_component_manager = SpsStationComponentManager(
        1,  # station_id
        [get_subrack_name(subrack_id), get_subrack_name(subrack_id + 1)],
        tile_fqdns,
        "",  # lmc_daq_trl
        "",  # bandpass_daq_trl
        "",  # wren_trl
        ipaddress.IPv4Interface("10.0.0.152/16"),  # sdn_first_interface
        None,  # sdn_gateway
        None,  # csp_ingest_ip
        None,  # channeliser_rounding
        4,  # csp_rounding
        antenna_uri,
        True,  # whether or not to start bandpasses in initialise
        5,  # Bandpass integration time
        True,  # wren_health_check_fail_on_timeout
        120,  # wren_health_check_timeout
        logger,
        callbacks["communication_status"],
        callbacks["component_state"],
        callbacks["tile_health"],
        callbacks["subrack_health"],
        callbacks["wren_health"],
        tile_group=_mock_group("station-1-tiles", tile_fqdns),
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


@pytest.mark.parametrize(
    ("result", "target_adc", "bias"),
    [
        (7.5, 17, 0),
        # testing target adc
        (9.25, 14, 0),
        (6.0, 20, 0),
        # testing bias
        (8.5, 17, 1),
        (6.5, 17, -1),
        # testing limits
        (31.75, 0, -32),
        (0, 1600, 32),
        (0, 40, 0),
    ],
)
def test_trigger_adc_equalisation(
    communicating_station_component_manager: SpsStationComponentManager,
    result: float,
    target_adc: float,
    bias: float,
) -> None:
    """
    Test the adc triggering equalisation.

    :param communicating_station_component_manager: the SPS station component
        manager under test
    :param result: expected result after equalisation
    :param target_adc: the expected average power received by antennas in ADU units.
    :param bias: user specified bias.
    """
    expected_adc = 16.0
    expected_preadu = 8.0

    for proxy in communicating_station_component_manager._tile_proxies.values():
        proxy._proxy.adcPower = [expected_adc] * 32  # type: ignore
        proxy._proxy.preaduLevels = [expected_preadu] * 32  # type: ignore

    # Assertion fails, the preadu levels may be empty or containing something
    # in a non deterministic way
    # assert communicating_station_component_manager.preadu_levels == []

    communicating_station_component_manager.trigger_adc_equalisation(target_adc, bias)

    assert communicating_station_component_manager._desired_preadu_levels is not None
    for value in communicating_station_component_manager._desired_preadu_levels:
        assert value == result


def test_load_pointing_delays(
    communicating_station_component_manager: SpsStationComponentManager,
    mock_tiles: list[MccsDeviceProxy],
) -> None:
    """
    Test mapping in load pointing delays.

    :param communicating_station_component_manager: the SPS station component
        manager under test
    :param mock_tiles: mock tile proxies, one per tile in the harness.
    """
    # First we need an example mapping for our antennas, we only have 1 tile in tests,
    # but lets pretend we have a whole station
    channels = list(range(16))

    # Let's make sure we've got a random assignment of antennas to channels
    random.shuffle(channels)
    antenna_no = 1
    for tpm in range(16):
        for channel in channels:
            communicating_station_component_manager._antenna_mapping[antenna_no] = {
                "tpm": tpm,  # tpm is 0 based (logical ID)
                "tpm_y_channel": channel * 2,
                "tpm_x_channel": channel * 2 + 1,
                "delay": 1,
            }
            antenna_no += 1

    # We have a mapping, lets give an argument, this arg
    # is un-realistic but useful for testing
    antenna_order_delays = [float(x) for x in range(513)]

    communicating_station_component_manager.load_pointing_delays(
        copy.deepcopy(antenna_order_delays)
    )

    # The zero-th element should be the zero-th element of the original input
    expected_tile_arg = [antenna_order_delays[0]] + [0.0] * 32

    # The rest of the args should be pairs of (delay, delay_rate) for each channel
    for channel in range(16):
        for (
            antenna_no,
            antenna_config,
        ) in communicating_station_component_manager._antenna_mapping.items():
            tile_no = antenna_config["tpm"]
            y_channel = antenna_config["tpm_y_channel"]
            if tile_no == 0 and int(y_channel / 2) == channel:  # First tile
                delay, delay_rate = (
                    antenna_order_delays[antenna_no * 2 - 1],
                    antenna_order_delays[antenna_no * 2],
                )
        expected_tile_arg[2 * channel + 1] = delay
        expected_tile_arg[2 * channel + 2] = delay_rate

    mock_tiles[0].LoadPointingDelays.assert_next_call(pytest.approx(expected_tile_arg))


def test_preadu_levels_fanout_to_correct_tile(
    station_component_manager: SpsStationComponentManager,
    mock_tiles: list[MccsDeviceProxy],
    num_tiles: int,
) -> None:
    """
    Test that preadu_levels sends each tile's slice to the correct tile.

    preadu_levels slices its input by iteration order of
    ``self._tile_proxies``, which matches the registration order of
    ``mock_tiles``.

    :param station_component_manager: the SPS station component manager
        under test
    :param mock_tiles: mock tile proxies, one per tile in the harness.
    :param num_tiles: number of tiles in the test.
    """
    expected_levels_by_index = {i: [100.0 + i] * ADC_CHANNELS for i in range(num_tiles)}
    station_component_manager.preadu_levels = [
        level for i in range(num_tiles) for level in expected_levels_by_index[i]
    ]

    for i in range(num_tiles):
        assert list(mock_tiles[i].preaduLevels) == expected_levels_by_index[i]


@pytest.fixture(name="communicating_station_component_manager")
def communicating_station_component_manager_fixture(
    station_component_manager: SpsStationComponentManager, callbacks: MockCallableGroup
) -> Generator[SpsStationComponentManager, None, None]:
    """
    Yield a component manager with connections to mocks established.

    :param station_component_manager: the SPS station component manager
        under test
    :param callbacks: dictionary of driver callbacks.

    :yields: the component manager
    """
    station_component_manager.start_communicating()
    callbacks["communication_status"].assert_call(CommunicationStatus.NOT_ESTABLISHED)
    callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)

    yield station_component_manager


def test_static_delays_fanout_to_correct_tile(
    communicating_station_component_manager: SpsStationComponentManager,
    mock_tiles: list[MccsDeviceProxy],
    num_tiles: int,
) -> None:
    """
    Test that static_delays sends each tile's slice to the correct tile.

    Unlike preadu_levels, static_delays slices its input by each tile's own
    ``logicalTileId``, not by registration order. We reassign
    ``logicalTileId`` to a non-identity permutation of the default mapping
    so that the two orderings disagree -- this is what proves the setter is
    actually keying off ``logicalTileId``, rather than coincidentally
    passing because both orderings happen to match by default.

    :param communicating_station_component_manager: the SPS station component manager
        under test
    :param mock_tiles: mock tile proxies, one per tile in the harness.
    :param num_tiles: number of tiles in the test.
    """
    assert num_tiles == 4  # test assumes 4 tiles, to define the permutation below.
    logical_id_by_index = [3, 1, 2, 0]
    for i, logical_id in enumerate(logical_id_by_index):
        mock_tiles[i].logicalTileId = logical_id

    expected_delays_by_logical_id = {
        logical_id: [10.0 + logical_id] * ADC_CHANNELS
        for logical_id in range(num_tiles)
    }
    communicating_station_component_manager.static_delays = [
        delay
        for logical_id in range(num_tiles)
        for delay in expected_delays_by_logical_id[logical_id]
    ]

    for i, logical_id in enumerate(logical_id_by_index):
        assert (
            list(mock_tiles[i].staticTimeDelays)
            == expected_delays_by_logical_id[logical_id]
        )


def test_static_delays_reports_tile_write_failure(
    communicating_station_component_manager: SpsStationComponentManager,
    mock_tiles: list[MccsDeviceProxy],
    num_tiles: int,
) -> None:
    """
    Test that a tile write failure is reported via tango.DevFailed.

    When one tile in the group fails to write staticTimeDelays,
    ``_group_write_attribute`` must raise ``tango.DevFailed`` carrying
    that tile's own failure reason through to the caller -- not a
    generic or empty error -- while the other tiles' writes still go
    through.

    The failure is injected at the tile group itself (rather than by
    patching the mock tile device proxy), since the group is what
    ``_group_write_attribute`` actually talks to.

    :param communicating_station_component_manager: the SPS station component manager
        under test
    :param mock_tiles: mock tile proxies, one per tile in the harness.
    :param num_tiles: number of tiles in the test.
    """
    failing_index = 0
    failure_reason = "SimulatedStaticTimeDelaysFailure"
    expected_delays = [10.0] * ADC_CHANNELS

    tile_group = communicating_station_component_manager._tile_group
    real_write_attribute = tile_group.write_attribute

    def _write_attribute_with_one_failure(
        attr_name: str, value: Any, **kwargs: Any
    ) -> list[Any]:
        replies = real_write_attribute(attr_name, value, **kwargs)
        if attr_name == "staticTimeDelays":
            replies[failing_index] = _FakeGroupReply(
                replies[failing_index].dev_name(),
                attr_name,
                exception=tango.DevFailed(failure_reason),
            )
        return replies

    with (
        unittest.mock.patch.object(
            tile_group,
            "write_attribute",
            side_effect=_write_attribute_with_one_failure,
        ),
        pytest.raises(tango.DevFailed) as exc_info,
    ):
        communicating_station_component_manager.static_delays = (
            expected_delays * num_tiles
        )

    error_stack = exc_info.value.args
    assert len(error_stack) == 1
    assert failure_reason in error_stack[0].reason
    assert error_stack[0].origin == "staticTimeDelays"

    for i in range(num_tiles):
        if i == failing_index:
            continue
        assert list(mock_tiles[i].staticTimeDelays) == expected_delays


def test_global_reference_time_broadcast_to_all_tiles(
    station_component_manager: SpsStationComponentManager,
    mock_tiles: list[MccsDeviceProxy],
    num_tiles: int,
) -> None:
    """
    Test that global_reference_time broadcasts the same value to every tile.

    :param station_component_manager: the SPS station component manager
        under test
    :param mock_tiles: mock tile proxies, one per tile in the harness.
    :param num_tiles: number of tiles in the test.
    """
    reference_time = "2026-08-04T00:00:00.000Z"
    station_component_manager.global_reference_time = reference_time

    for i in range(num_tiles):
        assert mock_tiles[i].globalReferenceTime == reference_time


def test_port_to_antenna_order(
    communicating_station_component_manager: SpsStationComponentManager,
) -> None:
    """
    Test that `port_to_antenna_order` properly re-orders data.

    :param communicating_station_component_manager: the SPS station component
        manager under test
    """
    antenna_mapping = communicating_station_component_manager._antenna_mapping
    assert antenna_mapping != {}

    tpm_x_mapping = np.zeros((16, 16))
    for antenna, antenna_info in antenna_mapping.items():
        tpm = int(antenna_info["tpm"])
        x_port = antenna_info["tpm_x_channel"]
        # Create a simple dataset where map[tpm][port] = antenna_number
        # so that it's obvious if we've re-ordered it correctly or not.
        tpm_x_mapping[tpm][x_port // 2] = antenna

    reshaped_x_tpm_map = tpm_x_mapping.reshape((256, 1))

    antenna_ordered_map = (
        communicating_station_component_manager._port_to_antenna_order(
            antenna_mapping, reshaped_x_tpm_map
        )
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


def test_read_lmc_integrated_mode_returns_40g_when_load_balancer_disabled(
    station_component_manager: SpsStationComponentManager,
) -> None:
    """
    Test reading 40G integrated mode from bandpass DAQ attribute.

    :param station_component_manager: the SPS station component manager under test.
    """
    station_component_manager._bandpass_daq_proxy = SimpleNamespace(
        _proxy=SimpleNamespace(bandpassLoadBalancerEnabled=False)
    )  # type: ignore[assignment]

    assert (
        station_component_manager._read_lmc_integrated_mode_from_bandpass_daq(
            log_context="test"
        )
        == "40G"
    )


def test_read_lmc_integrated_mode_returns_none_when_attribute_missing(
    station_component_manager: SpsStationComponentManager,
) -> None:
    """
    Test fallback when bandpass DAQ does not expose the feature attribute.

    :param station_component_manager: the SPS station component manager under test.
    """
    station_component_manager._bandpass_daq_proxy = SimpleNamespace(
        _proxy=object()  # type: ignore[assignment]
    )

    assert (
        station_component_manager._read_lmc_integrated_mode_from_bandpass_daq(
            log_context="test"
        )
        is None
    )


def test_read_lmc_integrated_mode_retries_proxy_not_ready_then_returns_none(
    station_component_manager: SpsStationComponentManager,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Test retry/fallback path when bandpass DAQ proxy is unavailable.

    :param station_component_manager: the SPS station component manager under test.
    :param monkeypatch: pytest monkeypatch fixture.
    """
    logger = unittest.mock.Mock()
    station_component_manager.logger = logger
    station_component_manager._bandpass_daq_proxy = None

    monkeypatch.setattr(station_cm, "_LMC_INTEGRATED_MODE_RETRY_ATTEMPTS", 3)
    monkeypatch.setattr(station_cm, "_LMC_INTEGRATED_MODE_RETRY_DELAY", 0.0)

    assert (
        station_component_manager._read_lmc_integrated_mode_from_bandpass_daq(
            log_context="test"
        )
        is None
    )

    assert logger.info.call_count == 3
    logger.warning.assert_called_once()


_DAQ_TRL = "low-mccs/daqreceiver/ci-1"


def _fake_daq(ip: str, port: int = 4660) -> SimpleNamespace:
    """
    Return a stand-in for a DAQ proxy, advertising the given destination.

    :param ip: the IP the DAQ advertises.
    :param port: the port the DAQ advertises.

    :return: a stand-in for a DAQ proxy.
    """
    status = json.dumps({"Receiver IP": [ip], "Receiver Ports": [port]})
    return SimpleNamespace(
        _proxy=SimpleNamespace(
            DaqStatus=lambda: status, bandpassLoadBalancerEnabled=False
        )
    )


def _sent(
    tile_commands: unittest.mock.Mock, command_name: str, timeout: float = 5.0
) -> list[dict[str, Any]]:
    """
    Return the arguments of every send of a command to the tiles.

    Re-routes happen asynchronously, so wait up to a timeout for the first,
    then a little longer so that any duplicate sends are also returned.

    :param tile_commands: the mock standing in for the tile fan-out.
    :param command_name: the tile command of interest.
    :param timeout: how long to wait for at least one send.

    :return: the decoded JSON argument of each send, in order.
    """

    def sends() -> list[dict[str, Any]]:
        return [
            json.loads(sent.args[1])
            for sent in tile_commands.call_args_list
            if sent.args[0] == command_name
        ]

    deadline = time.monotonic() + timeout
    while not sends() and time.monotonic() < deadline:
        time.sleep(0.05)
    time.sleep(0.3)
    return sends()


@pytest.fixture(name="routed")
def routed_fixture(
    station_component_manager: SpsStationComponentManager,
) -> SimpleNamespace:
    """
    Return a station component manager that has routed data to its DAQs.

    The LMC DAQ advertises 10.0.0.1:4663 and the bandpass DAQ advertises
    10.0.0.2:4660. The bandpass DAQ has no load balancer, so integrated
    data is routed over 40G.

    :param station_component_manager: the SPS station component manager under test.

    :return: the component manager, the mock tile fan-out, and the JSON
        that was routed for each tile command.
    """
    station_component_manager._lmc_daq_proxy = _fake_daq(  # type: ignore[assignment]
        "10.0.0.1", 4663
    )
    station_component_manager._bandpass_daq_proxy = _fake_daq(
        "10.0.0.2"
    )  # type: ignore[assignment]
    tile_commands = unittest.mock.Mock(return_value=([ResultCode.OK], ["OK"]))
    station_component_manager._execute_async_on_tiles = (  # type: ignore[method-assign]
        tile_commands
    )
    result_code, _ = station_component_manager._route_data(start_bandpasses=False)
    assert result_code == ResultCode.OK
    routed_json = {
        command_name: _sent(tile_commands, command_name)[-1]
        for command_name in ("SetLmcDownload", "SetLmcIntegratedDownload")
    }
    assert routed_json["SetLmcIntegratedDownload"]["destination_ip"] == "10.0.0.2"
    assert routed_json["SetLmcIntegratedDownload"]["mode"] == "10G"
    assert routed_json["SetLmcDownload"]["destination_ip"] == "10.0.0.1"
    assert routed_json["SetLmcDownload"]["destination_port"] == 4663
    tile_commands.reset_mock()
    return SimpleNamespace(
        component_manager=station_component_manager,
        tile_commands=tile_commands,
        json=routed_json,
    )


@pytest.mark.parametrize(
    ("daq", "command_name", "advertisement", "changed_fields"),
    [
        pytest.param(
            "bandpass",
            "SetLmcIntegratedDownload",
            {"receiverIP": "10.0.0.20"},
            {"destination_ip": "10.0.0.20"},
            id="bandpass DAQ moves",
        ),
        pytest.param(
            "lmc",
            "SetLmcDownload",
            {"receiverIP": "10.0.0.10"},
            {"destination_ip": "10.0.0.10"},
            id="LMC DAQ moves",
        ),
        pytest.param(
            "bandpass",
            "SetLmcIntegratedDownload",
            {"receiverPorts": [5000]},
            {"destination_port": 5000},
            id="only the port changes",
        ),
    ],
)
def test_daq_destination_change_reroutes_tiles(
    routed: SimpleNamespace,
    daq: str,
    command_name: str,
    advertisement: dict[str, Any],
    changed_fields: dict[str, Any],
) -> None:
    """
    Test that a change in a DAQ's advertised destination re-routes the tiles.

    Only the destination changes: the rest of the previous command,
    including the 40G mode, is sent unchanged.

    :param routed: a component manager that has routed data to its DAQs.
    :param daq: which DAQ advertises the change.
    :param command_name: the tile command expected to be re-sent.
    :param advertisement: the change the DAQ advertises.
    :param changed_fields: the fields expected to differ from the routed command.
    """
    state_changed = getattr(routed.component_manager, f"_{daq}_daq_state_changed")
    state_changed(_DAQ_TRL, **advertisement)

    assert _sent(routed.tile_commands, command_name) == [
        routed.json[command_name] | changed_fields
    ]


def test_daq_move_detected_from_events_alone(
    station_component_manager: SpsStationComponentManager,
) -> None:
    """
    Test that a DAQ move is detected when only its events give its destination.

    A new subscription reports the IP and the ports as separate events, so
    each must be recorded on its own for the DAQ's destination to be known.

    This tests behaviour that only exists with the DAQ-following fix, so it
    cannot be run against the code without it.

    :param station_component_manager: the SPS station component manager under test.
    """
    tile_commands = unittest.mock.Mock(return_value=([ResultCode.OK], ["OK"]))
    station_component_manager._execute_async_on_tiles = (  # type: ignore[method-assign]
        tile_commands
    )
    station_component_manager.set_lmc_integrated_download(
        mode="1G",
        channel_payload_length=1024,
        beam_payload_length=1024,
        dst_ip="10.0.0.2",
        override=False,
    )
    routed = _sent(tile_commands, "SetLmcIntegratedDownload")[-1]
    tile_commands.reset_mock()
    station_component_manager._bandpass_daq_state_changed(
        _DAQ_TRL, receiverIP="10.0.0.2"
    )
    station_component_manager._bandpass_daq_state_changed(
        _DAQ_TRL, receiverPorts=[4660]
    )

    station_component_manager._bandpass_daq_state_changed(
        _DAQ_TRL, receiverIP="10.0.0.20"
    )

    assert _sent(tile_commands, "SetLmcIntegratedDownload") == [
        routed | {"destination_ip": "10.0.0.20"}
    ]


@pytest.mark.parametrize("proxy_class", ["_LMCDaqProxy", "_BandpassDaqProxy"])
@pytest.mark.parametrize(
    "version_id",
    ["9.1.0", "9.1.0-rc1", "9.1.0-dev.c1234abcd", "9.1.0+dev.c1234abcd", "9.1.0.dev1"],
)
def test_daq_proxy_subscribes_to_destination_when_supported(
    proxy_class: str,
    version_id: str,
    logger: logging.Logger,
) -> None:
    """
    Test that a DAQ proxy subscribes to the destination on a DAQ that publishes it.

    Development and pre-release builds of the first release that publishes
    it publish it too.

    :param proxy_class: the DAQ proxy class under test.
    :param version_id: the DAQ's version.
    :param logger: a logger for the proxy.
    """
    proxy = getattr(station_cm, proxy_class)(
        _DAQ_TRL, 1, logger, unittest.mock.Mock(), unittest.mock.Mock()
    )
    proxy._proxy = SimpleNamespace(versionId=version_id)

    subscribed = {name.lower() for name in proxy.get_change_event_callbacks()}

    assert {"receiverip", "receiverports"} <= subscribed


@pytest.mark.parametrize(
    "advertisement",
    [
        pytest.param({"receiverIP": "10.0.0.2"}, id="same IP"),
        pytest.param({"receiverPorts": [4660]}, id="same port"),
        pytest.param({"receiverIP": "123.123.123"}, id="invalid IP"),
        pytest.param({"receiverIP": "0.0.0.0"}, id="unspecified IP"),
        pytest.param({"receiverIP": ""}, id="empty IP"),
        pytest.param({"receiverPorts": []}, id="no ports"),
    ],
)
def test_daq_destination_without_change_is_ignored(
    routed: SimpleNamespace,
    advertisement: dict[str, Any],
) -> None:
    """
    Test that an advertisement that doesn't move the DAQ doesn't re-route.

    This guards the DAQ-following behaviour; it does not reproduce the bug.

    :param routed: a component manager that has routed data to its DAQs.
    :param advertisement: what the DAQ advertises.
    """
    component_manager = routed.component_manager
    with unittest.mock.patch.object(
        component_manager, "submit_task", wraps=component_manager.submit_task
    ) as submit_task:
        component_manager._bandpass_daq_state_changed(_DAQ_TRL, **advertisement)

    submit_task.assert_not_called()
    assert not _sent(routed.tile_commands, "SetLmcIntegratedDownload", timeout=0.5)


def test_daq_destination_before_routing_is_only_recorded(
    station_component_manager: SpsStationComponentManager,
) -> None:
    """
    Test that DAQ advertisements don't route data the station never routed.

    This covers the station restarting while tiles are running: whatever
    the tiles are doing is left alone. This guards the DAQ-following
    behaviour; it does not reproduce the bug.

    :param station_component_manager: the SPS station component manager under test.
    """
    tile_commands = unittest.mock.Mock(return_value=([ResultCode.OK], ["OK"]))
    station_component_manager._execute_async_on_tiles = (  # type: ignore[method-assign]
        tile_commands
    )

    for ip in ("10.0.0.2", "10.0.0.20"):
        station_component_manager._bandpass_daq_state_changed(
            _DAQ_TRL, receiverIP=ip, receiverPorts=[4660]
        )

    assert not _sent(tile_commands, "SetLmcIntegratedDownload", timeout=0.5)


def test_first_destination_after_station_start_is_only_recorded(
    station_component_manager: SpsStationComponentManager,
) -> None:
    """
    Test that the first destination a DAQ advertises is not acted on.

    After the station starts, whatever the tiles were last told is left
    alone, even though it differs from what the DAQ advertises. Here the
    tiles were told by a manual override. This guards the DAQ-following
    behaviour; it does not reproduce the bug.

    :param station_component_manager: the SPS station component manager under test.
    """
    tile_commands = unittest.mock.Mock(return_value=([ResultCode.OK], ["OK"]))
    station_component_manager._execute_async_on_tiles = (  # type: ignore[method-assign]
        tile_commands
    )
    station_component_manager.set_lmc_integrated_download(
        mode="1G",
        channel_payload_length=1024,
        beam_payload_length=1024,
        dst_ip="10.0.0.99",
    )
    tile_commands.reset_mock()

    station_component_manager._bandpass_daq_state_changed(
        _DAQ_TRL, receiverIP="10.0.0.2"
    )
    station_component_manager._bandpass_daq_state_changed(
        _DAQ_TRL, receiverPorts=[4661]
    )

    assert not _sent(tile_commands, "SetLmcIntegratedDownload", timeout=0.5)


def test_reroute_skipped_when_tiles_already_at_destination(
    routed: SimpleNamespace,
) -> None:
    """
    Test that a queued re-route does nothing if the stream was routed meanwhile.

    A DAQ change during On or Initialise queues a re-route behind that
    command, which has itself routed data to the DAQ's new destination.
    This tests behaviour that only exists with the DAQ-following fix, so it
    cannot be run against the code without it.

    :param routed: a component manager that has routed data to its DAQs.
    """
    routed.component_manager._reroute("bandpass")

    assert not _sent(routed.tile_commands, "SetLmcIntegratedDownload", timeout=0.5)


@pytest.mark.parametrize(
    ("version_id", "log_level"),
    [
        ("9.0.1", "info"),
        ("9.0.2-rc1", "info"),
        ("not a version", "warning"),
        (None, "warning"),
    ],
)
def test_daq_proxy_does_not_subscribe_to_destination_when_unsupported(
    version_id: Optional[str],
    log_level: str,
) -> None:
    """
    Test that a DAQ proxy doesn't subscribe to an older DAQ's destination.

    An older DAQ is expected, but a version that can't be read or understood
    is a problem, so it is warned about. This tests behaviour that only
    exists with the DAQ-following fix, so it cannot be run against the code
    without it.

    :param version_id: the DAQ's version, or None if it can't be read.
    :param log_level: the level at which not subscribing should be logged.
    """
    logger = unittest.mock.Mock()
    proxy = station_cm._BandpassDaqProxy(
        _DAQ_TRL, 1, logger, unittest.mock.Mock(), unittest.mock.Mock()
    )
    if version_id is None:
        proxy._proxy = unittest.mock.Mock()
        type(proxy._proxy).versionId = unittest.mock.PropertyMock(
            side_effect=tango.DevFailed()
        )
    else:
        proxy._proxy = SimpleNamespace(versionId=version_id)  # type: ignore[assignment]

    subscribed = {name.lower() for name in proxy.get_change_event_callbacks()}

    assert not {"receiverip", "receiverports"} & subscribed
    assert any(
        "does not publish its destination" in str(call)
        or "could not be read" in str(call)
        for call in getattr(logger, log_level).call_args_list
    )


def test_daq_proxy_ignores_invalid_destination_event(
    logger: logging.Logger,
) -> None:
    """
    Test that a DAQ proxy doesn't pass on an invalid destination.

    This tests behaviour that only exists with the DAQ-following fix, so it
    cannot be run against the code without it.

    :param logger: a logger for the proxy.
    """
    component_state_callback = unittest.mock.Mock()
    proxy = station_cm._BandpassDaqProxy(
        _DAQ_TRL, 1, logger, unittest.mock.Mock(), component_state_callback
    )
    proxy._proxy = SimpleNamespace(versionId="9.1.0")  # type: ignore[assignment]
    callback = proxy.get_change_event_callbacks()["receiverIP"]

    callback("receiverIP", "10.0.0.20", tango.AttrQuality.ATTR_INVALID)

    component_state_callback.assert_not_called()


def test_daq_move_while_routing_data_is_followed(
    routed: SimpleNamespace,
) -> None:
    """
    Test that a DAQ move reported while data is being routed is not lost.

    Here the move is reported after _route_data has read the DAQ's old
    destination from DaqStatus, and before it has used it.

    :param routed: a component manager that has routed data to its DAQs.
    """
    component_manager = routed.component_manager
    old_status = component_manager._bandpass_daq_proxy._proxy.DaqStatus()

    def daq_status_then_move() -> str:
        component_manager._bandpass_daq_state_changed(_DAQ_TRL, receiverIP="10.0.0.20")
        return old_status

    component_manager._bandpass_daq_proxy._proxy.DaqStatus = daq_status_then_move

    component_manager._route_data(start_bandpasses=False)

    assert (
        _sent(routed.tile_commands, "SetLmcIntegratedDownload")[-1]["destination_ip"]
        == "10.0.0.20"
    )
    assert component_manager._daq_routes["bandpass"].advertised_ip == "10.0.0.20"


def test_manual_override_during_reroute_is_kept(
    routed: SimpleNamespace,
) -> None:
    """
    Test that a manual override made while a re-route is in progress is kept.

    The re-route must not send its stale copy of the previous command's
    settings after the override has been sent.

    This tests behaviour that only exists with the DAQ-following fix, so it
    cannot be run against the code without it.

    :param routed: a component manager that has routed data to its DAQs.
    """
    component_manager = routed.component_manager
    send_route = component_manager._send_route
    override_done = threading.Event()

    def override() -> None:
        component_manager.set_lmc_integrated_download(
            mode="1G",
            channel_payload_length=512,
            beam_payload_length=256,
            dst_ip="10.0.0.99",
            override=True,
        )
        override_done.set()

    def send_route_with_override(*args: Any, **kwargs: Any) -> Any:
        if threading.current_thread() is not override_thread:
            override_thread.start()
            override_done.wait(timeout=0.5)
        return send_route(*args, **kwargs)

    override_thread = threading.Thread(target=override)
    with unittest.mock.patch.object(
        component_manager, "_send_route", side_effect=send_route_with_override
    ):
        component_manager._bandpass_daq_state_changed(_DAQ_TRL, receiverIP="10.0.0.20")
        assert override_done.wait(timeout=5.0)
    override_thread.join(timeout=5.0)

    final = _sent(routed.tile_commands, "SetLmcIntegratedDownload")[-1]
    assert (final["destination_ip"], final["beam_payload_length"]) == (
        "10.0.0.99",
        256,
    )
    assert component_manager._daq_routes["bandpass"].last_sent == final


def acquire_data_for_calibration(
    component_manager: SpsStationComponentManager,
) -> None:
    """
    Acquire data for calibration, without needing communication established.

    :param component_manager: the SPS station component manager under test.
    """
    # Called past its check_communicating decorator.
    acquire = SpsStationComponentManager.acquire_data_for_calibration
    acquire.__wrapped__(  # type: ignore[attr-defined] # pylint: disable=no-member
        component_manager, first_channel=0, last_channel=1
    )


def test_daq_move_during_calibration_acquisition_waits(
    routed: SimpleNamespace,
) -> None:
    """
    Test that a DAQ move isn't followed during a calibration acquisition.

    Re-routing would disrupt the acquisition, so the move is followed when
    the acquisition's teardown runs. Here the acquisition stops early,
    because the tiles aren't synchronised.

    :param routed: a component manager that has routed data to its DAQs.
    """
    component_manager = routed.component_manager
    component_manager._stop_daq = unittest.mock.Mock()  # type: ignore[method-assign]

    def move_daq_during_acquisition() -> list[str]:
        component_manager._lmc_daq_state_changed(_DAQ_TRL, receiverIP="10.0.0.10")
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and not any(
            "calibration acquisition" in str(call) for call in warning.call_args_list
        ):
            time.sleep(0.05)
        assert not _sent(routed.tile_commands, "SetLmcDownload", timeout=0.1)
        return ["Initialised"]

    with unittest.mock.patch.object(
        component_manager.logger, "warning", wraps=component_manager.logger.warning
    ) as warning, unittest.mock.patch.object(
        component_manager,
        "tile_programming_state",
        side_effect=move_daq_during_acquisition,
    ):
        acquire_data_for_calibration(component_manager)

    assert any(
        "calibration acquisition" in str(call) for call in warning.call_args_list
    )
    assert _sent(routed.tile_commands, "SetLmcDownload") == [
        routed.json["SetLmcDownload"] | {"destination_ip": "10.0.0.10"}
    ]
    component_manager._stop_daq.assert_called_once()


def test_calibration_teardown_stops_daq_even_if_following_daqs_fails(
    routed: SimpleNamespace,
) -> None:
    """
    Test that an acquisition's teardown stops the DAQ whatever else fails.

    :param routed: a component manager that has routed data to its DAQs.
    """
    component_manager = routed.component_manager
    component_manager._stop_daq = unittest.mock.Mock()  # type: ignore[method-assign]
    component_manager._follow_daqs = unittest.mock.Mock(  # type: ignore[method-assign]
        side_effect=RuntimeError("Executor has been shut down")
    )

    with unittest.mock.patch.object(
        component_manager, "tile_programming_state", return_value=["Initialised"]
    ):
        acquire_data_for_calibration(component_manager)

    component_manager._stop_daq.assert_called_once()


@pytest.mark.parametrize("command_name", ["SetLmcDownload", "SetLmcIntegratedDownload"])
def test_omitted_destination_rejected_when_daq_has_not_advertised(
    station_component_manager: SpsStationComponentManager,
    command_name: str,
) -> None:
    """
    Test that a routing command without a destination needs one from the DAQ.

    There is no silent fallback to 0.0.0.0, and the rejected command changes
    none of the station's routing settings.

    :param station_component_manager: the SPS station component manager under test.
    :param command_name: the routing command under test.
    """
    tile_commands = unittest.mock.Mock(return_value=([ResultCode.OK], ["OK"]))
    station_component_manager._execute_async_on_tiles = (  # type: ignore[method-assign]
        tile_commands
    )
    settings = (
        station_component_manager._lmc_integrated_mode,
        station_component_manager._lmc_integrated_mode_locked,
        station_component_manager._lmc_channel_payload_length,
        station_component_manager._lmc_beam_payload_length,
    )

    if command_name == "SetLmcDownload":
        result = station_component_manager.set_lmc_download(
            mode="10G", payload_length=8192, dst_ip=""
        )
    else:
        result = station_component_manager.set_lmc_integrated_download(
            mode="40G", channel_payload_length=512, beam_payload_length=256
        )

    assert result[0] == [ResultCode.REJECTED]
    tile_commands.assert_not_called()
    assert settings == (
        station_component_manager._lmc_integrated_mode,
        station_component_manager._lmc_integrated_mode_locked,
        station_component_manager._lmc_channel_payload_length,
        station_component_manager._lmc_beam_payload_length,
    )


def test_route_data_skips_stream_whose_daq_destination_is_unknown(
    station_component_manager: SpsStationComponentManager,
) -> None:
    """
    Test that data is not routed to a DAQ whose destination is unknown.

    Here there is no bandpass DAQ, so the bandpass stream is neither routed
    nor started, rather than being sent to 0.0.0.0.

    :param station_component_manager: the SPS station component manager under test.
    """
    station_component_manager._lmc_daq_proxy = _fake_daq(  # type: ignore[assignment]
        "10.0.0.1"
    )
    tile_commands = unittest.mock.Mock(return_value=([ResultCode.OK], ["OK"]))
    station_component_manager._execute_async_on_tiles = (  # type: ignore[method-assign]
        tile_commands
    )

    result_code, _ = station_component_manager._route_data(start_bandpasses=True)

    assert result_code == ResultCode.OK
    assert [sent.args[0] for sent in tile_commands.call_args_list] == ["SetLmcDownload"]


class _ReroutingDaqSelfCheck(BaseDaqTest):
    """A DAQ self-check that routes data elsewhere, as the real ones do."""

    fail = False

    def test(self: _ReroutingDaqSelfCheck) -> None:
        """
        Route both streams to somewhere other than their DAQs.

        :raises RuntimeError: if the self-check is set to fail.
        """
        self.component_manager.set_lmc_integrated_download(
            mode="1G",
            channel_payload_length=512,
            beam_payload_length=256,
            dst_ip="10.0.0.1",
        )
        self.component_manager.set_lmc_download(
            mode="10G", payload_length=8192, dst_ip="10.0.0.1", dst_port=4999
        )
        if self.fail:
            raise RuntimeError("Self-check failed part way through.")


@pytest.mark.parametrize("self_check_fails", [False, True])
def test_daq_self_check_restores_routing(
    routed: SimpleNamespace,
    logger: logging.Logger,
    self_check_fails: bool,
) -> None:
    """
    Test that a DAQ self-check leaves the station's data routing as it found it.

    That includes the routing settings that the station uses next time it
    routes data, such as the integrated mode and payload lengths.

    :param routed: a component manager that has routed data to its DAQs.
    :param logger: a logger for the self-check.
    :param self_check_fails: whether the self-check fails part way through.
    """
    component_manager = routed.component_manager
    settings = (
        component_manager._lmc_integrated_mode,
        component_manager._lmc_integrated_mode_locked,
        component_manager._lmc_channel_payload_length,
        component_manager._lmc_beam_payload_length,
    )
    self_check = _ReroutingDaqSelfCheck(component_manager, logger, [], [], "", "")
    self_check._proxies_constructed = True
    self_check.fail = self_check_fails

    with unittest.mock.patch.object(
        self_check, "check_requirements", return_value=(True, "")
    ):
        result, _ = self_check.run_test()

    assert result == (TestResult.ERROR if self_check_fails else TestResult.PASSED)
    for route_name, command_name in [
        ("bandpass", "SetLmcIntegratedDownload"),
        ("lmc", "SetLmcDownload"),
    ]:
        assert (
            _sent(routed.tile_commands, command_name)[-1] == routed.json[command_name]
        )
        route = component_manager._daq_routes[route_name]
        assert route.last_sent == routed.json[command_name]
    assert settings == (
        component_manager._lmc_integrated_mode,
        component_manager._lmc_integrated_mode_locked,
        component_manager._lmc_channel_payload_length,
        component_manager._lmc_beam_payload_length,
    )
    assert component_manager.misrouted_data_streams == []


@pytest.mark.parametrize("command_name", ["SetLmcDownload", "SetLmcIntegratedDownload"])
def test_failed_routing_command_not_recorded(
    routed: SimpleNamespace,
    command_name: str,
) -> None:
    """
    Test that a routing command the tiles don't accept changes no settings.

    The station must not believe the tiles are routed in a way they
    rejected, nor re-send that command later.

    :param routed: a component manager that has routed data to its DAQs.
    :param command_name: the routing command under test.
    """
    component_manager = routed.component_manager
    settings = (
        component_manager._lmc_integrated_mode,
        component_manager._lmc_integrated_mode_locked,
        component_manager._lmc_channel_payload_length,
        component_manager._lmc_beam_payload_length,
    )
    routed.tile_commands.return_value = ([ResultCode.FAILED], ["Rejected."])

    if command_name == "SetLmcDownload":
        component_manager.set_lmc_download(
            mode="1G", payload_length=1024, dst_ip="10.0.0.99"
        )
        route = component_manager._daq_routes["lmc"]
    else:
        component_manager.set_lmc_integrated_download(
            mode="1G",
            channel_payload_length=512,
            beam_payload_length=256,
            dst_ip="10.0.0.99",
        )
        route = component_manager._daq_routes["bandpass"]

    assert route.last_sent == routed.json[command_name]
    assert settings == (
        component_manager._lmc_integrated_mode,
        component_manager._lmc_integrated_mode_locked,
        component_manager._lmc_channel_payload_length,
        component_manager._lmc_beam_payload_length,
    )


def test_failed_reroute_flags_misrouted_stream(
    routed: SimpleNamespace,
) -> None:
    """
    Test that the station flags tiles left sending data to an old DAQ address.

    A failed re-route is not retried; the operator is told, and
    RouteDataToDaqs puts it right.

    This tests behaviour that only exists with the DAQ-following fix, so it
    cannot be run against the code without it.

    :param routed: a component manager that has routed data to its DAQs.
    """
    component_manager = routed.component_manager
    routed.tile_commands.return_value = ([ResultCode.FAILED], ["Rejected."])

    component_manager._bandpass_daq_state_changed(_DAQ_TRL, receiverIP="10.0.0.20")

    assert _sent(routed.tile_commands, "SetLmcIntegratedDownload")
    assert component_manager.misrouted_data_streams == ["bandpass: 10.0.0.2:4660"]

    routed.tile_commands.reset_mock()
    routed.tile_commands.return_value = ([ResultCode.OK], ["OK"])
    component_manager._bandpass_daq_state_changed(_DAQ_TRL, receiverIP="10.0.0.20")
    assert not _sent(routed.tile_commands, "SetLmcIntegratedDownload", timeout=0.5)

    component_manager._bandpass_daq_proxy = _fake_daq(  # type: ignore[assignment]
        "10.0.0.20"
    )
    component_manager.route_data_to_daqs()

    assert component_manager.misrouted_data_streams == []


def test_misrouted_data_streams(
    routed: SimpleNamespace,
) -> None:
    """
    Test which routing the station flags as sending data to no DAQ.

    Routing a stream to another of the station's DAQs, as the self-checks
    do, is not flagged. Routing it to an address that none of them
    advertise is.

    This tests behaviour that only exists with the DAQ-following fix, so it
    cannot be run against the code without it.

    :param routed: a component manager that has routed data to its DAQs.
    """
    component_manager = routed.component_manager
    assert component_manager.misrouted_data_streams == []

    component_manager.set_lmc_integrated_download(
        mode="10G",
        channel_payload_length=1024,
        beam_payload_length=1024,
        dst_ip="10.0.0.1",
        dst_port=4663,
    )
    assert component_manager.misrouted_data_streams == []

    component_manager.set_lmc_integrated_download(
        mode="10G",
        channel_payload_length=1024,
        beam_payload_length=1024,
        dst_ip="10.0.0.99",
    )
    assert component_manager.misrouted_data_streams == ["bandpass: 10.0.0.99:4660"]

    component_manager._lmc_daq_state_changed(_DAQ_TRL, receiverIP="0.0.0.0")
    assert component_manager.misrouted_data_streams == [
        "bandpass: 10.0.0.99:4660",
        "LMC: 10.0.0.1:4663",
    ]


def test_reroutes_coalesce(
    routed: SimpleNamespace,
) -> None:
    """
    Test that DAQ moves made before a re-route has run share that re-route.

    :param routed: a component manager that has routed data to its DAQs.
    """
    component_manager = routed.component_manager
    lane_free = threading.Event()

    def occupy_lane(task_callback: Any = None, task_abort_event: Any = None) -> None:
        lane_free.wait(timeout=5.0)

    component_manager.submit_task(occupy_lane)
    with unittest.mock.patch.object(
        component_manager, "submit_task", wraps=component_manager.submit_task
    ) as submit_task:
        for ip in ("10.0.0.20", "10.0.0.21", "10.0.0.20", "10.0.0.22"):
            component_manager._bandpass_daq_state_changed(_DAQ_TRL, receiverIP=ip)
        lane_free.set()
        assert _sent(routed.tile_commands, "SetLmcIntegratedDownload") == [
            routed.json["SetLmcIntegratedDownload"] | {"destination_ip": "10.0.0.22"}
        ]

    assert submit_task.call_count == 1


def test_route_data_carries_on_when_daq_status_cannot_be_read(
    routed: SimpleNamespace,
) -> None:
    """
    Test that a DAQ that can't be asked for its destination doesn't stop routing.

    The DAQ's last advertised destination is used instead, and the other
    stream is routed as usual.

    :param routed: a component manager that has routed data to its DAQs.
    """
    component_manager = routed.component_manager
    component_manager._bandpass_daq_proxy._proxy.DaqStatus = unittest.mock.Mock(
        side_effect=tango.DevFailed()
    )
    task_callback = unittest.mock.Mock()

    component_manager.route_data_to_daqs(task_callback=task_callback)

    assert _sent(routed.tile_commands, "SetLmcIntegratedDownload") == [
        routed.json["SetLmcIntegratedDownload"]
    ]
    assert _sent(routed.tile_commands, "SetLmcDownload") == [
        routed.json["SetLmcDownload"]
    ]
    assert task_callback.call_args.kwargs["status"] == TaskStatus.COMPLETED


@pytest.mark.parametrize(
    "problem", ["bandpass DAQ has no destination", "bandpasses fail to start"]
)
def test_on_and_initialise_unaffected_by_daq_routing_problems(
    routed: SimpleNamespace,
    problem: str,
) -> None:
    """
    Test that DAQ routing problems don't fail On or Initialise.

    They fail only if the tiles reject a routing command, as before. A
    stream that can't be routed is skipped with a warning, and the result
    of starting the bandpasses is not checked.

    :param routed: a component manager that has routed data to its DAQs.
    :param problem: what goes wrong while routing data.
    """
    component_manager = routed.component_manager
    if problem == "bandpass DAQ has no destination":
        component_manager._bandpass_daq_proxy = _fake_daq(  # type: ignore[assignment]
            "0.0.0.0"
        )
    else:
        routed.tile_commands.side_effect = lambda command_name, *args: (
            ([ResultCode.FAILED], ["Rejected."])
            if command_name == "ConfigureIntegratedChannelData"
            else ([ResultCode.OK], ["OK"])
        )

    result_code, _ = component_manager._route_data(start_bandpasses=True)

    assert result_code == ResultCode.OK
    assert _sent(routed.tile_commands, "SetLmcDownload") == [
        routed.json["SetLmcDownload"]
    ]


def test_route_data_fails_when_daq_no_longer_advertises_a_destination(
    routed: SimpleNamespace,
) -> None:
    """
    Test that a stream whose DAQ now reports 0.0.0.0 is neither routed nor ignored.

    Routing it to the DAQ's previous destination would be routing it to a
    stale address, so it isn't routed, and the command fails, saying what
    was routed.

    :param routed: a component manager that has routed data to its DAQs.
    """
    component_manager = routed.component_manager
    component_manager._bandpass_daq_proxy = _fake_daq(  # type: ignore[assignment]
        "0.0.0.0"
    )
    task_callback = unittest.mock.Mock()

    component_manager.route_data_to_daqs(task_callback=task_callback)

    assert not _sent(routed.tile_commands, "SetLmcIntegratedDownload", timeout=0.5)
    assert _sent(routed.tile_commands, "SetLmcDownload") == [
        routed.json["SetLmcDownload"]
    ]
    status = task_callback.call_args.kwargs["status"]
    result_code, message = task_callback.call_args.kwargs["result"]
    assert (status, result_code) == (TaskStatus.FAILED, ResultCode.FAILED)
    assert "bandpass" in message and "LMC" in message


def test_omitted_destination_uses_daq_ip(
    routed: SimpleNamespace,
) -> None:
    """
    Test that a routing command without a destination IP uses the DAQ's IP.

    The port still defaults to 4660, even though the LMC DAQ here advertises
    another port.

    :param routed: a component manager that has routed data to its DAQs.
    """
    routed.component_manager.set_lmc_download(
        mode="10G", payload_length=8192, dst_ip=""
    )

    sent = _sent(routed.tile_commands, "SetLmcDownload")[-1]
    assert (sent["destination_ip"], sent["destination_port"]) == ("10.0.0.1", 4660)


def test_route_data_to_daqs_does_not_start_bandpasses(
    routed: SimpleNamespace,
) -> None:
    """
    Test that routing data to the DAQs on request doesn't start the bandpasses.

    This tests behaviour that only exists with the DAQ-following fix, so it
    cannot be run against the code without it.

    :param routed: a component manager that has routed data to its DAQs.
    """
    task_callback = unittest.mock.Mock()

    routed.component_manager.route_data_to_daqs(task_callback=task_callback)

    assert [sent.args[0] for sent in routed.tile_commands.call_args_list] == [
        "SetLmcIntegratedDownload",
        "SetLmcDownload",
    ]
    task_callback.assert_called_with(
        status=TaskStatus.COMPLETED,
        result=(
            ResultCode.OK,
            "Data routed to DAQs: bandpass data routed to 10.0.0.2:4660; "
            "LMC data routed to 10.0.0.1:4663.",
        ),
    )


def test_get_static_delays(
    communicating_station_component_manager: SpsStationComponentManager,
    tile_id: int,
) -> None:
    """
    Test getting static delays from dummy TelModel.

    :param communicating_station_component_manager: the SPS station component
        manager under test
    :param tile_id: id of the tile which the component manager has been given.
    """
    # First we need an example mapping for our antennas, we have 4 tiles in tests,
    # but lets pretend we have a whole station
    channels = list(range(16))

    # Let's make sure we've got a random assignment of antennas to channels
    random.shuffle(channels)

    antenna_no = 1
    for tpm in range(16):
        for channel in channels:
            communicating_station_component_manager._antenna_mapping[antenna_no] = {
                "tpm": tpm,
                "tpm_y_channel": channel * 2,
                "tpm_x_channel": channel * 2 + 1,
                "delay": antenna_no // 2,
            }
            antenna_no += 1

    static_delays = communicating_station_component_manager._update_static_delays()
    number_of_tiles = communicating_station_component_manager._number_of_tiles
    expected_static_delays = [0 for _ in range(number_of_tiles * 2 * len(channels))]
    antenna_mapping = communicating_station_component_manager._antenna_mapping
    for antenna, antenna_config in antenna_mapping.items():
        if int(antenna_config["tpm"]) in range(
            number_of_tiles
        ):  # Check against 0-based logical IDs [0, 1, 2, 3]
            expected_static_delays[
                (antenna_config["tpm"] * 2 * len(channels))
                + antenna_config["tpm_y_channel"]
            ] = antenna_config["delay"]
            expected_static_delays[
                (antenna_config["tpm"] * 2 * len(channels))
                + antenna_config["tpm_x_channel"]
            ] = antenna_config["delay"]
    assert static_delays == expected_static_delays


def test_self_check(
    communicating_station_component_manager: SpsStationComponentManager,
    callbacks: MockCallableGroup,
) -> None:
    """
    Test running a self_check with example tests.

    :param communicating_station_component_manager: the SPS station component
        manager under test
    :param callbacks: dictionary of driver callbacks.
    """
    communicating_station_component_manager.self_check(task_callback=callbacks["task"])

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
    communicating_station_component_manager: SpsStationComponentManager,
    callbacks: MockCallableGroup,
    test_name: str,
) -> None:
    """
    Test running a run_test with example tests.

    :param communicating_station_component_manager: the SPS station component
        manager under test
    :param callbacks: dictionary of driver callbacks.
    :param test_name: name of test to run.
    """
    communicating_station_component_manager.run_test(
        task_callback=callbacks["task"], test_name=test_name, count=1
    )

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
    communicating_station_component_manager: SpsStationComponentManager,
    mock_tiles: list[MccsDeviceProxy],
) -> None:
    """
    Test the method to run commands async.

    :param communicating_station_component_manager: the SPS station component
        manager under test
    :param mock_tiles: mock tile proxies, one per tile in the harness.
    """
    mock_tiles[0].tileProgrammingState = "Synchronised"
    mock_tiles[0].pendingDataRequests = True
    [result], [msg] = communicating_station_component_manager.send_data_samples(
        json.dumps({"data_type": "raw"})
    )
    assert result == ResultCode.REJECTED

    [result], [msg] = communicating_station_component_manager.send_data_samples(
        json.dumps({"data_type": "raw"}), force=True
    )
    assert result == ResultCode.OK

    mock_tiles[0].pendingDataRequests = False
    [result], [msg] = communicating_station_component_manager.send_data_samples(
        json.dumps({"data_type": "raw"})
    )
    assert result == ResultCode.OK


def test_power_state_transitions(
    communicating_station_component_manager: SpsStationComponentManager,
    callbacks: MockCallableGroup,
) -> None:
    """
    Test SpsStation's state transitions.

    :param communicating_station_component_manager: the SPS station component
        manager under test
    :param callbacks: dictionary of driver callbacks.
    """
    # Local alias to avoid reformatting every line below to fit the
    # longer fixture name within the line-length limit.
    station_component_manager = communicating_station_component_manager

    for subrack in station_component_manager._subrack_proxies.values():
        assert subrack._proxy is not None
        assert subrack._proxy.state() == tango.DevState.ON
        callbacks["component_state"].assert_call(
            device_name=subrack._name,
            health=HealthState.OK,
            lookahead=25,
        )

    for tile in station_component_manager._tile_proxies.values():
        assert tile._proxy is not None
        assert tile._proxy.state() == tango.DevState.ON
        callbacks["component_state"].assert_call(
            device_name=tile._name,
            health=HealthState.OK,
            lookahead=25,
        )
        # Need to wait for this event to come through before we turn a tile OFF.
        callbacks["component_state"].assert_call(
            device_name=tile._name,
            power=PowerState.ON,
            lookahead=25,
        )
    callbacks["component_state"].assert_call(power=PowerState.ON, lookahead=25)
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
    mock_tiles: list[MccsDeviceProxy],
    num_tiles: int,
) -> None:
    """
    Test the method to run commands async.

    :param station_component_manager: the SPS station component manager
        under test
    :param callbacks: dictionary of driver callbacks.
    :param mock_tiles: list of mock tile proxies that are synchronised.
    :param num_tiles: Number of tiles in the test.
    """
    assert station_component_manager.communication_state == CommunicationStatus.DISABLED
    assert station_component_manager._number_of_tiles >= 4  # Test assumes 4 tiles.

    for idx, tile in enumerate(mock_tiles):
        tile.ppsDelay = 12 + idx  # 12, 13, 14, 15 — distinct from tile indices
        assert tile.tileProgrammingState == "Unknown"
    station_component_manager.start_communicating()
    callbacks["communication_status"].assert_call(CommunicationStatus.NOT_ESTABLISHED)
    callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)

    # Wait for ppsDelay subscription callbacks to populate _pps_delays[0-n].
    total_slots = 16
    expected_delays = [12 + i for i in range(num_tiles)] + [0] * (
        total_slots - num_tiles
    )
    deadline = time.time() + 5.0
    while station_component_manager._pps_delays != expected_delays:
        assert time.time() < deadline, (
            f"Timed out waiting for ppsDelay callbacks: "
            f"{station_component_manager._pps_delays}"
        )
        time.sleep(0.01)
    callbacks["component_state"].assert_call(
        tileProgrammingState=["Unknown", "Unknown", "Unknown", "Unknown"],
        lookahead=25,
    )
    assert station_component_manager._pps_delays == expected_delays
    assert station_component_manager._pps_delay_spread == 0

    # Spread is computed only from Synchronised tiles; move all tiles there first.
    for tile_id in range(0, num_tiles):
        station_component_manager._on_tile_attribute_change(
            logical_tile_id=tile_id,
            attribute_name="tileProgrammingState",
            attribute_value="Synchronised",
            attribute_quality=tango.AttrQuality.ATTR_VALID,
        )

    # Seed all tiles to 0 to create a deterministic baseline.
    for tile_id in range(0, num_tiles):
        station_component_manager._on_tile_attribute_change(
            logical_tile_id=tile_id,
            attribute_name="ppsDelay",
            attribute_value=0,
            attribute_quality=tango.AttrQuality.ATTR_VALID,
        )
    assert station_component_manager._pps_delay_spread == 0

    # Change one tile and verify the spread is computed correctly (4 - 0 == 4).
    station_component_manager._on_tile_attribute_change(
        logical_tile_id=1,
        attribute_name="ppsDelay",
        attribute_value=4,
        attribute_quality=tango.AttrQuality.ATTR_VALID,
    )
    assert station_component_manager._pps_delay_spread == 4

    # Set all tiles to a delay of 4 for a delta of 0.
    for tile_id in range(0, num_tiles):
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


def test_beamformer_table(
    communicating_station_component_manager: SpsStationComponentManager,
    callbacks: MockCallableGroup,
    mock_tiles: list[MccsDeviceProxy],
    tile_initial_beamformer_table: list[int],
    tile_initial_beamformer_regions: list[int],
) -> None:
    """
    Test the method to run commands async.

    :param communicating_station_component_manager: the SPS station component
        manager under test
    :param callbacks: dictionary of driver callbacks.
    :param mock_tiles: mock tile proxies.
    :param tile_initial_beamformer_table: an initial beamformer table for a tile.
    :param tile_initial_beamformer_regions: an initial beamformer regions for a tile.
    """
    # Component manager stores these in np.ndarrays of dims (48, 7 or 8)
    # Should we be converting the tango atttribute to do the same?
    expected_initial_beamformer_regions = np.reshape(
        np.pad(
            tile_initial_beamformer_regions,
            (0, (48 * 8 - len(tile_initial_beamformer_regions))),
        ),
        (48, 8),
    )
    expected_initial_beamformer_table = np.reshape(
        np.pad(
            tile_initial_beamformer_table,
            (0, (48 * 7 - len(tile_initial_beamformer_table))),
        ),
        (48, 7),
    )

    # Component state callback is getting called by many many sources.
    callbacks["component_state"].assert_call(
        beamformerTable=tile_initial_beamformer_table,
        lookahead=50,
        consume_nonmatches=True,
    )
    callbacks["component_state"].assert_call(
        beamformerRegions=tile_initial_beamformer_regions,
        lookahead=10,
    )
    np.testing.assert_array_equal(
        communicating_station_component_manager._beamformer_regions,
        expected_initial_beamformer_regions,
    )
    np.testing.assert_array_equal(
        communicating_station_component_manager._beamformer_table,
        expected_initial_beamformer_table,
    )


def test_initialise_progress_callbacks(
    communicating_station_component_manager: SpsStationComponentManager,
) -> None:
    """
    Test that initialise fires progress callbacks at each step in the right order.

    The per-tile incremental progress inside ``_reinitialise_tiles`` is
    covered by the dedicated test below.

    :param communicating_station_component_manager: the SPS station component
        manager under test
    """
    # Local alias to avoid reformatting every line below to fit the
    # longer fixture name within the line-length limit.
    station_component_manager = communicating_station_component_manager

    # All subracks and tiles must report ON for initialise to proceed.
    for fqdn in station_component_manager._subrack_power_states:
        station_component_manager._subrack_power_states[fqdn] = PowerState.ON
    for fqdn in station_component_manager._tile_power_states:
        station_component_manager._tile_power_states[fqdn] = PowerState.ON

    task_callback = unittest.mock.Mock()

    ok = (ResultCode.OK, "")
    with (
        unittest.mock.patch.object(
            station_component_manager, "_wait_for_wren", return_value=ok
        ),
        unittest.mock.patch.object(
            station_component_manager, "_set_tile_source_ips", return_value=ok
        ),
        unittest.mock.patch.object(
            station_component_manager,
            "_set_global_reference_time",
            return_value=ResultCode.OK,
        ),
        unittest.mock.patch.object(
            station_component_manager, "_reinitialise_tiles", return_value=ok
        ),
        unittest.mock.patch.object(
            station_component_manager, "_initialise_tile_parameters", return_value=ok
        ),
        unittest.mock.patch.object(
            station_component_manager, "_wren_proxy", return_value=object
        ),
        unittest.mock.patch.object(
            station_component_manager, "_initialise_station", return_value=ok
        ),
        unittest.mock.patch.object(
            station_component_manager, "_wait_for_arp_table", return_value=ok
        ),
        unittest.mock.patch.object(
            station_component_manager, "_route_data", return_value=ok
        ),
        unittest.mock.patch.object(
            station_component_manager,
            "_check_station_synchronisation",
            return_value=ok,
        ),
        unittest.mock.patch.object(station_component_manager, "start_beamformer"),
    ):
        station_component_manager.initialise(task_callback=task_callback)

    progress_calls = [
        call.kwargs["progress"]
        for call in task_callback.call_args_list
        if "progress" in call.kwargs
    ]
    assert progress_calls == [5, 10, 70, 75, 85, 90, 95]

    task_callback.assert_called_with(
        status=TaskStatus.COMPLETED,
        result=(ResultCode.OK, "Initialisation Complete"),
    )


def test_reinitialise_tiles_progress_callbacks(
    communicating_station_component_manager: SpsStationComponentManager,
    num_tiles: int,
) -> None:
    """
    Test that _reinitialise_tiles fires progress callbacks.

    Progress should be interpolated between progress_start and progress_end
    based on how many tiles have reached the desired state, and a callback
    should only fire when that count changes.

    :param communicating_station_component_manager: the SPS station component
        manager under test
    :param num_tiles: number of TPMs in the test.
    """
    # Set a non-empty global reference time so the desired state is only "Synchronised"
    communicating_station_component_manager._global_reference_time = (
        "2026-01-01T00:00:00.000000Z"
    )

    task_callback = unittest.mock.Mock()

    # The mock tile programming state function simulates tiles coming up one at a time.
    # call_count tracks how many tiles have reached "Synchronised" so far.
    call_count = 0

    def mock_tile_programming_state() -> list[str]:
        nonlocal call_count
        n_ready = min(call_count, num_tiles)
        call_count += 1
        return ["Synchronised"] * n_ready + ["Unknown"] * (num_tiles - n_ready)

    progress_start = 10
    progress_end = 70

    with (
        unittest.mock.patch(
            "ska_low_mccs_spshw.station.station_component_manager.time.sleep"
        ),
        unittest.mock.patch.object(
            communicating_station_component_manager,
            "tile_programming_state",
            mock_tile_programming_state,
        ),
    ):
        result_code, _ = communicating_station_component_manager._reinitialise_tiles(
            task_callback=task_callback,
            progress_start=progress_start,
            progress_end=progress_end,
        )

    assert result_code == ResultCode.OK

    progress_calls = [call.kwargs["progress"] for call in task_callback.call_args_list]

    expected_progress = [
        int(progress_start + (progress_end - progress_start) * i / num_tiles)
        for i in range(1, num_tiles + 1)
    ]
    assert progress_calls == expected_progress


def test_pointing_delays(
    communicating_station_component_manager: SpsStationComponentManager,
    callbacks: MockCallableGroup,
    num_tiles: int,
    tile_initial_pointing_delays: np.ndarray,
) -> None:
    """
    Test we record pointing delays correctly.

    :param communicating_station_component_manager: the SPS station component
        manager under test
    :param callbacks: dictionary of driver callbacks.
    :param num_tiles: number of TPMs in the test.
    :param tile_initial_pointing_delays: intial pointing delays the TPMs
        are mocked to have
    """
    expected_call = {
        tile_id: tile_initial_pointing_delays for tile_id in range(num_tiles)
    }

    # Large lookahead as this is only done once we got data for all TPMs
    callbacks["component_state"].assert_call(
        pointingdelays=expected_call,
        lookahead=50,
    )


def test_pointing_delays_with_unsupported_beams_still_publishes(
    station_component_manager: SpsStationComponentManager,
    callbacks: MockCallableGroup,
    num_tiles: int,
) -> None:
    """
    Test that unsupported beams on one tile don't block publishing forever.

    A tile on older firmware only supports 8 (of 48) beams, and reports
    NaN for the remaining, permanently-unsupported beam rows. This must
    not prevent pointingdelays from ever being published for the rest of
    the station, and must not prevent later rounds from publishing either.

    Calls _on_tile_attribute_change directly without start_communicating() to
    avoid race conditions with background Tango subscription event threads.

    :param station_component_manager: the SPS station component manager
        under test
    :param callbacks: dictionary of driver callbacks.
    :param num_tiles: number of TPMs in the test.
    """
    full_delays = np.arange(48 * 32, dtype=float).reshape(48, 32)
    old_firmware_delays = full_delays.copy()
    old_firmware_delays[8:] = np.nan
    old_firmware_tile = 0

    def report_all_tiles() -> None:
        for tile_id in range(num_tiles):
            delays = (
                old_firmware_delays if tile_id == old_firmware_tile else full_delays
            )
            station_component_manager._on_tile_attribute_change(
                tile_id, "pointingDelays", delays, tango.AttrQuality.ATTR_VALID
            )

    expected_call = {
        tile_id: (old_firmware_delays if tile_id == old_firmware_tile else full_delays)
        for tile_id in range(num_tiles)
    }

    report_all_tiles()
    callbacks["component_state"].assert_call(pointingdelays=expected_call)

    # A second round with the same permanently-unsupported beams must also
    # publish, rather than getting stuck forever waiting for those beams to
    # stop being NaN.
    report_all_tiles()
    callbacks["component_state"].assert_call(pointingdelays=expected_call)


def test_beamformer_daisy_chain(
    station_component_manager: SpsStationComponentManager,
    callbacks: MockCallableGroup,
    num_tiles: int,
) -> None:
    """
    Test that the station validates beamformer daisy-chain routing.

    Verifies that the component manager emits beamformerDaisyChainValid=True
    once all tiles report the expected destination IPs, and flips to False when
    a tile reports a wrong IP.

    Calls _on_tile_attribute_change directly without start_communicating() to
    avoid race conditions with background Tango subscription event threads.

    :param station_component_manager: the SPS station component manager under test
    :param callbacks: dictionary of driver callbacks.
    :param num_tiles: number of TPMs in the test.
    """
    # Fixture uses IPv4Interface("10.0.0.152/16").
    sdn_base = ipaddress.IPv4Address("10.0.0.152")
    last = num_tiles - 1

    def set_dst_ips(tile_id: int, fpga1: str, fpga2: str) -> None:
        station_component_manager._on_tile_attribute_change(
            tile_id, "dstip40gfpga1", fpga1, tango.AttrQuality.ATTR_VALID
        )
        station_component_manager._on_tile_attribute_change(
            tile_id, "dstip40gfpga2", fpga2, tango.AttrQuality.ATTR_VALID
        )

    # Tiles within the chain send to each other; last tile is ignored.
    for tile_id in range(last):
        set_dst_ips(
            tile_id,
            str(sdn_base + 2 * tile_id + 2),
            str(sdn_base + 2 * tile_id + 3),
        )
    callbacks["component_state"].assert_call(beamformerDaisyChainValid=True)

    # Oh no someone broke it.
    set_dst_ips(1, "1.2.3.4", str(sdn_base + 2 * 1 + 3))
    callbacks["component_state"].assert_call(beamformerDaisyChainValid=False)

    # Yay they fixed it.
    set_dst_ips(1, str(sdn_base + 2 * 1 + 2), str(sdn_base + 2 * 1 + 3))
    callbacks["component_state"].assert_call(beamformerDaisyChainValid=True)


def test_beamformer_flagged_count(
    station_component_manager: SpsStationComponentManager,
    callbacks: MockCallableGroup,
    num_tiles: int,
) -> None:
    """
    Test that only the final tile's beamformer flagged counts affect health.

    Calls _on_tile_attribute_change directly without start_communicating() to
    avoid race conditions with background Tango subscription event threads.

    Checks:
    - Non-final tiles' counts do not fire any component_state callback.
    - Final tile non-zero fpga0 count → finalTileBeamformerFlaggedCountOk=False.
    - Repeated identical value does not re-fire (deduplication).
    - fpga0 cleared while fpga1 still zero → True.
    - Non-zero fpga1 → False; clearing → True.

    :param station_component_manager: the SPS station component manager under test.
    :param callbacks: dictionary of driver callbacks.
    :param num_tiles: number of TPMs in the test.
    """
    last = num_tiles - 1

    # Non-final tiles must not trigger any callback.
    for tile_id in range(last):
        station_component_manager._on_tile_attribute_change(
            tile_id,
            "fpga0_station_beamformer_flagged_count",
            5,
            tango.AttrQuality.ATTR_VALID,
        )
    callbacks["component_state"].assert_not_called()

    # Final tile fpga0 non-zero → not ok.
    station_component_manager._on_tile_attribute_change(
        last,
        "fpga0_station_beamformer_flagged_count",
        5,
        tango.AttrQuality.ATTR_VALID,
    )
    callbacks["component_state"].assert_call(finalTileBeamformerFlaggedCountOk=False)

    # Same value again — no duplicate callback.
    station_component_manager._on_tile_attribute_change(
        last,
        "fpga0_station_beamformer_flagged_count",
        5,
        tango.AttrQuality.ATTR_VALID,
    )
    callbacks["component_state"].assert_not_called()

    # fpga0 back to zero (fpga1 still zero) → ok.
    station_component_manager._on_tile_attribute_change(
        last,
        "fpga0_station_beamformer_flagged_count",
        0,
        tango.AttrQuality.ATTR_VALID,
    )
    callbacks["component_state"].assert_call(finalTileBeamformerFlaggedCountOk=True)

    # fpga1 non-zero → not ok.
    station_component_manager._on_tile_attribute_change(
        last,
        "fpga1_station_beamformer_flagged_count",
        3,
        tango.AttrQuality.ATTR_VALID,
    )
    callbacks["component_state"].assert_call(finalTileBeamformerFlaggedCountOk=False)

    # Both zero → ok.
    station_component_manager._on_tile_attribute_change(
        last,
        "fpga1_station_beamformer_flagged_count",
        0,
        tango.AttrQuality.ATTR_VALID,
    )
    callbacks["component_state"].assert_call(finalTileBeamformerFlaggedCountOk=True)


@pytest.mark.parametrize(
    ("fail_on_timeout", "timedout", "expected_result"),
    [
        (True, True, ResultCode.FAILED),
        (True, False, ResultCode.OK),
        (False, True, ResultCode.OK),
        (False, False, ResultCode.OK),
    ],
)
def test_wait_for_wren(
    station_component_manager: SpsStationComponentManager,
    callbacks: MockCallableGroup,
    fail_on_timeout: bool,
    timedout: bool,
    expected_result: ResultCode,
) -> None:
    """
    Test the wait for WREN functionality.

    Checks the following:
    - If fail_on_timeout is True and timeout return FAILED
    - If fail_on_timeout is True and not timeout return OK
    - If fail_on_timeout is False and timeout return OK
    - If fail_on_timeout is False and not timeout return OK

    :param station_component_manager: the SPS station component manager under test.
    :param callbacks: dictionary of driver callbacks.
    :param fail_on_timeout: Is the fail on timeout flag set
    :param timedout: Does the command timeout
    :param expected_result: The expected result

    """
    # Start communicating
    station_component_manager.start_communicating()
    callbacks["communication_status"].assert_call(CommunicationStatus.NOT_ESTABLISHED)
    callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)

    # Setup the health state ok event
    health_state_ok = threading.Event()
    if not timedout:
        health_state_ok.set()

    # Create a mock wren proxy object
    mock_wren_proxy = unittest.mock.Mock(health_state_ok=health_state_ok)

    # Ensure healthState is as expected
    assert mock_wren_proxy.health_state_ok.is_set() != timedout

    # Mock the station component manager _wren_proxy
    station_component_manager._wren_proxy = mock_wren_proxy

    # Wait for the WREN to be in health state OK
    result_code, _ = station_component_manager._wait_for_wren(
        None, None, timeout=1, fail_on_timeout=fail_on_timeout
    )

    # Check we get the expected result
    assert result_code == expected_result
