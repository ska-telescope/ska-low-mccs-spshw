# type: ignore
"""This module contains the BDD tests for TMC-MCCS interactions."""
import json
import time

import pytest
from pytest_bdd import scenario, given, when, then, parsers
from tango import DevState

from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import AdminMode, ObsState, HealthState

from ska_low_mccs import MccsDeviceProxy

from testing.harness.tango_harness import TangoHarness
from testing.harness import HelperClass


@pytest.fixture(scope="module")
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
        "package": "ska_low_mccs",
        "devices": [
            {"name": "controller", "proxy": MccsDeviceProxy},
            {"name": "subarray_01", "proxy": MccsDeviceProxy},
            {"name": "subarray_02", "proxy": MccsDeviceProxy},
            {"name": "station_001", "proxy": MccsDeviceProxy},
            {"name": "station_002", "proxy": MccsDeviceProxy},
            {"name": "subrack_01", "proxy": MccsDeviceProxy},
            {"name": "tile_0001", "proxy": MccsDeviceProxy},
            {"name": "tile_0002", "proxy": MccsDeviceProxy},
            {"name": "tile_0003", "proxy": MccsDeviceProxy},
            {"name": "tile_0004", "proxy": MccsDeviceProxy},
            {"name": "subarraybeam_01", "proxy": MccsDeviceProxy},
            {"name": "subarraybeam_02", "proxy": MccsDeviceProxy},
            {"name": "subarraybeam_03", "proxy": MccsDeviceProxy},
            {"name": "subarraybeam_04", "proxy": MccsDeviceProxy},
        ],
    }


@pytest.fixture()
def controller(tango_harness: TangoHarness):
    """
    Return the controller device.

    :param tango_harness: a test harness for tango devices

    :return: the controller device
    :rtype: :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`
    """
    return tango_harness.get_device("low-mccs/control/control")


@pytest.fixture()
def subarrays(tango_harness: TangoHarness):
    """
    Return a dictionary of subarrays keyed by their number.

    :param tango_harness: a test harness for tango devices

    :return: subarrays by number
    :rtype: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    """
    return {
        1: tango_harness.get_device("low-mccs/subarray/01"),
        2: tango_harness.get_device("low-mccs/subarray/02"),
    }


@pytest.fixture()
def stations(tango_harness: TangoHarness):
    """
    Return a dictionary of stations keyed by their number.

    :param tango_harness: a test harness for tango devices

    :return: stations by number
    :rtype: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    """
    return {
        1: tango_harness.get_device("low-mccs/station/001"),
        2: tango_harness.get_device("low-mccs/station/002"),
    }


@pytest.fixture()
def subracks(tango_harness: TangoHarness):
    """
    Return a dictionary of subracks keyed by their number.

    :param tango_harness: a test harness for tango devices

    :return: subracks by number
    :rtype: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    """
    return {1: tango_harness.get_device("low-mccs/subrack/01")}


@pytest.fixture()
def tiles(tango_harness: TangoHarness):
    """
    Return a dictionary of tiles keyed by their number.

    :param tango_harness: a test harness for tango devices

    :return: tiles by number
    :rtype: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    """
    return {
        1: tango_harness.get_device("low-mccs/tile/0001"),
        2: tango_harness.get_device("low-mccs/tile/0002"),
        3: tango_harness.get_device("low-mccs/tile/0003"),
        4: tango_harness.get_device("low-mccs/tile/0004"),
    }


@pytest.fixture()
def apius(tango_harness: TangoHarness):
    """
    Return a dictionary of APIUs keyed by their number.

    :param tango_harness: a test harness for tango devices

    :return: APIUs by number
    :rtype: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    """
    return {
        # workaround for https://github.com/tango-controls/cppTango/issues/816
        # 1: tango_harness.get_device("low-mccs/apiu/001"),
    }


