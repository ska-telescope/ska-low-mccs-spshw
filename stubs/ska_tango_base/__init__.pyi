# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
from ska_tango_base.base import SKABaseDevice
from ska_tango_base.commands import DeviceInitCommand, ResultCode

class SKATelState(SKABaseDevice):
    class InitCommand(DeviceInitCommand):
        def do(  # type: ignore[override]
            self: SKATelState.InitCommand
        ) -> tuple[ResultCode, str]: ...