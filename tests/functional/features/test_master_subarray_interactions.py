"""
This module contains the pytest-bdd implementation of the Gherkin BDD
tests for the SKA Low MCCS prototype
"""

from pytest_bdd import scenario, given, when, then, parsers
from tango import DevState

devices_to_load = {
    "path": "charts/mccs/data/configuration.json",
    "package": "ska.low.mccs",
    "devices": [
        "master",
        "subarray1",
        "subarray2",
        "station1",
        "station2",
        "tile1",
        "tile2",
        "tile3",
        "tile4",
        "antenna1",
        "antenna2",
        "antenna3",
        "antenna4",
    ],
}


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


@given(
    parsers.parse("we have {subarray_count:d} subarrays"), target_fixture="subarrays"
)
def we_have_n_subarrays(tango_context, subarray_count):
    """
    Returns device proxies to the subarray devices; accessible as "subarrays" fixture

    :param tango_context: fixture that provides a tango context of some
        sort
    :type tango_context: a tango context of some sort; possibly a
        MultiDeviceTestContext, possibly the real thing. The only
        requirement is that it provide a "get_device(fqdn)" method that
        returns a DeviceProxy.
    :param subarray_count: number of subarrays we have
    :type subarray_count: int
    :returns: a sequence of subarrays
    :rtype: list of DeviceProxy
    """
    return [
        tango_context.get_device(f"low/elt/subarray_{i+1}")
        for i in range(subarray_count)
    ]


@given(parsers.parse("we have {station_count:d} stations"), target_fixture="stations")
def we_have_n_stations(tango_context, station_count):
    """
    Returns device proxies to the station devices; accessible as "stations" fixture

    :param tango_context: fixture that provides a tango context of some
        sort
    :type tango_context: a tango context of some sort; possibly a
        MultiDeviceTestContext, possibly the real thing. The only
        requirement is that it provide a "get_device(fqdn)" method that
        returns a DeviceProxy.
    :param station_count: number of stations we have
    :type station_count: int
    :returns: a sequence of stations
    :rtype: list of DeviceProxy
    """
    return [
        tango_context.get_device(f"low/elt/station_{i+1}") for i in range(station_count)
    ]


@given(parsers.parse("we have {tile_count:d} tiles"), target_fixture="tiles")
def we_have_n_tiles(tango_context, tile_count):
    """
    Returns device proxies to the tile devices; accessible as "tiles" fixture

    :param tango_context: fixture that provides a tango context of some
        sort
    :type tango_context: a tango context of some sort; possibly a
        MultiDeviceTestContext, possibly the real thing. The only
        requirement is that it provide a "get_device(fqdn)" method that
        returns a DeviceProxy.
    :param tile_count: number of tiles we have
    :type tile_count: int
    :returns: a sequence of tiles
    :rtype: list of DeviceProxy
    """
    return [tango_context.get_device(f"low/elt/tile_{i+1}") for i in range(tile_count)]


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


@given(parsers.parse("station {station_id:d} is off"))
def station_n_is_off(stations, station_id):
    """
    Asserts that the nth station device is off

    :param stations: sequence of stations
    :type stations: list of DeviceProxy
    :param station_id: id of the station to check
    :type station_id: int
    """
    assert stations[station_id - 1].state() == DevState.OFF


@given(parsers.parse("tile {tile_id:d} is off"))
def tile_n_is_off(tiles, tile_id):
    """
    Asserts that the nth tile device is off

    :param tiles: sequence of tiles
    :type tiles: list of DeviceProxy
    :param tile_id: id of the station to check
    :type tile_id: int
    """
    assert tiles[tile_id - 1].state() == DevState.OFF


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


@then(parsers.parse("station {station_id:d} should be on"))
def station_n_should_be_on(stations, station_id):
    """
    Asserts that the nth station device is on

    :param stations: sequence of stations
    :type stations: list of DeviceProxy
    :param station_id: id of the station to check
    :type station_id: int
    """
    assert stations[station_id - 1].state() in (DevState.ON, DevState.ALARM)


@then(parsers.parse("tile {tile_id:d} should be on"))
def tile_n_should_be_on(tiles, tile_id):
    """
    Asserts that the nth tile device is on

    :param tiles: sequence of tiles
    :type tiles: list of DeviceProxy
    :param tile_id: id of the tile to check
    :type tile_id: int
    """
    assert tiles[tile_id - 1].state() in (DevState.ON, DevState.ALARM)


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


@given(parsers.parse("subarray {subarray_id:d} is off"))
def subarray_n_is_off(subarrays, subarray_id):
    """
    Asserts that the nth subarray device is off

    :param subarrays: sequence of subarrays
    :type subarrays: list of DeviceProxy
    :param subarray_id: id of the subarray to check
    :type subarray_id: int
    """
    assert subarrays[subarray_id - 1].state() == DevState.OFF


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


@then(parsers.parse("subarray {subarray_id:d} should be on"))
def subarray_n_should_be_on(subarrays, subarray_id):
    """
    Asserts that the nth subarray device is on

    :param subarrays: sequence of subarrays
    :type subarrays: list of DeviceProxy
    :param subarray_id: id of the subarrays to check
    :type subarray_id: int
    """
    assert subarrays[subarray_id - 1].state() in (DevState.ON, DevState.ALARM)


@then(parsers.parse("subarray {subarray_id:d} should be off"))
def subarray_n_should_be_off(subarrays, subarray_id):
    """
    Asserts that the nth subarray device is off

    :param subarrays: sequence of subarrays
    :type subarrays: list of DeviceProxy
    :param subarray_id: id of the subarrays to check
    :type subarray_id: int
    """
    assert subarrays[subarray_id - 1].state() == DevState.OFF


# @scenario(
#     "master_subarray_interactions.feature", "Master allocates stations to subarrays"
# )
# def test_subarray_allocation():
#     pass


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
