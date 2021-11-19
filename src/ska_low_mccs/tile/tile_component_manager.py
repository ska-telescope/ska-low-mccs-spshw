# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""This module implements component management for tiles."""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional, Tuple, cast

import tango

from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import PowerMode, SimulationMode, TestMode

from ska_low_mccs import MccsDeviceProxy

from ska_low_mccs.component import (
    CommunicationStatus,
    ExtendedPowerMode,
    MccsComponentManagerProtocol,
    ObjectComponentManager,
    SwitchingComponentManager,
    check_communicating,
    check_on,
)
from ska_low_mccs.component.component_manager import MccsComponentManager
from ska_low_mccs.tile import (
    TpmDriver,
    BaseTpmSimulator,
    DynamicTpmSimulator,
    StaticTpmSimulator,
)
from ska_low_mccs.tile.tile_orchestrator import TileOrchestrator

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
        push_change_event: Optional[Callable],
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        component_fault_callback: Callable[[bool], None],
    ) -> None:
        """
        Initialise a new instance.

        :param tpm_simulator: the TPM simulator component managed by
            this component manager
        :param logger: a logger for this object to use
        :param push_change_event: method to call when the base classes
            want to send an event
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_fault_callback: callback to be called when the
            component faults (or stops faulting)
        """
        super().__init__(
            tpm_simulator,
            logger,
            push_change_event,
            communication_status_changed_callback,
            None,
            component_fault_callback,
        )

    __PASSTHROUGH = [
        "adc_rms",
        "arp_table",
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
        "firmware_available",
        "firmware_name",
        "firmware_version",
        "fpga1_temperature",
        "fpga2_temperature",
        "fpgas_time",
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
        push_change_event: Optional[Callable],
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        component_fault_callback: Callable[[bool], None],
    ) -> None:
        """
        Initialise a new instance.

        :param logger: a logger for this object to use
        :param push_change_event: method to call when the base classes
            want to send an event
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_fault_callback: callback to be called when the
            component faults (or stops faulting)
        """
        super().__init__(
            StaticTpmSimulator(
                logger,
            ),
            logger,
            push_change_event,
            communication_status_changed_callback,
            component_fault_callback,
        )


