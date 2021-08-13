# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""
LFAA Cluster Manager Device Server.

An implementation of the Cluster Manager Device Server for the MCCS
based upon architecture in SKA-TEL-LFAA-06000052-02.
"""

from __future__ import annotations  # allow forward references in type hints

import json
from typing import List, Optional, Tuple

import tango
from tango import DevState
from tango.server import attribute, command

from ska_tango_base.base import SKABaseDevice
from ska_tango_base.commands import BaseCommand, ResponseCommand, ResultCode
from ska_tango_base.control_model import HealthState, PowerMode, SimulationMode

from ska_low_mccs.cluster_manager import ClusterComponentManager, ClusterHealthModel
from ska_low_mccs.cluster_manager.cluster_simulator import JobStatus, JobConfig
from ska_low_mccs.component import CommunicationStatus
import ska_low_mccs.release as release


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
        super().init_device()

    def _init_state_model(self: MccsClusterManagerDevice) -> None:
        """Initialise the state model."""
        super()._init_state_model()
        self._health_state = None  # SKABaseDevice.InitCommand.do() does this too late.
        self._health_model = ClusterHealthModel(self.health_changed)
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
            SimulationMode.TRUE,
            self._component_communication_status_changed,
            self._component_power_mode_changed,
            self._component_fault,
            self._health_model.shadow_master_pool_node_health_changed,
        )

    def init_command_objects(self: MccsClusterManagerDevice) -> None:
        """Set up the command handler object for this device's commands."""
        super().init_command_objects()

        for (command_name, command_object) in [
            ("StartJob", self.StartJobCommand),
            ("StopJob", self.StopJobCommand),
            ("SubmitJob", self.SubmitJobCommand),
            ("GetJobStatus", self.GetJobStatusCommand),
            ("ClearJobStats", self.ClearJobStatsCommand),
            ("PingMasterPool", self.PingMasterPoolCommand),
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
            super().do()
            device = self.target
            device._build_state = release.get_release_info()
            device._version_id = release.version

            # The health model updates our health, but then the base class super().do()
            # overwrites it with OK, so we need to update this again.
            # TODO: This needs to be fixed in the base classes.
            device._health_state = device._health_model.health_state

            return (ResultCode.OK, "Init command completed OK")

    # --------------
    # Callback hooks
    # --------------
    def _component_communication_status_changed(
        self: MccsClusterManagerDevice,
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
        self: MccsClusterManagerDevice,
        power_mode: PowerMode,
    ) -> None:
        """
        Handle change in the power mode of the component.

        This is a callback hook, called by the component manager when
        the power mode of the component changes. It is implemented here
        to drive the op_state.

        :param power_mode: the power mode of the component.
        """
        action_map = {
            PowerMode.OFF: "component_off",
            PowerMode.STANDBY: "component_standby",
            PowerMode.ON: "component_on",
            PowerMode.UNKNOWN: "component_unknown",
        }

        self.op_state_model.perform_action(action_map[power_mode])

    def _component_fault(
        self: MccsClusterManagerDevice,
        is_fault: bool,
    ) -> None:
        """
        Handle change in the fault status of the component.

        This is a callback hook, called by the component manager when
        the component fault status changes. It is implemented here to
        drive the op_state.

        :param is_fault: whether the component is faulting or not.
        """
        if is_fault:
            self.op_state_model.perform_action("component_fault")
            self._health_model.component_fault(True)
        else:
            power_mode = self.component_manager.power_mode
            if power_mode is not None:
                self._component_power_mode_changed(self.component_manager.power_mode)
            self._health_model.component_fault(False)

    def health_changed(self: MccsClusterManagerDevice, health: HealthState):
        """
        Handle change in this device's health state.

        This is a callback hook, called whenever the HealthModel's
        evaluated health state changes. It is responsible for updating
        the tango side of things i.e. making sure the attribute is up to
        date, and events are pushed.

        :param health: the new health value
        """
        if self._health_state == health:
            return
        self._health_state = health
        self.push_change_event("healthState", health)

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

    @attribute(dtype=("",), max_dim_x=100, label="shadowMasterPoolStatus")
    def shadowMasterPoolStatus(self: MccsClusterManagerDevice) -> DevState:
        """
        Return the states of nodes in the shadow master pool.

        :return: the states of nodes in the shadow master pool
        """
        return self.component_manager.shadow_master_pool_status

    # --------
    # Commands
    # --------

    class StartJobCommand(ResponseCommand):
        """Class for handling the StartJob(argin) command."""

        SUCCEEDED_MESSAGE = "StartJob command completed OK"

        def do(  # type: ignore[override]
            self: MccsClusterManagerDevice.StartJobCommand, argin: str
        ) -> tuple[ResultCode, str]:
            """
            Run the user-specified functionality of this command.

            :param argin: the job id

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            component_manager = self.target
            try:
                component_manager.start_job(argin)
            except ValueError as value_error:
                return (ResultCode.FAILED, str(value_error))
            except ConnectionError as connection_error:
                return (ResultCode.FAILED, str(connection_error))
            else:
                return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

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

    class StopJobCommand(ResponseCommand):
        """Class for handling the StopJob(argin) command."""

        SUCCEEDED_MESSAGE = "StopJob command completed OK"

        def do(  # type: ignore[override]
            self: MccsClusterManagerDevice.StopJobCommand, argin: str
        ) -> tuple[ResultCode, str]:
            """
            Run the user-specified functionality of this command.

            :param argin: the job id

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            component_manager = self.target
            try:
                component_manager.stop_job(argin)
            except ValueError as value_error:
                return (ResultCode.FAILED, str(value_error))
            except ConnectionError as connection_error:
                return (ResultCode.FAILED, str(connection_error))
            else:
                return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

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

    class SubmitJobCommand(BaseCommand):
        """Class for handling the SubmitJob(argin) command."""

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

            component_manager = self.target
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

    class GetJobStatusCommand(BaseCommand):
        """Class for handling the GetJobStatus(argin) command."""

        def do(  # type: ignore[override]
            self: MccsClusterManagerDevice.GetJobStatusCommand, argin: str
        ) -> JobStatus:
            """
            Run the user-specified functionality of this command.

            :param argin: the job id

            :return: The status of the job
            """
            component_manager = self.target
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

    class ClearJobStatsCommand(ResponseCommand):
        """Class for handling the ClearJobStats() command."""

        SUCCEEDED_MESSAGE = "Job stats cleared"

        def do(  # type: ignore[override]
            self: MccsClusterManagerDevice.ClearJobStatsCommand,
        ) -> tuple[ResultCode, str]:
            """
            Run the user-specified functionality of this command.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            component_manager = self.target
            try:
                component_manager.clear_job_stats()
            except ConnectionError as connection_error:
                return ResultCode.FAILED, str(connection_error)
            else:
                return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_out="DevVarLongStringArray")
    def ClearJobStats(self: MccsClusterManagerDevice) -> DevVarLongStringArrayType:
        """
        Reset all job counters.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("ClearJobStats")
        (return_code, message) = handler()
        return ([return_code], [message])

    class PingMasterPoolCommand(ResponseCommand):
        """Class for handling the PingMasterPool() command."""

        SUCCEEDED_MESSAGE = "PingMasterPool command completed OK"

        def do(  # type: ignore[override]
            self: MccsClusterManagerDevice.PingMasterPoolCommand,
        ) -> tuple[ResultCode, str]:
            """
            Run the user-specified functionality of this command.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            component_manager = self.target
            try:
                component_manager.ping_master_pool()
            except ConnectionError as connection_error:
                return (ResultCode.FAILED, str(connection_error))
            else:
                return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_out="DevVarLongStringArray")
    def PingMasterPool(self: MccsClusterManagerDevice) -> DevVarLongStringArrayType:
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


def main(*args: str, **kwargs: str) -> int:
    """
    Entry point for module.

    :param args: positional arguments
    :param kwargs: named arguments

    :return: exit code
    """
    return MccsClusterManagerDevice.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
