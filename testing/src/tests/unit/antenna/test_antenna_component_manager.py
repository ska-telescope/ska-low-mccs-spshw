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
"""This module contains unit tests of the MCCS antenna component manager module."""
from __future__ import annotations

import time
import unittest

import pytest
import tango

from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import PowerMode

from ska_low_mccs.antenna import AntennaComponentManager
from ska_low_mccs.antenna.antenna_component_manager import (
    _ApiuProxy,
    _TileProxy,
)
from ska_low_mccs.component import CommunicationStatus

from ska_low_mccs.testing.mock import MockCallable


class TestAntennaApiuProxy:
    """Tests of the _ApiuProxy class."""

    def test_communication(
        self: TestAntennaApiuProxy,
        antenna_apiu_proxy: _ApiuProxy,
        communication_status_changed_callback: MockCallable,
    ) -> None:
        """
        Test this antenna APIU proxy's communication with the antenna.

        :param antenna_apiu_proxy: a proxy to the antenna's APIU device.
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        """
        assert antenna_apiu_proxy.communication_status == CommunicationStatus.DISABLED
        antenna_apiu_proxy.start_communicating()

        # communication status is NOT_ESTABLISHED because establishing
        # a connection to MccsAPIU has been enqueued but not yet run
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )

        # communication status is ESTABLISHED because MccsAPIU's state
        # is OFF, from which we can infer that the antenna is powered
        # off.
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.ESTABLISHED
        )

        antenna_apiu_proxy.stop_communicating()
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.DISABLED
        )

    def test_power_command(
        self: TestAntennaApiuProxy,
        antenna_apiu_proxy: _ApiuProxy,
        mock_apiu_device_proxy: unittest.mock.Mock,
        initial_are_antennas_on: list[bool],
        apiu_antenna_id: int,
    ) -> None:
        """
        Test that this antenna APIU proxy can control the power mode of the antenna.

        :param antenna_apiu_proxy: a proxy to the antenna's APIU device.
        :param mock_apiu_device_proxy: a mock device proxy to an APIU
            device.
        :param initial_are_antennas_on: whether each antenna is
            initially on in the APIU
        :param apiu_antenna_id: the id of the antenna in its APIU
            device.
        """
        with pytest.raises(
            ConnectionError,
            match="Communication with component is not established",
        ):
            antenna_apiu_proxy.on()

        assert antenna_apiu_proxy.power_mode is None

        antenna_apiu_proxy.start_communicating()
        time.sleep(0.1)

        # communication status is ESTABLISHED because MccsAPIU's state
        # is OFF, from which it can be inferred that the antenna itself
        # is powered off
        assert antenna_apiu_proxy.power_mode == PowerMode.OFF
        assert antenna_apiu_proxy.supplied_power_mode == PowerMode.OFF

        antenna_apiu_proxy.on()
        mock_apiu_device_proxy.On.assert_next_call()

        # Fake an event that tells this proxy that the APIU has been turned on.
        antenna_apiu_proxy._device_state_changed(
            "state", tango.DevState.ON, tango.AttrQuality.ATTR_VALID
        )
        assert antenna_apiu_proxy.power_mode == PowerMode.ON

        assert antenna_apiu_proxy.supplied_power_mode == PowerMode.OFF

        time.sleep(0.1)
        assert antenna_apiu_proxy.power_on() == ResultCode.QUEUED
        mock_apiu_device_proxy.PowerUpAntenna.assert_next_call(apiu_antenna_id)

        # The antenna power mode won't update until an event confirms that the antenna is on.
        assert antenna_apiu_proxy.supplied_power_mode == PowerMode.OFF

        # Fake an event that tells this proxy that the antenna is now on as requested
        are_antennas_on = initial_are_antennas_on
        are_antennas_on[apiu_antenna_id - 1] = True
        antenna_apiu_proxy._antenna_power_mode_changed(
            "areAntennasOn", are_antennas_on, tango.AttrQuality.ATTR_VALID
        )
        assert antenna_apiu_proxy.supplied_power_mode == PowerMode.ON

        assert antenna_apiu_proxy.power_on() is None
        mock_apiu_device_proxy.PowerUpAntenna.assert_not_called()
        assert antenna_apiu_proxy.supplied_power_mode == PowerMode.ON

        assert antenna_apiu_proxy.power_off() == ResultCode.QUEUED
        mock_apiu_device_proxy.PowerDownAntenna.assert_next_call(apiu_antenna_id)

        # The power mode won't update until an event confirms that the antenna is on.
        assert antenna_apiu_proxy.supplied_power_mode == PowerMode.ON

        # Fake an event that tells this proxy that the antenna is now off as requested
        are_antennas_on[apiu_antenna_id - 1] = False
        antenna_apiu_proxy._antenna_power_mode_changed(
            "areAntennasOn", are_antennas_on, tango.AttrQuality.ATTR_VALID
        )
        assert antenna_apiu_proxy.supplied_power_mode == PowerMode.OFF

        assert antenna_apiu_proxy.power_off() is None
        mock_apiu_device_proxy.PowerDownAntenna.assert_not_called()
        assert antenna_apiu_proxy.supplied_power_mode == PowerMode.OFF

    def test_reset(self: TestAntennaApiuProxy, antenna_apiu_proxy: _ApiuProxy) -> None:
        """
        Test that this antenna APIU proxy refuses to try to reset the antenna.

        :param antenna_apiu_proxy: a proxy to the antenna's APIU device.
        """
        with pytest.raises(
            NotImplementedError,
            match="Antenna cannot be reset.",
        ):
            antenna_apiu_proxy.reset()