class DynamicTpmSimulatorComponentManager(_TpmSimulatorComponentManager):
    """A component manager for a dynamic TPM simulator."""

    def __init__(
        self: DynamicTpmSimulatorComponentManager,
        logger: logging.Logger,
        push_change_event: Optional[Callable],
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        component_fault_callback: Callable[[bool], None],
    ) -> None:
        """
        Initialise a new instance.

        :param logger: a logger for this object to use
        :param push_change_event: method to call when the base classes
            want to send an event
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_fault_callback: callback to be called when the
            component faults (or stops faulting)
        """
        super().__init__(
            DynamicTpmSimulator(
                logger,
            ),
            logger,
            push_change_event,
            communication_status_changed_callback,
            component_fault_callback,
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
        push_change_event: Optional[Callable],
        tpm_ip: str,
        tpm_cpld_port: int,
        tpm_version: str,
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        component_fault_callback: Callable[[bool], None],
    ) -> None:
        """
        Initialise a new instance.

        :param initial_simulation_mode: the simulation mode that the
            component should start in
        :param initial_test_mode: the simulation mode that the component
            should start in
        :param logger: a logger for this object to use
        :param push_change_event: method to call when the base classes
            want to send an event
        :param tpm_ip: the IP address of the tile
        :param tpm_cpld_port: the port at which the tile is accessed for control
        :param tpm_version: TPM version: "tpm_v1_2" or "tpm_v1_6"
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_fault_callback: callback to be called when the
            component faults (or stops faulting)
        """
        tpm_driver = TpmDriver(
            logger,
            push_change_event,
            tpm_ip,
            tpm_cpld_port,
            tpm_version,
            communication_status_changed_callback,
            component_fault_callback,
        )

        dynamic_tpm_simulator_component_manager = DynamicTpmSimulatorComponentManager(
            logger,
            push_change_event,
            communication_status_changed_callback,
            component_fault_callback,
        )

        static_tpm_simulator_component_manager = StaticTpmSimulatorComponentManager(
            logger,
            push_change_event,
            communication_status_changed_callback,
            component_fault_callback,
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
        push_change_event: Optional[Callable],
        tpm_ip: str,
        tpm_cpld_port: int,
        tpm_version: str,
        subrack_fqdn: str,
        subrack_tpm_id: int,
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        component_power_mode_changed_callback: Callable[[PowerMode], None],
        component_fault_callback: Callable[[bool], None],
        _tpm_component_manager: Optional[MccsComponentManagerProtocol] = None,
    ) -> None:
        """
        Initialise a new instance.

        :param initial_simulation_mode: the simulation mode that the
            component should start in
        :param initial_test_mode: the test mode that the component
            should start in
        :param logger: a logger for this object to use
        :param push_change_event: method to call when the base classes
            want to send an event
        :param tpm_ip: the IP address of the tile
        :param tpm_cpld_port: the port at which the tile is accessed for control
        :param tpm_version: TPM version: "tpm_v1_2" or "tpm_v1_6"
        :param subrack_fqdn: FQDN of the subrack that controls power to
            this tile
        :param subrack_tpm_id: This tile's position in its subrack
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_power_mode_changed_callback: callback to be
            called when the component power mode changes
        :param component_fault_callback: callback to be called when the
            component faults (or stops faulting)
        :param _tpm_component_manager: a tpm component manager to use
            instead of creating one. This is provided for testing
            purposes only.
        """
        self._subrack_fqdn = subrack_fqdn
        self._subrack_tpm_id = subrack_tpm_id

        self._subrack_proxy: Optional[MccsDeviceProxy] = None

        self._subrack_communication_status = CommunicationStatus.DISABLED
        self._tpm_communication_status = CommunicationStatus.DISABLED

        self._tpm_component_manager = (
            _tpm_component_manager
            or SwitchingTpmComponentManager(
                initial_simulation_mode,
                initial_test_mode,
                logger,
                push_change_event,
                tpm_ip,
                tpm_cpld_port,
                tpm_version,
                self._tpm_communication_status_changed,
                self.component_fault_changed,
            )
        )

        self._tile_orchestrator = TileOrchestrator(
            self._start_communicating_with_subrack,
            self._stop_communicating_with_subrack,
            self._start_communicating_with_tpm,
            self._stop_communicating_with_tpm,
            self._turn_off_tpm,
            self._turn_on_tpm,
            self.update_communication_status,
            self.update_component_power_mode,
            self.update_component_fault,
            logger,
        )

        super().__init__(
            logger,
            push_change_event,
            communication_status_changed_callback,
            component_power_mode_changed_callback,
            component_fault_callback,
        )

    def start_communicating(self: TileComponentManager) -> None:
        """Establish communication with the tpm and the upstream power supply."""
        self._tile_orchestrator.desire_online()

    def stop_communicating(self: TileComponentManager) -> None:
        """Establish communication with the tpm and the upstream power supply."""
        self._tile_orchestrator.desire_offline()

    @check_communicating  # TODO: orchestrator should handle this
    def off(self: TileComponentManager) -> ResultCode:
        """
        Tell the upstream power supply proxy to turn the tpm off.

        :return: a result code, or None if there was nothing to do.
        """
        return self._tile_orchestrator.desire_off()

    @check_communicating  # TODO: orchestrator should handle this
    def on(self: TileComponentManager) -> ResultCode:
        """
        Tell the upstream power supply proxy to turn the tpm off.

        :return: a result code, or None if there was nothing to do.
        """
        return self._tile_orchestrator.desire_on()

    def component_progress_changed(self: TileComponentManager, progress: int) -> None:
        """
        Handle notification that the component's progress value has changed.

        This is a callback hook, to be passed to the managed component.

        :param progress: The progress percentage of the long-running command
        """
        if self._component_progress_changed_callback is not None:
            self._component_progress_changed_callback(progress)

    def _subrack_communication_status_changed(
        self: TileComponentManager,
        communication_status: CommunicationStatus,
    ) -> None:
        """
        Handle a change in status of communication with the antenna via the APIU.

        :param communication_status: the status of communication with
            the antenna via the APIU.
        """
        self._tile_orchestrator.update_subrack_communication_status(
            communication_status
        )

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

    # TODO RCL: Convert this to a LRC. This doesn't need to be done right now.
    #           This needs an instantitation of a new class derived from
    #           DeviceComponentManager that provides its own message queue.
    #           That allows the proxy call to other Tango devices to be queued
    #           rather than blocking until the call to the Tango device has been
    #           issued and queued in that device. This becomes increasing
    #           important when we have many Tango devices.
    def _start_communicating_with_subrack(self: TileComponentManager) -> None:
        """
        Establish communication with the subrack, then start monitoring.

        This contains the actual communication logic that is enqueued to
        be run asynchronously.

        :raises ConnectionError: if the attempt to establish
            communication with the channel fails.
        """
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

        self._subrack_proxy.add_change_event_callback(
            f"tpm{self._subrack_tpm_id}PowerMode",
            self._tpm_power_mode_change_event_received,
        )
        self._tile_orchestrator.update_subrack_communication_status(
            CommunicationStatus.ESTABLISHED
        )

    def _tpm_power_mode_change_event_received(
        self: TileComponentManager,
        event_name: str,
        event_value: ExtendedPowerMode,
        event_quality: tango.AttrQuality,
    ) -> None:
        """
        Handle change in tpm power modes.

        This is a callback that is triggered by an event subscription
        on the subrack device.

        :param event_name: name of the event; will always be
            "areTpmsOn" for this callback
        :param event_value: the new attribute value
        :param event_quality: the quality of the change event
        """
        assert event_name.lower() == f"tpm{self._subrack_tpm_id}PowerMode".lower(), (
            f"subrack 'tpm{self._subrack_tpm_id}PowerMode' attribute changed callback "
            f"called but event_name is {event_name}."
        )
        self._tpm_power_mode_changed(event_value)

    def _stop_communicating_with_subrack(self: TileComponentManager) -> None:
        self._subrack_proxy = None
        self._tile_orchestrator.update_subrack_communication_status(
            CommunicationStatus.DISABLED
        )

    # TODO RCL: Convert this to a LRC
    # @enqueue
    def _turn_off_tpm(self: TileComponentManager) -> ResultCode:
        assert self._subrack_proxy is not None  # for the type checker
        ([result_code], [message]) = self._subrack_proxy.PowerOffTpm(
            self._subrack_tpm_id
        )
        # TODO better handling of result code and exceptions.
        return result_code

    # TODO RCL: Convert this to a LRC
    # @enqueue
    def _turn_on_tpm(self: TileComponentManager) -> ResultCode:
        assert self._subrack_proxy is not None  # for the type checker
        ([result_code], [message]) = self._subrack_proxy.PowerOnTpm(
            self._subrack_tpm_id
        )
        # TODO better handling of result code and exceptions.
        return result_code

    def _tpm_power_mode_changed(
        self: TileComponentManager,
        power_mode: ExtendedPowerMode,
    ) -> None:
        self._tile_orchestrator.update_tpm_power_mode(power_mode)

    def _tpm_communication_status_changed(
        self: TileComponentManager,
        communication_status: CommunicationStatus,
    ) -> None:
        """
        Handle a change in status of communication with the tpm.

        :param communication_status: the status of communication with
            the tpm.
        """
        self._tile_orchestrator.update_tpm_communication_status(communication_status)

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

    __PASSTHROUGH = [
        "adc_rms",
        "arp_table",
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
        "firmware_available",
        "firmware_name",
        "firmware_version",
        "fpga1_temperature",
        "fpga2_temperature",
        "fpgas_time",
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
