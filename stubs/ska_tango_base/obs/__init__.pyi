from ska_tango_base.base import SKABaseDevice
from ska_tango_base.commands import ResultCode


class SKAObsDevice(SKABaseDevice):

    class InitCommand(SKABaseDevice.InitCommand):
        def do(  # type: ignore[override]
            self: SKAObsDevice.InitCommand) -> tuple[ResultCode, str]: ...
