"""This module contains tests of the object_component_manager module."""
from __future__ import annotations

import logging
import time

import pytest

from ska_tango_base.control_model import PowerMode

from ska_low_mccs.component import (
    CommunicationStatus,
    MessageQueue,
    PowerSupplyProxySimulator,
)

from ska_low_mccs.testing.mock import MockCallable


class TestPowerSupplyProxySimulator:
    """Tests of the PowerSupplyProxySimulator class."""

    @pytest.fixture()
    def component_manager(
        self: TestPowerSupplyProxySimulator,
        message_queue: MessageQueue,
        logger: logging.Logger,
        communication_status_changed_callback: MockCallable,
        component_power_mode_changed_callback: MockCallable,
    ) -> PowerSupplyProxySimulator:
        """
        Return a component manager for the component object.

        :param message_queue: the message queue to be used by this
            component manager
        :param logger: a logger for the component manager to use
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_power_mode_changed_callback: callback to be
            called when the component power mode changes

        :return: a fake upstream power supply proxy.
        """
        return PowerSupplyProxySimulator(
            message_queue,
            logger,
            communication_status_changed_callback,
            component_power_mode_changed_callback,
        )

    def test_communication(
        self: TestPowerSupplyProxySimulator,
        component_manager: PowerSupplyProxySimulator,
        communication_status_changed_callback: MockCallable,
    ) -> None:
        """
        Test communication from the component manager to its component.

        :param component_manager: a component manager for the component object.
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        """
        assert component_manager.communication_status == CommunicationStatus.DISABLED
        component_manager.start_communicating()
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.ESTABLISHED
        )
        assert component_manager.communication_status == CommunicationStatus.ESTABLISHED

        component_manager.stop_communicating()
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.DISABLED
        )
        assert component_manager.communication_status == CommunicationStatus.DISABLED

    def test_communication_failure(
        self: TestPowerSupplyProxySimulator,
        component_manager: PowerSupplyProxySimulator,
        communication_status_changed_callback: MockCallable,
    ) -> None:
        """
        Test handling of communication failure between component manager and component.

        :param component_manager: a component manager for the component object.
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        """
        assert component_manager.communication_status == CommunicationStatus.DISABLED
        component_manager.simulate_communication_failure(True)

        with pytest.raises(ConnectionError, match="Failed to connect"):
            component_manager.start_communicating()
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        assert (
            component_manager.communication_status
            == CommunicationStatus.NOT_ESTABLISHED
        )

        component_manager.stop_communicating()
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.DISABLED
        )
        assert component_manager.communication_status == CommunicationStatus.DISABLED

        component_manager.simulate_communication_failure(False)
        component_manager.start_communicating()
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.ESTABLISHED
        )
        assert component_manager.communication_status == CommunicationStatus.ESTABLISHED

        component_manager.simulate_communication_failure(True)
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        assert (
            component_manager.communication_status
            == CommunicationStatus.NOT_ESTABLISHED
        )

        with pytest.raises(ConnectionError, match="Failed to connect"):
            component_manager.start_communicating()

        component_manager.stop_communicating()
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.DISABLED
        )
        assert component_manager.communication_status == CommunicationStatus.DISABLED

    @pytest.mark.parametrize(
        ("command", "expected_supplied_power_mode"),
        [("power_on", PowerMode.ON), ("power_off", PowerMode.OFF)],
    )
    def test_command(
        self: TestPowerSupplyProxySimulator,
        component_manager: PowerSupplyProxySimulator,
        command: str,
        expected_supplied_power_mode: PowerMode,
    ) -> None:
        """
        Test the component manager can execute basic commands on its component.

        :param component_manager: a component manager for the component
            object.
        :param command: name of the command to be executed.
        :param expected_supplied_power_mode: the expected supplied power
            mode after executing the command
        """
        assert component_manager.supplied_power_mode is None

        with pytest.raises(ConnectionError, match="Not connected"):
            getattr(component_manager, command)()
        time.sleep(0.1)
        assert component_manager.supplied_power_mode is None

        component_manager.start_communicating()
        time.sleep(0.1)
        assert component_manager.supplied_power_mode == PowerMode.OFF

        getattr(component_manager, command)()
        time.sleep(0.1)
        assert component_manager.supplied_power_mode == expected_supplied_power_mode
