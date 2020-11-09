# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

""" LFAA Cluster Manager Device Server

An implementation of the Cluster Manager Device Server for the MCCS
based upon architecture in SKA-TEL-LFAA-06000052-02.
"""
import threading

from tango import DebugIt, EnsureOmniThread
from tango.server import attribute, command, AttrWriteType
import json

from ska.base.commands import BaseCommand, ResponseCommand, ResultCode
from ska.base.control_model import HealthState, SimulationMode
from ska.low.mccs import MccsGroupDevice
from ska.low.mccs.cluster_simulator import ClusterSimulator, JobStatus, JobConfig
from ska.low.mccs.hardware import (
    HardwareHealthEvaluator,
    SimulableHardwareManager,
    SimulableHardwareFactory,
)
from ska.low.mccs.health import HealthModel

__all__ = [
    "ClusterHealthEvaluator",
    "ClusterManager",
    "MccsClusterManagerDevice",
    "main",
]


class ClusterHealthEvaluator(HardwareHealthEvaluator):
    """
    A simple :py:class:`~ska.low.mccs.hardware.HardwareHealthEvaluator`
    for a cluster.

    Implements a policy to decide on the health state of the cluster

    At present, the policy returns:

    * FAILED if the connection to the cluster has been lost, or if all
      of the master shadow nodes have failed

    * DEGRADED if any (but not all) of the master shadow nodes have
      failed.

    * OK if all of the master shadow nodes are okay.
    """

    def evaluate_health(self, cluster):
        """
        Evaluate the health of the hardware.

        :param cluster: the cluster driver or simulator for which
            health is being evaluated
        :type cluster: :py:class:`ClusterDriver` or
            :py:class:`ClusterSimulator`

        :return: the evaluated health of the cluster
        :rtype: :py:class:`~ska.base.control_model.HealthState`
        """
        if not cluster.is_connected:
            return HealthState.FAILED

        master_shadow_pool_node_health_ok = tuple(
            status == HealthState.OK for status in cluster.shadow_master_pool_status
        )
        if all(master_shadow_pool_node_health_ok):
            return HealthState.OK
        elif any(master_shadow_pool_node_health_ok):
            return HealthState.DEGRADED
        else:
            return HealthState.FAILED


class ClusterFactory(SimulableHardwareFactory):
    """
    A hardware factory for cluster hardware. At present, this returns a
    :py:class:`~ska.low.mccs.cluster_simulator.ClusterSimulator` object
    when in simulation mode, and raises
    :py:exception:`NotImplementedError` if the hardware is sought whilst
    not in simulation mode
    """

    def __init__(self, simulation_mode):
        """
        Create a new factory instance

        :param simulation_mode: the initial simulation mode for this
            cluster manager
        :type simulation_mode:
            :py:class:`~ska.base.control_model.SimulationMode`
        """
        super().__init__(simulation_mode)

    def _create_simulator(self):
        """
        Returns a hardware simulator

        :return: a hardware simulator for the tile
        :rtype: :py:class:`TpmSimulator`
        """
        return ClusterSimulator()