@pytest.fixture()
def antennas(tango_harness: TangoHarness):
    """
    Return a dictionary of antennas keyed by their number.

    :param tango_harness: a test harness for tango devices

    :return: antennas by number
    :rtype: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    """
    return {
        # workaround for https://github.com/tango-controls/cppTango/issues/816
        # 1: tango_harness.get_device("low-mccs/antenna/000001"),
        # 2: tango_harness.get_device("low-mccs/antenna/000002"),
        # 3: tango_harness.get_device("low-mccs/antenna/000003"),
        # 4: tango_harness.get_device("low-mccs/antenna/000004"),
    }


@pytest.fixture()
def subarraybeams(tango_harness: TangoHarness):
    """
    Return a dictionary of subarray beams keyed by their number.

    :param tango_harness: a test harness for tango devices

    :return: subarray beams by number
    :rtype: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    """
    return {
        1: tango_harness.get_device("low-mccs/subarraybeam/01"),
        2: tango_harness.get_device("low-mccs/subarraybeam/02"),
        # 3: tango_harness.get_device("low-mccs/subarraybeam/03"),
        # 4: tango_harness.get_device("low-mccs/subarraybeam/04"),
    }


def assert_command(device, command, argin=None, expected_result=ResultCode.OK):
    """
    Method to simplify assertions on the result of TMC calls.

    :param device: The MCCS device to send command to
    :type device: :py:class:`tango.DeviceProxy`
    :param command: The command to send to the device
    :type command: str
    :param argin: Optional argument to send to the command
    :type argin: str
    :param expected_result: The expected return code from the command
    :type expected_result: :py:class:`~ska_tango_base.commands.ResultCode`
    """
    # Call the specified command synchronously
    if argin:
        result = device.command_inout(command, argin)
    else:
        result = device.command_inout(command)
    if expected_result is None:
        assert result is None
    else:
        ((result_code,), _) = result
        assert result_code == expected_result


@scenario(
    "features/controller_subarray_interactions.feature", "MCCS Start up low telescope"
)
def test_start_up_low_telescope(controller, subarrays, stations, command_helper):
    """
    This is run at the end of the scenario. Turn MCCS Controller Off.

    :param controller: a proxy to the controller device
    :type controller: :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`
    :param subarrays: proxies to the subarray devices, keyed by number
    :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param stations: proxies to the station devices, keyed by number
    :type stations: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param command_helper: A command helper fixture
    :type command_helper: CommandHelper
    """
    assert_command(device=controller, command="Off", expected_result=ResultCode.QUEUED)
    command_helper.check_device_state(controller, DevState.OFF)
    check_reset_state(controller, subarrays, stations)


@given(parsers.parse("we have mvplow running an instance of {component_name}"))
def we_have_mvplow_running_an_instance_of(
    component_name,
    controller,
    subarrays,
    stations,
    subracks,
    tiles,
    apius,
    antennas,
    subarraybeams,
):
    """
    Asserts the existence/availability of a component.

    :param component_name: name of the component
    :type component_name: str
    :param controller: a proxy to the controller device
    :type controller: :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`
    :param subarrays: proxies to the subarray devices, keyed by number
    :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param stations: proxies to the station devices, keyed by number
    :type stations: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param subracks: proxies to the subrack devices, keyed by number
    :type subracks: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param tiles: proxies to the tile devices, keyed by number
    :type tiles: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param apius: proxies to the apiu devices, keyed by number
    :type apius: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param antennas: proxies to the antenna devices, keyed by number
    :type antennas: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param subarraybeams: proxies to the subarray beam devices, keyed by number
    :type subarraybeams: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    """
    assert component_name in ["mccs", "tmc"]
    # nothing more to do here, because we have already checked that our
    # subsystem is ready to go, simply by instantiating the fixtures.


