# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the SKA Low MCCS Controller device prototype."""

from __future__ import annotations  # allow forward references in type hints

import json
import time
from typing import List, Optional, Tuple

import tango
from ska_tango_base.base import SKABaseDevice
from ska_tango_base.commands import ResponseCommand, ResultCode
from ska_tango_base.control_model import HealthState, PowerState
from tango.server import command, device_property

import ska_low_mccs.release as release
from ska_low_mccs import MccsDeviceProxy
from ska_low_mccs.component import CommunicationStatus
from ska_low_mccs.controller import ControllerComponentManager, ControllerHealthModel

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

    def create_component_manager(
        self: MccsController,
    ) -> ControllerComponentManager:
        """
        Create and return a component manager for this device.

        :return: a component manager for this device.
        """
        self._communication_status: Optional[CommunicationStatus] = None
        self._component_power_mode: Optional[PowerState] = None

        return ControllerComponentManager(
            self.MccsSubarrays,
            self.MccsSubracks,
            self.MccsStations,
            self.MccsSubarrayBeams,
            self.MccsStationBeams,
            self.logger,
            self.push_change_event,
            self._communication_status_changed,
            self._component_power_mode_changed,
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
            self.OnCommand(self, self.op_state_model, self.logger),
        )
        self.register_command_object(
            "Off",
            self.OffCommand(self, self.op_state_model, self.logger),
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

            return (result_code, message)

    class OnCommand(SKABaseDevice.OnCommand):
        """A class for the MccsController's On() command."""

        def do(  # type: ignore[override]
            self: MccsController.OnCommand,
        ) -> tuple[ResultCode, str]:
            """
            Stateless hook for On() command functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            result_code = self.target.component_manager.on()
            if result_code == ResultCode.FAILED:
                return (
                    ResultCode.FAILED,
                    "Controller failed to initiate On command",
                )

            def wait_until_on(
                device: MccsDeviceProxy, timeout: float, period: float = 0.5
            ) -> tuple[ResultCode, str]:
                """
                Wait until the device is on.

                :param device: the device to wait for
                :param timeout: the time we are prepared to wait for the device to become ON
                :param period: the polling period in seconds

                :return: a return code and a string message indicating status.
                    The message is for information purpose only.
                """
                elapsed_time = 0.0
                while elapsed_time <= timeout:
                    if device.get_state() == tango.DevState.ON:
                        message = "Controller On command completed OK"
                        return (ResultCode.OK, message)
                    time.sleep(period)
                    elapsed_time += period
                message = (
                    f"Controller On command didn't complete within {timeout} seconds"
                )
                return (ResultCode.FAILED, message)

            # Wait for conditions on component manager to unblock
            result_code, message = wait_until_on(self.target, timeout=30.0)
            self.target.logger.info(message)
            return (result_code, message)

    class OffCommand(SKABaseDevice.OffCommand):
        """A class for the MccsController's Off() command."""

        def do(  # type: ignore[override]
            self: MccsController.OffCommand,
        ) -> tuple[ResultCode, str]:
            """
            Stateless hook for Off() command functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            result_code = self.target.component_manager.off()
            if result_code == ResultCode.FAILED:
                return (
                    ResultCode.FAILED,
                    "Controller failed to initiate Off command",
                )

            def wait_until_off(
                device: MccsDeviceProxy, timeout: float, period: float = 0.5
            ) -> tuple[ResultCode, str]:
                """
                Wait until the device is off.

                :param device: the device to wait for
                :param timeout: the time we are prepared to wait for the device to become OFF
                :param period: the polling period in seconds

                :return: a return code and a string message indicating status.
                    The message is for information purpose only.
                """
                elapsed_time = 0.0
                while elapsed_time <= timeout:
                    if device.get_state() == tango.DevState.OFF:
                        message = "Controller Off command completed OK"
                        return (ResultCode.OK, message)
                    time.sleep(period)
                    elapsed_time += period
                message = (
                    f"Controller Off command didn't complete within {timeout} seconds"
                )
                return (ResultCode.FAILED, message)

            # Wait for conditions on component manager to unblock
            result_code, message = wait_until_off(self.target, timeout=10.0)
            self.target.logger.info(message)
            return (result_code, message)

    # ----------
    # Callbacks
    # ----------
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
        # TODO: This method and the next are implemented to work around
        # the following issue:
        # * The controller component manager's communication status
        #   depends on the status of communication with all subservient
        #   devices.
        # * But at present its power mode depends only on the power mode
        #   of subracks and stations.
        # Once communication with the subrack and stations is
        # established, these start reporting power mode, and if they all
        # report their power mode before communications with all other
        # devices is established, then the component manager ends up
        # publishing a power mode change *before* is has announced that
        # comms is established. This leads to problems.
        # Eventually we should figure out a more elegant way to handle
        # this.
        self._communication_status = communication_status

        if communication_status == CommunicationStatus.DISABLED:
            self.op_state_model.perform_action("component_disconnected")
        elif communication_status == CommunicationStatus.NOT_ESTABLISHED:
            self.op_state_model.perform_action("component_unknown")
        elif self._component_power_mode == PowerState.OFF:
            self.op_state_model.perform_action("component_off")
        elif self._component_power_mode == PowerState.STANDBY:
            self.op_state_model.perform_action("component_standby")
        elif self._component_power_mode == PowerState.ON:
            self.op_state_model.perform_action("component_on")
        elif self._component_power_mode == PowerState.UNKNOWN:
            self.op_state_model.perform_action("component_unknown")
        else:  # self._component_power_mode is None
            pass  # wait for a power mode update

        self._health_model.is_communicating(
            communication_status == CommunicationStatus.ESTABLISHED
        )

    def _component_power_mode_changed(
        self: MccsController,
        power_mode: PowerState,
    ) -> None:
        """
        Handle change in the power mode of the component.

        This is a callback hook, called by the component manager when
        the power mode of the component changes. It is implemented here
        to drive the op_state.

        :param power_mode: the power mode of the component.
        """
        self._component_power_mode = power_mode

        if self._communication_status == CommunicationStatus.ESTABLISHED:
            action_map = {
                PowerState.OFF: "component_off",
                PowerState.STANDBY: "component_standby",
                PowerState.ON: "component_on",
                PowerState.UNKNOWN: "component_unknown",
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

        SUCCEEDED_MESSAGE = "Restart subarray command completed OK"
        QUEUED_MESSAGE = "Restart subarray command queued"
        FAILED_MESSAGE = "Restart subarray command failed"

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
