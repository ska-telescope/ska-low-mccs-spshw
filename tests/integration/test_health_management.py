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

import pytest

from ska.base.control_model import HealthState
from ska.low.mccs.tile.demo_tile_device import DemoTile
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
            "beam_001",
            "beam_002",
            "beam_003",
            "beam_004",
        ],
        "patch": {
            "tile_0001": DemoTile,
            "tile_0002": DemoTile,
            "tile_0003": DemoTile,
            "tile_0004": DemoTile,
        },
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
    Test that health rolls up to the controller.

    :param device_context: fixture that provides a tango context of some
        sort
    :type device_context: a tango context of some sort; possibly a
        MultiDeviceTestContext, possibly the real thing. The only
        requirement is that it provide a "get_device(fqdn)" method that
        returns a DeviceProxy.
    """
    controller = device_context.get_device("controller")
    station_1 = device_context.get_device("station_001")
    station_2 = device_context.get_device("station_002")
    subrack = device_context.get_device("subrack_01")
    tile_1 = device_context.get_device("tile_0001")
    tile_2 = device_context.get_device("tile_0002")
    tile_3 = device_context.get_device("tile_0003")
    tile_4 = device_context.get_device("tile_0004")
    # workaround for https://github.com/tango-controls/cppTango/issues/816
    # apiu_1 = device_context.get_device("apiu_001")

    # antenna_1 = device_context.get_device("antenna_000001")
    # antenna_2 = device_context.get_device("antenna_000002")
    # antenna_3 = device_context.get_device("antenna_000003")
    # antenna_4 = device_context.get_device("antenna_000004")

    # beam_1 = device_context.get_device("low-mccs/beam/001")
    # beam_2 = device_context.get_device("low-mccs/beam/002")
    # beam_3 = device_context.get_device("low-mccs/beam/003")
    # beam_4 = device_context.get_device("low-mccs/beam/004")

    # TODO: For now, we need to get our devices to OFF state (the highest state of
    # device readiness for a device that isn't actual on -- and a state in which the
    # hardware is turned on) before we can put them into ON state.
    # This is a counterintuitive mess that will be fixed in SP-1501.
    subrack.Off()
    subrack.On()
    tile_1.Off()
    tile_1.On()

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

    # tile_1.Off()
    # tile_1.Disable()
    # tile_1.adminMode = AdminMode.OFFLINE
    tile_1.TakeOffline()  # A single command to do all of the above, because webjive

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
    # tile_1.adminMode = AdminMode.ONLINE
    # tile_1.Off()
    # tile_1.On()
    tile_1.PutOnline()  # A single command to do all of the above, because webjive

    assert tile_1.healthState == HealthState.OK
    assert tile_2.healthState == HealthState.OK
    assert tile_3.healthState == HealthState.OK
    assert tile_4.healthState == HealthState.OK
    sleep()
    assert station_1.healthState == HealthState.OK
    assert station_2.healthState == HealthState.OK
    sleep()
    assert controller.healthState == HealthState.OK


def test_subarray_health_rollup(device_context):
    """
    Test that health rolls up to the subarray.

    :param device_context: fixture that provides a tango context of some
        sort
    :type device_context: a tango context of some sort; possibly a
        MultiDeviceTestContext, possibly the real thing. The only
        requirement is that it provide a "get_device(fqdn)" method that
        returns a DeviceProxy.
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

    # workaround for https://github.com/tango-controls/cppTango/issues/816
    # apiu_1 = device_context.get_device("apiu_001")
    # antenna_1 = device_context.get_device("antenna_000001")
    # antenna_2 = device_context.get_device("antenna_000002")
    # antenna_3 = device_context.get_device("antenna_000003")
    # antenna_4 = device_context.get_device("antenna_000004")
    # beam_1 = device_context.get_device("low-mccs/beam/001")
    # beam_2 = device_context.get_device("low-mccs/beam/002")
    # beam_3 = device_context.get_device("low-mccs/beam/003")
    # beam_4 = device_context.get_device("low-mccs/beam/004")

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

    assert subarray_1.healthState == HealthState.OK
    assert subarray_2.healthState == HealthState.OK

    _ = controller.Startup()

    _ = call_with_json(
        controller.Allocate, subarray_id=1, station_ids=[1], station_beams=[1]
    )
    _ = call_with_json(
        controller.Allocate, subarray_id=2, station_ids=[2], station_beams=[2]
    )

    sleep()

    assert subarray_1.healthState == HealthState.OK
    assert subarray_2.healthState == HealthState.OK

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
    assert subarray_1.healthState == HealthState.DEGRADED
    assert subarray_2.healthState == HealthState.OK
    assert controller.healthState == HealthState.DEGRADED

    # It might take some time to replace the failed tile 1, and
    # meanwhile we don't want it alarming for weeks. Let's disable it,
    # then take it offline. The tile will still report itself as FAILED,
    # but station will not take it into account when calculating its own
    # health.

    # tile_1.Off()
    # tile_1.Disable()
    # tile_1.adminMode = AdminMode.OFFLINE
    tile_1.TakeOffline()  # A single command to all both of the above, because webjive

    assert tile_1.healthState == HealthState.FAILED
    assert tile_2.healthState == HealthState.OK
    assert tile_3.healthState == HealthState.OK
    assert tile_4.healthState == HealthState.OK
    sleep()
    assert station_1.healthState == HealthState.OK
    assert station_2.healthState == HealthState.OK
    sleep()
    assert subarray_1.healthState == HealthState.OK
    assert subarray_2.healthState == HealthState.OK
    assert controller.healthState == HealthState.OK

    # Okay, we've finally fixed the tile. Let's make it work again, and
    # put it back online
    tile_1.SimulateConnectionFailure(False)

    # tile_1.adminMode = AdminMode.ONLINE
    # tile_1.Off()
    # tile_1.On()
    tile_1.PutOnline()  # A single command to do all of the above, because webjive

    assert tile_1.healthState == HealthState.OK
    assert tile_2.healthState == HealthState.OK
    assert tile_3.healthState == HealthState.OK
    assert tile_4.healthState == HealthState.OK
    sleep()
    assert station_1.healthState == HealthState.OK
    assert station_2.healthState == HealthState.OK
    sleep()
    assert subarray_1.healthState == HealthState.OK
    assert subarray_2.healthState == HealthState.OK
    assert controller.healthState == HealthState.OK