@given(parsers.parse("{component_name} is ready to {direction} a startup command"))
def component_is_ready_to_receive_a_startup_command(
    controller, component_name, direction
):
    """
    Asserts that a component is ready to receive an on command.

    :param controller: a proxy to the controller device
    :type controller: :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`
    :param component_name: name of the component
    :type component_name: str
    :param direction: direction of communication
    :type direction: str
    """
    if component_name == "mccs":
        allowed_states = [DevState.DISABLE, DevState.OFF, DevState.ON]
        assert controller.state() in allowed_states
    elif component_name == "tmc":
        pass
    else:
        assert False


@when(parsers.parse("tmc tells mccs controller to start up"))
def tmc_tells_mccs_controller_to_start_up(controller):
    """
    Start up the MCCS subsystem.

    :param controller: a proxy to the controller device
    :type controller: :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`
    """
    assert_command(
        device=controller, command="Startup", expected_result=ResultCode.QUEUED
    )

    # TODO: Workaround for bug MCCS-409
    #
    # The stations have just turned on, and have published change
    # events on their healthState. But events move through the event
    # subsystem asynchronously, so the controller might not have
    # received these events yet. Until it receives those change events,
    # and updates its record of station health, it will refuse to
    # allocate those stations to a subarray.
    #
    # For now, let's sleep for a second, to allow time for the events to
    # arrive. In future we need a better solution to this.
    time.sleep(1.0)


@then(parsers.parse("mccs controller state is {device_state}"))
def check_mccs_controller_state(controller, device_state):
    """
    Asserts that mccs controller is on/off.

    :param controller: a proxy to the controller device
    :type controller: :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`
    :param device_state: asserted state of the device -- either "off" or
        "on"
    :type device_state: str
    """
    check_mccs_device_state(controller, device_state)


def check_mccs_device_state(device, device_state):
    """
    Asserts that the mccs device is on/off.

    :param device: a proxy to the device
    :type device: :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`
    :param device_state: asserted state of the device -- either "off" or
        "on"
    :type device_state: str
    """
    state_map = {
        "off": [DevState.OFF],
        "on": [DevState.ON, DevState.ALARM],
    }
    count = 0.0
    while not device.State() in state_map[device_state] and count < 3.0:
        count += 0.1
        time.sleep(0.1)
    assert device.State() in state_map[device_state]


@then(parsers.parse("all mccs station states are {state}"))
def all_mccs_station_states_are_onoff(stations, device_state):
    """
    Asserts that online or maintenance mccs station devices are on/off.

    :param stations: proxies to the station devices, keyed by number
    :type stations: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param device_state: asserted state of the device -- either "off" or
        "on"
    :type device_state: str
    """
    state_map = {"off": [DevState.OFF], "on": [DevState.ON, DevState.ALARM]}
    for i in stations:
        if stations[i].AdminMode in [AdminMode.ONLINE, AdminMode.MAINTENANCE]:
            assert stations[i].state() in state_map[device_state]


def check_reset_state(controller, subarrays, stations):
    """
    Check that the MCCS devices are in a known reset state.

    :param controller: a proxy to the controller device
    :type controller: :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`
    :param subarrays: proxies to the subarray devices, keyed by number
    :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param stations: proxies to the station devices, keyed by number
    :type stations: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    """
    check_mccs_device_state(controller, "off")
    assert controller.aPoolStats == "0 0 "
    check_mccs_device_state(subarrays[1], "off")
    check_mccs_device_state(subarrays[2], "off")
    assert subarrays[1].stationFQDNs is None or subarrays[1].stationFQDNs == ()
    assert subarrays[2].stationFQDNs is None or subarrays[2].stationFQDNs == ()
    check_mccs_device_state(stations[1], "off")
    check_mccs_device_state(stations[2], "off")
    assert stations[1].subarrayId == 0
    assert stations[2].subarrayId == 0


