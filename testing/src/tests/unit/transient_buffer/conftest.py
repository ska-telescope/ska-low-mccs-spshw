# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module defined a pytest harness for testing the MCCS transient buffer module."""
from __future__ import annotations

import logging
from typing import Callable

import pytest

from ska_low_mccs.transient_buffer import (
    TransientBuffer,
    TransientBufferComponentManager,
)

from ska_low_mccs.component import CommunicationStatus


@pytest.fixture()
def transient_buffer_component(logger: logging.Logger) -> TransientBuffer:
    """
    Fixture that returns a transient buffer.

    :param logger: a logger for the transient buffer to use.

    :return: a transient buffer
    """
    return TransientBuffer(logger)


@pytest.fixture()
def transient_buffer_component_manager(
    logger: logging.Logger,
    communication_status_changed_callback: Callable[[CommunicationStatus], None],
    message_queue_size_callback: Callable[[int], None],
) -> TransientBufferComponentManager:
    """
    Return a transient buffer component manager.

    :param logger: the logger to be used by this object.
    :param communication_status_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param message_queue_size_callback: callback to be called when the
        size of the message queue changes.

    :return: a transient buffer component manager
    """
    return TransientBufferComponentManager(
        logger,
        communication_status_changed_callback,
        message_queue_size_callback,
    )
