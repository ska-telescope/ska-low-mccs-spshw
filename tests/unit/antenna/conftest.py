# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module defined a pytest test harness for testing the MCCS antenna module."""
from __future__ import annotations

import logging
import unittest.mock
from typing import Any, Callable, Optional

import pytest
import pytest_mock
import tango
from ska_control_model import CommunicationStatus, PowerState, ResultCode, TaskStatus
from ska_low_mccs_common import MccsDeviceProxy
from ska_low_mccs_common.testing import TangoHarness
from ska_low_mccs_common.testing.mock import (
    MockCallable,
    MockCallableDeque,
    MockDeviceBuilder,
)
from tango.server import command

from ska_low_mccs import MccsAntenna
from ska_low_mccs.antenna import AntennaComponentManager
from ska_low_mccs.antenna.antenna_component_manager import _ApiuProxy, _TileProxy


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


@pytest.fixture(name="mock_component_manager")
def mock_component_manager_fixture(
    mocker: pytest_mock.MockerFixture,
) -> unittest.mock.Mock:
    """
    Return a mock to be used as a component manager for the antenna device.

    :param mocker: fixture that wraps the :py:mod:`unittest.mock`
        module

    :return: a mock to be used as a component manager for the antenna
        device.
    """
    mock_component_manager = mocker.Mock()
    mock_component_manager.apply_pointing = MockLongRunningCommand()
    mock_component_manager.configure = MockLongRunningCommand()
    return mock_component_manager


@pytest.fixture(name="patched_antenna_class")
def patched_antenna_class_fixture(
    mock_component_manager: unittest.mock.Mock,
) -> type[MccsAntenna]:
    """
    Return a antenna device class that has been patched for testing.

    :param mock_component_manager: the mock component manage to patch
        into this antenna.

    :return: a antenna device class that has been patched for testing.
    """

    class PatchedAntenna(MccsAntenna):
        """A antenna class that has had its component manager mocked out for testing."""

        def create_component_manager(
            self: PatchedAntenna,
        ) -> unittest.mock.Mock:
            """
            Return a mock component manager instead of the usual one.

            :return: a mock component manager
            """
            return mock_component_manager

    return PatchedAntenna


@pytest.fixture(name="apiu_fqdn")
def apiu_fqdn_fixture() -> str:
    """
    Return the FQDN of the antenna's APIU device.

    :return: the FQDN of the antenna's APIU device.
    """
    return "low-mccs/apiu/001"


@pytest.fixture(name="apiu_antenna_id")
def apiu_antenna_id_fixture() -> int:
    """
    Return the id of the antenna in the APIU.

    :return: the id of the antenna in the APIU.
    """
    # TODO: This must match the LogicalApiuAntennaId property of the
    # antenna device. We should refactor the harness so that we can pull
    # it straight from the device configuration.
    return 1


@pytest.fixture(name="tile_fqdn")
def tile_fqdn_fixture() -> str:
    """
    Return the FQDN of the antenna's tile device.

    :return: the FQDN of the antenna's tile device.
    """
    return "low-mccs/tile/0001"


@pytest.fixture(name="tile_antenna_id")
def tile_antenna_id_fixture() -> int:
    """
    Return the id of the antenna in the tile.

    :return: the id of the antenna in the tile.
    """
    return 1


@pytest.fixture(name="max_workers")
def max_workers_fixture() -> int:
    """
    Return the number of maximum worker threads.

    :return: the number of maximum worker threads.
    """
    return 1


@pytest.fixture(name="component_state_changed_callback")
def component_state_changed_callback_fixture(
    mock_callback_deque_factory: Callable[[], unittest.mock.Mock],
) -> unittest.mock.Mock:
    """
    Return a mock callback for antenna state change.

    :param mock_callback_deque_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the component manager
        detects that the state of its component has changed.
    """
    return mock_callback_deque_factory()


# @pytest.fixture()
# def communication_state_changed_callback(
#     mock_callback_deque_factory: Callable[[], unittest.mock.Mock],
# ) -> unittest.mock.Mock:
#     """
#     Return a mock callback for communication change.

#     :param mock_callback_deque_factory: fixture that provides a mock callback
#         factory (i.e. an object that returns mock callbacks when
#         called).

#     :return: a mock callback to be called when the communication status
#         of a component manager changed.
#     """
#     return mock_callback_deque_factory()