@scenario("features/controller_subarray_interactions.feature", "MCCS Allocate subarray")
def test_allocate_subarray(controller, subarrays, stations, command_helper):
    """
    This is run at the end of the scenario. Turn MCCS Controller Off.

    :param controller: a proxy to the controller device
    :type controller: :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`
    :param subarrays: proxies to the subarray devices, keyed by number
    :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param stations: proxies to the station devices, keyed by number
    :type stations: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param command_helper: A command helper fixture
    :type command_helper: CommandHelper
    """
    release_config = {"subarray_id": 1, "release_all": True}
    json_string = json.dumps(release_config)
    assert_command(device=controller, command="Release", argin=json_string)
    assert_command(device=controller, command="Off", expected_result=ResultCode.QUEUED)
    command_helper.check_device_state(controller, DevState.OFF)
    check_reset_state(controller, subarrays, stations)


@given(parsers.parse("{component_name} is ready to {action} a subarray"))
def component_is_ready_to_action_a_subarray(
    component_name, action, controller, subarrays, stations
):
    """
    Asserts that a component is ready to perform an action on a subarray.

    :param component_name: name of the component
    :type component_name: str
    :param action: action to perform on a subarray
    :type action: str
    :param controller: a proxy to the controller device
    :type controller: :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`
    :param subarrays: proxies to the subarray devices, keyed by number
    :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param stations: proxies to the station devices, keyed by number
    :type stations: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    """
    if component_name == "mccs":
        tmc_tells_mccs_controller_to_start_up(controller)
        check_mccs_device_state(controller, "on")
        check_mccs_device_state(subarrays[1], "off")
        check_mccs_device_state(subarrays[2], "off")
        assert stations[1].subarrayId == 0
        assert stations[2].subarrayId == 0
    elif component_name == "tmc":
        pass
    else:
        assert False


@given(parsers.parse("subarray obsstate is idle or empty"))
def subarray_obsstate_is_idle_or_empty(subarrays, cached_obsstate):
    """
    The obsstate of each subarray should be idle or empty.

    :param subarrays: proxies to the subarray devices, keyed by number
    :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param cached_obsstate: pytest message box for the cached obsstate
    :type cached_obsstate:
        dict<string, :py:class:`~ska_tango_base.control_model.ObsState`>
    """
    for i in subarrays:
        obsstate = subarrays[i].obsstate
        assert (obsstate == ObsState.IDLE) or (obsstate == ObsState.EMPTY)
        cached_obsstate[i] = obsstate


@when(parsers.parse("tmc allocates a subarray with {validity} parameters"))
def tmc_allocates_a_subarray_with_validity_parameters(controller, subarrays, validity):
    """
    TMC allocates a subarray.

    :param controller: a proxy to the controller device
    :type controller: :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`
    :param subarrays: proxies to the subarray devices, keyed by number
    :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param validity: whether the allocate has valid|invalid parameters
    :type validity: str
    """
    parameters = {
        "subarray_id": 1,
        "station_ids": [[1, 2]],
        "channel_blocks": [2],
        "subarray_beam_ids": [1],
    }

    if validity == "invalid":
        parameters["subarray_id"] = 3
        json_string = json.dumps(parameters)
        assert_command(
            device=controller,
            command="Allocate",
            argin=json_string,
            expected_result=ResultCode.FAILED,
        )
        return

    json_string = json.dumps(parameters)
    [result], [message, uid] = controller.command_inout("Allocate", json_string)
    assert result == ResultCode.QUEUED
    assert ":Allocate" in uid
    assert message

    # Check that the allocate command has completed
    helper = HelperClass()
    helper.wait_for_command_to_complete(controller)

    command_result = controller.commandResult
    kwargs = json.loads(command_result)
    message_uid = kwargs.get("message_uid")
    assert message_uid == uid

    # We need to wait until the subarray is in IDLE state
    assert subarrays[1].obsstate == ObsState.IDLE


