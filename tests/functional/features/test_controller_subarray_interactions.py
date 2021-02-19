"""
This module contains the pytest-bdd implementation of the Gherkin BDD
tests for TMC and MCCS interactions.
"""
import backoff
import json

import pytest
from pytest_bdd import scenario, given, when, then, parsers
from tango import DevState, DevSource

from ska.base.commands import ResultCode
from ska.base.control_model import AdminMode, ObsState, HealthState


# TODO: This has been temporarily moved from the conftest.py file
# because of a weird pytest bug -- pytest tries to import it from a
# different conftest.py, and throws an ImportError.
# Besides, it's commonly considered bad practice to input from conftest
# anyhow:
# https://github.com/pytest-dev/pytest/issues/3272#issuecomment-369252005
# This will be fixed when we get around to doing MCCS-329.
@backoff.on_predicate(backoff.expo, factor=0.1, max_time=180)
def confirm_initialised(devices):
    """
    Helper function that tries to confirm that a device has completed
    its initialisation and transitioned out of INIT state, using an
    exponential backoff-retry scheme in case of failure.

    :param devices: the devices that we are waiting to initialise
    :type devices: :py:class:`tango.DeviceProxy`

    :returns: whether the devices are all initialised or not
    :rtype: bool
    """
    return all(
        device.state() not in [DevState.UNKNOWN, DevState.INIT] for device in devices
    )


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
            "subarraybeam_01",
            "subarraybeam_02",
            "subarraybeam_03",
            "subarraybeam_04",
        ],
    }


@pytest.fixture(scope="module")
def cached_obsstate():
    """
    Use a pytest message box to retain obsstate between test stages.

    :return: cached_obsstate: pytest message box for the cached obsstate
    :rtype: cached_obsstate: dict<string, :py:class:`ska.base.control_model.ObsState`>
    """
    return {}


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
    :rtype: dict<string, :py:class:`tango.DeviceProxy`>
    """
    device_dict = {
        "controller": tango_context.get_device("low-mccs/control/control"),
        "subarray_01": tango_context.get_device("low-mccs/subarray/01"),
        "subarray_02": tango_context.get_device("low-mccs/subarray/02"),
        "station_001": tango_context.get_device("low-mccs/station/001"),
        "station_002": tango_context.get_device("low-mccs/station/002"),
        "subrack_01": tango_context.get_device("low-mccs/subrack/01"),
        "tile_0001": tango_context.get_device("low-mccs/tile/0001"),
        "tile_0002": tango_context.get_device("low-mccs/tile/0002"),
        "tile_0003": tango_context.get_device("low-mccs/tile/0003"),
        "tile_0004": tango_context.get_device("low-mccs/tile/0004"),
        # workaround for https://github.com/tango-controls/cppTango/issues/816
        # "apiu_001": tango_context.get_device("low-mccs/apiu/001"),
        # "antenna_000001": tango_context.get_device("low-mccs/antenna/000001"),
        # "antenna_000002": tango_context.get_device("low-mccs/antenna/000002"),
        # "antenna_000003": tango_context.get_device("low-mccs/antenna/000003"),
        # "antenna_000004": tango_context.get_device("low-mccs/antenna/000004"),
        "subarraybeam_01": tango_context.get_device("low-mccs/subarraybeam/01"),
        "subarraybeam_02": tango_context.get_device("low-mccs/subarraybeam/02"),
        "subarraybeam_03": tango_context.get_device("low-mccs/subarraybeam/03"),
        "subarraybeam_04": tango_context.get_device("low-mccs/subarraybeam/04"),
    }

    # Bypass the cache because stationFQDNs etc are polled attributes,
    # and having written to them, we don't want to have to wait a
    # polling period to test that the write has stuck.
    # TODO: Need to investigate disabling this section for tests performed on
    #       a real deployment (i.e. not in a test/development environment)
    for device in device_dict.values():
        # HACK: increasing the timeout until we can make some commands synchronous
        device.set_timeout_millis(5000)

        device.set_source(DevSource.DEV)
    assert confirm_initialised(device_dict.values())
    return device_dict


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
    :type expected_result: :py:class:`ska.base.commands.ResultCode`
    """
    # Call the specified command synchronously
    result = device.command_inout(command, argin)
    if expected_result is None:
        assert result is None
    else:
        ((result_code,), (_,)) = result
        assert result_code == expected_result


