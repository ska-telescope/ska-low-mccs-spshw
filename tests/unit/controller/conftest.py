# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module defines a pytest harness for testing the MCCS controller module."""
from __future__ import annotations

import logging
import unittest
from typing import Callable, Iterable, Optional

import pytest
import pytest_mock
from ska_control_model import CommunicationStatus, PowerState, ResultCode, TaskStatus
from ska_low_mccs_common import MccsDeviceProxy
from ska_low_mccs_common.testing import TangoHarness
from ska_low_mccs_common.testing.mock import (  # MockChangeEventCallback,
    MockCallable,
    MockCallableDeque,
    MockDeviceBuilder,
    MockSubarrayBuilder,
)

from ska_low_mccs.controller import (
    ControllerComponentManager,
    ControllerResourceManager,
    MccsController,
)


@pytest.fixture()
def subarray_fqdns() -> list[str]:
    """
    Return the FQDNs of subarrays managed by the controller.

    :return: the FQDNs of subarrays managed by the controller.
    """
    # TODO: This must match the MccsSubarrays property of the
    # controller. We should refactor the harness so that we can pull it
    # straight from the device configuration.
    return ["low-mccs/subarray/01", "low-mccs/subarray/02"]


@pytest.fixture()
def subrack_fqdns() -> list[str]:
    """
    Return the FQDNs of subracks managed by the controller.

    :return: the FQDNs of subracks managed by the controller.
    """
    # TODO: This must match the MccsSubracks property of the
    # controller. We should refactor the harness so that we can pull it
    # straight from the device configuration.
    return ["low-mccs/subrack/01"]


@pytest.fixture()
def station_fqdns() -> list[str]:
    """
    Return the FQDNs of stations managed by the controller.

    :return: the FQDNs of stations managed by the controller.
    """
    # TODO: This must match the MccsStations property of the
    # controller. We should refactor the harness so that we can pull it
    # straight from the device configuration.
    return ["low-mccs/station/001", "low-mccs/station/002"]


@pytest.fixture()
def subarray_beam_fqdns() -> list[str]:
    """
    Return the FQDNs of subarray_beams managed by the controller.

    :return: the FQDNs of subarray_beams managed by the controller.
    """
    # TODO: This must match the MccsSubarrayBeams property of the
    # controller. We should refactor the harness so that we can pull it
    # straight from the device configuration.
    return [
        "low-mccs/subarraybeam/01",
        "low-mccs/subarraybeam/02",
        "low-mccs/subarraybeam/03",
        "low-mccs/subarraybeam/04",
    ]


@pytest.fixture()
def station_beam_fqdns() -> list[str]:
    """
    Return the FQDNs of station_beams managed by the controller.

    :return: the FQDNs of station_beams managed by the controller.
    """
    # TODO: This must match the MccsStationBeams property of the
    # controller. We should refactor the harness so that we can pull it
    # straight from the device configuration.
    return [
        "low-mccs/beam/01",
        "low-mccs/beam/02",
        "low-mccs/beam/03",
        "low-mccs/beam/04",
    ]


@pytest.fixture()
def channel_blocks() -> list[int]:
    """
    Return the channel blocks controlled by this controller.

    :return: the channel blocks controller by this controller.
    """
    return list(range(1, 49))  # TODO: Should this be "range(9, 57)"?


@pytest.fixture()
def controller_resource_manager(
    subarray_fqdns: Iterable[str],
    subrack_fqdns: Iterable[str],
    subarray_beam_fqdns: Iterable[str],
    station_beam_fqdns: Iterable[str],
    channel_blocks: Iterable[int],
) -> ControllerResourceManager:
    """
    Return a controller resource manager for testing.

    :param subarray_fqdns: FQDNS of all subarray devices
    :param subrack_fqdns: FQDNS of all subrack devices
    :param subarray_beam_fqdns: FQDNS of all subarray beam devices
    :param station_beam_fqdns: FQDNS of all subarray beam devices
    :param channel_blocks: ordinal numbers of all channel blocks

    :return: a controller resource manager for testing
    """
    return ControllerResourceManager(
        subarray_fqdns,
        subrack_fqdns,
        subarray_beam_fqdns,
        station_beam_fqdns,
        channel_blocks,
    )


