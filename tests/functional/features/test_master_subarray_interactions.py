"""
This module contains the pytest-bdd implementation of the Gherkin BDD
tests for the SKA Low MCCS prototype
"""

from pytest_bdd import scenario, given, when, then, parsers
from tango import DevState

from ska.low.mccs import (
    MccsMaster,
    MccsSubarray,
    MccsStation,
    MccsStationBeam,
    MccsTile,
    MccsAntenna,
)

# from ska.low.mccs.utils import call_with_json


_NUM_SUBARRAYS = 2
_NUM_STATIONS = 2
_NUM_BEAMS = 1
_NUM_TILES = 4
_NUM_ANTENNAS = 4


devices_info = [
    {
        "class": MccsMaster,
        "devices": (
            {
                "name": "low/elt/master",
                "properties": {
                    "MccsSubarrays": [
                        f"low/elt/subarray_{id}" for id in range(1, _NUM_SUBARRAYS + 1)
                    ],
                    "MccsStations": [
                        f"low/elt/station_{id}" for id in range(1, _NUM_STATIONS + 1)
                    ],
                },
            },
        ),
    },
    {
        "class": MccsSubarray,
        "devices": [
            {
                "name": f"low/elt/subarray_{id}",
                "properties": {"CapabilityTypes": ["BAND1", "BAND2"]},
            }
            for id in range(1, _NUM_SUBARRAYS + 1)
        ],
    },
    {
        "class": MccsStation,
        "devices": [
            {
                "name": "low/elt/station_1",
                "properties": {
                    "TileFQDNs": [f"low/elt/tile_{id}" for id in range(1, 3)],
                    "AntennaFQDNs": [f"low/elt/antenna_{id}" for id in range(1, 3)],
                    "LoggingLevelDefault": 3,
                },
            },
            {
                "name": "low/elt/station_2",
                "properties": {
                    "TileFQDNs": [f"low/elt/tile_{id}" for id in range(3, 5)],
                    "AntennaFQDNs": [f"low/elt/antenna_{id}" for id in range(3, 5)],
                    "LoggingLevelDefault": 3,
                },
            },
        ],
    },
    {
        "class": MccsStationBeam,
        "devices": [
            {"name": f"low/elt/beam_{id}", "properties": {"BeamId": id}}
            for id in range(1, _NUM_BEAMS + 1)
        ],
    },
    {
        "class": MccsTile,
        "devices": [
            {
                "name": f"low/elt/tile_{id}",
                "properties": {"TileId": id, "LoggingLevelDefault": 3},
            }
            for id in range(1, _NUM_TILES + 1)
        ],
    },
    {
        "class": MccsAntenna,
        "devices": [
            {"name": f"low/elt/antenna_{id}", "properties": {"LoggingLevelDefault": 3}}
            for id in range(1, _NUM_ANTENNAS + 1)
        ],
    },
]


@given("we have master", target_fixture="master")
def we_have_master(tango_context):
    """
    Returns a DeviceProxy to the master device; accessible as "master"
    fixture

    :param tango_context: fixture that provides a tango context of some
        sort
    :type tango_context: a tango context of some sort; possibly a
        MultiDeviceTestContext, possibly the real thing. The only
        requirement is that it provide a "get_device(fqdn)" method that
        returns a DeviceProxy.
    :returns: a DeviceProxy to the master device
    :rtype: DeviceProxy
    """
    return tango_context.get_device("low/elt/master")


@given("we have subarray 1", target_fixture="subarray_1")
def we_have_subarray_1(tango_context):
    """
    Returns a DeviceProxy to the subarray_1 device; accessible as
    "subarrray_1" fixture

    :param tango_context: fixture that provides a tango context of some
        sort
    :type tango_context: a tango context of some sort; possibly a
        MultiDeviceTestContext, possibly the real thing. The only
        requirement is that it provide a "get_device(fqdn)" method that
        returns a DeviceProxy.
    :returns: a DeviceProxy to the subarray_1 device
    :rtype: DeviceProxy
    """
    return tango_context.get_device("low/elt/subarray_1")


