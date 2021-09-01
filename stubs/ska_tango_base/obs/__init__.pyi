import logging
from typing import Any, Callable, Optional

from ska_tango_base.base import BaseComponentManager, SKABaseDevice
from ska_tango_base.base.op_state_model import OpStateModel
from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import ObsState


class SKAObsDevice(SKABaseDevice):

    class InitCommand(SKABaseDevice.InitCommand):
        def do(  # type: ignore[override]
            self: SKAObsDevice.InitCommand) -> tuple[ResultCode, str]: ...