# pylint: disable=too-many-arguments
@pytest.fixture(name="antenna_apiu_proxy")
def antenna_apiu_proxy_fixture(
    tango_harness: TangoHarness,
    apiu_fqdn: str,
    apiu_antenna_id: int,
    logger: logging.Logger,
    max_workers: int,
    communication_state_changed_callback: MockCallable,
    component_state_changed_callback: MockCallable,
) -> _ApiuProxy:
    """
    Return an antenna APIU proxy for testing.

    This is a pytest fixture.

    :param tango_harness: a test harness for MCCS tango devices
    :param apiu_fqdn: FQDN of the antenna's APIU device
    :param apiu_antenna_id: the id of the antenna in the APIU device
    :param logger: a loger for the antenna component manager to use
    :param max_workers: the maximum worker threads available
    :param communication_state_changed_callback: callback to be called
        when the status of the communications channel between the
        component manager and its component changes
    :param component_state_changed_callback: callback to be called
        when the component state changes

    :return: an antenna APIU proxy
    """
    return _ApiuProxy(
        apiu_fqdn,
        apiu_antenna_id,
        logger,
        max_workers,
        communication_state_changed_callback,
        component_state_changed_callback,
    )


# pylint: disable=too-many-arguments
@pytest.fixture(name="antenna_tile_proxy")
def antenna_tile_proxy_fixture(
    tango_harness: TangoHarness,
    tile_fqdn: str,
    tile_antenna_id: int,
    logger: logging.Logger,
    max_workers: int,
    communication_state_changed_callback: MockCallableDeque,
    component_state_changed_callback: Callable[[Any], None],
) -> _TileProxy:
    """
    Return an antenna tile proxy for testing.

    This is a pytest fixture.

    :param tango_harness: a test harness for MCCS tango devices
    :param tile_fqdn: FQDN of the antenna's tile device
    :param tile_antenna_id: the id of the antenna in the tile device
    :param logger: a loger for the antenna component manager to use
    :param max_workers: the maximum worker threads available
    :param communication_state_changed_callback: callback to be called
        when the status of the communications channel between the
        component manager and its component changes
    :param component_state_changed_callback: callback to be called
        when the component state changes

    :return: an antenna tile proxy for testing
    """
    return _TileProxy(
        tile_fqdn,
        tile_antenna_id,
        logger,
        max_workers,
        communication_state_changed_callback,
        component_state_changed_callback,
    )


# pylint: disable=too-many-arguments
@pytest.fixture(name="antenna_component_manager")
def antenna_component_manager_fixture(
    tango_harness: TangoHarness,
    apiu_fqdn: str,
    apiu_antenna_id: int,
    tile_fqdn: str,
    tile_antenna_id: int,
    logger: logging.Logger,
    max_workers: int,
    communication_state_changed_callback: Callable[[CommunicationStatus], None],
    component_state_changed_callback: Callable[[dict[str, Any], Optional[str]], None],
) -> AntennaComponentManager:
    """
    Return an antenna component manager.

    :param tango_harness: a test harness for MCCS tango devices
    :param apiu_fqdn: FQDN of the antenna's APIU device
    :param apiu_antenna_id: the id of the antenna in the APIU device
    :param tile_fqdn: FQDN of the antenna's tile device
    :param tile_antenna_id: the id of the antenna in the tile device
    :param logger: a loger for the antenna component manager to use
    :param max_workers: the maximum worker threads available
    :param communication_state_changed_callback: callback to be called
        when the status of the communications channel between the
        component manager and its component changes
    :param component_state_changed_callback: callback to be called
        when the component state changes

    :return: an antenna component manager
    """
    return AntennaComponentManager(
        apiu_fqdn,
        apiu_antenna_id,
        tile_fqdn,
        tile_antenna_id,
        logger,
        max_workers,
        communication_state_changed_callback,
        component_state_changed_callback,
    )


@pytest.fixture(name="initial_antenna_power_mode")
def initial_antenna_power_mode_fixture() -> int:
    """
    Return the initial power mode of the antenna.

    :return: the initial power mode of the antenna.
    """
    return PowerState.OFF


@pytest.fixture(name="initial_are_antennas_on")
def initial_are_antennas_on_fixture(
    apiu_antenna_id: int,
    initial_antenna_power_mode: PowerState,
) -> list[bool]:
    """
    Return whether each antenna is initially on in the APIU.

    The antenna under test will be set off or on in accordance with the
    initial_antenna_power_mode argument. All other antennas will
    initially be off.

    :param apiu_antenna_id: the id of the antenna under test.
    :param initial_antenna_power_mode: whether the antenna under test is
        initially on.

    :return: whether each antenna is initially on in the APIU.
    """
    are_antennas_on = [False] * apiu_antenna_id
    are_antennas_on[apiu_antenna_id - 1] = initial_antenna_power_mode == PowerState.ON
    return are_antennas_on


