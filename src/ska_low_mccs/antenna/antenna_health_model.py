# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""An implementation of a health model for an antenna."""
from ska_low_mccs.health import HealthModel

__all__ = ["AntennaHealthModel"]


class AntennaHealthModel(HealthModel):
    """
    A health model for an antenna.

    At present this uses the base health model; this is a placeholder
    for a future, better implementation.
    """
