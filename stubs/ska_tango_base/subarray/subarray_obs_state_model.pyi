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
