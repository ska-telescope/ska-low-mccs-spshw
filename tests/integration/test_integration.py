"""
This module contains tests of interactions between ska.low.mccs classes,
particularly tango devices.
"""

from tango import DevSource, DevState

from ska.base.commands import ResultCode
from ska.low.mccs.utils import call_with_json

devices_to_load = {
    "path": "charts/mccs/data/configuration.json",
    "package": "ska.low.mccs",
    "devices": [
        "controller",
        "subarray_01",
        "subarray_02",
        "station_001",
        "station_002",
        "tile_0001",
        "tile_0002",
        "tile_0003",
        "tile_0004",
        "antenna_000001",
        "antenna_000002",
        "antenna_000003",
        "antenna_000004",
    ],
}


class TestMccsIntegration:
    """
    Integration test cases for the Mccs device classes
    """

    def test_controller_allocate_subarray(self, device_context):
        """
        Test that an MccsController device can allocate resources to an
        MccsSubarray device.

        :param device_context: a test context for a set of tango devices
        :type device_context: tango.MultiDeviceTestContext
        """
        controller = device_context.get_device("low-mccs/control/control")
        subarray_1 = device_context.get_device("low-mccs/subarray/01")
        subarray_2 = device_context.get_device("low-mccs/subarray/02")
        station_1 = device_context.get_device("low-mccs/station/001")
        station_2 = device_context.get_device("low-mccs/station/002")
        tile_1 = device_context.get_device("low-mccs/tile/0001")
        tile_2 = device_context.get_device("low-mccs/tile/0002")
        tile_3 = device_context.get_device("low-mccs/tile/0003")
        tile_4 = device_context.get_device("low-mccs/tile/0004")

        # Bypass the cache because stationFQDNs etc are polled attributes,
        # and having written to them, we don't want to have to wait a
        # polling period to test that the write has stuck.
        controller.set_source(DevSource.DEV)
        subarray_1.set_source(DevSource.DEV)
        subarray_2.set_source(DevSource.DEV)
        station_1.set_source(DevSource.DEV)
        station_2.set_source(DevSource.DEV)
        tile_1.set_source(DevSource.DEV)
        tile_2.set_source(DevSource.DEV)
        tile_3.set_source(DevSource.DEV)
        tile_4.set_source(DevSource.DEV)

        # check initial state
        assert subarray_1.stationFQDNs is None
        assert subarray_2.stationFQDNs is None
        assert station_1.subarrayId == 0
        assert station_2.subarrayId == 0
        assert tile_1.subarrayId == 0
        assert tile_2.subarrayId == 0
        assert tile_3.subarrayId == 0
        assert tile_4.subarrayId == 0

        controller.On()

        # allocate station_1 to subarray_1
        (result_code, message) = call_with_json(
            controller.Allocate, subarray_id=1, station_ids=[1]
        )
        assert result_code == ResultCode.OK

        # check that station_1 and only station_1 is allocated
        assert list(subarray_1.stationFQDNs) == ["low-mccs/station/001"]
        assert subarray_2.stationFQDNs is None
        assert station_1.subarrayId == 1
        assert station_2.subarrayId == 0
        assert tile_1.subarrayId == 1
        assert tile_2.subarrayId == 1
        assert tile_3.subarrayId == 0
        assert tile_4.subarrayId == 0

        # allocating station_1 to subarray 2 should fail, because it is already
        # allocated to subarray 1
        (result_code, message) = call_with_json(
            controller.Allocate, subarray_id=2, station_ids=[1]
        )
        assert result_code == ResultCode.FAILED

        # check no side-effects
        assert list(subarray_1.stationFQDNs) == ["low-mccs/station/001"]
        assert subarray_2.stationFQDNs is None
        assert station_1.subarrayId == 1
        assert station_2.subarrayId == 0
        assert tile_1.subarrayId == 1
        assert tile_2.subarrayId == 1
        assert tile_3.subarrayId == 0
        assert tile_4.subarrayId == 0

        # allocating stations 1 and 2 to subarray 1 should succeed,
        # because the already allocated station is allocated to the same
        # subarray
        (result_code, message) = call_with_json(
            controller.Allocate, subarray_id=1, station_ids=[1, 2]
        )
        assert result_code == ResultCode.OK

        # check
        assert list(subarray_1.stationFQDNs) == [
            "low-mccs/station/001",
            "low-mccs/station/002",
        ]
        assert subarray_2.stationFQDNs is None
        assert station_1.subarrayId == 1
        assert station_2.subarrayId == 1
        assert tile_1.subarrayId == 1
        assert tile_2.subarrayId == 1
        assert tile_3.subarrayId == 1
        assert tile_4.subarrayId == 1

    def test_controller_release_subarray(self, device_context):
        """
        Test that an MccsController device can release the resources of an
        MccsSubarray device.

        :param device_context: a test context for a set of tango devices
        :type device_context: tango.MultiDeviceTestContext
        """
        controller = device_context.get_device("low-mccs/control/control")
        subarray_1 = device_context.get_device("low-mccs/subarray/01")
        subarray_2 = device_context.get_device("low-mccs/subarray/02")
        station_1 = device_context.get_device("low-mccs/station/001")
        station_2 = device_context.get_device("low-mccs/station/002")
        tile_1 = device_context.get_device("low-mccs/tile/0001")
        tile_2 = device_context.get_device("low-mccs/tile/0002")
        tile_3 = device_context.get_device("low-mccs/tile/0003")
        tile_4 = device_context.get_device("low-mccs/tile/0004")

        # Bypass the cache because stationFQDNs etc are polled attributes,
        # and having written to them, we don't want to have to wait a
        # polling period so test that the write has stuck.
        controller.set_source(DevSource.DEV)
        subarray_1.set_source(DevSource.DEV)
        subarray_2.set_source(DevSource.DEV)
        station_1.set_source(DevSource.DEV)
        station_2.set_source(DevSource.DEV)
        tile_1.set_source(DevSource.DEV)
        tile_2.set_source(DevSource.DEV)
        tile_3.set_source(DevSource.DEV)
        tile_4.set_source(DevSource.DEV)

        controller.On()

        # allocate stations 1 to subarray 1
        call_with_json(controller.Allocate, subarray_id=1, station_ids=[1])

        # allocate station 2 to subarray 2
        call_with_json(controller.Allocate, subarray_id=2, station_ids=[2])

        # check initial state
        assert list(subarray_1.stationFQDNs) == ["low-mccs/station/001"]
        assert list(subarray_2.stationFQDNs) == ["low-mccs/station/002"]
        assert station_1.subarrayId == 1
        assert station_2.subarrayId == 2
        assert tile_1.subarrayId == 1
        assert tile_2.subarrayId == 1
        assert tile_3.subarrayId == 2
        assert tile_4.subarrayId == 2

        # release resources of subarray_2
        (result_code, message) = call_with_json(
            controller.Release, subarray_id=2, release_all=True
        )
        assert result_code == ResultCode.OK

        # check
        assert list(subarray_1.stationFQDNs) == ["low-mccs/station/001"]
        assert subarray_2.stationFQDNs is None
        assert station_1.subarrayId == 1
        assert station_2.subarrayId == 0
        assert tile_1.subarrayId == 1
        assert tile_2.subarrayId == 1
        assert tile_3.subarrayId == 0
        assert tile_4.subarrayId == 0

        # releasing resources of unresourced subarray_2 should fail
        (result_code, message) = call_with_json(
            controller.Release, subarray_id=2, release_all=True
        )
        assert result_code == ResultCode.FAILED

        # check no side-effect to failed release
        assert list(subarray_1.stationFQDNs) == ["low-mccs/station/001"]
        assert subarray_2.stationFQDNs is None
        assert station_1.subarrayId == 1
        assert station_2.subarrayId == 0
        assert tile_1.subarrayId == 1
        assert tile_2.subarrayId == 1
        assert tile_3.subarrayId == 0
        assert tile_4.subarrayId == 0

        # release resources of subarray_1
        (result_code, message) = call_with_json(
            controller.Release, subarray_id=1, release_all=True
        )
        assert result_code == ResultCode.OK

        # check all released
        assert subarray_1.stationFQDNs is None
        assert subarray_2.stationFQDNs is None
        assert station_1.subarrayId == 0
        assert station_2.subarrayId == 0
        assert tile_1.subarrayId == 0
        assert tile_2.subarrayId == 0
        assert tile_3.subarrayId == 0
        assert tile_4.subarrayId == 0

    def test_station_tile_subarray_id(self, device_context):
        """
        Test that a write to attribute subarrayId on an MccsStation
        device also results in an update to attribute subarrayId on its
        MccsTiles.

        :param device_context: a test context for a set of tango devices
        :type device_context: tango.MultiDeviceTestContext
        """
        station = device_context.get_device("low-mccs/station/001")
        tile_1 = device_context.get_device("low-mccs/tile/0001")
        tile_2 = device_context.get_device("low-mccs/tile/0002")

        # Bypass the cache because stationFQDNs etc are polled attributes,
        # and having written to them, we don't want to have to wait a
        # polling period so test that the write has stuck.
        station.set_source(DevSource.DEV)
        tile_1.set_source(DevSource.DEV)
        tile_2.set_source(DevSource.DEV)

        # check initial state
        assert station.subarrayId == 0
        assert tile_1.subarrayId == 0
        assert tile_2.subarrayId == 0

        # write subarray_id
        station.subarrayId = 1

        # check state
        assert station.subarrayId == 1
        assert tile_1.subarrayId == 1
        assert tile_2.subarrayId == 1