class TestAntennaTileProxy:
    """Tests of the _TileProxy class."""

    def test_communication(
        self: TestAntennaTileProxy,
        antenna_tile_proxy: _TileProxy,
        communication_status_changed_callback: MockCallable,
    ) -> None:
        """
        Test that this proxy refuses to try to invoke power commands on the antenna.

        :param antenna_tile_proxy: a proxy to the antenna's tile device.
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        """
        assert antenna_tile_proxy.communication_status == CommunicationStatus.DISABLED
        antenna_tile_proxy.start_communicating()
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.ESTABLISHED
        )

        antenna_tile_proxy.stop_communicating()
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.DISABLED
        )

    @pytest.mark.parametrize("command", ["on", "standby", "off"])
    def test_power_command(
        self: TestAntennaTileProxy, antenna_tile_proxy: _TileProxy, command: str
    ) -> None:
        """
        Test that this proxy will refuse to try to run power commands on the antenna.

        :param antenna_tile_proxy: a proxy to the antenna's tile device.
        :param command: name of the power command to run.
        """
        with pytest.raises(
            NotImplementedError,
            match="Antenna power mode is not controlled via Tile device.",
        ):
            getattr(antenna_tile_proxy, command)()

    def test_reset(self: TestAntennaTileProxy, antenna_tile_proxy: _TileProxy) -> None:
        """
        Test that this antenna tile proxy refuses to try to reset the antenna.

        :param antenna_tile_proxy: a proxy to the antenna's tile device.
        """
        with pytest.raises(
            NotImplementedError,
            match="Antenna hardware is not resettable.",
        ):
            antenna_tile_proxy.reset()


