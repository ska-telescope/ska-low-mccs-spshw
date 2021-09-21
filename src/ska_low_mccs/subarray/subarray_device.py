# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""This module implements MCCS functionality for monitoring and control of subarrays."""

from __future__ import annotations  # allow forward references in type hints

import logging
from typing import Any, List, Optional, Tuple

import tango
from tango.server import attribute, command

from ska_tango_base.subarray import SKASubarray
from ska_tango_base.base.op_state_model import OpStateModel
from ska_tango_base.commands import (
    ObservationCommand,
    ResponseCommand,
    ResultCode,
    StateModelCommand,
)
from ska_tango_base.control_model import HealthState
from ska_tango_base.subarray.subarray_obs_state_model import SubarrayObsStateModel

from ska_low_mccs.component import CommunicationStatus
from ska_low_mccs.subarray import SubarrayComponentManager, SubarrayHealthModel
import ska_low_mccs.release as release


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
        super().init_device()

    def _init_state_model(self: MccsSubarray) -> None:
        super()._init_state_model()
        self._health_state = HealthState.UNKNOWN  # InitCommand.do() does this too late.
        self._health_model = SubarrayHealthModel(self.health_changed)
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
            self._component_communication_status_changed,
            self._message_queue_size_changed,
            self._assign_completed,
            self._release_completed,
            self._configure_completed,
            self._abort_completed,
            self._obsreset_completed,
            self._restart_completed,
            self._resources_changed,
            self._configured_changed,
            self._scanning_changed,
            self._obs_fault_occurred,
            self._health_model.station_health_changed,
            self._health_model.subarray_beam_health_changed,
        )

    def init_command_objects(self: MccsSubarray) -> None:
        """Initialise the command handlers for commands supported by this device."""
        super().init_command_objects()

        self.register_command_object(
            "SendTransientBuffer",
            self.SendTransientBufferCommand(
                self.component_manager,
                self.op_state_model,
                self.obs_state_model,
                self.logger,
            ),
        )

    class InitCommand(SKASubarray.InitCommand):
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
            (result_code, message) = super().do()

            device = self.target
            device.set_change_event("stationFQDNs", True, True)
            device.set_archive_event("stationFQDNs", True, True)

            device._build_state = release.get_release_info()
            device._version_id = release.version

            # The health model updates our health, but then the base class super().do()
            # overwrites it with OK, so we need to update this again.
            # TODO: This needs to be fixed in the base classes.
            device._health_state = device._health_model.health_state

            return (ResultCode.OK, "Init command started")

    # ----------
    # Callbacks
    # ----------
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

    def _message_queue_size_changed(
        self: MccsSubarray,
        size: int,
    ) -> None:
        """
        Handle change in component manager message queue size.

        :param size: the new size of the component manager's message
            queue
        """
        # TODO: This should push an event but the details have to wait for SP-1827
        self.logger.info(f"Message queue size is now {size}")

    def _assign_completed(
        self: MccsSubarray,
    ) -> None:
        """
        Handle completion of the assign command.

        This is a callback hook, called by the component manager when
        the assign command completes.
        """
        self.obs_state_model.perform_action("assign_completed")

    def _release_completed(
        self: MccsSubarray,
    ) -> None:
        """
        Handle completion of the release or release_all command.

        This is a callback hook, called by the component manager when
        the release or release_all command completes.
        """
        self.obs_state_model.perform_action("release_completed")

    def _configure_completed(
        self: MccsSubarray,
    ) -> None:
        """
        Handle completion of the configure command.

        This is a callback hook, called by the component manager when
        the configure command completes.
        """
        self.obs_state_model.perform_action("configure_completed")

    def _abort_completed(
        self: MccsSubarray,
    ) -> None:
        """
        Handle completion of the abort command.

        This is a callback hook, called by the component manager when
        the abort command completes.
        """
        self.obs_state_model.perform_action("abort_completed")

    def _obsreset_completed(
        self: MccsSubarray,
    ) -> None:
        """
        Handle completion of the obs_reset command.

        This is a callback hook, called by the component manager when
        the obs_reset command completes.
        """
        self.obs_state_model.perform_action("obsreset_completed")

    def _restart_completed(
        self: MccsSubarray,
    ) -> None:
        """
        Handle completion of the restart command.

        This is a callback hook, called by the component manager when
        the restart command completes.
        """
        self.obs_state_model.perform_action("restart_completed")

    def _resources_changed(
        self: MccsSubarray,
        station_fqdns: set[str],
        subarray_beam_fqdns: set[str],
    ) -> None:
        """
        Handle change in subarray resources.

        This is a callback hook, called by the component manager when
        the resources of the subarray changes.

        :param station_fqdns: the FQDNs of stations assigned to this
            subarray
        :param subarray_beam_fqdns: the FQDNs of subarray beams assigned
            to this subarray
        """
        if station_fqdns or subarray_beam_fqdns:
            self.obs_state_model.perform_action("component_resourced")
        else:
            self.obs_state_model.perform_action("component_unresourced")
        self._health_model.resources_changed(station_fqdns, subarray_beam_fqdns)

    def _configured_changed(
        self: MccsSubarray,
        is_configured: bool,
    ) -> None:
        """
        Handle change in whether the subarray is configured.

        This is a callback hook, called by the component manager when
        whether the subarray is configured changes.

        :param is_configured: whether the subarray is configured
        """
        if is_configured:
            self.obs_state_model.perform_action("component_configured")
        else:
            self.obs_state_model.perform_action("component_unconfigured")

    def _scanning_changed(
        self: MccsSubarray,
        is_scanning: bool,
    ) -> None:
        """
        Handle change in whether the subarray is scanning.

        This is a callback hook, called by the component manager when
        whether the subarray is scanning changes.

        :param is_scanning: whether the subarray is scanning
        """
        if is_scanning:
            self.obs_state_model.perform_action("component_scanning")
        else:
            self.obs_state_model.perform_action("component_not_scanning")

    def _obs_fault_occurred(
        self: MccsSubarray,
    ) -> None:
        """
        Handle occurrence of an observation fault.

        This is a callback hook, called by the component manager when an
        observation fault occurs.
        """
        self.obs_state_model.perform_action("component_obsfault")

    def health_changed(self: MccsSubarray, health: HealthState) -> None:
        """
        Handle the HealthModel's health state changes.

        Responsible for updating the tango side of things i.e. making sure the attribute
        is up to date, and events are pushed.

        :param health: the new health value
        """
        if self._health_state == health:
            return
        self._health_state = health
        self.push_change_event("healthState", health)

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

    @attribute(dtype=("str",), max_dim_x=100)
    def assignedResources(self: MccsSubarray) -> list[str]:
        """
        Return this subarray's assigned resources.

        :return: this subarray's assigned resources.
        """
        return sorted(self.component_manager.assigned_resources)

    # ------------------
    # Attribute methods
    # ------------------
    class AssignResourcesCommand(
        ObservationCommand, ResponseCommand, StateModelCommand
    ):
        """
        A class for MccsSubarray's AssignResources() command.

        Overrides SKASubarray.AssignResourcesCommand because that is a
        CompletionCommand, which is misimplemented and assumes
        synchronous completion.
        """

        RESULT_MESSAGES = {
            ResultCode.OK: "AssignResources command completed OK",
            ResultCode.QUEUED: "AssignResources command queued",
            ResultCode.FAILED: "AssignResources command failed",
        }

        def __init__(
            self: MccsSubarray.AssignResourcesCommand,
            target: Any,
            op_state_model: OpStateModel,
            obs_state_model: SubarrayObsStateModel,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new instance.

            :param target: the object that this command acts upon; for
                example, the device's component manager
            :param op_state_model: the op state model that this command
                uses to check that it is allowed to run
            :param obs_state_model: the observation state model that
                 this command uses to check that it is allowed to run,
                 and that it drives with actions.
            :param logger: the logger to be used by this Command. If not
                provided, then a default module logger will be used.
            """
            super().__init__(
                target, obs_state_model, "assign", op_state_model, logger=logger
            )

        def do(  # type: ignore[override]
            self: MccsSubarray.AssignResourcesCommand, argin: str
        ) -> tuple[ResultCode, str]:
            """
            Stateless hook for AssignResources() command functionality.

            :param argin: The resources to be assigned

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            component_manager = self.target
            result_code = component_manager.assign(argin)
            return (result_code, self.RESULT_MESSAGES[result_code])

    class ReleaseResourcesCommand(
        ObservationCommand, ResponseCommand, StateModelCommand
    ):
        """
        A class for MccsSubarray's ReleaseResources() command.

        Overrides SKASubarray.ReleaseResourcesCommand because that is a
        CompletionCommand, which is misimplemented and assumes
        synchronous completion.
        """

        RESULT_MESSAGES = {
            ResultCode.OK: "ReleaseResources command completed OK",
            ResultCode.QUEUED: "ReleaseResources command queued",
            ResultCode.FAILED: "ReleaseResources command failed",
        }

        def __init__(
            self: MccsSubarray.ReleaseResourcesCommand,
            target: Any,
            op_state_model: OpStateModel,
            obs_state_model: SubarrayObsStateModel,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new ReleaseResourcesCommand instance.

            :param target: the object that this command acts upon; for
                example, the device's component manager
            :param op_state_model: the op state model that this command
                uses to check that it is allowed to run
            :param obs_state_model: the observation state model that
                 this command uses to check that it is allowed to run,
                 and that it drives with actions.
            :param logger: the logger to be used by this Command. If not
                provided, then a default module logger will be used.
            """
            super().__init__(
                target, obs_state_model, "release", op_state_model, logger=logger
            )

        def do(  # type: ignore[override]
            self: MccsSubarray.ReleaseResourcesCommand, argin: str
        ) -> tuple[ResultCode, str]:
            """
            Stateless hook for ReleaseResources() command functionality.

            :param argin: The resources to be released

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            component_manager = self.target
            result_code = component_manager.release(argin)
            return (result_code, self.RESULT_MESSAGES[result_code])

    class ReleaseAllResourcesCommand(
        ObservationCommand, ResponseCommand, StateModelCommand
    ):
        """
        A class for MccsSubarray's ReleaseAllResources() command.

        Overrides SKASubarray.ReleaseAllResourcesCommand because that is
        a CompletionCommand, which is misimplemented and assumes
        synchronous completion.
        """

        RESULT_MESSAGES = {
            ResultCode.OK: "ReleaseAllResources command completed OK",
            ResultCode.QUEUED: "ReleaseAllResources command queued",
            ResultCode.FAILED: "ReleaseAllResources command failed",
        }

        def __init__(
            self: MccsSubarray.ReleaseAllResourcesCommand,
            target: Any,
            op_state_model: OpStateModel,
            obs_state_model: SubarrayObsStateModel,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new ReleaseAllResourcesCommand instance.

            :param target: the object that this command acts upon; for
                example, the device's component manager
            :param op_state_model: the op state model that this command
                uses to check that it is allowed to run
            :param obs_state_model: the observation state model that
                 this command uses to check that it is allowed to run,
                 and that it drives with actions.
            :param logger: the logger to be used by this Command. If not
                provided, then a default module logger will be used.
            """
            super().__init__(
                target, obs_state_model, "release", op_state_model, logger=logger
            )

        def do(  # type: ignore[override]
            self: MccsSubarray.ReleaseAllResourcesCommand,
        ) -> tuple[ResultCode, str]:
            """
            Stateless hook for ReleaseAllResources() command functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            component_manager = self.target
            result_code = component_manager.release_all()
            return (result_code, self.RESULT_MESSAGES[result_code])

    class ConfigureCommand(ObservationCommand, ResponseCommand, StateModelCommand):
        """
        Class for handling the Configure(argin) command.

        Overrides SKASubarray.ConfigureCommand because that is a
        CompletionCommand, which is misimplemented and assumes
        synchronous completion.
        """

        RESULT_MESSAGES = {
            ResultCode.OK: "Configure command completed OK",
            ResultCode.QUEUED: "Configure command queued",
            ResultCode.FAILED: "Configure command failed",
        }

        def __init__(
            self: MccsSubarray.ConfigureCommand,
            target: Any,
            op_state_model: OpStateModel,
            obs_state_model: SubarrayObsStateModel,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new ConfigureCommand instance.

            :param target: the object that this command acts upon; for
                example, the device's component manager
            :param op_state_model: the op state model that this command
                uses to check that it is allowed to run
            :param obs_state_model: the observation state model that
                 this command uses to check that it is allowed to run,
                 and that it drives with actions.
            :param logger: the logger to be used by this Command. If not
                provided, then a default module logger will be used.
            """
            super().__init__(
                target, obs_state_model, "configure", op_state_model, logger=logger
            )

        def do(  # type: ignore[override]
            self: MccsSubarray.ConfigureCommand, argin: dict
        ) -> tuple[ResultCode, str]:
            """
            Implement the functionality of the configure command.

            :py:meth:`ska_tango_base.subarray.subarray_device.SKASubarray.Configure` command for this
            :py:class:`.MccsSubarray` device.

            :param argin: JSON configuration specification
                {
                "interface": "https://schema.skao.int/ska-low-mccs-configure/2.0",
                "stations":[{"station_id": 1},{"station_id": 2}],
                "subarray_beams":[{
                "subarray_beam_id":1,
                "station_ids":[1,2],
                "update_rate": 0.0,
                "channels":  [[0, 8, 1, 1], [8, 8, 2, 1], [24, 16, 2, 1]],
                "sky_coordinates": [0.0, 180.0, 0.0, 45.0, 0.0],
                "antenna_weights": [1.0, 1.0, 1.0],
                "phase_centre": [0.0, 0.0]}]
                }

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            component_manager = self.target
            result_code = component_manager.configure(argin)
            return (result_code, self.RESULT_MESSAGES[result_code])

    class ScanCommand(SKASubarray.ScanCommand):
        """Class for handling the Scan(argin) command."""

        RESULT_MESSAGES = {
            ResultCode.OK: "Scan command started",  # Base classes return this
            ResultCode.STARTED: "Scan command started",
            ResultCode.FAILED: "Scan command failed",
        }

        def do(  # type: ignore[override]
            self: MccsSubarray.ScanCommand, argin: dict[str, Any]
        ) -> tuple[ResultCode, str]:
            """
            Implement the functionality of the scan command.

            :py:meth:`ska_tango_base.subarray.subarray_device.SKASubarray.Scan`
            command for this :py:class:`.MccsSubarray` device.

            :param argin: dict
                {
                "interface": "https://schema.skao.int/ska-low-mccs-scan/2.0",
                "scan_id":1,
                "start_time": 0.0,
                }

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            scan_id = argin["scan_id"]
            start_time = argin["start_time"]

            component_manager = self.target
            result_code = component_manager.scan(scan_id, start_time)
            return (result_code, self.RESULT_MESSAGES[result_code])

    class EndScanCommand(SKASubarray.EndScanCommand):
        """Class for handling the EndScan() command."""

        RESULT_MESSAGES = {
            ResultCode.OK: "End Scan command completed OK",
            ResultCode.FAILED: "Scan command failed",
        }

        def do(  # type: ignore[override]
            self: MccsSubarray.EndScanCommand,
        ) -> tuple[ResultCode, str]:
            """
            Implement the functionality of EndScanCommand.

            :py:meth:`ska_tango_base.subarray.subarray_device.SKASubarray.EndScan` command for this
            :py:class:`.MccsSubarray` device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            component_manager = self.target
            result_code = component_manager.end_scan()
            return (result_code, self.RESULT_MESSAGES[result_code])

    class EndCommand(SKASubarray.EndCommand):
        """Class for handling the End() command."""

        RESULT_MESSAGES = {
            ResultCode.OK: "End command started",
            ResultCode.FAILED: "End command failed",
        }

        def do(  # type: ignore[override]
            self: MccsSubarray.EndCommand,
        ) -> tuple[ResultCode, str]:
            """
            Implement the functionality of the end command.

            :py:meth:`ska_tango_base.subarray.subarray_device.SKASubarray.End` command for this
            :py:class:`.MccsSubarray` device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            component_manager = self.target
            result_code = component_manager.deconfigure()
            return (result_code, self.RESULT_MESSAGES[result_code])

    class AbortCommand(SKASubarray.AbortCommand):
        """Class for handling the Abort() command."""

        RESULT_MESSAGES = {
            ResultCode.OK: "Scan command started",  # Base classes return this
            ResultCode.FAILED: "Scan command failed",
        }

        def do(  # type: ignore[override]
            self: MccsSubarray.AbortCommand,
        ) -> tuple[ResultCode, str]:
            """
            Implement the functionality of the AbortCommand.

            :py:meth:`ska_tango_base.subarray.subarray_device.SKASubarray.Abort` command for this
            :py:class:`.MccsSubarray` device.

            An abort command will leave the system in an ABORTED state.
            Output to CSP is stopped, as is the beamformer and all running
            jobs. The system can then be inspected in the ABORTED state
            before it's de-configured and returned to the IDLE state by the
            ObsReset command.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            component_manager = self.target
            result_code = component_manager.abort()
            return (result_code, self.RESULT_MESSAGES[result_code])

    class ObsResetCommand(SKASubarray.ObsResetCommand):
        """Class for handling the ObsReset() command."""

        RESULT_MESSAGES = {
            ResultCode.OK: "ObsReset command completed OK",
            ResultCode.FAILED: "ObsReset command failed",
        }

        def do(  # type: ignore[override]
            self: MccsSubarray.ObsResetCommand,
        ) -> tuple[ResultCode, str]:
            """
            Implement the functionality of the ObsResetCommand.

            :py:meth:`ska_tango_base.subarray.subarray_device.SKASubarray.ObsReset` command for this
            :py:class:`.MccsSubarray` device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            component_manager = self.target
            result_code = component_manager.obs_reset()
            return (result_code, self.RESULT_MESSAGES[result_code])

    class RestartCommand(SKASubarray.RestartCommand):
        """Class for handling the Restart() command."""

        RESULT_MESSAGES = {
            ResultCode.OK: "RestartCommand command completed OK",
            ResultCode.FAILED: "RestartCommand command failed",
        }

        def do(  # type: ignore[override]
            self: MccsSubarray.RestartCommand,
        ) -> tuple[ResultCode, str]:
            """
            Implement the functionality of the RestartComand.

            :py:meth:`ska_tango_base.subarray.subarray_device.SKASubarray.Restart` command for this
            :py:class:`.MccsSubarray` device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            component_manager = self.target
            result_code = component_manager.obs_reset()
            return (result_code, self.RESULT_MESSAGES[result_code])

    class SendTransientBufferCommand(ResponseCommand):
        """Class for handling the SendTransientBuffer(argin) command."""

        RESULT_MESSAGES = {
            ResultCode.OK: "SendTransientBuffer command completed OK",
            ResultCode.QUEUED: "SendTransientBuffer command queued",
            ResultCode.FAILED: "SendTransientBuffer command failed",
        }

        def do(  # type: ignore[override]
            self: MccsSubarray.SendTransientBufferCommand, argin: list[int]
        ) -> tuple[ResultCode, str]:
            """
            Implement the SendTransientBuffer command.

            :param argin: specification of the segment of the transient
                buffer to send, comprising:
                1. Start time (timestamp: milliseconds since UNIX epoch)
                2. End time (timestamp: milliseconds since UNIX epoch)
                3. Dispersion measure
                Together, these parameters narrow the selection of
                transient buffer data to the period of time and
                frequencies that are of interest.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            component_manager = self.target
            result_code = component_manager.send_transient_buffer()
            return (result_code, self.RESULT_MESSAGES[result_code])

    @command(dtype_in="DevVarLongArray", dtype_out="DevVarLongStringArray")
    def SendTransientBuffer(
        self: MccsSubarray, argin: list[int]
    ) -> DevVarLongStringArrayType:
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
    return MccsSubarray.run_server(args=args or None, **kwargs)


if __name__ == "__main__":
    main()
