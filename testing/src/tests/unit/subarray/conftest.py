# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module defined a pytest harness for testing the MCCS subarray module."""
from __future__ import annotations

import logging
import unittest.mock
from typing import Any, Callable

import pytest
import tango
from ska_tango_base.commands import ResultCode

from ska_low_mccs.subarray import SubarrayComponentManager, MccsSubarray
from ska_low_mccs.testing import TangoHarness
from ska_low_mccs.testing.mock import MockCallable, MockDeviceBuilder, MockCallableDeque


@pytest.fixture()
def component_state_changed_callback(
    mock_callback_deque_factory: Callable[['dict[str, Any]'], unittest.mock.Mock],
) -> unittest.mock.Mock:
    """
    Return a mock callback.

    To be called when the subarray's state changes.
    A side effect function is passed in to update the DUT's state

    :param mock_callback_deque_factory: fixture that provides a mock callback
        factory which uses a double-ended queue (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the subarray's state changes.
    """
    config = None
    return mock_callback_deque_factory(config)


# TODO: Delete fixtures from here to.....
@pytest.fixture()
def assign_completed_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> unittest.mock.Mock:
    """
    Return a mock callback.

    To be called when the subarray completes a resource assignment.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the subarray completes a
        resource assignment
    """
    return mock_callback_factory()


@pytest.fixture()
def release_completed_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> unittest.mock.Mock:
    """
    Return a mock callback to be called when the subarray completes a resource release.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the subarray completes a
        resource release
    """
    return mock_callback_factory()


@pytest.fixture()
def configure_completed_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> unittest.mock.Mock:
    """
    Return a mock callback to be called when the subarray completes a configuration.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the subarray completes a
        configuration
    """
    return mock_callback_factory()


@pytest.fixture()
def abort_completed_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> unittest.mock.Mock:
    """
    Return a mock callback to be called when the subarray completes an abort.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the subarray completes an
        abort
    """
    return mock_callback_factory()


@pytest.fixture()
def obsreset_completed_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> unittest.mock.Mock:
    """
    Return a mock callback.

    To be called when the subarray completes an observation
    reset.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the subarray completes an
        observation reset.
    """
    return mock_callback_factory()


@pytest.fixture()
def restart_completed_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> unittest.mock.Mock:
    """
    Return a mock callback to be called when the subarray completes a restart.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the subarray completes a
        restart.
    """
    return mock_callback_factory()


@pytest.fixture()
def resources_changed_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> unittest.mock.Mock:
    """
    Return a mock callback to be called when the subarray's resources change.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the subarray's resources
        change
    """
    return mock_callback_factory()


@pytest.fixture()
def configured_changed_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> unittest.mock.Mock:
    """
    Return a mock callback to be called when whether the subarray is configured changes.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when whether the subarray is
        configured changes
    """
    return mock_callback_factory()


@pytest.fixture()
def scanning_changed_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> unittest.mock.Mock:
    """
    Return a mock callback to be called when whether the subarray is scanning changes.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when whether the subarray is
        scanning changes
    """
    return mock_callback_factory()


@pytest.fixture()
def obs_fault_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> unittest.mock.Mock:
    """
    Return a mock callback to be called when an observation fault occurs or stops.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when whether the subarray is
        experiencing an observation fault changes
    """
    return mock_callback_factory()


@pytest.fixture()
def station_health_changed_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> unittest.mock.Mock:
    """
    Return a mock callback for a change in the health of one of the subarray's stations.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the component manager
        detects that one of its stations has changed health.
    """
    return mock_callback_factory()


@pytest.fixture()
def subarray_beam_health_changed_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> unittest.mock.Mock:
    """
    Return a mock callback for a change in the health of one of the subarray's beams.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the component manager
        detects that one of its subarray beams has changed health.
    """
    return mock_callback_factory()


@pytest.fixture()
def station_beam_health_changed_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> unittest.mock.Mock:
    """
    Return a mock callback for a change in the health of one of the subarray's beams.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the component manager
        detects that one of its station beams has changed health.
    """
    return mock_callback_factory()


# TODO: ... to here.


@pytest.fixture()
def subarray_component_manager(
    tango_harness: TangoHarness,
    logger: logging.Logger,
    max_workers: int,
    communication_status_changed_callback: MockCallable,
    component_state_changed_callback: MockCallableDeque,
) -> SubarrayComponentManager:
    """
    Return a subarray component manager.

    :param tango_harness: a test harness for MCCS tango devices
    :param logger: the logger to be used by this object.
    :param max_workers: Maximum number of workers in the thread pool.
    :param communication_status_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_state_changed_callback: callback to be called when the
        component's state changes.

    :return: a subarray component manager
    """
    return SubarrayComponentManager(
        logger,
        max_workers,
        communication_status_changed_callback,
        component_state_changed_callback,
    )


