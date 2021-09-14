from ska_tango_base.base import SKABaseDevice
from ska_tango_base.commands import CompletionCommand, ResultCode, ResponseCommand

class SKATelState(SKABaseDevice):
    class InitCommand(ResponseCommand, CompletionCommand):
        def do(  # type: ignore[override]
            self: SKATelState.InitCommand
        ) -> tuple[ResultCode, str]: ...
