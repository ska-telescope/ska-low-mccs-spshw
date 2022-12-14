# type: ignore
# pylint: skip-file
#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements component management for tiles."""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Callable, Optional, cast

import tango
from pyaavs.tile import Tile as Tile12
from pyaavs.tile_wrapper import Tile as HwTile
from ska_control_model import (
    CommunicationStatus,
    PowerState,
    ResultCode,
    SimulationMode,
    TaskStatus,
    TestMode,
)
from ska_low_mccs_common import MccsDeviceProxy
from ska_low_mccs_common.component import (
    MccsComponentManager,
    ObjectComponentManager,
    check_communicating,
    check_on,
)

from ska_low_mccs_spshw.tile import (
    BaseTpmSimulator,
    DynamicTpmSimulator,
    StaticTpmSimulator,
    TpmDriver,
)
from ska_low_mccs_spshw.tile.tile_orchestrator import TileOrchestrator
from ska_low_mccs_spshw.tile.time_util import TileTime
from ska_low_mccs_spshw.tile.tpm_status import TpmStatus

__all__ = [
    "DynamicTpmSimulatorComponentManager",
    "StaticTpmSimulatorComponentManager",
    "TileComponentManager",
]


class _TpmSimulatorComponentManager(ObjectComponentManager):
    """
    A component manager for a TPM simulator.

    This is a private class that supports the public component manager
    classes for static and dynamic TPM simulators.
    """

    def __init__(
        self: _TpmSimulatorComponentManager,
        tpm_simulator: BaseTpmSimulator,
        logger: logging.Logger,
        max_workers: int,
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """
        Initialise a new instance.

        :param tpm_simulator: the TPM simulator component managed by
            this component manager
        :param logger: a logger for this object to use
        :param max_workers: Nos of worker threads for async commands.
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be called when the
            component state changes.
        """
        super().__init__(
            tpm_simulator,
            logger,
            max_workers,
            communication_state_changed_callback,
            component_state_changed_callback,
        )
        self._component_state_changed_callback = component_state_changed_callback

    __PASSTHROUGH = [
        "adc_rms",
        "apply_pointing_delays",
        "arp_table",
        "beamformer_table",
        "board_temperature",
        "channeliser_truncation",
        "pending_data_requests",
        "clock_present",
        "configure_40g_core",
        "configure_integrated_beam_data",
        "configure_integrated_channel_data",
        "configure_test_generator",
        "csp_rounding",
        "current_tile_beamformer_frame",
        "download_firmware",
        "erase_fpga",
        "firmware_available",
        "firmware_name",
        "firmware_version",
        "fpga1_temperature",
        "fpga2_temperature",
        "fpga_current_frame",
        "fpgas_time",
        "fpga_reference_time",
        "get_40g_configuration",
        "tpm_version",
        "initialise_beamformer",
        "initialise",
        "is_beamformer_running",
        "is_programmed",
        "load_calibration_coefficients",
        "load_pointing_delays",
        "phase_terminal_count",
        "pll_locked",
        "post_synchronisation",
        "pps_delay",
        "pps_present",
        "preadu_levels",
        "read_address",
        "read_register",
        "register_list",
        "send_data_samples",
        "set_beamformer_regions",
        "set_lmc_download",
        "set_lmc_integrated_download",
        "start_acquisition",
        "start_beamformer",
        "static_delays",
        "station_id",
        "stop_beamformer",
        "stop_data_transmission",
        "stop_integrated_data",
        "apply_calibration",
        "sync_fpgas",
        "sysref_present",
        "test_generator_active",
        "test_generator_input_select",
        "tile_id",
        "tpm_status",
        "tpm_version",
        "voltage",
        "write_address",
        "write_register",
    ]

    def __getattr__(
        self: _TpmSimulatorComponentManager, name: str, default_value: Any = None
    ) -> Any:
        """
        Get value for an attribute not found in the usual way.

        Implemented to check against a list of attributes to pass down
        to the simulator. The intent is to avoid having to implement a
        whole lot of methods that simply call the corresponding method
        on the simulator. The only reason this is possible is because
        the simulator has much the same interface as its component
        manager.

        :param name: name of the requested attribute
        :param default_value: value to return if the attribute is not
            found

        :return: the requested attribute
        """
        if name in self.__PASSTHROUGH:
            return self._get_from_component(name)
        return default_value

    @check_communicating
    def _get_from_component(self: _TpmSimulatorComponentManager, name: str) -> Any:
        """
        Get an attribute from the component (if we are communicating with it).

        :param name: name of the attribute to get.

        :return: the attribute value
        """
        # This one-liner is only a method so that we can decorate it.
        return getattr(self._component, name)

    def __setattr__(self: _TpmSimulatorComponentManager, name: str, value: Any) -> Any:
        """
        Set an attribute on this TPM simulator component manager.

        This is implemented to pass writes to certain attributes to the
        underlying TPM simulator.

        :param name: name of the attribute for which the value is to be
            set
        :param value: new value of the attribute
        """
        if name in self.__PASSTHROUGH:
            self._set_in_component(name, value)
        else:
            super().__setattr__(name, value)

    @check_communicating
    def _set_in_component(
        self: _TpmSimulatorComponentManager, name: str, value: Any
    ) -> None:
        """
        Set an attribute in the component (if we are communicating with it).

        :param name: name of the attribute to set.
        :param value: new value for the attribute
        """
        # This one-liner is only a method so that we can decorate it.
        setattr(self._component, name, value)

    def _set_tpm_status(self: _TpmSimulatorComponentManager, status: TpmStatus) -> None:
        """
        Set the TPM status in the simulator.

        :param status: the new TPM status
        """
        self._component._set_tpm_status(status)


class StaticTpmSimulatorComponentManager(_TpmSimulatorComponentManager):
    """A component manager for a static TPM simulator."""

    def __init__(
        self: StaticTpmSimulatorComponentManager,
        logger: logging.Logger,
        max_workers: int,
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """
        Initialise a new instance.

        :param logger: a logger for this object to use
        :param max_workers: Nos of worker threads for async commands.
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be called when the
            component state changes.
        """
        super().__init__(
            StaticTpmSimulator(logger, component_state_changed_callback),
            logger,
            max_workers,
            communication_state_changed_callback,
            component_state_changed_callback,
        )

        self._component_state_changed_callback = component_state_changed_callback


class DynamicTpmSimulatorComponentManager(_TpmSimulatorComponentManager):
    """A component manager for a dynamic TPM simulator."""

    def __init__(
        self: DynamicTpmSimulatorComponentManager,
        logger: logging.Logger,
        max_workers: int,
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """
        Initialise a new instance.

        :param logger: a logger for this object to use
        :param max_workers: Nos of worker threads for async commands.
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be called when the
            component state changes.
        """
        super().__init__(
            DynamicTpmSimulator(logger, component_state_changed_callback),
            logger,
            max_workers,
            communication_state_changed_callback,
            component_state_changed_callback,
        )


class TileComponentManager(MccsComponentManager):
    """A component manager for a TPM (simulator or driver) and its power supply."""

    def __init__(
        self: TileComponentManager,
        simulation_mode: SimulationMode,
        test_mode: TestMode,
        logger: logging.Logger,
        max_workers: int,
        tile_id: int,
        tpm_ip: str,
        tpm_cpld_port: int,
        tpm_version: str,
        subrack_fqdn: str,
        subrack_tpm_id: int,
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """
        Initialise a new instance.

        :param simulation_mode: the simulation mode of this component
            manager. If `SimulationMode.TRUE`, then this component
            manager will launch an internal TPM simulator and interact
            with it; if `SimulationMode.FALSE`, this component manager
            will attempt to connect with an external TPM at the
            configured IP address and port.
        :param test_mode: the test mode of this component manager. This
            has no effect when the device is in `SimulationMode.FALSE`.
            But when the simulation mode is `SimulationMode.TRUE`, then
            this determines some properties of the simulator: if the
            test mode is `TestMode.TEST`, then the simulator will
            return static "canned" values that are easy to assert
            against during testing; if `TestMode.NONE`, the simulator
            will return dynamically changing values for attributes such
            as temperatures and voltages, making for a nice demo but not
            so easy to test against.
        :param logger: a logger for this object to use
        :param max_workers: nos. of worker threads
        :param tile_id: the unique ID for the tile
        :param tpm_ip: the IP address of the tile
        :param tpm_cpld_port: the port at which the tile is accessed for control
        :param tpm_version: TPM version: "tpm_v1_2" or "tpm_v1_6"
        :param subrack_fqdn: FQDN of the subrack that controls power to
            this tile
        :param subrack_tpm_id: This tile's position in its subrack
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be
            called when the component state changes
        """
        self._subrack_fqdn = subrack_fqdn
        self._subrack_tpm_id = subrack_tpm_id
        self._power_state_lock = threading.RLock()
        self._subrack_proxy: Optional[MccsDeviceProxy] = None
        self._component_state_changed_callback = component_state_changed_callback
        self._subrack_communication_state = CommunicationStatus.DISABLED
        self._tpm_communication_state = CommunicationStatus.DISABLED

        if tpm_version not in ["tpm_v1_2", "tpm_v1_6"]:
            self.logger.warning(
                "TPM version "
                + tpm_version
                + " not valid. Trying to read version from board, which must be on"
            )
            tpm_version = None

        tile = cast(
            Tile12,
            HwTile(
                ip=tpm_ip, port=tpm_cpld_port, logger=logger, tpm_version=tpm_version
            ),
        )

        if simulation_mode == SimulationMode.FALSE:
            self._tpm_component_manager = TpmDriver(
                logger,
                max_workers,
                tile_id,
                tile,
                tpm_version,
                self._tpm_communication_state_changed,
                component_state_changed_callback,
            )
        elif test_mode == TestMode.TEST:  # and SimulationMode.TRUE
            self._tpm_component_manager = StaticTpmSimulatorComponentManager(
                logger,
                max_workers,
                self._tpm_communication_state_changed,
                component_state_changed_callback,
            )
        else:  # SimulationMode.TRUE and TestMode.NONE
            self._tpm_component_manager = DynamicTpmSimulatorComponentManager(
                logger,
                max_workers,
                self._tpm_communication_state_changed,
                component_state_changed_callback,
            )

        self._tile_orchestrator = TileOrchestrator(
            self._start_communicating_with_subrack,
            self._stop_communicating_with_subrack,
            self._start_communicating_with_tpm,
            self._stop_communicating_with_tpm,
            self._turn_off_tpm,
            self._turn_on_tpm,
            self.update_communication_state,
            component_state_changed_callback,
            logger,
        )

        self._tile_time = TileTime(0)

        super().__init__(
            logger,
            max_workers,
            communication_state_changed_callback,
            component_state_changed_callback,
        )

    def start_communicating(self: TileComponentManager) -> None:
        """Establish communication with the tpm and the upstream power supply."""
        self._tile_orchestrator.desire_online()

    def stop_communicating(self: TileComponentManager) -> None:
        """Establish communication with the tpm and the upstream power supply."""
        self._tile_orchestrator.desire_offline()

    def off(
        self: TileComponentManager, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Tell the upstream power supply proxy to turn the tpm off.

        :param task_callback: Update task state, defaults to None

        :return: a result code and a unique_id or message.
        """
        return self.submit_task(
            self._tile_orchestrator.desire_off, args=[], task_callback=task_callback
        )

    def on(
        self: TileComponentManager, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Tell the upstream power supply proxy to turn the tpm on.

        :param task_callback: Update task state, defaults to None

        :return: a result code and a unique_id or message.
        """
        return self.submit_task(
            self._tile_orchestrator.desire_on, args=[], task_callback=task_callback
        )

    def standby(
        self: TileComponentManager, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Tell the upstream power supply proxy to turn the tpm on.

        :param task_callback: Update task state, defaults to None

        :return: a result code, or None if there was nothing to do.
        """
        return self.submit_task(
            self._tile_orchestrator.desire_standby, args=[], task_callback=task_callback
        )

    # def component_progress_changed(self: TileComponentManager, progress: int) -> None:
    #     """
    #     Handle notification that the component's progress value has changed.

    #     This is a callback hook, to be passed to the managed component.

    #     :param progress: The progress percentage of the long-running command
    #     """
    #     if self._component_progress_changed_callback is not None:
    #         self._component_progress_changed_callback(progress)

    def _subrack_communication_state_changed(
        self: TileComponentManager, communication_state: CommunicationStatus
    ) -> None:
        """
        Handle a change in status of communication with the antenna via the APIU.

        :param communication_state: the status of communication with
            the antenna via the APIU.
        """
        self._tile_orchestrator.update_subrack_communication_state(communication_state)

    def _start_communicating_with_tpm(self: TileComponentManager) -> None:
        # Pass this as a callback, rather than the method that is calls,
        # so that self._tpm_component_manager is resolved when the
        # callback is called, not when it is registered.
        self._tpm_component_manager.start_communicating()

    def _stop_communicating_with_tpm(self: TileComponentManager) -> None:
        # Pass this as a callback, rather than the method that is calls,
        # so that self._tpm_component_manager is resolved when the
        # callback is called, not when it is registered.
        self._tpm_component_manager.stop_communicating()

    # TODO: Convert this to a LRC. This doesn't need to be done right now.
    #       This needs an instantiation of a new class derived from
    #       DeviceComponentManager that provides its own message queue.
    #       That allows the proxy call to other Tango devices to be queued
    #       rather than blocking until the call to the Tango device has been
    #       issued and queued in that device. This becomes increasing
    #       important when we have many Tango devices.
    def _start_communicating_with_subrack(self: TileComponentManager) -> None:
        """
        Establish communication with the subrack, then start monitoring.

        This contains the actual communication logic that is enqueued to
        be run asynchronously.

        :raises ConnectionError: Connection to subrack failed
        """
        # Don't set comms NOT_ESTABLISHED here. It should already have been handled
        # synchronously by the orchestator.
        # Check if it was already connected.
        unconnected = self._subrack_proxy is None
        if unconnected:
            self._subrack_proxy = MccsDeviceProxy(
                self._subrack_fqdn, self._logger, connect=False
            )
            try:
                self._subrack_proxy.connect()
            except tango.DevFailed as dev_failed:
                self._subrack_proxy = None
                raise ConnectionError(
                    f"Could not connect to '{self._subrack_fqdn}'"
                ) from dev_failed

        cast(MccsDeviceProxy, self._subrack_proxy).add_change_event_callback(
            "longRunningCommandResult",
            self._tile_orchestrator.propogate_subrack_lrc,
        )
        cast(MccsDeviceProxy, self._subrack_proxy).add_change_event_callback(
            f"tpm{self._subrack_tpm_id}PowerState",
            self._tpm_power_state_change_event_received,
        )
        time.sleep(0.1)
        if unconnected:
            self._tile_orchestrator.update_subrack_communication_state(
                CommunicationStatus.ESTABLISHED
            )

    def _tpm_power_state_change_event_received(
        self: TileComponentManager,
        event_name: str,
        event_value: PowerState,
        event_quality: tango.AttrQuality,
    ) -> None:
        """
        Handle change in tpm power states.

        This is a callback that is triggered by an event subscription
        on the subrack device.

        :param event_name: name of the event; will always be
            "areTpmsOn" for this callback
        :param event_value: the new attribute value
        :param event_quality: the quality of the change event
        """
        assert event_name.lower() == f"tpm{self._subrack_tpm_id}PowerState".lower(), (
            f"subrack 'tpm{self._subrack_tpm_id}PowerState' attribute changed callback "
            f"called but event_name is {event_name}."
        )
        self._tpm_power_state_changed(event_value)

    def _stop_communicating_with_subrack(self: TileComponentManager) -> None:
        self._subrack_proxy = None

    # Converted to a LRC, in subrack
    # This code only tells you if the command was submitted NOT the result
    def _turn_off_tpm(self: TileComponentManager) -> ResultCode:
        assert self._subrack_proxy is not None  # for the type checker
        ([result_code], [unique_id]) = self._subrack_proxy.PowerOffTpm(
            self._subrack_tpm_id
        )
        # TODO better handling of result code and exceptions.
        if result_code > 2:
            self.logger.error(
                f"Turn off tpm {self._subrack_tpm_id} returns {result_code}"
            )
        return result_code, unique_id

    # Converted to a LRC, in subrack
    # This code only tells you if the command was submitted NOT the result
    def _turn_on_tpm(self: TileComponentManager) -> ResultCode:
        assert self._subrack_proxy is not None  # for the type checker
        ([result_code], [unique_id]) = self._subrack_proxy.PowerOnTpm(
            self._subrack_tpm_id
        )
        # TODO better handling of result code and exceptions.
        if result_code > 2:
            self.logger.error(
                f"Turn on tpm {self._subrack_tpm_id} returns {result_code}"
            )
        return result_code, unique_id

    def _tpm_power_state_changed(
        self: TileComponentManager, power_state: PowerState
    ) -> None:
        self._tile_orchestrator.update_tpm_power_state(power_state)

    def _tpm_communication_state_changed(
        self: TileComponentManager, communication_state: CommunicationStatus
    ) -> None:
        """
        Handle a change in status of communication with the tpm.

        :param communication_state: the status of communication with
            the tpm.
        """
        self._tile_orchestrator.update_tpm_communication_state(communication_state)

    def update_tpm_power_state(
        self: TileComponentManager, power_state: PowerState
    ) -> None:
        """
        Update the power state, calling callbacks as required.

        If power state is ON, then the TPM is checked for initialisation,
        and initialised if not already so.

        :param power_state: the new power state of the component. This can
            be None, in which case the internal value is updated but no
            callback is called. This is useful to ensure that the
            callback is called next time a real value is pushed.
        """
        self.set_power_state(power_state)
        self.logger.debug(
            f"power state: {self.power_state}, communication status: "
            f"{self.communication_state}"
        )
        if self.communication_state == CommunicationStatus.ESTABLISHED:
            if power_state == PowerState.ON:
                if (not self.is_programmed) or (
                    self.tpm_status == TpmStatus.PROGRAMMED
                ):
                    self.initialise()
                self._tile_time.set_reference_time(self.tile_reference_time)
            if power_state == PowerState.STANDBY:
                self.erase_fpga()
                self._tile_time.set_reference_time(0)

    @property
    def tpm_status(self: TileComponentManager) -> TpmStatus:
        """
        Return the TPM status.

        :return: the TPM status
        """
        if self.power_state == PowerState.UNKNOWN:
            self.logger.debug("power state UNKNOWN")
            status = TpmStatus.UNKNOWN
        elif self.power_state != PowerState.ON:
            status = TpmStatus.OFF
        elif self.communication_state != CommunicationStatus.ESTABLISHED:
            status = TpmStatus.UNCONNECTED
        else:
            status = self._tpm_component_manager.tpm_status
        return status

    @property
    def fpgas_unix_time(self: TileComponentManager) -> list[int]:
        """
        Return FPGA internal Unix time.

        Used to check proper synchronization
        :return: list of two Unix time integers
        """
        return self.fpgas_time

    @property
    def fpga_time(self: TileComponentManager) -> str:
        """
        Return FPGA internal time in UTC format.

        :return: FPGA internal time
        """
        return self._tile_time.format_time_from_timestamp(self.fpgas_time[0])

    @property
    def fpga_reference_time(self: TileComponentManager) -> str:
        """
        Return FPGA reference time in UTC format.

        Reference time is set as part of start_observation.
        It represents the timestamp  for the first frame

        :return: FPGA reference time
        """
        reference_time = self._tpm_component_manager.fpga_reference_time
        self._tile_time.set_reference_time(reference_time)
        return self._tile_time.format_time_from_timestamp(reference_time)

    @property
    def fpga_frame_time(self: TileComponentManager) -> str:
        """
        Return FPGA frame time in UTC format.

        frame time is the timestamp for the current frame being processed.
        Value reported here refers to the ADC frames, but the total processing
        delay is < 1ms and thus irrelevant on the timescales of MCCS response time

        :return: FPGA reference time
        """
        reference_time = self._tpm_component_manager.fpga_reference_time
        self._tile_time.set_reference_time(reference_time)
        return self._tile_time.format_time_from_frame(self.fpga_current_frame)

    #
    # Timed commands. Convert time to frame number
    #
    @check_communicating
    def apply_calibration(
        self: TileComponentManager, load_time: Optional[str] = ""
    ) -> None:
        """
        Load the calibration coefficients at the specified time delay.

        :param load_time: switch time as ISO formatted time

        :raises ValueError: invalid time
        """
        if load_time == "":
            load_frame = 0
        elif type(load_time) == int:  # added for backward compatibility
            load_frame = load_time
        else:
            load_frame = self._tile_time.frame_from_utc_time(load_time)
            if load_frame < 0:
                self.logger.error(f"apply_calibration: Invalid time {load_time}")
                raise ValueError(f"Invalid time {load_time}")
            if (load_frame - self.fpga_current_frame) < 20:
                self.logger.error("apply_calibration: time not enough in the future")
                raise ValueError("Time too early")
        self._tpm_component_manager.apply_calibration(load_frame)

    @check_communicating
    def apply_pointing_delays(
        self: TileComponentManager, load_time: Optional[str] = ""
    ) -> None:
        """
        Load the pointing delays at the specified time delay.

        :param load_time: switch time as ISO formatted time

        :raises ValueError: invalid time
        """
        if load_time == "":
            load_frame = 0
        elif type(load_time) == int:  # added for backward compatibility
            load_frame = load_time
        else:
            load_frame = self._tile_time.frame_from_utc_time(load_time)
            if load_frame < 0:
                self.logger.error(f"apply_pointing_delays: Invalid time {load_time}")
                raise ValueError(f"Invalid time {load_time}")
            if (load_frame - self.fpga_current_frame) < 20:
                self.logger.error(
                    "apply_pointing_delays: time not enough in the future"
                )
                raise ValueError("Time too early")
        self._tpm_component_manager.apply_pointing_delays(load_frame)

    @check_communicating
    def start_beamformer(
        self: TileComponentManager,
        start_time: Optional[str] = None,
        duration: Optional[int] = -1,
        subarray_beam_id: Optional[int] = -1,
        scan_id: Optional[int] = 0,
    ) -> None:
        """
        Start beamforming on a specific subset of the beamformed channels.

        Current firmware version does not support channel mask and scan ID,
        these are ignored

        :param start_time: Start time as ISO formatted time
        :param duration: Scan duration, in frames, default "forever"
        :param subarray_beam_id: Subarray beam ID of the channels to be started
                Command affects only beamformed channels for given subarray ID
                Default -1: all channels
        :param scan_id: ID of the scan to be started. Default 0

        :raises ValueError: invalid time specified
        """
        if start_time is None:
            start_frame = 0
        elif type(start_time) == int:  # added for backward compatibility
            start_frame = start_time
        else:
            start_frame = self._tile_time.frame_from_utc_time(start_time)
            if start_frame < 0:
                self.logger.error(f"start_beamformer: Invalid time {start_time}")
                raise ValueError(f"Invalid time {start_time}")
            if (start_frame - self.fpga_current_frame) < 20:
                self.logger.error("start_beamformer: time not enough in the future")
                raise ValueError("Time too early")
        self._tpm_component_manager.start_beamformer(
            start_frame, duration, subarray_beam_id, scan_id
        )

    @check_communicating
    def configure_test_generator(
        self: TileComponentManager,
        frequency0: float,
        amplitude0: float,
        frequency1: float,
        amplitude1: float,
        amplitude_noise: float,
        pulse_code: int,
        amplitude_pulse: float,
        load_time: str = None,
    ) -> None:
        """
        Test generator setting.

        :param frequency0: Tone frequency in Hz of DDC 0
        :param amplitude0: Tone peak amplitude, normalized to 31.875 ADC units,
            resolution 0.125 ADU
        :param frequency1: Tone frequency in Hz of DDC 1
        :param amplitude1: Tone peak amplitude, normalized to 31.875 ADC units,
            resolution 0.125 ADU
        :param amplitude_noise: Amplitude of pseudorandom noise
            normalized to 26.03 ADC units, resolution 0.102 ADU
        :param pulse_code: Code for pulse frequency.
            Range 0 to 7: 16,12,8,6,4,3,2 times frame frequency
        :param amplitude_pulse: pulse peak amplitude, normalized
            to 127.5 ADC units, resolution 0.5 ADU
        :param load_time: Time to start the generator. in UTC ISO formatted string.

        :raises ValueError: invalid time specified
        """
        if load_time is None:
            load_frame = 0
        else:
            load_frame = self._tile_time.frame_from_utc_time(load_time)
            if load_frame < 0:
                self.logger.error("configure_test_generator: Invalid time")
                raise ValueError("Invalid time")
            if (load_frame - self.fpga_current_frame) < 20:
                self.logger.error(
                    "configure_test_generator: time not enough in the future"
                )
                raise ValueError("Time too early")
        self._tpm_component_manager.configure_test_generator(
            frequency0,
            amplitude0,
            frequency1,
            amplitude1,
            amplitude_noise,
            pulse_code,
            amplitude_pulse,
            load_frame,
        )

    @check_communicating
    def send_data_samples(
        self: TpmDriver,
        data_type: str = "",
        start_time: str = None,
        seconds: float = 0.2,
        n_samples: int = 1024,
        sync: bool = False,
        first_channel: int = 0,
        last_channel: int = 512,
        channel_id: int = 128,
        frequency: float = 100.0,
        round_bits: int = 3,
        **params: Any,
    ) -> None:
        """
        Front end for send_xxx_data methods.

        :param data_type: sample type. "raw", "channel", "channel_continuous",
                "narrowband", "beam"
        :param start_time: UTC Time for start sending data. Default start now
        :param seconds: Delay if timestamp is not specified. Default 0.2 seconds
        :param n_samples: number of samples to send per packet
        :param sync: (raw) send synchronised antenna samples, vs. round robin
        :param first_channel: (channel) first channel to send, default 0
        :param last_channel: (channel) last channel to send, default 511
        :param channel_id: (channel_continuous) channel to send
        :param frequency: (narrowband) Sky frequency for band centre, in Hz
        :param round_bits: (narrowband) how many bits to round
        :param params: any additional keyword arguments

        :raises ValueError: error in time specification
        """
        self.logger.debug(f"send_data_samples: {params}")
        # Check if another operation is pending. Wait at most 0.2 seconds
        if self.pending_data_requests:
            time.sleep(0.2)
            if self.pending_data_requests:
                self.logger.error("Another send operation is active")
                raise ValueError("Cannot send data, another send operatin active")
        # Check for type of data to be sent to LMC
        if start_time is None:
            timestamp = 0
            seconds = params.get("seconds", 0.2)
        elif self.fpga_reference_time == 0:
            self.logger.error("Cannot send data, acquisition not started")
            raise ValueError("Cannot send data, acquisition not started")
        else:
            timestamp = self._tile_time.frame_from_utc_time(start_time)
            if timestamp < 0:
                self.logger.error(f"Invalid time: {start_time}")
                raise ValueError(f"Invalid time: {start_time}")
            seconds = 0.0

        self._tpm_component_manager.send_data_samples(
            data_type,
            timestamp,
            seconds,
            n_samples,
            sync,
            first_channel,
            last_channel,
            channel_id,
            frequency,
            round_bits,
        )

    __PASSTHROUGH = [
        "adc_rms",
        "apply_pointing_delays",
        "arp_table",
        "beamformer_table",
        "board_temperature",
        "channeliser_truncation",
        "pending_data_requests",
        "clock_present",
        "configure_40g_core",
        "configure_integrated_beam_data",
        "configure_integrated_channel_data",
        "csp_rounding",
        "current_tile_beamformer_frame",
        "erase_fpga",
        "firmware_available",
        "firmware_name",
        "firmware_version",
        "fpga1_temperature",
        "fpga2_temperature",
        "fpgas_time",
        "fpga_current_frame",
        "get_40g_configuration",
        "hardware_version",
        "initialise_beamformer",
        "is_beamformer_running",
        "is_programmed",
        "load_calibration_coefficients",
        "load_pointing_delays",
        "phase_terminal_count",
        "pll_locked",
        "pps_delay",
        "pps_present",
        "preadu_levels",
        "read_address",
        "read_register",
        "register_list",
        # "send_data_samples",
        "set_beamformer_regions",
        "set_lmc_download",
        "set_lmc_integrated_download",
        "static_delays",
        "station_id",
        "stop_beamformer",
        "stop_data_transmission",
        "stop_integrated_data",
        "sync_fpgas",
        "sysref_present",
        "test_generator_active",
        "test_generator_input_select",
        "tile_id",
        "tpm_status",
        "voltage",
        "write_address",
        "write_register",
    ]

    def __getattr__(
        self: TileComponentManager, name: str, default_value: Any = None
    ) -> Any:
        """
        Get value for an attribute not found in the usual way.

        Implemented to check against a list of attributes to pass down
        to the simulator. The intent is to avoid having to implement a
        whole lot of methods that simply call the corresponding method
        on the simulator. The only reason this is possible is because
        the simulator has much the same interface as its component
        manager.

        :param name: name of the requested attribute
        :param default_value: value to return if the attribute is not
            found

        :return: the requested attribute
        """
        if name in self.__PASSTHROUGH:
            return self._get_from_hardware(name)
        return default_value

    @check_communicating
    @check_on
    def _get_from_hardware(self: TileComponentManager, name: str) -> Any:
        """
        Get an attribute from the component (if we are communicating with it).

        :param name: name of the attribute to get.

        :return: the attribute value
        """
        # This one-liner is only a method so that we can decorate it.
        return getattr(self._tpm_component_manager, name)

    def __setattr__(self: TileComponentManager, name: str, value: Any) -> None:
        """
        Set an attribute on this tile component manager.

        This is implemented to pass writes to certain attributes to the
        underlying hardware component manager.

        :param name: name of the attribute for which the value is to be
            set
        :param value: new value of the attribute
        """
        if name in self.__PASSTHROUGH:
            self._set_in_hardware(name, value)
        else:
            super().__setattr__(name, value)

    @check_communicating
    @check_on
    def _set_in_hardware(self: TileComponentManager, name: str, value: Any) -> None:
        """
        Set an attribute in the component (if we are communicating with it).

        :param name: name of the attribute to set.
        :param value: new value for the attribute
        """
        # This one-liner is only a method so that we can decorate it.
        setattr(self._tpm_component_manager, name, value)

    #
    # Long running commands
    #
    @check_communicating
    def initialise(
        self: TileComponentManager, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Submit the initialise slow task.

        This method returns immediately after it is submitted for execution.

        :param task_callback: Update task state, defaults to None

        :return: A tuple containing a task status and a unique id string to
            identify the command
        """
        try:
            return self.submit_task(self._initialise, task_callback=task_callback)
        except ConnectionError as comm_err:
            return (TaskStatus.FAILED, f"Tile Connection Error {comm_err}")

    def _initialise(
        self: TileComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Initialise the tpm using slow command.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        try:
            self._tpm_component_manager.initialise()
        except Exception as ex:
            self.logger.error(f"error {ex}")
            if task_callback:
                task_callback(status=TaskStatus.FAILED, result=f"Exception: {ex}")
            return

        if task_abort_event and task_abort_event.is_set():
            if task_callback:
                task_callback(
                    status=TaskStatus.ABORTED, result="Initialise tpm task aborted"
                )
            return

        if task_callback:
            task_callback(
                status=TaskStatus.COMPLETED, result="Initialise tpm task has completed"
            )
            return

    @check_communicating
    def download_firmware(
        self: TileComponentManager, argin: str, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Submit the download_firmware slow task.

        This method returns immediately after it is submitted for execution.

        :param argin: can either be the design name returned from
            GetFirmwareAvailable command, or a path to a
            file
        :param task_callback: Update task state, defaults to None

        :return: A tuple containing a task status and a unique id string to
            identify the command
        """
        return self.submit_task(
            self._download_firmware, args=[argin], task_callback=task_callback
        )

    def _download_firmware(
        self: TileComponentManager,
        argin: str,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Download tpm firmware using slow command.

        :param argin: can either be the design name returned or a path to a file
        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None

        :raises NotImplementedError: Command not implemented
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        try:
            self._tpm_component_manager.download_firmware(argin)
        except NotImplementedError:
            raise NotImplementedError
        except Exception as ex:
            self.logger.error(f"error {ex}")
            if task_callback:
                task_callback(status=TaskStatus.FAILED, result=f"Exception: {ex}")
            return

        if task_abort_event and task_abort_event.is_set():
            if task_callback:
                task_callback(
                    status=TaskStatus.ABORTED,
                    result="Download tpm firmware task aborted",
                )
            return

        if task_callback:
            task_callback(
                status=TaskStatus.COMPLETED,
                result="Download tpm firmware has completed",
            )
            return

    @check_communicating
    def start_acquisition(
        self: TileComponentManager, argin: str, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Submit the start_acquisition slow task.

        :param argin: json dictionary with optional keywords

        * start_time - (str) start time
        * delay - (int) delay start

        :param task_callback: Update task state, defaults to None

        :return: A tuple containing a task status and a unique id string to
            identify the command
        """
        params = json.loads(argin)
        start_time = params.get("start_time", None)
        if start_time is None:
            start_frame = None
            delay = params.get("delay", 2)
        else:
            start_frame = self._tile_time.timestamp_from_utc_time(start_time)
            if start_frame < 0:
                self.logger.error("Invalid time")
            delay = 0

        return self.submit_task(
            self._start_acquisition,
            args=[start_frame, delay],
            task_callback=task_callback,
        )

    def _start_acquisition(
        self: TileComponentManager,
        start_time: Optional[str] = None,
        delay: Optional[int] = 2,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Start acquisition using slow command.

        :param start_time: the time at which to start data acquisition, defaults to None
        :param delay: delay start, defaults to 2
        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        :raises NotImplementedError: Command not implemented
        """
        success = False
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        try:
            success = self._tpm_component_manager.start_acquisition(start_time, delay)
        except NotImplementedError:
            raise NotImplementedError
        except Exception as ex:
            self.logger.error(f"error {ex}")
            if task_callback:
                task_callback(status=TaskStatus.FAILED, result=f"Exception: {ex}")
            return

        if task_abort_event and task_abort_event.is_set():
            if task_callback:
                task_callback(
                    status=TaskStatus.ABORTED, result="Start acquisition task aborted"
                )
            return

        if task_callback:
            if success:
                self._tile_time.set_reference_time(self.tile_reference_time)
                task_callback(
                    status=TaskStatus.COMPLETED,
                    result="Start acquisition has completed",
                )
            else:
                task_callback(
                    status=TaskStatus.FAILED, result="Start acquisition task failed"
                )
            return

    @check_communicating
    def post_synchronisation(
        self: TileComponentManager, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Submit the post_synchronisation slow task.

        This method returns immediately after it is submitted for execution.

        :param task_callback: Update task state, defaults to None

        :return: A tuple containing a task status and a unique id string to
            identify the command
        """
        return self.submit_task(self._post_synchronisation, task_callback=task_callback)

    def _post_synchronisation(
        self: TileComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Post synchronisation using slow command.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None

        :raises NotImplementedError: Command not implemented
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        try:
            self._tpm_component_manager.post_synchronisation()
        except NotImplementedError:
            raise NotImplementedError
        except Exception as ex:
            self.logger.error(f"error {ex}")
            if task_callback:
                task_callback(status=TaskStatus.FAILED, result=f"Exception: {ex}")
            return

        if task_abort_event and task_abort_event.is_set():
            if task_callback:
                task_callback(
                    status=TaskStatus.ABORTED,
                    result="Post synchronisation task aborted",
                )
            return

        if task_callback:
            task_callback(
                status=TaskStatus.COMPLETED, result="Post synchronisation has completed"
            )
            return

    def set_power_state(self: TileComponentManager, power_state: PowerState) -> None:
        """
        Set the power state of the tile.

        If power state changed, re-evaluate the tile programming state and
        updates it inside the driver. This pushes a callback if it changed.

        :param power_state: The desired power state
        """
        with self._power_state_lock:
            self.power_state = power_state