@pytest.fixture()
def station_off_id() -> int:
    """
    Return the id of a mock station that is powered off.

    :return: the id of a mock station that is powered off.
    """
    return 1


@pytest.fixture()
def station_on_id() -> int:
    """
    Return the id of a mock station that is powered on.

    :return: the id of a mock station that is powered on.
    """
    return 2


@pytest.fixture()
def station_off_fqdn(station_off_id: int) -> str:
    """
    Return the FQDN of a mock station that is powered off.

    :param station_off_id: the ID number of a station that is powered
        off.

    :return: the FQDN for a mock station that is powered off.
    """
    return f"low-mccs/station/{station_off_id:03d}"


@pytest.fixture()
def station_on_fqdn(station_on_id: int) -> str:
    """
    Return the FQDN of a mock station that is powered on.

    :param station_on_id: the ID number of a station that is powered on.

    :return: the FQDN for a mock station that is powered on.
    """
    return f"low-mccs/station/{station_on_id:03d}"


@pytest.fixture()
def subarray_beam_off_id() -> int:
    """
    Return the id of a mock subarray beam that is powered off.

    :return: the id of a mock subarray beam that is powered off.
    """
    return 2


@pytest.fixture()
def subarray_beam_on_id() -> int:
    """
    Return the id of a mock subarray beam that is powered on.

    :return: the id of a mock subarray beam that is powered on.
    """
    return 3


@pytest.fixture()
def subarray_beam_off_fqdn(subarray_beam_off_id: int) -> str:
    """
    Fixture that provides the FQDN for a mock subarray beam that is powered off.

    :param subarray_beam_off_id: the id number of a subarray beam that
        is powered off.

    :return: the FQDN for a mock subarray beam that is powered off.
    """
    return f"low-mccs/subarraybeam/{subarray_beam_off_id:02d}"


@pytest.fixture()
def subarray_beam_on_fqdn(subarray_beam_on_id: int) -> str:
    """
    Fixture that provides the FQDN for a mock subarray beam that is powered on.

    :param subarray_beam_on_id: the id number of a subarray beam that is
        powered on

    :return: the FQDN for a mock subarray beam that is powered on.
    """
    return f"low-mccs/subarraybeam/{subarray_beam_on_id:02d}"


@pytest.fixture()
def station_beam_off_id() -> int:
    """
    Return the id of a mock station beam that is powered off.

    :return: the id of a mock station beam that is powered off.
    """
    return 2


@pytest.fixture()
def station_beam_on_id() -> int:
    """
    Return the id of a mock station beam that is powered on.

    :return: the id of a mock station beam that is powered on.
    """
    return 3


@pytest.fixture()
def station_beam_off_fqdn(station_beam_off_id: int) -> str:
    """
    Fixture that provides the FQDN for a mock station beam that is powered off.

    :param station_beam_off_id: the id number of a station beam that
        is powered off.

    :return: the FQDN for a mock station beam that is powered off.
    """
    return f"low-mccs/beam/{station_beam_off_id:02d}"


@pytest.fixture()
def station_beam_on_fqdn(station_beam_on_id: int) -> str:
    """
    Fixture that provides the FQDN for a mock station beam that is powered on.

    :param station_beam_on_id: the id number of a station beam that is
        powered on

    :return: the FQDN for a mock station beam that is powered on.
    """
    return f"low-mccs/beam/{station_beam_on_id:02d}"


@pytest.fixture()
def channel_blocks() -> list[int]:
    """
    Return a list of channel blocks.

    :return: a list of channel blocks.
    """
    return [1]


@pytest.fixture()
def mock_station_off() -> unittest.mock.Mock:
    """
    Return a mock station device that is powered off.

    :return: a mock station device that is powered off
    """
    builder = MockDeviceBuilder()
    builder.set_state(tango.DevState.OFF)
    builder.add_result_command("Configure", result_code=ResultCode.QUEUED)
    return builder()


@pytest.fixture()
def mock_station_on() -> unittest.mock.Mock:
    """
    Return a mock station device that is powered on.

    :return: a mock station device that is powered on
    """
    builder = MockDeviceBuilder()
    builder.set_state(tango.DevState.ON)
    builder.add_result_command("Configure", result_code=ResultCode.QUEUED)
    return builder()


