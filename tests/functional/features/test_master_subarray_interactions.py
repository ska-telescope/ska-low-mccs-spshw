from pytest_bdd import scenario, given, when, then, parsers
from tango import DevState

from ska.low.mccs import (
    MccsMaster,
    MccsSubarray,
    MccsStation,
    MccsStationBeam,
    MccsTile,
)

# from ska.low.mccs.utils import call_with_json


_NUM_SUBARRAYS = 2
_NUM_STATIONS = 2
_NUM_BEAMS = 1
_NUM_TILES = 6


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
                    "TileFQDNs": [f"low/elt/tile_{id}" for id in range(1, 4)]
                },
            },
            {
                "name": "low/elt/station_2",
                "properties": {
                    "TileFQDNs": [f"low/elt/tile_{id}" for id in range(4, 7)]
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
            {"name": f"low/elt/tile_{id}", "properties": {"TileId": id}}
            for id in range(1, _NUM_TILES + 1)
        ],
    },
]


@scenario(
    "master_subarray_interactions.feature", "Master enables and disables subarrays"
)
def test_subarray_enabling_and_disabling():
    pass


@given("we have master")
def master(tango_context):
    return tango_context.get_device("low/elt/master")


@given(parsers.parse("we have {subarray_count:d} subarrays"))
def subarrays(subarray_count, tango_context):
    return {
        i: tango_context.get_device(f"low/elt/subarray_{i}")
        for i in range(1, subarray_count + 1)
    }


@when("we turn master on")
def turn_master_on(master):
    master.On()


@when(parsers.parse("we tell master to enable subarray {subarray_id:d}"))
def master_enables_subarray(master, subarray_id):
    master.EnableSubarray(subarray_id)


@when(parsers.parse("we tell master to disable subarray {subarray_id:d}"))
def master_disables_subarray(master, subarray_id):
    master.DisableSubarray(subarray_id)


@then(parsers.parse("subarray {subarray_id:d} should be on"))
def subarray_is_on(subarrays, subarray_id):
    assert subarrays[subarray_id].state() == DevState.ON


@then(parsers.parse("subarray {subarray_id:d} should be off"))
def subarray_is_off(subarrays, subarray_id):
    assert subarrays[subarray_id].state() == DevState.OFF


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
