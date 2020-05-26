# flake8: noqa
"""
Basic order of proceedings for an iTango demo in Malte's k8s environment
"""

# Test master enabling and disabling subarray
master = DeviceProxy("low/elt/master")
subarray = DeviceProxy("low/elt/subarray_1")
subarray.adminMode  # subarray is offline

master.DisableSubarray(1)  # error: subarray is already disabled

master.EnableSubarray(1)
subarray.adminMode  # subarray is online

master.EnableSubarray(1)  # error: subarray is already enabled

master.DisableSubarray(1)
subarray.adminMode  # subarray is offline


# Test master allocating and releasing resources
master.Allocate('{"subarray_id": 1, "stations": ["low/elt/station_1", "low/elt.station_2"]}')  # error: cannot allocate resources to disabled subarray

master.EnableSubarray(1)
master.Allocate('{"subarray_id": 1, "stations": ["low/elt/station_1", "low/elt.station_2"]}')  # error: cannot allocate resources to disabled subarray
subarray.stationFQDNs  # ('low/elt/station_1', 'low/elt/station_2')

master.Release(1)
subarray.stationFQDNs  # empty

master.DisableSubarray(1)