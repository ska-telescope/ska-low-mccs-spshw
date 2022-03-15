# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
import logging
from typing import Any, Optional, Tuple

from tango.server import Device

from ska_tango_base.base.op_state_model import OpStateModel
from ska_tango_base.base.task_queue_manager import QueueManager
from ska_tango_base.commands import CompletionCommand, ResultCode, ResponseCommand, StateModelCommand, BaseCommand
from ska_tango_base.control_model import PowerState

class BaseComponentManager:
    def __init__(
        self: BaseComponentManager,
        op_state_model: OpStateModel | None,
        *args: Any,
        **kwargs: Any,
    ):
        self._queue_manager: QueueManager
        ...

    @property
    def is_communicating(self: BaseComponentManager) -> bool: ...
    @property
    def power_mode(self: BaseComponentManager) -> Optional[PowerState]: ...
    @property
    def faulty(self: BaseComponentManager) -> Optional[bool]: ...

    def start_communicating(self: BaseComponentManager) -> None: ...
    def stop_communicating(self: BaseComponentManager) -> None: ...
    def off(self: BaseComponentManager) -> ResultCode | None: ...
    def standby(self: BaseComponentManager) -> ResultCode | None: ...
    def on(self: BaseComponentManager) -> ResultCode | None: ...
    def reset(self: BaseComponentManager) -> ResultCode | None: ...
    def component_power_mode_changed(
        self: BaseComponentManager, power_mode: PowerState
    ) -> None: ...
    def component_fault(self: BaseComponentManager) -> None: ...
    def enqueue(self: BaseComponentManager, task: BaseCommand, argin: Optional[Any] = None) -> Tuple[str, ResultCode]: ...

class SKABaseDevice(Device):
    def _init_state_model(self: SKABaseDevice) -> None: ...
    def _init_logging(self: SKABaseDevice) -> None: ...
    def init_device(self: SKABaseDevice) -> None: ...

    class InitCommand(ResponseCommand, CompletionCommand):
        def __init__(
            self: SKABaseDevice.InitCommand,
            target: Any,
            op_state_model: OpStateModel,
            logger: Optional[logging.Logger]=None
        ) -> None:
            self.logger = logger
            ...

        def do(  # type: ignore[override]
            self: SKABaseDevice.InitCommand
        ) -> tuple[ResultCode, str]: ...

    class OnCommand(StateModelCommand, ResponseCommand):
        def __init__(
            self: SKABaseDevice.OnCommand,
            target: object,
            op_state_model: OpStateModel,
            logger: Optional[logging.Logger]=None
        ) -> None: ...

        def do(  # type: ignore[override]
            self: SKABaseDevice.OnCommand
        ) -> tuple[ResultCode, str]: ...

    class OffCommand(StateModelCommand, ResponseCommand):
        def __init__(
            self: SKABaseDevice.OffCommand,
            target: object,
            op_state_model: OpStateModel,
            logger: Optional[logging.Logger]=None
        ) -> None:
            self.logger = logger
            ...

        def do(  # type: ignore[override]
            self: SKABaseDevice.OffCommand
        ) -> tuple[ResultCode, str]: ...

    def is_On_allowed(self: SKABaseDevice) -> bool: ...
    def On(self: SKABaseDevice) -> tuple[list[ResultCode], list[Optional[str]]]: ...