class TestAntennaComponentManager:
    """Tests of the AntennaComponentManager."""

    def test_communication(
        self: TestAntennaComponentManager,
        antenna_component_manager: AntennaComponentManager,
        communication_status_changed_callback: MockCallable,
    ) -> None:
        """
        Test communication between the antenna component manager and its antenna.

        :param antenna_component_manager: the antenna component manager
            under test
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        """
        assert (
            antenna_component_manager.communication_status
            == CommunicationStatus.DISABLED
        )

        antenna_component_manager.start_communicating()

        # communication status is NOT_ESTABLISHED because the task of
        # connecting to devices has been enqueued rather than directly
        # run.
        assert (
            antenna_component_manager.communication_status
            == CommunicationStatus.NOT_ESTABLISHED
        )
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.ESTABLISHED
        )
        assert (
            antenna_component_manager.communication_status
            == CommunicationStatus.ESTABLISHED
        )

        antenna_component_manager.stop_communicating()
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.DISABLED
        )
        assert (
            antenna_component_manager.communication_status
            == CommunicationStatus.DISABLED
        )

    def test_power_commands(
        self: TestAntennaComponentManager,
        antenna_component_manager: AntennaComponentManager,
        mock_apiu_device_proxy: unittest.mock.Mock,
        initial_are_antennas_on: list[bool],
        apiu_antenna_id: int,
    ) -> None:
        """
        Test the power commands.

        :param antenna_component_manager: the antenna component manager
            under test
        :param mock_apiu_device_proxy: a mock proxy to the antenna's
            APIU device
        :param initial_are_antennas_on: whether each antenna is
            initially on in the APIU
        :param apiu_antenna_id: the id of the antenna in its APIU
            device.
        """
        assert antenna_component_manager.power_mode is None

        antenna_component_manager.start_communicating()
        time.sleep(0.1)
        assert antenna_component_manager.power_mode == PowerMode.OFF  # APIU is off

        antenna_component_manager._apiu_proxy._device_state_changed(
            "state", tango.DevState.ON, tango.AttrQuality.ATTR_VALID
        )
        time.sleep(0.1)

        assert antenna_component_manager.power_mode == PowerMode.OFF
        # APIU is on but antenna is off

        assert antenna_component_manager.on() == ResultCode.QUEUED
        mock_apiu_device_proxy.PowerUpAntenna.assert_next_call(apiu_antenna_id)

        # The power mode won't update until an event confirms that the antenna is on.
        assert antenna_component_manager.power_mode == PowerMode.OFF

        # Fake an event that tells the APIU proxy that the antenna is now on
        are_antennas_on = list(initial_are_antennas_on)
        are_antennas_on[apiu_antenna_id - 1] = True
        antenna_component_manager._apiu_proxy._antenna_power_mode_changed(
            "areAntennasOn", are_antennas_on, tango.AttrQuality.ATTR_VALID
        )
        assert antenna_component_manager.power_mode == PowerMode.ON

        assert antenna_component_manager.on() is None
        mock_apiu_device_proxy.PowerUpAntenna.assert_not_called()
        assert antenna_component_manager.power_mode == PowerMode.ON

        assert antenna_component_manager.off() == ResultCode.QUEUED
        mock_apiu_device_proxy.PowerDownAntenna.assert_next_call(apiu_antenna_id)

        # The power mode won't update until an event confirms that the antenna is on.
        assert antenna_component_manager.power_mode == PowerMode.ON

        # Fake an event that tells this proxy that the antenna is now off as requested
        are_antennas_on[apiu_antenna_id - 1] = False
        antenna_component_manager._apiu_proxy._antenna_power_mode_changed(
            "areAntennasOn", are_antennas_on, tango.AttrQuality.ATTR_VALID
        )
        assert antenna_component_manager.power_mode == PowerMode.OFF

        assert antenna_component_manager.off() is None
        mock_apiu_device_proxy.PowerDownAntenna.assert_not_called()
        assert antenna_component_manager.power_mode == PowerMode.OFF

        with pytest.raises(
            NotImplementedError,
            match="Antenna has no standby mode.",
        ):
            antenna_component_manager.standby()

    def test_eventual_consistency_of_on_command(
        self: TestAntennaComponentManager,
        antenna_component_manager: AntennaComponentManager,
        communication_status_changed_callback: MockCallable,
        apiu_antenna_id: int,
        mock_apiu_device_proxy: unittest.mock.Mock,
    ) -> None:
        """
        Test that eventual consistency semantics of the on command.

        This test tells the antenna component manager to turn on, in
        circumstances in which it cannot possibly do so (the APIU is
        turned off). Instead of failing, it waits to the APIU to turn
        on, and then executes the on command.

        :param antenna_component_manager: the antenna component manager
            under test
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param apiu_antenna_id: This antenna's position in its APIU
        :param mock_apiu_device_proxy: a mock device proxy to a
            APIU device.
        """
        antenna_component_manager.start_communicating()

        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.ESTABLISHED
        )

        assert antenna_component_manager.on() == ResultCode.QUEUED

        # no action taken initially because the APIU is switched off
        mock_apiu_device_proxy.PowerUpAntenna.assert_not_called()

        antenna_component_manager._apiu_power_mode_changed(PowerMode.ON)

        # now that the antenna has been notified that the APIU is on,
        # it tells it to turn on its antenna
        mock_apiu_device_proxy.PowerUpAntenna.assert_next_call(apiu_antenna_id)

    def test_reset(
        self: TestAntennaComponentManager,
        antenna_component_manager: AntennaComponentManager,
    ) -> None:
        """
        Test that the antenna component manager refused to try to reset the antenna.

        :param antenna_component_manager: the antenna component manager
            under test
        """
        with pytest.raises(
            NotImplementedError,
            match="Antenna cannot be reset.",
        ):
            antenna_component_manager.reset()
