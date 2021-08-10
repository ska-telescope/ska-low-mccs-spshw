# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""An implementation of a health model for an APIU."""
from ska_low_mccs.health import HealthModel


__all__ = ["ApiuHealthModel"]


class ApiuHealthModel(HealthModel):
    """
    A health model for an apiu.

    At present this uses the base health model; this is a placeholder
    for a future, better implementation.
    """
