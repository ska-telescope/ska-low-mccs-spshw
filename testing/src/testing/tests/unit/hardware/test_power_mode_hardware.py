# type: ignore
########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
########################################################################
"""
This module contains the tests for the
:py:mod:`ska_low_mccs.hardware.power_mode_hardware` module.
"""
from contextlib import nullcontext

import pytest

from ska_tango_base.control_model import HealthState
from ska_low_mccs.hardware import (
    ConnectionStatus,
    OnOffHardwareSimulator,
    OnStandbyHardwareSimulator,
    OnStandbyOffHardwareSimulator,
    OnStandbyOffHardwareManager,
    PowerMode,
)


class TestPowerModeHardware:
    """
    Contains tests of the hardware classes that support `off`, `standby` and `on` modes:

    * :py:class:`ska_low_mccs.hardware.power_mode_hardware.OnOffHardwareSimulator`
    * :py:class:`ska_low_mccs.hardware.power_mode_hardware.OnStandbyHardwareSimulator`
    * :py:class:`ska_low_mccs.hardware.power_mode_hardware.OnStandbyOffHardwareSimulator`
    * :py:class:`ska_low_mccs.hardware.power_mode_hardware.OnOffHardwareManager`
    """

    @pytest.fixture()
    def hardware_driver(self, request):
        """
        Fixture that returns a hardware driver (actually a simulator for testing
        purposes)

        :param request: A pytest object giving access to the requesting test
            context.
        :type request: :py:class:`pytest.FixtureRequest`

        :return: a hardware simulator
        :rtype: :py:class:`~ska_low_mccs.hardware.power_mode_hardware.OnOffHardwareSimulator`
        """
        return OnStandbyOffHardwareSimulator(power_mode=PowerMode.OFF)

    @pytest.fixture()
    def hardware_simulator(self, request):
        """
        Fixture that returns a hardware simulator for testing.

        :param request: A pytest object giving access to the requesting test
            context.
        :type request: :py:class:`pytest.FixtureRequest`
        :return: a hardware simulator
        :rtype: :py:class:`~ska_low_mccs.hardware.power_mode_hardware.OnOffHardwareSimulator`
        """
        parameters = getattr(request, "param", None)
        if parameters is None:
            return OnOffHardwareSimulator(power_mode=PowerMode.OFF)

        return parameters[0](
            is_connectible=parameters[1],
            fail_connect=parameters[2],
            power_mode=parameters[3],
        )

    @pytest.fixture()
    def hardware_manager(self, hardware_factory, hardware_health_evaluator):
        """
        Fixture that returns an
        :py:class:`~ska_low_mccs.hardware.power_mode_hardware.OnOffHardwareManager` for testing

        :param hardware_factory: the hardware driver factory used by
            this hardware manager
        :type hardware_factory:
            :py:class:`~ska_low_mccs.hardware.base_hardware.HardwareFactory`
        :param hardware_health_evaluator: the hardware health evaluator
            used by this hardware manager
        :type hardware_health_evaluator:
            :py:class:`ska_low_mccs.hardware.base_hardware.HardwareHealthEvaluator`

        :return: a hardware manager
        :rtype: :py:class:`~ska_low_mccs.hardware.power_mode_hardware.OnOffHardwareManager`
        """
        return OnStandbyOffHardwareManager(hardware_factory, hardware_health_evaluator)

    class TestHardwareSimulator:
        """
        This class contains the tests for the OnOffHardwareSimulator class.

        (The OnOffHardwareSimulator class is a software representation
        of hardware that can be turned on and off.)
        """

        @pytest.mark.parametrize(
            ("hardware_simulator", "connection_status", "power_mode"),
            [
                # We pass the test a hardware simulator that has been
                # initialised with the first element of this triple, and
                # test that its connection status is that of the second
                # element, and its power mode is that of the third.
                #
                # For example,
                #     (
                #         (OnOffHardwareSimulator, True, False, PowerMode.OFF),
                #         True,
                #         PowerMode.OFF
                #     )
                # means:
                # * take a hardware simulator of class OnOffHardwareSimulator, which has
                #   has been initialised as connectible and not simulating connection
                #   failure, but turned off;
                #   and
                # * test that it behaves as though connected, but turned off
                (
                    (OnOffHardwareSimulator, False, False, PowerMode.OFF),
                    ConnectionStatus.NOT_CONNECTIBLE,
                    None,  # irrelevant
                ),
                (
                    (OnOffHardwareSimulator, False, False, PowerMode.ON),
                    ConnectionStatus.NOT_CONNECTIBLE,
                    None,  # irrelevant
                ),
                (
                    (OnOffHardwareSimulator, False, True, PowerMode.OFF),
                    ConnectionStatus.NOT_CONNECTIBLE,
                    None,  # irrelevant
                ),
                (
                    (OnOffHardwareSimulator, False, True, PowerMode.ON),
                    ConnectionStatus.NOT_CONNECTIBLE,
                    None,  # irrelevant
                ),
                (
                    (OnStandbyHardwareSimulator, False, False, PowerMode.STANDBY),
                    ConnectionStatus.NOT_CONNECTIBLE,
                    None,  # irrelevant
                ),
                (
                    (OnStandbyHardwareSimulator, False, False, PowerMode.ON),
                    ConnectionStatus.NOT_CONNECTIBLE,
                    None,  # irrelevant
                ),
                (
                    (OnStandbyHardwareSimulator, False, True, PowerMode.STANDBY),
                    ConnectionStatus.NOT_CONNECTIBLE,
                    None,  # irrelevant
                ),
                (
                    (OnStandbyHardwareSimulator, False, True, PowerMode.ON),
                    ConnectionStatus.NOT_CONNECTIBLE,
                    None,  # irrelevant
                ),
                (
                    (OnStandbyOffHardwareSimulator, False, False, PowerMode.OFF),
                    ConnectionStatus.NOT_CONNECTIBLE,
                    None,  # irrelevant
                ),
                (
                    (OnStandbyOffHardwareSimulator, False, False, PowerMode.STANDBY),
                    ConnectionStatus.NOT_CONNECTIBLE,
                    None,  # irrelevant
                ),
                (
                    (OnStandbyOffHardwareSimulator, False, False, PowerMode.ON),
                    ConnectionStatus.NOT_CONNECTIBLE,
                    None,  # irrelevant
                ),
                (
                    (OnStandbyOffHardwareSimulator, False, True, PowerMode.OFF),
                    ConnectionStatus.NOT_CONNECTIBLE,
                    None,  # irrelevant
                ),
                (
                    (OnStandbyOffHardwareSimulator, False, True, PowerMode.STANDBY),
                    ConnectionStatus.NOT_CONNECTIBLE,
                    None,  # irrelevant
                ),
                (
                    (OnStandbyOffHardwareSimulator, False, True, PowerMode.ON),
                    ConnectionStatus.NOT_CONNECTIBLE,
                    None,  # irrelevant
                ),
                (
                    (OnOffHardwareSimulator, True, False, PowerMode.OFF),
                    ConnectionStatus.CONNECTED,
                    PowerMode.OFF,
                ),
                (
                    (OnOffHardwareSimulator, True, False, PowerMode.ON),
                    ConnectionStatus.CONNECTED,
                    PowerMode.ON,
                ),
                (
                    (OnOffHardwareSimulator, True, True, PowerMode.OFF),
                    ConnectionStatus.NOT_CONNECTED,
                    None,  # irrelevant
                ),
                (
                    (OnOffHardwareSimulator, True, True, PowerMode.ON),
                    ConnectionStatus.NOT_CONNECTED,
                    None,  # irrelevant
                ),
                (
                    (OnStandbyHardwareSimulator, True, False, PowerMode.STANDBY),
                    ConnectionStatus.CONNECTED,
                    PowerMode.STANDBY,
                ),
                (
                    (OnStandbyHardwareSimulator, True, False, PowerMode.ON),
                    ConnectionStatus.CONNECTED,
                    PowerMode.ON,
                ),
                (
                    (OnStandbyHardwareSimulator, True, True, PowerMode.STANDBY),
                    ConnectionStatus.NOT_CONNECTED,
                    None,  # irrelevant
                ),
                (
                    (OnStandbyHardwareSimulator, True, True, PowerMode.ON),
                    ConnectionStatus.NOT_CONNECTED,
                    None,  # irrelevant
                ),
                (
                    (OnStandbyOffHardwareSimulator, True, False, PowerMode.OFF),
                    ConnectionStatus.CONNECTED,
                    PowerMode.OFF,
                ),
                (
                    (OnStandbyOffHardwareSimulator, True, False, PowerMode.STANDBY),
                    ConnectionStatus.CONNECTED,
                    PowerMode.STANDBY,
                ),
                (
                    (OnStandbyOffHardwareSimulator, True, False, PowerMode.ON),
                    ConnectionStatus.CONNECTED,
                    PowerMode.ON,
                ),
                (
                    (OnStandbyOffHardwareSimulator, True, True, PowerMode.OFF),
                    ConnectionStatus.NOT_CONNECTED,
                    None,  # irrelevant
                ),
                (
                    (OnStandbyOffHardwareSimulator, True, True, PowerMode.STANDBY),
                    ConnectionStatus.NOT_CONNECTED,
                    None,  # irrelevant
                ),
                (
                    (OnStandbyOffHardwareSimulator, True, True, PowerMode.ON),
                    ConnectionStatus.NOT_CONNECTED,
                    None,  # irrelevant
                ),
            ],
            indirect=("hardware_simulator",),
        )
        def test_init(self, hardware_simulator, connection_status, power_mode):
            """
            Test initialisation of this hardware simulator.

            :param hardware_simulator: the hardware simulator under test
            :type hardware_simulator:
                :py:class:`~ska_low_mccs.hardware.power_mode_hardware.OnOffHardwareSimulator`
            :param connection_status: the status of the simulated
                software-hardware connection
            :type connection_status:
                :py:class:`ska_low_mccs.hardware.base_hardware.ConnectionStatus`
            :param power_mode: the initial power mode of the hardware
            :type power_mode: :py:class:`ska_low_mccs.hardware.power_mode_hardware.PowerMode`
            """
            contexts = {
                ConnectionStatus.NOT_CONNECTIBLE: pytest.raises(
                    ConnectionError, match="Hardware is not currently connectible."
                ),
                ConnectionStatus.NOT_CONNECTED: pytest.raises(
                    ConnectionError, match="No connection to hardware"
                ),
                ConnectionStatus.CONNECTED: nullcontext(),
            }

            hardware_simulator.connect()

            assert hardware_simulator.connection_status == connection_status
            with contexts[connection_status]:
                assert hardware_simulator.power_mode == power_mode

        @pytest.mark.parametrize(
            ("hardware_simulator", "command_name", "expected_power_mode"),
            [
                # We pass the test a hardware simulator that has been
                # initialised with the first element of this triple, and
                # then test that when we call the command specified by
                # the second element, the resulting power mode is that
                # specified in the third element. Or, if the third
                # element is None, we expect an exception.
                #
                # For example,
                # (
                #     (OnOffHardwareSimulator, True, False, PowerMode.OFF),
                #     "on",
                #     PowerMode.ON
                # )
                # means:
                # * take a hardware simulator of class OnOffHardwareSimulator,
                #   which has been initialised as connectible and not simulating
                #   connection failure, but turned off; and
                # * test that when we call the "on" command, the power mode become ON
                (
                    (OnOffHardwareSimulator, True, False, PowerMode.OFF),
                    "off",
                    PowerMode.OFF,
                ),
                ((OnOffHardwareSimulator, True, False, PowerMode.OFF), "standby", None),
                (
                    (OnOffHardwareSimulator, True, False, PowerMode.OFF),
                    "on",
                    PowerMode.ON,
                ),
                (
                    (OnOffHardwareSimulator, True, False, PowerMode.ON),
                    "off",
                    PowerMode.OFF,
                ),
                ((OnOffHardwareSimulator, True, False, PowerMode.ON), "standby", None),
                (
                    (OnOffHardwareSimulator, True, False, PowerMode.ON),
                    "on",
                    PowerMode.ON,
                ),
                (
                    (OnStandbyHardwareSimulator, True, False, PowerMode.STANDBY),
                    "off",
                    None,
                ),
                (
                    (OnStandbyHardwareSimulator, True, False, PowerMode.STANDBY),
                    "standby",
                    PowerMode.STANDBY,
                ),
                (
                    (OnStandbyHardwareSimulator, True, False, PowerMode.STANDBY),
                    "on",
                    PowerMode.ON,
                ),
                ((OnStandbyHardwareSimulator, True, False, PowerMode.ON), "off", None),
                (
                    (OnStandbyHardwareSimulator, True, False, PowerMode.ON),
                    "standby",
                    PowerMode.STANDBY,
                ),
                (
                    (OnStandbyHardwareSimulator, True, False, PowerMode.ON),
                    "on",
                    PowerMode.ON,
                ),
                (
                    (OnStandbyOffHardwareSimulator, True, False, PowerMode.OFF),
                    "off",
                    PowerMode.OFF,
                ),
                (
                    (OnStandbyOffHardwareSimulator, True, False, PowerMode.OFF),
                    "standby",
                    PowerMode.STANDBY,
                ),
                (
                    (OnStandbyOffHardwareSimulator, True, False, PowerMode.OFF),
                    "on",
                    PowerMode.ON,
                ),
                (
                    (OnStandbyOffHardwareSimulator, True, False, PowerMode.STANDBY),
                    "off",
                    PowerMode.OFF,
                ),
                (
                    (OnStandbyOffHardwareSimulator, True, False, PowerMode.STANDBY),
                    "standby",
                    PowerMode.STANDBY,
                ),
                (
                    (OnStandbyOffHardwareSimulator, True, False, PowerMode.STANDBY),
                    "on",
                    PowerMode.ON,
                ),
                (
                    (OnStandbyOffHardwareSimulator, True, False, PowerMode.ON),
                    "off",
                    PowerMode.OFF,
                ),
                (
                    (OnStandbyOffHardwareSimulator, True, False, PowerMode.ON),
                    "standby",
                    PowerMode.STANDBY,
                ),
                (
                    (OnStandbyOffHardwareSimulator, True, False, PowerMode.ON),
                    "on",
                    PowerMode.ON,
                ),
            ],
            indirect=("hardware_simulator",),
        )
        def test_on_standby_off(
            self, hardware_simulator, command_name, expected_power_mode
        ):
            """
            Test that we can use the off, on and standby commands to transition
            simulator power mode, as delimited by the particular hardware simulator in
            use.

            :param hardware_simulator: the hardware simulator under
                test
            :type hardware_simulator:
                :py:class:`~ska_low_mccs.hardware.simulable_hardware.HardwareSimulator`
            :param command_name: name of the command under test
            :type command_name: str
            :param expected_power_mode: the expected power mode of the
                simulator after the command has been called, or None if
                the command is expected not to exist on the simulator
            :type expected_power_mode: str
            """
            hardware_simulator.connect()
            assert hardware_simulator.connection_status == ConnectionStatus.CONNECTED

            command = getattr(hardware_simulator, command_name, None)
            if expected_power_mode is None:
                assert command is None
            else:
                command()
                assert hardware_simulator.power_mode == expected_power_mode

    class TestOnStandbyOffHardwareManager:
        """
        This class contains the tests for the
        :py:class:`ska_low_mccs.hardware.power_mode_hardware.OnStandbyOffHardwareManager`
        class.
        """

        def test(self, hardware_driver, hardware_manager):
            """
            Test that.

            * the hardware can be turned off and on and to standby, when
              not failed
            * when the hardware fails and cannot be turned off and on
              and to standby, the hardware manager reports that failure

            :param hardware_driver: the hardware driver
            :type hardware_driver:
                :py:class:`~ska_low_mccs.hardware.base_hardware.HardwareDriver`
            :param hardware_manager: the hardware_manager under test
            :type hardware_manager:
                :py:class:`~ska_low_mccs.hardware.power_mode_hardware.OnStandbyOffHardwareManager`
            """
            assert hardware_manager.health == HealthState.UNKNOWN
            hardware_manager.poll()
            assert hardware_manager.health == HealthState.OK

            # check turning this healthy hardware off and on
            assert hardware_manager.power_mode == PowerMode.OFF
            assert hardware_manager.off() is None  # nothing to do
            assert hardware_manager.power_mode == PowerMode.OFF
            assert hardware_manager.standby()  # success
            assert hardware_manager.power_mode == PowerMode.STANDBY
            assert hardware_manager.standby() is None  # nothing to do
            assert hardware_manager.power_mode == PowerMode.STANDBY
            assert hardware_manager.on()  # success
            assert hardware_manager.power_mode == PowerMode.ON
            assert hardware_manager.on() is None  # nothing to do
            assert hardware_manager.power_mode == PowerMode.ON
            assert hardware_manager.off()  # success
            assert hardware_manager.power_mode == PowerMode.OFF

            # make this hardware fail. Check that health changes and
            # callback is called
            hardware_driver.simulate_connection_failure(True)
            # because this is an external event, the hardware manager won't
            # know about it until it polls
            hardware_manager.poll()
            assert hardware_manager.health == HealthState.FAILED

            # check that when turning hardware on fails, the hardware
            # manager reports failure through its return codes
            with pytest.raises(ConnectionError, match="No connection to hardware"):
                hardware_manager.on()
            with pytest.raises(ConnectionError, match="No connection to hardware"):
                hardware_manager.standby()
            with pytest.raises(ConnectionError, match="No connection to hardware"):
                hardware_manager.off()
            with pytest.raises(ConnectionError, match="No connection to hardware"):
                _ = hardware_manager.power_mode

            hardware_driver.simulate_connection_failure(False)
            hardware_manager.poll()
            assert hardware_manager.health == HealthState.OK
            assert hardware_manager.power_mode == PowerMode.OFF
