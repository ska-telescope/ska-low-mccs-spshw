# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements component management for tiles."""
from __future__ import annotations
import time
import logging
import threading
from typing import Any, Callable, Optional, Tuple, cast

import tango
from ska_tango_base.commands import ResultCode
from ska_tango_base.executor import TaskStatus
from ska_tango_base.control_model import (
    CommunicationStatus,
    PowerState,
    SimulationMode,
    TestMode,
)

from ska_low_mccs import MccsDeviceProxy
from ska_low_mccs.component import (
    MccsComponentManager,
    MccsComponentManagerProtocol,
    ObjectComponentManager,
    SwitchingComponentManager,
    check_communicating,
    check_on,
)
from ska_low_mccs.tile import (
    BaseTpmSimulator,
    DynamicTpmSimulator,
    StaticTpmSimulator,
    TileTime,
    TpmDriver,
)

from ska_low_mccs.tile.time_util import TileTime
from ska_low_mccs.tile.tile_orchestrator import TileOrchestrator
from ska_low_mccs.tile.tpm_status import TpmStatus

__all__ = [
    "DynamicTpmSimulatorComponentManager",
    "StaticTpmSimulatorComponentManager",
    "SwitchingTpmComponentManager",
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
        "get_arp_table",
        "board_temperature",
        "calculate_delay",
        "check_pending_data_requests",
        "compute_calibration_coefficients",
        "configure_40g_core",
        "configure_integrated_beam_data",
        "configure_integrated_channel_data",
        "configure_test_generator",
        "cpld_flash_write",
        "current_tile_beamformer_frame",
        "current",
        "download_firmware",
        "erase_fpga",
        "firmware_available",
        "firmware_name",
        "firmware_version",
        "fpga1_temperature",
        "fpga2_temperature",
        "fpgas_time",
        "fpga_sync_time",
        "fpga_current_frame",
        "get_40g_configuration",
        "tpm_version",
        "initialise_beamformer",
        "initialise",
        "is_beamformer_running",
        "is_programmed",
        "load_antenna_tapering",
        "load_beam_angle",
        "load_calibration_coefficients",
        "load_calibration_curve",
        "load_pointing_delay",
        "phase_terminal_count",
        "post_synchronisation",
        "pps_delay",
        "read_address",
        "read_register",
        "register_list",
        "send_beam_data",
        "send_channelised_data_continuous",
        "send_channelised_data_narrowband",
        "send_channelised_data",
        "send_raw_data_synchronised",
        "send_raw_data",
        "set_beamformer_regions",
        "set_channeliser_truncation",
        "set_csp_rounding",
        "set_lmc_download",
        "set_lmc_integrated_download",
        "set_pointing_delay",
        "set_time_delays",
        "start_acquisition",
        "start_beamformer",
        "station_id",
        "stop_beamformer",
        "stop_data_transmission",
        "stop_integrated_data",
        "switch_calibration_bank",
        "sync_fpgas",
        "test_generator_active",
        "test_generator_input_select",
        "tile_id",
        "tpm_status",
        "tweak_transceivers",
        "voltage",
        "write_address",
        "write_register",
    ]

    def __getattr__(
        self: _TpmSimulatorComponentManager,
        name: str,
        default_value: Any = None,
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
    def _get_from_component(
        self: _TpmSimulatorComponentManager,
        name: str,
    ) -> Any:
        """
        Get an attribute from the component (if we are communicating with it).

        :param name: name of the attribute to get.

        :return: the attribute value
        """
        # This one-liner is only a method so that we can decorate it.
        return getattr(self._component, name)

    def __setattr__(
        self: _TpmSimulatorComponentManager,
        name: str,
        value: Any,
    ) -> Any:
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
            StaticTpmSimulator(
                logger,
            ),
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
            DynamicTpmSimulator(
                logger,
            ),
            logger,
            max_workers,
            communication_state_changed_callback,
            component_state_changed_callback,
        )


