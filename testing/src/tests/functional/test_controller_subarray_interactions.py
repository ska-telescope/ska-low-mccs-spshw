"""This module contains the BDD tests for TMC-MCCS interactions."""
from __future__ import annotations

# import json
# import time

# import pytest
from pytest_bdd import scenario, given, parsers, then, when
import tango

# from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import AdminMode  # , HealthState, ObsState

from ska_low_mccs import MccsDeviceProxy

from ska_low_mccs.testing.mock import MockChangeEventCallback

# from ska_low_mccs.testing.tango_harness import TangoHarness


@scenario(
    "features/controller_subarray_interactions.feature", "MCCS Turn on low telescope"
)
def test_turn_on_low_telescope(
    controller: MccsDeviceProxy,
    subarrays: dict[int, MccsDeviceProxy],
    stations: dict[int, MccsDeviceProxy],
    controller_device_state_changed_callback: MockChangeEventCallback,
) -> None:
    """
    This is run at the end of the scenario. Turn MCCS Controller Off.

    :param controller: a proxy to the controller device
    :param subarrays: proxies to the subarray devices, keyed by number
    :param stations: proxies to the station devices, keyed by number
    :param controller_device_state_changed_callback: a callback to be
        used to subscribe to controller state change
    """
    controller.Off()
    controller_device_state_changed_callback.assert_last_change_event(
        tango.DevState.OFF
    )

    assert controller.state() == tango.DevState.OFF

    assert subarrays[1].state() == tango.DevState.ON
    assert subarrays[2].state() == tango.DevState.ON
    assert subarrays[1].stationFQDNs is None or subarrays[1].stationFQDNs == ()
    assert subarrays[2].stationFQDNs is None or subarrays[2].stationFQDNs == ()

    assert stations[1].state() == tango.DevState.OFF
    assert stations[2].state() == tango.DevState.OFF
    assert stations[1].subarrayId == 0
    assert stations[2].subarrayId == 0


@given(parsers.parse("we have mvplow running an instance of {subsystem_name}"))
def we_have_mvplow_running_an_instance_of(
    subsystem_name: str,
    controller: MccsDeviceProxy,
    controller_device_state_changed_callback: MockChangeEventCallback,
    subrack: MccsDeviceProxy,
    subarrays: dict[int, MccsDeviceProxy],
    subarray_beams: dict[int, MccsDeviceProxy],
    stations: dict[int, MccsDeviceProxy],
    station_beams: dict[int, MccsDeviceProxy],
    apius: dict[int, MccsDeviceProxy],
    tiles: dict[int, MccsDeviceProxy],
    antennas: dict[int, MccsDeviceProxy],
) -> None:
    """
    Asserts the existence/availability of a subsystem.

    :param subsystem_name: name of the subsystem
    :param controller: a proxy to the controller device
    :param controller_device_state_changed_callback: a callback to be
        used to subscribe to controller state change
    :param subrack: a proxy to the subrack device
    :param subarrays: proxies to the subarray devices, keyed by number
    :param subarray_beams: proxies to the subarray beam devices, keyed by number
    :param stations: proxies to the station devices, keyed by number
    :param station_beams: proxies to the station beam devices, keyed by number
    :param apius: proxies to the apiu devices, keyed by number
    :param tiles: proxies to the tile devices, keyed by number
    :param antennas: proxies to the antenna devices, keyed by number
    """
    assert subsystem_name in ["mccs", "tmc"]

    if subsystem_name == "tmc":
        return

    controller.add_change_event_callback(
        "state", controller_device_state_changed_callback
    )
    controller_device_state_changed_callback.assert_next_change_event(
        tango.DevState.DISABLE
    )

    subrack.adminMode = AdminMode.ONLINE
    subarrays[1].adminMode = AdminMode.ONLINE
    subarrays[2].adminMode = AdminMode.ONLINE
    subarray_beams[1].adminMode = AdminMode.ONLINE
    subarray_beams[2].adminMode = AdminMode.ONLINE
    subarray_beams[3].adminMode = AdminMode.ONLINE
    subarray_beams[4].adminMode = AdminMode.ONLINE
    stations[1].adminMode = AdminMode.ONLINE
    stations[2].adminMode = AdminMode.ONLINE
    station_beams[1].adminMode = AdminMode.ONLINE
    station_beams[2].adminMode = AdminMode.ONLINE
    station_beams[3].adminMode = AdminMode.ONLINE
    station_beams[4].adminMode = AdminMode.ONLINE
    apius[1].adminMode = AdminMode.ONLINE
    apius[2].adminMode = AdminMode.ONLINE
    tiles[1].adminMode = AdminMode.ONLINE
    tiles[2].adminMode = AdminMode.ONLINE
    tiles[3].adminMode = AdminMode.ONLINE
    tiles[4].adminMode = AdminMode.ONLINE
    antennas[1].adminMode = AdminMode.ONLINE
    antennas[2].adminMode = AdminMode.ONLINE
    antennas[3].adminMode = AdminMode.ONLINE
    antennas[4].adminMode = AdminMode.ONLINE
    antennas[5].adminMode = AdminMode.ONLINE
    antennas[6].adminMode = AdminMode.ONLINE
    antennas[7].adminMode = AdminMode.ONLINE
    antennas[8].adminMode = AdminMode.ONLINE
    controller.adminMode = AdminMode.ONLINE

    controller_device_state_changed_callback.assert_next_change_event(
        tango.DevState.UNKNOWN
    )
    controller_device_state_changed_callback.assert_next_change_event(
        tango.DevState.OFF
    )


