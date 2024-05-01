#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""An implementation of a basic test for a station."""
from __future__ import annotations

from .base_tpm_test import TpmSelfCheckTest

__all__ = ["BasicTangoTest"]


class BasicTangoTest(TpmSelfCheckTest):
    """A basic test to show we can connect to proxies."""

    def test(self: BasicTangoTest) -> None:
        """A basic test to show we can connect to proxies."""
        self.test_logger.debug(f"{self.tile_proxies[0].state()=}")

    def check_requirements(self: BasicTangoTest) -> tuple[bool, str]:
        """
        Check we have at least one TPM.

        :returns: true if we have at least one TPM.
        """
        if len(self.tile_trls) < 1:
            return (False, "This test requires at least one TPM")
        return super().check_requirements()