class ClusterManager(SimulableHardwareManager):
    """
    This class manages a cluster on behalf of the MccsClusterManagerDevice
    device.
    """

    def __init__(self, simulation_mode, _factory=None):
        """
        Initialise a new ClusterManager instance

        :param simulation_mode: the initial simulation mode for this
            cluster manager
        :type simulation_mode:
            :py:class:`~ska.base.control_model.SimulationMode`
        :param _factory: allows for substitution of a hardware factory.
            This is useful for testing, but generally should not be used
            in operations.
        :type _factory: :py:class:`AntennaHardwareFactory`
        """
        cluster_factory = _factory or ClusterFactory(
            simulation_mode == SimulationMode.TRUE
        )
        super().__init__(cluster_factory, ClusterHealthEvaluator())

    @property
    def jobs_errored(self):
        """
        Return the number of jobs that have errored

        :return: the number of jobs that have errored
        :rtype: int
        """
        return self._factory.hardware.jobs_errored

    @property
    def jobs_failed(self):
        """
        Return the number of jobs that have failed

        :return: the number of jobs that have failed
        :rtype: int
        """
        return self._factory.hardware.jobs_failed

    @property
    def jobs_finished(self):
        """
        Return the number of jobs that have finished

        :return: the number of jobs that have finished
        :rtype: int
        """
        return self._factory.hardware.jobs_finished

    @property
    def jobs_killed(self):
        """
        Return the number of jobs that have been killed

        :return: the number of jobs that have been killed
        :rtype: int
        """
        return self._factory.hardware.jobs_killed

    @property
    def jobs_lost(self):
        """
        Return the number of jobs that have been lost

        :return: the number of jobs that have been lost
        :rtype: int
        """
        return self._factory.hardware.jobs_lost

    @property
    def jobs_staging(self):
        """
        Return the number of jobs that are currently staging

        :return: the number of jobs that are currently staging
        :rtype: int
        """
        return self._factory.hardware.jobs_staging

    @property
    def jobs_starting(self):
        """
        Return the number of jobs that are currently starting

        :return: the number of jobs that are currently starting
        :rtype: int
        """
        return self._factory.hardware.jobs_starting

    @property
    def jobs_running(self):
        """
        Return the number of jobs that are currently running

        :return: the number of jobs that are currently running
        :rtype: int
        """
        return self._factory.hardware.jobs_running

    @property
    def jobs_killing(self):
        """
        Return the number of jobs that are currently being killed

        :return: the number of jobs that are currently being killed
        :rtype: int
        """
        return self._factory.hardware.jobs_killing

    @property
    def jobs_unreachable(self):
        """
        Return the number of jobs that are currently unreachable

        :return: the number of jobs that are currently unreachable
        :rtype: int
        """
        return self._factory.hardware.jobs_unreachable

    @property
    def memory_total(self):
        """
        Return the total memory of the cluster

        :return: the total memory of the cluster
        :rtype: float
        """
        return self._factory.hardware.memory_total

    @property
    def memory_used(self):
        """
        Return the used memory of the cluster

        :return: the used memory of the cluster
        :rtype: float
        """
        return self._factory.hardware.memory_used

    @property
    def memory_avail(self):
        """
        Return the available memory of the cluster

        :return: the available memory of the cluster
        :rtype: float
        """
        return self._factory.hardware.memory_avail

    @property
    def nodes_total(self):
        """
        Return the total number of nodes in the cluster

        :return: the total number of nodes in the cluster
        :rtype: int
        """
        return self._factory.hardware.nodes_total

    @property
    def nodes_in_use(self):
        """
        Return the number of nodes in use in the cluster

        :return: the number of nodes in use in the cluster
        :rtype: int
        """
        return self._factory.hardware.nodes_in_use

    @property
    def nodes_avail(self):
        """
        Return the number of available nodes in the cluster

        :return: the number of available nodes in the cluster
        :rtype: int
        """
        return self._factory.hardware.nodes_avail

    @property
    def master_cpus_total(self):
        """
        Return the total number of CPUs on the master node

        :return: the total number of CPUs on the master node
        :rtype: int
        """
        return self._factory.hardware.master_cpus_total

    @property
    def master_cpus_used(self):
        """
        Return the total number of CPUs in use on the master node

        :return: the total number of CPUs in use on the master node
        :rtype: int
        """
        return self._factory.hardware.master_cpus_used

    @property
    def master_cpus_allocated_percent(self):
        """
        Return the percent of CPUs allocated on master

        :return: the percent of CPUs allocated on master
        :rtype: float
        """
        return self._factory.hardware.master_cpus_allocated_percent

    @property
    def master_disk_total(self):
        """
        Return the total disk size on the master node

        :return: the total disk size on the master node
        :rtype: float
        """
        return self._factory.hardware.master_disk_total

    @property
    def master_disk_used(self):
        """
        Return the total disk usage on the master node

        :return: the total disk usage on the master node
        :rtype: float
        """
        return self._factory.hardware.master_disk_used

    @property
    def master_disk_percent(self):
        """
        Return the percent of disk used on master

        :return: the percent of disk used on master
        :rtype: float
        """
        return self._factory.hardware.master_disk_percent

    @property
    def master_mem_total(self):
        """
        Return the total memory size on the master node

        :return: the total memory size on the master node
        :rtype: float
        """
        return self._factory.hardware.master_mem_total

    @property
    def master_mem_used(self):
        """
        Return the total memory usage on the master node

        :return: the total memory usage on the master node
        :rtype: float
        """
        return self._factory.hardware.master_mem_used

    @property
    def master_mem_percent(self):
        """
        Return the percent of memory used on master

        :return: the percent of memory used on master
        :rtype: float
        """
        return self._factory.hardware.master_mem_percent

    @property
    def master_node_id(self):
        """
        Return the id of the master node

        :return: the id of the master node
        :rtype: int
        """
        return self._factory.hardware.master_node_id

    @property
    def shadow_master_pool_node_ids(self):
        """
        Return the ids of nodes in the shadow master pool

        :return: the ids of nodes in the shadow master pool
        :rtype: tuple of int
        """
        return self._factory.hardware.shadow_master_pool_node_ids

    @property
    def shadow_master_pool_status(self):
        """
        Return the statuses of nodes in the shadow master pool

        :return: the statuses of nodes in the shadow master pool
        :rtype: tuple of HealthState
        """
        return self._factory.hardware.shadow_master_pool_status

    def ping_master_pool(self):
        """
        Ping the master pool nodes to make sure they are ok.
        This has not been implemented.
        """
        self._factory.hardware.ping_master_pool()

    def clear_job_stats(self):
        """
        Clear stats for closed jobs
        """
        self._factory.hardware.clear_job_stats()

    def get_job_status(self, job_id):
        """
        Return the status of an open job

        :param job_id: the id of the job
        :type job_id: str

        :return: the status of the job
        :rtype: str
        """
        return self._factory.hardware.get_job_status(job_id)

    def submit_job(self, job_config):
        """
        Submit a job to the cluster. Since the JobConfig class is not
        yet implemented, this simply creates a unique job id for the
        job, registers it as a STAGING job, and returns the job id.

        :param job_config: specification of the submitted job
        :type job_config: :py:class:`JobConfig`

        :return: the job_id
        :rtype: int
        """
        return self._factory.hardware.submit_job(job_config)

    def start_job(self, job_id):
        """
        Start a specified job

        :param job_id: The id of the job to be started
        :type job_id: str
        """
        self._factory.hardware.start_job(job_id)

    def stop_job(self, job_id):
        """
        Start a specified job

        :param job_id: The id of the job to be started
        :type job_id: str
        """
        self._factory.hardware.stop_job(job_id)


