# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
from enum import IntEnum
from typing import Any, Callable, Optional

class TaskStatus(IntEnum):
    STAGING = 0
    QUEUED = 1
    IN_PROGRESS = 2
    ABORTED = 3
    NOT_FOUND = 4
    COMPLETED = 5
    REJECTED = 6
    FAILED = 7

class TaskExecutor:
    def __init__(self: TaskExecutor, max_workers: Optional[int]) -> None: ...
    def submit(  # type: ignore[return]
        self: TaskExecutor,
        func: Callable,
        args: Optional[Any] = None,  # should this be *args??
        kwargs: Optional[Any] = None,  # should this be **kwargs??
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]: ...

