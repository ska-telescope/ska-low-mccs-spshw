# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""An implementation of a health model for telescope state."""
from ska_low_mccs.health import HealthModel


__all__ = ["TelStateHealthModel"]


class TelStateHealthModel(HealthModel):
    """
    A health model for telescope state.

    At present this uses the base health model; this is a placeholder
    for a future, better implementation.
    """
