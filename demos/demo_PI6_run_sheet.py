# flake8: noqa
"""
Basic order of proceedings for an iTango demo in Malte's k8s environment
"""

# Test master enabling and disabling subarray
master = DeviceProxy("low-mccs/master/1")
subarray = DeviceProxy("low-mccs/subarray/01")
station_1 = DeviceProxy("low-mccs/station/001")
station_2 = DeviceProxy("low-mccs/station/002")
tile_1 = DeviceProxy("low-mccs/tile/0001")
tile_2 = DeviceProxy("low-mccs/tile/0002")
tile_3 = DeviceProxy("low-mccs/tile/0003")
tile_4 = DeviceProxy("low-mccs/tile/0004")

subarray_1.adminMode  # subarray is offline

master.DisableSubarray(1)  # error: subarray is already disabled

master.EnableSubarray(1)
subarray.adminMode  # subarray is online

master.EnableSubarray(1)  # error: subarray is already enabled

master.DisableSubarray(1)
subarray.adminMode  # subarray is offline


# Test master allocating and releasing resources
master.Allocate(
    '{"subarray_id": 1, "stations": ["low-mccs/station/001", "low-mccs/station/002"]}'
)  # error: cannot allocate resources to disabled subarray

master.EnableSubarray(1)

master.Allocate('{"subarray_id": 1, "stations": ["low-mccs/station/001"]}')

subarray.stationFQDNs  # ('low-mccs/station/001')
station_1.subarray_id  # 1 - this is allocated to subarray 1
tile_1.subarray_id  # 1 - this is attached to station 1, so allocated to subarray 1
tile_2.subarray_id  # 1 - this is attached to station 1, so allocated to subarray 1

station_2.subarray_id  # 0 - this is unallocated
tile_1.subarray_id  # 1 - this is attached to station 2, so unallocated
tile_2.subarray_id  # 1 - this is attached to station 2, so unallocated

master.Release(1)
subarray.stationFQDNs  # empty

master.DisableSubarray(1)
