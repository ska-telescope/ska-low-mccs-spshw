import logging
from typing import Callable

import tango

class OpStateModel:
    def __init__(
        self: OpStateModel,
        logger: logging.Logger,
        callback: Callable[[tango.DevState], None],
    ): ...
    @property
    def op_state(self: OpStateModel) -> tango.DevState: ...
    def _op_state_changed(self: OpStateModel, machine_state: str) -> None: ...
    def is_action_allowed(
        self: OpStateModel,
        action: str,
        raise_if_disallowed: bool = False,
    ) -> bool: ...
    def perform_action(self: OpStateModel, action: str) -> None: ...
    def _straight_to_state(self: OpStateModel, op_state_name: str) -> None: ...
