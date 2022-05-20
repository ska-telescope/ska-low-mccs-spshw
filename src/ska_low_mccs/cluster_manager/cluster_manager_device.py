# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
LFAA Cluster Manager Device Server.

An implementation of the Cluster Manager Device Server for the MCCS
based upon architecture in SKA-TEL-LFAA-06000052-02.
"""

from __future__ import annotations  # allow forward references in type hints

import logging
import json
from typing import Any, List, Optional, Tuple

import tango
from ska_tango_base.base import SKABaseDevice
from ska_tango_base.commands import FastCommand, ResultCode, SubmittedSlowCommand
from ska_tango_base.control_model import (
    CommunicationStatus,
    HealthState,
    PowerState,
    SimulationMode,
)
from tango import DevState
from tango.server import attribute, command

import ska_low_mccs.release as release
from ska_low_mccs.cluster_manager import ClusterComponentManager, ClusterHealthModel
from ska_low_mccs.cluster_manager.cluster_simulator import JobConfig, JobStatus

__all__ = ["MccsClusterManagerDevice", "main"]

DevVarLongStringArrayType = Tuple[List[ResultCode], List[Optional[str]]]


class MccsClusterManagerDevice(SKABaseDevice):
    """An implementation of a cluster manager Tango device server for MCCS."""

    # ---------------
    # General methods
    # ---------------
    def init_device(self: MccsClusterManagerDevice) -> None:
        """
        Initialise the device.

        This is overridden here to change the Tango serialisation model.
        """
        util = tango.Util.instance()
        util.set_serial_model(tango.SerialModel.NO_SYNC)
        self._max_workers = 1
        super().init_device()

    def _init_state_model(self: MccsClusterManagerDevice) -> None:
        """Initialise the state model."""
        super()._init_state_model()
        self._health_state: Optional[
            HealthState
        ] = None  # SKABaseDevice.InitCommand.do() does this too late.
        self._health_model = ClusterHealthModel(self._component_state_changed_callback)
        self.set_change_event("healthState", True, False)

    def create_component_manager(
        self: MccsClusterManagerDevice,
    ) -> ClusterComponentManager:
        """
        Create and return a component manager for this device.

        :return: a component manager for this device.
        """
        # TODO: the default value for simulationMode should be
        # FALSE, but we don't have real hardware to test yet, so we
        # can't take our devices out of simulation mode. Once we
        # have a driver for real hardware, we should change this
        # default to FALSE.
        return ClusterComponentManager(
            self.logger,
            self._max_workers,
            SimulationMode.TRUE,
            self._communication_state_changed_callback,
            self._component_state_changed_callback,
        )

    def init_command_objects(self: MccsClusterManagerDevice) -> None:
        """Set up the command handler object for this device's commands."""
        super().init_command_objects()

        for (command_name, method_name) in [
            ("StartJob", "start_job"),
            ("StopJob", "stop_job"),
            # ("SubmitJob", "submit_job"),
            # ("GetJobStatus", "get_job_status"),
            ("ClearJobStats", "clear_job_stats"),
            ("PingMasterPool", "ping_master_pool"),
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

        for (command_name, command_object) in [
            ("SubmitJob", self.SubmitJobCommand),
            ("GetJobStatus", self.GetJobStatusCommand),
        ]:
            self.register_command_object(
                command_name,
                command_object(self.component_manager, self.logger),
            )

    class InitCommand(SKABaseDevice.InitCommand):
        """Class that implements device initialisation for this device."""

        def do(  # type: ignore[override]
            self: MccsClusterManagerDevice.InitCommand,
        ) -> tuple[ResultCode, str]:
            """
            Execute the Init Command.

            Stateless hook for device initialisation: initialises the attributes and
            properties of the :py:class:`.MccsClusterManagerDevice`.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            self._device._build_state = release.get_release_info()
            self._device._version_id = release.version

            return (ResultCode.OK, "Init command completed OK")

    # --------------
    # Callback hooks
    # --------------
    def _communication_state_changed_callback(
        self: MccsClusterManagerDevice,
        communication_state: CommunicationStatus,
    ) -> None:
        """
        Handle change in communications status between component manager and component.

        This is a callback hook, called by the component manager when
        the communications status changes. It is implemented here to
        drive the op_state.

        :param communication_state: the status of communications
            between the component manager and its component.
        """
        action_map = {
            CommunicationStatus.DISABLED: "component_disconnected",
            CommunicationStatus.NOT_ESTABLISHED: "component_unknown",
            CommunicationStatus.ESTABLISHED: None,  # wait for a power mode update
        }

        action = action_map[communication_state]
        if action is not None:
            self.op_state_model.perform_action(action)

        self._health_model.is_communicating(
            communication_state == CommunicationStatus.ESTABLISHED
        )

    def _component_state_changed_callback(
        self: MccsClusterManagerDevice, state_change: dict[str, Any]
    ) -> None:
        """
        Handle change in the state of the component.

        This is a callback hook, called by the component manager when
        the state of the component changes.

        :param state_change: dictionary of state change parameters.
        """
        action_map = {
            PowerState.OFF: "component_off",
            PowerState.STANDBY: "component_standby",
            PowerState.ON: "component_on",
            PowerState.UNKNOWN: "component_unknown",
        }
        if "power_state" in state_change.keys():
            power_state = state_change.get("power_state")
            self.op_state_model.perform_action(action_map[power_state])

        if "fault" in state_change.keys():
            is_fault = state_change.get("fault")
            if is_fault:
                self.op_state_model.perform_action("component_fault")
                self._health_model.component_fault(True)
            else:
                power_mode = self.component_manager.power_mode
                if power_mode is not None:
                    self._component_power_mode_changed(
                        self.component_manager.power_mode
                    )
                self._health_model.component_fault(False)

        if "health_state" in state_change.keys():
            health = state_change.get("health_state")
            if self._health_state != health:
                self._health_state = health
                self.push_change_event("healthState", health)

        if "shadow_master_pool_node_healths" in state_change.keys():
            healths = state_change.get("shadow_master_pool_node_healths")
            self._health_model.shadow_master_pool_node_health_changed(healths)

    # ----------
    # Attributes
    # ----------
    @attribute(
        dtype=SimulationMode,
        memorized=True,
        hw_memorized=True,
    )
    def simulationMode(self: MccsClusterManagerDevice) -> SimulationMode:
        """
        Report the simulation mode of the device.

        :return: Return the current simulation mode
        """
        return self.component_manager.simulation_mode

    @simulationMode.write  # type: ignore[no-redef]
    def simulationMode(self: MccsClusterManagerDevice, value: SimulationMode) -> None:
        """
        Set the simulation mode.

        :param value: The simulation mode, as a SimulationMode value
        """
        self.component_manager.simulation_mode = value

    @attribute(dtype="DevShort", label="jobsErrored")
    def jobsErrored(self: MccsClusterManagerDevice) -> int:
        """
        Return the number of errored jobs.

        :return: the number of errored jobs
        """
        return self.component_manager.jobs_errored

    @attribute(dtype="DevShort", label="jobsFailed", max_alarm=1)
    def jobsFailed(self: MccsClusterManagerDevice) -> int:
        """
        Return the number of failed jobs.

        :return: the number of failed jobs
        """
        return self.component_manager.jobs_failed

    @attribute(dtype="DevShort", label="jobsFinished")
    def jobsFinished(self: MccsClusterManagerDevice) -> int:
        """
        Return the number of finished jobs.

        :return: the number of finished jobs
        """
        return self.component_manager.jobs_finished

    @attribute(dtype="DevShort", label="jobsKilled")
    def jobsKilled(self: MccsClusterManagerDevice) -> int:
        """
        Return the number of killed jobs.

        :return: the number of killed jobs
        """
        return self.component_manager.jobs_killed

    @attribute(dtype="DevShort", label="jobsKilling")
    def jobsKilling(self: MccsClusterManagerDevice) -> int:
        """
        Return the number of jobs currently being killed.

        :return: the number of jobs currently being killed
        """
        return self.component_manager.jobs_killing

    @attribute(dtype="DevShort", label="jobsLost")
    def jobsLost(self: MccsClusterManagerDevice) -> int:
        """
        Return the number of lost jobs.

        :return: the number of lost jobs
        """
        return self.component_manager.jobs_lost

    @attribute(dtype="DevShort", label="jobsRunning")
    def jobsRunning(self: MccsClusterManagerDevice) -> int:
        """
        Return the number of running jobs.

        :return: the number of running jobs
        """
        return self.component_manager.jobs_running

    @attribute(dtype="DevShort", label="jobsStaging")
    def jobsStaging(self: MccsClusterManagerDevice) -> int:
        """
        Return the number of staging jobs.

        :return: the number of staging jobs
        """
        return self.component_manager.jobs_staging

    @attribute(dtype="DevShort", label="jobsStarting")
    def jobsStarting(self: MccsClusterManagerDevice) -> int:
        """
        Return the number of starting jobs.

        :return: the number of starting jobs
        """
        return self.component_manager.jobs_starting

    @attribute(dtype="DevShort", max_alarm=1)
    def jobsUnreachable(self: MccsClusterManagerDevice) -> int:
        """
        Return the number of unreachable jobs.

        :return: the number of unreachable jobs
        """
        return self.component_manager.jobs_unreachable

    @attribute(dtype="DevFloat", label="memoryTotal")
    def memoryTotal(self: MccsClusterManagerDevice) -> float:
        """
        Return the total memory size.

        :return: the total memory size
        """
        return self.component_manager.memory_total

    @attribute(dtype="DevFloat", label="memoryAvail")
    def memoryAvail(self: MccsClusterManagerDevice) -> float:
        """
        Return the available memory.

        :return: the available memory
        """
        return self.component_manager.memory_avail

    @attribute(dtype="DevFloat", label="memoryUsed")
    def memoryUsed(self: MccsClusterManagerDevice) -> float:
        """
        Return the amount of memory in use.

        :return: the amount of memory in use
        """
        return self.component_manager.memory_used

    @attribute(dtype="DevShort", label="nodesInUse")
    def nodesInUse(self: MccsClusterManagerDevice) -> int:
        """
        Return the number of nodes in use.

        :return: the number of nodes in use
        """
        return self.component_manager.nodes_in_use

    @attribute(dtype="DevShort", label="nodesAvail")
    def nodesAvail(self: MccsClusterManagerDevice) -> int:
        """
        Return the number of available nodes.

        :return: the number of available nodes
        """
        return self.component_manager.nodes_avail

    @attribute(dtype="DevShort", label="nodesTotal")
    def nodesTotal(self: MccsClusterManagerDevice) -> int:
        """
        Return the total number of nodes.

        :return: the total number of notes
        """
        return self.component_manager.nodes_total

    @attribute(dtype="DevShort", label="masterNodeId")
    def masterNodeId(self: MccsClusterManagerDevice) -> int:
        """
        Return the id of the master node.

        :return: the id of the master node
        """
        return self.component_manager.master_node_id

    @attribute(dtype="DevFloat", label="masterCpusAllocatedPercent")
    def masterCpusAllocatedPercent(self: MccsClusterManagerDevice) -> float:
        """
        Return the percent allocation of the CPUs.

        :return: the percent allocation of the CPUs
        """
        return self.component_manager.master_cpus_allocated_percent

    @attribute(dtype="DevShort", label="masterCpusUsed")
    def masterCpusUsed(self: MccsClusterManagerDevice) -> int:
        """
        Return the number of CPUs in use on the master node.

        :return: the number of CPUs in use on the master node
        """
        return self.component_manager.master_cpus_used

    @attribute(dtype="DevShort", label="masterCpusTotal")
    def masterCpusTotal(self: MccsClusterManagerDevice) -> int:
        """
        Return the number of CPUs that the master node has.

        :return: the number of CPUs that the master node has
        """
        return self.component_manager.master_cpus_total

    @attribute(dtype="DevFloat", label="masterDiskPercent")
    def masterDiskPercent(self: MccsClusterManagerDevice) -> float:
        """
        Return the proportion of the master node disk that has been used.

        :return: the proportion of the master node disk that has been
            used, as a percentage
        """
        return self.component_manager.master_disk_percent

    @attribute(dtype="DevDouble", label="masterDiskUsed")
    def masterDiskUsed(self: MccsClusterManagerDevice) -> float:
        """
        Return the amount of the master node disk that has been used.

        :return: the amount of the master node disk that has been
            used
        """
        return self.component_manager.master_disk_used

    @attribute(dtype="DevFloat", label="masterDiskTotal")
    def masterDiskTotal(self: MccsClusterManagerDevice) -> float:
        """
        Return the total disk size on the master node.

        :return: the total disk size on the master node
        """
        return self.component_manager.master_disk_total

    @attribute(dtype="DevFloat", label="masterMemPercent")
    def masterMemPercent(self: MccsClusterManagerDevice) -> float:
        """
        Return the proportion of memory that has been used on the master node.

        :return:  the proportion of memory that has been used on the
            master node
        """
        return self.component_manager.master_mem_percent

    @attribute(dtype="DevFloat", label="masterMemPercent")
    def masterMemUsed(self: MccsClusterManagerDevice) -> float:
        """
        Return the amount of memory that has been used on the master node.

        :return:  the amount of memory that has been used on the master
            node
        """
        return self.component_manager.master_mem_used

    @attribute(dtype="DevFloat", label="masterMemTotal")
    def masterMemTotal(self: MccsClusterManagerDevice) -> float:
        """
        Return the total amount of memory on the master node.

        :return:  the total amount of memory on the master node
        """
        return self.component_manager.master_mem_total

    @attribute(dtype=("DevShort",), max_dim_x=100, label="shadowMasterPoolNodeIds")
    def shadowMasterPoolNodeIds(self: MccsClusterManagerDevice) -> list[int]:
        """
        Return the ids of nodes in the shadow master pool.

        :return: the ids of nodes in the shadow master pool
        """
        return self.component_manager.shadow_master_pool_node_ids

    @attribute(dtype=("DevState",), max_dim_x=100, label="shadowMasterPoolStatus")
    def shadowMasterPoolStatus(
        self: MccsClusterManagerDevice,
    ) -> list[DevState]:
        """
        Return the states of nodes in the shadow master pool.

        :return: the states of nodes in the shadow master pool
        """
        return self.component_manager.shadow_master_pool_status

    # --------
    # Commands
    # --------

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def StartJob(
        self: MccsClusterManagerDevice, argin: str
    ) -> DevVarLongStringArrayType:
        """
        Command to start a particular job.

        :param argin: the job id

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("StartJob")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def StopJob(
        self: MccsClusterManagerDevice, argin: str
    ) -> DevVarLongStringArrayType:
        """
        Command to stop a particular job.

        :param argin: the job id

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("StopJob")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    # @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    # def SubmitJob(
    #     self: MccsClusterManagerDevice, argin: str
    # ) -> DevVarLongStringArrayType:
    #     """
    #     Command to submit a job to the queue.

    #     :param argin: the job configuration, encoded as a JSON string

    #     :return: the job id of the submitted job
    #     """
    #     handler = self.get_command_object("SubmitJob")
    #     (return_code, message) = handler(argin)
    #     return ([return_code], [message])

    class SubmitJobCommand(FastCommand):
        """Class for handling the SubmitJob(argin) command."""

        def __init__(
            self: MccsClusterManagerDevice.SubmitJobCommand,
            component_manager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new SubmitJobCommand instance.

            :param component_manager: The component manager to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        def do(  # type: ignore[override]
            self: MccsClusterManagerDevice.SubmitJobCommand, argin: str
        ) -> tuple[ResultCode, str]:
            """
            Run the user-specified functionality of this command.

            :param argin: a JSON string specifying the job configuration

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            kwargs = json.loads(argin)
            job_config = JobConfig(**kwargs)

            component_manager = self._component_manager
            return component_manager.submit_job(job_config)

    @command(dtype_in="DevString", dtype_out="DevString")
    def SubmitJob(self: MccsClusterManagerDevice, argin: str) -> str:
        """
        Command to submit a job to the queue.

        :param argin: the job configuration, encoded as a JSON string

        :return: the job id of the submitted job
        """
        handler = self.get_command_object("SubmitJob")
        return handler(argin)


    class GetJobStatusCommand(FastCommand):
        """Class for handling GetJobStatus() command."""

        def __init__(
            self: MccsClusterManagerDevice.GetJobStatusCommand,
            component_manager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new GetJobStatusCommand instance.

            :param component_manager: The component manager to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        def do(  # type: ignore[override]
            self: MccsClusterManagerDevice.GetJobStatusCommand,
            argin: str,
        ) -> JobStatus:
            """
            Run the user-specified functionality of this command.

            :param argin: the job id

            :return: The status of the job
            """
            component_manager = self._component_manager
            try:
                return component_manager.get_job_status(argin)
            except ValueError:
                return JobStatus.UNKNOWN

    @command(dtype_in="DevString", dtype_out="DevShort")
    def GetJobStatus(self: MccsClusterManagerDevice, argin: str) -> int:
        """
        Poll the current status for a job.

        :param argin: the job id

        :return: the job status.
        """
        handler = self.get_command_object("GetJobStatus")
        return handler(argin)

    @command(dtype_out="DevVarLongStringArray")
    def ClearJobStats(
        self: MccsClusterManagerDevice,
    ) -> DevVarLongStringArrayType:
        """
        Reset all job counters.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("ClearJobStats")
        (return_code, message) = handler()
        return ([return_code], [message])

    @command(dtype_out="DevVarLongStringArray")
    def PingMasterPool(
        self: MccsClusterManagerDevice,
    ) -> DevVarLongStringArrayType:
        """
        Pings all nodes in shadow master pool, to maintain status of each.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("PingMasterPool")
        (return_code, message) = handler()
        return ([return_code], [message])


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
    return MccsClusterManagerDevice.run_server(args=args or None, **kwargs)


if __name__ == "__main__":
    main()
