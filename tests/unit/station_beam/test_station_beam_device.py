# type: ignore
# pylint: skip-file
# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests for MccsStationBeam."""
from __future__ import annotations

from typing import Any, Type

import pytest
from ska_control_model import HealthState
from ska_low_mccs_common import MccsDeviceProxy
from ska_low_mccs_common.testing.mock import MockChangeEventCallback
from ska_low_mccs_common.testing.tango_harness import DeviceToLoadType, TangoHarness
from tango.server import command

from ska_low_mccs.station_beam.station_beam_component_manager import (
    StationBeamComponentManager,
)
from ska_low_mccs.station_beam.station_beam_device import MccsStationBeam


@pytest.fixture()
def patched_station_beam_device_class(
    mock_station_beam_component_manager: StationBeamComponentManager,
) -> Type[MccsStationBeam]:
    """
    Return a station beam device class, patched with extra methods for testing.

    :param mock_station_beam_component_manager: A fixture that provides a partially
        mocked component manager which has access to the
        component_state_changed_callback.

    :return: a patched station beam device class, patched with extra methods
        for testing
    """

    class PatchedStationBeamDevice(MccsStationBeam):
        """
        MccsSubarray patched with extra commands for testing purposes.

        The extra commands allow us to mock the receipt of obs state
        change events from subservient devices, turn on DeviceProxies,
        set the initial obsState and examine the health model.
        """

        @command(dtype_in=str)
        def set_obs_state(
            self: PatchedStationBeamDevice,
            obs_state_name: str,
        ) -> None:
            """
            Set the obsState of this device.

            A method to set the obsState for testing purposes.

            :param obs_state_name: The name of the obsState to directly transition to.
            """
            self.obs_state_model._straight_to_state(obs_state_name)

        @command(dtype_in=bool, dtype_out=int)
        def examine_health_model(
            self: PatchedStationBeamDevice,
            get_station_health: bool,
        ) -> HealthState:
            """
            Return the health state of the station beam or station.

            Returns the health state of the station beam or the station for use
            in tests.

            :param get_station_health: Whether to return the station health instead
                of station beam.

            :return: The HealthState of the device.
            """
            if get_station_health:
                return self._health_model._station_health
            else:
                return self._health_state

        @command(dtype_out=bool)
        def get_station_fault(
            self: PatchedStationBeamDevice,
        ) -> bool:
            """
            Return the station fault state.

            Returns the fault state of the station for use in tests.

            :return: The HealthState of the device.
            """
            return self._health_model._station_fault

        @command(dtype_out=int)
        def get_beam_health(
            self: PatchedStationBeamDevice,
        ) -> HealthState:
            """
            Return the station fault state.

            Returns the fault state of the station for use in tests.

            :return: The HealthState of the device.
            """
            return self._health_model._beam_health

        def create_component_manager(
            self: PatchedStationBeamDevice,
        ) -> StationBeamComponentManager:
            """
            Return a partially mocked component manager instead of the usual one.

            :return: a mock component manager
            """
            mock_station_beam_component_manager._communication_state_changed_callback = (  # noqa E501
                self._communication_state_changed
            )
            mock_station_beam_component_manager._component_state_changed_callback = (
                self._component_state_changed_callback
            )

            return mock_station_beam_component_manager

    return PatchedStationBeamDevice


@pytest.fixture()
def device_to_load(
    patched_station_beam_device_class: type[MccsStationBeam],
) -> DeviceToLoadType:
    """
    Fixture that specifies the device to be loaded for testing.

    :param patched_station_beam_device_class: a class for a patched station beam
        device with extra methods for testing purposes.

    :return: specification of the device to be loaded
    """
    return {
        "path": "charts/ska-low-mccs/data/configuration.json",
        "package": "ska_low_mccs",
        "device": "beam_01",
        "proxy": MccsDeviceProxy,
        "patch": patched_station_beam_device_class,
    }