@given(parsers.parse("{subsystem_name} is ready to {direction} an on command"))
def subsystem_is_ready_to_receive_an_on_command(
    subsystem_name: str,
    direction: str,
    controller: MccsDeviceProxy,
) -> None:
    """
    Asserts that a subsystem is ready to receive an on command.

    :param controller: a proxy to the controller device
    :param subsystem_name: name of the subsystem
    :param direction: direction of communication

    :raises AssertionError: if passed an unknown subsystem
    """
    if subsystem_name == "mccs":
        assert controller.state() == tango.DevState.OFF
    elif subsystem_name == "tmc":
        pass
    else:
        raise AssertionError(f"Unknown subsystem {subsystem_name}")


@when(parsers.parse("tmc tells mccs controller to turn on"))
def tmc_tells_mccs_controller_to_turn_on(
    controller: MccsDeviceProxy,
    controller_device_state_changed_callback: MockChangeEventCallback,
) -> None:
    """
    Issue an on command to MCCS Controller

    :param controller: a proxy to the controller device
    """
    controller.On()
    controller_device_state_changed_callback.assert_last_change_event(tango.DevState.ON)
    assert controller.state() == tango.DevState.ON


@then(parsers.parse("mccs controller state is {state_name}"))
def check_mccs_controller_state(
    state_name: str,
    controller: MccsDeviceProxy,
    controller_device_state_changed_callback: MockChangeEventCallback,
) -> None:
    """
    Asserts that mccs controller is on/off.

    :param controller: a proxy to the controller device
    :param controller_device_state_changed_callback: a callback to be
        used to subscribe to controller state change
    :param state_name: asserted state of the device -- either "off" or
        "on"
    """
    state_map = {
        "off": tango.DevState.OFF,
        "on": tango.DevState.ON,
    }
    device_state = state_map[state_name]
    controller_device_state_changed_callback.assert_last_change_event(device_state)
    assert controller.state() == device_state


@then(parsers.parse("all mccs station states are {state}"))
def all_mccs_station_states_are_onoff(
    state_name: str,
    stations: dict[int, MccsDeviceProxy],
) -> None:
    """
    Asserts that online or maintenance mccs station devices are on/off.

    :param stations: proxies to the station devices, keyed by number
    :param state_name: asserted state of the device -- either "off" or
        "on"
    """
    state_map = {
        "off": tango.DevState.OFF,
        "on": tango.DevState.ON,
    }
    device_state = state_map[state_name]
    for i in stations:
        assert stations[i].state() == device_state


# @scenario("features/controller_subarray_interactions.feature", "MCCS Allocate subarray")
# def test_allocate_subarray(controller, subarrays, stations):
#     """
#     This is run at the end of the scenario. Turn MCCS Controller Off.

