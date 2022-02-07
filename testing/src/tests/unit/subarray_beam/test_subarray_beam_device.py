# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests for MccsSubarrayBeam."""
from __future__ import annotations

from typing import Any

import pytest
import tango
from ska_tango_base.control_model import AdminMode, HealthState

from ska_low_mccs import MccsDeviceProxy
from ska_low_mccs.testing.mock import MockChangeEventCallback
from ska_low_mccs.testing.tango_harness import DeviceToLoadType, TangoHarness


@pytest.fixture()
def device_to_load() -> DeviceToLoadType:
    """
    Fixture that specifies the device to be loaded for testing.

    :return: specification of the device to be loaded
    """
    return {
        "path": "charts/ska-low-mccs/data/configuration.json",
        "package": "ska_low_mccs",
        "device": "subarraybeam_01",
        "proxy": MccsDeviceProxy,
    }


class TestMccsSubarrayBeam(object):
    """Test class for MccsSubarrayBeam tests."""

    @pytest.fixture()
    def device_under_test(self: TestMccsSubarrayBeam, tango_harness: TangoHarness,) -> MccsDeviceProxy:
        """
        Fixture that returns the device under test.

        :param tango_harness: a test harness for Tango devices

        :return: the device under test
        """
        return tango_harness.get_device("low-mccs/subarraybeam/01")

    def test_healthState(
        self: TestMccsSubarrayBeam,
        device_under_test: MccsDeviceProxy,
        device_health_state_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for healthState.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param device_health_state_changed_callback: a callback that we
            can use to subscribe to health state changes on the device
        """
        device_under_test.add_change_event_callback(
            "healthState", device_health_state_changed_callback,
        )
        device_health_state_changed_callback.assert_next_change_event(HealthState.UNKNOWN)
        assert device_under_test.healthState == HealthState.UNKNOWN

    @pytest.mark.parametrize(
        ("attribute", "initial_value", "write_value"),
        [
            ("subarrayId", 0, None),
            ("subarrayBeamId", 0, None),
            ("logicalBeamId", 0, None),
            ("updateRate", 0.0, None),
            ("isBeamLocked", False, None),
        ],
    )
    def test_attributes(
        self: TestMccsSubarrayBeam,
        device_under_test: MccsDeviceProxy,
        attribute: str,
        initial_value: Any,
        write_value: Any,
    ) -> None:
        """
        Test attribute values.

        This is a very weak test that simply checks that attributes take
        certain initial values, and that, when we write to a writable
        attribute, the write sticks.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param attribute: name of the attribute under test.
        :param initial_value: the expected initial value of the
            attribute.
        :param write_value: a value to write to check that it sticks
        """
        with pytest.raises(tango.DevFailed, match="Communication with component is not established"):
            _ = getattr(device_under_test, attribute)

        device_under_test.adminMode = AdminMode.ONLINE

        assert getattr(device_under_test, attribute) == initial_value

        if write_value is not None:
            device_under_test.write_attribute(attribute, write_value)
            assert getattr(device_under_test, attribute) == write_value

    def test_stationIds(self: TestMccsSubarrayBeam, device_under_test: MccsDeviceProxy,) -> None:
        """
        Test stationIds attribute.

        This is a very weak test that simply checks that the attribute
        starts as an empty list, and when we write a new value to it,
        the write sticks.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        with pytest.raises(tango.DevFailed, match="Communication with component is not established"):
            _ = device_under_test.stationIds

        device_under_test.adminMode = AdminMode.ONLINE

        assert list(device_under_test.stationIds) == []

        value_to_write = [3, 4, 5, 6]
        device_under_test.stationIds = value_to_write
        assert list(device_under_test.stationIds) == value_to_write

    @pytest.mark.parametrize("attribute", ["channels", "antennaWeights", "phaseCentre"])
    def test_empty_list_attributes(
        self: TestMccsSubarrayBeam, device_under_test: MccsDeviceProxy, attribute: str,
    ) -> None:
        """
        Test attribute values for attributes that return lists of floats.

        This is a very weak test that simply checks that attributes are
        initialised to the empty list.

        Due to a Tango bug with return empty lists through image
        attributes or float spectrum attributes, the attribute value
        will come through as None rather than [].

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param attribute: name of the attribute under test.
        """
        with pytest.raises(tango.DevFailed, match="Communication with component is not established"):
            _ = getattr(device_under_test, attribute)
        device_under_test.adminMode = AdminMode.ONLINE
        assert getattr(device_under_test, attribute) is None

    def test_desired_pointing(self: TestMccsSubarrayBeam, device_under_test: MccsDeviceProxy,) -> None:
        """
        Test the desired pointing attribute.

        This is a weak test that simply check that the attribute's
        initial value is as expected, and that we can write a new value
        to it.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        with pytest.raises(tango.DevFailed, match="Communication with component is not established"):
            _ = device_under_test.desiredPointing
        device_under_test.adminMode = AdminMode.ONLINE

        assert list(device_under_test.desiredPointing) == []

        value_to_write = [1585619550.0, 192.85948, 2.0, 27.12825, 1.0]
        device_under_test.desiredPointing = value_to_write
        assert list(device_under_test.desiredPointing) == pytest.approx(value_to_write)
