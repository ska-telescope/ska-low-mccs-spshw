import logging
from typing import Any, Callable, Hashable, Optional

from ska_tango_base.base import BaseComponentManager, OpStateModel
from ska_tango_base.obs import ObsStateModel
from ska_tango_base.control_model import ObsState


class SubarrayObsStateModel(ObsStateModel):
    def __init__(
        self: SubarrayObsStateModel,
        logger: logging.Logger,
        callback: Optional[Callable[[ObsState], None]]=None) -> None: ...

    def _obs_state_changed(
        self: SubarrayObsStateModel,
        machine_state: ObsStateModel,
    ) -> None: ...


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