#     :param controller: a proxy to the controller device
#     :type controller: :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`
#     :param subarrays: proxies to the subarray devices, keyed by number
#     :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
#     :param stations: proxies to the station devices, keyed by number
#     :type stations: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
#     """
#     release_config = {"subarray_id": 1, "release_all": True}
#     json_string = json.dumps(release_config)
#     assert_command(device=controller, command="Release", argin=json_string)
#     assert_command(device=controller, command="Off", expected_result=ResultCode.QUEUED)
#     wait_for_command_to_complete(controller)
#     command_helper.check_device_state(controller, tango.DevState.OFF)
#     check_reset_state(controller, subarrays, stations)


# @given(parsers.parse("{subsystem_name} is ready to {action} a subarray"))
# def subsystem_is_ready_to_action_a_subarray(
#     subsystem_name, action, controller, subarrays, stations
# ):
#     """
#     Asserts that a subsystem is ready to perform an action on a subarray.

#     :param subsystem_name: name of the subsystem
#     :type subsystem_name: str
#     :param action: action to perform on a subarray
#     :type action: str
#     :param controller: a proxy to the controller device
#     :type controller: :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`
#     :param subarrays: proxies to the subarray devices, keyed by number
#     :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
#     :param stations: proxies to the station devices, keyed by number
#     :type stations: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
#     """
#     if subsystem_name == "mccs":
#         tmc_tells_mccs_controller_to_turn_on(controller)
#         check_mccs_device_state(controller, "on")
#         check_mccs_device_state(subarrays[1], "off")
#         check_mccs_device_state(subarrays[2], "off")
#         assert stations[1].subarrayId == 0
#         assert stations[2].subarrayId == 0
#     elif subsystem_name == "tmc":
#         pass
#     else:
#         assert False


# @given(parsers.parse("subarray obsstate is idle or empty"))
# def subarray_obsstate_is_idle_or_empty(subarrays, cached_obsstate):
#     """
#     The obsstate of each subarray should be idle or empty.

#     :param subarrays: proxies to the subarray devices, keyed by number
#     :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
#     :param cached_obsstate: pytest message box for the cached obsstate
#     :type cached_obsstate:
#         dict<string, :py:class:`~ska_tango_base.control_model.ObsState`>
#     """
#     for i in subarrays:
#         obsstate = subarrays[i].obsstate
#         assert (obsstate == ObsState.IDLE) or (obsstate == ObsState.EMPTY)
#         cached_obsstate[i] = obsstate


# @when(parsers.parse("tmc allocates a subarray with {validity} parameters"))
# def tmc_allocates_a_subarray_with_validity_parameters(controller, subarrays, validity):
#     """
#     TMC allocates a subarray.

#     :param controller: a proxy to the controller device
#     :type controller: :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`
#     :param subarrays: proxies to the subarray devices, keyed by number
#     :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
#     :param validity: whether the allocate has valid|invalid parameters
#     :type validity: str
#     """
#     parameters = {
#         "subarray_id": 1,
#         "station_ids": [[1, 2]],
#         "channel_blocks": [2],
#         "subarray_beam_ids": [1],
#     }

#     if validity == "invalid":
#         parameters["subarray_id"] = 3
#         json_string = json.dumps(parameters)
#         assert_command(
#             device=controller,
#             command="Allocate",
#             argin=json_string,
#             expected_result=ResultCode.FAILED,
#         )
#         return

#     json_string = json.dumps(parameters)
#     [result], [message, uid] = controller.command_inout("Allocate", json_string)
#     assert result == ResultCode.QUEUED
#     assert ":Allocate" in uid
#     assert message

#     # Check that the allocate command has completed
#     wait_for_command_to_complete(controller)

#     command_result = controller.commandResult
#     kwargs = json.loads(command_result)
#     message_uid = kwargs.get("message_uid")
#     assert message_uid == uid

#     # We need to wait until the subarray is in IDLE state
#     assert subarrays[1].obsstate == ObsState.IDLE


