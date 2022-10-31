# type: ignore
# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests for MccsTransientBuffer."""
from __future__ import annotations

import unittest.mock
from typing import Any

import pytest
import pytest_mock
from ska_control_model import HealthState
from ska_low_mccs_common import MccsDeviceProxy
from ska_low_mccs_common.testing.mock import MockChangeEventCallback
from ska_low_mccs_common.testing.tango_harness import DeviceToLoadType, TangoHarness

from ska_low_mccs import MccsTransientBuffer


@pytest.fixture()
def device_under_test(tango_harness: TangoHarness) -> MccsDeviceProxy:
    """
    Fixture that returns the device under test.

    :param tango_harness: a test harness for Tango devices

    :return: the device under test
    """
    return tango_harness.get_device("low-mccs/transientbuffer/transientbuffer")


class TestMccsTransientBuffer:
    """Tests of the MCCS transient buffer device."""

    @pytest.fixture()
    def mock_component_manager(
        self: TestMccsTransientBuffer,
        mocker: pytest_mock.MockerFixture,
    ) -> unittest.mock.Mock:
        """
        Return a mock to be used as a component manager for the transient buffer device.

        :param mocker: fixture that wraps the :py:mod:`unittest.mock`
            module

        :return: a mock to be used as a component manager for the
            transient buffer device.
        """
        return mocker.Mock()

    @pytest.fixture()
    def patched_device_class(
        self: TestMccsTransientBuffer,
        mock_component_manager: unittest.mock.Mock,
    ) -> type[MccsTransientBuffer]:
        """
        Return a transient buffer device that is patched with a mock component manager.

        :param mock_component_manager: the mock component manager with
            which to patch the device

        :return: a transient buffer device that is patched with a mock
            component manager.
        """

        class PatchedMccsTransientBuffer(MccsTransientBuffer):
            """A transient buffer device patched with a mock component manager."""

            def create_component_manager(
                self: PatchedMccsTransientBuffer,
            ) -> unittest.mock.Mock:
                """
                Return a mock component manager instead of the usual one.

                :return: a mock component manager
                """
                mock_component_manager._component_state_changed_callback = (
                    self.component_state_changed_callback
                )

                return mock_component_manager

        return PatchedMccsTransientBuffer

    @pytest.fixture()
    def device_to_load(
        self: TestMccsTransientBuffer,
        patched_device_class: MccsTransientBuffer,
    ) -> DeviceToLoadType:
        """
        Fixture that specifies the device to be loaded for testing.

        :param patched_device_class: a transient buffer device subclass
            that has been patched with a mock component manager

        :return: specification of the device to be loaded
        """
        return {
            "path": "charts/ska-low-mccs/data/extra.json",
            "package": "ska_low_mccs",
            "device": "transientbuffer",
            "proxy": MccsDeviceProxy,
            "patch": patched_device_class,
        }

    def test_healthState(
        self: TestMccsTransientBuffer,
        device_under_test: MccsDeviceProxy,
        device_health_state_changed_callback: MockChangeEventCallback,
        mock_component_manager: unittest.mock.Mock,
    ) -> None:
        """
        Test for healthState.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param device_health_state_changed_callback: a callback that we
            can use to subscribe to health state changes on the device
        :param mock_component_manager: mocked component manager used
            to access the real component state changed callback
        """
        device_under_test.add_change_event_callback(
            "healthState",
            device_health_state_changed_callback,
        )
        device_health_state_changed_callback.assert_next_change_event(
            HealthState.UNKNOWN
        )
        assert device_under_test.healthState == HealthState.UNKNOWN

        mock_component_manager._component_state_changed_callback(
            {"health_state": HealthState.OK}
        )
        device_health_state_changed_callback.assert_next_change_event(HealthState.OK)
        assert device_under_test.healthState == HealthState.OK

    @pytest.mark.parametrize(
        ("device_attribute", "component_manager_property", "example_value"),
        [
            ("stationId", "station_id", "example_string"),
            (
                "transientBufferJobId",
                "transient_buffer_job_id",
                "example_string",
            ),
            ("transientFrequencyWindow", "transient_frequency_window", (0.0,)),
            ("resamplingBits", "resampling_bits", 0),
            ("nStations", "n_stations", 0),
            ("stationIds", "station_ids", ("example_string",)),
        ],
    )
    def test_attributes(
        self: TestMccsTransientBuffer,
        mocker: pytest_mock.MockerFixture,
        device_under_test: MccsDeviceProxy,
        mock_component_manager: unittest.mock.Mock,
        device_attribute: str,
        component_manager_property: str,
        example_value: Any,
    ) -> None:
        """
        Test that device attributes reads result in component manager property reads.

        :param mocker: fixture that wraps the :py:mod:`unittest.mock`
            module
        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param mock_component_manager: the mock component manager being
            used by the patched transient buffer device.
        :param device_attribute: name of the device attribute under test.
        :param component_manager_property: name of the component manager
            property that is expected to be called when the device
            attribute is called.
        :param example_value: any value of the correct type for the
            device attribute.
        """
        property_mock = mocker.PropertyMock(return_value=example_value)
        setattr(
            type(mock_component_manager),
            component_manager_property,
            property_mock,
        )
        property_mock.assert_not_called()

        _ = getattr(device_under_test, device_attribute)
        property_mock.assert_called_once_with()
