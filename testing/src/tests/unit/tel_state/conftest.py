# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module defined a pytest harness for testing the MCCS tel state module."""
from __future__ import annotations

import logging
from typing import Callable

import pytest

from ska_low_mccs.tel_state import (
    TelState,
    TelStateComponentManager,
)

from ska_low_mccs.component import CommunicationStatus
from ska_low_mccs.testing.mock import MockChangeEventCallback


@pytest.fixture()
def tel_state_component(logger: logging.Logger) -> TelState:
    """
    Fixture that returns a tel state component.

    :param logger: a logger for the tel state component to use.

    :return: a tel state component
    """
    return TelState(logger)


@pytest.fixture()
def tel_state_component_manager(
    logger: logging.Logger,
    lrc_result_changed_callback: MockChangeEventCallback,
    communication_status_changed_callback: Callable[[CommunicationStatus], None],
) -> TelStateComponentManager:
    """
    Return a tel state component manager.

    :param logger: the logger to be used by this object.
    :param lrc_result_changed_callback: a callback to
        be used to subscribe to device LRC result changes
    :param communication_status_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes

    :return: a tel state component manager
    """
    return TelStateComponentManager(
        logger,
        lrc_result_changed_callback,
        communication_status_changed_callback,
    )