@pytest.fixture()
def mock_subarray_beam_off() -> unittest.mock.Mock:
    """
    Return a mock subarray beam device that is powered off.

    :return: a mock subarray beam device that is powered off.
    """
    builder = MockDeviceBuilder()
    builder.set_state(tango.DevState.OFF)
    builder.add_result_command("Configure", result_code=ResultCode.QUEUED)
    return builder()


@pytest.fixture()
def mock_subarray_beam_on() -> unittest.mock.Mock:
    """
    Return a mock subarray beam device that is powered on.

    :return: a mock subarray beam device that is powered on.
    """
    builder = MockDeviceBuilder()
    builder.set_state(tango.DevState.ON)
    builder.add_result_command("Configure", result_code=ResultCode.QUEUED)
    builder.add_result_command("Scan", result_code=ResultCode.QUEUED)
    return builder()


@pytest.fixture()
def mock_station_beam_off() -> unittest.mock.Mock:
    """
    Return a mock station beam device that is powered off.

    :return: a mock station beam device that is powered off.
    """
    builder = MockDeviceBuilder()
    builder.set_state(tango.DevState.OFF)
    builder.add_result_command("Configure", result_code=ResultCode.QUEUED)
    return builder()


@pytest.fixture()
def mock_station_beam_on() -> unittest.mock.Mock:
    """
    Return a mock station beam device that is powered on.

    :return: a mock station beam device that is powered on.
    """
    builder = MockDeviceBuilder()
    builder.set_state(tango.DevState.ON)
    builder.add_result_command("Configure", result_code=ResultCode.QUEUED)
    return builder()


@pytest.fixture()
def initial_mocks(
    station_off_fqdn: str,
    mock_station_off: unittest.mock.Mock,
    station_on_fqdn: str,
    mock_station_on: unittest.mock.Mock,
    subarray_beam_off_fqdn: str,
    mock_subarray_beam_off: unittest.mock.Mock,
    subarray_beam_on_fqdn: str,
    mock_subarray_beam_on: unittest.mock.Mock,
    station_beam_off_fqdn: str,
    mock_station_beam_off: unittest.mock.Mock,
    station_beam_on_fqdn: str,
    mock_station_beam_on: unittest.mock.Mock,
) -> dict[str, unittest.mock.Mock]:
    """
    Return a dictionary of device proxy mocks to pre-register.

    The default fixture is overridden here to provide mock stations and
    subarray beams in both off and on states. That way, instead of
    turning the subarray on and off, we can drive it into the desired
    state by assigning the corresponding resources.

    :param station_off_fqdn: the FQDN of a station that is powered off.
    :param mock_station_off: a mock station that is powered off.
    :param station_on_fqdn: the FQDN of a station that is powered on.
    :param mock_station_on: a mock station that is powered on.
    :param subarray_beam_off_fqdn: the FQDN of a subarray beam that is
        powered off.
    :param mock_subarray_beam_off: a mock subarray beam that is powered
        off.
    :param subarray_beam_on_fqdn: the FQDN of a subarray beam that is
        powered on.
    :param mock_subarray_beam_on: a mock subarray beam that is powered
        on.
    :param station_beam_off_fqdn: the FQDN of a station beam that is
        powered off.
    :param mock_station_beam_off: a mock station beam that is powered
        off.
    :param station_beam_on_fqdn: the FQDN of a station beam that is
        powered on.
    :param mock_station_beam_on: a mock station beam that is powered
        on.

    :return: a dictionary of device proxy mocks to pre-register.
    """
    return {
        station_off_fqdn: mock_station_off,
        station_on_fqdn: mock_station_on,
        subarray_beam_off_fqdn: mock_subarray_beam_off,
        subarray_beam_on_fqdn: mock_subarray_beam_on,
        station_beam_off_fqdn: mock_station_beam_off,
        station_beam_on_fqdn: mock_station_beam_on,
    }


@pytest.fixture()
def scan_id() -> int:
    """
    Return a scan id for use in testing.

    :return: a scan id for use in testing.
    """
    return 1


@pytest.fixture()
def start_time() -> float:
    """
    Return a scan start time for use in testing.

    :return: a scan start time for use in testing.
    """
    return 0.0


@pytest.fixture()
def max_workers() -> int:
    """
    Return a value for max_workers for use in testing.

    :return: maximum number of workers in thread pool for use in testing.
    """
    return 2
