###############################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
###############################################################################
"""
This module contains the tests for MccsStation.
"""
import logging
import threading
import time

import json
import pytest
import tango
from tango import DevState

from ska.base import DeviceStateModel
from ska.base.commands import CommandError, ResultCode
from ska.base.control_model import (
    AdminMode,
    ControlMode,
    HealthState,
    SimulationMode,
    TestMode,
)
from ska.low.mccs import MccsStation, release
from ska.low.mccs.station import StationPowerManager

device_to_load = {
    "path": "charts/ska-low-mccs/data/configuration.json",
    "package": "ska.low.mccs",
    "device": "station_001",
}


class TestMccsStation:
    """
    Test class for MccsStation tests
    """

    def test_InitDevice(self, device_under_test):
        """
        Test for Initial state.
        A freshly initialised station device has no assigned resources

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.healthState == HealthState.UNKNOWN
        assert device_under_test.controlMode == ControlMode.REMOTE
        assert device_under_test.simulationMode == SimulationMode.FALSE
        assert device_under_test.testMode == TestMode.NONE

        # The following reads might not be allowed in this state once properly
        # implemented
        assert device_under_test.subarrayId == 0
        assert device_under_test.transientBufferFQDN == ""
        assert not device_under_test.isCalibrated
        assert not device_under_test.isConfigured
        assert device_under_test.calibrationJobId == 0
        assert device_under_test.daqJobId == 0
        assert device_under_test.dataDirectory == ""
        assert device_under_test.beamFQDNs is None
        assert list(device_under_test.delayCentre) == []
        assert device_under_test.calibrationCoefficients is None

        # check that initialisation leaves us in a state where turning
        # the device on doesn't put it into ALARM state
        device_under_test.On()
        assert device_under_test.state() == DevState.ON
        time.sleep(0.2)
        assert device_under_test.state() == DevState.ON

    def test_healthState(self, device_under_test, mocker):
        """
        Test for healthState

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param mocker: fixture that wraps unittest.Mock
        :type mocker: wrapper for :py:mod:`unittest.mock`
        """

        # The device has subscribed to healthState change events on
        # its subsidiary, but hasn't heard from them (because in unit
        # testing these devices are mocked out), so its healthState is
        # UNKNOWN
        assert device_under_test.healthState == HealthState.UNKNOWN

        # Test that polling is turned on and subscription yields an
        # event as expected
        mock_callback = mocker.Mock()
        _ = device_under_test.subscribe_event(
            "healthState", tango.EventType.CHANGE_EVENT, mock_callback
        )
        mock_callback.assert_called_once()

        event_data = mock_callback.call_args[0][0].attr_value
        assert event_data.name == "healthState"
        assert event_data.value == HealthState.UNKNOWN
        assert event_data.quality == tango.AttrQuality.ATTR_VALID

        mock_callback.reset_mock()

    # overridden base class attributes
    def test_buildState(self, device_under_test):
        """
        Test for buildState

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        build_info = release.get_release_info()
        assert device_under_test.buildState == build_info

    # overridden base class commands
    def test_GetVersionInfo(self, device_under_test):
        """
        Test for GetVersionInfo

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        version_info = release.get_release_info(device_under_test.info().dev_class)
        assert device_under_test.GetVersionInfo() == [version_info]

    def test_versionId(self, device_under_test):
        """
        Test for versionId

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.versionId == release.version

    # MccsStation attributes
    def test_subarrayId(self, device_under_test):
        """
        Test for subarrayId attribute

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        station = device_under_test  # to make test easier to read
        mock_tile_1 = tango.DeviceProxy("low-mccs/tile/0001")
        mock_tile_2 = tango.DeviceProxy("low-mccs/tile/0002")

        # These tiles are mock devices so we have to manually set their
        # initial states
        mock_tile_1.subarrayId = 0
        mock_tile_2.subarrayId = 0

        # check initial state
        assert station.subarrayId == 0
        assert mock_tile_1.subarrayId == 0
        assert mock_tile_2.subarrayId == 0

        # action under test
        station.subarrayId = 1

        # check
        assert station.subarrayId == 1
        assert mock_tile_1.subarrayId == 1
        assert mock_tile_2.subarrayId == 1

    def test_beamFQDNs(self, device_under_test):
        """
        Test for beamFQDNs attribute

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.beamFQDNs is None

    def test_transientBufferFQDN(self, device_under_test):
        """
        Test for transientBufferFQDN attribute

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.transientBufferFQDN == ""

    def test_delayCentre(self, device_under_test):
        """
        Test for delayCentre attribute. This is a messy test because
        there is some loss of floating-point precision during transfer,
        so you have to check approximate equality when reading back what
        you've written.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert list(device_under_test.delayCentre) == []

        # SETUP
        dummy_location = (-30.72113, 21.411128)
        float_format = "{:3.4f}"
        dummy_location_str = [float_format.format(x) for x in dummy_location]

        # RUN
        device_under_test.delayCentre = dummy_location
        delay_centre = device_under_test.delayCentre

        # CHECK
        delay_centre_str = [float_format.format(x) for x in delay_centre]
        assert delay_centre_str == dummy_location_str

    def test_calibrationCoefficients(self, device_under_test):
        """
        Test for calibrationCoefficients attribute

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.calibrationCoefficients is None

    def test_isCalibrated(self, device_under_test):
        """
        Test for isCalibrated attribute

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert not device_under_test.isCalibrated

    def test_isConfigured(self, device_under_test):
        """
        Test for isConfigured attribute

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert not device_under_test.isConfigured

    def test_calibrationJobId(self, device_under_test):
        """
        Test for calibrationJobId attribute

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.calibrationJobId == 0

    def test_daqJobId(self, device_under_test):
        """
        Test for daqJobId attributes

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.daqJobId == 0

    def test_dataDirectory(self, device_under_test):
        """
        Test for dataDirectory attribute

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.dataDirectory == ""

    def test_configure(self, device_under_test):
        """
        Test for configure command

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        config_dict = {"station_id": 1}
        json_str = json.dumps(config_dict)
        [[result_code], [message]] = device_under_test.configure(json_str)
        assert result_code == ResultCode.OK
        assert device_under_test.isConfigured is True


class TestStationPowerManager:
    """
    This class contains tests of the ska.low.mccs.station.StationPowerManager
    class
    """

    @pytest.fixture()
    def logger(self):
        """
        Fixture that returns a logger for the power manager under test
        (or its components) to use

        :return: a logger for the power manager under test to use
        :rtype: :py:class:`logging.Logger` or something that implements
            the same logging interface
        """
        return logging.getLogger()

    @pytest.fixture()
    def power_manager(self):
        """
        Fixture that returns a power manager with no subservient devices

        :return: a power manager with no hardware and no subservient
            devices
        :rtype: :py:class:`ska.low.mccs.power.PowerManager`

        """
        return StationPowerManager([])

    @pytest.fixture()
    def state_model(self, logger):
        """
        Fixture that returns a state model for the command under test to
        use

        :param logger: a logger for the state model to use
        :type logger: an instance of :py:class:`logging.Logger`, or
            an object that implements the same interface

        :return: a state model for the command under test to use
        :rtype: :py:class:`~ska.base.DeviceStateModel`
        """
        return DeviceStateModel(logger)

    def test_OnCommand(self, power_manager, state_model):
        """
        Test the working of the On command.

        Because the PowerManager and DeviceStateModel are thoroughly
        unit-tested elsewhere, here we just need to check that the On
        command drives them correctly. The scope of this test is: check
        that the On command is not allowed to run the state model is
        not in the OFF state; check that such attempts fail with no
        side-effects; check that On() command IS allowed to run when
        the state model is in the OFF state; check that running the
        On() command succeeds, and that the result is the state model
        moves to state ON, and the power manager thinks it is on.

        :param power_manager: a power manager with no subservient
            devices
        :type power_manager: :py:class:`ska.low.mccs.power.PowerManager`
        :param state_model: the state model for the device
        :type state_model: :py:class:`~ska.base.DeviceStateModel`
        """
        on_command = MccsStation.OnCommand(power_manager, state_model)
        assert not power_manager.is_on()

        # in all states except OFF, the on command is not permitted,
        # should not be allowed, should fail, should have no side-effect
        # There's no need to check them all though, as that is done in
        # the lmcbaseclasses testing. Let's just double-check DISABLE
        state_model._straight_to_state(
            admin_mode=AdminMode.ONLINE, op_state=DevState.DISABLE
        )

        assert not on_command.is_allowed()
        with pytest.raises(CommandError):
            on_command()

        assert not power_manager.is_on()
        assert state_model.op_state == DevState.DISABLE

        # now push to OFF, the state in which the On command IS allowed
        state_model._straight_to_state(
            admin_mode=AdminMode.ONLINE, op_state=DevState.OFF
        )

        assert on_command.is_allowed()
        assert on_command() == (ResultCode.OK, "On command completed OK")
        assert power_manager.is_on()
        assert state_model.op_state == DevState.ON

    def test_OffCommand(self, power_manager, state_model):
        """
        Test the working of the Off command.

        Because the PowerManager and DeviceStateModel are thoroughly
        unit-tested elsewhere, here we just need to check that the Off
        command drives them correctly. The scope of this test is: check
        that the Off command is not allowed to run if the state model is
        not in the ON state; check that such attempts fail with no
        side-effects; check that Off() command IS allowed to run when
        the state model is in the ON state; check that running the
        Off() command succeeds, and that the result is the state model
        moves to state OFF, and the power manager thinks it is off.

        :param power_manager: a power manager with no subservient
            devices
        :type power_manager: :py:class:`ska.low.mccs.power.PowerManager`
        :param state_model: the state model for the device
        :type state_model: :py:class:`~ska.base.DeviceStateModel`
        """
        off_command = MccsStation.OffCommand(power_manager, state_model)
        power_manager.on()
        assert power_manager.is_on()

        # The Off command is allowed in states DISABLE, STANDBY and ON.
        # It is disallowed in states INIT and FAULT.

        # There's no need to check them all though, as that is done in
        # the lmcbaseclasses testing. Let's just check that the command
        # is disallowed from FAULT, and allowed from STANDBY

        state_model._straight_to_state(
            admin_mode=AdminMode.ONLINE, op_state=DevState.FAULT
        )

        assert not off_command.is_allowed()
        with pytest.raises(CommandError):
            off_command()

        assert power_manager.is_on()
        assert state_model.op_state == DevState.FAULT

        # now push to STANDBY, a state in which the Off command IS
        # allowed
        state_model._straight_to_state(
            admin_mode=AdminMode.ONLINE, op_state=DevState.STANDBY
        )

        assert off_command.is_allowed()
        assert off_command() == (ResultCode.OK, "Off command completed OK")
        assert not power_manager.is_on()
        assert state_model.op_state == DevState.OFF


class TestMccsStation_InitCommand:
    """
    Contains the tests of :py:class:`~ska.low.mccs.MccsStation`'s
    :py:class:`~ska.low.mccs.MccsStation.InitCommand`.
    """

    class HangableInitCommand(MccsStation.InitCommand):
        """
        A subclass of InitCommand with the following properties that
        support testing:

        * A lock that, if acquired prior to calling the command, causes
          the command to hang until the lock is released
        * Call trace attributes that record which methods were called
        """

        def __init__(self, target, state_model, logger=None):
            """
            Create a new HangableInitCommand instance

            :param target: the object that this command acts upon; for
                example, the device for which this class implements the
                command
            :type target: object
            :param state_model: the state model that this command uses
                 to check that it is allowed to run, and that it drives
                 with actions.
            :type state_model: :py:class:`DeviceStateModel`
            :param logger: the logger to be used by this Command. If not
                provided, then a default module logger will be used.
            :type logger: a logger that implements the standard library
                logger interface
            """
            super().__init__(target, state_model, logger)
            self._hang_lock = threading.Lock()
            self._initialise_health_monitoring_called = False
            self._initialise_power_management_called = False

        def _initialise_health_monitoring(self, device, fqdns):
            """
            Initialise the health model for this device (overridden
            here to inject a call trace attribute).

            :param device: the device for which the health model is
                being initialised
            :type device: :py:class:`~ska.base.SKABaseDevice`
            :param fqdns: FQDNs of subservient devices
            :type fqdns: list of str
            """
            self._initialise_health_monitoring_called = True
            super()._initialise_health_monitoring(device, fqdns)
            with self._hang_lock:
                # hang until the hang lock is released
                pass

        def _initialise_power_management(self, device, fqdns):
            """
            Initialise the device's power manager (overridden here to
            inject a call trace attribute).

            :param device: the device for which power management is
                being initialised
            :type device: :py:class:`~ska.base.SKABaseDevice`
            :param fqdns: FQDNs of subservient devices
            :type fqdns: list of str
            """
            self._initialise_power_management_called = True
            super()._initialise_power_management(device, fqdns)

    def test_interrupt(self, mocker):
        """
        Test that the command's interrupt method will cause a running
        thread to stop prematurely

        :param mocker: fixture that wraps the :py:mod:`unittest.mock`
            module
        :type mocker: wrapper for :py:mod:`unittest.mock`
        """
        mock_device = mocker.MagicMock()
        mock_state_model = mocker.Mock()

        init_command = self.HangableInitCommand(mock_device, mock_state_model)

        with init_command._hang_lock:
            init_command()
            # we got the hang lock first, so the initialisation thread
            # will hang in health initialisation until we release it
            init_command.interrupt()

        init_command._thread.join()

        # now that we've released the hang lock, the thread can exit
        # its _initialise_health_monitoring, but before it enters its
        # _initialise_power_management, it will detect that it has been
        # interrupted, and return
        assert init_command._initialise_health_monitoring_called
        assert not init_command._initialise_power_management_called