@then(parsers.parse("the stations have the correct subarray id"))
def the_stations_have_the_correct_subarray_id(stations):
    """
    Stations have the correct subarray id.

    :param stations: proxies to the station devices, keyed by number
    :type stations: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    """
    # We need to wait until the subarray is in IDLE state
    for station_id in [1, 2]:
        timeout = 0.0
        while not stations[station_id].subarrayId == 1 and timeout < 5.0:
            timeout += 0.1
            time.sleep(0.1)
        assert stations[station_id].subarrayId == 1
        assert timeout < 5.0


@then(parsers.parse("subarray state is on"))
def subarray_state_is_on(subarrays):
    """
    The subarray should be on.

    :param subarrays: proxies to the subarray devices, keyed by number
    :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    """
    assert subarrays[1].State() == DevState.ON


@then(
    parsers.parse("according to allocation policy health of allocated subarray is good")
)
def according_to_allocation_policy_health_of_allocated_subarray_is_good(
    controller, subarrays, stations
):
    """
    Health is good.

    :param controller: a proxy to the controller device
    :type controller: :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`
    :param subarrays: proxies to the subarray devices, keyed by number
    :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param stations: proxies to the station devices, keyed by number
    :type stations: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    """
    assert controller.healthState == HealthState.OK
    assert subarrays[1].healthState == HealthState.OK
    assert subarrays[2].healthState == HealthState.OK
    assert stations[1].healthState == HealthState.OK
    assert stations[2].healthState == HealthState.OK


@then(parsers.parse("other resources are not affected"))
def other_resources_are_not_affected(subarrays):
    """
    Other resource should not be affected.

    :param subarrays: proxies to the subarray devices, keyed by number
    :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    """
    check_mccs_device_state(subarrays[2], "off")
    assert subarrays[2].obsState == ObsState.EMPTY


@then(parsers.parse("subarray obsstate is not changed"))
def subarray_obsstate_is_not_changed(subarrays, cached_obsstate):
    """
    Check that the subarray obsState has not changed.

    :param subarrays: proxies to the subarray devices, keyed by number
    :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param cached_obsstate: pytest message box for the cached obsstate
    :type cached_obsstate:
        dict<string, :py:class:`~ska_tango_base.control_model.ObsState`>
    """
    assert subarrays[1].obsstate == cached_obsstate[1]
    assert subarrays[2].obsstate == cached_obsstate[2]


@scenario(
    "features/controller_subarray_interactions.feature", "MCCS Configure a subarray"
)
def test_configure_a_subarray(controller, subarrays, stations, command_helper):
    """
    This is run at the end of the scenario. Turn MCCS Controller Off.

    :param controller: a proxy to the controller device
    :type controller: :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`
    :param subarrays: proxies to the subarray devices, keyed by number
    :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param stations: proxies to the station devices, keyed by number
    :type stations: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param command_helper: A command helper fixture
    :type command_helper: CommandHelper
    """
    assert_command(device=subarrays[1], command="End")
    release_config = {"subarray_id": 1, "release_all": True}
    json_string = json.dumps(release_config)
    assert_command(device=controller, command="Release", argin=json_string)
    assert_command(device=controller, command="Off", expected_result=ResultCode.QUEUED)
    command_helper.check_device_state(controller, DevState.OFF)
    check_reset_state(controller, subarrays, stations)


