#  -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""An implementation of a health model for a calibration store."""
from ska_low_mccs_common.health import BaseHealthModel

__all__ = ["CalibrationStoreHealthModel"]


class CalibrationStoreHealthModel(BaseHealthModel):
    """
    A health model for a calibration store.

    At present this uses the base health model; this is a placeholder
    for a future, better implementation.
    """