@given("we have subarray 2", target_fixture="subarray_2")
def we_have_subarray_2(tango_context):
    """
    Returns a DeviceProxy to the subarray_2 device; accessible as
    "subarrray_2" fixture

    :param tango_context: fixture that provides a tango context of some
        sort
    :type tango_context: a tango context of some sort; possibly a
        MultiDeviceTestContext, possibly the real thing. The only
        requirement is that it provide a "get_device(fqdn)" method that
        returns a DeviceProxy.
    :returns: a DeviceProxy to the subarray_2 device
    :rtype: DeviceProxy
    """
    return tango_context.get_device("low/elt/subarray_2")


@given("we have station 1", target_fixture="station_1")
def we_have_station_1(tango_context):
    """
    Returns a DeviceProxy to the station_1 device; accessible as
    "station_1" fixture

    :param tango_context: fixture that provides a tango context of some
        sort
    :type tango_context: a tango context of some sort; possibly a
        MultiDeviceTestContext, possibly the real thing. The only
        requirement is that it provide a "get_device(fqdn)" method that
        returns a DeviceProxy.
    :returns: a DeviceProxy to the station_2 device
    :rtype: DeviceProxy
    """
    return tango_context.get_device("low/elt/station_1")


@given("we have station 2", target_fixture="station_2")
def we_have_station_2(tango_context):
    """
    Returns a DeviceProxy to the station_2 device; accessible as
    "station_2" fixture

    :param tango_context: fixture that provides a tango context of some
        sort
    :type tango_context: a tango context of some sort; possibly a
        MultiDeviceTestContext, possibly the real thing. The only
        requirement is that it provide a "get_device(fqdn)" method that
        returns a DeviceProxy.
    :returns: a DeviceProxy to the station_2 device
    :rtype: DeviceProxy
    """
    return tango_context.get_device("low/elt/station_2")


@given("we have tile 1", target_fixture="tile_1")
def we_have_tile_1(tango_context):
    """
    Returns a DeviceProxy to the tile_1 device; accessible as
    "tile_1" fixture

    :param tango_context: fixture that provides a tango context of some
        sort
    :type tango_context: a tango context of some sort; possibly a
        MultiDeviceTestContext, possibly the real thing. The only
        requirement is that it provide a "get_device(fqdn)" method that
        returns a DeviceProxy.
    :returns: a DeviceProxy to the tile_1 device
    :rtype: DeviceProxy
    """
    return tango_context.get_device("low/elt/tile_1")


@given("we have tile 2", target_fixture="tile_2")
def we_have_tile_2(tango_context):
    """
    Returns a DeviceProxy to the tile_2 device; accessible as
    "tile_2" fixture

    :param tango_context: fixture that provides a tango context of some
        sort
    :type tango_context: a tango context of some sort; possibly a
        MultiDeviceTestContext, possibly the real thing. The only
        requirement is that it provide a "get_device(fqdn)" method that
        returns a DeviceProxy.
    :returns: a DeviceProxy to the tile_2 device
    :rtype: DeviceProxy
    """
    return tango_context.get_device("low/elt/tile_2")


@given("we have tile 3", target_fixture="tile_3")
def we_have_tile_3(tango_context):
    """
    Returns a DeviceProxy to the tile_3 device; accessible as
    "tile_3" fixture

    :param tango_context: fixture that provides a tango context of some
        sort
    :type tango_context: a tango context of some sort; possibly a
        MultiDeviceTestContext, possibly the real thing. The only
        requirement is that it provide a "get_device(fqdn)" method that
        returns a DeviceProxy.
    :returns: a DeviceProxy to the tile_3 device
    :rtype: DeviceProxy
    """
    return tango_context.get_device("low/elt/tile_3")


@given("we have tile 4", target_fixture="tile_4")
def we_have_tile_4(tango_context):
    """
    Returns a DeviceProxy to the tile_4 device; accessible as
    "tile_4" fixture

    :param tango_context: fixture that provides a tango context of some
        sort
    :type tango_context: a tango context of some sort; possibly a
        MultiDeviceTestContext, possibly the real thing. The only
        requirement is that it provide a "get_device(fqdn)" method that
        returns a DeviceProxy.
    :returns: a DeviceProxy to the tile_4 device
    :rtype: DeviceProxy
    """
    return tango_context.get_device("low/elt/tile_4")


