# -*- coding: utf-8 -*-
#
# This file is part of the MccsClusterManager project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

""" LFAA Cluster Manager Device Server

An implementation of the Cluster Manager Device Server for the MCCS
based upon architecture in SKA-TEL-LFAA-06000052-02.
"""

# PyTango imports
from tango import DebugIt
from tango.server import attribute, command
from tango import DevState
from ska.low.mccs import MccsGroupDevice

# Additional import
from ska.base.commands import ResponseCommand, ResultCode

__all__ = ["MccsClusterManager", "main"]


class MccsClusterManager(MccsGroupDevice):
    """
    An implementation of the Cluster Manager Device Server for the MCCS
    based upon architecture in SKA-TEL-LFAA-06000052-02.
    """

    # -----------------
    # Device Properties
    # -----------------

    # ---------------
    # General methods
    # ---------------

    class InitCommand(MccsGroupDevice.InitCommand):
        """
        Command class for device initialisation
        """

        def do(self):
            """
            Initialises the attributes and properties of the
            :py:class:`MccsClusterManager`.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`ska.base.command.ResultCode`, str)
            """
            super().do()
            device = self.target

            device._jobs_error = 0
            device._jobs_failed = 0
            device._jobs_finished = 0
            device._jobs_killed = 0
            device._jobs_killing = 0
            device._jobs_lost = 0
            device._jobs_running = 0
            device._jobs_staging = 0
            device._jobs_starting = 0
            device._jobs_unreachable = 0
            device._memory_total = 0.0
            device._memory_avail = 0.0
            device._memory_used = 0.0
            device._nodes_in_use = 0
            device._nodes_total = 0
            device._master_node_id = 0
            device._master_cpus_allocated_percent = 0.0
            device._master_cpus_used = 0
            device._master_cpus_total = 0
            device._master_disk_percent = 0.0
            device._master_disk_used = 0.0
            device._master_disk_total = 0.0
            device._master_mem_percent = 0.0
            device._master_mem_used = 0.0
            device._master_mem_total = 0.0
            device._shadow_master_pool_node_ids = (0,)
            device._shadow_master_pool_status = (DevState.UNKNOWN,)

            device.set_change_event("jobsError", True, False)
            device.set_archive_event("jobsError", True, False)
            device.set_change_event("jobsFailed", True, False)
            device.set_archive_event("jobsFailed", True, False)
            device.set_change_event("jobsFinished", True, False)
            device.set_archive_event("jobsFinished", True, False)
            device.set_change_event("jobsKilled", True, False)
            device.set_archive_event("jobsKilled", True, False)
            device.set_change_event("jobsKilling", True, False)
            device.set_archive_event("jobsKilling", True, False)
            device.set_change_event("jobsLost", True, False)
            device.set_archive_event("jobsLost", True, False)
            device.set_change_event("jobsRunning", True, False)
            device.set_archive_event("jobsRunning", True, False)
            device.set_change_event("jobsStaging", True, False)
            device.set_archive_event("jobsStaging", True, False)
            device.set_change_event("jobsStarting", True, False)
            device.set_archive_event("jobsStarting", True, False)
            device.set_change_event("jobsUnreachable", True, False)
            device.set_archive_event("jobsUnreachable", True, False)
            device.set_change_event("memoryTotal", True, False)
            device.set_archive_event("memoryTotal", True, False)
            device.set_change_event("memoryAvail", True, False)
            device.set_archive_event("memoryAvail", True, False)
            device.set_change_event("memoryUsed", True, False)
            device.set_archive_event("memoryUsed", True, False)
            device.set_change_event("nodesInUse", True, False)
            device.set_archive_event("nodesInUse", True, False)
            device.set_change_event("nodesTotal", True, False)
            device.set_archive_event("nodesTotal", True, False)
            device.set_change_event("masterNodeId", True, False)
            device.set_archive_event("masterNodeId", True, False)
            device.set_change_event("masterCpusAllocatedPercent", True, False)
            device.set_archive_event("masterCpusAllocatedPercent", True, False)
            device.set_change_event("masterCpusUsed", True, False)
            device.set_archive_event("masterCpusUsed", True, False)
            device.set_change_event("masterCpusTotal", True, False)
            device.set_archive_event("masterCpusTotal", True, False)
            device.set_change_event("masterDiskPercent", True, False)
            device.set_archive_event("masterDiskPercent", True, False)
            device.set_change_event("masterDiskUsed", True, False)
            device.set_archive_event("masterDiskUsed", True, False)
            device.set_change_event("masterDiskTotal", True, False)
            device.set_archive_event("masterDiskTotal", True, False)
            device.set_change_event("masterMemPercent", True, False)
            device.set_archive_event("masterMemPercent", True, False)
            device.set_change_event("masterMemUsed", True, False)
            device.set_archive_event("masterMemUsed", True, False)
            device.set_change_event("masterMemTotal", True, False)
            device.set_archive_event("masterMemTotal", True, False)
            device.set_change_event("shadowMasterPoolNodeIds", True, False)
            device.set_archive_event("shadowMasterPoolNodeIds", True, False)
            device.set_change_event("shadowMasterPoolStatus", True, False)
            device.set_archive_event("shadowMasterPoolStatus", True, False)

            return (ResultCode.OK, "Init command succeeded")

    def init_command_objects(self):
        """
        Set up the handler objects for Commands
        """
        super().init_command_objects()

        args = (self, self.state_model, self.logger)

        self.register_command_object("StartJob", self.StartJobCommand(*args))
        self.register_command_object("StopJob", self.StopJobCommand(*args))
        self.register_command_object("SubmitJob", self.SubmitJobCommand(*args))
        self.register_command_object("GetJobStatus", self.GetJobStatusCommand(*args))
        self.register_command_object("ClearJobStats", self.ClearJobStatsCommand(*args))
        self.register_command_object(
            "PingMasterPool", self.PingMasterPoolCommand(*args)
        )

    def always_executed_hook(self):
        """Method always executed before any TANGO command is executed."""

    def delete_device(self):
        """Hook to delete resources allocated in init_device.

        This method allows for any memory or other resources allocated in the
        init_device method to be released.  This method is called by the device
        destructor and by the device Init command.
        """

    # ------------------
    # Attributes methods
    # ------------------

    @attribute(dtype="DevShort", label="jobsError")
    def jobsError(self):
        """
        Return the number of errored jobs.

        :return: the number of errored jobs
        :rtype: int
        """
        return self._jobs_error

    @attribute(dtype="DevShort", label="jobsFailed", max_alarm=1)
    def jobsFailed(self):
        """
        Return the number of failed jobs

        :return: the number of failed jobs
        :rtype: int
        """
        return self._jobs_failed

    @attribute(dtype="DevShort", label="jobsFinished")
    def jobsFinished(self):
        """
        Returns the number of finished jobs

        :return: the number of finished jobs
        :rtype: int
        """
        return self._jobs_finished

    @attribute(dtype="DevShort", label="jobsKilled")
    def jobsKilled(self):
        """
        Return the number of killed jobs

        :return: the number of killed jobs
        :rtype: int
        """
        return self._jobs_killed

    @attribute(dtype="DevShort", label="jobsKilling")
    def jobsKilling(self):
        """
        Return the number of jobs currently being killed

        :return: the number of jobs currently being killed
        :rtype: int
        """
        return self._jobs_killing

    @attribute(dtype="DevShort", label="jobsLost")
    def jobsLost(self):
        """
        Return the number of lost jobs

        :return: the number of lost jobs
        :rtype: int
        """
        return self._jobs_lost

    @attribute(dtype="DevShort", label="jobsRunning")
    def jobsRunning(self):
        """
        Return the number of running jobs

        :return: the number of running jobs
        :rtype: int
        """
        return self._jobs_running

    @attribute(dtype="DevShort", label="jobsStaging")
    def jobsStaging(self):
        """
        Return the number of staging jobs

        :return: the number of staging jobs
        :rtype: int
        """
        return self._jobs_staging

    @attribute(dtype="DevShort", label="jobsStarting")
    def jobsStarting(self):
        """
        Return the number of starting jobs

        :return: the number of starting jobs
        :rtype: int
        """
        return self._jobs_starting

    @attribute(dtype="DevShort", max_alarm=1)
    def jobsUnreachable(self):
        """
        Return the number of unreachable jobs

        :return: the number of unreachable jobs
        :rtype: int
        """
        return self._jobs_unreachable

    @attribute(dtype="DevFloat", label="memoryTotal")
    def memoryTotal(self):
        """
        Return the total memory size

        :return: the total memory size
        :rtype: float
        """
        return self._memory_total

    @attribute(dtype="DevFloat", label="memoryAvail")
    def memoryAvail(self):
        """
        Return the available memory

        :return: the available memory
        :rtype: float
        """
        return self._memory_avail

    @attribute(dtype="DevFloat", label="memoryUsed")
    def memoryUsed(self):
        """
        Return the amount of memory in use

        :return: the amount of memory in use
        :rtype: float
        """
        return self._memory_used

    @attribute(dtype="DevShort", label="nodesInUse")
    def nodesInUse(self):
        """
        Return the number of nodes in use

        :return: the number of nodes in use
        :rtype: int
        """
        return self._nodes_in_use

    @attribute(dtype="DevShort", label="nodesTotal")
    def nodesTotal(self):
        """
        Return the total number of nodes

        :return: the total number of notes
        :rtype: int
        """
        return self._nodes_total

    @attribute(dtype="DevShort", label="masterNodeId")
    def masterNodeId(self):
        """
        Return the id of the master node

        :return: the id of the master node
        :rtype: int
        """
        return self._master_node_id

    @attribute(dtype="DevFloat", label="masterCpusAllocatedPercent")
    def masterCpusAllocatedPercent(self):
        """
        Return the percent allocation of the CPUs

        :return: the percent allocation of the CPUs
        :rtype: float
        """
        return self._master_cpus_allocated_percent

    @attribute(dtype="DevShort", label="masterCpusUsed")
    def masterCpusUsed(self):
        """
        Return the number of CPUs in use on the master node

        :return: the number of CPUs in use on the master node
        :rtype: int
        """
        return self._master_cpus_used

    @attribute(dtype="DevShort", label="masterCpusTotal")
    def masterCpusTotal(self):
        """
        Return the number of CPUs that the master node has

        :return: the number of CPUs that the master node has
        :rtype: int
        """
        return self._master_cpus_total

    @attribute(dtype="DevFloat", label="masterDiskPercent")
    def masterDiskPercent(self):
        """
        Return the proportion of the master node disk that has been used

        :return: the proportion of the master node disk that has been
            used, as a percentage
        :rtype: float
        """
        return self._master_disk_percent

    @attribute(dtype="DevDouble", label="masterDiskUsed")
    def masterDiskUsed(self):
        """
        Return the amount of the master node disk that has been used

        :return: the amount of the master node disk that has been
            used
        :rtype: double
        """
        return self._master_disk_used

    @attribute(dtype="DevFloat", label="masterDiskTotal")
    def masterDiskTotal(self):
        """
        The total disk size on the master node

        :return: the total disk size on the master node
        :rtype: float
        """
        return self._master_disk_total

    @attribute(dtype="DevFloat", label="masterMemPercent")
    def masterMemPercent(self):
        """
        Return the proportion of memory that has been used on the master
            node

        :return:  the proportion of memory that has been used on the
            master node
        :rtype: float
        """
        return self._master_mem_percent

    @attribute(dtype="DevFloat", label="masterMemPercent")
    def masterMemUsed(self):
        """
        Return the amount of memory that has been used on the master
            node

        :return:  the amount of memory that has been used on the master
            node
        :rtype: float
        """
        return self._master_mem_used

    @attribute(dtype="DevFloat", label="masterMemTotal")
    def masterMemTotal(self):
        """
        Return the total amount of memory on the master node

        :return:  the total amount of memory on the master node
        :rtype: float
        """
        return self._master_mem_total

    @attribute(dtype=("DevShort",), max_dim_x=100, label="shadowMasterPoolNodeIds")
    def shadowMasterPoolNodeIds(self):
        """
        Return the ids of nodes in the shadow master pool

        :return: the ids of nodes in the shadow master pool
        :rtype: list of int
        """
        return self._shadow_master_pool_node_ids

    @attribute(dtype=("DevState",), max_dim_x=100, label="shadowMasterPoolStatus")
    def shadowMasterPoolStatus(self):
        """
        Return the states of nodes in the shadow master pool

        :return: the states of nodes in the shadow master pool
        :rtype: list of :py:class:`tango.DevState`
        """
        return self._shadow_master_pool_status

    # --------
    # Commands
    # --------

    class StartJobCommand(ResponseCommand):
        """
        Class for handling the StartJob(argin) command
        """

        def do(self, argin):
            """
            Stateless do hook for the
            :py:meth:`MccsClusterManager.StartJob`
            command

            :param argin: the job id
            :type argin: :py:class:`tango.DevShort`
            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`ska.base.command.ResultCode`, str)
            """
            return (
                ResultCode.OK,
                "Stub implementation of StartJobCommand(), does nothing",
            )

    @command(
        dtype_in="DevShort",
        doc_in="jobId",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'information-only string')",
    )
    @DebugIt()
    def StartJob(self, argin):
        """
        Command to start a particular job

        :param argin: the job id
        :type argin: :py:class:`tango.DevShort`

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`ska.base.command.ResultCode`, str)
        """
        handler = self.get_command_object("StartJob")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class StopJobCommand(ResponseCommand):
        """
        Class for handling the StopJob(argin) command
        """

        def do(self, argin):
            """
            Stateless do hook for the
            :py:meth:`MccsClusterManager.StopJob`
            command

            :param argin: the job id
            :type argin: :py:class:`tango.DevShort`
            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`ska.base.command.ResultCode`, str)
            """
            return (
                ResultCode.OK,
                "Stub implementation of StopJobCommand(), does nothing",
            )

    @command(
        dtype_in="DevShort",
        doc_in="jobId",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'information-only string')",
    )
    @DebugIt()
    def StopJob(self, argin):
        """
        Command to stop a particular job

        :param argin: the job id
        :type argin: :py:class:`tango.DevShort`

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`ska.base.command.ResultCode`, str)
        """
        handler = self.get_command_object("StopJob")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class SubmitJobCommand(ResponseCommand):
        """
        Class for handling the SubmitJob(argin) command
        """

        def do(self, argin):
            """
            Stateless do hook for the
            :py:meth:`MccsClusterManager.SubmitJob`
            command

            :param argin: the job configuration
            :type argin: :py:class:`tango.DevShort`
            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`ska.base.command.ResultCode`, str)
            """
            return (
                ResultCode.OK,
                "Stub implementation of SubmitJobCommand(), does nothing",
            )

    @command(
        dtype_in="DevShort",
        doc_in="jobConfig",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'information-only string')",
    )
    @DebugIt()
    def SubmitJob(self, argin):
        """
        Command to submit a job to the queue

        :param argin: the job configuration
        :type argin: :py:class:`tango.DevShort`

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`ska.base.command.ResultCode`, str)
        """
        handler = self.get_command_object("SubmitJob")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class GetJobStatusCommand(ResponseCommand):
        """
        Class for handling the GetJobStatus(argin) command
        """

        def do(self, argin):
            """
            Stateless do hook for the
            :py:meth:`MccsClusterManager.GetJobStatus`
            command

            :param argin: the job id
            :type argin: :py:class:`tango.DevShort`
            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`ska.base.command.ResultCode`, str)
            """
            return (
                ResultCode.OK,
                "Stub implementation of GetJobStatusCommand(), does nothing",
            )

    @command(
        dtype_in="DevShort",
        doc_in="jobId",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'information-only string')",
    )
    @DebugIt()
    def GetJobStatus(self, argin):
        """
        Poll the current status for a job

        :param argin: the job id
        :type argin: :py:class:`tango.DevShort`

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`ska.base.command.ResultCode`, str)
        """
        handler = self.get_command_object("GetJobStatus")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class ClearJobStatsCommand(ResponseCommand):
        """
        Class for handling the ClearJobStats() command
        """

        def do(self):
            """
            Stateless do hook for the
            :py:meth:`MccsClusterManager.ClearJobStats`
            command

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`ska.base.command.ResultCode`, str)
            """
            return (
                ResultCode.OK,
                "Stub implementation of ClearJobStatsCommand(), does nothing",
            )

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'information-only string')",
    )
    @DebugIt()
    def ClearJobStats(self):
        """
        Used to reset all job counters - useful at the start of a new observation

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`ska.base.command.ResultCode`, str)
        """
        handler = self.get_command_object("ClearJobStats")
        (return_code, message) = handler()
        return [[return_code], [message]]

    class PingMasterPoolCommand(ResponseCommand):
        """
        Class for handling the PingMasterPool() command
        """

        def do(self):
            """
            Stateless do hook for the
            :py:meth:`MccsClusterManager.PingMasterPool`
            command

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`ska.base.command.ResultCode`, str)
            """
            return (
                ResultCode.OK,
                "Stub implementation of PingMasterPoolCommand(), does nothing",
            )

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'information-only string')",
    )
    @DebugIt()
    def PingMasterPool(self):
        """
        Pings all nodes in shadow master pool, to maintain status of each

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`ska.base.command.ResultCode`, str)
        """
        handler = self.get_command_object("PingMasterPool")
        (return_code, message) = handler()
        return [[return_code], [message]]


# ----------
# Run server
# ----------


def main(args=None, **kwargs):
    """
    Main function of the :py:mod:`ska.low.mccs.cluster_manager` module.

    :param args: positional arguments
    :type args: list
    :param kwargs: named arguments
    :type kwargs: dict

    :return: exit code
    :rtype: int
    """
    return MccsClusterManager.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
