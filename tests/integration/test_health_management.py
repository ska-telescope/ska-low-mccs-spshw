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

from ska_tango_base.control_model import AdminMode, HealthState

from ska.low.mccs import MccsDeviceProxy
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
            {"name": "controller", "proxy": MccsDeviceProxy},
            {"name": "subarray_01", "proxy": MccsDeviceProxy},
            {"name": "subarray_02", "proxy": MccsDeviceProxy},
            {"name": "station_001", "proxy": MccsDeviceProxy},
            {"name": "station_002", "proxy": MccsDeviceProxy},
            {"name": "subrack_01", "proxy": MccsDeviceProxy},
            {"name": "tile_0001", "proxy": MccsDeviceProxy, "patch": DemoTile},
            {"name": "tile_0002", "proxy": MccsDeviceProxy, "patch": DemoTile},
            {"name": "tile_0003", "proxy": MccsDeviceProxy, "patch": DemoTile},
            {"name": "tile_0004", "proxy": MccsDeviceProxy, "patch": DemoTile},
            {"name": "beam_001", "proxy": MccsDeviceProxy},
            {"name": "beam_002", "proxy": MccsDeviceProxy},
            {"name": "beam_003", "proxy": MccsDeviceProxy},
            {"name": "beam_004", "proxy": MccsDeviceProxy},
        ],
    }


def sleep(seconds=0.2):
    """
    Sleep for a short time. Used to allow time for events to be pushed
    through the events subsystem.

    :param seconds: number of seconds to sleep; optional, defaults to 0.1
    :type seconds: float
    """
    time.sleep(seconds)


def test_controller_health_rollup(device_context):
    """
    Test that health rolls up to the controller.

    :param device_context: A tango context of some sort; possibly a
        :py:class:`tango.test_context.MultiDeviceTestContext`, possibly
        the real thing. The only requirement is that it provide a
        ``get_device(fqdn)`` method that returns a
        :py:class:`tango.DeviceProxy`.
    :type device_context: :py:class:`contextmanager`
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
    _ = controller.Startup()

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

    # TODO: This bit of the test no longer functions as intended. The
    # idea was to put the failing tile into OFFLINE mode, and we would
    # see that it continues to report HealthState.FAILED, but the
    # station to which it belongs would stop rolling its healthState up
    # so its own health would return to HealthState.OK.
    # But at present
    # * we can't take the tile OFFLINE until we have DISABLEd it
    # * DISABLing it means telling the subrack to deny power to the
    #   TPM
    # * and at that point the tile device no longer recognises the
    #   connection failure as a failure state -- because of course it
    #   can't connect to the TPM if it isn't even powered!
    # Hopefully this will be fixed in SP-1501: we'll be able to put the
    # device into OFFLINE mode without turning the TPM off.

    # It might take some time to replace the failed tile 1, and
    # meanwhile we don't want it alarming for weeks. Let's disable it,
    # then take it offline. The tile will still report itself as FAILED,
    # but station will not take it into account when calculating its own
    # health.

    tile_1.Off()
    tile_1.Disable()
    tile_1.adminMode = AdminMode.OFFLINE

    # assert tile_1.healthState == HealthState.FAILED
    assert tile_1.healthState == HealthState.UNKNOWN  # see above

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

    assert not subrack.isTpmOn(1)
    tile_1.Off()
    assert subrack.isTpmOn(1)

    tile_1.On()
    sleep()
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

    :param device_context: A tango context of some sort; possibly a
        :py:class:`tango.test_context.MultiDeviceTestContext`, possibly
        the real thing. The only requirement is that it provide a
        ``get_device(fqdn)`` method that returns a
        :py:class:`tango.DeviceProxy`.
    :type device_context: :py:class:`contextmanager`
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

    _ = controller.Startup()

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

    tile_1.Off()
    tile_1.Disable()
    tile_1.adminMode = AdminMode.OFFLINE

    # assert tile_1.healthState == HealthState.FAILED
    assert tile_1.healthState == HealthState.UNKNOWN  # see above
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

    tile_1.adminMode = AdminMode.ONLINE
    tile_1.Off()
    tile_1.On()

    sleep()
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
