import logging
from typing import Any, Hashable, Optional

from ska_tango_base.base import BaseComponentManager
from ska_tango_base.base.op_state_model import OpStateModel
from ska_tango_base.commands import CompletionCommand, ResultCode, ResponseCommand, ObservationCommand
from ska_tango_base.obs import SKAObsDevice
from ska_tango_base.subarray.subarray_obs_state_model import SubarrayObsStateModel


class SKASubarray(SKAObsDevice):

    class InitCommand(SKAObsDevice.InitCommand):
        def do( # type: ignore[override]
            self: SKASubarray.InitCommand
        ) -> tuple[ResultCode, str]: ...


    class ScanCommand(ObservationCommand, ResponseCommand):
        def __init__(
            self: SKASubarray.ScanCommand,
            target: Any,
            op_state_model: OpStateModel,
            obs_state_model: SubarrayObsStateModel,
            logger: Optional[logging.Logger]=None
        ) -> None: ...
        def do(  # type: ignore[override]
            self: SKASubarray.ScanCommand, argin: str) -> tuple[ResultCode, str]: ...


    class EndScanCommand(ObservationCommand, ResponseCommand):
        def __init__(
            self: SKASubarray.EndScanCommand,
            target: Any,
            op_state_model: OpStateModel,
            obs_state_model: SubarrayObsStateModel,
            logger: Optional[logging.Logger]=None
        ) -> None: ...
        def do(  # type: ignore[override]
            self: SKASubarray.EndScanCommand) -> tuple[ResultCode, str]: ...


    class EndCommand(ObservationCommand, ResponseCommand):
        def __init__(
            self: SKASubarray.EndCommand,
            target: Any,
            op_state_model: OpStateModel,
            obs_state_model: SubarrayObsStateModel,
            logger: Optional[logging.Logger]=None
        ) -> None: ...
        def do(  # type: ignore[override]
            self: SKASubarray.EndCommand) -> tuple[ResultCode, str]: ...


    class AbortCommand(ObservationCommand, ResponseCommand, CompletionCommand):
        def __init__(
            self: SKASubarray.AbortCommand,
            target: Any,
            op_state_model: OpStateModel,
            obs_state_model: SubarrayObsStateModel,
            logger: Optional[logging.Logger]=None
        ) -> None: ...
        def do(  # type: ignore[override]
            self: SKASubarray.AbortCommand) -> tuple[ResultCode, str]: ...


    class ObsResetCommand(ObservationCommand, ResponseCommand, CompletionCommand):
        def __init__(
            self: SKASubarray.ObsResetCommand,
            target: Any,
            op_state_model: OpStateModel,
            obs_state_model: SubarrayObsStateModel,
            logger: Optional[logging.Logger]=None
        ) -> None: ...
        def do(  # type: ignore[override]
            self: SKASubarray.ObsResetCommand) -> tuple[ResultCode, str]: ...


    class RestartCommand(ObservationCommand, ResponseCommand, CompletionCommand):
        def __init__(
            self: SKASubarray.RestartCommand,
            target: Any,
            op_state_model: OpStateModel,
            obs_state_model: SubarrayObsStateModel,
            logger: Optional[logging.Logger]=None
        ) -> None: ...
        def do(  # type: ignore[override]
            self: SKASubarray.RestartCommand) -> tuple[ResultCode, str]: ...


class SubarrayComponentManager(BaseComponentManager):
    def __init__(
        self: SubarrayComponentManager,
        op_state_model: OpStateModel,
        obs_state_model: SubarrayObsStateModel,
    ) -> None: ...

    def assign(
        self: SubarrayComponentManager,
        resources: list[Any]
    ) -> None: ...

    def release(
        self: SubarrayComponentManager,
        resources: list[Any]
    ) -> None: ...

    def release_all(self: SubarrayComponentManager) -> None: ...

    def configure(
        self: SubarrayComponentManager,
        configuration: dict[Hashable, Any],
    ) -> None: ...

    def deconfigure(self: SubarrayComponentManager) -> None: ...

    def scan(
        self: SubarrayComponentManager,
        *args: Any,
        **kwargs: Any
    ) -> None: ...

    def end_scan(self: SubarrayComponentManager) -> None: ...

    def abort(self: SubarrayComponentManager) -> None: ...

    def obsreset(self: SubarrayComponentManager) -> None: ...

    def restart(self: SubarrayComponentManager) -> None: ...

    @property
    def assigned_resources(self: SubarrayComponentManager) -> set[Any]: ...

    @property
    def configured_capabilities(self: SubarrayComponentManager) -> list[str]: ...

    def component_resourced(self: SubarrayComponentManager, resourced: bool) -> None: ...

    def component_configured(self: SubarrayComponentManager, configured: bool) -> None: ...

    def component_scanning(self: SubarrayComponentManager, scanning: bool) -> None: ...

    def component_obsfault(self: SubarrayComponentManager) -> None: ...
