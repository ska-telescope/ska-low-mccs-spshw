# type: ignore
# pylint: skip-file
# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains integration tests of MCCS device interactions."""
from __future__ import annotations

import pytest
import tango
from ska_control_model import AdminMode, HealthState, ResultCode
from ska_low_mccs_common import MccsDeviceProxy
from ska_low_mccs_common.testing.tango_harness import DevicesToLoadType, TangoHarness
from tango import DevState


@pytest.fixture()
def devices_to_load() -> DevicesToLoadType:
    """
    Fixture that specifies the devices to be loaded for testing.

    :return: specification of the devices to be loaded
    """
    return {
        "path": "tests/data/controller_only_configuration.json",
        "package": "ska_low_mccs",
        "devices": [
            {"name": "controller", "proxy": MccsDeviceProxy},
        ],
    }


class TestMccsController:
    """Integration test case for the MccsController class."""

    @pytest.mark.timeout(19)
    def test_controller_no_subservient(
        self: TestMccsController,
        tango_harness: TangoHarness,
    ):
        """
        Test that an MccsController can allocate resources to an MccsSubarray.

        :param tango_harness: a test harness for tango devices
        """
        controller = tango_harness.get_device("low-mccs/control/control")

        assert controller.adminMode == AdminMode.OFFLINE
        # state = controller.State()
        assert controller.State() == DevState.DISABLE
        assert controller.healthState == HealthState.UNKNOWN

        for i in range(2):
            controller.adminMode = AdminMode.ONLINE

            assert controller.adminMode == AdminMode.ONLINE
            state = controller.State()
            assert state == DevState.ON
            assert controller.healthState == HealthState.OK

            controller.adminMode = AdminMode.OFFLINE

            assert controller.adminMode == AdminMode.OFFLINE
            state = controller.State()
            assert state == DevState.DISABLE
            assert controller.healthState == HealthState.UNKNOWN

        with pytest.raises(
            tango.DevFailed,
            match="Command On not allowed when the device is in DISABLE state",
        ):
            _ = controller.On()

        controller.adminMode = AdminMode.ONLINE

        ([result_code], [msg]) = controller.On()
        assert result_code == ResultCode.REJECTED
        assert msg == "Device is already in ON state."

        ([result_code], [msg]) = controller.Off()
        assert result_code == ResultCode.REJECTED
        assert msg == "No subservient devices to turn off"

        ([result_code], [msg]) = controller.StandBy()
        assert result_code == ResultCode.REJECTED
        assert msg == "No subservient devices to put into standby"

        ([result_code], [msg]) = controller.StandByFull()
        assert result_code == ResultCode.REJECTED
        assert msg == "No subservient devices to put into standby"

        ([result_code], [msg]) = controller.StandByLow()
        assert result_code == ResultCode.REJECTED
        assert msg == "No subservient devices to put into standby"

        ([result_code], [msg]) = controller.Allocate("")
        assert result_code == ResultCode.REJECTED
        assert msg == "No subservient devices to allocate"

        ([result_code], [msg]) = controller.Release("1")
        assert result_code == ResultCode.REJECTED
        assert msg == "No subservient subarray devices to release"

        ([result_code], [msg]) = controller.RestartSubarray(1)
        assert result_code == ResultCode.REJECTED
        assert msg == "No subservient subarray devices to restart"
