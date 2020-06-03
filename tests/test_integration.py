import pytest

from tango import DevFailed, DevSource, DevState

from ska.base.control_model import AdminMode
from ska.low.mccs.utils import call_with_json


class TestMccsIntegration:
    """
    Integration test cases for the Mccs device classes
    """

    def test_master_enable_subarray(self, tango_context):
        """
        Test that a MccsMaster device can enable an MccsSubarray device.
        """
        master = tango_context.get_device("low/elt/master")
        subarray_1 = tango_context.get_device("low/elt/subarray_1")
        subarray_2 = tango_context.get_device("low/elt/subarray_2")

        # check both subarrays are disabled
        assert subarray_1.adminMode == AdminMode.OFFLINE
        assert subarray_1.State() == DevState.DISABLE

        assert subarray_2.adminMode == AdminMode.OFFLINE
        assert subarray_2.State() == DevState.DISABLE

        # enable subarray 1
        master.EnableSubarray(1)

        # check only subarray 1 is enabled.
        assert subarray_1.adminMode == AdminMode.ONLINE
        assert subarray_1.State() == DevState.OFF

        assert subarray_2.adminMode == AdminMode.OFFLINE
        assert subarray_2.State() == DevState.DISABLE

        # try to enable subarray 1 again -- this should fail
        with pytest.raises(DevFailed):
            master.EnableSubarray(1)

        # check failure has no side-effect
        assert subarray_1.adminMode == AdminMode.ONLINE
        assert subarray_1.State() == DevState.OFF

        assert subarray_2.adminMode == AdminMode.OFFLINE
        assert subarray_2.State() == DevState.DISABLE

        # enable subarray 2
        master.EnableSubarray(2)

        # check both subarrays now enabled
        assert subarray_1.adminMode == AdminMode.ONLINE
        assert subarray_1.State() == DevState.OFF

        assert subarray_2.adminMode == AdminMode.ONLINE
        assert subarray_2.State() == DevState.OFF

    def test_master_disable_subarray(self, tango_context):
        """
        Test that an MccsMaster device can disable an MccsSubarray
        device.
        """
        master = tango_context.get_device("low/elt/master")
        subarray_1 = tango_context.get_device("low/elt/subarray_1")
        subarray_2 = tango_context.get_device("low/elt/subarray_2")

        master.EnableSubarray(1)
        master.EnableSubarray(2)

        # check both subarrays are enabled
        assert subarray_1.adminMode == AdminMode.ONLINE
        assert subarray_1.State() == DevState.OFF

        assert subarray_2.adminMode == AdminMode.ONLINE
        assert subarray_2.State() == DevState.OFF

        # disable subarray 1
        master.DisableSubarray(1)

        # check only subarray 1 is disabled.
        assert subarray_1.adminMode == AdminMode.OFFLINE
        assert subarray_1.State() == DevState.DISABLE

        assert subarray_2.adminMode == AdminMode.ONLINE
        assert subarray_2.State() == DevState.OFF

        # try to disable subarray 1 again -- this should fail
        with pytest.raises(DevFailed):
            master.DisableSubarray(1)

        # check failure has no side-effect
        assert subarray_1.adminMode == AdminMode.OFFLINE
        assert subarray_1.State() == DevState.DISABLE

        assert subarray_2.adminMode == AdminMode.ONLINE
        assert subarray_2.State() == DevState.OFF

        # disable subarray 2
        master.DisableSubarray(2)

        # check both subarrays now disabled
        assert subarray_1.adminMode == AdminMode.OFFLINE
        assert subarray_1.State() == DevState.DISABLE

        assert subarray_2.adminMode == AdminMode.OFFLINE
        assert subarray_2.State() == DevState.DISABLE

    def test_master_allocate_subarray(self, tango_context):
        """
        Test that an MccsMaster device can allocate resources to an
        MccsSubarray device.
        """
        master = tango_context.get_device("low/elt/master")
        subarray_1 = tango_context.get_device("low/elt/subarray_1")
        subarray_2 = tango_context.get_device("low/elt/subarray_2")
        station_1 = tango_context.get_device("low/elt/station_1")
        station_2 = tango_context.get_device("low/elt/station_2")
        tile_1 = tango_context.get_device("low/elt/tile_1")
        tile_2 = tango_context.get_device("low/elt/tile_2")
        tile_3 = tango_context.get_device("low/elt/tile_3")
        tile_4 = tango_context.get_device("low/elt/tile_4")

        # Bypass the cache because stationFQDNs etc are polled attributes,
        # and having written to them, we don't want to have to wait a
        # polling period to test that the write has stuck.
        master.set_source(DevSource.DEV)
        subarray_1.set_source(DevSource.DEV)
        subarray_2.set_source(DevSource.DEV)
        station_1.set_source(DevSource.DEV)
        station_2.set_source(DevSource.DEV)
        tile_1.set_source(DevSource.DEV)
        tile_2.set_source(DevSource.DEV)
        tile_3.set_source(DevSource.DEV)
        tile_4.set_source(DevSource.DEV)

        # check initial state
        assert list(subarray_1.stationFQDNs) == []
        assert list(subarray_2.stationFQDNs) == []
        assert station_1.subarrayId == 0
        assert station_2.subarrayId == 0
        assert tile_1.subarrayId == 0
        assert tile_2.subarrayId == 0
        assert tile_3.subarrayId == 0
        assert tile_4.subarrayId == 0

        # Can't allocate to an array that hasn't been enabled
        with pytest.raises(DevFailed):
            call_with_json(
                master.Allocate,
                subarray_id=1,
                stations=["low/elt/station_1"],
            )

        # check no side-effect to failure
        assert list(subarray_1.stationFQDNs) == []
        assert list(subarray_2.stationFQDNs) == []
        assert station_1.subarrayId == 0
        assert station_2.subarrayId == 0
        assert tile_1.subarrayId == 0
        assert tile_2.subarrayId == 0
        assert tile_3.subarrayId == 0
        assert tile_4.subarrayId == 0

        # now enable subarrays
        master.EnableSubarray(1)
        master.EnableSubarray(2)

        # allocate station_1 to subarray_1
        call_with_json(
            master.Allocate,
            subarray_id=1,
            stations=["low/elt/station_1"],
        )

        # check that station_1 and only station_1 is allocated
        assert list(subarray_1.stationFQDNs) == ["low/elt/station_1"]
        assert list(subarray_2.stationFQDNs) == []
        assert station_1.subarrayId == 1
        assert station_2.subarrayId == 0
        assert tile_1.subarrayId == 1
        assert tile_2.subarrayId == 1
        assert tile_3.subarrayId == 0
        assert tile_4.subarrayId == 0

        # allocating station_1 to subarray 2 should fail, because it is already
        # allocated to subarray 1
        with pytest.raises(DevFailed):
            call_with_json(
                master.Allocate,
                subarray_id=2,
                stations=["low/elt/station_1"],
            )

        # check no side-effects
        assert list(subarray_1.stationFQDNs) == ["low/elt/station_1"]
        assert list(subarray_2.stationFQDNs) == []
        assert station_1.subarrayId == 1
        assert station_2.subarrayId == 0
        assert tile_1.subarrayId == 1
        assert tile_2.subarrayId == 1
        assert tile_3.subarrayId == 0
        assert tile_4.subarrayId == 0

        # allocating stations 1 and 2 to subarray 1 should succeed,
        # because the already allocated station is allocated to the same
        # subarray
        call_with_json(
            master.Allocate,
            subarray_id=1,
            stations=["low/elt/station_1", "low/elt/station_2"],
        )

        # check
        assert list(subarray_1.stationFQDNs) == ["low/elt/station_1",
                                                 "low/elt/station_2"]
        assert list(subarray_2.stationFQDNs) == []
        assert station_1.subarrayId == 1
        assert station_2.subarrayId == 1
        assert tile_1.subarrayId == 1
        assert tile_2.subarrayId == 1
        assert tile_3.subarrayId == 1
        assert tile_4.subarrayId == 1

        # now disable subarray 1
        master.DisableSubarray(1)

        # check that subarray 1's resources have been released
        assert list(subarray_1.stationFQDNs) == []
        assert list(subarray_2.stationFQDNs) == []
        assert station_1.subarrayId == 0
        assert station_2.subarrayId == 0
        assert tile_1.subarrayId == 0
        assert tile_2.subarrayId == 0
        assert tile_3.subarrayId == 0
        assert tile_4.subarrayId == 0

        # now that subarray 1 has been disabled, its resources should have
        # been released and it should be possible to allocate them to
        # subarray 2
        call_with_json(
            master.Allocate,
            subarray_id=2,
            stations=["low/elt/station_1", "low/elt/station_2"],
        )

        # check
        assert list(subarray_1.stationFQDNs) == []
        assert list(subarray_2.stationFQDNs) == ["low/elt/station_1",
                                                 "low/elt/station_2"]
        assert station_1.subarrayId == 2
        assert station_2.subarrayId == 2
        assert tile_1.subarrayId == 2
        assert tile_2.subarrayId == 2
        assert tile_3.subarrayId == 2
        assert tile_4.subarrayId == 2

        # disable the other subarray
        master.DisableSubarray(2)

        # check all resources released
        assert list(subarray_1.stationFQDNs) == []
        assert list(subarray_2.stationFQDNs) == []
        assert station_1.subarrayId == 0
        assert station_2.subarrayId == 0
        assert tile_1.subarrayId == 0
        assert tile_2.subarrayId == 0
        assert tile_3.subarrayId == 0
        assert tile_4.subarrayId == 0

    def test_master_release_subarray(self, tango_context):
        """
        Test that an MccsMaster device can release the resources of an
        MccsSubarray device.
        """
        master = tango_context.get_device("low/elt/master")
        subarray_1 = tango_context.get_device("low/elt/subarray_1")
        subarray_2 = tango_context.get_device("low/elt/subarray_2")
        station_1 = tango_context.get_device("low/elt/station_1")
        station_2 = tango_context.get_device("low/elt/station_2")
        tile_1 = tango_context.get_device("low/elt/tile_1")
        tile_2 = tango_context.get_device("low/elt/tile_2")
        tile_3 = tango_context.get_device("low/elt/tile_3")
        tile_4 = tango_context.get_device("low/elt/tile_4")

        # Bypass the cache because stationFQDNs etc are polled attributes,
        # and having written to them, we don't want to have to wait a
        # polling period so test that the write has stuck.
        master.set_source(DevSource.DEV)
        subarray_1.set_source(DevSource.DEV)
        subarray_2.set_source(DevSource.DEV)
        station_1.set_source(DevSource.DEV)
        station_2.set_source(DevSource.DEV)
        tile_1.set_source(DevSource.DEV)
        tile_2.set_source(DevSource.DEV)
        tile_3.set_source(DevSource.DEV)
        tile_4.set_source(DevSource.DEV)

        # enable subarrays
        master.EnableSubarray(1)
        master.EnableSubarray(2)

        # allocate stations 1 to subarray 1
        call_with_json(
            master.Allocate,
            subarray_id=1,
            stations=["low/elt/station_1"]
        )

        # allocate station 2 to subarray 2
        call_with_json(
            master.Allocate,
            subarray_id=2,
            stations=["low/elt/station_2"]
        )

        # check initial state
        assert list(subarray_1.stationFQDNs) == ["low/elt/station_1"]
        assert list(subarray_2.stationFQDNs) == ["low/elt/station_2"]
        assert station_1.subarrayId == 1
        assert station_2.subarrayId == 2
        assert tile_1.subarrayId == 1
        assert tile_2.subarrayId == 1
        assert tile_3.subarrayId == 2
        assert tile_4.subarrayId == 2

        # release resources of subarray_2
        master.Release(2)

        # check
        assert list(subarray_1.stationFQDNs) == ["low/elt/station_1"]
        assert list(subarray_2.stationFQDNs) == []
        assert station_1.subarrayId == 1
        assert station_2.subarrayId == 0
        assert tile_1.subarrayId == 1
        assert tile_2.subarrayId == 1
        assert tile_3.subarrayId == 0
        assert tile_4.subarrayId == 0

        # releasing resources of unresourced subarray_2 should fail
        with pytest.raises(DevFailed):
            master.Release(2)

        # check no side-effect to failed release
        assert list(subarray_1.stationFQDNs) == ["low/elt/station_1"]
        assert list(subarray_2.stationFQDNs) == []
        assert station_1.subarrayId == 1
        assert station_2.subarrayId == 0
        assert tile_1.subarrayId == 1
        assert tile_2.subarrayId == 1
        assert tile_3.subarrayId == 0
        assert tile_4.subarrayId == 0

        # release resources of subarray_1
        master.Release(1)

        # check all released
        assert list(subarray_1.stationFQDNs) == []
        assert list(subarray_2.stationFQDNs) == []
        assert station_1.subarrayId == 0
        assert station_2.subarrayId == 0
        assert tile_1.subarrayId == 0
        assert tile_2.subarrayId == 0
        assert tile_3.subarrayId == 0
        assert tile_4.subarrayId == 0

    def test_station_tile_subarray_id(self, tango_context):
        """
        Test that a write to attribute subarrayId on an MccsStation
        device also results in an update to attribute subarrayId on its
        MccsTiles.
        """
        station = tango_context.get_device("low/elt/station_1")
        tile_1 = tango_context.get_device("low/elt/tile_1")
        tile_2 = tango_context.get_device("low/elt/tile_2")

        # Bypass the cache because stationFQDNs etc are polled attributes,
        # and having written to them, we don't want to have to wait a
        # polling period so test that the write has stuck.
        station.set_source(DevSource.DEV)
        tile_1.set_source(DevSource.DEV)
        tile_2.set_source(DevSource.DEV)

        # check initial state
        assert list(station.tileFQDNs) == ["low/elt/tile_1", "low/elt/tile_2"]
        assert station.subarrayId == 0
        assert tile_1.subarrayId == 0
        assert tile_2.subarrayId == 0

        # write subarray_id
        station.subarrayId = 1

        # check state
        assert list(station.tileFQDNs) == ["low/elt/tile_1", "low/elt/tile_2"]
        assert station.subarrayId == 1
        assert tile_1.subarrayId == 1
        assert tile_2.subarrayId == 1
