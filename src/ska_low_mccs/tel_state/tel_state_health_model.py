# type: ignore
#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""An implementation of a health model for telescope state."""
from ska_low_mccs_common.health import HealthModel

__all__ = ["TelStateHealthModel"]


class TelStateHealthModel(HealthModel):
    """
    A health model for telescope state.

    At present this uses the base health model; this is a placeholder
    for a future, better implementation.
    """
