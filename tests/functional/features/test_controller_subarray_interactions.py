"""
This module contains the pytest-bdd implementation of the Gherkin BDD
tests for the SKA Low MCCS prototype
"""

import pytest
import json
from pytest_bdd import scenario, given, when, then, parsers
from tango import DevState

devices_to_load = {
    "path": "charts/mccs/data/configuration.json",
    "package": "ska.low.mccs",
    "devices": [
        "controller",
        "subarray_01",
        "subarray_02",
        "station_001",
        "station_002",
        "tile_0001",
        "tile_0002",
        "tile_0003",
        "tile_0004",
        "antenna_000001",
        "antenna_000002",
        "antenna_000003",
        "antenna_000004",
    ],
}


@pytest.fixture()
def devices(tango_context):
    """
    Fixture that provides access to devices via their names.

    :todo: For now the purpose of this fixture is to isolate FQDNs in a
        single place in this module. In future this will be changed to
        extract the device FQDNs straight from the configuration file.

    :param tango_context: fixture that provides a tango context of some
        sort
    :type tango_context: a tango context of some sort; possibly a
        MultiDeviceTestContext, possibly the real thing. The only
        requirement is that it provide a "get_device(fqdn)" method that
        returns a DeviceProxy.

    :return: a dictionary of devices keyed by their name
    :rtype: dict<string, DeviceProxy>
    """
    return {
        "controller": tango_context.get_device("low-mccs/control/control"),
        "subarray_01": tango_context.get_device("low-mccs/subarray/01"),
        "subarray_02": tango_context.get_device("low-mccs/subarray/02"),
        "station_001": tango_context.get_device("low-mccs/station/001"),
        "station_002": tango_context.get_device("low-mccs/station/002"),
        "tile_0001": tango_context.get_device("low-mccs/tile/0001"),
        "tile_0002": tango_context.get_device("low-mccs/tile/0002"),
        "tile_0003": tango_context.get_device("low-mccs/tile/0003"),
        "tile_0004": tango_context.get_device("low-mccs/tile/0004"),
    }


@given(parsers.parse("we have {device_name}"))
def we_have_device(devices, device_name):
    """
    Asserts that existence/availability of a device

    :param devices: fixture that provides access to devices by their name
    :type devices: dict<string, DeviceProxy>
    :param device_name: name of the device
    :type device_name: str
    """
    assert device_name in devices


@scenario("controller_subarray_interactions.feature", "Controller is turned on")
def test_controller_is_turned_on():
    """
    This is run at the end of the scenario. It does nothing at present.
    """
    pass


@given(parsers.parse("{device_name} is {device_state}"))
def device_is_offon(devices, device_name, device_state):
    """
    Asserts that a device is off/on

    :param devices: fixture that provides access to devices by their name
    :type devices: dict<string, DeviceProxy>
    :param device_name: name of the device
    :type device_name: str
    :param device_state: asserted state of the device -- either "off" or
        "on"
    :type device_state: str
    """
    state_map = {"off": [DevState.OFF], "on": [DevState.ON, DevState.ALARM]}
    assert devices[device_name].state() in state_map[device_state]


@when(parsers.parse("we turn {device_name} {device_state}"))
def we_turn_device_onoff(devices, device_name, device_state):
    """
    Turn a device off/on

    :param devices: fixture that provides access to devices by their name
    :type devices: dict<string, DeviceProxy>
    :param device_name: name of the device
    :type device_name: str
    :param device_state: target state of the device -- either "off" or
        "on"
    :type device_state: str
    """
    {"off": lambda device: device.Off(), "on": lambda device: device.On()}[
        device_state
    ](devices[device_name])


@then(parsers.parse("{device_name} should be {device_state}"))
def device_should_be_onoff(devices, device_name, device_state):
    """
    Asserts that the controller device is on

    :param devices: fixture that provides access to devices by their name
    :type devices: dict<string, DeviceProxy>
    :param device_name: name of the device
    :type device_name: str
    :param device_state: asserted state of the device -- either "off" or
        "on"
    :type device_state: str
    """
    state_map = {"off": [DevState.OFF], "on": [DevState.ON, DevState.ALARM]}
    assert devices[device_name].state() in state_map[device_state]


@scenario("controller_subarray_interactions.feature", "Controller enables subarray")
def test_controller_enables_subarray():
    """
    This is run at the end of the scenario. It does nothing at present.
    """
    pass


@when(parsers.parse("we tell controller to allocate subarray {subarray_id:d}"))
def controller_enables_subarray(devices, subarray_id):
    """
    Tells controller to allocate the nth subarray

    :param devices: fixture that provides access to devices by their name
    :type devices: dict<string, DeviceProxy>
    :param subarray_id: controller's id number for the subarray to be enabled
    :type subarray_id: int
    """
    parameters = {"subarray_id": subarray_id, "station_ids": [1, 2]}
    json_str = json.dumps(parameters)
    devices["controller"].Allocate(json_str)


# @scenario(
#     "controller_subarray_interactions.feature",
#     "Controller allocates stations to subarrays"
# )
# def test_subarray_allocation():
#     pass


# @when(
#     parsers.parse(
#         "we tell controller to allocate station {station_id:d} to subarray "
#         "{subarray_id:d}"
#     )
# )
# def controller_allocates_station_to_subarray(controller, subarray_id, station_id):
#     call_with_json(
#         controller.Allocate,
#         subarray_id=subarray_id,
#         stations=[f"low-mccs/station/{station_id:03}"],
#     )


# @then(
#     parsers.parse(
#         "the stations that subarray {subarray_id:d} thinks are allocated to it "
#         "should include station {station_id:d}"
#     )
# )
# def subarray_allocation_includes_station(subarrays, subarray_id, station_id):
#     assert f"low-mccs/station/{station_id:03}" in subarrays[subarray_id].stationFQDNs


# @then(
#     parsers.parse(
#         "the subarray id of station {station_id:d} should be subarray {subarray_id:d}"
#     )
# )
# def subarray_id_of_station_is(stations, station_id, subarray_id):
#     assert stations[station_id].subarrayId == subarray_id