@pytest.fixture()
def subrack_health_changed_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> unittest.mock.Mock:
    """
    Return a mock callback for a change in the health of a subrack.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the component manager
        detects that health of a subrack has changed.
    """
    return mock_callback_factory()


@pytest.fixture()
def station_health_changed_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> unittest.mock.Mock:
    """
    Return a mock callback for a change in the health of a station.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the component manager
        detects that health of a station has changed.
    """
    return mock_callback_factory()


@pytest.fixture()
def subarray_beam_health_changed_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> unittest.mock.Mock:
    """
    Return a mock callback for a change in the health of a subarray beam.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the component manager
        detects that health of a subarray beam has changed.
    """
    return mock_callback_factory()


@pytest.fixture()
def station_beam_health_changed_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> unittest.mock.Mock:
    """
    Return a mock callback for a change in the health of a station beam.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the component manager
        detects that health of a station beam has changed.
    """
    return mock_callback_factory()


@pytest.fixture()
def component_state_changed_callback(
    mock_callback_deque_factory: Callable[[], unittest.mock.Mock],
) -> unittest.mock.Mock:
    """
    Return a mock callback for a change in state.

    :param mock_callback_deque_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the component manager
        detects that state has changed.
    """
    return mock_callback_deque_factory()


@pytest.fixture()
def max_workers() -> int:
    """
    Return the number of MockCallableworker threads.

    (This is a pytest fixture.)

    :return: the number of worker threads
    """
    return 1


@pytest.fixture()
def controller_component_manager(
    tango_harness: TangoHarness,
    subarray_fqdns: Iterable[str],
    subrack_fqdns: Iterable[str],
    station_fqdns: Iterable[str],
    subarray_beam_fqdns: Iterable[str],
    station_beam_fqdns: Iterable[str],
    logger: logging.Logger,
    max_workers: int,
    communication_state_changed_callback: MockCallable,
    component_state_changed_callback: MockCallableDeque,
) -> ControllerComponentManager:
    """
    Return a controller component manager in simulation mode.

    :param tango_harness: a test harness for Tango devices
    :param subarray_fqdns: FQDNS of all subarray devices
    :param subrack_fqdns: FQDNS of all subrack devices
    :param station_fqdns: FQDNS of all station devices
    :param subarray_beam_fqdns: FQDNS of all subarray beam devices
    :param station_beam_fqdns: FQDNS of all station beam devices
    :param logger: the logger to be used by this object.
    :param max_workers: nos of threads
    :param communication_state_changed_callback: callback to be called
        when the status of the communications channel between the
        component manager and its component changes
    :param component_state_changed_callback: callback to be called
        when the component state changes

    :return: a component manager for the MCCS controller device
    """
    return ControllerComponentManager(
        subarray_fqdns,
        subrack_fqdns,
        station_fqdns,
        subarray_beam_fqdns,
        station_beam_fqdns,
        logger,
        max_workers,
        communication_state_changed_callback,
        component_state_changed_callback,
    )


