# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module defined a pytest harness for testing the MCCS station module."""
from __future__ import annotations

import logging
import unittest.mock
from typing import Any, Callable, Iterable

import pytest
import pytest_mock
from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import HealthState
from ska_tango_base.executor import TaskStatus

from ska_low_mccs import MccsDeviceProxy, MccsStation
from ska_low_mccs.station import StationComponentManager
from ska_low_mccs.testing import TangoHarness
from ska_low_mccs.testing.mock import MockCallable, MockDeviceBuilder
from ska_low_mccs.testing.mock.mock_callable import MockCallableDeque


class MockLongRunningCommand(MockCallable):
    """
    Mock the call to submit a LRC.

    A long running command submission, if successful, returns a
    TaskStatus and result message.
    """

    def __call__(self: MockCallable, *args: Any, **kwargs: Any) -> Any:
        """
        Handle a callback call.

        Create a standard mock, call it, and put it on the queue. (This
        approach lets us take advantange of the mock's assertion
        functionality later.)

        :param args: positional args in the call
        :param kwargs: keyword args in the call

        :return: the object's return calue
        """
        called_mock = unittest.mock.Mock()
        called_mock(*args, **kwargs)
        self._queue.put(called_mock)
        return TaskStatus.QUEUED, "Task queued"


@pytest.fixture()
def station_id() -> int:
    """
    Return the station id of this station.

    :return: the station id of this station.
    """
    # TODO: This must match the StationId property of the station under
    # test. We should refactor the harness so that we can pull it
    # straight from the device configuration.
    return 1


@pytest.fixture()
def apiu_fqdn() -> str:
    """
    Return the FQDN of the Tango device that manages the station's APIU.

    :return: the FQDN of the Tango device that manages the station's
        APIU.
    """
    # TODO: This must match the AntennaFDQNs property of the station
    # under test. We should refactor the harness so that we can pull it
    # straight from the device configuration.
    return "low-mccs/apiu/001"


@pytest.fixture()
def antenna_fqdns() -> list[str]:
    """
    Return the FQDNs of the Tango devices that manage the station's antennas.

    :return: the FQDNs of the Tango devices that manage the station's
        antennas.
    """
    # TODO: This must match the AntennaFDQNs property of the station
    # under test. We should refactor the harness so that we can pull it
    # straight from the device configuration.
    return [
        "low-mccs/antenna/000001",
        "low-mccs/antenna/000002",
        "low-mccs/antenna/000003",
        "low-mccs/antenna/000004",
    ]


@pytest.fixture()
def tile_fqdns() -> list[str]:
    """
    Return the FQDNs of the Tango devices that manage the station's tiles.

    :return: the FQDNs of the Tango devices that manage the station's
        tiles.
    """
    # TODO: This must match the TileFDQNs property of the station
    # under test. We should refactor the harness so that we can pull it
    # straight from the device configuration.
    return ["low-mccs/tile/0001", "low-mccs/tile/0002"]


@pytest.fixture()
def mock_apiu() -> MockDeviceBuilder:
    """
    Fixture that provides a mock apiu.

    The only special behaviour of these mocks is they return a
    (result_code, message) tuple in response to the SetPointingDelay
    call.

    :return: a factory for device proxy mocks
    """
    builder = MockDeviceBuilder()
    builder.add_result_command("Off", result_code=ResultCode.OK)
    builder.add_result_command("On", result_code=ResultCode.OK)
    return builder()


@pytest.fixture()
def mock_antenna_factory() -> MockDeviceBuilder:
    """
    Fixture that provides a factory for mock antennas.

    The only special behaviour of these mocks is they return a
    (result_code, message) tuple in response to the SetPointingDelay
    call.

    :return: a factory for device proxy mocks
    """
    builder = MockDeviceBuilder()
    builder.add_result_command("Off", result_code=ResultCode.OK)
    builder.add_result_command("On", result_code=ResultCode.OK)
    return builder


@pytest.fixture()
def mock_tile_factory() -> MockDeviceBuilder:
    """
    Fixture that provides a factory for mock tiles.

    The only special behaviour of these mocks is they return a
    (result_code, message) tuple in response to the SetPointingDelay
    call.

    :return: a factory for device proxy mocks
    """
    builder = MockDeviceBuilder()
    builder.add_result_command("Off", result_code=ResultCode.OK)
    builder.add_result_command("On", result_code=ResultCode.OK)
    builder.add_result_command("SetPointingDelay", result_code=ResultCode.OK)
    return builder


