"""
This module contains tests of interactions between ska.low.mccs classes,
particularly tango devices.
"""

import pytest

from ska_tango_base.commands import ResultCode
from ska.low.mccs.utils import call_with_json


@pytest.fixture()
def devices_to_load():
    """
    Fixture that specifies the devices to be loaded for testing.

    :return: specification of the devices to be loaded
    :rtype: dict
    """
    # TODO: Once https://github.com/tango-controls/cppTango/issues/816 is resolved, we
    # should reinstate the APIUs and antennas in these tests.
    return {
        "path": "charts/ska-low-mccs/data/configuration_without_antennas.json",
        "package": "ska.low.mccs",
        "devices": [
            "controller",
            "subarray_01",
            "subarray_02",
            "station_001",
            "station_002",
            "subrack_01",
            "tile_0001",
            "tile_0002",
            "tile_0003",
            "tile_0004",
            "subarraybeam_01",
            "subarraybeam_02",
            "subarraybeam_03",
            "subarraybeam_04",
        ],
    }


class TestMccsIntegration:
    """
    Integration test cases for the Mccs device classes.
    """

    def test_controller_allocate_subarray(self, device_context):
        """
        Test that an MccsController device can allocate resources to an
        MccsSubarray device.

        :param device_context: a test context for a set of tango devices
        :type device_context: :py:class:`tango.MultiDeviceTestContext`
        """
        controller = device_context.get_device("controller")
        subarray_1 = device_context.get_device("subarray_01")
        subarray_2 = device_context.get_device("subarray_02")
        station_1 = device_context.get_device("station_001")
        station_2 = device_context.get_device("station_002")
        tile_1 = device_context.get_device("tile_0001")
        tile_2 = device_context.get_device("tile_0002")
        tile_3 = device_context.get_device("tile_0003")
        tile_4 = device_context.get_device("tile_0004")

        # check initial state
        assert subarray_1.stationFQDNs is None
        assert subarray_2.stationFQDNs is None
        assert station_1.subarrayId == 0
        assert station_2.subarrayId == 0
        assert tile_1.subarrayId == 0
        assert tile_2.subarrayId == 0
        assert tile_3.subarrayId == 0
        assert tile_4.subarrayId == 0

        controller.Startup()

        # allocate station_1 to subarray_1
        ((result_code,), (message,)) = call_with_json(
            controller.Allocate,
            subarray_id=1,
            station_ids=[1],
            subarray_beam_ids=[1],
            channels=[[0, 8, 1, 1], [8, 8, 2, 1]],
        )
        assert result_code == ResultCode.OK

        # check that station_1 and only station_1 is allocated
        assert list(subarray_1.stationFQDNs) == [station_1.get_fqdn()]
        assert subarray_2.stationFQDNs is None
        assert station_1.subarrayId == 1
        assert station_2.subarrayId == 0
        assert tile_1.subarrayId == 1
        assert tile_2.subarrayId == 1
        assert tile_3.subarrayId == 0
        assert tile_4.subarrayId == 0

        # allocating station_1 to subarray 2 should fail, because it is already
        # allocated to subarray 1
        ((result_code,), (_,)) = call_with_json(
            controller.Allocate,
            subarray_id=2,
            station_ids=[1],
            subarray_beam_ids=[1],
            channels=[[0, 8, 1, 1], [8, 8, 2, 1]],
        )
        assert result_code == ResultCode.FAILED

        # check no side-effects
        assert list(subarray_1.stationFQDNs) == [station_1.get_fqdn()]
        assert subarray_2.stationFQDNs is None
        assert station_1.subarrayId == 1
        assert station_2.subarrayId == 0
        assert tile_1.subarrayId == 1
        assert tile_2.subarrayId == 1
        assert tile_3.subarrayId == 0
        assert tile_4.subarrayId == 0

        # allocating stations 1 and 2 to subarray 1 should succeed,
        # because the already allocated station is allocated to the same
        # subarray, BUT we must remember that the subarray cannot reallocate
        # the same subarray_beam.
        # ToDo This will change when subarray_beam is not a list.
        ((result_code,), (message,)) = call_with_json(
            controller.Allocate,
            subarray_id=1,
            station_ids=[1, 2],
            subarray_beam_ids=[2],
            channels=[[0, 8, 1, 1], [8, 8, 2, 1]],
        )
        assert result_code == ResultCode.OK

        # check
        assert list(subarray_1.stationFQDNs) == [
            station_1.get_fqdn(),
            station_2.get_fqdn(),
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
        Test that an MccsController device can release the resources of
        an MccsSubarray device.

        :param device_context: a test context for a set of tango devices
        :type device_context: :py:class:`tango.MultiDeviceTestContext`
        """
        controller = device_context.get_device("controller")
        subarray_1 = device_context.get_device("subarray_01")
        subarray_2 = device_context.get_device("subarray_02")
        station_1 = device_context.get_device("station_001")
        station_2 = device_context.get_device("station_002")
        tile_1 = device_context.get_device("tile_0001")
        tile_2 = device_context.get_device("tile_0002")
        tile_3 = device_context.get_device("tile_0003")
        tile_4 = device_context.get_device("tile_0004")

        controller.Startup()

        # allocate stations 1 to subarray 1
        call_with_json(
            controller.Allocate,
            subarray_id=1,
            station_ids=[1],
            subarray_beam_ids=[1],
            channels=[[0, 8, 1, 1], [8, 8, 2, 1]],
        )

        # allocate station 2 to subarray 2
        call_with_json(
            controller.Allocate,
            subarray_id=2,
            station_ids=[2],
            subarray_beam_ids=[2],
            channels=[[0, 8, 1, 1], [8, 8, 2, 1]],
        )

        # check initial state
        assert list(subarray_1.stationFQDNs) == [station_1.get_fqdn()]
        assert list(subarray_2.stationFQDNs) == [station_2.get_fqdn()]
        assert station_1.subarrayId == 1
        assert station_2.subarrayId == 2
        assert tile_1.subarrayId == 1
        assert tile_2.subarrayId == 1
        assert tile_3.subarrayId == 2
        assert tile_4.subarrayId == 2

        # release resources of subarray_2
        ((result_code,), (_,)) = call_with_json(
            controller.Release, subarray_id=2, release_all=True
        )
        assert result_code == ResultCode.OK

        # check
        assert list(subarray_1.stationFQDNs) == [station_1.get_fqdn()]
        assert subarray_2.stationFQDNs is None
        assert station_1.subarrayId == 1
        assert station_2.subarrayId == 0
        assert tile_1.subarrayId == 1
        assert tile_2.subarrayId == 1
        assert tile_3.subarrayId == 0
        assert tile_4.subarrayId == 0

        # releasing resources of unresourced subarray_2 should fail
        ((result_code,), (_,)) = call_with_json(
            controller.Release, subarray_id=2, release_all=True
        )
        assert result_code == ResultCode.FAILED

        # check no side-effect to failed release
        assert list(subarray_1.stationFQDNs) == [station_1.get_fqdn()]
        assert subarray_2.stationFQDNs is None
        assert station_1.subarrayId == 1
        assert station_2.subarrayId == 0
        assert tile_1.subarrayId == 1
        assert tile_2.subarrayId == 1
        assert tile_3.subarrayId == 0
        assert tile_4.subarrayId == 0

        # release resources of subarray_1
        ((result_code,), (_,)) = call_with_json(
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
        :type device_context: :py:class:`tango.MultiDeviceTestContext`
        """
        station = device_context.get_device("station_001")
        tile_1 = device_context.get_device("tile_0001")
        tile_2 = device_context.get_device("tile_0002")

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
