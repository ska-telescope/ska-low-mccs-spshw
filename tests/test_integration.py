import pytest

from tango import DevFailed, DevSource, DevState
from tango.test_context import MultiDeviceTestContext

from ska.base.control_model import AdminMode
from ska.mccs import MccsMaster, MccsSubarray, MccsStation, MccsTile
from ska.mccs.utils import call_with_json


class TestMccsIntegration:
    """
    Integration test cases for the Mccs device classes
    """

    @pytest.mark.skip(reason="MultiDeviceTestContext is flaky")
    def test_master_enable_subarray(self):
        """
        Test that a MccsMaster device can enable an MccsSubarray device.
        """
        devices_info = [
            {
                "class": MccsMaster,
                "devices": (
                    {
                        "name": "low/elt/master",
                        "properties": {
                            "MccsSubarrays": ["low/elt/subarray_1",
                                              "low/elt/subarray_2"],
                            "MccsStations": ["low/elt/station_1"],
                            "MccsTiles": ["low/elt/tile_47"],
                        }
                    },
                )
            },
            {
                "class": MccsSubarray,
                "devices": [
                    {
                        "name": "low/elt/subarray_1",
                        "properties": {
                        }
                    },
                    {
                        "name": "low/elt/subarray_2",
                        "properties": {
                        }
                    },
                ]
            }
        ]

        with MultiDeviceTestContext(devices_info) as context:
            master = context.get_device("low/elt/master")
            subarray_1 = context.get_device("low/elt/subarray_1")
            subarray_2 = context.get_device("low/elt/subarray_2")

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

    @pytest.mark.skip(reason="MultiDeviceTestContext is flaky")
    def test_master_disable_subarray(self):
        """
        Test that an MccsMaster device can disable an MccsSubarray
        device.
        """
        devices_info = [
            {
                "class": MccsMaster,
                "devices": (
                    {
                        "name": "low/elt/master",
                        "properties": {
                            "MccsSubarrays": ["low/elt/subarray_1",
                                              "low/elt/subarray_2"],
                            "MccsStations": ["low/elt/station_1"],
                            "MccsTiles": ["low/elt/tile_47"]
                        }
                    },
                )
            },
            {
                "class": MccsSubarray,
                "devices": [
                    {
                        "name": "low/elt/subarray_1",
                        "properties": {
                        }
                    },
                    {
                        "name": "low/elt/subarray_2",
                        "properties": {
                        }
                    },
                ]
            }
        ]

        with MultiDeviceTestContext(devices_info) as context:
            master = context.get_device("low/elt/master")
            subarray_1 = context.get_device("low/elt/subarray_1")
            subarray_2 = context.get_device("low/elt/subarray_2")

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

            # check both subarrays now enabled
            assert subarray_1.adminMode == AdminMode.OFFLINE
            assert subarray_1.State() == DevState.DISABLE

            assert subarray_2.adminMode == AdminMode.OFFLINE
            assert subarray_2.State() == DevState.DISABLE

    @pytest.mark.skip(reason="MultiDeviceTestContext is flaky")
    def test_master_allocate_subarray(self):
        """
        Test that an MccsMaster device can allocate resources to an
        MccsSubarray device.
        """
        devices_info = [
            {
                "class": MccsMaster,
                "devices": (
                    {
                        "name": "low/elt/master",
                        "properties": {
                            "MccsSubarrays": ["low/elt/subarray_1",
                                              "low/elt/subarray_2"],
                            "MccsStations": ["low/elt/station_1",
                                             "low/elt/station_2"],
                            "MccsTiles": ["low/elt/tile_47",
                                          "low/elt/tile_129"],
                        }
                    },
                )
            },
            {
                "class": MccsSubarray,
                "devices": [
                    {
                        "name": "low/elt/subarray_1",
                        "properties": {
                        }
                    },
                    {
                        "name": "low/elt/subarray_2",
                        "properties": {
                        }
                    }
                ]
            },
            {
                "class": MccsStation,
                "devices": [
                    {
                        "name": "low/elt/station_1",
                        "properties": {
                        }
                    },
                    {
                        "name": "low/elt/station_2",
                        "properties": {
                        }
                    },
                ]
            },
            {
                "class": MccsTile,
                "devices": [
                    {
                        "name": "low/elt/tile_47",
                        "properties": {
                        }
                    },
                    {
                        "name": "low/elt/tile_129",
                        "properties": {
                        }
                    },
                ]
            },
        ]

        with MultiDeviceTestContext(devices_info) as context:
            master = context.get_device("low/elt/master")
            subarray_1 = context.get_device("low/elt/subarray_1")
            subarray_2 = context.get_device("low/elt/subarray_2")
            station_1 = context.get_device("low/elt/station_1")
            station_2 = context.get_device("low/elt/station_2")
            tile_1 = context.get_device("low/elt/tile_47")
            tile_2 = context.get_device("low/elt/tile_129")

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

            # now enable subarrays
            master.EnableSubarray(1)
            master.EnableSubarray(2)

            assert subarray_1.stationFQDNs is None
            assert subarray_1.tileFQDNs is None
            assert subarray_2.stationFQDNs is None
            assert subarray_1.tileFQDNs is None
            assert station_1.subarrayId == 0
            assert station_2.subarrayId == 0
            assert tile_1.subarrayId == 0
            assert tile_2.subarrayId == 0

            # allocating station 1 and tile 2 to subarray 1 should succeed
            call_with_json(
                master.Allocate,
                subarray_id=1,
                stations=[True, False],
                tiles=[False, True]
            )

            assert list(subarray_1.stationFQDNs) == ["low/elt/station_1"]
            assert list(subarray_1.tileFQDNs) == ["low/elt/tile_129"]
            assert subarray_2.stationFQDNs is None
            assert subarray_2.tileFQDNs is None
            assert station_1.subarrayId == 1
            assert station_2.subarrayId == 0
            assert tile_1.subarrayId == 0
            assert tile_2.subarrayId == 1

            # allocating station 1 and tile 1 to subarray 1 should succeed,
            # because the already allocated station is allocated to the same
            # subarray
            call_with_json(
                master.Allocate,
                subarray_id=1,
                stations=[True, False],
                tiles=[True, False]
            )

            assert list(subarray_1.stationFQDNs) == ["low/elt/station_1"]
            assert list(subarray_1.tileFQDNs) == ["low/elt/tile_47"]
            assert subarray_2.stationFQDNs is None
            assert subarray_2.tileFQDNs is None
            assert station_1.subarrayId == 1
            assert station_2.subarrayId == 0
            assert tile_1.subarrayId == 1
            assert tile_2.subarrayId == 0

            # allocating stations 1 and 2 to subarray 2 should fail, because
            # station 1 is already allocated to subarray 1
            with pytest.raises(DevFailed):
                call_with_json(
                    master.Allocate,
                    subarray_id=2,
                    stations=[True, True],
                    tiles=[False, False]
                )

            assert list(subarray_1.stationFQDNs) == ["low/elt/station_1"]
            assert list(subarray_1.tileFQDNs) == ["low/elt/tile_47"]
            assert subarray_2.stationFQDNs is None
            assert subarray_2.tileFQDNs is None
            assert station_1.subarrayId == 1
            assert station_2.subarrayId == 0
            assert tile_1.subarrayId == 1
            assert tile_2.subarrayId == 0

            # allocating station 2 and tile 2 to subarray 2 should succeed
            call_with_json(
                master.Allocate,
                subarray_id=2,
                stations=[False, True],
                tiles=[False, True]
            )

            assert list(subarray_1.stationFQDNs) == ["low/elt/station_1"]
            assert list(subarray_1.tileFQDNs) == ["low/elt/tile_47"]
            assert list(subarray_2.stationFQDNs) == ["low/elt/station_2"]
            assert list(subarray_2.tileFQDNs) == ["low/elt/tile_129"]
            assert station_1.subarrayId == 1
            assert station_2.subarrayId == 2
            assert tile_1.subarrayId == 1
            assert tile_2.subarrayId == 2

            master.DisableSubarray(1)

            assert subarray_1.stationFQDNs is None
            assert subarray_1.tileFQDNs is None
            assert list(subarray_2.stationFQDNs) == ["low/elt/station_2"]
            assert list(subarray_2.tileFQDNs) == ["low/elt/tile_129"]
            assert station_1.subarrayId == 0
            assert station_2.subarrayId == 2
            assert tile_1.subarrayId == 0
            assert tile_2.subarrayId == 2

            # now that subarray 1 has been disabled, its resources should have
            # been released and it should be possible to allocate them to
            # subarray 2
            call_with_json(
                master.Allocate,
                subarray_id=2,
                stations=[True, True],
                tiles=[True, True]
            )

            assert subarray_1.stationFQDNs is None
            assert subarray_1.tileFQDNs is None
            assert list(subarray_2.stationFQDNs) == ["low/elt/station_1",
                                                     "low/elt/station_2"]
            assert list(subarray_2.tileFQDNs) == ["low/elt/tile_129",
                                                  "low/elt/tile_47"]
            assert station_1.subarrayId == 2
            assert station_2.subarrayId == 2
            assert tile_1.subarrayId == 2
            assert tile_2.subarrayId == 2

            master.DisableSubarray(2)

            assert subarray_1.stationFQDNs is None
            assert subarray_1.tileFQDNs is None
            assert subarray_2.stationFQDNs is None
            assert subarray_2.tileFQDNs is None
            assert station_1.subarrayId == 0
            assert station_2.subarrayId == 0
            assert tile_1.subarrayId == 0
            assert tile_2.subarrayId == 0

            context.stop()

    @pytest.mark.skip(reason="MultiDeviceTestContext is flaky")
    def test_master_release_subarray(self):
        """
        Test that an MccsMaster device can release the resources of an
        MccsSubarray device.
        """
        devices_info = [
            {
                "class": MccsMaster,
                "devices": (
                    {
                        "name": "low/elt/master",
                        "properties": {
                            "MccsSubarrays": ["low/elt/subarray_1",
                                              "low/elt/subarray_2"],
                            "MccsStations": ["low/elt/station_1",
                                             "low/elt/station_2"],
                            "MccsTiles": ["low/elt/tile_47",
                                          "low/elt/tile_129"],
                        }
                    },
                )
            },
            {
                "class": MccsSubarray,
                "devices": [
                    {
                        "name": "low/elt/subarray_1",
                        "properties": {
                        }
                    },
                    {
                        "name": "low/elt/subarray_2",
                        "properties": {
                        }
                    }
                ]
            },
            {
                "class": MccsStation,
                "devices": [
                    {
                        "name": "low/elt/station_1",
                        "properties": {
                        }
                    },
                    {
                        "name": "low/elt/station_2",
                        "properties": {
                        }
                    },
                ]
            },
            {
                "class": MccsTile,
                "devices": [
                    {
                        "name": "low/elt/tile_47",
                        "properties": {
                        }
                    },
                    {
                        "name": "low/elt/tile_129",
                        "properties": {
                        }
                    },
                ]
            },
        ]

        with MultiDeviceTestContext(devices_info, timeout=30, process=True) as context:
            master = context.get_device("low/elt/master")
            subarray_1 = context.get_device("low/elt/subarray_1")
            subarray_2 = context.get_device("low/elt/subarray_2")
            station_1 = context.get_device("low/elt/station_1")
            station_2 = context.get_device("low/elt/station_2")
            tile_1 = context.get_device("low/elt/tile_47")
            tile_2 = context.get_device("low/elt/tile_129")

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

            # now enable subarrays
            master.EnableSubarray(1)
            master.EnableSubarray(2)

            # allocate station 1 and tile 1 to subarray 1
            call_with_json(
                master.Allocate,
                subarray_id=1,
                stations=[True, False],
                tiles=[True, False]
            )

            # allocate station 2 and tile 2 to subarray 2
            call_with_json(
                master.Allocate,
                subarray_id=2,
                stations=[False, True],
                tiles=[False, True]
            )

            # check initial state
            assert list(subarray_1.stationFQDNs) == ["low/elt/station_1"]
            assert list(subarray_1.tileFQDNs) == ["low/elt/tile_47"]
            assert list(subarray_2.stationFQDNs) == ["low/elt/station_2"]
            assert list(subarray_2.tileFQDNs) == ["low/elt/tile_129"]
            assert station_1.subarrayId == 1
            assert station_2.subarrayId == 2
            assert tile_1.subarrayId == 1
            assert tile_2.subarrayId == 2

            master.Release(2)

            assert list(subarray_1.stationFQDNs) == ["low/elt/station_1"]
            assert list(subarray_1.tileFQDNs) == ["low/elt/tile_47"]
            assert subarray_2.stationFQDNs is None
            assert subarray_2.tileFQDNs is None
            assert station_1.subarrayId == 1
            assert station_2.subarrayId == 0
            assert tile_1.subarrayId == 1
            assert tile_2.subarrayId == 0

            with pytest.raises(DevFailed):
                master.Release(2)

            # check initial state
            assert list(subarray_1.stationFQDNs) == ["low/elt/station_1"]
            assert list(subarray_1.tileFQDNs) == ["low/elt/tile_47"]
            assert subarray_2.stationFQDNs is None
            assert subarray_2.tileFQDNs is None
            assert station_1.subarrayId == 1
            assert station_2.subarrayId == 0
            assert tile_1.subarrayId == 1
            assert tile_2.subarrayId == 0

            master.Release(1)

            # check initial state
            assert subarray_1.stationFQDNs is None
            assert subarray_1.tileFQDNs is None
            assert subarray_2.stationFQDNs is None
            assert subarray_2.tileFQDNs is None
            assert station_1.subarrayId == 0
            assert station_2.subarrayId == 0
            assert tile_1.subarrayId == 0
            assert tile_2.subarrayId == 0
