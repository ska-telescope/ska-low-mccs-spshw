# -*- coding: utf-8 -*
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
from ska_control_model import HealthState, ResultCode, TaskStatus
from ska_low_mccs_common import MccsDeviceProxy
from ska_low_mccs_common.testing import TangoHarness
from ska_low_mccs_common.testing.mock import MockCallable, MockDeviceBuilder
from ska_low_mccs_common.testing.mock.mock_callable import MockCallableDeque

from ska_low_mccs import MccsStation
from ska_low_mccs.station import StationComponentManager


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


@pytest.fixture(name="station_id")
def station_id_fixture() -> int:
    """
    Return the station id of this station.

    :return: the station id of this station.
    """
    # TODO: This must match the StationId property of the station under
    # test. We should refactor the harness so that we can pull it
    # straight from the device configuration.
    return 1


@pytest.fixture(name="apiu_fqdn")
def apiu_fqdn_fixture() -> str:
    """
    Return the FQDN of the Tango device that manages the station's APIU.

    :return: the FQDN of the Tango device that manages the station's
        APIU.
    """
    # TODO: This must match the AntennaFDQNs property of the station
    # under test. We should refactor the harness so that we can pull it
    # straight from the device configuration.
    return "low-mccs/apiu/001"


@pytest.fixture(name="antenna_fqdns")
def antenna_fqdns_fixture() -> list[str]:
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


@pytest.fixture(name="tile_fqdns")
def tile_fqdns_fixture() -> list[str]:
    """
    Return the FQDNs of the Tango devices that manage the station's tiles.

    :return: the FQDNs of the Tango devices that manage the station's
        tiles.
    """
    # TODO: This must match the TileFDQNs property of the station
    # under test. We should refactor the harness so that we can pull it
    # straight from the device configuration.
    return ["low-mccs/tile/0001", "low-mccs/tile/0002"]


@pytest.fixture(name="mock_apiu")
def mock_apiu_fixture() -> MockDeviceBuilder:
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


@pytest.fixture(name="mock_antenna_factory")
def mock_antenna_factory_fixture() -> MockDeviceBuilder:
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


@pytest.fixture(name="mock_tile_factory")
def mock_tile_factory_fixture() -> MockDeviceBuilder:
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


@pytest.fixture(name="initial_mocks")
def initial_mocks_fixture(
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


@pytest.fixture(name="apiu_health_changed_callback")
def apiu_health_changed_callback_fixture(
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


@pytest.fixture(name="antenna_health_changed_callback")
def antenna_health_changed_callback_fixture(
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


@pytest.fixture(name="tile_health_changed_callback")
def tile_health_changed_callback_fixture(
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


@pytest.fixture(name="is_configured_changed_callback")
def is_configured_changed_callback_fixture(
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


@pytest.fixture(name="component_state_changed_callback")
def component_state_changed_callback_fixture(
    mock_callback_deque_factory: Callable[[], unittest.mock.Mock],
) -> Callable[[], None]:
    """
    Return a mock callback for a change in whether the station changes state.

    :param mock_callback_deque_factory: fixture that provides a mock callback deque
        factory.

    :return: a mock callback deque holding a sequence of calls to
        component_state_changed_callback.
    """
    return mock_callback_deque_factory()


@pytest.fixture(name="max_workers")
def max_workers_fixture() -> int:
    """
    Max worker threads available to run a LRC.

    Return an integer specifying the maximum number of worker threads available to
    execute long-running-commands.

    :return: the max number of worker threads.
    """
    max_workers = 1
    return max_workers


# pylint: disable=too-many-arguments
@pytest.fixture(name="station_component_manager")
def station_component_manager_fixture(
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


# pylint: disable=too-many-arguments
@pytest.fixture(name="mock_station_component_manager")
def mock_station_component_manage_fixturer(
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


@pytest.fixture(name="pointing_delays")
def pointing_delays_fixture(mocker: pytest_mock.MockerFixture) -> unittest.mock.Mock:
    """
    Return some mock pointing_delays.

    For now this just returns a mock, but later we might need it to
    behave more like a list of floats

    :param mocker: a fixture that wraps unittest.mock

    :return: some more pointing delays
    """
    return mocker.Mock()


@pytest.fixture(name="mock_component_manager")
def mock_component_manager_fixture(
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


@pytest.fixture(name="patched_station_class")
def patched_station_class_fixture(
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


@pytest.fixture(name="apiu_proxy")
def apiu_proxy_fixture(apiu_fqdn: str, logger: logging.Logger) -> MccsDeviceProxy:
    """
    Return a proxy to the APIU.

    :param apiu_fqdn: FQDN of this station's APIU
    :param logger: a logger for the proxy to use.

    :return: a proxy to the APIU.
    """
    return MccsDeviceProxy(apiu_fqdn, logger)


@pytest.fixture(name="tile_proxies")
def tile_proxies_fixture(
    tile_fqdns: Iterable[str], logger: logging.Logger
) -> list[MccsDeviceProxy]:
    """
    Return a list of proxies to tile devices.

    :param tile_fqdns: FQDNs of tiles in this station
    :param logger: a logger for the proxies to use.

    :return: a list of proxies to tile devices
    """
    return [MccsDeviceProxy(fqdn, logger) for fqdn in tile_fqdns]


@pytest.fixture(name="antenna_proxies")
def antenna_proxies_fixture(
    antenna_fqdns: Iterable[str], logger: logging.Logger
) -> list[MccsDeviceProxy]:
    """
    Return a list of proxies to antenna devices.

    :param antenna_fqdns: FQDNs of antennas in this station
    :param logger: a logger for the proxies to use.

    :return: a list of proxies to antenna devices
    """
    return [MccsDeviceProxy(fqdn, logger) for fqdn in antenna_fqdns]
