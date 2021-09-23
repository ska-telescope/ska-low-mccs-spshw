#########################################################################
# !/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
#########################################################################
"""This module defined a pytest harness for testing the MCCS station beam module."""
from __future__ import annotations

import logging
from typing import Callable
import unittest.mock

import pytest
import tango

from ska_low_mccs.station_beam import StationBeamComponentManager

from ska_low_mccs.testing import TangoHarness
from ska_low_mccs.testing.mock import MockCallable, MockDeviceBuilder


@pytest.fixture()
def component_device_health_changed_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> unittest.mock.Mock:
    """
    Return a mock callback for a change in the health of the component device.

    (i.e. the station).

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the component manager
        detects that component device health has changed.
    """
    return mock_callback_factory()


@pytest.fixture()
def component_device_fault_changed_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> unittest.mock.Mock:
    """
    Return a mock callback for a change in the fault state of the component device.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the component manager
        detects that component device health has changed.
    """
    return mock_callback_factory()


@pytest.fixture()
def component_is_beam_locked_changed_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> Callable[[bool], None]:
    """
    Return a mock callback for a change in whether the station beam is locked.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the component manager
        detects that whether the beam is locked has changed
    """
    return mock_callback_factory()


@pytest.fixture()
def beam_id() -> int:
    """
    Return a beam id for the station beam under test.

    :return: a beam id for the station beam under test.
    """
    return 1


@pytest.fixture()
def station_beam_component_manager(
    tango_harness: TangoHarness,
    beam_id: int,
    logger: logging.Logger,
    communication_status_changed_callback: MockCallable,
    message_queue_size_callback: Callable[[int], None],
    component_is_beam_locked_changed_callback: MockCallable,
    component_device_health_changed_callback: MockCallable,
    component_device_fault_changed_callback: MockCallable,
) -> StationBeamComponentManager:
    """
    Return a station beam component manager.

    :param tango_harness: a test harness for MCCS tango devices
    :param beam_id: a beam id for the station beam under test.
    :param logger: the logger to be used by this object.
    :param communication_status_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param message_queue_size_callback: callback to be called when the
        size of the message queue changes.
    :param component_is_beam_locked_changed_callback: a callback to be
        called when whether the beam is locked changes.
    :param component_device_health_changed_callback: a callback to be
        called when the health of the component device (i.e. the
        station) changes
    :param component_device_fault_changed_callback: a callback to be
        called when the fault state of the component device (i.e. the
        station) changes

    :return: a station beam component manager
    """
    return StationBeamComponentManager(
        beam_id,
        logger,
        communication_status_changed_callback,
        message_queue_size_callback,
        component_is_beam_locked_changed_callback,
        component_device_health_changed_callback,
        component_device_fault_changed_callback,
    )


@pytest.fixture()
def mock_station_off_fqdn() -> str:
    """
    Fixture that provides the FQDN for a mock station that is in state OFF.

    :return: the FQDN for a mock station that is in state OFF.
    """
    return "mock/station/off"


@pytest.fixture()
def mock_station_off() -> unittest.mock.Mock:
    """
    Fixture that provides a mock MccsStation device that is in OFF state.

    :return: a mock MccsStation device that is in OFF state.
    """
    builder = MockDeviceBuilder()
    builder.set_state(tango.DevState.OFF)
    return builder()


@pytest.fixture()
def mock_station_on_fqdn() -> str:
    """
    Fixture that provides the FQDN for a mock station that is in state ON.

    :return: the FQDN for a mock station that is in state ON.
    """
    return "mock/station/on"


@pytest.fixture()
def mock_station_on() -> unittest.mock.Mock:
    """
    Fixture that provides a mock MccsStation device that is in ON state.

    :return: a mock MccsStation device that is in ON state.
    """
    builder = MockDeviceBuilder()
    builder.set_state(tango.DevState.ON)
    return builder()


@pytest.fixture()
def initial_mocks(
    mock_station_off_fqdn: str,
    mock_station_off: unittest.mock.Mock,
    mock_station_on_fqdn: str,
    mock_station_on: unittest.mock.Mock,
) -> dict[str, unittest.mock.Mock]:
    """
    Return a dictionary of pre-registered device proxy mocks.

    The default fixture is overridden here to provide two mock
    MccsStation devices: one in OFF state, the other in ON state.

    :param mock_station_off_fqdn: FQDN of the station device that is in
        OFF state.
    :param mock_station_off: a station device that is in OFF state.
    :param mock_station_on_fqdn: FQDN of the station device that is in
        ON state.
    :param mock_station_on: a station device that is in ON state.

    :return: a dictionary of mocks, keyed by FQDN
    """
    return {
        mock_station_off_fqdn: mock_station_off,
        mock_station_on_fqdn: mock_station_on,
    }
