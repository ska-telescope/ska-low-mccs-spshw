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
from ska.low.mccs import MccsDeviceProxy, MccsSubarray, release
from ska.low.mccs.utils import call_with_json


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
        "package": "ska.low.mccs",
        "device": "subarray_01",
        "proxy": MccsDeviceProxy,
    }


@pytest.fixture()
def mock_factory(mocker):
    """
    Fixture that provides a mock factory for device proxy mocks. This
    default factory provides vanilla mocks, but this fixture can be
    overridden by test modules/classes to provide mocks with specified
    behaviours.

    :param mocker: the pytest `mocker` fixture is a wrapper around the
        `unittest.mock` package
    :type mocker: :py:class:`pytest_mock.mocker`

    :return: a factory for device proxy mocks
    :rtype: :py:class:`unittest.mock.Mock` (the class itself, not an
        instance)
    """
    _values = {"healthState": HealthState.UNKNOWN, "adminMode": AdminMode.ONLINE}

    def _mock_attribute(name, *args, **kwargs):
        """
        Returns a mock of a :py:class:`tango.DeviceAttribute` instance,
        for a given attribute name.

        :param name: name of the attribute
        :type name: str
        :param args: positional args to the
            :py:meth:`tango.DeviceProxy.read_attribute` method patched
            by this mock factory
        :type args: list
        :param kwargs: named args to the
            :py:meth:`tango.DeviceProxy.read_attribute` method patched
            by this mock factory
        :type kwargs: dict

        :return: a basic mock for a :py:class:`tango.DeviceAttribute`
            instance, with name, value and quality values
        :rtype: :py:class:`unittest.mock.Mock`
        """
        mock = mocker.Mock()
        mock.name = name
        mock.value = _values.get(name, "MockValue")
        mock.quality = "MockQuality"
        return mock

    def _mock_device():
        """
        Returns a mock for a :py:class:`tango.DeviceProxy` instance,
        with its :py:meth:`tango.DeviceProxy.read_attribute` method
        mocked to return :py:class:`tango.DeviceAttribute` mocks.

        :return: a basic mock for a :py:class:`tango.DeviceProxy`
            instance,
        :rtype: :py:class:`unittest.mock.Mock`
        """
        mock = mocker.Mock()
        mock.read_attribute.side_effect = _mock_attribute
        return mock

    return _mock_device