@scenario("controller_subarray_interactions.feature", "MCCS Start up low telescope")
def test_start_up_low_telescope(devices):
    """
    This is run at the end of the scenario. Turn MCCS Controller Off.

    :param devices: fixture that provides access to devices by their name
    :type devices: dict<string, :py:class:`tango.DeviceProxy`>
    """
    assert_command(device=devices["controller"], command="Off")
    check_mccs_controller_state(devices, "off")
    check_reset_state(devices)


@given(parsers.parse("we have mvplow running an instance of {component_name}"))
def we_have_mvplow_running_an_instance_of(devices, devices_to_load, component_name):
    """
    Asserts the existence/availability of a component.

    :param devices: fixture that provides access to devices by their name
    :type devices: dict<string, :py:class:`tango.DeviceProxy`>
    :param devices_to_load: fixture that provides a specification of the
        devices that are to be included in the devices_info dictionary
    :type devices_to_load: dictionary
    :param component_name: name of the component
    :type component_name: str
    """

    if component_name == "mccs":
        for device_name in devices_to_load["devices"]:
            assert device_name in devices
    elif component_name == "tmc":
        pass
    else:
        assert False


@given(parsers.parse("{component_name} is ready to {direction} a startup command"))
def component_is_ready_to_receive_a_startup_command(devices, component_name, direction):
    """
    Asserts that a component is ready to receive an on command.

    :param devices: fixture that provides access to devices by their name
    :type devices: dict<string, :py:class:`tango.DeviceProxy`>
    :param component_name: name of the component
    :type component_name: str
    :param direction: direction of communication
    :type direction: str
    """
    if component_name == "mccs":
        assert devices["controller"].state() == DevState.DISABLE
    elif component_name == "tmc":
        pass
    else:
        assert False


@when(parsers.parse("tmc tells mccs controller to start up"))
def tmc_tells_mccs_controller_to_start_up(devices):
    """
    Start up the MCCS subsystem.

    :param devices: fixture that provides access to devices by their name
    :type devices: dict<string, :py:class:`tango.DeviceProxy`>
    """
    assert_command(device=devices["controller"], command="Startup")


@when(parsers.parse("tmc turns mccs controller {device_state}"))
def tmc_turns_mccs_controller_onoff(devices, device_state):
    """
    Turn the mccs controller device off/on.

    :param devices: fixture that provides access to devices by their name
    :type devices: dict<string, :py:class:`tango.DeviceProxy`>
    :param device_state: the state to transition to (on/off)
    :type device_state: str
    """
    {
        "off": lambda device: assert_command(device=device, command="Off"),
        "on": lambda device: assert_command(device=device, command="On"),
    }[device_state](devices["controller"])


@then(parsers.parse("mccs controller state is {device_state}"))
def check_mccs_controller_state(devices, device_state):
    """
    Asserts that the mccs controller device is on/off.

    :param devices: fixture that provides access to devices by their name
    :type devices: dict<string, :py:class:`tango.DeviceProxy`>
    :param device_state: asserted state of the device -- either "off" or
        "on"
    :type device_state: str
    """
    state_map = {"off": [DevState.OFF], "on": [DevState.ON, DevState.ALARM]}
    assert devices["controller"].state() in state_map[device_state]


@then(parsers.parse("all mccs station states are {state}"))
def all_mccs_station_states_are_onoff(devices, device_state):
    """
    Asserts that online or maintenance mccs station devices are on/off.

    :param devices: fixture that provides access to devices by their name
    :type devices: dict<string, :py:class:`tango.DeviceProxy`>
    :param device_state: asserted state of the device -- either "off" or
        "on"
    :type device_state: str
    """
    state_map = {"off": [DevState.OFF], "on": [DevState.ON, DevState.ALARM]}
    for number in range(1, 513):
        station_key = f"station_{number:03}"
        if station_key in devices:
            station = devices[station_key]
            if station.AdminMode in [AdminMode.ONLINE, AdminMode.MAINTENANCE]:
                assert station.state() in state_map[device_state]


