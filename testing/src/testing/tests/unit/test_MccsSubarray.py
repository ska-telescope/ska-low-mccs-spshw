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
This module contains the tests for MccsSubarray.
"""
import json
import pytest

from tango import AttrQuality, EventType, DevState

from ska_tango_base import SKASubarrayStateModel
from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import (
    AdminMode,
    ControlMode,
    HealthState,
    ObsState,
    SimulationMode,
    TestMode,
)
from ska_low_mccs import MccsDeviceProxy, MccsSubarray, release
from ska_low_mccs.utils import call_with_json

from testing.harness.mock import MockDeviceBuilder, MockSubarrayBuilder


@pytest.fixture
def subarray_state_model(logger):
    """
    Yields a new SKASubarrayStateModel for testing.

    :param logger: the logger to be used by the object under test
    :type logger: :py:class:`logging.Logger`

    :return: a new SKASubarrayStateModel for testing
    :rtype: :py:class:`ska_tango_base.SKASubarrayStateModel`
    """
    return SKASubarrayStateModel(logger)


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
        "device": "subarray_01",
        "proxy": MccsDeviceProxy,
    }


@pytest.fixture()
def mock_factory(mocker):
    """
    Fixture that provides a mock factory for device proxy mocks. This default factory
    provides vanilla mocks, but this fixture can be overridden by test modules/classes
    to provide mocks with specified behaviours.

    :param mocker: the pytest `mocker` fixture is a wrapper around the
        `unittest.mock` package
    :type mocker: :py:class:`pytest_mock.mocker`

    :return: a factory for device proxy mocks
    :rtype: :py:class:`unittest.mock.Mock` (the class itself, not an
        instance)
    """
    builder = MockDeviceBuilder()
    builder.add_attribute("healthState", HealthState.UNKNOWN)
    builder.add_attribute("adminMode", AdminMode.ONLINE)
    return builder


# pylint: disable=invalid-name
class TestMccsSubarray:
    """
    Test class for MccsSubarray tests.
    """

    @pytest.fixture()
    def device_under_test(self, tango_harness):
        """
        Fixture that returns the device under test.

        :param tango_harness: a test harness for Tango devices

        :return: the device under test
        """
        return tango_harness.get_device("low-mccs/subarray/01")

    # tests of general methods
    def test_InitDevice(self, device_under_test):
        """
        Test for Initial state.

        :todo: Test for different memorized values of adminMode.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.healthState == HealthState.OK
        assert device_under_test.controlMode == ControlMode.REMOTE
        assert device_under_test.simulationMode == SimulationMode.FALSE
        assert device_under_test.testMode == TestMode.TEST
        assert device_under_test.assignedResources is None

        # The following reads might not be allowed in this state once
        # properly implemented
        assert device_under_test.scanId == -1
        assert list(device_under_test.configuredCapabilities) == ["BAND1:0", "BAND2:0"]
        assert device_under_test.stationFQDNs is None
        #         assert device_under_test.tileFQDNs is None
        #         assert device_under_test.stationBeamFQDNs is None
        assert device_under_test.activationTime == 0

    def test_healthState(self, device_under_test, mock_callback):
        """
        Test for healthState.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param mock_callback: a mock to pass as a callback
        :type mock_callback: :py:class:`unittest.mock.Mock`
        """
        # The device has neither hardware nor (yet) subsidiary devices,
        # so its healthState is OK
        assert device_under_test.healthState == HealthState.OK

        _ = device_under_test.subscribe_event(
            "healthState", EventType.CHANGE_EVENT, mock_callback
        )
        mock_callback.assert_called_once()

        event_data = mock_callback.call_args[0][0].attr_value
        assert event_data.name == "healthState"
        assert event_data.value == HealthState.OK
        assert event_data.quality == AttrQuality.ATTR_VALID

    def test_GetVersionInfo(self, device_under_test):
        """
        Test for GetVersionInfo.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        version_info = release.get_release_info(device_under_test.info().dev_class)
        assert device_under_test.GetVersionInfo() == [version_info]

    # tests of MccsSubarray commands
    def test_sendTransientBuffer(self, device_under_test):
        """
        Test for sendTransientBuffer.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        segment_spec = []
        returned = device_under_test.sendTransientBuffer(segment_spec)
        assert returned == [
            [ResultCode.OK],
            [MccsSubarray.SendTransientBufferCommand.SUCCEEDED_MESSAGE],
        ]

    # tests of overridden base class attributes
    def test_buildState(self, device_under_test):
        """
        Test for buildState.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        build_info = release.get_release_info()
        assert device_under_test.buildState == build_info

    def test_versionId(self, device_under_test):
        """
        Test for versionId.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.versionId == release.version

    # tests of MccsSubarray attributes
    def test_scanId(self, device_under_test):
        """
        Test for scanID attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.scanId == -1

    def test_stationFQDNs(self, device_under_test):
        """
        Test for stationFQDNs attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.stationFQDNs is None

    class TestAssignResourcesAndConfigure:
        """
        Class containing fixtures and tests of the MccsSubarray's
        :py:meth:`~ska_tango_base.SKASubarray.AssignResources` and
        :py:meth:`~ska_tango_base.SKASubarray.ReleaseResources` and
        :py:meth:`~ska_tango_base.SKASubarray.Configure` commands
        """

        @pytest.fixture()
        def initial_mocks(self, mock_factory):
            """
            Fixture that registers device proxy mocks prior to patching.
            The default fixture is overridden here to ensure that mock
            subarrays and stations respond suitably to actions taken on
            them as part of the controller's
            :py:meth:`~ska_tango_base.SKASubarray.AssignResources` and
            :py:meth:`~ska_tango_base.SKASubarray.ReleaseResources` and
            :py:meth:`~ska_tango_base.SKASubarray.Configure` commands

            :param mock_factory: a factory for
                :py:class:`tango.DeviceProxy` mocks
            :type mock_factory: object
            :return: a dictionary of mocks, keyed by FQDN
            :rtype: dict
            """

            mock_subarray_factory = MockSubarrayBuilder(mock_factory)

            mock_station_factory = MockDeviceBuilder(mock_factory)
            mock_station_factory.add_attribute("subarrayId", 0)

            mock_subarraybeam_factory = MockDeviceBuilder(mock_factory)
            mock_subarraybeam_factory.add_attribute("healthState", HealthState.OK)
            mock_subarraybeam_factory.add_attribute("updateRate", 0)

            return {
                "low-mccs/subarray/01": mock_subarray_factory(),
                "low-mccs/subarray/02": mock_subarray_factory(),
                "low-mccs/station/001": mock_station_factory(),
                "low-mccs/station/002": mock_station_factory(),
                "low-mccs/subarraybeam/01": mock_subarraybeam_factory(),
                "low-mccs/subarraybeam/02": mock_subarraybeam_factory(),
            }

        def test_AllocateResources(self, device_under_test, logger):
            """
            Test for AllocateResources.

            :param device_under_test: fixture that provides a
                :py:class:`tango.DeviceProxy` to the device under test, in a
                :py:class:`tango.test_context.DeviceTestContext`.
            :type device_under_test: :py:class:`tango.DeviceProxy`
            :param logger: the logger to be used by the object under test
            :type logger: :py:class:`logging.Logger`
            """
            station_fqdns = ["low-mccs/station/001", "low-mccs/station/002"]
            mock_station_1 = MccsDeviceProxy(station_fqdns[0], logger)
            subarray_beam_fqdn = "low-mccs/subarraybeam/01"
            mock_subarray_beam = MccsDeviceProxy(subarray_beam_fqdn, logger)

            device_under_test.On()
            assert mock_subarray_beam.healthState == HealthState.OK

            [[result_code], [message]] = call_with_json(
                device_under_test.AssignResources,
                subarray_id=1,
                stations=[[station_fqdns[0]]],
                subarray_beams=[subarray_beam_fqdn],
                channel_blocks=[2],
            )

            assert result_code == ResultCode.OK
            assert message == MccsSubarray.AssignResourcesCommand.SUCCEEDED_MESSAGE
            assert sorted(list(device_under_test.stationFQDNs)) == sorted(
                [station_fqdns[0]]
            )
            assert mock_subarray_beam.stationIds == [1]

            mock_station_1.InitialSetup.assert_called_once_with()

            device_under_test.ReleaseAllResources()
            assert mock_subarray_beam.stationIds == []

            # now assign station beam to both stations...
            device_under_test.On()
            [[result_code], [message]] = call_with_json(
                device_under_test.AssignResources,
                subarray_id=1,
                stations=[station_fqdns],
                subarray_beams=[subarray_beam_fqdn],
                channel_blocks=[2],
            )
            assert result_code == ResultCode.OK
            assert message == MccsSubarray.AssignResourcesCommand.SUCCEEDED_MESSAGE
            assert sorted(device_under_test.stationFQDNs) == sorted(station_fqdns)
            assert mock_subarray_beam.stationIds == [1, 2]

        def test_ReleaseAllResources(self, device_under_test, logger):
            """
            Test for ReleaseAllResources.

            :param device_under_test: fixture that provides a
                :py:class:`tango.DeviceProxy` to the device under test, in a
                :py:class:`tango.test_context.DeviceTestContext`.
            :type device_under_test: :py:class:`tango.DeviceProxy`
            :param logger: the logger to be used by the object under test
            :type logger: :py:class:`logging.Logger`
            """
            station_fqdns = ["low-mccs/station/001", "low-mccs/station/002"]
            mock_station_1 = MccsDeviceProxy(station_fqdns[0], logger)
            mock_station_2 = MccsDeviceProxy(station_fqdns[1], logger)
            subarray_beam_fqdns = [
                "low-mccs/subarraybeam/01",
                "low-mccs/subarraybeam/02",
            ]
            mock_subarray_beam_1 = MccsDeviceProxy(subarray_beam_fqdns[0], logger)
            mock_subarray_beam_2 = MccsDeviceProxy(subarray_beam_fqdns[1], logger)

            device_under_test.On()
            [[result_code], [message]] = call_with_json(
                device_under_test.AssignResources,
                stations=[station_fqdns, station_fqdns],
                subarray_beams=subarray_beam_fqdns,
                channel_blocks=[2],
            )
            assert result_code == ResultCode.OK
            assert message == MccsSubarray.AssignResourcesCommand.SUCCEEDED_MESSAGE
            assert sorted(list(device_under_test.stationFQDNs)) == sorted(station_fqdns)

            mock_station_1.InitialSetup.assert_called_once_with()
            mock_station_2.InitialSetup.assert_called_once_with()

            assert mock_subarray_beam_1.stationIds == [1, 2]
            assert mock_subarray_beam_2.stationIds == [1, 2]

            [[result_code], [message]] = call_with_json(
                device_under_test.ReleaseResources,
                subarray_beam_fqdns=[subarray_beam_fqdns[0]],
            )
            assert result_code == ResultCode.OK
            assert message == MccsSubarray.ReleaseResourcesCommand.SUCCEEDED_MESSAGE

            assert mock_subarray_beam_1.stationIds == []
            assert mock_subarray_beam_2.stationIds == [1, 2]

            # reassign
            call_with_json(
                device_under_test.AssignResources,
                stations=[[station_fqdns[1]]],
                subarray_beams=[subarray_beam_fqdns[0]],
                channel_blocks=[2],
            )
            assert mock_subarray_beam_1.stationIds == [2]

            # ReleaseAll again
            [[result_code], [message]] = device_under_test.ReleaseAllResources()
            assert result_code == ResultCode.OK
            assert message == MccsSubarray.ReleaseAllResourcesCommand.SUCCEEDED_MESSAGE

            assert mock_subarray_beam_1.stationIds == []
            assert mock_subarray_beam_2.stationIds == []

        def test_configure(self, device_under_test, logger):
            """
            Test for Configure.

            :param device_under_test: fixture that provides a
                :py:class:`tango.DeviceProxy` to the device under test, in a
                :py:class:`tango.test_context.DeviceTestContext`.
            :type device_under_test: :py:class:`tango.DeviceProxy`
            :param logger: the logger to be used by the object under test
            :type logger: :py:class:`logging.Logger`
            """
            station_fqdns = ["low-mccs/station/001", "low-mccs/station/002"]
            mock_station_1 = MccsDeviceProxy(station_fqdns[0], logger)
            subarray_beam_fqdn = "low-mccs/subarraybeam/01"
            mock_subarray_beam = MccsDeviceProxy(subarray_beam_fqdn, logger)

            device_under_test.On()
            assert mock_subarray_beam.healthState == HealthState.OK

            [[result_code], [message]] = call_with_json(
                device_under_test.AssignResources,
                stations=[[station_fqdns[0]]],
                subarray_beams=[subarray_beam_fqdn],
                channel_blocks=[2],
            )

            assert result_code == ResultCode.OK
            assert message == MccsSubarray.AssignResourcesCommand.SUCCEEDED_MESSAGE
            assert sorted(list(device_under_test.stationFQDNs)) == [station_fqdns[0]]

            assert mock_subarray_beam.stationIds == [1]

            mock_station_1.InitialSetup.assert_called_once_with()

            device_under_test.ReleaseAllResources()
            assert mock_subarray_beam.stationIds == []

            # now assign station beam to both stations...
            device_under_test.On()
            [[result_code], [message]] = call_with_json(
                device_under_test.AssignResources,
                stations=[station_fqdns],
                subarray_beams=[subarray_beam_fqdn],
                channel_blocks=[2],
            )
            assert result_code == ResultCode.OK
            assert message == MccsSubarray.AssignResourcesCommand.SUCCEEDED_MESSAGE
            assert sorted(device_under_test.stationFQDNs) == sorted(station_fqdns)
            assert mock_subarray_beam.stationIds == [1, 2]

            config_dict = {
                "stations": [{"station_id": 1}, {"station_id": 2}],
                "subarray_beams": [
                    {
                        "subarray_beam_id": 1,
                        "station_ids": [1, 2],
                        "channels": [[0, 8, 1, 1], [8, 8, 2, 1]],
                        "update_rate": 3.14,
                        "sky_coordinates": [1585619550.0, 192.0, 2.0, 27.0, 1.0],
                        "antenna_weights": [1.0, 1.0, 1.0],
                        "phase_centre": [0.0, 0.0],
                    }
                ],
            }
            json_str = json.dumps(config_dict)
            expected = config_dict["subarray_beams"][0]
            [[result_code], [message]] = device_under_test.Configure(json_str)
            assert result_code == ResultCode.OK
            assert message == MccsSubarray.ConfigureCommand.SUCCEEDED_MESSAGE
            assert device_under_test.obsState == ObsState.READY

            # remove preceeding "call(\" and trailing "\)"
            output = str(mock_subarray_beam.configure.call_args)[6:-2]
            assert json.loads(output) == expected