# @then(parsers.parse("the stations have the correct subarray id"))
# def the_stations_have_the_correct_subarray_id(stations):
#     """
#     Stations have the correct subarray id.

#     :param stations: proxies to the station devices, keyed by number
#     :type stations: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
#     """
#     # We need to wait until the subarray is in IDLE state
#     for station_id in [1, 2]:
#         timeout = 0.0
#         while not stations[station_id].subarrayId == 1 and timeout < 5.0:
#             timeout += 0.1
#             time.sleep(0.1)
#         assert stations[station_id].subarrayId == 1
#         assert timeout < 5.0


# @then(parsers.parse("subarray state is on"))
# def subarray_state_is_on(subarrays):
#     """
#     The subarray should be on.

#     :param subarrays: proxies to the subarray devices, keyed by number
#     :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
#     """
#     assert subarrays[1].State() == tango.DevState.ON


# @then(
#     parsers.parse("according to allocation policy health of allocated subarray is good")
# )
# def according_to_allocation_policy_health_of_allocated_subarray_is_good(
#     controller, subarrays, stations
# ):
#     """
#     Health is good.

#     :param controller: a proxy to the controller device
#     :type controller: :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`
#     :param subarrays: proxies to the subarray devices, keyed by number
#     :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
#     :param stations: proxies to the station devices, keyed by number
#     :type stations: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
#     """
#     assert controller.healthState == HealthState.OK
#     assert subarrays[1].healthState == HealthState.OK
#     assert subarrays[2].healthState == HealthState.OK
#     assert stations[1].healthState == HealthState.OK
#     assert stations[2].healthState == HealthState.OK


# @then(parsers.parse("other resources are not affected"))
# def other_resources_are_not_affected(subarrays):
#     """
#     Other resource should not be affected.

#     :param subarrays: proxies to the subarray devices, keyed by number
#     :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
#     """
#     check_mccs_device_state(subarrays[2], "off")
#     assert subarrays[2].obsState == ObsState.EMPTY


# @then(parsers.parse("subarray obsstate is not changed"))
# def subarray_obsstate_is_not_changed(subarrays, cached_obsstate):
#     """
#     Check that the subarray obsState has not changed.

#     :param subarrays: proxies to the subarray devices, keyed by number
#     :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
#     :param cached_obsstate: pytest message box for the cached obsstate
#     :type cached_obsstate:
#         dict<string, :py:class:`~ska_tango_base.control_model.ObsState`>
#     """
#     assert subarrays[1].obsstate == cached_obsstate[1]
#     assert subarrays[2].obsstate == cached_obsstate[2]


# @scenario(
#     "features/controller_subarray_interactions.feature", "MCCS Configure a subarray"
# )
# def test_configure_a_subarray(controller, subarrays, stations):
#     """
#     This is run at the end of the scenario. Turn MCCS Controller Off.

#     :param controller: a proxy to the controller device
#     :type controller: :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`
#     :param subarrays: proxies to the subarray devices, keyed by number
#     :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
#     :param stations: proxies to the station devices, keyed by number
#     :type stations: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
#     """
#     assert_command(device=subarrays[1], command="End")
#     release_config = {"subarray_id": 1, "release_all": True}
#     json_string = json.dumps(release_config)
#     assert_command(device=controller, command="Release", argin=json_string)
#     assert_command(device=controller, command="Off", expected_result=ResultCode.QUEUED)
#     wait_for_command_to_complete(controller)
#     command_helper.check_device_state(controller, tango.DevState.OFF)
#     check_reset_state(controller, subarrays, stations)


# @given(parsers.parse("we have a successfully {desired_state} subarray"))
# def we_have_a_successfully_configured_and_or_allocated_subarray(
#     controller,
#     subarrays,
#     stations,
#     subracks,
#     tiles,
#     apius,
#     antennas,
#     subarraybeams,
#     desired_state,
#     cached_obsstate,
# ):
#     """
#     Get the subarray into an configured and/or allocated state.

