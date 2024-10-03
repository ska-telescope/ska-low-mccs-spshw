# -*- coding: utf-8 -*-
#
# This file is part of the SKA MCCS project
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE.txt for more info.
"""An implementation of a health model for a PDU."""
from __future__ import annotations

from typing import Callable

from ska_low_mccs_common.health import BaseHealthModel

__all__ = ["PduHealthModel"]


class PduHealthModel(BaseHealthModel):
    """
    A health model for a PDU.

    At present this uses the base health model; this is a placeholder
    for a future, better implementation.
    """

    DEGRADED_CRITERIA = 0.05
    FAILED_CRITERIA = 0.2

    def __init__(
        self: PduHealthModel,
        health_changed_callback: Callable,
    ) -> None:
        """
        Initialise a new instance.

        :param health_changed_callback: a callback to be called when the
            health of the PDU (as evaluated by this model) changes
        """
        super().__init__(health_changed_callback)
