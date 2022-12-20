# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests for MccsSubarrayBeam."""
from __future__ import annotations

from typing import Any, Type

import pytest
import tango
from ska_control_model import AdminMode, HealthState
from ska_low_mccs_common import MccsDeviceProxy
from ska_low_mccs_common.testing.mock import MockChangeEventCallback
from ska_low_mccs_common.testing.tango_harness import DeviceToLoadType, TangoHarness

from ska_low_mccs import MccsSubarrayBeam
from ska_low_mccs.subarray_beam.subarray_beam_component_manager import (
    SubarrayBeamComponentManager,
)


@pytest.fixture(name="patched_subarray_beam_device_class")
def patched_subarray_beam_device_class_fixture(
    subarray_beam_component_manager: SubarrayBeamComponentManager,
) -> Type[MccsSubarrayBeam]:
    """
    Return a subarray beam device class, patched with extra methods for testing.

    :param subarray_beam_component_manager: mocked component manager
        which has access to the component_state_changed_callback

    :return: a patched subarray beam device class, patched with extra methods
        for testing
    """

    class PatchedSubarrayBeamDevice(MccsSubarrayBeam):
        """MccsSubarrayBeam patched with extra commands for testing purposes."""

        def create_component_manager(
            self: PatchedSubarrayBeamDevice,
        ) -> SubarrayBeamComponentManager:
            """
            Return a patched component manager instead of the usual one.

            :return: a patched component manager
            """
            subarray_beam_component_manager._communication_state_changed_callback = (
                self._component_communication_state_changed
            )
            subarray_beam_component_manager._component_state_changed_callback = (
                self.component_state_changed_callback
            )
            return subarray_beam_component_manager

    return PatchedSubarrayBeamDevice


@pytest.fixture(name="device_to_load")
def device_to_load_fixture(
    patched_subarray_beam_device_class: type[MccsSubarrayBeam],
) -> DeviceToLoadType:
    """
    Fixture that specifies the device to be loaded for testing.

    :param patched_subarray_beam_device_class: a subarray beam
        device class that has been patched with a mock component manager

    :return: specification of the device to be loaded
    """
    return {
        "path": "tests/data/configuration.json",
        "package": "ska_low_mccs",
        "device": "subarraybeam_01",
        "proxy": MccsDeviceProxy,
        "patch": patched_subarray_beam_device_class,
    }


class TestMccsSubarrayBeam:
    """Test class for MccsSubarrayBeam tests."""

    @pytest.fixture()
    def device_under_test(
        self: TestMccsSubarrayBeam,
        tango_harness: TangoHarness,
    ) -> MccsDeviceProxy:
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
        subarray_beam_component_manager: SubarrayBeamComponentManager,
    ) -> None:
        """
        Test for healthState.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param device_health_state_changed_callback: a callback that we
            can use to subscribe to health state changes on the device
        :param subarray_beam_component_manager: mocked component manager
            which has access to the component_state_changed_callback
        """
        device_under_test.add_change_event_callback(
            "healthState",
            device_health_state_changed_callback,
        )
        device_health_state_changed_callback.assert_next_change_event(
            HealthState.UNKNOWN
        )
        assert device_under_test.healthState == HealthState.UNKNOWN

        if subarray_beam_component_manager._component_state_changed_callback:
            subarray_beam_component_manager._component_state_changed_callback(
                {"health_state": HealthState.OK}
            )

        device_health_state_changed_callback.assert_next_change_event(HealthState.OK)
        assert device_under_test.healthState == HealthState.OK

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
        with pytest.raises(
            tango.DevFailed,
            match="Communication is not being attempted so cannot be established.",
        ):
            _ = getattr(device_under_test, attribute)

        device_under_test.adminMode = AdminMode.ONLINE

        assert getattr(device_under_test, attribute) == initial_value

        if write_value is not None:
            device_under_test.write_attribute(attribute, write_value)
            assert getattr(device_under_test, attribute) == write_value

    def test_stationIds(
        self: TestMccsSubarrayBeam,
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
        with pytest.raises(
            tango.DevFailed,
            match="Communication is not being attempted so cannot be established.",
        ):
            _ = device_under_test.stationIds

        device_under_test.adminMode = AdminMode.ONLINE

        assert not list(device_under_test.stationIds)

        value_to_write = [3, 4, 5, 6]
        device_under_test.stationIds = value_to_write
        assert list(device_under_test.stationIds) == value_to_write

    @pytest.mark.parametrize("attribute", ["channels", "antennaWeights", "phaseCentre"])
    def test_empty_list_attributes(
        self: TestMccsSubarrayBeam,
        device_under_test: MccsDeviceProxy,
        attribute: str,
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
        with pytest.raises(
            tango.DevFailed,
            match="Communication is not being attempted so cannot be established.",
        ):
            _ = getattr(device_under_test, attribute)
        device_under_test.adminMode = AdminMode.ONLINE
        assert getattr(device_under_test, attribute) is None

    def test_desired_pointing(
        self: TestMccsSubarrayBeam,
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
        with pytest.raises(
            tango.DevFailed,
            match="Communication is not being attempted so cannot be established.",
        ):
            _ = device_under_test.desiredPointing
        device_under_test.adminMode = AdminMode.ONLINE

        assert not list(device_under_test.desiredPointing)

        value_to_write = [1585619550.0, 192.85948, 2.0, 27.12825, 1.0]
        device_under_test.desiredPointing = value_to_write
        assert list(device_under_test.desiredPointing) == pytest.approx(value_to_write)
