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


from ska.base.control_model import HealthState
from ska.low.mccs.demo import ConnectionFailableTile
from conftest import confirm_initialised


devices_to_load = {
    "path": "charts/ska-low-mccs/data/configuration.json",
    "package": "ska.low.mccs",
    "devices": [
        # "controller",
        # "subarray_01",
        # "subarray_02",
        "station_001",
        # "station_002",
        "tile_0001",
        "tile_0002",
        # "tile_0003",
        # "tile_0004",
        "apiu_001",
        "antenna_000001",
        "antenna_000002",
        # "antenna_000003",
        # "antenna_000004",
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


def test(device_context):
    """
    Test that events are received

    :param device_context: fixture that provides a tango context of some
        sort
    :type device_context: a tango context of some sort; possibly a
        MultiDeviceTestContext, possibly the real thing. The only
        requirement is that it provide a "get_device(fqdn)" method that
        returns a DeviceProxy.
    """
    failable_tile = device_context.get_device("low-mccs/tile/0001")
    station = device_context.get_device("low-mccs/station/001")

    confirm_initialised([failable_tile, station])

    assert failable_tile.healthState == HealthState.OK
    sleep()
    assert station.healthState == HealthState.OK

    failable_tile.SimulateConnectionFailure(True)

    assert failable_tile.healthState == HealthState.FAILED
    sleep()
    assert station.healthState == HealthState.FAILED

    failable_tile.SimulateConnectionFailure(False)

    assert failable_tile.healthState == HealthState.OK
    sleep()
    assert station.healthState == HealthState.OK
