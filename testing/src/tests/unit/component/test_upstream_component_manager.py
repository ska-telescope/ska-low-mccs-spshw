# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains tests of the object_component_manager module."""
from __future__ import annotations

import logging
import time

import pytest
from ska_tango_base.control_model import CommunicationStatus, PowerState

from ska_low_mccs.component import PowerSupplyProxySimulator
from ska_low_mccs.testing.mock import MockCallable, MockCallableDeque


class TestPowerSupplyProxySimulator:
    """Tests of the PowerSupplyProxySimulator class."""

    @pytest.fixture()
    def component_manager(
        self: TestPowerSupplyProxySimulator,
        logger: logging.Logger,
        max_workers: int,
        communication_state_changed_callback: MockCallable,
        component_state_changed_callback: MockCallableDeque,
    ) -> PowerSupplyProxySimulator:
        """
        Return a component manager for the component object.

        :param logger: a logger for the component manager to use
        :param max_workers: nos of worker threads
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be
            called when the component state changes

        :return: a fake upstream power supply proxy.
        """
        return PowerSupplyProxySimulator(
            logger,
            max_workers,
            communication_state_changed_callback,
            component_state_changed_callback,
        )

    def test_communication(
        self: TestPowerSupplyProxySimulator,
        component_manager: PowerSupplyProxySimulator,
        communication_state_changed_callback: MockCallable,
        component_state_changed_callback: MockCallableDeque,
    ) -> None:
        """
        Test communication from the component manager to its component.

        :param component_manager: a component manager for the component object.
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be called
            when the state of the component changes
        """
        assert component_manager.communication_state == CommunicationStatus.DISABLED
        component_manager.start_communicating()
        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.ESTABLISHED
        )
        assert component_manager.communication_state == CommunicationStatus.ESTABLISHED

        component_manager.stop_communicating()
        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.DISABLED
        )
        time.sleep(0.1)
        expected_arguments = {"power_state": PowerState.OFF}
        component_state_changed_callback.assert_in_deque(expected_arguments)

        assert component_manager.communication_state == CommunicationStatus.DISABLED

    def test_communication_failure(
        self: TestPowerSupplyProxySimulator,
        component_manager: PowerSupplyProxySimulator,
        communication_state_changed_callback: MockCallable,
    ) -> None:
        """
        Test handling of communication failure between component manager and component.

        :param component_manager: a component manager for the component object.
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        """
        assert component_manager.communication_state == CommunicationStatus.DISABLED
        component_manager.simulate_communication_failure(True)

        with pytest.raises(ConnectionError, match="Failed to connect"):
            component_manager.start_communicating()
        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        assert (
            component_manager.communication_state == CommunicationStatus.NOT_ESTABLISHED
        )

        component_manager.stop_communicating()
        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.DISABLED
        )
        assert component_manager.communication_state == CommunicationStatus.DISABLED

        component_manager.simulate_communication_failure(False)
        component_manager.start_communicating()
        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.ESTABLISHED
        )
        assert component_manager.communication_state == CommunicationStatus.ESTABLISHED

        component_manager.simulate_communication_failure(True)
        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        assert (
            component_manager.communication_state == CommunicationStatus.NOT_ESTABLISHED
        )

        with pytest.raises(ConnectionError, match="Failed to connect"):
            component_manager.start_communicating()

        component_manager.stop_communicating()
        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.DISABLED
        )
        assert component_manager.communication_state == CommunicationStatus.DISABLED

    @pytest.mark.parametrize(
        ("command", "expected_supplied_power_state"),
        [("power_on", PowerState.ON), ("power_off", PowerState.OFF)],
    )
    def test_command(
        self: TestPowerSupplyProxySimulator,
        component_manager: PowerSupplyProxySimulator,
        command: str,
        expected_supplied_power_state: PowerState,
    ) -> None:
        """
        Test the component manager can execute basic commands on its component.

        :param component_manager: a component manager for the component
            object.
        :param command: name of the command to be executed.
        :param expected_supplied_power_state: the expected supplied power
            state after executing the command
        """
        assert component_manager._supplied_power_state is None
        with pytest.raises(
            ConnectionError,
            match="Communication with component is not established",
        ):
            getattr(component_manager, command)()
        time.sleep(0.1)
        assert component_manager._supplied_power_state is None

        component_manager.start_communicating()
        time.sleep(0.1)
        assert component_manager.supplied_power_state == PowerState.OFF

        getattr(component_manager, command)()
        time.sleep(0.1)
        assert component_manager._supplied_power_state == expected_supplied_power_state
