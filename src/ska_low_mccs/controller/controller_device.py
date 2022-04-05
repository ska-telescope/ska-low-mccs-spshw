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
import threading
import time
from typing import List, Optional, Tuple

import tango
from ska_tango_base.base import SKABaseDevice
from ska_tango_base.commands import (
    DeviceInitCommand,
    FastCommand,
    ResultCode,
    SubmittedSlowCommand,
)
from ska_tango_base.control_model import CommunicationStatus, HealthState, PowerState
from tango.server import command, device_property

import ska_low_mccs.release as release
from ska_low_mccs import MccsDeviceProxy
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
        self._max_workers = 1
        self._power_state_lock = threading.RLock()
        self._communication_status: Optional[CommunicationStatus] = None
        self._component_power_state: Optional[PowerState] = None
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
            self._component_state_changed_callback,
        )
        self.set_change_event("healthState", True, False)

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
            self._max_workers,
            self._communication_status_changed_callback,
            self._component_state_changed_callback,
        )

    def init_command_objects(self: MccsController) -> None:
        """Set up the handler objects for Commands."""
        super().init_command_objects()

        for (command_name, method_name) in [
            ("Allocate", "allocate"),
            ("Release", "release"),
            ("RestartSubarray", "restart_subarray"),
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
            self._device._build_state = release.get_release_info()
            self._device._version_id = release.version

            return (ResultCode.OK, "Initialisation complete")

    # ----------
    # Callbacks
    # ----------
    def _communication_status_changed_callback(
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
        elif self._component_power_state == PowerState.OFF:
            self.op_state_model.perform_action("component_off")
        elif self._component_power_state == PowerState.STANDBY:
            self.op_state_model.perform_action("component_standby")
        elif self._component_power_state == PowerState.ON:
            self.op_state_model.perform_action("component_on")
        elif self._component_power_state == PowerState.UNKNOWN:
            self.op_state_model.perform_action("component_unknown")
        else:  # self._component_power_state is None
            pass  # wait for a power mode update

        self._health_model.is_communicating(
            communication_status == CommunicationStatus.ESTABLISHED
        )

    def _component_state_changed_callback(
        self: MccsController,
        state_change: dict[str, Any],
    ) -> None:
        """
        Handle change in the state of the component.

        This is a callback hook, called by the component manager when
        the state of the component changes.

        :param state_change: the state of the component.
        """
        action_map = {
            PowerState.OFF: "component_off",
            PowerState.STANDBY: "component_standby",
            PowerState.ON: "component_on",
            PowerState.UNKNOWN: "component_unknown",
        }
        with self._power_state_lock:
            if "power_state" in state_change.keys():
                power_state = state_change.get("power_state")
                self.component_manager.power_state = power_state

        if self._communication_status == CommunicationStatus.ESTABLISHED:
            self.op_state_model.perform_action(action_map[power_state])

        if "health_state" in state_change.keys():
            health = state_change.get("health_state")
            if self._health_state != health:
                self._health_state = health
                self.push_change_event("healthState", health)

        if "fault" in state_change.keys():
            is_fault = state_change.get("fault")
            if is_fault:
                self.op_state_model.perform_action("component_fault")
                self._health_model.component_fault(True)
            else:
                self.op_state_model.perform_action(
                    action_map[self.component_manager.power_state]
                )
                self._health_model.component_fault(False)

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
        message = f"Controller On command didn't complete within {timeout} seconds"
        return (ResultCode.FAILED, message)

        # Wait for conditions on component manager to unblock
        result_code, message = wait_until_on(self.target, timeout=30.0)
        self.target.logger.info(message)
        return (result_code, message)

    # ----------
    # Attributes
    # ----------

    # --------
    # Commands
    # --------
    @command(dtype_out="DevVarLongStringArray")
    def StandbyFull(self: MccsController) -> DevVarLongStringArrayType:
        """
        Put MCCS into standby mode.

        Some elements of SKA Mid have both low and full standby
        modes, but SKA Low has no such elements. We just need a
        Standby command, not separate StandbyLow and StandbyFull.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("Standby")
        (result_code, status) = handler()
        return ([result_code], [status])

    @command(dtype_out="DevVarLongStringArray")
    def StandbyLow(self: MccsController) -> DevVarLongStringArrayType:
        """
        Put MCCS into standby mode.

        Some elements of SKA Mid have both low and full standby
        modes, but SKA Low has no such elements. We just need a
        Standby command, not separate StandbyLow and StandbyFull.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("Standby")
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

    @command(dtype_in=int, dtype_out="DevVarLongStringArray")
    def RestartSubarray(self: MccsController, argin: int) -> DevVarLongStringArrayType:
        """
        Restart an MCCS subarray.

        :param argin: an integer subarray_id.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("RestartSubarray")
        (result_code, status) = handler(argin)
        return ([result_code], [status])

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
