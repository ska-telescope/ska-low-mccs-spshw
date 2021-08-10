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
"""This module contains the tests for MccsStationBeam."""
from __future__ import annotations
from typing import Any

import pytest

from ska_tango_base.control_model import HealthState

from ska_low_mccs import MccsDeviceProxy


@pytest.fixture()
def device_to_load():
    """
    Fixture that specifies the device to be loaded for testing.

    :return: specification of the device to be loaded
    :rtype: dict
    """
    return {
        "path": "charts/ska-low-mccs/data/configuration.json",
        "package": "ska_low_mccs",
        "device": "beam_001",
        "proxy": MccsDeviceProxy,
    }


class TestMccsStationBeam(object):
    """Test class for MccsStationBeam tests."""

    @pytest.fixture()
    def device_under_test(self, tango_harness):
        """
        Fixture that returns the device under test.

        :param tango_harness: a test harness for Tango devices

        :return: the device under test
        """
        return tango_harness.get_device("low-mccs/beam/001")

    @pytest.mark.skip(reason="Occasional deadlock?")
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
            ("subarrayId", 0, None),
            ("logicalBeamId", 0, None),
            ("updateRate", 0.0, None),
            ("isBeamLocked", False, None),
        ],
    )
    def test_scalar_attributes(
        self,
        device_under_test: MccsDeviceProxy,
        attribute: str,
        initial_value: Any,
        write_value: Any,
    ):
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
        assert getattr(device_under_test, attribute) == initial_value

        if write_value is not None:
            device_under_test.write_attribute(attribute, write_value)
            assert getattr(device_under_test, attribute) == write_value

    def test_beamId(
        self,
        device_under_test: MccsDeviceProxy,
        beam_id: int,
    ):
        """
        Test the beam id attribute.

        This is a very weak test that simply checks that it takes a
        certain initial value.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param beam_id: the beam id of the device.
        """
        assert device_under_test.beamId == beam_id

    def test_stationIds(
        self,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test stationIds attribute.

        This is a very weak test that simply checks that the attribute
        starts as an empty list, and when we write a new value to it,
        the write sticks.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert list(device_under_test.stationIds) == []

        value_to_write = [3, 4, 5, 6]
        device_under_test.stationIds = value_to_write
        assert list(device_under_test.stationIds) == value_to_write

    @pytest.mark.parametrize(
        "attribute",
        [
            "channels",
            "antennaWeights",
            "phaseCentre",
            "pointingDelay",
            "pointingDelayRate",
        ],
    )
    def test_empty_list_attributes(
        self,
        device_under_test: MccsDeviceProxy,
        attribute: str,
    ):
        """
        Test attribute values for attributes that return lists of floats.

        This is a very weak test that simply checks that attributes are
        initialised to the empty list.

        Due to a Tango bug with return of empty lists through image
        attributes or float spectrum attributes, the attribute value
        may come through as None rather than [].

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param attribute: name of the attribute under test.
        """
        value = getattr(device_under_test, attribute)
        assert value is None or list(value) == []

    def test_desired_pointing(
        self,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test the desired pointing attribute.

        This is a weak test that simply check that the attribute's
        initial value is as expected, and that we can write a new value
        to it.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert list(device_under_test.desiredPointing) == []

        value_to_write = [1585619550.0, 192.85948, 2.0, 27.12825, 1.0]
        device_under_test.desiredPointing = value_to_write
        assert list(device_under_test.desiredPointing) == pytest.approx(value_to_write)