# pylint: disable=invalid-name
class TestMccsSubarray:
    """
    Test class for MccsSubarray tests.
    """

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

            def _subarray_mock():
                """
                Sets up a mock for a :py:class:`tango.DeviceProxy` that
                connects to an
                :py:class:`~ska.low.mccs.subarray.MccsSubarray` device.
                The returned mock will respond suitably to
                :py:meth:`~ska_tango_base.SKASubarray.AssignResources`
                and
                :py:meth:`~ska_tango_base.SKASubarray.ReleaseResources`
                and
                :py:meth:`~ska_tango_base.SKASubarray.Configure`
                commands.

                :return: a mock for a :py:class:`tango.DeviceProxy` that
                    connects to an
                    :py:class:`~ska.low.mccs.subarray.MccsSubarray`
                    device.
                :rtype: :py:class:`unittest.mock.Mock`
                """
                mock_subarray = mock_factory()
                mock_subarray.On.return_value = (
                    ResultCode.OK,
                    MccsSubarray.OnCommand.SUCCEEDED_MESSAGE,
                )
                mock_subarray.AssignResources.return_value = (
                    ResultCode.OK,
                    MccsSubarray.AssignResourcesCommand.SUCCEEDED_MESSAGE,
                )
                mock_subarray.Configure.return_value = (
                    ResultCode.OK,
                    MccsSubarray.ConfigureCommand.SUCCEEDED_MESSAGE,
                )
                mock_subarray.ReleaseResources.return_value = (
                    ResultCode.OK,
                    MccsSubarray.ReleaseResourcesCommand.SUCCEEDED_MESSAGE,
                )
                mock_subarray.ReleaseAllResources.return_value = (
                    ResultCode.OK,
                    MccsSubarray.ReleaseAllResourcesCommand.SUCCEEDED_MESSAGE,
                )
                mock_subarray.Off.return_value = (
                    ResultCode.OK,
                    "Subarray switched off",
                )
                return mock_subarray

            def _station_mock():
                """
                Sets up a mock for a :py:class:`tango.DeviceProxy` that
                connects to an
                :py:class:`~ska.low.mccs.station.MccsStation` device.
                The returned mock will respond suitably to actions taken
                on it by the controller as part of the controller's
                :py:meth:`~.mccs.controller.controller_device.MccsController.Allocate`
                and
                :py:meth:`~.mccs.controller.controller_device.MccsController.Release`
                commands.

                :return: a mock for a :py:class:`tango.DeviceProxy` that
                    connects to an
                    :py:class:`~ska.low.mccs.station.MccsStation`
                    device.
                :rtype: :py:class:`unittest.mock.Mock`
                """
                mock = mock_factory()
                mock.subarrayId = 0
                return mock

            def _subarraybeam_mock():
                """
                Sets up a mock for a :py:class:`tango.DeviceProxy` that
                connects to an :py:class:`~ska.low.mccs.subarray.MccsSubarrayBeam`
                device. The returned mock will respond suitably to
                actions taken on it by the subarray as part of the
                subarray's
                :py:meth:`~ska_tango_base.SKASubarray.Allocate` and
                :py:meth:`~ska_tango_base.SKASubarray.Release`
                commands.

                :return: a mock for a :py:class:`tango.DeviceProxy` that
                    connects to an
                    :py:class:`~ska.low.mccs.subarray.MccsSubarrayBeam` device.
                :rtype: :py:class:`unittest.mock.Mock`
                """
                mock = mock_factory()
                mock.healthState = HealthState.OK
                mock._update_rate = 0.0
                return mock

            return {
                "low-mccs/subarray/01": _subarray_mock(),
                "low-mccs/subarray/02": _subarray_mock(),
                "low-mccs/station/001": _station_mock(),
                "low-mccs/station/002": _station_mock(),
                "low-mccs/subarraybeam/01": _subarraybeam_mock(),
                "low-mccs/subarraybeam/02": _subarraybeam_mock(),
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
                stations=[station_fqdns[0]],
                subarray_beams=[subarray_beam_fqdn],
                channels=[[0, 8, 1, 1], [8, 8, 2, 1]],
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
                stations=station_fqdns,
                subarray_beams=[subarray_beam_fqdn],
                channels=[[0, 8, 1, 1], [8, 8, 2, 1]],
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
                stations=station_fqdns,
                subarray_beams=subarray_beam_fqdns,
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
                subarray_id=1,
                stations=[station_fqdns[1]],
                subarray_beams=[subarray_beam_fqdns[0]],
                channels=[[0, 8, 1, 1], [8, 8, 2, 1]],
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
                subarray_id=1,
                stations=[station_fqdns[0]],
                subarray_beams=[subarray_beam_fqdn],
                channels=[[0, 8, 1, 1], [8, 8, 2, 1]],
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
                subarray_id=1,
                stations=station_fqdns,
                subarray_beams=[subarray_beam_fqdn],
                channels=[[0, 8, 1, 1], [8, 8, 2, 1]],
            )
            assert result_code == ResultCode.OK
            assert message == MccsSubarray.AssignResourcesCommand.SUCCEEDED_MESSAGE
            assert sorted(device_under_test.stationFQDNs) == sorted(station_fqdns)
            assert mock_subarray_beam.stationIds == [1, 2]

            config_dict = {
                "stations": [{"station_id": 1}, {"station_id": 2}],
                "subarray_beams": [
                    {
                        "subarray_id": 1,
                        "subarray_beam_id": 1,
                        "station_ids": [1, 2],
                        "channels": [[0, 8, 1, 1], [8, 8, 2, 1]],
                        "update_rate": 3.14,
                        "sky_coordinates": [1585619550.0, 192.0, 2.0, 27.0, 1.0],
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
        mock._station_beam_pool_manager.scan.return_value = (None, "")
        scan_command = MccsSubarray.ScanCommand(mock, subarray_state_model)
        scan_args = {"id": 1, "scan_time": 4}
        json_str = json.dumps(scan_args)
        (result_code, message) = scan_command(json_str)
        assert result_code == ResultCode.STARTED
        assert message == f"Scan command STARTED - config {scan_args}"

        mock.reset_mock()
        failure_code = ResultCode.FAILED
        failure_message = "failure path unit test"
        mock._station_beam_pool_manager.scan.return_value = (
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
