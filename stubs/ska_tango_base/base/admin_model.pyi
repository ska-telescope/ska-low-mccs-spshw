# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
from __future__ import annotations

import logging
from typing import Callable, Optional, cast

from transitions.extensions import LockedMachine as Machine

from ska_tango_base.control_model import AdminMode
from ska_tango_base.faults import StateModelError
from ska_tango_base.utils import for_testing_only


class _AdminModeMachine(Machine):
    def __init__(
        self: _AdminModeMachine,
        callback: Optional[Callable[[AdminMode], None]] = None,
        **extra_kwargs: dict,
    ) -> None: ...
    def _state_changed(self: _AdminModeMachine) -> None: ..


class AdminModeModel:
    def __init__(
        self: AdminModeModel,
        logger: logging.Logger,
        callback: Optional[Callable[[AdminMode], None]] = None,
    ) -> None: ...
    @property
    def admin_mode(self: AdminModeModel) -> AdminMode: ...
    def _admin_mode_changed(self: AdminModeModel, machine_state: str) -> None: ...
        def is_action_allowed(
        self: AdminModeModel, action: str, raise_if_disallowed: bool = False
    ) -> bool: ...
    def perform_action(self: AdminModeModel, action: str) -> None: ...
    