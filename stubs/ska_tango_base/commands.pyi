import enum
import logging
from typing import Any, Optional

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
    ) -> None: ...
    def __call__(self: BaseCommand, argin: Optional[Any] = None) -> Any: ...
    def do(self: BaseCommand, argin: Optional[Any] = None) -> Any: ...

class ResponseCommand(BaseCommand):
    def _call_do(self: ResponseCommand, argin: Optional[Any] = None) -> tuple[ResultCode, str]: ...
    