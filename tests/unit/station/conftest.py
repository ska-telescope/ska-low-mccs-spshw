#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module defined a pytest harness for unit testing the SPS Station module."""
from __future__ import annotations

import unittest.mock

import pytest
import tango
from ska_control_model import PowerState, ResultCode
from ska_low_mccs_common.testing.mock import MockDeviceBuilder
from tango.server import command

from ska_low_mccs_spshw import SpsStation


@pytest.fixture(name="mock_subrack")
def mock_subrack_fixture() -> unittest.mock.Mock:
    """
    Fixture that provides a mock MccsSubrack device.

    :return: a mock MccsSubrack device.
    """
    builder = MockDeviceBuilder()
    builder.set_state(tango.DevState.ON)
    builder.add_result_command("Off", ResultCode.STARTED)
    builder.add_result_command("On", ResultCode.STARTED)
    return builder()


@pytest.fixture(name="mock_tile")
def mock_tile_fixture() -> unittest.mock.Mock:
    """
    Fixture that provides a mock MccsSubrack device.

    :return: a mock MccsSubrack device.
    """
    builder = MockDeviceBuilder()
    builder.set_state(tango.DevState.ON)
    return builder()


@pytest.fixture(name="patched_station_device_class")
def patched_station_device_class_fixture() -> type[SpsStation]:
    """
    Return a station device class patched with extra methods for testing.

    :return: a station device class patched with extra methods for
        testing.
    """

    class PatchedStationDevice(SpsStation):
        """
        SpsStation patched with extra commands for testing purposes.

        The extra commands allow us to mock the receipt of a state
        change event from subservient subrack devices.
        """

        @command()
        def MockSubracksOff(self: PatchedStationDevice) -> None:
            """
            Mock all subracks being turned off.

            Make the station device think it has received state change
            event from its subracks, indicating that the subracks are
            now OFF.
            """
            for name in self.component_manager._subrack_proxies:
                self.component_manager._subrack_state_changed(
                    name, power=PowerState.OFF
                )

            for name in self.component_manager._tile_proxies:
                self.component_manager._tile_state_changed(
                    name, power=PowerState.NO_SUPPLY
                )

    return PatchedStationDevice
