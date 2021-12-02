"""This module contains tests of the object_component_manager module."""
from __future__ import annotations

import logging
import unittest.mock

import pytest
import pytest_mock

from ska_low_mccs.component import (
    CommunicationStatus,
    ObjectComponentManager,
)
from ska_low_mccs.testing.mock import MockCallable
from ska_low_mccs.testing.mock import MockChangeEventCallback


class TestObjectComponentManager:
    """Tests of the ObjectComponentManager class."""

    @pytest.fixture()
    def component(
        self: TestObjectComponentManager,
        mocker: pytest_mock.mocker,
    ) -> unittest.mock.Mock:
        """
        Return a mock to use as a component object.

        :param mocker: fixture that returns a mock.

        :return: a mock to use as a component object.
        """
        return mocker.Mock()

    @pytest.fixture()
    def component_manager(
        self: TestObjectComponentManager,
        component: unittest.mock.Mock,
        logger: logging.Logger,
        lrc_result_changed_callback: MockChangeEventCallback,
        communication_status_changed_callback: MockCallable,
        component_power_mode_changed_callback: MockCallable,
        component_fault_callback: MockCallable,
    ) -> ObjectComponentManager:
        """
        Return a component manager for the component object.

        :param component: the component to be managed by the component
            manager.
        :param logger: a logger for the component manager to use
        :param lrc_result_changed_callback: a callback to
            be used to subscribe to device LRC result changes
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_power_mode_changed_callback: callback to be
            called when the component power mode changes
        :param component_fault_callback: callback to be called when the
            component faults (or stops faulting)

        :return: a component manager for the component object.
        """
        return ObjectComponentManager(
            component,
            logger,
            lrc_result_changed_callback,
            communication_status_changed_callback,
            component_power_mode_changed_callback,
            component_fault_callback,
        )

    def test_communication(
        self: TestObjectComponentManager,
        component_manager: ObjectComponentManager,
        communication_status_changed_callback: MockCallable,
    ) -> None:
        """
        Test communication from the component manager to its component.

        :param component_manager: a component manager for the component object.
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        """
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
        self: TestObjectComponentManager,
        component_manager: ObjectComponentManager,
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

    @pytest.mark.parametrize("command", ["on", "standby", "off", "reset"])
    def test_command(
        self: TestObjectComponentManager,
        component_manager: ObjectComponentManager,
        component: unittest.mock.Mock,
        command: str,
    ) -> None:
        """
        Test the component manager can execute basic commands on its component.

        :param component_manager: a component manager for the component object.
        :param component: a mock component for the component manager to manage.
        :param command: name of the command to be executed.
        """
        setattr(component, command, MockCallable())

        with pytest.raises(
            ConnectionError, match="Communication with component is not established"
        ):
            getattr(component_manager, command)()
        getattr(component, command).assert_not_called()

        component_manager.start_communicating()

        getattr(component_manager, command)()
        getattr(component, command).assert_next_call()