@given(parsers.parse("we have a successfully {desired_state} subarray"))
def we_have_a_successfully_configured_and_or_allocated_subarray(
    controller,
    subarrays,
    stations,
    subracks,
    tiles,
    apius,
    antennas,
    subarraybeams,
    desired_state,
    cached_obsstate,
):
    """
    Get the subarray into an configured and/or allocated state.

    :param controller: a proxy to the controller device
    :type controller: :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`
    :param subarrays: proxies to the subarray devices, keyed by number
    :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param stations: proxies to the station devices, keyed by number
    :type stations: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param subracks: proxies to the subrack devices, keyed by number
    :type subracks: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param tiles: proxies to the tile devices, keyed by number
    :type tiles: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param apius: proxies to the apiu devices, keyed by number
    :type apius: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param antennas: proxies to the antenna devices, keyed by number
    :type antennas: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param subarraybeams: proxies to the subarray beam devices, keyed by number
    :type subarraybeams: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param desired_state: The desired state to be in
    :type desired_state: str
    :param cached_obsstate: pytest message box for the cached obsstate
    :type cached_obsstate:
        dict<string, :py:class:`~ska_tango_base.control_model.ObsState`>
    """
    we_have_mvplow_running_an_instance_of(
        "mccs",
        controller,
        subarrays,
        stations,
        subracks,
        tiles,
        apius,
        antennas,
        subarraybeams,
    )
    component_is_ready_to_action_a_subarray(
        "mccs", "allocate", controller, subarrays, stations
    )
    subarray_obsstate_is_idle_or_empty(subarrays, cached_obsstate)
    tmc_allocates_a_subarray_with_validity_parameters(controller, subarrays, "valid")

    if desired_state == "configured" or desired_state == "scanning":
        configure_subarray(subarrays)
        the_subarray_obsstate_is(subarrays, "ready")
    if desired_state == "scanning":
        tmc_starts_a_scan_on_subarray(subarrays)
        the_subarray_obsstate_is(subarrays, "scanning")
    if desired_state == "allocated":
        the_subarray_obsstate_is(subarrays, "idle")


def configure_subarray(subarrays):
    """
    Configure the subarray.

    :param subarrays: proxies to the subarray devices, keyed by number
    :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    """
    # Configure the subarray
    configuration = {
        "stations": [{"station_id": 1}, {"station_id": 2}],
        "subarray_beams": [
            {
                "subarray_beam_id": 1,
                "station_ids": [1, 2],
                "channels": [[0, 8, 1, 1], [8, 8, 2, 1]],
                "update_rate": 0.0,
                "sky_coordinates": [0.0, 180.0, 0.0, 45.0, 0.0],
                "antenna_weights": [1.0, 1.0, 1.0],
                "phase_centre": [0.0, 0.0],
            }
        ],
    }
    json_string = json.dumps(configuration)
    assert_command(device=subarrays[1], command="Configure", argin=json_string)


@when(parsers.parse("tmc starts a scan on subarray"))
def tmc_starts_a_scan_on_subarray(subarrays):
    """
    TMC starts a scan on the subarray.

    :param subarrays: proxies to the subarray devices, keyed by number
    :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    """
    scan_config = {"id": 1, "scan_time": 4}
    json_string = json.dumps(scan_config)
    assert_command(
        device=subarrays[1],
        command="Scan",
        argin=json_string,
        expected_result=ResultCode.STARTED,
    )


@when(parsers.parse("tmc configures the subarray"))
def tmc_configures_the_subarray(subarrays):
    """
    TMC configures a subarray.

    :param subarrays: proxies to the subarray devices, keyed by number
    :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    """
    configure_subarray(subarrays)
    the_subarray_obsstate_is(subarrays, "ready")


@then(parsers.parse("the subarray obsstate is {obsstate}"))
def the_subarray_obsstate_is(subarrays, obsstate):
    """
    The subarray obsstate is {obsstate}

    :param subarrays: proxies to the subarray devices, keyed by number
    :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param obsstate: The observation state
    :type obsstate: str
    """
    assert subarrays[1].obsState.name == obsstate.upper()


@then(parsers.parse("subarray health is good"))
def subarray_health_is_good(subarrays):
    """
    The health of the subarray is good.

    :param subarrays: proxies to the subarray devices, keyed by number
    :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    """
    assert subarrays[1].healthState == HealthState.OK


