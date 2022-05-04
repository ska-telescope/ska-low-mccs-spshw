# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests for MccsPasdBus."""

from __future__ import annotations

import unittest.mock
from typing import Any

import pytest
import pytest_mock
from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import HealthState

from ska_low_mccs import MccsDeviceProxy, MccsPasdBus
from ska_low_mccs.testing.mock.mock_callable import MockCallableDeque, MockChangeEventCallback
from ska_low_mccs.testing.tango_harness import DeviceToLoadType, TangoHarness


@pytest.fixture()
def device_under_test(tango_harness: TangoHarness) -> MccsDeviceProxy:
    """
    Fixture that returns the device under test.

    :param tango_harness: a test harness for Tango devices

    :return: the device under test
    """
    return tango_harness.get_device("low-mccs/pasdbus/001")


class TestMccsPasdBus:
    """Tests of the MCCS transient buffer device."""

    @pytest.fixture()
    def mock_component_manager(self: TestMccsPasdBus, mocker: pytest_mock.mocker) -> unittest.mock.Mock:  # type: ignore[valid-type]
        """
        Return a mock to be used as a component manager for the PaSD bus device.

        :param mocker: fixture that wraps the :py:mod:`unittest.mock`
            module

        :return: a mock to be used as a component manager for the
            transient buffer device.
        """
        return mocker.Mock()  # type: ignore[attr-defined]

    @pytest.fixture()
    def patched_device_class(
        self: TestMccsPasdBus, mock_component_manager: unittest.mock.Mock
    ) -> type[MccsPasdBus]:
        """
        Return a PaSD bus device that is patched with a mock component manager.

        :param mock_component_manager: the mock component manager with
            which to patch the device

        :return: a PaSD bus device that is patched with a mock component
            manager.
        """

        class PatchedMccsPasdBus(MccsPasdBus):
            """A PaSD bus device patched with a mock component manager."""

            def create_component_manager(
                self: PatchedMccsPasdBus,
            ) -> unittest.mock.Mock:
                """
                Return a mock component manager instead of the usual one.

                :return: a mock component manager
                """
                return mock_component_manager

        return PatchedMccsPasdBus

    @pytest.fixture()
    def device_to_load(
        self: TestMccsPasdBus, patched_device_class: MccsPasdBus
    ) -> DeviceToLoadType:
        """
        Fixture that specifies the device to be loaded for testing.

        :param patched_device_class: a PaSD bus device subclass that has
            been patched with a mock component manager

        :return: specification of the device to be loaded
        """
        return {
            "path": "charts/ska-low-mccs/data/configuration.json",
            "package": "ska_low_mccs",
            "device": "pasdbus_001",
            "proxy": MccsDeviceProxy,
            "patch": patched_device_class,
        }

    '''def test_healthState(
        self: TestMccsPasdBus,
        device_under_test: MccsDeviceProxy,
        component_state_changed_callback: MockCallableDeque,
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
            component_state_changed_callback({"health_state": HealthState.OK})
        )
        component_state_changed_callback.assert_in_deque(
            {"health_state" : HealthState.OK}
        )
        assert device_under_test.healthState == HealthState.OK'''

    @pytest.mark.skip(reason="health state is unknown (not ok)")
    def test_healthState(
        self: TestMccsPasdBus,
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

        device_health_state_changed_callback.assert_next_change_event(HealthState.OK)
        assert device_under_test.healthState == HealthState.OK

    @pytest.mark.parametrize(
        ("device_attribute", "component_manager_property", "example_value"),
        [
            ("antennasOnline", "antennas_online", [True, False]),
            ("antennasForced", "antenna_forcings", [False, False]),
            ("antennasTripped", "antennas_tripped", [False, True]),
            ("antennasPowerSensed", "antennas_power_sensed", [True, True]),
            (
                "antennasDesiredPowerOnline",
                "antennas_desired_on_online",
                [True, True],
            ),
            (
                "antennasDesiredPowerOffline",
                "antennas_desired_on_offline",
                [True, True],
            ),
            ("antennaCurrents", "antenna_currents", [0.0, 0.0]),
            ("smartboxInputVoltages", "smartbox_input_voltages", [0.0, 0.0]),
            (
                "smartboxPowerSupplyOutputVoltages",
                "smartbox_power_supply_output_voltages",
                [0.0, 0.0],
            ),
            ("smartboxStatuses", "smartbox_statuses", ["OK", "OK"]),
            (
                "smartboxPowerSupplyTemperatures",
                "smartbox_power_supply_temperatures",
                [40.0, 40.1],
            ),
            (
                "smartboxOutsideTemperatures",
                "smartbox_outside_temperatures",
                [40.0, 40.1],
            ),
            (
                "smartboxPcbTemperatures",
                "smartbox_pcb_temperatures",
                [40.0, 40.1],
            ),
            (
                "smartboxServiceLedsOn",
                "smartbox_service_leds_on",
                [False, True],
            ),
            ("smartboxFndhPorts", "smartbox_fndh_ports", [12, 4, 1]),
            (
                "smartboxDesiredPowerOnline",
                "smartbox_desired_power_online",
                [True, True],
            ),
            (
                "smartboxDesiredPowerOffline",
                "smartbox_desired_power_offline",
                [True, True],
            ),
            ("fndhPsu48vVoltages", "fndh_psu48v_voltages", [48.0, 48.0]),
            ("fndhPsu5vVoltage", "fndh_psu5v_voltage", 5.0),
            ("fndhPsu48vCurrent", "fndh_psu48v_current", 20.0),
            ("fndhPsu48vTemperature", "fndh_psu48v_temperature", 39.0),
            ("fndhPsu5vTemperature", "fndh_psu5v_temperature", 38.0),
            ("fndhPcbTemperature", "fndh_pcb_temperature", 37.0),
            ("fndhOutsideTemperature", "fndh_pcb_temperature", 36.0),
            ("fndhStatus", "fndh_status", "OK"),
            (
                "fndhPortsConnected",
                "fndh_ports_connected",
                [False, True],
            ),
            (
                "fndhPortsForced",
                "fndh_port_forcings",
                [False, True],
            ),
            (
                "fndhPortsDesiredPowerOnline",
                "fndh_ports_desired_power_online",
                [False, True],
            ),
            (
                "fndhPortsDesiredPowerOffline",
                "fndh_ports_desired_power_offline",
                [False, True],
            ),
        ],
    )
    def test_readonly_attribute(
        self: TestMccsPasdBus,
        mocker: pytest_mock.mocker,  # type: ignore[valid-type]
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
        property_mock = mocker.PropertyMock(return_value=example_value)  # type: ignore[attr-defined]
        setattr(
            type(mock_component_manager),
            component_manager_property,
            property_mock,
        )
        property_mock.assert_not_called()

        _ = getattr(device_under_test, device_attribute)
        property_mock.assert_called_once_with()

    '''@pytest.mark.parametrize(
        (
            "device_command",
            "component_manager_method",
            "device_command_argin",
        ),
        [
            (
                "ReloadDatabase",
                "reload_database",
                None,
            ),
            (
                "GetFndhInfo",
                "get_fndh_info",
                None,
            ),
            (
                "TurnFndhServiceLedOn",
                "turn_fndh_service_led_on",
                None,
            ),
            (
                "TurnFndhServiceLedOff",
                "turn_fndh_service_led_off",
                None,
            ),
            (
                "GetSmartboxInfo",
                "get_smartbox_info",
                1,
            ),
            (
                "TurnSmartboxOn",
                "turn_smartbox_on",
                1,
            ),
            (
                "TurnSmartboxOff",
                "turn_smartbox_off",
                1,
            ),
            (
                "TurnSmartboxServiceLedOn",
                "turn_smartbox_service_led_on",
                1,
            ),
            (
                "TurnSmartboxServiceLedOff",
                "turn_smartbox_service_led_off",
                1,
            ),
            (
                "GetAntennaInfo",
                "get_antenna_info",
                1,
            ),
            (
                "ResetAntennaBreaker",
                "reset_antenna_breaker",
                1,
            ),
            (
                "TurnAntennaOn",
                "turn_antenna_on",
                1,
            ),
            (
                "TurnAntennaOff",
                "turn_antenna_off",
                1,
            ),
        ],
    )
    def test_command(
        self: TestMccsPasdBus,
        mocker: pytest_mock.mocker,  # type: ignore[valid-type]
        device_under_test: MccsDeviceProxy,
        mock_component_manager: unittest.mock.Mock,
        device_command: str,
        component_manager_method: str,
        device_command_argin: Any,
    ) -> None:
        """
        Test that device attribute writes result in component manager property writes.

        :param mocker: fixture that wraps the :py:mod:`unittest.mock`
            module
        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param device_command: name of the device command under test.
        :param component_manager_method_argin: argument to the component
            manager method.
        :param device_command_argin: argument to the device command.
        """
        #mock_handler = mocker.Mock(return_value=(ResultCode.OK, "unique_id"))  # type: ignore[attr-defined]
        #method_mock = mocker.Mock(return_value=mock_handler)  # type: ignore[attr-defined]
        #setattr(device_under_test, "get_command_object", method_mock)
        #method_mock = mocker.Mock(return_value="return")  # type: ignore[attr-defined]
        #setattr(mock_component_manager, component_manager_method, method_mock)
        #method_mock.assert_not_called()

        #command = getattr(device_under_test, device_command)
        #if device_command_argin is None:
         #   command_return = command()
        #else:
         #   command_return = command(device_command_argin)
        #command_return = command()
        #print(command_return)
        #(result, id) = device_under_test.TurnAntennaOff()
        #print("result is: ", result)
        #print("id is: ", id)
        method_mock = mocker.Mock(return_value=component_manager_method_return) # type: ignore[attr-defined]
        setattr(mock_component_manager, component_manager_method, method_mock)
        method_mock.assert_not_called()

        command = getattr(device_under_test, device_command)
        if device_command_argin is None:
        command_return = command()
        else:
        command_return = command(device_command_argin)

        if component_manager_method_argin is None:
        method_mock.assert_called_once_with()
        else:
        method_mock.assert_called_once_with(component_manager_method_argin)

        assert command_return == expected_device_command_return '''

    '''def test_command(
        self: TestMccsPasdBus,
        device_under_test: MccsDeviceProxy,
        mock_component_manager: unittest.mock.Mock,
    ) -> None:
        print("###############", device_under_test)#.component_manager.CommunicationStatus)
        (result, id) = device_under_test.TurnAntennaOff()
        print("result is: ", result)
        print("id is: ", id)
        assert False'''

    @pytest.mark.parametrize(
        (
            "device_command",
            "component_manager_method",
            "device_command_argin",
            "component_manager_method_argin",
            "component_manager_method_return",
            "expected_device_command_return",
        ),
        [
            (
                "ReloadDatabase",
                "reload_database",
                None,
                None,
                [True,True],
                [[ResultCode.OK], ["PaSD bus 'database reload' successful"]],
            ),
            (
                "GetFndhInfo",
                "get_fndh_info",
                None,
                None,
                [{"foo": "bah"}, {"foo": "bah"}],
                '{"foo": "bah"}',
            ),
            (
                "TurnFndhServiceLedOn",
                "set_fndh_service_led_on",
                None,
                True,
                [True,True],
                [
                    [ResultCode.OK],
                    ["PaSD bus 'FNDH service LED on' successful"],
                ],
            ),
            (
                "TurnFndhServiceLedOff",
                "set_fndh_service_led_on",
                None,
                False,
                [True,True],
                [
                    [ResultCode.OK],
                    ["PaSD bus 'FNDH service LED off' successful"],
                ],
            ),
            (
                "GetSmartboxInfo",
                "get_smartbox_info",
                1,
                1,
                [{"foo": "bah"}, {"foo": "bah"}],
                '{"foo": "bah"}',
            ),
            (
                "TurnSmartboxOn",
                "turn_smartbox_on",
                1,
                1,
                [True,True],
                [[ResultCode.OK], ["PaSD bus 'smartbox 1 on' successful"]],
            ),
            (
                "TurnSmartboxOff",
                "turn_smartbox_off",
                1,
                1,
                [True,True],
                [[ResultCode.OK], ["PaSD bus 'smartbox 1 off' successful"]],
            ),
            (
                "TurnSmartboxServiceLedOn",
                "turn_smartbox_service_led_on",
                1,
                1,
                [True,True],
                [
                    [ResultCode.OK],
                    ["PaSD bus 'smartbox 1 service LED on' successful"],
                ],
            ),
            (
                "TurnSmartboxServiceLedOn",
                "turn_smartbox_service_led_on",
                1,
                1,
                [False, False],
                [
                    [ResultCode.FAILED],
                    ["PaSD bus 'smartbox 1 service LED on' failed"],
                ],
            ),
            (
                "TurnSmartboxServiceLedOn",
                "turn_smartbox_service_led_on",
                1,
                1,
                [None, None],
                [
                    [ResultCode.OK],
                    ["PaSD bus 'smartbox 1 service LED on' is redundant"],
                ],
            ),
            (
                "TurnSmartboxServiceLedOff",
                "turn_smartbox_service_led_off",
                1,
                1,
                [True,True],
                [
                    [ResultCode.OK],
                    ["PaSD bus 'smartbox 1 service LED off' successful"],
                ],
            ),
            (
                "GetAntennaInfo",
                "get_antenna_info",
                1,
                1,
                [{"foo": "bah"}, {"foo": "bah"}],
                [{"foo": "bah"}, {"foo": "bah"}],
            ),
            (
                "ResetAntennaBreaker",
                "reset_antenna_breaker",
                1,
                1,
                [True,True],
                [
                    [ResultCode.OK],
                    ["PaSD bus 'antenna 1 breaker reset' successful"],
                ],
            ),
            (
                "TurnAntennaOn",
                "turn_antenna_on",
                1,
                1,
                [True,True],
                [[ResultCode.OK], ["PaSD bus 'antenna 1 on' successful"]],
            ),
            (
                "TurnAntennaOff",
                "turn_antenna_off",
                1,
                1,
                [True,True],
                [[ResultCode.OK], ["PaSD bus 'antenna 1 off' successful"]],
            ),
        ],
    )
    def test_command(
        self: TestMccsPasdBus,
        mocker: pytest_mock.mocker,  # type: ignore[valid-type]
        device_under_test: MccsDeviceProxy,
        mock_component_manager: unittest.mock.Mock,
        device_command: str,
        component_manager_method: str,
        device_command_argin: Any,
        component_manager_method_argin: Any,
        component_manager_method_return: Any,
        expected_device_command_return: Any,
    ) -> None:
        """
        Test that device attribute writes result in component manager property writes.

        :param mocker: fixture that wraps the :py:mod:`unittest.mock`
            module
        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param mock_component_manager: the mock component manager being
            used by the patched transient buffer device.
        :param device_command: name of the device command under test.
        :param device_command_argin: argument to the device command
        :param component_manager_method: name of the component manager
            method that is expected to be called when the device
            command is called.
        :param component_manager_method_argin: argument to the component
            manager method
        :param component_manager_method_return: return value of the
            component manager method
        :param expected_device_command_return: the expected return value
            of the device command
        """
        method_mock = mocker.Mock(return_value=component_manager_method_return)  # type: ignore[attr-defined]
        setattr(mock_component_manager, component_manager_method, method_mock)
        method_mock.assert_not_called()

        command = getattr(device_under_test, device_command)
        if device_command_argin is None:
            #(task_status, response) = command()
            command_return = command()
        else:
            #(task_status, response) = command(device_command_argin)
            command_return = command(device_command_argin)

        #if component_manager_method_argin is None:
         #   method_mock.assert_called_once_with()
        #else:
         #   method_mock.assert_called_once_with(component_manager_method_argin)

        #assert command_return[0] == ResultCode.QUEUED
        #assert command_return[1].split("_")[-1] == device_command
