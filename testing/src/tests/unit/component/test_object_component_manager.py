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
import unittest.mock

import pytest
import pytest_mock
from ska_tango_base.control_model import CommunicationStatus

from ska_low_mccs.component import ObjectComponentManager
from ska_low_mccs.testing.mock import MockCallable


class TestObjectComponentManager:
    """Tests of the ObjectComponentManager class."""

    @pytest.fixture()
    def component(
        self: TestObjectComponentManager,
        mocker: pytest_mock.MockerFixture,
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
        max_workers: int,
        communication_state_changed_callback: MockCallable,
        component_state_changed_callback: MockCallable,
    ) -> ObjectComponentManager:
        """
        Return a component manager for the component object.

        :param component: the component to be managed by the component
            manager.
        :param logger: a logger for the component manager to use
        :param max_workers: nos of threads
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be
            called when the component state changes

        :return: a component manager for the component object.
        """
        return ObjectComponentManager(
            component,
            logger,
            max_workers,
            communication_state_changed_callback,
            component_state_changed_callback,
        )

    def test_communication(
        self: TestObjectComponentManager,
        component_manager: ObjectComponentManager,
        communication_state_changed_callback: MockCallable,
    ) -> None:
        """
        Test communication from the component manager to its component.

        :param component_manager: a component manager for the component object.
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        """
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
        assert component_manager.communication_state == CommunicationStatus.DISABLED

    def test_communication_failure(
        self: TestObjectComponentManager,
        component_manager: ObjectComponentManager,
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
            component_manager.communication_state
            == CommunicationStatus.NOT_ESTABLISHED
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
            component_manager.communication_state
            == CommunicationStatus.NOT_ESTABLISHED
        )

        with pytest.raises(ConnectionError, match="Failed to connect"):
            component_manager.start_communicating()

        component_manager.stop_communicating()
        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.DISABLED
        )
        assert component_manager.communication_state == CommunicationStatus.DISABLED

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
            ConnectionError,
            match="Communication with component is not established",
        ):
            getattr(component_manager, command)()
        getattr(component, command).assert_not_called()

        component_manager.start_communicating()

        getattr(component_manager, command)()
        attr = getattr(component, command)
        attr.assert_next_call(None)
