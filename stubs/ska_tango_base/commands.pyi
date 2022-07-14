# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
import enum
import logging
from typing import Any, Callable, Optional

from tango.server import Device

from ska_tango_base.base.component_manager import BaseComponentManager
from ska_tango_base.base.op_state_model import OpStateModel
from ska_tango_base.subarray.subarray_obs_state_model import SubarrayObsStateModel

class ResultCode(enum.IntEnum):
    OK = 0
    STARTED = 1
    QUEUED = 2
    FAILED = 3
    UNKNOWN = 4

class _BaseCommand:
    def __init__(self: _BaseCommand, logger: Optional[logging.Logger] = None) -> None: ...
    def __call__(self: _BaseCommand, *args: Any, **kwargs: Any) -> Any: ...
    def do(self: _BaseCommand, *args: Any, **kwargs: Any) -> Any:...

class FastCommand(_BaseCommand):
    def __call__(self: FastCommand, *args: Any, **kwargs: Any) -> Any: ...

class SlowCommand(_BaseCommand):
    def __init__(
        self: SlowCommand,
        callback: Optional[Callable],
        logger: Optional[logging.Logger] = None,
    ) -> None: ...
    def __call__(self: SlowCommand, *args: Any, **kwargs: Any) -> Any: ...
    def _invoked(self: SlowCommand) -> None: ...
    def _completed(self: SlowCommand) -> None: ...

class DeviceInitCommand(SlowCommand):
    def __init__(
        self: DeviceInitCommand, device: Device, logger: Optional[logging.Logger] = None
    ) -> None:
        self._device = device
        ...

class SubmittedSlowCommand(SlowCommand):
    def __init__(  # type: ignore[no-untyped-def]
        self: SubmittedSlowCommand,
        command_name: str,
        command_tracker,  # noqa: F821
        component_manager: BaseComponentManager,
        method_name: str,
        callback: Optional[Callable] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None: ...
    def do(  # type: ignore[return]
        self: SubmittedSlowCommand, *args: Any, **kwargs: Any
    ) -> tuple[ResultCode, str]: ...