@given("we have tile 5", target_fixture="tile_5")
def we_have_tile_5(tango_context):
    """
    Returns a DeviceProxy to the tile_5 device; accessible as
    "tile_5" fixture

    :param tango_context: fixture that provides a tango context of some
        sort
    :type tango_context: a tango context of some sort; possibly a
        MultiDeviceTestContext, possibly the real thing. The only
        requirement is that it provide a "get_device(fqdn)" method that
        returns a DeviceProxy.
    :returns: a DeviceProxy to the tile_5 device
    :rtype: DeviceProxy
    """
    return tango_context.get_device("low/elt/tile_5")


@given("we have tile 6", target_fixture="tile_6")
def we_have_tile_6(tango_context):
    """
    Returns a DeviceProxy to the tile_6 device; accessible as
    "tile_6" fixture

    :param tango_context: fixture that provides a tango context of some
        sort
    :type tango_context: a tango context of some sort; possibly a
        MultiDeviceTestContext, possibly the real thing. The only
        requirement is that it provide a "get_device(fqdn)" method that
        returns a DeviceProxy.
    :returns: a DeviceProxy to the tile_6 device
    :rtype: DeviceProxy
    """
    return tango_context.get_device("low/elt/tile_6")


@scenario("master_subarray_interactions.feature", "Master is turned on")
def test_master_is_turned_on():
    """
    This is run at the end of the scenario; does nothing at present
    because our assertions are captured in the THEN step.
    """
    pass


@given("master is off")
def master_is_off(master):
    """
    Asserts that the master device is off

    :param master: fixture that provides a DeviceProxy to the master
        device
    :type master: DeviceProxy
    """
    assert master.state() == DevState.OFF


@given("station 1 is off")
def station_1_is_off(station_1):
    """
    Asserts that the station_1 device is off

    :param station_1: fixture that provides a DeviceProxy to the station_1
        device
    :type master: DeviceProxy
    """
    assert station_1.state() == DevState.OFF


@given("station 2 is off")
def station_2_is_off(station_2):
    """
    Asserts that the station_2 device is off

    :param station_2: fixture that provides a DeviceProxy to the station_2
        device
    :type master: DeviceProxy
    """
    assert station_2.state() == DevState.OFF


@given("tile 1 is off")
def tile_1_is_off(tile_1):
    """
    Asserts that the tile_1 device is off

    :param tile_1: fixture that provides a DeviceProxy to the tile_1
        device
    :type master: DeviceProxy
    """
    assert tile_1.state() == DevState.OFF


@given("tile 2 is off")
def tile_2_is_off(tile_2):
    """
    Asserts that the tile_2 device is off

    :param tile_2: fixture that provides a DeviceProxy to the tile_2
        device
    :type master: DeviceProxy
    """
    assert tile_2.state() == DevState.OFF


@given("tile 3 is off")
def tile_3_is_off(tile_3):
    """
    Asserts that the tile_3 device is off

    :param tile_3: fixture that provides a DeviceProxy to the tile_3
        device
    :type master: DeviceProxy
    """
    assert tile_3.state() == DevState.OFF


@given("tile 4 is off")
def tile_4_is_off(tile_4):
    """
    Asserts that the tile_4 device is off

    :param tile_4: fixture that provides a DeviceProxy to the tile_4
        device
    :type master: DeviceProxy
    """
    assert tile_4.state() == DevState.OFF


@given("tile 5 is off")
def tile_5_is_off(tile_5):
    """
    Asserts that the tile_5 device is off

    :param tile_5: fixture that provides a DeviceProxy to the tile_5
        device
    :type master: DeviceProxy
    """
    assert tile_5.state() == DevState.OFF


@given("tile 6 is off")
def tile_6_is_off(tile_6):
    """
    Asserts that the tile_6 device is off

    :param tile_6: fixture that provides a DeviceProxy to the tile_6
        device
    :type master: DeviceProxy
    """
    assert tile_6.state() == DevState.OFF


@when("we turn master on")
def we_turn_master_on(master):
    """
    Turns the master device on

    :param master: fixture that provides a DeviceProxy to the master
        device
    :type master: DeviceProxy
    """
    master.On()


