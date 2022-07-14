import functools
import logging
import threading
from typing import Any, Callable, Optional, TypeVar, cast

from ska_tango_base.control_model import CommunicationStatus, PowerState
from ska_tango_base.executor import TaskExecutor, TaskStatus

class BaseComponentManager:
    def __init__(
        self: BaseComponentManager,
        logger: logging.Logger,
        communication_state_callback: Callable[[CommunicationStatus], None],
        component_state_callback: Callable,
        **state: Any,
    ) -> None: ...
    def start_communicating(self: BaseComponentManager) -> None: ...
    def stop_communicating(self: BaseComponentManager) -> None: ...
    @property
    def communication_state(self: BaseComponentManager) -> CommunicationStatus: ...
    def _update_communication_state(
        self: BaseComponentManager,
        communication_state: CommunicationStatus,
    ) -> None: ...
    def _push_communication_state_update(
        self: BaseComponentManager, communication_state: CommunicationStatus
    ) -> None: ...
    @property
    def component_state(self: BaseComponentManager) -> dict[str, Any]: ...
    def _update_component_state(
        self: BaseComponentManager,
        **kwargs: Any,
    ) -> None: ...
    def _push_component_state_update(self: BaseComponentManager, **kwargs: Any) -> None: ...
    def off(self: BaseComponentManager, task_callback: Callable) -> tuple[TaskStatus, str]: ...
    def standby(self: BaseComponentManager, task_callback: Callable) -> tuple[TaskStatus, str]: ...
    def on(self: BaseComponentManager, task_callback: Callable) -> tuple[TaskStatus, str]: ...
    def reset(self: BaseComponentManager, task_callback: Callable) -> tuple[TaskStatus, str]: ...
    def abort_tasks(self: BaseComponentManager) -> tuple[TaskStatus, str]: ...


class TaskExecutorComponentManager(BaseComponentManager):
    def __init__(
        self: TaskExecutorComponentManager,
        *args: Any,
        max_workers: Optional[int] = None,
        **kwargs: Any,
    ) -> None: ...
    def submit_task(
        self: TaskExecutorComponentManager,
        func: Callable,
        args: Optional[Any] = None,
        kwargs: Optional[Any] = None,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]: ...
    def abort_tasks(
        self: TaskExecutorComponentManager, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]: ...