class TestMccsStationBeam(object):
    """Test class for MccsStationBeam tests."""

    @pytest.fixture()
    def device_under_test(
        self: TestMccsStationBeam, tango_harness: TangoHarness
    ) -> MccsDeviceProxy:
        """
        Fixture that returns the device under test.

        :param tango_harness: a test harness for Tango devices

        :return: the device under test
        """
        return tango_harness.get_device("low-mccs/beam/01")

    def test_healthState(
        self: TestMccsStationBeam,
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
        self: TestMccsStationBeam,
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
        assert getattr(device_under_test, attribute) == initial_value

        if write_value is not None:
            device_under_test.write_attribute(attribute, write_value)
            assert getattr(device_under_test, attribute) == write_value

    def test_beamId(
        self: TestMccsStationBeam,
        device_under_test: MccsDeviceProxy,
        beam_id: int,
    ) -> None:
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

    def test_stationId(
        self: TestMccsStationBeam,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test stationId attribute.

        This is a very weak test that simply checks that the attribute
        starts as zero, and when we write a new value to it,
        the write sticks.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.stationId == 0

        value_to_write = 3
        device_under_test.stationId = value_to_write
        assert device_under_test.stationId == value_to_write

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
        self: TestMccsStationBeam,
        device_under_test: MccsDeviceProxy,
        attribute: str,
    ) -> None:
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
        self: TestMccsStationBeam,
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

    @pytest.mark.parametrize("target_health_state", list(HealthState))
    def test_component_state_changed_callback_health(
        self: TestMccsStationBeam,
        device_under_test: MccsDeviceProxy,
        mock_station_beam_component_manager: StationBeamComponentManager,
        target_health_state: HealthState,
        device_health_state_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test `component_state_changed` properly handles health updates.

        Here we test that the change event is pushed and that we receive it and
        that the health state is correctly updated.

        :param mock_station_beam_component_manager: A fixture that provides a
            partially mocked component manager which has access to the
            component_state_changed_callback.
        :param target_health_state: The HealthState that the device should end up in.
        :param device_health_state_changed_callback: A mock callback to be called when
            the device's health state changes.
        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        device_under_test.add_change_event_callback(
            "healthState",
            device_health_state_changed_callback,
        )
        device_health_state_changed_callback.assert_next_change_event(
            HealthState.UNKNOWN
        )
        key = "health_state"
        get_station_health = False  # We want station beam health.
        state_change = {key: target_health_state}

        # Initial state is UNKNOWN so skip that one.
        if target_health_state != HealthState.UNKNOWN:
            mock_station_beam_component_manager._component_state_changed_callback(
                state_change
            )
            device_health_state_changed_callback.assert_next_change_event(
                target_health_state
            )
            dev_final_health_state = device_under_test.examine_health_model(
                get_station_health
            )
            assert dev_final_health_state == target_health_state

    @pytest.mark.parametrize("target_health_state", list(HealthState))
    def test_component_state_changed_callback_station_health(
        self: TestMccsStationBeam,
        device_under_test: MccsDeviceProxy,
        mock_station_beam_component_manager: StationBeamComponentManager,
        target_health_state: HealthState,
        mock_station_on_fqdn: str,
    ) -> None:
        """
        Test `component_state_changed` properly handles health updates.

        Test that the station health attribute is correctly updated.

        :param mock_station_beam_component_manager: A fixture that provides a
            partially mocked component manager which has access to the
            component_state_changed_callback.
        :param target_health_state: The HealthState that the device should end up in.
        :param mock_station_on_fqdn: The FQDN of a powered on station.
        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        key = "health_state"
        get_station_health = True  # We want station health.
        state_change = {key: target_health_state}

        mock_station_beam_component_manager._component_state_changed_callback(
            state_change, mock_station_on_fqdn
        )
        # Check that station health has updated.
        station_final_health_state = device_under_test.examine_health_model(
            get_station_health
        )
        assert station_final_health_state == target_health_state

    @pytest.mark.parametrize("station_fault", [True, False])
    def test_component_state_changed_callback_station_fault(
        self: TestMccsStationBeam,
        device_under_test: MccsDeviceProxy,
        mock_station_beam_component_manager: StationBeamComponentManager,
        station_fault: bool,
        mock_station_on_fqdn: str,
    ) -> None:
        """
        Test `component_state_changed` properly handles station fault updates.

        Test that the station_fault attribute updated correctly.

        :param mock_station_beam_component_manager: A fixture that provides a
            partially mocked component manager which has access to the
            component_state_changed_callback.
        :param station_fault: Whether the station is faulting or coming out of fault.
        :param mock_station_on_fqdn: The FQDN of a powered on station.
        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        key = "fault"
        state_change = {key: station_fault}
        mock_station_beam_component_manager._component_state_changed_callback(
            state_change, mock_station_on_fqdn
        )
        final_fault = device_under_test.get_station_fault()
        assert final_fault == station_fault

    @pytest.mark.parametrize("beam_locked", [True, False])
    def test_component_state_changed_callback_beam_locked(
        self: TestMccsStationBeam,
        device_under_test: MccsDeviceProxy,
        mock_station_beam_component_manager: StationBeamComponentManager,
        beam_locked: bool,
    ) -> None:
        """
        Test `component_state_changed` properly handles health updates.

        Here we only test that the change event is pushed and that we receive it.
        HealthState.UNKNOWN is omitted due to it being the initial state.

        :param mock_station_beam_component_manager: A fixture that provides a
            partially mocked component manager which has access to the
            component_state_changed_callback.
        :param beam_locked: Whether the beam is locked or not.
        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        key = "beam_locked"
        state_change = {key: beam_locked}
        mock_station_beam_component_manager._component_state_changed_callback(
            state_change
        )
        beam_health = device_under_test.get_beam_health()
        if beam_locked:
            assert beam_health == HealthState.OK
        else:
            assert beam_health == HealthState.DEGRADED