# pylint: disable=invalid-name
class TestMccsSubarrayCommandClasses:
    """
    This class contains tests of MCCSSubarray command classes.
    """

    def test_ScanCommand(self, subarray_state_model, mocker):
        """
        Test for MCCSSubarray.Scan()

        :param subarray_state_model: the state model that this test uses
            to check that it is allowed to run, and that it drives
            with actions.
        :type subarray_state_model:
            :py:class:`ska_tango_base.SKASubarrayStateModel`
        :param mocker: the pytest `mocker` fixture is a wrapper around
            the `unittest.mock` package
        :type mocker: :py:class:`pytest_mock.mocker`
        """
        subarray_state_model._straight_to_state(
            op_state=DevState.ON, admin_mode=AdminMode.ONLINE, obs_state=ObsState.READY
        )
        mock = mocker.Mock()
        mock._subarray_beam_resource_manager.scan.return_value = (None, "")
        scan_command = MccsSubarray.ScanCommand(mock, subarray_state_model)
        scan_args = {"scan_id": 1, "scan_time": 4}
        json_str = json.dumps(scan_args)
        (result_code, message) = scan_command(json_str)
        assert result_code == ResultCode.STARTED
        assert message == f"Scan command STARTED - config {scan_args}"

        mock.reset_mock()
        failure_code = ResultCode.FAILED
        failure_message = "failure path unit test"
        mock._subarray_beam_resource_manager.scan.return_value = (
            failure_code,
            failure_message,
        )
        subarray_state_model._straight_to_state(
            op_state=DevState.ON, admin_mode=AdminMode.ONLINE, obs_state=ObsState.READY
        )
        scan_command = MccsSubarray.ScanCommand(mock, subarray_state_model)
        (result_code, message) = scan_command(json_str)
        assert result_code == failure_code
        assert message == failure_message

    def test_AbortCommand(self, subarray_state_model):
        """
        Test for MCCSSubarray.Abort()

        :param subarray_state_model: the state model that this test uses
            to check that it is allowed to run, and that it drives
            with actions.
        :type subarray_state_model:
            :py:class:`ska_tango_base.SKASubarrayStateModel`
        """
        subarray_state_model._straight_to_state(
            op_state=DevState.ON,
            admin_mode=AdminMode.ONLINE,
            obs_state=ObsState.SCANNING,
        )
        abort_command = MccsSubarray.AbortCommand(self, subarray_state_model)
        (result_code, message) = abort_command()
        assert result_code == ResultCode.OK
        assert message == MccsSubarray.AbortCommand.SUCCEEDED_MESSAGE

    def test_ObsResetCommand(self, subarray_state_model, mocker):
        """
        Test for MCCSSubarray.ObsReset()

        :param subarray_state_model: the state model that this test uses
            to check that it is allowed to run, and that it drives
            with actions.
        :type subarray_state_model:
            :py:class:`ska_tango_base.SKASubarrayStateModel`
        :param mocker: the pytest `mocker` fixture is a wrapper around
            the `unittest.mock` package
        :type mocker: :py:class:`pytest_mock.mocker`
        """
        subarray_state_model._straight_to_state(
            op_state=DevState.ON,
            admin_mode=AdminMode.ONLINE,
            obs_state=ObsState.ABORTED,
        )
        mock = mocker.Mock()
        obsreset_command = MccsSubarray.ObsResetCommand(mock, subarray_state_model)
        (result_code, message) = obsreset_command()
        assert result_code == ResultCode.OK
        assert message == MccsSubarray.ObsResetCommand.SUCCEEDED_MESSAGE
