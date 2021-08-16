import enum
import logging
from typing import Any, Optional

from ska_tango_base.base import OpStateModel

class ResultCode(enum.IntEnum):
    OK = 0
    STARTED = 1
    QUEUED = 2
    FAILED = 3
    UNKNOWN = 4

class BaseCommand:
    def __init__(
        self: BaseCommand,
        target: Any,
        *args: Any,
        logger: Optional[logging.Logger] = None,
        **kwargs: Any
    ) -> None:
        self.target = target
        ...

    def __call__(self: BaseCommand, argin: Any = None) -> Any: ...
    def do(self: BaseCommand, argin: Any = None) -> Any: ...

class StateModelCommand(BaseCommand):
    def __init__(
        self: StateModelCommand,
        target: Any,
        state_model: Any,
        action_slug: Optional[str]=None,
        *args: Any,
        logger: Optional[logging.Logger]=None,
        **kwargs: Any
    ) -> None: ...
    def __call__(self: StateModelCommand, argin: Any=None) -> Any: ...
    def is_allowed(self: StateModelCommand, raise_if_disallowed: bool=False) -> bool: ...

class ResponseCommand(BaseCommand):
    def _call_do(self: ResponseCommand, argin: Any=None) -> tuple[ResultCode, str]: ...

class CompletionCommand(StateModelCommand):
    def __init__(
        self: CompletionCommand,
        target: Any,
        state_model: Any,
        action_slug: str,
        *args: Any,
        logger: Optional[logging.Logger] = None,
        **kwargs: Any
    ) -> None: ...

    def completed(self: CompletionCommand) -> None: ...
