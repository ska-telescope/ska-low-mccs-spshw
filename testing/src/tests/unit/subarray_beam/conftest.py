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
"""This module defined a pytest harness for testing the MCCS subarray beam module."""
from __future__ import annotations

import logging
from typing import Callable
import unittest.mock

import pytest

from ska_low_mccs.subarray_beam import (
    SubarrayBeam,
    SubarrayBeamComponentManager,
)

from ska_low_mccs.component import CommunicationStatus
from ska_low_mccs.testing.mock import MockChangeEventCallback

@pytest.fixture()
def component_is_beam_locked_changed_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> Callable[[bool], None]:
    """
    Return a mock callback for a change in whether the subarray beam is locked.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the component manager
        detects that whether the beam is locked has changed
    """
    return mock_callback_factory()


@pytest.fixture()
def is_configured_changed_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> Callable[[bool], None]:
    """
    Return a mock callback for a change in whether the subarray beam is configured.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the component manager
        detects that whether the beam is configured has changed
    """
    return mock_callback_factory()


@pytest.fixture()
def subarray_beam_component(
    logger: logging.Logger,
) -> SubarrayBeam:
    """
    Fixture that returns a subarray beam component.

    :param logger: a logger for the subarray beam component to use.

    :return: a subarray beam component
    """
    return SubarrayBeam(logger)


@pytest.fixture()
def subarray_beam_component_manager(
    logger: logging.Logger,
    lrc_result_changed_callback: MockChangeEventCallback,
    communication_status_changed_callback: Callable[[CommunicationStatus], None],
    component_is_beam_locked_changed_callback: Callable[[bool], None],
    is_configured_changed_callback: Callable[[bool], None],
) -> SubarrayBeamComponentManager:
    """
    Return a subarray beam component manager.

    :param logger: the logger to be used by this object.
    :param communication_status_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_is_beam_locked_changed_callback: a callback to be
        called when whether the beam is locked changes.
    :param is_configured_changed_callback: a callback to be
        called when whether the beam is configured changes.

    :return: a subarray beam component manager
    """
    return SubarrayBeamComponentManager(
        logger,
        lrc_result_changed_callback,
        communication_status_changed_callback,
        component_is_beam_locked_changed_callback,
        is_configured_changed_callback,
    )