def check_reset_state(devices):
    """
    Check that the MCCS devices are in a known reset state.

    :param devices: fixture that provides access to devices by their name
    :type devices: dict<string, :py:class:`tango.DeviceProxy`>
    """
    check_mccs_controller_state(devices, "off")
    assert devices["subarray_01"].State() == DevState.OFF
    assert devices["subarray_02"].State() == DevState.OFF
    assert devices["subarray_01"].stationFQDNs is None
    assert devices["subarray_02"].stationFQDNs is None
    assert devices["station_001"].State() == DevState.OFF
    assert devices["station_002"].State() == DevState.OFF
    assert devices["station_001"].subarrayId == 0
    assert devices["station_002"].subarrayId == 0


@scenario("controller_subarray_interactions.feature", "MCCS Allocate subarray")
def test_allocate_subarray(devices):
    """
    This is run at the end of the scenario. Turn MCCS Controller Off.

    :param devices: fixture that provides access to devices by their name
    :type devices: dict<string, :py:class:`tango.DeviceProxy`>
    """
    release_config = {"subarray_id": 1, "release_all": True}
    json_string = json.dumps(release_config)
    assert_command(device=devices["controller"], command="Release", argin=json_string)
    assert_command(device=devices["controller"], command="Off")
    check_reset_state(devices)


@given(parsers.parse("{component_name} is ready to {action} a subarray"))
def component_is_ready_to_action_a_subarray(devices, component_name, action):
    """
    Asserts that a component is ready to perform an action on a
    subarray.

    :param devices: fixture that provides access to devices by their name
    :type devices: dict<string, :py:class:`tango.DeviceProxy`>
    :param component_name: name of the component
    :type component_name: str
    :param action: action to perform on a subarray
    :type action: str
    """
    if component_name == "mccs":
        tmc_tells_mccs_controller_to_start_up(devices)
        check_mccs_controller_state(devices, "on")
        assert devices["subarray_01"].State() == DevState.OFF
        assert devices["subarray_02"].State() == DevState.OFF
        assert devices["station_001"].subarrayId == 0
        assert devices["station_002"].subarrayId == 0
    elif component_name == "tmc":
        pass
    else:
        assert False


@given(parsers.parse("subarray obsstate is idle or empty"))
def subarray_obsstate_is_idle_or_empty(devices, cached_obsstate):
    """
    The obsstate of each subarray should be idle or empty.

    :param devices: fixture that provides access to devices by their name
    :type devices: dict<string, :py:class:`tango.DeviceProxy`>
    :param cached_obsstate: pytest message box for the cached obsstate
    :type cached_obsstate: dict<string, :py:class:`ska.base.control_model.ObsState`>
    """

    for device in ["subarray_01", "subarray_02"]:
        obsstate = devices[device].obsstate
        assert (obsstate == ObsState.IDLE) or (obsstate == ObsState.EMPTY)
        cached_obsstate["subarry_01"] = devices["subarray_01"].obsstate
        cached_obsstate["subarry_02"] = devices["subarray_02"].obsstate


@when(parsers.parse("tmc allocates a subarray with {validity} parameters"))
def tmc_allocates_a_subarray_with_validity_parameters(devices, validity):
    """
    TMC allocates a subarray.

    :param devices: fixture that provides access to devices by their name
    :type devices: dict<string, :py:class:`tango.DeviceProxy`>
    :param validity: whether the allocate has valid|invalid parameters
    :type validity: str
    """
    parameters = {
        "subarray_id": 1,
        "station_ids": [1, 2],
        "channels": [[0, 8, 1, 1], [8, 8, 2, 1]],
        "subarray_beam_ids": [1],
    }
    expected_result = ResultCode.OK

    if validity == "invalid":
        parameters["subarray_id"] = 3
        expected_result = ResultCode.FAILED

    json_string = json.dumps(parameters)
    assert_command(
        device=devices["controller"],
        command="Allocate",
        argin=json_string,
        expected_result=expected_result,
    )


@then(parsers.parse("the stations have the correct subarray id"))
def the_stations_have_the_correct_subarray_id(devices):
    """
    Stations have the correct subarray id.

    :param devices: fixture that provides access to devices by their name
    :type devices: dict<string, :py:class:`tango.DeviceProxy`>
    """
    assert devices["station_001"].subarrayId == 1
    assert devices["station_002"].subarrayId == 1


