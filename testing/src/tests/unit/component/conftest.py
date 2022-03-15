# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains pytest test harness for tests of the MCCS component module."""
from __future__ import annotations

import logging
import unittest.mock
from typing import Callable

import pytest
import pytest_mock
from ska_tango_base.commands import ResultCode

from ska_low_mccs import MccsDeviceProxy
from ska_low_mccs.testing.mock import MockDeviceBuilder


@pytest.fixture()
def health_changed_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> unittest.mock.Mock:
    """
    Return a mock callback for a device component manager.

    To call when the health state of its device changes.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback for a device component manager to call when
        the health state of its device changes.
    """
    return mock_callback_factory()


@pytest.fixture()
def mock_factory() -> MockDeviceBuilder:
    """
    Fixture that provides a mock factory for device proxy mocks.

    This default factory provides mocks with some basic behaviours of
    base devices. i.e. on, off, standby, etc commands.

    :return: a factory for device proxy mocks
    """
    builder = MockDeviceBuilder()
    builder.add_result_command("Off", result_code=ResultCode.OK)
    builder.add_result_command("Standby", result_code=ResultCode.OK)
    builder.add_result_command("On", result_code=ResultCode.OK)
    builder.add_result_command("Reset", result_code=ResultCode.OK)
    return builder


@pytest.fixture()
def fqdn() -> str:
    """
    Return an FQDN for a mock device.

    :return: an FQDN for a mock device.
    """
    return "mock/mock/1"


@pytest.fixture()
def mock_proxy(fqdn: str, logger: logging.Logger) -> MccsDeviceProxy:
    """
    Return a mock proxy to the provided FQDN.

    :param fqdn: the FQDN of the device.
    :param logger: a logger for the device proxy.

    :return: a mock proxy to the device with the FQDN provided.
    """
    return MccsDeviceProxy(fqdn, logger)


@pytest.fixture()
def pool_member_communication_status_changed_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> unittest.mock.Mock:
    """
    Return a mock callback for a pool member communication status change.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the communication status
        of a member of pool component manager changes.
    """
    return mock_callback_factory()


@pytest.fixture()
def pool_member_component_power_mode_changed_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> unittest.mock.Mock:
    """
    Return a mock callback for pool member component power mode change.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when a member of a pool
        component manager detects that the power mode of its component
        has changed.
    """
    return mock_callback_factory()


@pytest.fixture()
def pool_member_component_fault_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> unittest.mock.Mock:
    """
    Return a mock callback for pool member component fault change.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when a member of a pool
        component manager detects that its component has faulted.
    """
    return mock_callback_factory()


@pytest.fixture()
def mock_component_manager_factory(
    mocker: pytest_mock.MockerFixture,
) -> Callable[[], unittest.mock.Mock]:
    """
    Return a factory that can be called to provide a mock component manager.

    :param mocker: fixture that wraps unittest.mock

    :return: a mock component manager factory
    """
    return mocker.Mock
