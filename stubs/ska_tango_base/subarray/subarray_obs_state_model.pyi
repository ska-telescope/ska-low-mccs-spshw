# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
import logging
from typing import Callable, Optional

from ska_tango_base.control_model import ObsState
from ska_tango_base.obs.obs_state_model import ObsStateModel


class SubarrayObsStateModel(ObsStateModel):
    def __init__(
        self: SubarrayObsStateModel,
        logger: logging.Logger,
        callback: Optional[Callable[[ObsState], None]]=None) -> None: ...

    def _obs_state_changed(
        self: SubarrayObsStateModel,
        machine_state: ObsStateModel,
    ) -> None: ...