@pytest.fixture(name="mock_apiu")
def mock_apiu_fixture(initial_are_antennas_on: list[bool]) -> unittest.mock.Mock:
    """
    Fixture that provides a mock MccsAPIU device.

    :param initial_are_antennas_on: whether each antenna is initially on
        in the APIU

    :return: a mock MccsAPIU device.
    """
    builder = MockDeviceBuilder()
    builder.set_state(tango.DevState.OFF)
    builder.add_command("IsAntennaOn", False)
    builder.add_result_command("On", ResultCode.OK)
    builder.add_result_command("PowerUpAntenna", ResultCode.OK)
    builder.add_result_command("PowerDownAntenna", ResultCode.OK)
    builder.add_attribute("areAntennasOn", initial_are_antennas_on)
    return builder()


@pytest.fixture(name="mock_tile")
def mock_tile_fixture() -> unittest.mock.Mock:
    """
    Fixture that provides a mock MccsTile device.

    This has no tile-specific functionality at present.

    :return: a mock Mccs device.
    """
    builder = MockDeviceBuilder()
    return builder()


@pytest.fixture(name="initial_mocks")
def initial_mocks_fixture(
    apiu_fqdn: str,
    mock_apiu: unittest.mock.Mock,
    tile_fqdn: str,
    mock_tile: unittest.mock.Mock,
) -> dict[str, unittest.mock.Mock]:
    """
    Return a dictionary of pre-registered device proxy mocks.

    The default fixture is overridden here to provide an MccsAPIU mock
    and an MccsTile mock..

    :param apiu_fqdn: FQDN of the APIU device
    :param mock_apiu: the mock APIU device to be provided when a device
        proxy to the APIU FQDN is requested.
    :param tile_fqdn: FQDN of the Tile device
    :param mock_tile: the mock Tile device to be provided when a device
        proxy to the Tile FQDN is requested.

    :return: a dictionary of mocks, keyed by FQDN
    """
    return {
        apiu_fqdn: mock_apiu,
        tile_fqdn: mock_tile,
    }


@pytest.fixture(name="mock_apiu_device_proxy")
def mock_apiu_device_proxy_fixture(
    apiu_fqdn: str, logger: logging.Logger
) -> MccsDeviceProxy:
    """
    Return a mock device proxy to an APIU device.

    :param apiu_fqdn: FQDN of the APIU device.
    :param logger: a logger for the device proxy to use.

    :return: a mock device proxy to an APIU device.
    """
    return MccsDeviceProxy(apiu_fqdn, logger)


@pytest.fixture(name="patched_antenna_device_class")
def patched_antenna_device_class_fixture(
    initial_are_antennas_on: list[bool],
) -> type[MccsAntenna]:
    """
    Return an antenna device class, patched with extra methods for testing.

    :param initial_are_antennas_on: whether each antenna is initially on
        in the APIU
    :return: an antenna device class, patched with extra methods for testing.
    """

    class PatchedAntennaDevice(MccsAntenna):
        """
        MccsAntenna patched with extra commands for testing purposes.

        The extra commands allow us to mock the receipt of a state change
        event from its APIU device.

        These methods are provided here because they are quite
        implementation dependent. If an implementation change breaks
        this, we only want to fix it in this one place.
        """

        @command()
        def MockAntennaPoweredOn(self: PatchedAntennaDevice) -> None:
            """Mock the Antenna being turned on."""
            are_antennas_on = list(initial_are_antennas_on)
            are_antennas_on[self.LogicalApiuAntennaId - 1] = True
            self.component_manager._apiu_proxy._antenna_power_state_changed(
                "areAntennasOn",
                are_antennas_on,
                tango.AttrQuality.ATTR_VALID,
            )

        @command()
        def MockApiuOff(self: PatchedAntennaDevice) -> None:
            """
            Mock the APIU being turned off.

            Make the antenna device think it has received a state change
            event from its APIU indicating that the APIU is now OFF.
            """
            self.component_manager._apiu_proxy._device_state_changed(
                "state", tango.DevState.OFF, tango.AttrQuality.ATTR_VALID
            )

        @command()
        def MockApiuOn(self: PatchedAntennaDevice) -> None:
            """
            Mock the APIU being turned on.

            Make the antenna device think it has received a state change
            event from its APIU indicating that the APIU is now ON.
            """
            self.component_manager._apiu_proxy._device_state_changed(
                "state", tango.DevState.ON, tango.AttrQuality.ATTR_VALID
            )

    return PatchedAntennaDevice