@pytest.fixture()
def mock_controller_component_manager(
    subarray_fqdns: Iterable[str],
    subrack_fqdns: Iterable[str],
    station_fqdns: Iterable[str],
    subarray_beam_fqdns: Iterable[str],
    station_beam_fqdns: Iterable[str],
    logger: logging.Logger,
    max_workers: int,
    communication_state_changed_callback: MockCallable,
    component_state_changed_callback: MockCallableDeque,
) -> ControllerComponentManager:
    """
    Return a controller component manager in simulation mode.

    :param subarray_fqdns: FQDNS of all subarray devices
    :param subrack_fqdns: FQDNS of all subrack devices
    :param station_fqdns: FQDNS of all station devices
    :param subarray_beam_fqdns: FQDNS of all subarray beam devices
    :param station_beam_fqdns: FQDNS of all station beam devices
    :param logger: the logger to be used by this object.
    :param max_workers: nos of threads
    :param communication_state_changed_callback: callback to be called
        when the status of the communications channel between the
        component manager and its component changes
    :param component_state_changed_callback: callback to be called
        when the component state changes

    :return: a component manager for the MCCS controller device
    """
    return ControllerComponentManager(
        subarray_fqdns,
        subrack_fqdns,
        station_fqdns,
        subarray_beam_fqdns,
        station_beam_fqdns,
        logger,
        max_workers,
        communication_state_changed_callback,
        component_state_changed_callback,
    )


@pytest.fixture()
def mock_subarray_factory() -> MockSubarrayBuilder:
    """
    Fixture that provides a factory for mock subarrays.

    :return: a factory for mock subarray
    """
    return MockSubarrayBuilder()


@pytest.fixture()
def mock_station_factory() -> MockDeviceBuilder:
    """
    Fixture that provides a factory for mock stations.

    The only special behaviour of these mocks is they return a
    (result_code, message) tuple in response on/off calls.

    :return: a factory for device proxy mocks
    """
    builder = MockDeviceBuilder()
    builder.add_result_command("Off", result_code=ResultCode.QUEUED)
    builder.add_result_command("On", result_code=ResultCode.QUEUED)
    return builder


@pytest.fixture()
def mock_subrack_factory() -> MockDeviceBuilder:
    """
    Fixture that provides a factory for mock subracks.

    The only special behaviour of these mocks is they return a
    (result_code, message) tuple in response on/off calls.

    :return: a factory for device proxy mocks
    """
    builder = MockDeviceBuilder()
    builder.add_result_command("Off", result_code=ResultCode.QUEUED)
    builder.add_result_command("On", result_code=ResultCode.QUEUED)
    return builder


@pytest.fixture()
def initial_mocks(
    subarray_fqdns: list[str],
    mock_subarray_factory: Callable[[], unittest.mock.Mock],
    station_fqdns: list[str],
    mock_station_factory: Callable[[], unittest.mock.Mock],
    subrack_fqdns: list[str],
    mock_subrack_factory: Callable[[], unittest.mock.Mock],
) -> dict[str, unittest.mock.Mock]:
    """
    Return a specification of the mock devices to be set up in the Tango test harness.

    This is a pytest fixture that can be used to inject pre-build mock
    devices into the Tango test harness at specified FQDNs.

    :param subarray_fqdns: FQDNs of the subarrays for which mocks are to
        be set up
    :param mock_subarray_factory: a factory for mock subarray devices to
        be injected into the Tango test harness
    :param station_fqdns: FQDNs of the stations for which mocks are to
        be set up
    :param mock_station_factory: a factory for mock station devices to
        be injected into the Tango test harness
    :param subrack_fqdns: FQDNs of the subracks for which mocks are to
        be set up
    :param mock_subrack_factory: a factory for mock subrack devices to
        be injected into the Tango test harness

    :return: specification of the mock devices to be set up in the Tango
        test harness.
    """
    initial_mocks = {
        subarray_fqdn: mock_subarray_factory() for subarray_fqdn in subarray_fqdns
    }
    initial_mocks.update(
        {station_fqdn: mock_station_factory() for station_fqdn in station_fqdns}
    )
    initial_mocks.update(
        {subrack_fqdn: mock_subrack_factory() for subrack_fqdn in subrack_fqdns}
    )
    return initial_mocks