@scenario(
    "features/controller_subarray_interactions.feature",
    "MCCS Perform a scan on subarray",
)
def test_perform_a_scan_on_subarray(controller, subarrays, stations, command_helper):
    """
    This is run at the end of the scenario. Turn MCCS Controller Off.

    :param controller: a proxy to the controller device
    :type controller: :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`
    :param subarrays: proxies to the subarray devices, keyed by number
    :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param stations: proxies to the station devices, keyed by number
    :type stations: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param command_helper: A command helper fixture
    :type command_helper: CommandHelper
    """
    assert_command(device=subarrays[1], command="EndScan")
    assert_command(device=subarrays[1], command="End")
    release_config = {"subarray_id": 1, "release_all": True}
    json_string = json.dumps(release_config)
    assert_command(device=controller, command="Release", argin=json_string)
    assert_command(device=controller, command="Off", expected_result=ResultCode.QUEUED)
    command_helper.check_device_state(controller, DevState.OFF)
    check_reset_state(controller, subarrays, stations)


def abort_post_operations(controller, subarrays, stations, command_helper):
    """
    Collection of operations to perform after an abort command.

    :param controller: a proxy to the controller device
    :type controller: :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`
    :param subarrays: proxies to the subarray devices, keyed by number
    :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param stations: proxies to the station devices, keyed by number
    :type stations: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param command_helper: A command helper fixture
    :type command_helper: CommandHelper
    """
    assert_command(device=subarrays[1], command="ObsReset")
    release_config = {"subarray_id": 1, "release_all": True}
    json_string = json.dumps(release_config)
    assert_command(device=controller, command="Release", argin=json_string)
    assert_command(device=controller, command="Off", expected_result=ResultCode.QUEUED)
    command_helper.check_device_state(controller, DevState.OFF)
    check_reset_state(controller, subarrays, stations)


@scenario(
    "features/controller_subarray_interactions.feature",
    "MCCS Perform an abort on a scanning subarray",
)
def test_perform_an_abort_on_a_scanning_subarray(
    controller, subarrays, stations, command_helper
):
    """
    This is run at the end of the scenario. Turn MCCS Controller Off.

    :param controller: a proxy to the controller device
    :type controller: :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`
    :param subarrays: proxies to the subarray devices, keyed by number
    :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param stations: proxies to the station devices, keyed by number
    :type stations: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param command_helper: A command helper fixture
    :type command_helper: CommandHelper
    """
    abort_post_operations(controller, subarrays, stations, command_helper)


@scenario(
    "features/controller_subarray_interactions.feature",
    "MCCS Perform an abort on an idle subarray",
)
def test_perform_an_abort_on_an_idle_subarray(
    controller, subarrays, stations, command_helper
):
    """
    This is run at the end of the scenario. Turn MCCS Controller Off.

    :param controller: a proxy to the controller device
    :type controller: :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`
    :param subarrays: proxies to the subarray devices, keyed by number
    :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param stations: proxies to the station devices, keyed by number
    :type stations: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param command_helper: A command helper fixture
    :type command_helper: CommandHelper
    """
    abort_post_operations(controller, subarrays, stations, command_helper)


@scenario(
    "features/controller_subarray_interactions.feature",
    "MCCS Perform an abort on a configured subarray",
)
def test_perform_an_abort_on_a_configured_subarray(
    controller, subarrays, stations, command_helper
):
    """
    This is run at the end of the scenario. Turn MCCS Controller Off.

    :param controller: a proxy to the controller device
    :type controller: :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`
    :param subarrays: proxies to the subarray devices, keyed by number
    :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param stations: proxies to the station devices, keyed by number
    :type stations: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    :param command_helper: A command helper fixture
    :type command_helper: CommandHelper
    """
    abort_post_operations(controller, subarrays, stations, command_helper)


@when(parsers.parse("tmc issues an abort on subarray"))
def tmc_issues_an_abort_on_subarray(subarrays):
    """
    TMC issues an abort on the subarray.

    :param subarrays: proxies to the subarray devices, keyed by number
    :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
    """
    assert_command(device=subarrays[1], command="Abort")