@then("master should be on")
def master_should_be_on(master):
    """
    Asserts that the master device is on

    :param master: fixture that provides a DeviceProxy to the master
        device
    :type master: DeviceProxy
    """
    assert master.state() == DevState.ON


@then("station 1 should be on")
def station_1_should_be_on(station_1):
    """
    Asserts that the station_1 device is on

    :param station_1: fixture that provides a DeviceProxy to the station_1
        device
    :type master: DeviceProxy
    """
    assert station_1.state() == DevState.ON


@then("station 2 should be on")
def station_2_should_be_on(station_2):
    """
    Asserts that the station_2 device is on

    :param station_2: fixture that provides a DeviceProxy to the station_2
        device
    :type master: DeviceProxy
    """
    assert station_2.state() == DevState.ON


@scenario("master_subarray_interactions.feature", "Master enables subarray")
def test_master_enables_subarray():
    """
    This is run at the end of the scenario; does nothing at present
    because our assertions are captured in the THEN step.
    """
    pass


@given("master is on")
def master_is_on(master):
    """
    Asserts that the master device is on

    :param master: fixture that provides a DeviceProxy to the master
        device
    :type master: DeviceProxy
    """
    assert master.state() == DevState.ON


@given("subarray 1 is off")
def subarray_1_is_off(subarray_1):
    """
    Asserts that the subarray_1 device is off

    :param subarray_1: fixture that provides a DeviceProxy to the subarray_1
        device
    :type subarray_1: DeviceProxy
    """
    assert subarray_1.state() == DevState.OFF


@given("subarray 2 is off")
def subarray_2_is_off(subarray_2):
    """
    Asserts that the subarray_2 device is off

    :param subarray_2: fixture that provides a DeviceProxy to the subarray_2
        device
    :type subarray_2: DeviceProxy
    """
    assert subarray_2.state() == DevState.OFF


@when(parsers.parse("we tell master to enable subarray {subarray_id:d}"))
def master_enables_subarray(master, subarray_id):
    """
    Tells master to enable a given subarray

    :param master: fixture that provides a DeviceProxy to the master
        device
    :type master: DeviceProxy
    :param subarray_id: master's id for the subarray to be turned on
    :type subarray_id: int
    """
    master.EnableSubarray(subarray_id)


@then(parsers.parse("subarray 1 should be on"))
def subarray_1_should_be_on(subarray_1):
    """
    Asserts that the subarray_1 device is on

    :param subarray_1: fixture that provides a DeviceProxy to the subarray_1
        device
    :type subarray_1: DeviceProxy
    """
    assert subarray_1.state() == DevState.ON


@then(parsers.parse("subarray 2 should be off"))
def subarray_2_should_be_off(subarray_2):
    """
    Asserts that the subarray_2 device is off

    :param subarray_2: fixture that provides a DeviceProxy to the subarray_2
        device
    :type subarray_2: DeviceProxy
    """
    assert subarray_2.state() == DevState.OFF


# @scenario(
#     "master_subarray_interactions.feature", "Master allocates stations to subarrays"
# )
# def test_subarray_allocation():
#     pass


# @given(parsers.parse("we have {station_count:d} stations"))
# def stations(station_count, tango_context):
#     return {
#         i: tango_context.get_device(f"low/elt/station_{i}")
#         for i in range(1, station_count + 1)
#     }


# @when(
#     parsers.parse(
#         "we tell master to allocate station {station_id:d} to subarray "
#         "{subarray_id:d}"
#     )
# )
# def master_allocates_station_to_subarray(master, subarray_id, station_id):
#     call_with_json(
#         master.Allocate,
#         subarray_id=subarray_id,
#         stations=[f"low/elt/station_{station_id}"],
#     )


# @then(
#     parsers.parse(
#         "the stations that subarray {subarray_id:d} thinks are allocated to it "
#         "should include station {station_id:d}"
#     )
# )
# def subarray_allocation_includes_station(subarrays, subarray_id, station_id):
#     assert f"low/elt/station_{station_id}" in subarrays[subarray_id].stationFQDNs


# @then(
#     parsers.parse(
#         "the subarray id of station {station_id:d} should be subarray {subarray_id:d}"
#     )
# )
# def subarray_id_of_station_is(stations, station_id, subarray_id):
#     assert stations[station_id].subarrayId == subarray_id