class MccsClusterManagerDevice(MccsGroupDevice):
    """
    An implementation of the Cluster Manager tango device server for
    SKA-Low-MCCS based upon architecture in SKA-TEL-LFAA-06000052-02.

    This class is a subclass of
    :py:class:`ska.low.mccs.group_device.MccsGroupDevice`.

    **Properties:**

    - Device Property
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

        def __init__(self, target, state_model, logger=None):
            """
            Create a new InitCommand

            :param target: the object that this command acts upon; for
                example, the device for which this class implements the
                command
            :type target: object
            :param state_model: the state model that this command uses
                 to check that it is allowed to run, and that it drives
                 with actions.
            :type state_model: :py:class:`DeviceStateModel`
            :param logger: the logger to be used by this Command. If not
                provided, then a default module logger will be used.
            :type logger: a logger that implements the standard library
                logger interface
            """
            super().__init__(target, state_model, logger)

            self._init_thread = None
            self._init_lock = threading.Lock()
            self._init_interrupt = False

        def do(self):
            """
            Initialises the attributes and properties of the
            :py:class:`MccsClusterManagerDevice`.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`ska.base.commands.ResultCode`, str)
            """
            super().do()
            device = self.target

            # TODO: the default value for simulationMode should be
            # FALSE, but we don't have real hardware to test yet, so we
            # can't take our devices out of simulation mode. However,
            # simulationMode is a memorized attribute, and
            # pytango.test_context.MultiDeviceTestContext will soon
            # support memorized attributes. Once it does, we should
            # figure out how to inject memorized values into our real
            # tango deployment, then start honouring the default of
            # FALSE by removing this next line.
            device._simulation_mode = SimulationMode.TRUE
            device.cluster_manager = None

            self._init_thread = threading.Thread(
                target=self._initialise_connections, args=(device,)
            )
            with self._init_lock:
                self._init_thread.start()
                return (ResultCode.STARTED, "Init command started")

        def _initialise_connections(self, device):
            """
            Thread target for asynchronous initialisation of connections
            to external entities such as hardware and other devices.

            :param device: the device being initialised
            :type device: :py:class:`~ska.base.SKABaseDevice`
            """
            # https://pytango.readthedocs.io/en/stable/howto.html
            # #using-clients-with-multithreading
            with EnsureOmniThread():
                self._initialise_hardware_management(device)
                if self._init_interrupt:
                    self._init_thread = None
                    self._init_interrupt = False
                    return
                self._initialise_health_monitoring(device)
                if self._init_interrupt:
                    self._init_thread = None
                    self._init_interrupt = False
                    return
                with self._init_lock:
                    self.succeeded()

        def _initialise_hardware_management(self, device):
            """
            Initialise the connection to the hardware being managed by
            this device. May also register commands that depend upon a
            connection to that hardware

            :param device: the device for which a connection to the
                hardware is being initialised
            :type device: :py:class:`~ska.base.SKABaseDevice`
            """
            device.cluster_manager = ClusterManager(device._simulation_mode)

            args = (device.cluster_manager, device.state_model, self.logger)

            device.register_command_object("StartJob", device.StartJobCommand(*args))
            device.register_command_object("StopJob", device.StopJobCommand(*args))
            device.register_command_object("SubmitJob", device.SubmitJobCommand(*args))
            device.register_command_object(
                "GetJobStatus", device.GetJobStatusCommand(*args)
            )
            device.register_command_object(
                "ClearJobStats", device.ClearJobStatsCommand(*args)
            )
            device.register_command_object(
                "PingMasterPool", device.PingMasterPoolCommand(*args)
            )

        def _initialise_health_monitoring(self, device):
            """
            Initialise the health model for this device.

            :param device: the device for which the health model is
                being initialised
            :type device: :py:class:`~ska.base.SKABaseDevice`
            """
            device.set_change_event("healthState", True, True)
            device.set_archive_event("healthState", True, True)

            device.health_model = HealthModel(
                device.cluster_manager, None, None, device._update_health_state
            )

        def interrupt(self):
            """
            Interrupt the initialisation thread (if one is running)

            :return: whether the initialisation thread was interrupted
            :rtype: bool
            """
            if self._thread is None:
                return False
            self._interrupt = True
            return True

    def always_executed_hook(self):
        """Method always executed before any TANGO command is executed."""
        if self.cluster_manager is not None:
            self.cluster_manager.poll()

    def delete_device(self):
        """
        Hook to delete resources allocated in the
        :py:meth:`~ska.low.mccs.cluster_manager.MccsClusterManagerDevice.InitCommand.do`
        method of the nested
        :py:class:`~ska.low.mccs.cluster_manager.MccsClusterManagerDevice.InitCommand`
        class.

        This method allows for any memory or other resources allocated in the
        :py:meth:`~ska.low.mccs.cluster_manager.MccsClusterManagerDevice.InitCommand.do`
        method to be released. This method is called by the device destructor,
        and by the Init command when the Tango device server is re-initialised.
        """

    # ------------------
    # Attributes methods
    # ------------------

    @attribute(dtype="DevShort", label="jobsErrored", polling_period=10000)
    def jobsErrored(self):
        """
        Return the number of errored jobs.

        :return: the number of errored jobs
        :rtype: int
        """
        return self.cluster_manager.jobs_errored

    @attribute(dtype="DevShort", label="jobsFailed", max_alarm=1, polling_period=10000)
    def jobsFailed(self):
        """
        Return the number of failed jobs

        :return: the number of failed jobs
        :rtype: int
        """
        return self.cluster_manager.jobs_failed

    @attribute(dtype="DevShort", label="jobsFinished", polling_period=10000)
    def jobsFinished(self):
        """
        Returns the number of finished jobs

        :return: the number of finished jobs
        :rtype: int
        """
        return self.cluster_manager.jobs_finished

    @attribute(dtype="DevShort", label="jobsKilled", polling_period=10000)
    def jobsKilled(self):
        """
        Return the number of killed jobs

        :return: the number of killed jobs
        :rtype: int
        """
        return self.cluster_manager.jobs_killed

    @attribute(dtype="DevShort", label="jobsKilling", polling_period=10000)
    def jobsKilling(self):
        """
        Return the number of jobs currently being killed

        :return: the number of jobs currently being killed
        :rtype: int
        """
        return self.cluster_manager.jobs_killing

    @attribute(dtype="DevShort", label="jobsLost", polling_period=10000)
    def jobsLost(self):
        """
        Return the number of lost jobs

        :return: the number of lost jobs
        :rtype: int
        """
        return self.cluster_manager.jobs_lost

    @attribute(dtype="DevShort", label="jobsRunning", polling_period=10000)
    def jobsRunning(self):
        """
        Return the number of running jobs

        :return: the number of running jobs
        :rtype: int
        """
        return self.cluster_manager.jobs_running

    @attribute(dtype="DevShort", label="jobsStaging", polling_period=10000)
    def jobsStaging(self):
        """
        Return the number of staging jobs

        :return: the number of staging jobs
        :rtype: int
        """
        return self.cluster_manager.jobs_staging

    @attribute(dtype="DevShort", label="jobsStarting", polling_period=10000)
    def jobsStarting(self):
        """
        Return the number of starting jobs

        :return: the number of starting jobs
        :rtype: int
        """
        return self.cluster_manager.jobs_starting

    @attribute(dtype="DevShort", max_alarm=1, polling_period=10000)
    def jobsUnreachable(self):
        """
        Return the number of unreachable jobs

        :return: the number of unreachable jobs
        :rtype: int
        """
        return self.cluster_manager.jobs_unreachable

    @attribute(dtype="DevFloat", label="memoryTotal", polling_period=10000)
    def memoryTotal(self):
        """
        Return the total memory size

        :return: the total memory size
        :rtype: float
        """
        return self.cluster_manager.memory_total

    @attribute(dtype="DevFloat", label="memoryAvail", polling_period=10000)
    def memoryAvail(self):
        """
        Return the available memory

        :return: the available memory
        :rtype: float
        """
        return self.cluster_manager.memory_avail

    @attribute(dtype="DevFloat", label="memoryUsed", polling_period=10000)
    def memoryUsed(self):
        """
        Return the amount of memory in use

        :return: the amount of memory in use
        :rtype: float
        """
        return self.cluster_manager.memory_used

    @attribute(dtype="DevShort", label="nodesInUse", polling_period=10000)
    def nodesInUse(self):
        """
        Return the number of nodes in use

        :return: the number of nodes in use
        :rtype: int
        """
        return self.cluster_manager.nodes_in_use

    @attribute(dtype="DevShort", label="nodesAvail", polling_period=10000)
    def nodesAvail(self):
        """
        Return the number of available nodes

        :return: the number of available nodes
        :rtype: int
        """
        return self.cluster_manager.nodes_avail

    @attribute(dtype="DevShort", label="nodesTotal", polling_period=10000)
    def nodesTotal(self):
        """
        Return the total number of nodes

        :return: the total number of notes
        :rtype: int
        """
        return self.cluster_manager.nodes_total

    @attribute(dtype="DevShort", label="masterNodeId", polling_period=10000)
    def masterNodeId(self):
        """
        Return the id of the master node

        :return: the id of the master node
        :rtype: int
        """
        return self.cluster_manager.master_node_id

    @attribute(
        dtype="DevFloat", label="masterCpusAllocatedPercent", polling_period=10000
    )
    def masterCpusAllocatedPercent(self):
        """
        Return the percent allocation of the CPUs

        :return: the percent allocation of the CPUs
        :rtype: float
        """
        return self.cluster_manager.master_cpus_allocated_percent

    @attribute(dtype="DevShort", label="masterCpusUsed", polling_period=10000)
    def masterCpusUsed(self):
        """
        Return the number of CPUs in use on the master node

        :return: the number of CPUs in use on the master node
        :rtype: int
        """
        return self.cluster_manager.master_cpus_used

    @attribute(dtype="DevShort", label="masterCpusTotal", polling_period=10000)
    def masterCpusTotal(self):
        """
        Return the number of CPUs that the master node has

        :return: the number of CPUs that the master node has
        :rtype: int
        """
        return self.cluster_manager.master_cpus_total

    @attribute(dtype="DevFloat", label="masterDiskPercent", polling_period=10000)
    def masterDiskPercent(self):
        """
        Return the proportion of the master node disk that has been used

        :return: the proportion of the master node disk that has been
            used, as a percentage
        :rtype: float
        """
        return self.cluster_manager.master_disk_percent

    @attribute(dtype="DevDouble", label="masterDiskUsed", polling_period=10000)
    def masterDiskUsed(self):
        """
        Return the amount of the master node disk that has been used

        :return: the amount of the master node disk that has been
            used
        :rtype: double
        """
        return self.cluster_manager.master_disk_used

    @attribute(dtype="DevFloat", label="masterDiskTotal", polling_period=10000)
    def masterDiskTotal(self):
        """
        The total disk size on the master node

        :return: the total disk size on the master node
        :rtype: float
        """
        return self.cluster_manager.master_disk_total

    @attribute(dtype="DevFloat", label="masterMemPercent", polling_period=10000)
    def masterMemPercent(self):
        """
        Return the proportion of memory that has been used on the master
            node

        :return:  the proportion of memory that has been used on the
            master node
        :rtype: float
        """
        return self.cluster_manager.master_mem_percent

    @attribute(dtype="DevFloat", label="masterMemPercent", polling_period=10000)
    def masterMemUsed(self):
        """
        Return the amount of memory that has been used on the master
            node

        :return:  the amount of memory that has been used on the master
            node
        :rtype: float
        """
        return self.cluster_manager.master_mem_used

    @attribute(dtype="DevFloat", label="masterMemTotal", polling_period=10000)
    def masterMemTotal(self):
        """
        Return the total amount of memory on the master node

        :return:  the total amount of memory on the master node
        :rtype: float
        """
        return self.cluster_manager.master_mem_total

    @attribute(
        dtype=("DevShort",),
        max_dim_x=100,
        label="shadowMasterPoolNodeIds",
        polling_period=10000,
    )
    def shadowMasterPoolNodeIds(self):
        """
        Return the ids of nodes in the shadow master pool

        :return: the ids of nodes in the shadow master pool
        :rtype: list of int
        """
        return self.cluster_manager.shadow_master_pool_node_ids

    @attribute(
        dtype=("DevState",),
        max_dim_x=100,
        label="shadowMasterPoolStatus",
        polling_period=10000,
    )
    def shadowMasterPoolStatus(self):
        """
        Return the states of nodes in the shadow master pool

        :return: the states of nodes in the shadow master pool
        :rtype: list of :py:class:`tango.DevState`
        """
        return self.cluster_manager.shadow_master_pool_status

    # override from base classes so that it can be stored in the hardware manager
    @attribute(dtype=SimulationMode, access=AttrWriteType.READ_WRITE, memorized=True)
    def simulationMode(self):
        """
        Return the simulation mode of this device

        :return: the simulation mode of this device
        :rtype: :py:class:`~ska.base.control_model.SimulationMode`
        """
        return self.cluster_manager.simulation_mode

    @simulationMode.write
    def simulationMode(self, value):
        """
        Set the simulation mode of this device

        :param value: the new simulation mode
        :type value: :py:class:`~ska.base.control_model.SimulationMode`
        """
        self.cluster_manager.simulation_mode = value

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
            :py:meth:`MccsClusterManagerDevice.StartJob`
            command

            :param argin: the job id
            :type argin: :py:class:`tango.DevShort`
            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`ska.base.commands.ResultCode`, str)
            """
            cluster_manager = self.target
            try:
                cluster_manager.start_job(argin)
            except ValueError as value_error:
                return (ResultCode.FAILED, str(value_error))
            except ConnectionError as connection_error:
                return (ResultCode.FAILED, str(connection_error))
            else:
                return (ResultCode.OK, "StartJob command successful")

    @command(
        dtype_in="DevString",
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
        :rtype: (:py:class:`ska.base.commands.ResultCode`, str)
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
            :py:meth:`MccsClusterManagerDevice.StopJob`
            command

            :param argin: the job id
            :type argin: :py:class:`tango.DevShort`
            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`ska.base.commands.ResultCode`, str)
            """
            cluster_manager = self.target
            try:
                cluster_manager.stop_job(argin)
            except ValueError as value_error:
                return (ResultCode.FAILED, str(value_error))
            except ConnectionError as connection_error:
                return (ResultCode.FAILED, str(connection_error))
            else:
                return (ResultCode.OK, "StopJob command successful")

    @command(
        dtype_in="DevString",
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
        :rtype: (:py:class:`ska.base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("StopJob")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class SubmitJobCommand(BaseCommand):
        """
        Class for handling the SubmitJob(argin) command
        """

        def do(self, argin):
            """
            Stateless do hook for the
            :py:meth:`MccsClusterManagerDevice.SubmitJob`
            command

            :param argin: a JSON string specifying the job configuration
            :type argin: str
            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`ska.base.commands.ResultCode`, str)
            """
            args = json.loads(argin)
            job_config = JobConfig(**args)

            cluster_manager = self.target
            return cluster_manager.submit_job(job_config)

    @command(
        dtype_in="DevString",
        doc_in="jobConfig",
        dtype_out="DevString",
        doc_out="the job id",
    )
    @DebugIt()
    def SubmitJob(self, argin):
        """
        Command to submit a job to the queue

        :param argin: the job configuration, encoded as a JSON string
        :type argin: :py:class:`tango.DevString`

        :return: the job id of the submitted job
        :rtype: str
        """
        handler = self.get_command_object("SubmitJob")
        return handler(argin)

    class GetJobStatusCommand(BaseCommand):
        """
        Class for handling the GetJobStatus(argin) command
        """

        def do(self, argin):
            """
            Stateless do hook for the
            :py:meth:`MccsClusterManagerDevice.GetJobStatus`
            command

            :param argin: the job id
            :type argin: :py:class:`tango.DevString`
            :return: The status of the job
            :rtype: :py:class:`ska.low.mccs.cluster_simulator.JobStatus`
            """
            cluster_manager = self.target
            try:
                return cluster_manager.get_job_status(argin)
            except ValueError:
                return JobStatus.UNKNOWN

    @command(
        dtype_in="DevString",
        doc_in="jobId",
        dtype_out="DevShort",
        doc_out="the job status of the job",
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
        :rtype: (:py:class:`ska.base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("GetJobStatus")
        return handler(argin)

    class ClearJobStatsCommand(ResponseCommand):
        """
        Class for handling the ClearJobStats() command
        """

        def do(self):
            """
            Stateless do hook for the
            :py:meth:`MccsClusterManagerDevice.ClearJobStats`
            command

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`ska.base.commands.ResultCode`, str)
            """
            cluster_manager = self.target
            try:
                cluster_manager.clear_job_stats()
            except ConnectionError as connection_error:
                return ResultCode.str(connection_error)
            else:
                return (ResultCode.OK, "Job stats cleared")

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
        :rtype: (:py:class:`ska.base.commands.ResultCode`, str)
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
            :py:meth:`MccsClusterManagerDevice.PingMasterPool`
            command

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`ska.base.commands.ResultCode`, str)
            """
            cluster_manager = self.target
            try:
                cluster_manager.ping_master_pool()
            except ConnectionError as connection_error:
                return (ResultCode.FAILED, str(connection_error))
            else:
                return (ResultCode.OK, "PingMasterPool command successful")

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
        :rtype: (:py:class:`ska.base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("PingMasterPool")
        (return_code, message) = handler()
        return [[return_code], [message]]

    def _update_health_state(self, health_state):
        """
        Update and push a change event for the healthState attribute

        :param health_state: The new health state
        :type health_state: :py:class:`ska.base.control_model.HealthState`
        """
        self.push_change_event("healthState", health_state)
        self._health_state = health_state
        self.logger.info("health state = " + str(health_state))


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
    return MccsClusterManagerDevice.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