#     :param controller: a proxy to the controller device
#     :type controller: :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`
#     :param subarrays: proxies to the subarray devices, keyed by number
#     :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
#     :param stations: proxies to the station devices, keyed by number
#     :type stations: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
#     :param subracks: proxies to the subrack devices, keyed by number
#     :type subracks: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
#     :param tiles: proxies to the tile devices, keyed by number
#     :type tiles: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
#     :param apius: proxies to the apiu devices, keyed by number
#     :type apius: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
#     :param antennas: proxies to the antenna devices, keyed by number
#     :type antennas: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
#     :param subarraybeams: proxies to the subarray beam devices, keyed by number
#     :type subarraybeams: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
#     :param desired_state: The desired state to be in
#     :type desired_state: str
#     :param cached_obsstate: pytest message box for the cached obsstate
#     :type cached_obsstate:
#         dict<string, :py:class:`~ska_tango_base.control_model.ObsState`>
#     """
#     we_have_mvplow_running_an_instance_of(
#         "mccs",
#         controller,
#         subarrays,
#         stations,
#         subracks,
#         tiles,
#         apius,
#         antennas,
#         subarraybeams,
#     )
#     subsystem_is_ready_to_action_a_subarray(
#         "mccs", "allocate", controller, subarrays, stations
#     )
#     subarray_obsstate_is_idle_or_empty(subarrays, cached_obsstate)
#     tmc_allocates_a_subarray_with_validity_parameters(controller, subarrays, "valid")

#     if desired_state == "configured" or desired_state == "scanning":
#         configure_subarray(subarrays)
#         the_subarray_obsstate_is(subarrays, "ready")
#     if desired_state == "scanning":
#         tmc_starts_a_scan_on_subarray(subarrays)
#         the_subarray_obsstate_is(subarrays, "scanning")
#     if desired_state == "allocated":
#         the_subarray_obsstate_is(subarrays, "idle")


# def configure_subarray(subarrays):
#     """
#     Configure the subarray.

#     :param subarrays: proxies to the subarray devices, keyed by number
#     :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
#     """
#     # Configure the subarray
#     configuration = {
#         "stations": [{"station_id": 1}, {"station_id": 2}],
#         "subarray_beams": [
#             {
#                 "subarray_beam_id": 1,
#                 "station_ids": [1, 2],
#                 "channels": [[0, 8, 1, 1], [8, 8, 2, 1]],
#                 "update_rate": 0.0,
#                 "sky_coordinates": [0.0, 180.0, 0.0, 45.0, 0.0],
#                 "antenna_weights": [1.0, 1.0, 1.0],
#                 "phase_centre": [0.0, 0.0],
#             }
#         ],
#     }
#     json_string = json.dumps(configuration)
#     assert_command(device=subarrays[1], command="Configure", argin=json_string)


# @when(parsers.parse("tmc starts a scan on subarray"))
# def tmc_starts_a_scan_on_subarray(subarrays):
#     """
#     TMC starts a scan on the subarray.

#     :param subarrays: proxies to the subarray devices, keyed by number
#     :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
#     """
#     scan_config = {"id": 1, "scan_time": 4}
#     json_string = json.dumps(scan_config)
#     assert_command(
#         device=subarrays[1],
#         command="Scan",
#         argin=json_string,
#         expected_result=ResultCode.STARTED,
#     )


# @when(parsers.parse("tmc configures the subarray"))
# def tmc_configures_the_subarray(subarrays):
#     """
#     TMC configures a subarray.

#     :param subarrays: proxies to the subarray devices, keyed by number
#     :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
#     """
#     configure_subarray(subarrays)
#     the_subarray_obsstate_is(subarrays, "ready")


# @then(parsers.parse("the subarray obsstate is {obsstate}"))
# def the_subarray_obsstate_is(subarrays, obsstate):
#     """
#     The subarray obsstate is {obsstate}

#     :param subarrays: proxies to the subarray devices, keyed by number
#     :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
#     :param obsstate: The observation state
#     :type obsstate: str
#     """
#     assert subarrays[1].obsState.name == obsstate.upper()


# @then(parsers.parse("subarray health is good"))
# def subarray_health_is_good(subarrays):
#     """
#     The health of the subarray is good.

#     :param subarrays: proxies to the subarray devices, keyed by number
#     :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
#     """
#     assert subarrays[1].healthState == HealthState.OK


