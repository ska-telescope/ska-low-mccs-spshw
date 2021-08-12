# type: ignore
#########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
#########################################################################
"""This module contains the tests for MccsTelState."""
from __future__ import annotations
from typing import Any

import pytest
import tango

from ska_tango_base.control_model import AdminMode, HealthState

from ska_low_mccs import MccsDeviceProxy


@pytest.fixture()
def device_to_load():
    """
    Fixture that specifies the device to be loaded for testing.

    :return: specification of the device to be loaded
    :rtype: dict
    """
    return {
        "path": "charts/ska-low-mccs/data/extra.json",
        "package": "ska_low_mccs",
        "device": "telstate",
        "proxy": MccsDeviceProxy,
    }


class TestMccsTelState(object):
    """Test class for MccsTelState tests."""

    @pytest.fixture()
    def device_under_test(self, tango_harness):
        """
        Fixture that returns the device under test.

        :param tango_harness: a test harness for Tango devices

        :return: the device under test
        """
        return tango_harness.get_device("low-mccs/telstate/telstate")

    def test_healthState(self, device_under_test, device_health_state_changed_callback):
        """
        Test for healthState.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param device_health_state_changed_callback: a callback that we
            can use to subscribe to health state changes on the device
        """
        device_under_test.add_change_event_callback(
            "healthState",
            device_health_state_changed_callback,
        )
        device_health_state_changed_callback.assert_next_change_event(
            HealthState.UNKNOWN
        )
        assert device_under_test.healthState == HealthState.UNKNOWN

    @pytest.mark.parametrize(
        ("attribute", "initial_value", "write_value"),
        [
            ("elementsStates", "", "elementsStates test string"),
            ("observationsStates", "", "observationsStates test string"),
            ("algorithms", "", "algorithms test string"),
            ("algorithmsVersion", "", "algorithmsVersion test string"),
        ],
    )
    def test_attributes(
        self,
        device_under_test: MccsDeviceProxy,
        attribute: str,
        initial_value: Any,
        write_value: Any,
    ):
        """
        Test attribute values.

        The tel state component is currently a simply placeholder with
        some read-only attributes with constant values. This test checks
        those values.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param attribute: name of the attribute under test.
        :param initial_value: the expected initial value of the
            attribute.
        :param write_value: a value to write to check that it sticks
        """
        with pytest.raises(tango.DevFailed, match="Not connected"):
            _ = getattr(device_under_test, attribute)

        device_under_test.adminMode = AdminMode.ONLINE

        assert getattr(device_under_test, attribute) == initial_value
        device_under_test.write_attribute(attribute, write_value)
        assert getattr(device_under_test, attribute) == write_value