@pytest.fixture()
def initial_mocks(
    apiu_fqdn: str,
    mock_apiu: unittest.mock.Mock,
    antenna_fqdns: list[str],
    mock_antenna_factory: Callable[[], unittest.mock.Mock],
    tile_fqdns: list[str],
    mock_tile_factory: Callable[[], unittest.mock.Mock],
) -> dict[str, unittest.mock.Mock]:
    """
    Return a specification of the mock devices to be set up in the Tango test harness.

    This is a pytest fixture that can be used to inject pre-build mock
    devices into the Tango test harness at specified FQDNs.

    :param apiu_fqdn: FQDN of this station's APIU
    :param mock_apiu: a mock APIU device to be injected into the Tango
        test harness

    :param antenna_fqdns: FQDNs of the antenna for which mocks are to be
        set up
    :param mock_antenna_factory: a factory for mock antenna devices to
        be injected into the Tango test harness
    :param tile_fqdns: FQDNs of the files for which mocks are to be set
        up
    :param mock_tile_factory: a factory for mock tile devices to be
        injected into the Tango test harness

    :return: specification of the mock devices to be set up in the Tango
        test harness.
    """
    initial_mocks = {apiu_fqdn: mock_apiu}
    initial_mocks.update(
        {antenna_fqdn: mock_antenna_factory() for antenna_fqdn in antenna_fqdns}
    )
    initial_mocks.update({tile_fqdn: mock_tile_factory() for tile_fqdn in tile_fqdns})
    return initial_mocks


@pytest.fixture()
def apiu_health_changed_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> Callable[[HealthState], None]:
    """
    Return a mock callback for a change in the health of the APIU.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the component manager
        detects that health of the APIU has changed.
    """
    return mock_callback_factory()


@pytest.fixture()
def antenna_health_changed_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> Callable[[HealthState], None]:
    """
    Return a mock callback for a change in the health of an antenna.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the component manager
        detects that health of an antenna has changed.
    """
    return mock_callback_factory()


@pytest.fixture()
def tile_health_changed_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> Callable[[HealthState], None]:
    """
    Return a mock callback for a change in the health of a tile.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the component manager
        detects that health of a tile has changed.
    """
    return mock_callback_factory()


@pytest.fixture()
def is_configured_changed_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> Callable[[bool], None]:
    """
    Return a mock callback for a change in whether the station is configured.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback for a change in whether the station is
        configured.
    """
    return mock_callback_factory()


@pytest.fixture()
def component_state_changed_callback(
    mock_callback_deque_factory: Callable[[], unittest.mock.Mock],
) -> Callable[[], None]:
    """
    Return a mock callback for a change in whether the station changes state.

    :param mock_callback_deque_factory: fixture that provides a mock callback deque
        factory.

    :return: a mock callback deque holding a sequence of calls to component_state_changed_callback.
    """
    return mock_callback_deque_factory()


@pytest.fixture()
def max_workers() -> int:
    """
    Max worker threads available to run a LRC.

    Return an integer specifying the maximum number of worker threads available to
    execute long-running-commands.

    :return: the max number of worker threads.
    """
    max_workers = 1
    return max_workers


@pytest.fixture()
def station_component_manager(
    tango_harness: TangoHarness,
    station_id: int,
    apiu_fqdn: str,
    antenna_fqdns: list[str],
    tile_fqdns: list[str],
    logger: logging.Logger,
    max_workers: int,
    communication_state_changed_callback: MockCallable,
    component_state_changed_callback: MockCallableDeque,
) -> StationComponentManager:
    """
    Return a station component manager.

    :param tango_harness: a test harness for Tango devices
    :param station_id: the station id of the station
    :param apiu_fqdn: FQDN of the Tango device that manages this
        station's APIU
    :param antenna_fqdns: FQDNs of the Tango devices that manage this
        station's antennas
    :param tile_fqdns: FQDNs of the Tango devices that manage this
        station's tiles
    :param logger: the logger to be used by this object.
    :param max_workers: max number of threads available to run a LRC.
    :param communication_state_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_state_changed_callback: callback to call when the
        device state changes.

    :return: a station component manager
    """
    return StationComponentManager(
        station_id,
        apiu_fqdn,
        antenna_fqdns,
        tile_fqdns,
        logger,
        max_workers,
        communication_state_changed_callback,
        component_state_changed_callback,
    )


