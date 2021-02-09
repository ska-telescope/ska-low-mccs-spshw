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

import tango
from tango import AttrQuality, EventType

from ska.base.control_model import (
    AdminMode,
    ControlMode,
    HealthState,
    ObsState,
    SimulationMode,
    TestMode,
)
from ska.base.commands import ResultCode
from ska.low.mccs import release
from ska.low.mccs.utils import call_with_json


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
    :type mocker: wrapper for :py:mod:`unittest.mock`

    :return: a factory for device proxy mocks
    :rtype: :py:class:`unittest.Mock` (the class itself, not an
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
        :rtype: :py:class:`unittest.Mock`
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
        :rtype: :py:class:`unittest.Mock`
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
        assert device_under_test.testMode == TestMode.NONE
        assert device_under_test.assignedResources is None

        # The following reads might not be allowed in this state once
        # properly implemented
        assert device_under_test.scanId == -1
        assert list(device_under_test.configuredCapabilities) == ["BAND1:0", "BAND2:0"]
        assert device_under_test.stationFQDNs is None
        #         assert device_under_test.tileFQDNs is None
        #         assert device_under_test.stationBeamFQDNs is None
        assert device_under_test.activationTime == 0

    def test_healthState(self, device_under_test, mocker):
        """
        Test for healthState.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param mocker: fixture that wraps unittest.Mock
        :type mocker: wrapper for :py:mod:`unittest.mock`
        """
        # The device has neither hardware nor (yet) subsidiary devices,
        # so its healthState is OK
        assert device_under_test.healthState == HealthState.OK

        # Test that polling is turned on and subscription yields an
        # event as expected
        mock_callback = mocker.Mock()
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
            ["SendTransientBuffer command completed successfully"],
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

    class TestAllocateAndConfigure:
        """
        Class containing fixtures and tests of the MccsController's
        :py:meth:`~ska.low.mccs.MccsController.Allocate` and
        :py:meth:`~ska.low.mccs.MccsController.Release` and
        :py:meth:`~ska.low.mccs.MccsController.Configure` commands
        """

        @pytest.fixture()
        def initial_mocks(self, mock_factory):
            """
            Fixture that registers device proxy mocks prior to patching.
            The default fixture is overridden here to ensure that mock
            subarrays and stations respond suitably to actions taken on
            them by the controller as part of the controller's
            :py:meth:`~ska.low.mccs.MccsController.Allocate` and
            :py:meth:`~ska.low.mccs.MccsController.Release` and
            :py:meth:`~ska.low.mccs.MccsController.Configure` commands

            :param mock_factory: a factory for
                :py:class:`tango.DeviceProxy` mocks
            :type mock_factory: object
            :return: a dictionary of mocks, keyed by FQDN
            :rtype: dict
            """

            def _subarray_mock():
                """
                Sets up a mock for a :py:class:`tango.DeviceProxy` that
                connects to an :py:class:`~ska.low.mccs.MccsSubarray`
                device. The returned mock will respond suitably to
                actions taken on it by the controller as part of the
                controller's
                :py:meth:`~ska.low.mccs.MccsController.Allocate`,
                :py:meth:`~ska.low.mccs.MccsController.Release` and
                :py:meth:`~ska.low.mccs.MccsController.Configure`
                commands.

                :return: a mock for a :py:class:`tango.DeviceProxy` that
                    connects to an
                    :py:class:`~ska.low.mccs.MccsSubarray` device.
                :rtype: :py:class:`unittest.Mock`
                """
                mock = mock_factory()
                mock.On.return_value = (
                    ResultCode.OK,
                    "On command completed successfully",
                )
                mock.AssignResources.return_value = (
                    ResultCode.OK,
                    "Resources assigned",
                )
                mock.Configure.return_value = (
                    ResultCode.OK,
                    "Configure command completed successfully",
                )
                mock.ReleaseResources.return_value = (
                    ResultCode.OK,
                    "Resources released",
                )
                mock.ReleaseAllResources.return_value = (
                    ResultCode.OK,
                    "Resources released",
                )
                mock.Off.return_value = (ResultCode.OK, "Subarray switched off")
                return mock

            def _station_mock():
                """
                Sets up a mock for a :py:class:`tango.DeviceProxy` that
                connects to an :py:class:`~ska.low.mccs.MccsStation`
                device. The returned mock will respond suitably to
                actions taken on it by the controller as part of the
                controller's
                :py:meth:`~ska.low.mccs.MccsController.Allocate` and
                :py:meth:`~ska.low.mccs.MccsController.Release`
                commands.

                :return: a mock for a :py:class:`tango.DeviceProxy` that
                    connects to an
                    :py:class:`~ska.low.mccs.MccsStation` device.
                :rtype: :py:class:`unittest.Mock`
                """
                mock = mock_factory()
                mock.subarrayId = 0
                return mock

            def _beam_mock():
                """
                Sets up a mock for a :py:class:`tango.DeviceProxy` that
                connects to an :py:class:`~ska.low.mccs.MccsStationBeam`
                device. The returned mock will respond suitably to
                actions taken on it by the subarray as part of the
                subarray's
                :py:meth:`~ska.low.mccs.MccsSubarray.Allocate` and
                :py:meth:`~ska.low.mccs.MccsSubarray.Release`
                commands.

                :return: a mock for a :py:class:`tango.DeviceProxy` that
                    connects to an
                    :py:class:`~ska.low.mccs.MccsStationBeam` device.
                :rtype: :py:class:`unittest.Mock`
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
                "low-mccs/beam/001": _beam_mock(),
                "low-mccs/beam/002": _beam_mock(),
            }

        def test_AllocateResources(self, device_under_test):
            """
            Test for AllocateResources.

            :param device_under_test: fixture that provides a
                :py:class:`tango.DeviceProxy` to the device under test, in a
                :py:class:`tango.test_context.DeviceTestContext`.
            :type device_under_test: :py:class:`tango.DeviceProxy`
            """
            station_fqdns = ["low-mccs/station/001", "low-mccs/station/002"]
            mock_station_1 = tango.DeviceProxy(station_fqdns[0])
            station_beam_fqdn = "low-mccs/beam/001"
            mock_station_beam = tango.DeviceProxy(station_beam_fqdn)

            device_under_test.On()
            assert mock_station_beam.healthState == HealthState.OK

            [[result_code], [message]] = call_with_json(
                device_under_test.AssignResources,
                stations=[station_fqdns[0]],
                station_beams=[station_beam_fqdn],
            )

            assert result_code == ResultCode.OK
            assert message == "AssignResources command completed successfully"
            assert sorted(list(device_under_test.stationFQDNs)) == sorted(
                [station_fqdns[0]]
            )
            assert mock_station_beam.stationIds == [1]

            mock_station_1.InitialSetup.assert_called_once_with()

            device_under_test.ReleaseAllResources()
            assert mock_station_beam.stationIds == []

            # now assign station beam to both stations...
            device_under_test.On()
            [[result_code], [message]] = call_with_json(
                device_under_test.AssignResources,
                stations=station_fqdns,
                station_beams=[station_beam_fqdn],
            )
            assert result_code == ResultCode.OK
            assert message == "AssignResources command completed successfully"
            assert sorted(device_under_test.stationFQDNs) == sorted(station_fqdns)
            assert mock_station_beam.stationIds == [1, 2]

        def test_ReleaseAllResources(self, device_under_test):
            """
            Test for ReleaseAllResources.

            :param device_under_test: fixture that provides a
                :py:class:`tango.DeviceProxy` to the device under test, in a
                :py:class:`tango.test_context.DeviceTestContext`.
            :type device_under_test: :py:class:`tango.DeviceProxy`
            """
            station_fqdns = ["low-mccs/station/001", "low-mccs/station/002"]
            mock_station_1 = tango.DeviceProxy(station_fqdns[0])
            mock_station_2 = tango.DeviceProxy(station_fqdns[1])
            station_beam_fqdns = ["low-mccs/beam/001", "low-mccs/beam/002"]
            mock_station_beam_1 = tango.DeviceProxy(station_beam_fqdns[0])
            mock_station_beam_2 = tango.DeviceProxy(station_beam_fqdns[1])

            device_under_test.On()
            [[result_code], [message]] = call_with_json(
                device_under_test.AssignResources,
                stations=station_fqdns,
                station_beams=station_beam_fqdns,
            )
            assert result_code == ResultCode.OK
            assert message == "AssignResources command completed successfully"
            assert sorted(list(device_under_test.stationFQDNs)) == sorted(station_fqdns)

            mock_station_1.InitialSetup.assert_called_once_with()
            mock_station_2.InitialSetup.assert_called_once_with()

            assert mock_station_beam_1.stationIds == [1, 2]
            assert mock_station_beam_2.stationIds == [1, 2]

            [[result_code], [message]] = call_with_json(
                device_under_test.ReleaseResources,
                station_beam_fqdns=[station_beam_fqdns[0]],
            )
            assert result_code == ResultCode.OK
            assert message == "ReleaseResources command completed successfully"

            assert mock_station_beam_1.stationIds == []
            assert mock_station_beam_2.stationIds == [1, 2]

            # reassign
            call_with_json(
                device_under_test.AssignResources,
                stations=[station_fqdns[1]],
                station_beams=[station_beam_fqdns[0]],
            )
            assert mock_station_beam_1.stationIds == [2]

            # ReleaseAll again
            [[result_code], [message]] = device_under_test.ReleaseAllResources()
            assert result_code == ResultCode.OK
            assert message == "ReleaseAllResources command completed successfully"

            assert mock_station_beam_1.stationIds == []
            assert mock_station_beam_2.stationIds == []

        def test_configure(self, device_under_test):
            """
            Test for Configure.

            :param device_under_test: fixture that provides a
                :py:class:`tango.DeviceProxy` to the device under test, in a
                :py:class:`tango.test_context.DeviceTestContext`.
            :type device_under_test: :py:class:`tango.DeviceProxy`
            """
            station_fqdns = ["low-mccs/station/001", "low-mccs/station/002"]
            mock_station_1 = tango.DeviceProxy(station_fqdns[0])
            station_beam_fqdn = "low-mccs/beam/001"
            mock_station_beam = tango.DeviceProxy(station_beam_fqdn)

            device_under_test.On()
            assert mock_station_beam.healthState == HealthState.OK

            [[result_code], [message]] = call_with_json(
                device_under_test.AssignResources,
                stations=[station_fqdns[0]],
                station_beams=[station_beam_fqdn],
            )

            assert result_code == ResultCode.OK
            assert message == "AssignResources command completed successfully"
            assert sorted(list(device_under_test.stationFQDNs)) == [station_fqdns[0]]

            assert mock_station_beam.stationIds == [1]

            mock_station_1.InitialSetup.assert_called_once_with()

            device_under_test.ReleaseAllResources()
            assert mock_station_beam.stationIds == []

            # now assign station beam to both stations...
            device_under_test.On()
            [[result_code], [message]] = call_with_json(
                device_under_test.AssignResources,
                stations=station_fqdns,
                station_beams=[station_beam_fqdn],
            )
            assert result_code == ResultCode.OK
            assert message == "AssignResources command completed successfully"
            assert sorted(device_under_test.stationFQDNs) == sorted(station_fqdns)
            assert mock_station_beam.stationIds == [1, 2]

            config_dict = {
                "mccs": {
                    "stations": [{"station_id": 1}, {"station_id": 2}],
                    "station_beams": [
                        {
                            "station_beam_id": 1,
                            "station_id": [1, 2],
                            "channels": [1, 2, 3, 4, 5, 6, 7, 8],
                            "update_rate": 3.14,
                            "sky_coordinates": [1585619550.0, 192.0, 2.0, 27.0, 1.0],
                        }
                    ],
                }
            }
            json_str = json.dumps(config_dict)
            expected = config_dict["mccs"]["station_beams"][0]
            [[result_code], [message]] = device_under_test.Configure(json_str)
            assert result_code == ResultCode.OK
            assert message == "Configure command completed successfully"
            assert device_under_test.obsState == ObsState.READY

            # remove preceeding "call(\" and trailing "\)"
            output = str(mock_station_beam.configure.call_args)[6:-2]
            assert json.loads(output) == expected

        def test_Scan(self, device_under_test):
            """
            Test for Scan.

            :param device_under_test: fixture that provides a
                :py:class:`tango.DeviceProxy` to the device under test, in a
                :py:class:`tango.test_context.DeviceTestContext`.
            :type device_under_test: :py:class:`tango.DeviceProxy`
            """
            self.test_configure(device_under_test)

            [[result_code], _] = call_with_json(
                device_under_test.Scan, subarray_id=1, scan_time=0.0
            )
            assert result_code == ResultCode.STARTED
            assert device_under_test.obsState == ObsState.SCANNING

        def test_Abort(self, device_under_test, mocker, helpers):
            """
            Test for Abort (including end of command event testing).

            :param device_under_test: fixture that provides a
                :py:class:`tango.DeviceProxy` to the device under test, in a
                :py:class:`tango.test_context.DeviceTestContext`.
            :type device_under_test: :py:class:`tango.DeviceProxy`
            :param mocker: fixture that wraps unittest.Mock
            :type mocker: wrapper for :py:mod:`unittest.mock`
            """
            self.test_Scan(device_under_test)

            # Test that subscription yields an event as expected
            mock_callback = mocker.Mock()
            _ = device_under_test.subscribe_event(
                "commandResult", tango.EventType.CHANGE_EVENT, mock_callback
            )
            helpers.callback_event_data_check(
                mock_callback=mock_callback, name="commandResult", result=None
            )
            try:
                # Call the Abort() command on the Subarray device
                [[result_code], [message]] = device_under_test.Abort()
                assert result_code == ResultCode.OK
                assert message == "Abort command completed OK"
                helpers.callback_command_result_check(
                    mock_callback=mock_callback,
                    name="commandResult",
                    result=result_code,
                )
            except Exception as reason:
                print(f"Exception: {reason}")
                assert False

            assert device_under_test.obsState == ObsState.ABORTED
