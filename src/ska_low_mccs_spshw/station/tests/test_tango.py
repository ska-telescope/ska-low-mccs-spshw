#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""An implementation of a basic test for a station."""
from __future__ import annotations

import tango

from .base_tpm_test import TpmSelfCheckTest


class BasicTangoTest(TpmSelfCheckTest):
    """A basic test to show we can connect to proxies."""

    def test(self: TpmSelfCheckTest) -> None:
        """A basic test to show we can connect to proxies."""
        station_proxy = tango.DeviceProxy("low-mccs/spsstation/ci-1")
        self.test_logger.debug(f"{station_proxy.state()=}")
        tile_proxy = tango.DeviceProxy(self.tile_trls[0])
        self.test_logger.debug(f"{tile_proxy.state()=}")

    def check_requirements(self: TpmSelfCheckTest) -> tuple[bool, str]:
        """
        Check we have at least one TPM.

        :returns: true if we have at least one TPM.
        """
        if len(self.tile_trls) < 1:
            return (False, "This test requires at least one TPM")
        return (True, "This test can be run")
