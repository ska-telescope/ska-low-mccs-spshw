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
This test module contains integration tests that exercise the health
management functionality of the SKA Low MCCS system.
"""
import time

from ska.base.control_model import AdminMode, HealthState
from ska.low.mccs.demo import ConnectionFailableTile
from conftest import confirm_initialised


devices_to_load = {
    "path": "charts/ska-low-mccs/data/configuration.json",
    "package": "ska.low.mccs",
    "devices": [
        "controller",
        # "subarray_01",
        # "subarray_02",
        "station_001",
        "station_002",
        "tile_0001",
        "tile_0002",
        "tile_0003",
        "tile_0004",
        "apiu_001",
        "antenna_000001",
        "antenna_000002",
        "antenna_000003",
        "antenna_000004",
    ],
    "patch": {"low-mccs/tile/0001": ConnectionFailableTile},
}


def sleep(seconds=0.1):
    """
    Sleep for a short time. Used to allow time for events to be pushed
    through the events subsystem.

    :param seconds: number of seconds to sleep, defaults to 0.1
    :type seconds: float, optional
    """
    time.sleep(seconds)


def test_controller_health_rollup(device_context):
    """
    Test that health rolls up to the controller

    :param device_context: fixture that provides a tango context of some
        sort
    :type device_context: a tango context of some sort; possibly a
        MultiDeviceTestContext, possibly the real thing. The only
        requirement is that it provide a "get_device(fqdn)" method that
        returns a DeviceProxy.
    """
    controller = device_context.get_device("low-mccs/control/control")
    station_1 = device_context.get_device("low-mccs/station/001")
    station_2 = device_context.get_device("low-mccs/station/002")
    tile_1 = device_context.get_device("low-mccs/tile/0001")
    tile_2 = device_context.get_device("low-mccs/tile/0002")
    tile_3 = device_context.get_device("low-mccs/tile/0003")
    tile_4 = device_context.get_device("low-mccs/tile/0004")
    apiu_1 = device_context.get_device("low-mccs/apiu/001")
    antenna_1 = device_context.get_device("low-mccs/antenna/000001")
    antenna_2 = device_context.get_device("low-mccs/antenna/000002")
    antenna_3 = device_context.get_device("low-mccs/antenna/000003")
    antenna_4 = device_context.get_device("low-mccs/antenna/000004")

    confirm_initialised(
        [
            controller,
            station_1,
            station_2,
            tile_1,
            tile_2,
            tile_3,
            tile_4,
            apiu_1,
            antenna_1,
            antenna_2,
            antenna_3,
            antenna_4,
        ]
    )

    # Check that all devices are OK
    assert tile_1.healthState == HealthState.OK
    assert tile_2.healthState == HealthState.OK
    assert tile_3.healthState == HealthState.OK
    assert tile_4.healthState == HealthState.OK
    sleep()
    assert station_1.healthState == HealthState.OK
    assert station_2.healthState == HealthState.OK
    sleep()
    assert controller.healthState == HealthState.OK

    # Now let's make tile 1 fail. We should see that failure
    # propagate up to station and then to controller
    tile_1.SimulateConnectionFailure(True)

    assert tile_1.healthState == HealthState.FAILED
    assert tile_2.healthState == HealthState.OK
    assert tile_3.healthState == HealthState.OK
    assert tile_4.healthState == HealthState.OK
    sleep()
    assert station_1.healthState == HealthState.DEGRADED
    assert station_2.healthState == HealthState.OK
    sleep()
    assert controller.healthState == HealthState.DEGRADED

    # It might take some time to replace the failed tile 1, and
    # meanwhile we don't want it alarming for weeks. Let's disable it,
    # then take it offline. The tile will still report itself as FAILED,
    # but station will not take it into account when calculating its own
    # health.
    tile_1.Disable()
    tile_1.adminMode = AdminMode.OFFLINE

    assert tile_1.healthState == HealthState.FAILED
    assert tile_2.healthState == HealthState.OK
    assert tile_3.healthState == HealthState.OK
    assert tile_4.healthState == HealthState.OK
    sleep()
    assert station_1.healthState == HealthState.OK
    assert station_2.healthState == HealthState.OK
    sleep()
    assert controller.healthState == HealthState.OK

    # Okay, we've finally fixed the tile. Let's make it work again, and
    # put it back online
    tile_1.SimulateConnectionFailure(False)
    tile_1.adminMode = AdminMode.ONLINE

    assert tile_1.healthState == HealthState.OK
    assert tile_2.healthState == HealthState.OK
    assert tile_3.healthState == HealthState.OK
    assert tile_4.healthState == HealthState.OK
    sleep()
    assert station_1.healthState == HealthState.OK
    assert station_2.healthState == HealthState.OK
    sleep()
    assert controller.healthState == HealthState.OK


# def test_subarray_health_rollup(device_context):
#     """
#     Test that health rolls up to the controller

