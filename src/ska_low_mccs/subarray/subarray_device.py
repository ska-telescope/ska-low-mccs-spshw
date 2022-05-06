# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements MCCS functionality for monitoring and control of subarrays."""

from __future__ import annotations  # allow forward references in type hints

import json
from typing import Any, List, Optional, Tuple

import tango
from ska_tango_base.commands import (  # FastCommand,
    DeviceInitCommand,
    ResultCode,
    SubmittedSlowCommand,
)
from ska_tango_base.control_model import CommunicationStatus, HealthState
from ska_tango_base.executor import TaskStatus
from ska_tango_base.subarray import SKASubarray
from tango.server import attribute, command

import ska_low_mccs.release as release
from ska_low_mccs.subarray import SubarrayComponentManager, SubarrayHealthModel

__all__ = ["MccsSubarray", "main"]


DevVarLongStringArrayType = Tuple[List[ResultCode], List[Optional[str]]]


class MccsSubarray(SKASubarray):
    """MccsSubarray is the Tango device class for the MCCS Subarray prototype."""

    # -----------------
    # Device Properties
    # -----------------

    # ---------------
    # Initialisation
    # ---------------
    def init_device(self: MccsSubarray) -> None:
        """
        Initialise the device.

        This is overridden here to change the Tango serialisation model.
        """
        util = tango.Util.instance()
        util.set_serial_model(tango.SerialModel.NO_SYNC)
        self._max_workers = 1
        super().init_device()

    def _init_state_model(self: MccsSubarray) -> None:
        super()._init_state_model()
        self._health_state = HealthState.UNKNOWN  # InitCommand.do() does this too late.
        self._health_model = SubarrayHealthModel(self._component_state_changed_callback)
        self.set_change_event("healthState", True, False)

    def create_component_manager(
        self: MccsSubarray,
    ) -> SubarrayComponentManager:
        """
        Create and return a component manager for this device.

        :return: a component manager for this device.
        """
        return SubarrayComponentManager(
            self.logger,
            self._max_workers,
            self._component_communication_status_changed,
            self._component_state_changed_callback,
        )

    def init_command_objects(self: MccsSubarray) -> None:
        """Initialise the command handlers for commands supported by this device."""
        super().init_command_objects()

        for (command_name, method_name) in [
            ("SendTransientBuffer", "send_transient_buffer"),
            ("AssignResources", "assign"),
            ("ReleaseResources", "release"),
            ("ReleaseAllResources", "release_all"),
            ("Configure", "configure"),
            ("Scan", "scan"),
            ("EndScan", "end_scan"),
            ("End", "deconfigure"),
            ("ObsReset", "obsreset"),
            ("Restart", "restart"),
        ]:
            self.register_command_object(
                command_name,
                SubmittedSlowCommand(
                    command_name,
                    self._command_tracker,
                    self.component_manager,
                    method_name,
                    callback=None,
                    logger=self.logger,
                ),
            )

    class InitCommand(DeviceInitCommand):
        """Command class for device initialisation."""

        def do(  # type: ignore[override]
            self: MccsSubarray.InitCommand,
        ) -> tuple[ResultCode, str]:
            """
            Initialise the attributes and properties of MccsSubarray.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            self._device.set_change_event("stationFQDNs", True, True)
            self._device.set_archive_event("stationFQDNs", True, True)

            self._device._build_state = release.get_release_info()
            self._device._version_id = release.version

            return (ResultCode.OK, "Init command started")

    # ----------
    # Callbacks
    # ----------
    def _component_state_changed_callback(
        self: MccsSubarray,
        state_change: dict[str, Any],
        fqdn: Optional[str] = None,
    ) -> None:
        """
        Handle change in this device's state.

        This is a callback hook, called whenever the state changes. It
        is responsible for updating the tango side of things i.e. making
        sure the attribute is up to date, and events are pushed.

        :param state_change: A dictionary containing the name of the state that changed and its new value.
        :param fqdn: The fqdn of the device.
        """
        #print("IN CALLBACK")
        #print(f"state change: {state_change}")
        #print(f"fqdn: {fqdn}")
        # The commented out stuff is an idea to solve an issue with proxies that hasn't reared its head yet.
        # valid_device_types = {"station": "station_health_changed",
        #                     "beam": "station_beam_health_changed",
        #                     "subarraybeam": "subarray_beam_health_changed"}
        if "health_state" in state_change.keys():
            health = state_change.get("health_state")
            if self._health_state != health:
                self._health_state = health
                self.push_change_event("healthState", health)
            # If all health states use "health_state" and overwrite each other
            # then the below code should fix it.
            # if fqdn is None:
            #     # Do regular health update. This device called the callback.
            #    if self._health_state != health:
            #         self._health_state = health
            #         self.push_change_event("healthState", health)
            # else:
            #     # Identify and call subservient device method.
            #     device_type = fqdn.split("/")[1]
            #     if device_type in valid_device_types.keys():
            #         valid_device_types[device_type](fqdn, health)

        if "station_health_state" in state_change.keys():
            station_health = state_change.get("station_health_state")
            self._health_model.station_health_changed(fqdn, station_health)

        if "station_beam_health_state" in state_change.keys():
            station_beam_health = state_change.get("station_beam_health_state")
            self._health_model.station_beam_health_changed(fqdn, station_beam_health)

        if "subarray_beam_health_state" in state_change.keys():
            subarray_beam_health = state_change.get("subarray_beam_health_state")
            self._health_model.subarray_beam_health_changed(fqdn, subarray_beam_health)

        # resources should be passed in the dict's value as a list of sets to be extracted here.
        if "resources_changed" in state_change.keys():
            print("IN CALLBACK RESOURCES CHANGED")
            resources = state_change.get("resources_changed")
            station_fqdns = resources[0]
            subarray_beam_fqdns = resources[1]
            station_beam_fqdns = resources[2]
            self._resources_changed(
                station_fqdns, subarray_beam_fqdns, station_beam_fqdns
            )

        if "configured_changed" in state_change.keys():
            is_configured = state_change.get("configured_changed")
            if is_configured:
                self.obs_state_model.perform_action("component_configured")
            else:
                self.obs_state_model.perform_action("component_unconfigured")

        if "scanning_changed" in state_change.keys():
            is_scanning = state_change.get("scanning_changed")
            if is_scanning:
                self.obs_state_model.perform_action("component_scanning")
            else:
                self.obs_state_model.perform_action("component_not_scanning")

        if "assign_completed" in state_change.keys():
            self.obs_state_model.perform_action("assign_completed")

        if "release_completed" in state_change.keys():
            self.obs_state_model.perform_action("release_completed")

        if "configure_completed" in state_change.keys():
            self.obs_state_model.perform_action("configure_completed")

        if "abort_completed" in state_change.keys():
            self.obs_state_model.perform_action("abort_completed")

        if "obsreset_completed" in state_change.keys():
            self.obs_state_model.perform_action("obsreset_completed")

        if "restart_completed" in state_change.keys():
            self.obs_state_model.perform_action("restart_completed")

        if "obsfault" in state_change.keys():
            self.obs_state_model.perform_action("component_obsfault")

        if "obsstate_changed" in state_change.keys():
            obs_state = state_change.get("obsstate_changed")
            self.component_manager._device_obs_state_changed(fqdn, obs_state)

        if "station_power_state" in state_change.keys():
            station_power = state_change.get("station_power_state")
            self.component_manager._station_power_state_changed(fqdn, station_power)

        # This might need changing. Seems that "power_state" changes could come from any subservient device too.
        if "power_state" in state_change.keys():
            power_state = state_change.get("power_state")
            with self.component_manager._power_state_lock:
                if power_state != self.component_manager.power_state:
                    self.component_manager.power_state = power_state

    def _component_communication_status_changed(
        self: MccsSubarray,
        communication_status: CommunicationStatus,
    ) -> None:
        """
        Handle change in communications status between component manager and component.

        This is a callback hook, called by the component manager when
        the communications status changes. It is implemented here to
        drive the op_state.

        :param communication_status: the status of communications
            between the component manager and its component.
        """
        action_map = {
            CommunicationStatus.DISABLED: "component_disconnected",
            CommunicationStatus.NOT_ESTABLISHED: "component_unknown",
            CommunicationStatus.ESTABLISHED: "component_on",
        }

        action = action_map[communication_status]
        if action is not None:
            self.op_state_model.perform_action(action)

        self._health_model.is_communicating(
            communication_status == CommunicationStatus.ESTABLISHED
        )

    def _resources_changed(
        self: MccsSubarray,
        station_fqdns: set[str],
        subarray_beam_fqdns: set[str],
        station_beam_fqdns: set[str],
    ) -> None:
        """
        Handle change in subarray resources.

        This is a callback hook, called by the component manager when
        the resources of the subarray changes.

        :param station_fqdns: the FQDNs of stations assigned to this
            subarray
        :param subarray_beam_fqdns: the FQDNs of subarray beams assigned
            to this subarray
        :param station_beam_fqdns: the FQDNs of station beams assigned
            to this subarray
        """
        print("IN _RESOURCES CHANGED")
        
        if station_fqdns or subarray_beam_fqdns or station_beam_fqdns:
            print("ACTION 1")
            print(self.obs_state_model.obs_state)
            self.obs_state_model.perform_action("component_resourced")
            print("AFTER ACTION 1")
        else:
            print("ACTION 2")
            print(self.obs_state_model.obs_state)
            self.obs_state_model.perform_action("component_unresourced")
            print("AFTER ACTION 2")

        print("AFTER IF")
        self._health_model.resources_changed(
            station_fqdns, subarray_beam_fqdns, station_beam_fqdns
        )
        print("DONE RES CHANGE")

    # def health_changed(self: MccsSubarray, health: HealthState) -> None:
    #     """
    #     Handle the HealthModel's health state changes.

    #     Responsible for updating the tango side of things i.e. making sure the attribute
    #     is up to date, and events are pushed.

    #     :param health: the new health value
    #     """
    #     if self._health_state == health:
    #         return
    #     self._health_state = health
    #     self.push_change_event("healthState", health)

    # ------------------
    # Attribute methods
    # ------------------
    @attribute(dtype="DevLong", format="%i")
    def scanId(self: MccsSubarray) -> int:
        """
        Return the scan id.

        :return: the scan id
        """
        scan_id = self.component_manager.scan_id
        return scan_id if scan_id is not None else -1

    @scanId.write  # type: ignore[no-redef]
    def scanId(self: MccsSubarray, scan_id) -> None:
        """
        Set the scanId attribute.

        :param scan_id: the new scanId
        """
        self.component_manager.scan_id = scan_id

    @attribute(dtype=("DevString",), max_dim_x=512, format="%s")
    def stationFQDNs(self: MccsSubarray) -> list[str]:
        """
        Return the FQDNs of stations assigned to this subarray.

        :return: FQDNs of stations assigned to this subarray
        """
        return sorted(self.component_manager.station_fqdns)

    @attribute(dtype=("DevString"), max_dim_x=1024)
    def assignedResources(self: MccsSubarray) -> str:
        """
        Return this subarray's assigned resources.

        :return: this subarray's assigned resources.
        """
        resource_dict = self.component_manager.assigned_resources_dict
        stations = []
        for station_group in resource_dict["stations"]:
            stations.append(
                [station.split("/")[-1].lstrip("0") for station in station_group]
            )
        subarray_beams = [
            subarray_beam.split("/")[-1].lstrip("0")
            for subarray_beam in resource_dict["subarray_beams"]
        ]
        channel_blocks = resource_dict["channel_blocks"]
        return json.dumps(
            {
                "interface": "https://schema.skao.int/ska-low-mccs-assignedresources/1.0",
                "subarray_beam_ids": subarray_beams,
                "station_ids": stations,
                "channel_blocks": channel_blocks,
            }
        )

    # ------------------
    # Attribute methods
    # ------------------
    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def AssignResources(self: MccsSubarray, argin: str) -> tuple[ResultCode, str]:
        """
        Assign resources to this subarray.

        :param argin: the resources to be assigned

        :return: A tuple containing a return code and a string
            message indicating status.
        """
        handler = self.get_command_object("AssignResources")
        params = json.loads(argin)
        (return_code, unique_id) = handler(params)
        return ([return_code], [unique_id])

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def ReleaseResources(self: MccsSubarray, argin: str) -> tuple[ResultCode, str]:
        """
        Release resources from this subarray.

        :param argin: the resources to be released

        :return: A tuple containing a return code and a string
            message indicating status.
        """
        handler = self.get_command_object("ReleaseResources")
        params = json.loads(argin)
        (return_code, unique_id) = handler(params)
        return ([return_code], [unique_id])

    @command(dtype_out="DevVarLongStringArray")
    def ReleaseAllResources(self: MccsSubarray) -> tuple[ResultCode, str]:
        """
        Release all resources from this subarray.

        :return: A tuple containing a return code and a string
            message indicating status.
        """
        print("RELEASEALLRESOURCES")
        handler = self.get_command_object("ReleaseAllResources")
        (return_code, unique_id) = handler()
        return ([return_code], [unique_id])

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def Configure(
        self: MccsSubarray,
        argin: dict,
    ) -> tuple[ResultCode, str]:
        """
        Configure this subarray.

        :param argin: Dictionary containing configuration settings.

        :return: A tuple containing a return code and a string
            message indicating status.
        """
        handler = self.get_command_object("Configure")
        (return_code, unique_id) = handler(argin)
        return ([return_code], [unique_id])

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def Scan(
        self: MccsSubarray,
        argin: dict[str, Any],
    ) -> tuple[ResultCode, str]:
        """
        Start scanning.

        :param argin: Json string containing scan_id and start_time.

        :return: A tuple containing a return code and a string
            message indicating status.
        """
        scan_id = argin["scan_id"]
        start_time = argin["start_time"]

        handler = self.get_command_object("Scan")
        (return_code, unique_id) = handler(scan_id, start_time)
        return ([return_code], [unique_id])

    @command(dtype_out="DevVarLongStringArray")
    def EndScan(self: MccsSubarray) -> tuple[ResultCode, str]:
        """
        Stop scanning.

        :return: A tuple containing a return code and a string
            message indicating status.
        """
        handler = self.get_command_object("EndScan")
        (return_code, unique_id) = handler()
        return ([return_code], [unique_id])

    @command(dtype_out="DevVarLongStringArray")
    def End(self: MccsSubarray) -> tuple[ResultCode, str]:
        """
        Deconfigure resources.

        :return: A tuple containing a return code and a string
            message indicating status.
        """
        handler = self.get_command_object("End")
        (return_code, unique_id) = handler()
        return ([return_code], [unique_id])

    #     class AbortCommand(FastCommand):
    #         """Class for handling the Abort() command."""
    #
    #         RESULT_MESSAGES = {
    #             ResultCode.OK: "Abort command started",  # Base classes return this
    #             ResultCode.FAILED: "Abort command failed",
    #         }
    #
    #         def do(  # type: ignore[override]
    #             self: MccsSubarray.AbortCommand,
    #         ) -> tuple[ResultCode, str]:
    #             """
    #             Implement the functionality of the AbortCommand.
    #
    #             :py:meth:`ska_tango_base.FastCommand` command for this
    #             :py:class:`.MccsSubarray` device.
    #
    #             An abort command will leave the system in an ABORTED state.
    #             Output to CSP is stopped, as is the beamformer and all running
    #             jobs. The system can then be inspected in the ABORTED state
    #             before it's de-configured and returned to the IDLE state by the
    #             ObsReset command.
    #
    #             :return: A tuple containing a return code and a string
    #                 message indicating status. The message is for
    #                 information purpose only.
    #             """
    #             result_code = self.component_manager.abort()
    #             return (result_code, self.RESULT_MESSAGES[result_code])

    @command(dtype_out="DevVarLongStringArray")
    def ObsReset(self: MccsSubarray) -> tuple[ResultCode, str]:
        """
        Reset the observation by returning to unconfigured state.

        :return: A tuple containing a return code and a string
            message indicating status.
        """
        handler = self.get_command_object("ObsReset")
        (return_code, unique_id) = handler()
        return ([return_code], [unique_id])

    @command(dtype_out="DevVarLongStringArray")
    def Restart(self: MccsSubarray) -> tuple[ResultCode, str]:
        """
        Restart the subarray by returning to unresourced state.

        :return: A tuple containing a return code and a string
            message indicating status.
        """
        handler = self.get_command_object("Restart")
        (return_code, unique_id) = handler()
        return ([return_code], [unique_id])

    @command(dtype_in="DevVarLongArray", dtype_out="DevVarLongStringArray")
    def SendTransientBuffer(
        self: MccsSubarray, argin: list[int]
    ) -> tuple[TaskStatus, str]:
        """
        Cause the subarray to send the requested segment of the transient buffer to SDP.

        The requested segment is specified by:

        1. Start time (timestamp: milliseconds since UNIX epoch)
        2. End time (timestamp: milliseconds since UNIX epoch)
        3. Dispersion measure

        Together, these parameters narrow the selection of transient
        buffer data to the period of time and frequencies that are of
        interest.

        Additional metadata, such as the ID of a triggering Scheduling
        Block, may need to be supplied to allow SDP to assign data
        ownership correctly (TBD75).

        :todo: This method is a stub that does nothing but return a
            dummy string.

        :param argin: Specification of the segment of the transient
            buffer to send

        :return: ASCII String that indicates status, for information
            purposes only
        """
        handler = self.get_command_object("SendTransientBuffer")
        (result_code, unique_id) = handler(argin)
        return ([result_code], [unique_id])


# ----------
# Run server
# ----------
def main(*args: str, **kwargs: str) -> int:  # pragma: no cover
    """
    Entry point for module.

    :param args: positional arguments
    :param kwargs: named arguments

    :return: exit code
    """
    return MccsSubarray.run_server(args=args or None, **kwargs)


if __name__ == "__main__":
    main()
