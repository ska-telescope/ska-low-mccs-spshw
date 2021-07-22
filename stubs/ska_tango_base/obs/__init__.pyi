import logging
from typing import Any, Callable, Optional

from ska_tango_base.base import BaseComponentManager, OpStateModel
from ska_tango_base.control_model import ObsState


class ObsStateModel:

    def __init__(
        self: ObsStateModel,
        state_machine_factory: Callable[[], Any],
        logger: logging.Logger,
        callback: Optional[Callable[[ObsState], None]]=None,
    ) -> None: ...

    @property
    def obs_state(self: ObsStateModel) -> ObsState: ...

    def is_action_allowed(
        self: ObsStateModel,
        action: str,
        raise_if_disallowed: bool = False
    ) -> bool: ...

    def perform_action(self: ObsStateModel, action:str) -> None: ...

    def _straight_to_state(self: ObsStateModel, obs_state_name: str) -> None: ...