@then(parsers.parse("subarray state is on"))
def subarray_state_is_on(devices):
    """
    The subarray should be on.

    :param devices: fixture that provides access to devices by their name
    :type devices: dict<string, :py:class:`tango.DeviceProxy`>
    """
    assert devices["subarray_01"].State() == DevState.ON


@then(
    parsers.parse("according to allocation policy health of allocated subarray is good")
)
def according_to_allocation_policy_health_of_allocated_subarray_is_good(devices):
    """
    Health is good.

    :param devices: fixture that provides access to devices by their name
    :type devices: dict<string, :py:class:`tango.DeviceProxy`>
    """
    assert devices["controller"].healthState == HealthState.OK
    assert devices["station_001"].healthState == HealthState.OK
    assert devices["station_002"].healthState == HealthState.OK
    assert devices["subarray_01"].healthState == HealthState.OK
    assert devices["subarray_02"].healthState == HealthState.OK


@then(parsers.parse("other resources are not affected"))
def other_resources_are_not_affected(devices):
    """
    Other resource should not be affected.

    :param devices: fixture that provides access to devices by their name
    :type devices: dict<string, :py:class:`tango.DeviceProxy`>
    """
    assert devices["subarray_02"].State() == DevState.OFF
    assert devices["subarray_02"].obsState == ObsState.EMPTY


@then(parsers.parse("subarray obsstate is not changed"))
def subarray_obsstate_is_not_changed(devices, cached_obsstate):
    """
    Check that the subarray obsState has not changed.

    :param devices: fixture that provides access to devices by their name
    :type devices: dict<string, :py:class:`tango.DeviceProxy`>
    :param cached_obsstate: pytest message box for the cached obsstate
    :type cached_obsstate: dict<string, :py:class:`ska.base.control_model.ObsState`>
    """
    assert devices["subarray_01"].obsstate == cached_obsstate["subarray_01"]
    assert devices["subarray_02"].obsstate == cached_obsstate["subarray_02"]


@scenario("controller_subarray_interactions.feature", "MCCS Configure a subarray")
def test_configure_a_subarray(devices):
    """
    This is run at the end of the scenario. Turn MCCS Controller Off.

    :param devices: fixture that provides access to devices by their name
    :type devices: dict<string, :py:class:`tango.DeviceProxy`>
    """
    assert_command(device=devices["subarray_01"], command="End")
    release_config = {"subarray_id": 1, "release_all": True}
    json_string = json.dumps(release_config)
    assert_command(device=devices["controller"], command="Release", argin=json_string)
    assert_command(device=devices["controller"], command="Off")
    check_reset_state(devices)


@given(parsers.parse("we have a successfully {desired_state} subarray"))
def we_have_a_successfully_configured_and_or_allocated_subarray(
    devices, devices_to_load, desired_state, cached_obsstate
):
    """
    Get the subarray into an configured and/or allocated state.

    :param devices: fixture that provides access to devices by their name
    :type devices: dict<string, :py:class:`tango.DeviceProxy`>
    :param devices_to_load: fixture that provides a specification of the
        devices that are to be included in the devices_info dictionary
    :type devices_to_load: dictionary
    :param desired_state: The desired state to be in
    :type desired_state: str
    :param cached_obsstate: pytest message box for the cached obsstate
    :type cached_obsstate: dict<string, :py:class:`ska.base.control_model.ObsState`>
    """
    we_have_mvplow_running_an_instance_of(devices, devices_to_load, "mccs")
    component_is_ready_to_action_a_subarray(devices, "mccs", "allocate")
    subarray_obsstate_is_idle_or_empty(devices, cached_obsstate)
    tmc_allocates_a_subarray_with_validity_parameters(devices, "valid")
    if desired_state == "configured" or desired_state == "scanning":
        configure_subarray(devices)
        the_subarray_obsstate_is(devices, "ready")
    if desired_state == "scanning":
        tmc_starts_a_scan_on_subarray(devices)
        the_subarray_obsstate_is(devices, "scanning")


