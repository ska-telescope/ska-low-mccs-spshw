########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
########################################################################
"""This module contains the tests for the ska_low_mccs.health module."""
from __future__ import annotations

from typing import Callable, Optional
import unittest.mock

import pytest

from ska_tango_base.control_model import HealthState

from ska_low_mccs.cluster_manager import ClusterHealthModel

from ska_low_mccs.testing.mock import MockCallable


class TestClusterHealthModel:
    """Tests of the ClusterHealthModel class."""

    @pytest.fixture()
    def health_changed_callback(
        self: TestClusterHealthModel,
        mock_callback_factory: Callable[[], unittest.mock.Mock],
    ) -> Callable[[HealthState], None]:
        """
        Return a mock callback to be called when the health model's health changes.

        :param mock_callback_factory: fixture that provides a mock
            callback factory (i.e. an object that returns mock callbacks
            when called).

        :return: a mock callback to be called when the health model
            under test decides that its health has changed.
        """
        return mock_callback_factory()

    @pytest.fixture()
    def cluster_health_model(
        self: TestClusterHealthModel,
        health_changed_callback: MockCallable,
    ) -> ClusterHealthModel:
        """
        Return a cluster health model for testing.

        :param health_changed_callback: a mock callback to be called
            when the health model under test decides that its health has
            changed.

        :return: a cluster health model for testing.
        """
        return ClusterHealthModel(health_changed_callback)

    def test(
        self: TestClusterHealthModel,
        cluster_health_model: ClusterHealthModel,
        health_changed_callback: MockCallable,
    ) -> None:
        """
        Test that health state reflects component health.

        :param cluster_health_model: the cluster health model under
            test.
        :param health_changed_callback: a mock callback to be called
            when the health model under test decides that its health has
            changed.
        """

        def assert_health_changed(health_state: Optional[HealthState]) -> None:
            if health_state is None:
                health_changed_callback.assert_not_called()
            else:
                assert cluster_health_model.health_state == health_state
                health_changed_callback.assert_next_call(health_state)

        # starting state
        assert_health_changed(HealthState.UNKNOWN)

        cluster_health_model.is_communicating(True)
        assert_health_changed(None)

        cluster_health_model.component_fault(True)
        assert_health_changed(HealthState.FAILED)

        cluster_health_model.component_fault(False)
        assert_health_changed(HealthState.UNKNOWN)

        cluster_health_model.shadow_master_pool_node_health_changed([True, True])
        assert_health_changed(HealthState.OK)

        cluster_health_model.is_communicating(False)
        assert_health_changed(HealthState.UNKNOWN)

        cluster_health_model.component_fault(False)
        cluster_health_model.is_communicating(True)
        assert_health_changed(HealthState.OK)

        cluster_health_model.shadow_master_pool_node_health_changed([True, False])
        assert_health_changed(HealthState.DEGRADED)

        cluster_health_model.is_communicating(False)
        assert_health_changed(HealthState.UNKNOWN)

        cluster_health_model.component_fault(True)
        cluster_health_model.is_communicating(True)
        assert_health_changed(HealthState.FAILED)

        cluster_health_model.component_fault(False)
        assert_health_changed(HealthState.DEGRADED)

        cluster_health_model.shadow_master_pool_node_health_changed([False, False])
        assert_health_changed(HealthState.FAILED)