@pytest.fixture()
def mock_station_component_manager(
    station_id: int,
    apiu_fqdn: str,
    antenna_fqdns: list[str],
    tile_fqdns: list[str],
    logger: logging.Logger,
    max_workers: int,
    communication_state_changed_callback: MockCallable,
    component_state_changed_callback: MockCallableDeque,
) -> StationComponentManager:
    """
    Return a station component manager.

    :param station_id: the station id of the station
    :param apiu_fqdn: FQDN of the Tango device that manages this
        station's APIU
    :param antenna_fqdns: FQDNs of the Tango devices that manage this
        station's antennas
    :param tile_fqdns: FQDNs of the Tango devices that manage this
        station's tiles
    :param logger: the logger to be used by this object.
    :param max_workers: max number of threads available to run a LRC.
    :param communication_state_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes.
    :param component_state_changed_callback: callback to call when the
        device state changes.

    :return: a station component manager
    """
    return StationComponentManager(
        station_id,
        apiu_fqdn,
        antenna_fqdns,
        tile_fqdns,
        logger,
        max_workers,
        communication_state_changed_callback,
        component_state_changed_callback,
    )


@pytest.fixture()
def pointing_delays(mocker: pytest_mock.MockerFixture) -> unittest.mock.Mock:
    """
    Return some mock pointing_delays.

    For now this just returns a mock, but later we might need it to
    behave more like a list of floats

    :param mocker: a fixture that wraps unittest.mock

    :return: some more pointing delays
    """
    return mocker.Mock()


@pytest.fixture()
def mock_component_manager(
    mocker: pytest_mock.MockerFixture,
) -> unittest.mock.Mock:
    """
    Return a mock to be used as a component manager for the station device.

    :param mocker: fixture that wraps the :py:mod:`unittest.mock`
        module

    :return: a mock to be used as a component manager for the station
        device.
    """
    mock_component_manager = mocker.Mock()
    mock_component_manager.apply_pointing = MockLongRunningCommand()
    mock_component_manager.configure = MockLongRunningCommand()
    return mock_component_manager


@pytest.fixture()
def patched_station_class(
    mock_component_manager: unittest.mock.Mock,
) -> type[MccsStation]:
    """
    Return a station device class that has been patched for testing.

    :param mock_component_manager: the mock component manage to patch
        into this station.

    :return: a station device class that has been patched for testing.
    """

    class PatchedStation(MccsStation):
        """A station class that has had its component manager mocked out for testing."""

        def create_component_manager(
            self: PatchedStation,
        ) -> unittest.mock.Mock:
            """
            Return a mock component manager instead of the usual one.

            :return: a mock component manager
            """
            return mock_component_manager

    return PatchedStation


@pytest.fixture()
def apiu_proxy(apiu_fqdn: str, logger: logging.Logger) -> MccsDeviceProxy:
    """
    Return a proxy to the APIU.

    :param apiu_fqdn: FQDN of this station's APIU
    :param logger: a logger for the proxy to use.

    :return: a proxy to the APIU.
    """
    return MccsDeviceProxy(apiu_fqdn, logger)


@pytest.fixture()
def tile_proxies(
    tile_fqdns: Iterable[str], logger: logging.Logger
) -> list[MccsDeviceProxy]:
    """
    Return a list of proxies to tile devices.

    :param tile_fqdns: FQDNs of tiles in this station
    :param logger: a logger for the proxies to use.

    :return: a list of proxies to tile devices
    """
    return [MccsDeviceProxy(fqdn, logger) for fqdn in tile_fqdns]


@pytest.fixture()
def antenna_proxies(
    antenna_fqdns: Iterable[str], logger: logging.Logger
) -> list[MccsDeviceProxy]:
    """
    Return a list of proxies to antenna devices.

    :param antenna_fqdns: FQDNs of antennas in this station
    :param logger: a logger for the proxies to use.

    :return: a list of proxies to antenna devices
    """
    return [MccsDeviceProxy(fqdn, logger) for fqdn in antenna_fqdns]