def configure_subarray(devices):
    """
    Configure the subarray.

    :param devices: fixture that provides access to devices by their name
    :type devices: dict<string, :py:class:`tango.DeviceProxy`>
    """
    # Configure the subarray
    configuration = {
        "stations": [{"station_id": 1}, {"station_id": 2}],
        "subarray_beams": [
            {
                "subarray_id": 1,
                "subarray_beam_id": 1,
                "station_ids": [1, 2],
                "channels": [[0, 8, 1, 1], [8, 8, 2, 1]],
                "update_rate": 0.0,
                "sky_coordinates": [0.0, 180.0, 0.0, 45.0, 0.0],
            }
        ],
    }
    json_string = json.dumps(configuration)
    assert_command(
        device=devices["subarray_01"], command="Configure", argin=json_string
    )


@when(parsers.parse("tmc starts a scan on subarray"))
def tmc_starts_a_scan_on_subarray(devices):
    """
    TMC starts a scan on the subarray.

    :param devices: fixture that provides access to devices by their name
    :type devices: dict<string, :py:class:`tango.DeviceProxy`>
    """
    scan_config = {"id": 1, "scan_time": 4}
    json_string = json.dumps(scan_config)
    assert_command(
        device=devices["subarray_01"],
        command="Scan",
        argin=json_string,
        expected_result=ResultCode.STARTED,
    )


@when(parsers.parse("tmc configures the subarray"))
def tmc_configures_the_subarray(devices):
    """
    TMC configures a subarray.

    :param devices: fixture that provides access to devices by their name
    :type devices: dict<string, :py:class:`tango.DeviceProxy`>
    """
    configure_subarray(devices)
    the_subarray_obsstate_is(devices, "ready")


@then(parsers.parse("the subarray obsstate is {obsstate}"))
def the_subarray_obsstate_is(devices, obsstate):
    """
    The subarray obsstate is {obsstate}

    :param devices: fixture that provides access to devices by their name
    :type devices: dict<string, :py:class:`tango.DeviceProxy`>
    :param obsstate: The observation state
    :type obsstate: str
    """
    assert devices["subarray_01"].obsState.name == obsstate.upper()


@then(parsers.parse("subarray health is good"))
def subarray_health_is_good(devices):
    """
    The health of the subarray is good.

    :param devices: fixture that provides access to devices by their name
    :type devices: dict<string, :py:class:`tango.DeviceProxy`>
    """
    assert devices["subarray_01"].healthState == HealthState.OK


@scenario("controller_subarray_interactions.feature", "MCCS Perform a scan on subarray")
def test_perform_a_scan_on_subarray(devices):
    """
    This is run at the end of the scenario. Turn MCCS Controller Off.

    :param devices: fixture that provides access to devices by their name
    :type devices: dict<string, :py:class:`tango.DeviceProxy`>
    """
    assert_command(device=devices["subarray_01"], command="EndScan")
    assert_command(device=devices["subarray_01"], command="End")
    release_config = {"subarray_id": 1, "release_all": True}
    json_string = json.dumps(release_config)
    assert_command(device=devices["controller"], command="Release", argin=json_string)
    assert_command(device=devices["controller"], command="Off")
    check_reset_state(devices)


@scenario(
    "controller_subarray_interactions.feature",
    "MCCS Perform an abort on a scanning subarray",
)
def test_perform_an_abort_on_a_scanning_subarray(devices):
    """
    This is run at the end of the scenario. Turn MCCS Controller Off.

    :param devices: fixture that provides access to devices by their name
    :type devices: dict<string, :py:class:`tango.DeviceProxy`>
    """
    assert_command(device=devices["subarray_01"], command="ObsReset")
    release_config = {"subarray_id": 1, "release_all": True}
    json_string = json.dumps(release_config)
    assert_command(device=devices["controller"], command="Release", argin=json_string)
    assert_command(device=devices["controller"], command="Off")
    check_reset_state(devices)


@when(parsers.parse("tmc issues an abort on subarray"))
def tmc_issues_an_abort_on_subarray(devices):
    """
    TMC issues an abort on the subarray.

    :param devices: fixture that provides access to devices by their name
    :type devices: dict<string, :py:class:`tango.DeviceProxy`>
    """
    the_subarray_obsstate_is(devices, "scanning")
    assert_command(device=devices["subarray_01"], command="Abort")
