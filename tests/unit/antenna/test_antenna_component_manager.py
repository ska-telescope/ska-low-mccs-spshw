# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains unit tests of the MCCS antenna component manager module."""
from __future__ import annotations

import time
import unittest

import pytest
import tango
from ska_control_model import CommunicationStatus, PowerState, ResultCode, TaskStatus
from ska_low_mccs_common.testing.mock import MockCallable, MockCallableDeque

from ska_low_mccs.antenna import AntennaComponentManager
from ska_low_mccs.antenna.antenna_component_manager import _ApiuProxy, _TileProxy


class TestAntennaApiuProxy:
    """Tests of the _ApiuProxy class."""

    def test_communication(
        self: TestAntennaApiuProxy,
        antenna_apiu_proxy: _ApiuProxy,
        communication_state_changed_callback: MockCallable,
    ) -> None:
        """
        Test this antenna APIU proxy's communication with the antenna.

        :param antenna_apiu_proxy: a proxy to the antenna's APIU device.
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        """
        assert antenna_apiu_proxy.communication_state == CommunicationStatus.DISABLED
        antenna_apiu_proxy.start_communicating()

        # communication status is NOT_ESTABLISHED because establishing
        # a connection to MccsAPIU has been enqueued but not yet run
        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )

        # communication status is ESTABLISHED because MccsAPIU's state
        # is OFF, from which we can infer that the antenna is powered
        # off.
        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.ESTABLISHED
        )

        antenna_apiu_proxy.stop_communicating()
        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.DISABLED
        )

    def test_power_command(
        self: TestAntennaApiuProxy,
        antenna_apiu_proxy: _ApiuProxy,
        mock_apiu_device_proxy: unittest.mock.Mock,
        initial_are_antennas_on: list[bool],
        apiu_antenna_id: int,
        component_state_changed_callback: MockCallableDeque,
    ) -> None:
        """
        Test that this antenna APIU proxy can control the power mode of the antenna.

        :param antenna_apiu_proxy: a proxy to the antenna's APIU device.
        :param mock_apiu_device_proxy: a mock device proxy to an APIU
            device.
        :param initial_are_antennas_on: whether each antenna is
            initially on in the APIU
        :param apiu_antenna_id: the id of the antenna in its APIU
            device
        :param component_state_changed_callback: callback to be called
            when the state of the component changes.
        """
        with pytest.raises(
            ConnectionError,
            match="Communication is not being attempted so cannot be established.",
        ):
            antenna_apiu_proxy.on()

        antenna_apiu_proxy.start_communicating()
        time.sleep(0.1)

        component_state_changed_callback.assert_next_call_with_keys(
            {"power_state": PowerState.OFF}
        )
        antenna_apiu_proxy.power_state = PowerState.OFF
        component_state_changed_callback.assert_next_call_with_keys(
            {"power_state": PowerState.OFF}
        )

        # communication status is ESTABLISHED because MccsAPIU's state
        # is OFF, from which it can be inferred that the antenna itself
        # is powered off
        assert antenna_apiu_proxy.power_state == PowerState.OFF
        assert antenna_apiu_proxy.supplied_power_state == PowerState.OFF

        assert antenna_apiu_proxy.on() == (TaskStatus.QUEUED, "Task queued")
        mock_apiu_device_proxy.On.assert_next_call()

        # Fake an event that tells this proxy that the APIU has been turned on.
        antenna_apiu_proxy._device_state_changed(
            "state", tango.DevState.ON, tango.AttrQuality.ATTR_VALID
        )
        component_state_changed_callback.assert_next_call_with_keys(
            {"power_state": PowerState.ON}
        )

        antenna_apiu_proxy.power_state = PowerState.ON

        assert antenna_apiu_proxy.power_state == PowerState.ON
        assert antenna_apiu_proxy.supplied_power_state == PowerState.OFF

        time.sleep(0.1)
        assert antenna_apiu_proxy.power_on() == ResultCode.OK
        mock_apiu_device_proxy.PowerUpAntenna.assert_next_call(apiu_antenna_id)

        # The antenna power mode won't update until an event confirms that
        # the antenna is on.
        assert antenna_apiu_proxy.supplied_power_state == PowerState.OFF

        # Fake an event that tells this proxy that the antenna is now on as requested
        are_antennas_on = initial_are_antennas_on
        are_antennas_on[apiu_antenna_id - 1] = True
        antenna_apiu_proxy._antenna_power_state_changed(
            "areAntennasOn", are_antennas_on, tango.AttrQuality.ATTR_VALID
        )
        assert antenna_apiu_proxy.supplied_power_state == PowerState.ON

        assert antenna_apiu_proxy.power_on() is None
        mock_apiu_device_proxy.PowerUpAntenna.assert_not_called()
        assert antenna_apiu_proxy.supplied_power_state == PowerState.ON

        assert antenna_apiu_proxy.power_off() == ResultCode.OK
        mock_apiu_device_proxy.PowerDownAntenna.assert_next_call(apiu_antenna_id)

        # The power mode won't update until an event confirms that the antenna is on.
        assert antenna_apiu_proxy.supplied_power_state == PowerState.ON

        # Fake an event that tells this proxy that the antenna is now off as requested
        are_antennas_on[apiu_antenna_id - 1] = False
        antenna_apiu_proxy._antenna_power_state_changed(
            "areAntennasOn", are_antennas_on, tango.AttrQuality.ATTR_VALID
        )
        assert antenna_apiu_proxy.supplied_power_state == PowerState.OFF

        assert antenna_apiu_proxy.power_off() is None
        mock_apiu_device_proxy.PowerDownAntenna.assert_not_called()
        assert antenna_apiu_proxy.supplied_power_state == PowerState.OFF

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
        communication_state_changed_callback: MockCallableDeque,
    ) -> None:
        """
        Test that this proxy refuses to try to invoke power commands on the antenna.

        :param antenna_tile_proxy: a proxy to the antenna's tile device.
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        """
        assert antenna_tile_proxy.communication_state == CommunicationStatus.DISABLED
        antenna_tile_proxy.start_communicating()
        time.sleep(0.1)
        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.ESTABLISHED
        )

        antenna_tile_proxy.stop_communicating()
        time.sleep(0.1)
        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.DISABLED
        )

    @pytest.mark.parametrize("command", ["on", "standby", "off"])
    def test_power_command(
        self: TestAntennaTileProxy,
        antenna_tile_proxy: _TileProxy,
        command: str,
    ) -> None:
        """
        Test that this proxy will refuse to try to run power commands on the antenna.

        :param antenna_tile_proxy: a proxy to the antenna's tile device.
        :param command: name of the power command to run.
        """
        with pytest.raises(
            NotImplementedError,
            match="Antenna power state is not controlled via Tile device.",
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
        communication_state_changed_callback: MockCallable,
    ) -> None:
        """
        Test communication between the antenna component manager and its antenna.

        :param antenna_component_manager: the antenna component manager
            under test
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        """
        assert (
            antenna_component_manager.communication_state
            == CommunicationStatus.DISABLED
        )

        antenna_component_manager.start_communicating()

        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.ESTABLISHED
        )
        assert (
            antenna_component_manager.communication_state
            == CommunicationStatus.ESTABLISHED
        )

        antenna_component_manager.stop_communicating()
        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.DISABLED
        )
        assert (
            antenna_component_manager.communication_state
            == CommunicationStatus.DISABLED
        )

    def test_power_commands(
        self: TestAntennaComponentManager,
        antenna_component_manager: AntennaComponentManager,
        mock_apiu_device_proxy: unittest.mock.Mock,
        initial_are_antennas_on: list[bool],
        apiu_antenna_id: int,
        component_state_changed_callback: MockCallableDeque,
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
            device
        :param component_state_changed_callback: callback to be called
            when the state of the component changes.
        """
        antenna_component_manager.start_communicating()
        time.sleep(0.1)

        component_state_changed_callback.assert_in_deque(
            {"power_state": PowerState.OFF}
        )
        antenna_component_manager.power_state = PowerState.OFF

        assert antenna_component_manager.power_state == PowerState.OFF  # APIU is off

        antenna_component_manager._apiu_proxy._device_state_changed(
            "state", tango.DevState.ON, tango.AttrQuality.ATTR_VALID
        )
        time.sleep(0.2)
        antenna_component_manager._apiu_power_state_changed(PowerState.ON)

        assert antenna_component_manager.power_state == PowerState.OFF
        # APIU is on but antenna is off

        task_callback_on = MockCallable()
        assert antenna_component_manager.on(task_callback_on) == (
            TaskStatus.QUEUED,
            "Task queued",
        )

        # antenna_component_manager.power_state = PowerState.ON
        mock_apiu_device_proxy.PowerUpAntenna.assert_next_call(apiu_antenna_id)

        # The power state won't update until an event confirms that the antenna is on.
        assert antenna_component_manager.power_state == PowerState.OFF

        # Fake an event that tells the APIU proxy that the antenna is now on
        are_antennas_on = list(initial_are_antennas_on)
        are_antennas_on[apiu_antenna_id - 1] = True
        antenna_component_manager._apiu_proxy._antenna_power_state_changed(
            "areAntennasOn", are_antennas_on, tango.AttrQuality.ATTR_VALID
        )
        component_state_changed_callback.assert_last_call(
            {"power_state": PowerState.ON},
            fqdn=antenna_component_manager._apiu_proxy._fqdn,
        )
        antenna_component_manager.power_state = PowerState.ON

        assert antenna_component_manager.power_state == PowerState.ON

        assert antenna_component_manager.on() == (TaskStatus.QUEUED, "Task queued")
        mock_apiu_device_proxy.PowerUpAntenna.assert_not_called()
        assert antenna_component_manager.power_state == PowerState.ON

        assert antenna_component_manager.off() == (TaskStatus.QUEUED, "Task queued")
        mock_apiu_device_proxy.PowerDownAntenna.assert_next_call(apiu_antenna_id)

        # The power state won't update until an event confirms that the antenna is on.
        assert antenna_component_manager.power_state == PowerState.ON

        # Fake an event that tells this proxy that the antenna is now off as requested
        are_antennas_on[apiu_antenna_id - 1] = False
        antenna_component_manager._apiu_proxy._antenna_power_state_changed(
            "areAntennasOn", are_antennas_on, tango.AttrQuality.ATTR_VALID
        )
        component_state_changed_callback.assert_last_call(
            {"power_state": PowerState.OFF},
            fqdn=antenna_component_manager._apiu_proxy._fqdn,
        )
        antenna_component_manager.power_state = PowerState.OFF
        assert antenna_component_manager.power_state == PowerState.OFF

        assert antenna_component_manager.off() == (TaskStatus.QUEUED, "Task queued")
        mock_apiu_device_proxy.PowerDownAntenna.assert_not_called()
        assert antenna_component_manager.power_state == PowerState.OFF

        with pytest.raises(
            NotImplementedError,
            match="Antenna has no standby state.",
        ):
            antenna_component_manager.standby()

    def test_eventual_consistency_of_on_command(
        self: TestAntennaComponentManager,
        antenna_component_manager: AntennaComponentManager,
        communication_state_changed_callback: MockCallable,
        component_state_changed_callback: MockCallableDeque,
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
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be called
            when the state of the component changes
        :param apiu_antenna_id: This antenna's position in its APIU
        :param mock_apiu_device_proxy: a mock device proxy to a
            APIU device.
        """
        antenna_component_manager.start_communicating()
        time.sleep(0.1)

        # Check for power state off callback, then update component manager accordingly
        component_state_changed_callback.assert_in_deque(
            {"power_state": PowerState.OFF}
        )
        antenna_component_manager.power_state = PowerState.OFF

        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.ESTABLISHED
        )

        on_command_callback = MockCallable()
        task_status, message = antenna_component_manager.on(on_command_callback)
        assert (task_status, message) == (TaskStatus.QUEUED, "Task queued")

        # time.sleep(0.5)

        # no action taken initially because the APIU is switched off
        mock_apiu_device_proxy.PowerUpAntenna.assert_not_called()

        antenna_component_manager._apiu_power_state_changed(PowerState.ON)

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

    def test_power_commands1(
        self: TestAntennaComponentManager,
        antenna_component_manager: AntennaComponentManager,
        mock_apiu_device_proxy: unittest.mock.Mock,
        initial_are_antennas_on: list[bool],
        apiu_antenna_id: int,
        component_state_changed_callback: MockCallableDeque,
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
            device
        :param component_state_changed_callback: callback to be called
            when the state of the component changes.
        """
        antenna_component_manager.start_communicating()
        time.sleep(0.1)

        component_state_changed_callback.assert_in_deque(
            {"power_state": PowerState.OFF}
        )

        antenna_component_manager._antenna_power_state_changed(PowerState.UNKNOWN)
        assert antenna_component_manager.power_state == PowerState.UNKNOWN

        antenna_component_manager._apiu_component_fault_changed(True)
        assert antenna_component_manager._faulty

        antenna_component_manager._apiu_component_fault_changed(False)
        assert not antenna_component_manager._faulty

        antenna_component_manager._tile_component_fault_changed(True)
        assert antenna_component_manager._faulty

        assert antenna_component_manager._faulty
        with pytest.raises(
            ValueError,
            match="unknown fqdn 'wrong_fqdn', should be None or belong to tile or apiu",
        ):
            antenna_component_manager.set_power_state(PowerState.ON, "wrong_fqdn")

        # case where we try to turn on with no proxy present.

        antenna_component_manager._apiu_proxy._proxy = None
        antenna_component_manager._apiu_power_state = PowerState.ON
        antenna_component_manager.power_state = PowerState.OFF
        time.sleep(2)

        task_callback_on = MockCallable()
        antenna_component_manager.on(task_callback_on)
        time.sleep(0.1)
        _, kwargs = task_callback_on.get_next_call()
        assert kwargs["status"] == TaskStatus.QUEUED

        time.sleep(0.1)
        _, kwargs = task_callback_on.get_next_call()
        assert kwargs["status"] == TaskStatus.IN_PROGRESS

        time.sleep(0.1)
        _, kwargs = task_callback_on.get_next_call()
        assert kwargs["status"] == TaskStatus.FAILED
        assert kwargs["result"] == "Exception: "

        time.sleep(0.1)
        _, kwargs = task_callback_on.get_next_call()
        assert kwargs["status"] == TaskStatus.COMPLETED

    def test_configure(
        self: TestAntennaComponentManager,
        antenna_component_manager: AntennaComponentManager,
        communication_state_changed_callback: MockCallable,
        component_state_changed_callback: MockCallableDeque,
    ) -> None:
        """
        Test tile attribute assignment.

        Specifically, test that when the antenna component manager
        established communication with its tiles, it write its antenna
        id and a unique logical tile id to each one.

        :param antenna_component_manager: the antenna component manager
            under test.
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be called
            when the antenna state changes
        """
        antenna_component_manager.start_communicating()
        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.ESTABLISHED
        )
        time.sleep(0.1)

        mock_task_callback = MockCallable()

        antenna_component_manager._configure(
            {
                "antenna": {"xDisplacement": 1.0, "yDisplacement": 1.0},
                "tile": {"fixed_delays": (1, 2)},
            },
            mock_task_callback,
        )
        mock_task_callback.assert_next_call(status=TaskStatus.IN_PROGRESS)
        mock_task_callback.assert_next_call(
            status=TaskStatus.COMPLETED, result="Configure command has completed"
        )

        component_state_changed_callback.assert_next_call_with_keys(
            {"configuration_changed": {"xDisplacement": 1.0, "yDisplacement": 1.0}}
        )