#     :param device_context: fixture that provides a tango context of some
#         sort
#     :type device_context: a tango context of some sort; possibly a
#         MultiDeviceTestContext, possibly the real thing. The only
#         requirement is that it provide a "get_device(fqdn)" method that
#         returns a DeviceProxy.
#     """
#     controller = device_context.get_device("low-mccs/control/control")
#     subarray_1 = device_context.get_device("low-mccs/subarray/001")
#     subarray_2 = device_context.get_device("low-mccs/subarray/002")
#     station_1 = device_context.get_device("low-mccs/station/001")
#     station_2 = device_context.get_device("low-mccs/station/002")
#     tile_1 = device_context.get_device("low-mccs/tile/0001")
#     tile_2 = device_context.get_device("low-mccs/tile/0002")
#     tile_3 = device_context.get_device("low-mccs/tile/0003")
#     tile_4 = device_context.get_device("low-mccs/tile/0004")
#     apiu_1 = device_context.get_device("low-mccs/apiu/001")
#     antenna_1 = device_context.get_device("low-mccs/antenna/000001")
#     antenna_2 = device_context.get_device("low-mccs/antenna/000002")
#     antenna_3 = device_context.get_device("low-mccs/antenna/000003")
#     antenna_4 = device_context.get_device("low-mccs/antenna/000004")

#     confirm_initialised(
#         [
#             controller,
#             subarray_1,
#             subarray_2,
#             station_1,
#             station_2,
#             tile_1,
#             tile_2,
#             tile_3,
#             tile_4,
#             apiu_1,
#             antenna_1,
#             antenna_2,
#             antenna_3,
#             antenna_4,
#         ]
#     )

#     # Check that all devices are OK
#     assert tile_1.healthState == HealthState.OK
#     assert tile_2.healthState == HealthState.OK
#     assert tile_3.healthState == HealthState.OK
#     assert tile_4.healthState == HealthState.OK
#     sleep()
#     assert station_1.healthState == HealthState.OK
#     assert station_2.healthState == HealthState.OK
#     sleep()
#     assert controller.healthState == HealthState.OK

#     assert subarray_1.healthState == HealthState.OK
#     assert subarray_2.healthState == HealthState.OK

#     _ = call_with_json(
#         controller.Allocate, subarray_id=1, station_ids=[1]
#     )
#     _ = call_with_json(
#         controller.Allocate, subarray_id=2, station_ids=[2]
#     )

#     sleep()

#     assert subarray_1.healthState == HealthState.OK
#     assert subarray_2.healthState == HealthState.OK


#     # Now let's make tile 1 fail. We should see that failure
#     # propagate up to station and then to controller
#     tile_1.SimulateConnectionFailure(True)

#     assert tile_1.healthState == HealthState.FAILED
#     assert tile_2.healthState == HealthState.OK
#     assert tile_3.healthState == HealthState.OK
#     assert tile_4.healthState == HealthState.OK
#     sleep()
#     assert station_1.healthState == HealthState.DEGRADED
#     assert station_2.healthState == HealthState.OK
#     sleep()
#     assert subarray_1.healthState == HealthState.DEGRADED
#     assert subarray_2.healthState == HealthState.OK
#     assert controller.healthState == HealthState.DEGRADED

#     # It might take some time to replace the failed tile 1, and
#     # meanwhile we don't want it alarming for weeks. Let's disable it,
#     # then take it offline. The tile will still report itself as FAILED,
#     # but station will not take it into account when calculating its own
#     # health.
#     tile_1.Disable()
#     tile_1.adminMode = AdminMode.OFFLINE

#     assert tile_1.healthState == HealthState.FAILED
#     assert tile_2.healthState == HealthState.OK
#     assert tile_3.healthState == HealthState.OK
#     assert tile_4.healthState == HealthState.OK
#     sleep()
#     assert station_1.healthState == HealthState.OK
#     assert station_2.healthState == HealthState.OK
#     sleep()
#     assert subarray_1.healthState == HealthState.OK
#     assert subarray_2.healthState == HealthState.OK
#     assert controller.healthState == HealthState.OK

#     # Okay, we've finally fixed the tile. Let's make it work again, and
#     # put it back online
#     tile_1.SimulateConnectionFailure(False)
#     tile_1.adminMode = AdminMode.ONLINE

#     assert tile_1.healthState == HealthState.OK
#     assert tile_2.healthState == HealthState.OK
#     assert tile_3.healthState == HealthState.OK
#     assert tile_4.healthState == HealthState.OK
#     sleep()
#     assert station_1.healthState == HealthState.OK
#     assert station_2.healthState == HealthState.OK
#     sleep()
#     assert subarray_1.healthState == HealthState.OK
#     assert subarray_2.healthState == HealthState.OK
#     assert controller.healthState == HealthState.OK
