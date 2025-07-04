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
from typing import Any

from ska_control_model import PowerState, TaskStatus
from ska_low_mccs_common import MccsDeviceProxy

from ...tile.tpm_status import TpmStatus
from .base_tpm_test import TpmSelfCheckTest

__all__ = ["InitialiseStation"]


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
    Test we can initialise and synchronise tiles correctly.

    ##########
    TEST STEPS
    ##########

    1. Initialise the station. This should iterate through each of your tiles
        and initialise each of them.
    2. Verify each tile has reached the INITIALISED state.
    3. Synchronise the station. This should iterate through each of your tiles
        and synchronise each of them to the same reference time.
    4. Verify each tile has reached the SYNCHRONISED state.

    #################
    TEST REQUIREMENTS
    #################

    1. Every SPS device in your station must be in adminmode.ENGINEERING, this is
        common for all tests.
    2. Your station must have at least 1 TPM.
    3. Your station must be DevState.ON.
    """

    def test(self: InitialiseStation) -> None:
        """Test we can initialise tiles correctly."""
        self.test_logger.debug("Starting test, initialising station.")

        self._task_status = TaskStatus.NOT_FOUND
        self.component_manager._initialise(None, task_callback=self._task_callback)

        assert self._task_status == TaskStatus.COMPLETED

        for tile_proxy in self.tile_proxies:
            assert _wait_for_attribute(
                tile_proxy, "tileprogrammingstate", TpmStatus.SYNCHRONISED.pretty_name()
            )
            self.test_logger.debug(f"Sucessfully initialised {tile_proxy.dev_name()}")

        for tile_proxy in self.tile_proxies:
            assert (
                tile_proxy.GetArpTable() != '{"0": [], "1": []}'
            ), f"Didn't populate ARP table on {tile_proxy.dev_name()} in time."
            self.test_logger.debug(f"ARP table populated on {tile_proxy.dev_name()}")

        self.test_logger.debug("ARP tables populated.")

        for tile in self.tile_proxies:
            for fpga in ["fpga1", "fpga2"]:
                assert (
                    tile.ReadRegister(f"{fpga}.beamf_fd.f2f_latency.count") < 100
                ), f"Tile {tile.dev_name()}, F2F latency error!"
                assert (
                    tile.ReadRegister(f"{fpga}.beamf_fd.f2f_latency.count_start") == 1
                ), f"Tile {tile.dev_name()}, F2F latency start error!"
                assert (
                    tile.ReadRegister(f"{fpga}.beamf_fd.f2f_latency.count_stop") == 1
                ), f"Tile {tile.dev_name()}, F2F latency stop error!"
                assert (
                    tile.ReadRegister(f"{fpga}.beamf_fd.errors") == 0
                ), f"Tile {tile.dev_name()}, F2F Tile Beamformer error!"
                for core in range(2):
                    for lane in range(8):
                        assert (
                            tile.ReadRegister(
                                f"{fpga}.jesd204_if.core_id_{core}_lane_"
                                f"{lane}_buffer_adjust"
                            )
                            < 32
                        ), (
                            f"Tile {tile.dev_name()}, JESD204B fill buffer "
                            "level larger than 32 octets"
                        )
                self.test_logger.debug(
                    f"Register assertions on {tile.dev_name()} successful."
                )

        self.test_logger.info("Test succeeded!")

    def check_requirements(self: InitialiseStation) -> tuple[bool, str]:
        """
        Check test requirements.

        * Station is in state tango.DevState.ON
        * Station has at least one Tile.

        :returns: true if all checks pass.

        """
        if self.component_manager.component_state["power"] != PowerState.ON:
            return (False, "Station must be ON to test initialisation.")

        if len(self.tile_trls) < 1:
            return (False, "This test requires at least one TPM.")

        return super().check_requirements()
