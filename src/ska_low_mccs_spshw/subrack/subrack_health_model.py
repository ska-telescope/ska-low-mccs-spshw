#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""An implementation of a health model for an APIU."""
from ska_low_mccs_common.health import BaseHealthModel

__all__ = ["SubrackHealthModel"]


class SubrackHealthModel(BaseHealthModel):
    """
    A health model for an subrack.

    At present this uses the base health model; this is a placeholder
    for a future, better implementation.
    """
