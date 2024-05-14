#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""An implementation of an initialise test for a station."""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from ska_control_model import PowerState, TaskStatus
from ska_low_mccs_common import MccsDeviceProxy

from ...tile.tpm_status import TpmStatus
from .base_tpm_test import TpmSelfCheckTest

__all__ = ["InitialiseStation"]

RFC_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def _wait_for_attribute(
    proxy: MccsDeviceProxy, attribute: str, expected_value: Any, timeout: int = 60
) -> bool:
    start_time = time.time()
    while time.time() < start_time + timeout:
        if getattr(proxy, attribute) == expected_value:
            return True
        time.sleep(1)
    return False


class InitialiseStation(TpmSelfCheckTest):
    """
    Test we can initialise tiles correctly.

    ##########
    TEST STEPS
    ##########

    1. Initialise the station. This should iterate through each of your tiles
        and initialise each of them.
    2. Verify each tile has reached the INITIALISED state.
    3. Synchronise the station. This should iterate through each of your tiles
        and synchronise each of them to the same reference time.
    4. Verify each tile has reached the SYNCHRONISED state.
    5. Configure the MccsDAQ to recieve station beam data.
    6. Start the station beamformer.
    7. Verify that the rate of data received at MccsDAQ is correct.

    #################
    TEST REQUIREMENTS
    #################

    1. Every SPS device in your station must be in adminmode.ENGINEERING, this is
        common for all tests.
    2. Your station must have at least 1 TPM.
    3. Your station must be DevState.ON.
    4. You must have a MccsDAQ instance to receive data.
    """

    def test(self: InitialiseStation) -> None:
        """Test we can initialise tiles correctly."""
        self.test_logger.debug("Starting test, initialising station.")
        self.component_manager._initialise(task_callback=self._task_callback)

        assert self._task_status == TaskStatus.COMPLETED

        for tile_proxy in self.tile_proxies:
            assert _wait_for_attribute(
                tile_proxy, "tileprogrammingstate", TpmStatus.INITIALISED.pretty_name()
            )
            self.test_logger.debug(f"Sucessfully initialised {tile_proxy.dev_name()}")

        self.test_logger.debug("Sucessfully initialised station, synchronising.")

        start_time = datetime.strftime(
            datetime.fromtimestamp(int(time.time()) + 2), RFC_FORMAT
        )

        self.component_manager._start_acquisition(
            start_time=start_time, task_callback=self._task_callback
        )

        assert self._task_status == TaskStatus.COMPLETED

        for tile_proxy in self.tile_proxies:
            assert _wait_for_attribute(
                tile_proxy, "tileprogrammingstate", TpmStatus.SYNCHRONISED.pretty_name()
            )
            self.test_logger.debug(f"Sucessfully synchronised {tile_proxy.dev_name()}")

        self.test_logger.debug("Sucessfully synchronised station, starting beamformer.")

        self.test_logger.error(f"{self.tile_proxies[0].fpgaReferenceTime=}")
        self.test_logger.error(f"{self.tile_proxies[0].fpgaFrameTime=}")

        time.sleep(1)

        start_time = datetime.strftime(
            datetime.fromtimestamp(int(time.time()) + 5), RFC_FORMAT
        )

        self.component_manager.start_beamformer(
            start_time=start_time, duration=-1, subarray_beam_id=-1, scan_id=0
        )

        for tile_proxy in self.tile_proxies:
            assert _wait_for_attribute(tile_proxy, "isBeamformerRunning", True)
            self.test_logger.debug(
                f"Sucessfully started beamformer {tile_proxy.dev_name()}"
            )

        assert self.component_manager.is_beamformer_running

        self.test_logger.debug("Sucessfully started station beamformer")

        self.component_manager.stop_beamformer()

        for tile_proxy in self.tile_proxies:
            assert _wait_for_attribute(tile_proxy, "isBeamformerRunning", False)
            self.test_logger.debug(
                f"Sucessfully stopped beamformer {tile_proxy.dev_name()}"
            )

        assert not self.component_manager.is_beamformer_running

        self.test_logger.debug("Sucessfully stopped station beamformer")

    def check_requirements(self: InitialiseStation) -> tuple[bool, str]:
        """
        Check test requirements.

        :returns: true if we have at least one TPM.
        """
        if self.component_manager.component_state["power"] != PowerState.ON:
            return (False, "Station must be on to test initialisation.")

        if len(self.tile_trls) < 1:
            return (False, "This test requires at least one TPM.")

        if self.daq_proxy is None:
            return (False, "This test requires a MccsDAQ instance.")
        return super().check_requirements()