class SwitchingTpmComponentManager(SwitchingComponentManager):
    """
    A component manager that switches between TPM simulators and TPM driver.

    The component managers provided for are
    * static TPM simulator
    * dynamic TPM simulator
    * TPM driver
    """

    def __init__(
        self: SwitchingTpmComponentManager,
        initial_simulation_mode: SimulationMode,
        initial_test_mode: TestMode,
        logger: logging.Logger,
        max_workers,
        tile_id: int,
        tpm_ip: str,
        tpm_cpld_port: int,
        tpm_version: str,
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """
        Initialise a new instance.

        :param initial_simulation_mode: the simulation mode that the
            component should start in
        :param initial_test_mode: the simulation mode that the component
            should start in
        :param logger: a logger for this object to use
        :param tile_id: the unique ID for the tile
        :param tpm_ip: the IP address of the tile
        :param tpm_cpld_port: the port at which the tile is accessed for control
        :param tpm_version: TPM version: "tpm_v1_2" or "tpm_v1_6"
        :param max_workers: Nos. of worker threads for async commands.
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be called when the
            component state changes
        """
        tpm_driver = TpmDriver(
            logger,
            max_workers,
            tile_id,
            tpm_ip,
            tpm_cpld_port,
            tpm_version,
            communication_state_changed_callback,
            component_state_changed_callback,
        )

        dynamic_tpm_simulator_component_manager = DynamicTpmSimulatorComponentManager(
            logger,
            max_workers,
            communication_state_changed_callback,
            component_state_changed_callback,
        )

        static_tpm_simulator_component_manager = StaticTpmSimulatorComponentManager(
            logger,
            max_workers,
            communication_state_changed_callback,
            component_state_changed_callback,
        )

        super().__init__(
            {
                (SimulationMode.FALSE, TestMode.NONE): tpm_driver,
                (SimulationMode.FALSE, TestMode.TEST): tpm_driver,
                (
                    SimulationMode.TRUE,
                    TestMode.NONE,
                ): dynamic_tpm_simulator_component_manager,
                (
                    SimulationMode.TRUE,
                    TestMode.TEST,
                ): static_tpm_simulator_component_manager,
            },
            (initial_simulation_mode, initial_test_mode),
        )

    @property
    def simulation_mode(self: SwitchingTpmComponentManager) -> SimulationMode:
        """
        Return the simulation mode.

        :return: the simulation mode
        """
        simulation_mode: SimulationMode  # typehint only

        (simulation_mode, _) = cast(Tuple[SimulationMode, TestMode], self.switcher_mode)
        return simulation_mode

    @simulation_mode.setter
    def simulation_mode(
        self: SwitchingTpmComponentManager,
        value: SimulationMode,
    ) -> None:
        """
        Set the simulation mode.

        :param value: the new value for the simulation mode.
        """
        simulation_mode: SimulationMode  # typehints only
        test_mode: TestMode  # typehints only

        (simulation_mode, test_mode) = cast(
            Tuple[SimulationMode, TestMode], self.switcher_mode
        )
        if simulation_mode != value:
            communicating = self.is_communicating
            if communicating:
                self.stop_communicating()
            self.switcher_mode = (value, test_mode)
            if communicating:
                self.start_communicating()

    @property
    def test_mode(self: SwitchingTpmComponentManager) -> TestMode:
        """
        Return the test mode.

        :return: the test mode
        """
        test_mode: TestMode  # typehint only
        (_, test_mode) = cast(Tuple[SimulationMode, TestMode], self.switcher_mode)
        return cast(TestMode, test_mode)

    @test_mode.setter
    def test_mode(
        self: SwitchingTpmComponentManager,
        value: TestMode,
    ) -> None:
        """
        Set the test mode.

        :param value: the new value for the test mode.
        """
        simulation_mode: SimulationMode  # typehint only
        test_mode: TestMode  # typehint only

        (simulation_mode, test_mode) = cast(
            Tuple[SimulationMode, TestMode], self.switcher_mode
        )

        if test_mode != value:
            communicating = self.is_communicating
            if communicating:
                self.stop_communicating()
            self.switcher_mode = (simulation_mode, value)
            if communicating:
                self.start_communicating()


class TileComponentManager(MccsComponentManager):
    """A component manager for a TPM (simulator or driver) and its power supply."""

    def __init__(
        self: TileComponentManager,
        initial_simulation_mode: SimulationMode,
        initial_test_mode: TestMode,
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
        _tpm_component_manager: Optional[MccsComponentManagerProtocol] = None,
    ) -> None:
        """
        Initialise a new instance.

        :param initial_simulation_mode: the simulation mode that the
            component should start in
        :param initial_test_mode: the test mode that the component
            should start in
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
        :param _tpm_component_manager: a tpm component manager to use
            instead of creating one. This is provided for testing
            purposes only.
        """
        self._subrack_fqdn = subrack_fqdn
        self._subrack_tpm_id = subrack_tpm_id
        self._power_state_lock = threading.RLock()
        self._subrack_proxy: Optional[MccsDeviceProxy] = None
        self._component_state_changed_callback = component_state_changed_callback
        self._subrack_communication_state = CommunicationStatus.DISABLED
        self._tpm_communication_state = CommunicationStatus.DISABLED

        self._tpm_component_manager = (
            _tpm_component_manager
            or SwitchingTpmComponentManager(
                initial_simulation_mode,
                initial_test_mode,
                logger,
                max_workers,
                tile_id,
                tpm_ip,
                tpm_cpld_port,
                tpm_version,
                self._tpm_communication_state_changed,
                component_state_changed_callback,
            )
        )

        self._tile_orchestrator = TileOrchestrator(
            self._start_communicating_with_subrack,
            self._stop_communicating_with_subrack,
            self._start_communicating_with_tpm,
            self._stop_communicating_with_tpm,
            self._turn_off_tpm,
            self._turn_on_tpm,
            self.update_communication_state,
            self.update_tpm_power_state,
            logger,
        )

        self._tile_time = TileTime()

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

    def off(self: TileComponentManager) -> ResultCode:
        """
        Tell the upstream power supply proxy to turn the tpm off.

        :return: a result code, or None if there was nothing to do.
        """
        return self._tile_orchestrator.desire_off()

    def on(self: TileComponentManager) -> ResultCode:
        """
        Tell the upstream power supply proxy to turn the tpm on.

        :return: a result code, or None if there was nothing to do.
        """
        return self._tile_orchestrator.desire_on()

    def standby(self: TileComponentManager) -> ResultCode:
        """
        Tell the upstream power supply proxy to turn the tpm on.

        :return: a result code, or None if there was nothing to do.
        """
        return self._tile_orchestrator.desire_standby()

    # def component_progress_changed(self: TileComponentManager, progress: int) -> None:
    #     """
    #     Handle notification that the component's progress value has changed.

    #     This is a callback hook, to be passed to the managed component.

    #     :param progress: The progress percentage of the long-running command
    #     """
    #     if self._component_progress_changed_callback is not None:
    #         self._component_progress_changed_callback(progress)

    def _subrack_communication_state_changed(
        self: TileComponentManager,
        communication_state: CommunicationStatus,
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
    def _turn_off_tpm(self: TileComponentManager) -> ResultCode:
        assert self._subrack_proxy is not None  # for the type checker
        ([result_code], _) = self._subrack_proxy.PowerOffTpm(self._subrack_tpm_id)
        # TODO better handling of result code and exceptions.
        if result_code > 2:
            self.logger.error(
                f"Turn off tpm {self._subrack_tpm_id} returns {result_code}"
            )
        return result_code

    # Converted to a LRC, in subrack
    def _turn_on_tpm(self: TileComponentManager) -> ResultCode:
        assert self._subrack_proxy is not None  # for the type checker
        ([result_code], _) = self._subrack_proxy.PowerOnTpm(self._subrack_tpm_id)
        # TODO better handling of result code and exceptions.
        if result_code > 2:
            self.logger.error(
                f"Turn on tpm {self._subrack_tpm_id} returns {result_code}"
            )
        return result_code

    def _tpm_power_state_changed(
        self: TileComponentManager,
        power_state: PowerState,
    ) -> None:
        self._tile_orchestrator.update_tpm_power_state(power_state)

    def _tpm_communication_state_changed(
        self: TileComponentManager,
        communication_state: CommunicationStatus,
    ) -> None:
        """
        Handle a change in status of communication with the tpm.

        :param communication_state: the status of communication with
            the tpm.
        """
        self._tile_orchestrator.update_tpm_communication_state(communication_state)

    def update_tpm_power_state(
        self: TileComponentManager, power_state: Optional[PowerState]
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
        self.set_power_state(power_state["power_state"])
        #self._component_state_changed_callback(power_state)
        self.logger.debug(
            f"power state: {self.power_state}, communication status: {self.communication_state}"
        )
        if self.communication_state == CommunicationStatus.ESTABLISHED:
            if power_state["power_state"] == PowerState.ON:
                if (not self.is_programmed) or (
                    self.tpm_status == TpmStatus.PROGRAMMED
                ):
                    self.initialise()
                self._tile_time.set_reference_time(self.tile_reference_time)
            if power_state == PowerState.STANDBY:
                self.erase_fpga()
                self._tile_time.set_reference_time(0)

    @property
    def simulation_mode(self: TileComponentManager) -> SimulationMode:
        """
        Return the simulation mode.

        :return: the simulation mode
        """
        return cast(
            SwitchingTpmComponentManager, self._tpm_component_manager
        ).simulation_mode

    @simulation_mode.setter
    def simulation_mode(self: TileComponentManager, value: SimulationMode) -> None:
        """
        Set the simulation mode.

        :param value: the new value for the simulation mode.
        """
        cast(
            SwitchingTpmComponentManager, self._tpm_component_manager
        ).simulation_mode = value

    @property
    def test_mode(self: TileComponentManager) -> TestMode:
        """
        Return the test mode.

        :return: the test mode
        """
        return cast(SwitchingTpmComponentManager, self._tpm_component_manager).test_mode

    @test_mode.setter
    def test_mode(
        self: TileComponentManager,
        value: TestMode,
    ) -> None:
        """
        Set the test mode.

        :param value: the new value for the test mode.
        """
        cast(
            SwitchingTpmComponentManager, self._tpm_component_manager
        ).test_mode = value

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
            status = cast(
                SwitchingTpmComponentManager, self._tpm_component_manager
            ).tpm_status
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
        reference_time = self.fpga_sync_time
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
        self._tile_time.set_reference_time(self.fpga_sync_time)
        return self._tile_time.format_time_from_frame(self.fpga_current_frame)

    __PASSTHROUGH = [
        "adc_rms",
        "get_arp_table",
        "board_temperature",
        "calculate_delay",
        "check_pending_data_requests",
        "compute_calibration_coefficients",
        "configure_40g_core",
        "configure_integrated_beam_data",
        "configure_integrated_channel_data",
        "configure_test_generator",
        "cpld_flash_write",
        "current_tile_beamformer_frame",
        "current",
        "download_firmware",
        "erase_fpga",
        "firmware_available",
        "firmware_name",
        "firmware_version",
        "fpga1_temperature",
        "fpga2_temperature",
        "fpgas_time",
        "fpga_sync_time",
        "fpga_current_frame",
        "get_40g_configuration",
        "hardware_version",
        "initialise_beamformer",
        "initialise",
        "is_beamformer_running",
        "is_programmed",
        "load_antenna_tapering",
        "load_beam_angle",
        "load_calibration_coefficients",
        "load_calibration_curve",
        "load_pointing_delay",
        "phase_terminal_count",
        "post_synchronisation",
        "pps_delay",
        "read_address",
        "read_register",
        "register_list",
        "send_beam_data",
        "send_channelised_data_continuous",
        "send_channelised_data_narrowband",
        "send_channelised_data",
        "send_raw_data_synchronised",
        "send_raw_data",
        "set_beamformer_regions",
        "set_channeliser_truncation",
        "set_csp_rounding",
        "set_lmc_download",
        "set_lmc_integrated_download",
        "set_pointing_delay",
        "set_time_delays",
        "start_acquisition",
        "start_beamformer",
        "station_id",
        "stop_beamformer",
        "stop_data_transmission",
        "stop_integrated_data",
        "switch_calibration_bank",
        "sync_fpgas",
        "test_generator_active",
        "test_generator_input_select",
        "tile_id",
        "tweak_transceivers",
        "voltage",
        "write_address",
        "write_register",
    ]

    def __getattr__(
        self: TileComponentManager,
        name: str,
        default_value: Any = None,
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

    def __setattr__(
        self: TileComponentManager,
        name: str,
        value: Any,
    ) -> None:
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

    def initialise(
        self: TileComponentManager,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the initialise slow task.

        This method returns immediately after it is submitted for execution.

        :param task_callback: Update task state, defaults to None

        :return: A tuple containing a task status and a unique id string to identify the command
        """
        return self.submit_task(self._initialise, task_callback=task_callback)

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
            cast(
                SwitchingTpmComponentManager, self._tpm_component_manager
            ).initialise()
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
                status=TaskStatus.COMPLETED,
                result="Initialise tpm task has completed",
            )
            return

    def download_firmware(
        self: TileComponentManager,
        argin: str,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the download_firmware slow task.

        This method returns immediately after it is submitted for execution.

        :param argin: can either be the design name returned from
            :py:meth:`.GetFirmwareAvailable` command, or a path to a
            file
        :param task_callback: Update task state, defaults to None

        :return: A tuple containing a task status and a unique id string to identify the command
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

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        try:
            cast(
                SwitchingTpmComponentManager, self._tpm_component_manager
            ).download_firmware(argin)
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

    def get_arp_table(
        self: TileComponentManager,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the get arp_table slow task.

        This method returns immediately after it is submitted for execution.

        :param task_callback: Update task state, defaults to None

        :return: A tuple containing a task status and a unique id string to identify the command
        """
        return self.submit_task(self._get_arp_table, task_callback=task_callback)

    def _get_arp_table(
        self: TileComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Get arp table using slow command.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        try:
            cast(SwitchingTpmComponentManager, self._tpm_component_manager).get_arp_table()
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
                    status=TaskStatus.ABORTED, result="Arp table task aborted"
                )
            return

        if task_callback:
            task_callback(
                status=TaskStatus.COMPLETED,
                result="Arp table has completed",
            )
            return

    def start_acquisition(
        self: TileComponentManager,
        argin: str,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the start_acquisition slow task.

        :param argin: json dictionary with optional keywords

        * StartTime - (int) start time
        * Delay - (int) delay start

        :param task_callback: Update task state, defaults to None
        :return: A tuple containing a task status and a unique id string to identify the command
        """
        return self.submit_task(
            self._start_acquisition, args=[argin], task_callback=task_callback
        )

    def _start_acquisition(
        self: TileComponentManager,
        argin: str,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Start acquisition using slow command.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        try:
            cast(
                SwitchingTpmComponentManager, self._tpm_component_manager
            ).start_acquisition(argin)
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
            task_callback(
                status=TaskStatus.COMPLETED,
                result="Start acquisition has completed",
            )
            return

    def cpld_flash_write(
        self: TileComponentManager,
        argin: str,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the cpld_flash_write slow task.

        This method returns immediately after it is submitted for execution.

        :param argin: is the path to a file containing the required CPLD firmware
        :param task_callback: Update task state, defaults to None

        :return: A tuple containing a task status and a unique id string to identify the command
        """
        return self.submit_task(
            self._cpld_flash_write, args=[argin], task_callback=task_callback
        )

    def _cpld_flash_write(
        self: TileComponentManager,
        bitfile: str,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Cpld flash write using slow command.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        try:
            cast(
                SwitchingTpmComponentManager, self._tpm_component_manager
            ).cpld_flash_write(bitfile)
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
                    status=TaskStatus.ABORTED, result="Cpld flash write task aborted"
                )
            return

        if task_callback:
            task_callback(
                status=TaskStatus.COMPLETED,
                result="Cpld flash write has completed",
            )
            return

    def post_synchronisation(
        self: TileComponentManager,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the post_synchronisation slow task.

        This method returns immediately after it is submitted for execution.

        :param task_callback: Update task state, defaults to None

        :return: A tuple containing a task status and a unique id string to identify the command
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
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        try:
            cast(
                SwitchingTpmComponentManager, self._tpm_component_manager
            ).post_synchronisation()
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
                status=TaskStatus.COMPLETED,
                result="Post synchronisation has completed",
            )
            return

    def sync_fpgas(
        self: TileComponentManager,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the sync_fpgas slow task.

        This method returns immediately after it is submitted for execution.

        :param task_callback: Update task state, defaults to None

        :return: A tuple containing a task status and a unique id string to identify the command
        """
        return self.submit_task(self._sync_fpgas, task_callback=task_callback)

    def _sync_fpgas(
        self: TileComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Fpgas synchronization using slow command.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        try:
            cast(SwitchingTpmComponentManager, self._tpm_component_manager).sync_fpgas()
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
                    result="Fpgas synchronization task aborted",
                )
            return

        if task_callback:
            task_callback(
                status=TaskStatus.COMPLETED,
                result="Fpgas synchronization has completed",
            )
            return

    def set_power_state(self: TileComponentManager, power_state: PowerState) -> None:
        """
        Set the power state of the tile.

        :param power_state: The desired power state
        """
        with self._power_state_lock:
            self.power_state = power_state
