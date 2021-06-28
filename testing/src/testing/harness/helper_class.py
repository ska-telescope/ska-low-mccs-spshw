# type: ignore
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""This module implements an MCCS test helper class."""

import pytest
import json
from time import sleep
from tango import DevState
from ska_tango_base.commands import ResultCode

__all__ = ["HelperClass"]


class HelperClass:
    """
    Common fixtures used in derived test classes.

    Mix this class in with the test class that requires these fixtures.
    """

    @pytest.fixture(autouse=True)
    def _autouse_these_fixtures(self, command_helper, empty_json_dict):
        """
        Autouse these fixtures for all tests. Store as part of the test object.

        :param command_helper: A command helper fixture
        :type command_helper: CommandHelper
        :param empty_json_dict: an empty json encoded dictionary
        :type empty_json_dict: str
        """
        self._command_helper = command_helper
        self._empty_json_dict = empty_json_dict

    def start_up_device(self, device_under_test):
        """
        Helper method to get the device into ON state.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        [result_code], _ = device_under_test.Off(self._empty_json_dict)
        assert result_code == ResultCode.OK
        self._command_helper.check_device_state(device_under_test, DevState.OFF)
        [result_code], _ = device_under_test.On(self._empty_json_dict)
        assert result_code == ResultCode.OK
        self._command_helper.check_device_state(device_under_test, DevState.ON)

    def wait_for_command_to_complete(
        self, controller, expected_result=ResultCode.OK, timeout_limit=5.0
    ):
        """
        Wait for the controller command to complete.

        :param controller: The controller device
        :type controller: DeviceProxy
        :param expected_result: The expected results
        :type expected_result: ResultCode
        :param timeout_limit: The maximum timeout allowed for a command to complete
        :type timeout_limit: float
        """
        busy = True
        initial_delay = 1.0
        delta_delay = 0.3
        sleep(initial_delay)
        timeout = initial_delay
        while busy:
            result = json.loads(controller.commandResult)
            if result.get("result_code") == expected_result or timeout >= timeout_limit:
                busy = False
            else:
                timeout += delta_delay
                sleep(delta_delay)
        result_code = result.get("result_code")
        message_uid = result.get("message_uid")
        assert result_code == expected_result, (
            f"{result_code} (Actual)"
            f" != {expected_result} (Expected); message_uid = {message_uid}"
        )
        assert timeout <= timeout_limit
        sleep(0.1)  # Added to reduce possibility of seg faults

    def check_states_of_devices(self, dev_states):
        """
        Helper to check that each device is in the expected state with a timeout.

        :param dev_states: the devices and expected states of them
        :type dev_states: dict
        """
        sleep(0.3)  # Stability testing
        delta_delay = 0.3
        for device, state in dev_states.items():
            count = 0.0
            while device.State() != state and count < 2.7:
                count += delta_delay
                sleep(delta_delay)
            assert device.State() == state
        sleep(0.1)  # Added to reduce possibility of seg faults