# @scenario(
#     "features/controller_subarray_interactions.feature",
#     "MCCS Perform a scan on subarray",
# )
# def test_perform_a_scan_on_subarray(controller, subarrays, stations):
#     """
#     This is run at the end of the scenario. Turn MCCS Controller Off.

#     :param controller: a proxy to the controller device
#     :type controller: :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`
#     :param subarrays: proxies to the subarray devices, keyed by number
#     :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
#     :param stations: proxies to the station devices, keyed by number
#     :type stations: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
#     """
#     assert_command(device=subarrays[1], command="EndScan")
#     assert_command(device=subarrays[1], command="End")
#     release_config = {"subarray_id": 1, "release_all": True}
#     json_string = json.dumps(release_config)
#     assert_command(device=controller, command="Release", argin=json_string)
#     assert_command(device=controller, command="Off", expected_result=ResultCode.QUEUED)
#     wait_for_command_to_complete(controller)
#     command_helper.check_device_state(controller, tango.DevState.OFF)
#     check_reset_state(controller, subarrays, stations)


# def abort_post_operations(controller, subarrays, stations):
#     """
#     Collection of operations to perform after an abort command.

#     :param controller: a proxy to the controller device
#     :type controller: :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`
#     :param subarrays: proxies to the subarray devices, keyed by number
#     :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
#     :param stations: proxies to the station devices, keyed by number
#     :type stations: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
#     """
#     assert_command(device=subarrays[1], command="ObsReset")
#     release_config = {"subarray_id": 1, "release_all": True}
#     json_string = json.dumps(release_config)
#     assert_command(device=controller, command="Release", argin=json_string)
#     assert_command(device=controller, command="Off", expected_result=ResultCode.QUEUED)
#     wait_for_command_to_complete(controller)
#     command_helper.check_device_state(controller, tango.DevState.OFF)
#     check_reset_state(controller, subarrays, stations)


# @scenario(
#     "features/controller_subarray_interactions.feature",
#     "MCCS Perform an abort on a scanning subarray",
# )
# def test_perform_an_abort_on_a_scanning_subarray(
#     controller, subarrays, stations
# ):
#     """
#     This is run at the end of the scenario. Turn MCCS Controller Off.

#     :param controller: a proxy to the controller device
#     :type controller: :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`
#     :param subarrays: proxies to the subarray devices, keyed by number
#     :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
#     :param stations: proxies to the station devices, keyed by number
#     :type stations: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
#     """
#     abort_post_operations(controller, subarrays, stations)


# @scenario(
#     "features/controller_subarray_interactions.feature",
#     "MCCS Perform an abort on an idle subarray",
# )
# def test_perform_an_abort_on_an_idle_subarray(
#     controller, subarrays, stations
# ):
#     """
#     This is run at the end of the scenario. Turn MCCS Controller Off.

#     :param controller: a proxy to the controller device
#     :type controller: :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`
#     :param subarrays: proxies to the subarray devices, keyed by number
#     :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
#     :param stations: proxies to the station devices, keyed by number
#     :type stations: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
#     """
#     abort_post_operations(controller, subarrays, stations)


# @scenario(
#     "features/controller_subarray_interactions.feature",
#     "MCCS Perform an abort on a configured subarray",
# )
# def test_perform_an_abort_on_a_configured_subarray(
#     controller, subarrays, stations
# ):
#     """
#     This is run at the end of the scenario. Turn MCCS Controller Off.

#     :param controller: a proxy to the controller device
#     :type controller: :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`
#     :param subarrays: proxies to the subarray devices, keyed by number
#     :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
#     :param stations: proxies to the station devices, keyed by number
#     :type stations: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
#     """
#     abort_post_operations(controller, subarrays, stations)


# @when(parsers.parse("tmc issues an abort on subarray"))
# def tmc_issues_an_abort_on_subarray(subarrays):
#     """
#     TMC issues an abort on the subarray.

#     :param subarrays: proxies to the subarray devices, keyed by number
#     :type subarrays: dict<int, :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`>
#     """
#     subarrays[1].Abort()
