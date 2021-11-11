# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""This module contains the SKA Low MCCS Controller device prototype."""

from __future__ import annotations  # allow forward references in type hints

import json
from typing import List, Optional, Tuple, Union, cast

import tango
import time
from tango.server import attribute, command, device_property

from ska_tango_base.base import SKABaseDevice
from ska_tango_base.control_model import HealthState, PowerMode
from ska_tango_base.commands import ResponseCommand, ResultCode

from ska_low_mccs.component import CommunicationStatus
from ska_low_mccs.controller import ControllerComponentManager, ControllerHealthModel
import ska_low_mccs.release as release

__all__ = ["MccsController", "main"]

DevVarLongStringArrayType = Tuple[List[ResultCode], List[Optional[str]]]


class MccsController(SKABaseDevice):
    """An implementation of a controller Tango device for MCCS."""

    # -----------------
    # Device Properties
    # -----------------
    MccsSubarrays = device_property(dtype="DevVarStringArray", default_value=[])
    MccsSubracks = device_property(dtype="DevVarStringArray", default_value=[])
    MccsStations = device_property(dtype="DevVarStringArray", default_value=[])
    MccsSubarrayBeams = device_property(dtype="DevVarStringArray", default_value=[])
    MccsStationBeams = device_property(dtype="DevVarStringArray", default_value=[])

    # ---------------
    # Initialisation
    # ---------------
    def init_device(self: MccsController) -> None:
        """
        Initialise the device.

        This is overridden here to change the Tango serialisation model.
        """
        util = tango.Util.instance()
        util.set_serial_model(tango.SerialModel.NO_SYNC)
        super().init_device()

    def _init_state_model(self: MccsController) -> None:
        """Initialise the state model."""
        super()._init_state_model()
        self._health_state = HealthState.UNKNOWN  # InitCommand.do() does this too late.
        self._health_model = ControllerHealthModel(
            self.MccsStations,
            self.MccsSubracks,
            self.MccsSubarrayBeams,
            self.MccsStationBeams,
            self.health_changed,
        )
        self.set_change_event("healthState", True, False)
        # self.set_change_event("longRunningCommandResult", True, True)

    def create_component_manager(
        self: MccsController,
    ) -> ControllerComponentManager:
        """
        Create and return a component manager for this device.

        :return: a component manager for this device.
        """
        return ControllerComponentManager(
            self.MccsSubarrays,
            self.MccsSubracks,
            self.MccsStations,
            self.MccsSubarrayBeams,
            self.MccsStationBeams,
            self.logger,
            self._communication_status_changed,
            self._component_power_mode_changed,
            self._long_running_command_result_changed,
            self._health_model.subrack_health_changed,
            self._health_model.station_health_changed,
            self._health_model.subarray_beam_health_changed,
            self._health_model.station_beam_health_changed,
        )

    def init_command_objects(self: MccsController) -> None:
        """Set up the handler objects for Commands."""
        super().init_command_objects()

        self.register_command_object(
            "On",
            self.OnCommand(
                self, self.op_state_model, self.logger
            ),
        )
        self.register_command_object(
            "Allocate",
            self.AllocateCommand(
                self.component_manager, self.op_state_model, self.logger
            ),
        )
        self.register_command_object(
            "Release",
            self.ReleaseCommand(
                self.component_manager, self.op_state_model, self.logger
            ),
        )
        self.register_command_object(
            "RestartSubarray",
            self.RestartSubarrayCommand(
                self.component_manager, self.op_state_model, self.logger
            ),
        )

    class InitCommand(SKABaseDevice.InitCommand):
        """
        A class for :py:class:`~.MccsController`'s Init command.

        The :py:meth:`~.MccsController.InitCommand.do` method below is
        called during :py:class:`~.MccsController`'s initialisation.
        """

        def do(  # type: ignore[override]
            self: MccsController.InitCommand,
        ) -> tuple[ResultCode, str]:
            """
            Initialise the attributes and properties of the `MccsController`.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            (result_code, message) = super().do()

            device = self.target
            device._build_state = release.get_release_info()
            device._version_id = release.version

            # The health model updates our health, but then the base class super().do()
            # overwrites it with OK, so we need to update this again.
            # TODO: This needs to be fixed in the base classes.
            device._health_state = device._health_model.health_state
            device._long_running_command_result = ("a", "default", "value")

            return (result_code, message)

    class OnCommand(SKABaseDevice.OnCommand):
        """A class for the MccsController's On() command."""

        def do(  # type: ignore[override]
            self: MccsController.OnCommand,
        ):
            """
            Stateless hook for On() command functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (ResultCode, str)
            """
            result_code = self.target.component_manager.on()
            if result_code == ResultCode.FAILED:
                return (ResultCode.FAILED, "Controller failed to initiate On command")
            # Johan: block here
            #
            # Wait for conditions on CM to unblock
            # Could include timeouts here too
            #
            def wait_until_on(device, timeout, period=0.25) -> ResultCode:
                """Wait untill the device is on"""
                elapsed_time = 0.0
                while elapsed_time <= timeout:
                    if device.get_state() == tango.DevState.ON: return ResultCode.OK
                    time.sleep(period)
                return ResultCode.FAILED

            timeout = 10.0
            result_code = wait_until_on(self.target, timeout=timeout)
            message = "Controller On command completed OK"
            if result_code != ResultCode.OK:
                message = "Controller On command didn't complete within {timeout} seconds"

            self.logger.info(message)
            return (result_code, message)

    # ----------
    # Callbacks
    # ----------
    def _long_running_command_result_changed(
        self: MccsController,
        long_running_command_result: Union[Tuple[str, str, str], Tuple[()]],
    ) -> None:
        """
        Handle change in long running command result.

        Responsible for updating the tango side of things i.e. making sure the attribute
        is up to date, and events are pushed.

        :param long_running_command_result: the new long running command result value
        """
        if (self._long_running_command_result == long_running_command_result):
            return
        self._long_running_command_result = long_running_command_result
        self.push_change_event(
            "longRunningCommandResult",
            self._long_running_command_result,
        )

    def _communication_status_changed(
        self: MccsController,
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
            CommunicationStatus.ESTABLISHED: None,  # wait for a power mode update
        }

        action = action_map[communication_status]
        if action is not None:
            self.op_state_model.perform_action(action)

        self._health_model.is_communicating(
            communication_status == CommunicationStatus.ESTABLISHED
        )

    def _component_power_mode_changed(
        self: MccsController,
        power_mode: PowerMode,
    ) -> None:
        """
        Handle change in the power mode of the component.

        This is a callback hook, called by the component manager when
        the power mode of the component changes. It is implemented here
        to drive the op_state.

        :param power_mode: the power mode of the component.
        """
        print(f"RCL: _component_power_mode_changed {power_mode}")
        action_map = {
            PowerMode.OFF: "component_off",
            PowerMode.STANDBY: "component_standby",
            PowerMode.ON: "component_on",
            PowerMode.UNKNOWN: "component_unknown",
        }

        self.op_state_model.perform_action(action_map[power_mode])

    def health_changed(self: MccsController, health: HealthState) -> None:
        """
        Call this method whenever the HealthModel's health state changes.

        Responsible for updating the tango side of things i.e. making sure the attribute
        is up to date, and events are pushed.

        :param health: the new health value
        """
        if self._health_state == health:
            return
        self._health_state = health
        self.push_change_event("healthState", health)

    # ----------
    # Attributes
    # ----------
    # @attribute(dtype=("DevString",), max_dim_x=3)
    # def longRunningCommandResult(self: MccsController) -> list(str):
    #     """
    #     Return the long running command result attribute.
    #
    #     :return: _long_running_command_result attribute
    #     """
    #     return self._long_running_command_result

    @attribute(dtype="DevString")
    def assignedResources(self: MccsController) -> str:
        """
        Return the assigned resources attribute.

        :return: assignedResources attribute
        """
        return self.component_manager.assigned_resources

    # --------
    # Commands
    # --------
    class StandbyFullCommand(ResponseCommand):
        """
        Class for handling the StandbyFull command.

        :todo: What is this command supposed to do? It takes no
            argument, and returns nothing.
        """

        SUCCEEDED_MESSAGE = "StandbyFull command completed OK"
        FAILED_MESSAGE = "StandbyFull command failed"

        def do(  # type: ignore[override]
            self: MccsController.StandbyFullCommand,
        ) -> tuple[ResultCode, str]:
            """
            Stateless hook to execute the StandbyFull command.

            Implements the functionality of the
            :py:meth:`.MccsController.StandbyFull` command.

            :todo: For now, StandbyLow and StandbyHigh simply implement
                a general "standby".

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            device_pool = self.target

            if device_pool.standby():
                return (ResultCode.OK, self.SUCCEEDED_MESSAGE)
            else:
                return (ResultCode.FAILED, self.FAILED_MESSAGE)

    @command(dtype_out="DevVarLongStringArray")
    def StandbyFull(self: MccsController) -> DevVarLongStringArrayType:
        """
        Put MCCS into full standby mode.

        :todo: Some elements of SKA Mid have both low and full standby
            modes, but SKA Low has no such elements. We just need a
            Standby command, not separate StandbyLow and StandbyFull.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("StandbyFull")
        (result_code, status) = handler()
        return ([result_code], [status])

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def Allocate(self: MccsController, argin: str) -> DevVarLongStringArrayType:
        """
        Allocate a set of unallocated MCCS resources to a sub-array.

        The JSON argument
        specifies the overall sub-array composition in terms of which stations should be
        allocated to the specified Sub-Array.

        Method returns as soon as the message has been enqueued.

        :param argin: JSON-formatted string containing an integer
            subarray_id, station_ids, channels and subarray_beam_ids.

        :return: A tuple containing a return code, a string
            message indicating status and message UID.
            The string message is for information purposes only, but
            the message UID is for message management use.

        :example:

        >>> proxy = tango.DeviceProxy("low-mccs/control/control")
        >>> proxy.Allocate(
                json.dumps(
                {
                    "interface": "https://schema.skao.int/ska-low-mccs-assignresources/1.0",
                    "subarray_id": 1,
                    "subarray_beam_ids": [1],
                    "station_ids": [[1,2]],
                    "channel_blocks": [3],
                }
                )
            )
        """
        handler = self.get_command_object("Allocate")
        (result_code, message) = handler(argin)
        return ([result_code], [message])

    class AllocateCommand(ResponseCommand):
        """
        Allocate a set of unallocated MCCS resources to a subarray.

        The JSON argument specifies the overall sub-array composition in
        terms of which stations should be allocated to the specified
        subarray_beam.
        """

        SUCCEEDED_MESSAGE = "Allocate command completed OK"
        QUEUED_MESSAGE = "Allocate command queued"
        FAILED_MESSAGE = "Allocate command failed"

        def do(  # type: ignore[override]
            self: MccsController.AllocateCommand, argin: str
        ) -> tuple[ResultCode, str]:
            """
            Stateless hook to execute the Allocate command.

            Implements the functionality of the
            :py:meth:`.MccsController.Allocate` command

            Allocate a set of unallocated MCCS resources to a sub-array.
            The JSON argument specifies the overall sub-array composition in
            terms of which stations should be allocated to the specified Sub-Array.

            :param argin: JSON-formatted string
                {
                "interface": "https://schema.skao.int/ska-low-mccs-assignresources/1.0",
                "subarray_id": int,
                "subarray_beam_ids": list[int],
                "station_ids": list[list[int]],
                "channel_blocks": list[int],
                }

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            component_manager = self.target

            kwargs = json.loads(argin)
            subarray_id = kwargs.get("subarray_id")

            subarray_beam_ids = kwargs.get("subarray_beam_ids", list())
            subarray_beam_fqdns = [
                f"low-mccs/subarraybeam/{subarray_beam_id:02d}"
                for subarray_beam_id in subarray_beam_ids
            ]
            station_ids = kwargs.get("station_ids", list())

            station_fqdns = []
            for station_id_list in station_ids:
                station_fqdns.append(
                    [
                        f"low-mccs/station/{station_id:03d}"
                        for station_id in station_id_list
                    ]
                )

            channel_blocks = kwargs.get("channel_blocks", list())
            result_code = component_manager.allocate(
                subarray_id, station_fqdns, subarray_beam_fqdns, channel_blocks
            )

            if result_code == ResultCode.OK:
                return (ResultCode.OK, self.SUCCEEDED_MESSAGE)
            elif result_code == ResultCode.QUEUED:
                return (ResultCode.QUEUED, self.QUEUED_MESSAGE)
            else:
                return (ResultCode.FAILED, self.FAILED_MESSAGE)

    @command(dtype_in=int, dtype_out="DevVarLongStringArray")
    def RestartSubarray(self: MccsController, argin: int) -> DevVarLongStringArrayType:
        """
        Restart an MCCS subarray.

        :param argin: JSON-formatted string containing an integer subarray_id.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("RestartSubarray")
        (result_code, status) = handler(argin)
        return ([result_code], [status])

    class RestartSubarrayCommand(ResponseCommand):
        """Restart a subarray."""

        SUCCEEDED_MESSAGE = "Allocate command completed OK"
        QUEUED_MESSAGE = "Allocate command queued"
        FAILED_MESSAGE = "Allocate command failed"

        def do(  # type: ignore[override]
            self: MccsController.RestartSubarrayCommand, subarray_id: int
        ) -> tuple[ResultCode, str]:
            """
            Do hook for the :py:meth:`.MccsController.RestartSubarray` command.

            :param subarray_id: id of the subarray to be restarted

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            component_manager = self.target
            result_code = component_manager.restart_subarray(
                f"low-mcss/subarray/{subarray_id:02d}"
            )

            if result_code == ResultCode.OK:
                return (ResultCode.OK, self.SUCCEEDED_MESSAGE)
            elif result_code == ResultCode.QUEUED:
                return (ResultCode.QUEUED, self.QUEUED_MESSAGE)
            else:
                return (ResultCode.FAILED, self.FAILED_MESSAGE)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def Release(self: MccsController, argin: str) -> DevVarLongStringArrayType:
        """
        Release resources from an MCCS Sub-Array.

        :param argin: JSON-formatted string containing an integer
            subarray_id, a release all flag and array resources.
            {
            "interface": "https://schema.skao.int/ska-low-tmc-releaseresources/2.0",
            "subarray_id": 1,
            "release_all": true
            }

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("Release")
        (result_code, status) = handler(argin)
        return ([result_code], [status])

    class ReleaseCommand(ResponseCommand):
        """Release a subarray's resources."""

        REDUNDANT_MESSAGE = "Nothing to release"
        SUCCEEDED_MESSAGE = "Release command completed OK"
        QUEUED_MESSAGE = "Release command queued"
        FAILED_MESSAGE = "Release command failed"

        def do(  # type: ignore[override]
            self: MccsController.ReleaseCommand, argin: str
        ) -> tuple[ResultCode, str]:
            """
            Stateless do hook for the :py:meth:`.MccsController.Release` command.

            :param argin: JSON-formatted string containing an integer
                subarray_id, a release all flag.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            component_manager = self.target
            kwargs = json.loads(argin)
            if kwargs["release_all"]:
                subarray_id = kwargs["subarray_id"]
                result_code = component_manager.deallocate_all(subarray_id)
            else:
                return (
                    ResultCode.FAILED,
                    "Currently Release can only be used to release all resources from a subarray.",
                )

            if result_code is None:
                return (ResultCode.OK, self.REDUNDANT_MESSAGE)
            if result_code == ResultCode.OK:
                return (ResultCode.OK, self.SUCCEEDED_MESSAGE)
            if result_code == ResultCode.QUEUED:
                return (ResultCode.QUEUED, self.QUEUED_MESSAGE)
            return (ResultCode.FAILED, self.FAILED_MESSAGE)


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
    return MccsController.run_server(args=args or None, **kwargs)


if __name__ == "__main__":
    main()