@pytest.fixture()
def subarray_proxies(
    subarray_fqdns: Iterable[str], logger: logging.Logger
) -> dict[str, MccsDeviceProxy]:
    """
    Return a dictioanry of proxies to subarray devices.

    :param subarray_fqdns: FQDNs of subarray in the MCCS subsystem.
    :param logger: the logger to be used by the proxies

    :return: a list of proxies to subarray devices
    """
    return {fqdn: MccsDeviceProxy(fqdn, logger) for fqdn in subarray_fqdns}


@pytest.fixture()
def station_proxies(
    station_fqdns: Iterable[str], logger: logging.Logger
) -> list[MccsDeviceProxy]:
    """
    Return a list of proxies to station devices.

    :param station_fqdns: FQDNs of stations in the MCCS subsystem.
    :param logger: the logger to be used by the proxies

    :return: a list of proxies to station devices
    """
    return [MccsDeviceProxy(fqdn, logger) for fqdn in station_fqdns]


@pytest.fixture()
def subrack_proxies(
    subrack_fqdns: Iterable[str], logger: logging.Logger
) -> list[MccsDeviceProxy]:
    """
    Return a list of proxies to subrack devices.

    :param subrack_fqdns: FQDNs of subracks in the MCCS subsystem.
    :param logger: the logger to be used by the proxies

    :return: a list of proxies to subrack devices
    """
    return [MccsDeviceProxy(fqdn, logger) for fqdn in subrack_fqdns]


@pytest.fixture
def unique_id() -> str:
    """
    Return a unique ID used to test Tango layer infrastructure.

    :return: a unique ID
    """
    return "a unique id"


@pytest.fixture()
def mock_component_manager(
    mocker: pytest_mock.mocker,  # type: ignore[valid-type]
    unique_id: str,
) -> unittest.mock.Mock:
    """
    Return a mock component manager.

    The mock component manager is a simple mock except for one bit of
    extra functionality: when we call start_communicating() on it, it
    makes calls to callbacks signaling that communication is established
    and the component is off.

    :param mocker: pytest wrapper for unittest.mockunittest.mock.Mock
    :param unique_id: a unique id used to check Tango layer functionality

    :return: a mock component manager
    """
    mock = mocker.Mock()  # type: ignore[attr-defined]
    mock.is_communicating = False
    mock.on.return_value = (TaskStatus.QUEUED, unique_id)
    mock.off.return_value = (TaskStatus.QUEUED, unique_id)
    mock.reset.return_value = (TaskStatus.QUEUED, unique_id)
    mock.standby.return_value = (TaskStatus.QUEUED, unique_id)

    def _start_communicating(mock: unittest.mock.Mock) -> None:
        mock.is_communicating = True
        mock._communication_state_changed_callback(CommunicationStatus.NOT_ESTABLISHED)
        mock._communication_state_changed_callback(CommunicationStatus.ESTABLISHED)
        mock._component_state_changed_callback({"power_state": PowerState.OFF})
        mock.is_communicating = True

    mock.start_communicating.side_effect = lambda: _start_communicating(mock)
    mock.return_value = unique_id, ResultCode.QUEUED
    return mock


@pytest.fixture()
def patched_controller_device_class(
    mock_component_manager: ControllerComponentManager,
) -> type[MccsController]:
    """
    Return a controller device that is patched with a mock component manager.

    :param mock_component_manager: the mock component manager with
        which to patch the device

    :return: a controller device that is patched with a mock component
        manager.
    """

    class PatchedMccsController(MccsController):
        """A controller device patched with a mock component manager."""

        def create_component_manager(
            self: PatchedMccsController,
        ) -> ControllerComponentManager:
            """
            Return a mock component manager instead of the usual one.

            :return: a mock component manager
            """
            self._communication_state: Optional[CommunicationStatus] = None
            # self._component_power_state: Optional[PowerState] = None

            mock_component_manager._communication_state_changed_callback = (
                self._communication_state_changed_callback
            )
            mock_component_manager._component_state_changed_callback = (
                self._component_state_changed_callback
            )
            return mock_component_manager

    return PatchedMccsController