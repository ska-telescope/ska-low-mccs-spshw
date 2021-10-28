# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""This module implements the MCCS PaSD bus device."""

from __future__ import annotations

import json
from typing import Tuple, List, Optional

import tango
from tango.server import attribute, command

from ska_tango_base.base import SKABaseDevice
from ska_tango_base.commands import BaseCommand, ResponseCommand, ResultCode
from ska_tango_base.control_model import HealthState, PowerMode, SimulationMode

from ska_low_mccs import release
from ska_low_mccs.component import CommunicationStatus
from ska_low_mccs.pasd_bus import (
    PasdBusComponentManager,
    PasdBusHealthModel,
)

__all__ = ["MccsPasdBus", "main"]


NUMBER_OF_ANTENNAS_PER_STATION = 256
NUMBER_OF_SMARTBOXES_PER_STATION = 24
NUMBER_OF_FNDH_PORTS = 28

DevVarLongStringArrayType = Tuple[List[ResultCode], List[Optional[str]]]


def create_return(success: Optional[bool], action: str) -> tuple[ResultCode, str]:
    """
    Create a tuple containing the ResultCode and status message.

    :param success: whether execution of the action was successful. This
        may be None, in which case the action was not performed due to
        redundancy (i.e. it was already done).
    :param action: Informal description of the action that the command
        performs, for use in constructing a message

    :return: A tuple containing a return code and a string
        message indicating status. The message is for
        information purpose only.
    """
    if success is None:
        return (ResultCode.OK, f"PaSD bus '{action}' is redundant")
    elif success:
        return (ResultCode.OK, f"PaSD bus '{action}' successful")
    else:
        return (ResultCode.FAILED, f"PaSD bus '{action}' failed")


class MccsPasdBus(SKABaseDevice):
    """An implementation of a PaSD bus Tango device for MCCS."""

    # ---------------
    # Initialisation
    # ---------------
    def init_device(self: MccsPasdBus) -> None:
        """
        Initialise the device.

        This is overridden here to change the Tango serialisation model.
        """
        util = tango.Util.instance()
        util.set_serial_model(tango.SerialModel.NO_SYNC)
        super().init_device()

    def _init_state_model(self: MccsPasdBus) -> None:
        super()._init_state_model()
        self._health_state = HealthState.UNKNOWN  # InitCommand.do() does this too late.
        self._health_model = PasdBusHealthModel(self.health_changed)
        self.set_change_event("healthState", True, False)

    def create_component_manager(
        self: MccsPasdBus,
    ) -> PasdBusComponentManager:
        """
        Create and return a component manager for this device.

        :return: a component manager for this device.
        """
        return PasdBusComponentManager(
            SimulationMode.TRUE,
            self.logger,
            self._component_communication_status_changed,
            self._component_fault,
        )

    def init_command_objects(self: MccsPasdBus) -> None:
        """Initialise the command handlers for commands supported by this device."""
        super().init_command_objects()

        for (command_name, command_object) in [
            ("ReloadDatabase", self.ReloadDatabaseCommand),
            ("GetFndhInfo", self.GetFndhInfoCommand),
            ("TurnFndhServiceLedOn", self.TurnFndhServiceLedOnCommand),
            ("TurnFndhServiceLedOff", self.TurnFndhServiceLedOffCommand),
            ("GetSmartboxInfo", self.GetSmartboxInfoCommand),
            ("TurnSmartboxOn", self.TurnSmartboxOnCommand),
            ("TurnSmartboxOff", self.TurnSmartboxOffCommand),
            ("TurnSmartboxServiceLedOn", self.TurnSmartboxServiceLedOnCommand),
            ("TurnSmartboxServiceLedOff", self.TurnSmartboxServiceLedOffCommand),
            ("GetAntennaInfo", self.GetAntennaInfoCommand),
            ("ResetAntennaBreaker", self.ResetAntennaBreakerCommand),
            ("TurnAntennaOn", self.TurnAntennaOnCommand),
            ("TurnAntennaOff", self.TurnAntennaOffCommand),
        ]:
            self.register_command_object(
                command_name,
                command_object(
                    self.component_manager, self.op_state_model, self.logger
                ),
            )

    class InitCommand(SKABaseDevice.InitCommand):
        """
        A class for :py:class:`~.MccsPasdBus`'s Init command.

        The :py:meth:`~.MccsPasdBus.InitCommand.do` method below is
        called upon :py:class:`~.MccsPasdBus`'s initialisation.
        """

        def do(  # type: ignore[override]
            self: MccsPasdBus.InitCommand,
        ) -> tuple[ResultCode, str]:
            """
            Initialise the attributes and properties of the MccsPasdBus.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            device = self.target

            device._build_state = release.get_release_info()
            device._version_id = release.version

            # The health model updates our health, but then the base class super().do()
            # overwrites it with OK, so we need to update this again.
            # TODO: This needs to be fixed in the base classes.
            device._health_state = device._health_model.health_state

            return super().do()

    # ----------
    # Callbacks
    # ----------
    def _component_communication_status_changed(
        self: MccsPasdBus,
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

    def _component_power_mode_changed(self: MccsPasdBus, power_mode: PowerMode) -> None:
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
        self: MccsPasdBus,
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
                self._component_power_mode_changed(power_mode)
            self._health_model.component_fault(False)

    def health_changed(self: MccsPasdBus, health: HealthState) -> None:
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
    @attribute(dtype=("float",), max_dim_x=2, label="fndhPsu48vVoltages")
    def fndhPsu48vVoltages(self: MccsPasdBus) -> list[float]:
        """
        Return the output voltages on the two 48V DC power supplies, in voltes.

        :return: the output voltages on the two 48V DC power supplies,
             in volts.
        """
        return self.component_manager.fndh_psu48v_voltages

    @attribute(dtype=float, label="fndhPsu5vVoltage")
    def fndhPsu5vVoltage(self: MccsPasdBus) -> float:
        """
        Return the output voltage on the 5V power supply, in volts.

        :return: the output voltage on the 5V power supply, in volts.
        """
        return self.component_manager.fndh_psu5v_voltage

    @attribute(dtype=float, label="fndhPsu48vCurrent")
    def fndhPsu48vCurrent(self: MccsPasdBus) -> float:
        """
        Return the total current on the 48V DC bus, in amperes.

        :return: the total current on the 48V DC bus, in amperes.
        """
        return self.component_manager.fndh_psu48v_current

    @attribute(dtype=float, label="fndhPsu48vTemperature")
    def fndhPsu48vTemperature(self: MccsPasdBus) -> float:
        """
        Return the common temperature for both 48V power supplies, in celcius.

        :return: the common temperature for both 48V power supplies, in celcius.
        """
        return self.component_manager.fndh_psu48v_temperature

    @attribute(dtype=float, label="fndhPsu5vTemperature")
    def fndhPsu5vTemperature(self: MccsPasdBus) -> float:
        """
        Return the temperature of the 5V power supply, in celcius.

        :return: the temperature of the 5V power supply, in celcius.
        """
        return self.component_manager.fndh_psu5v_temperature

    @attribute(dtype=float, label="fndhPcbTemperature")
    def fndhPcbTemperature(self: MccsPasdBus) -> float:
        """
        Return the temperature of the FNDH's PCB, in celcius.

        :return: the temperature of the FNDH's PCB, in celcius.
        """
        return self.component_manager.fndh_pcb_temperature

    @attribute(dtype=float, label="fndhOutsideTemperature")
    def fndhOutsideTemperature(self: MccsPasdBus) -> float:
        """
        Return the temperature outside the FNDH, in celcius.

        :return: the temperature outside the FNDH, in celcius.
        """
        return self.component_manager.fndh_pcb_temperature

    @attribute(dtype=str, label="fndhStatus")
    def fndhStatus(self: MccsPasdBus) -> str:
        """
        Return the status of the FNDH.

        :return: the status of the FNDH
        """
        return self.component_manager.fndh_status

    @attribute(dtype=bool, label="fndhServiceLedOn")
    def fndhServiceLedOn(self: MccsPasdBus) -> bool:
        """
        Whether the FNDH's blue service indicator LED is on.

        :return: whether the FNDH's blue service indicator LED is on.
        """
        return self.component_manager.fndh_service_led_on

    @fndhServiceLedOn.write  # type: ignore[no-redef]
    def fndhServiceLedOn(self: MccsPasdBus, led_on: bool) -> None:
        """
        Turn on/off the FNDH's blue service indicator LED.

        :param led_on: whether the LED should be on.
        """
        self.component_manager.set_fndh_service_led_on(led_on)

    @attribute(
        dtype=("DevBoolean",),
        max_dim_x=NUMBER_OF_FNDH_PORTS,
        label="fndhPortsPowerSensed",
    )
    def fndhPortsPowerSensed(self: MccsPasdBus) -> list[bool]:
        """
        Return the actual power state of each FNDH port.

        :return: the actual power state of each FNDH port.
        """
        return self.component_manager.fndh_ports_power_sensed

    @attribute(
        dtype=("DevBoolean",),
        max_dim_x=NUMBER_OF_FNDH_PORTS,
        label="fndhPortsConnected",
    )
    def fndhPortsConnected(self: MccsPasdBus) -> list[bool]:
        """
        Return whether there is a smartbox connected to each FNDH port.

        :return: whether there is a smartbox connected to each FNDH
            port.
        """
        return self.component_manager.fndh_ports_connected

    @attribute(
        dtype=("DevBoolean",),
        max_dim_x=NUMBER_OF_FNDH_PORTS,
        label="fndhPortsForced",
    )
    def fndhPortsForced(self: MccsPasdBus) -> list[bool]:
        """
        Return whether each FNDH port has had its power locally forced.

        :return: whether each FNDH port has had its power locally
            forced.
        """
        return [
            forcing is not None for forcing in self.component_manager.fndh_port_forcings
        ]

    @attribute(
        dtype=("DevBoolean",),
        max_dim_x=NUMBER_OF_FNDH_PORTS,
        label="fndhPortsDesiredPowerOnline",
    )
    def fndhPortsDesiredPowerOnline(self: MccsPasdBus) -> list[bool]:
        """
        Return whether each FNDH port is desired to be powered when controlled by MCCS.

        :return: whether each FNDH port is desired to be powered when
            controlled by MCCS
        """
        return self.component_manager.fndh_ports_desired_power_online

    @attribute(
        dtype=("DevBoolean",),
        max_dim_x=NUMBER_OF_FNDH_PORTS,
        label="fndhPortsDesiredPowerOffline",
    )
    def fndhPortsDesiredPowerOffline(self: MccsPasdBus) -> list[bool]:
        """
        Return whether each FNDH port should be powered when MCCS control has been lost.

        :return: whether each FNDH port is desired to be powered when
            MCCS control has been lost
        """
        return self.component_manager.fndh_ports_desired_power_offline

    @attribute(
        dtype=("float",),
        max_dim_x=NUMBER_OF_SMARTBOXES_PER_STATION,
        label="smartboxInputVoltages",
    )
    def smartboxInputVoltages(self: MccsPasdBus) -> list[float]:
        """
        Return each smartbox's power input voltage, in volts.

        :return: each smartbox's power input voltage, in volts.
        """
        return self.component_manager.smartbox_input_voltages

    @attribute(
        dtype=("float",),
        max_dim_x=NUMBER_OF_SMARTBOXES_PER_STATION,
        label="smartboxPowerSupplyOutputVoltages",
    )
    def smartboxPowerSupplyOutputVoltages(self: MccsPasdBus) -> list[float]:
        """
        Return each smartbox's power supply output voltage, in volts.

        :return: each smartbox's power supply output voltage, in volts.
        """
        return self.component_manager.smartbox_power_supply_output_voltages

    @attribute(
        dtype=("DevString",),
        max_dim_x=NUMBER_OF_SMARTBOXES_PER_STATION,
        label="smartboxStatuses",
    )
    def smartboxStatuses(self: MccsPasdBus) -> list[str]:
        """
        Return each smartbox's status.

        :return: each smartbox's status.
        """
        return self.component_manager.smartbox_statuses

    @attribute(
        dtype=("float",),
        max_dim_x=NUMBER_OF_SMARTBOXES_PER_STATION,
        label="smartboxPowerSupplyTemperatures",
    )
    def smartboxPowerSupplyTemperatures(self: MccsPasdBus) -> list[float]:
        """
        Return each smartbox's power supply temperature.

        :return: each smartbox's power supply temperature.
        """
        return self.component_manager.smartbox_power_supply_temperatures

    @attribute(
        dtype=("float",),
        max_dim_x=NUMBER_OF_SMARTBOXES_PER_STATION,
        label="smartboxOutsideTemperatures",
    )
    def smartboxOutsideTemperatures(self: MccsPasdBus) -> list[float]:
        """
        Return each smartbox's outside temperature.

        :return: each smartbox's outside temperature.
        """
        return self.component_manager.smartbox_outside_temperatures

    @attribute(
        dtype=("float",),
        max_dim_x=NUMBER_OF_SMARTBOXES_PER_STATION,
        label="smartboxPcbTemperatures",
    )
    def smartboxPcbTemperatures(self: MccsPasdBus) -> list[float]:
        """
        Return each smartbox's PCB temperature.

        :return: each smartbox's PCB temperature.
        """
        return self.component_manager.smartbox_pcb_temperatures

    @attribute(
        dtype=("DevBoolean",),
        max_dim_x=NUMBER_OF_SMARTBOXES_PER_STATION,
        label="smartboxServiceLedsOn",
    )
    def smartboxServiceLedsOn(self: MccsPasdBus) -> list[bool]:
        """
        Return whether each smartbox's blue service LED is on.

        :return: a list of booleans indicating whether each smartbox's
            blue service LED is on.
        """
        return self.component_manager.smartbox_service_leds_on

    @attribute(
        dtype=("int",),
        max_dim_x=NUMBER_OF_SMARTBOXES_PER_STATION,
        label="smartboxFndhPorts",
    )
    def smartboxFndhPorts(self: MccsPasdBus) -> list[int]:
        """
        Return each smartbox's FNDH port.

        :return: each smartbox's FNDH port.
        """
        return self.component_manager.smartbox_fndh_ports

    @attribute(
        dtype=("DevBoolean",),
        max_dim_x=NUMBER_OF_SMARTBOXES_PER_STATION,
        label="smartboxesDesiredPowerOnline",
    )
    def smartboxDesiredPowerOnline(self: MccsPasdBus) -> list[bool]:
        """
        Return whether each smartbox should be on when the PaSD is under MCCS control.

        :return: whether each smartbox should be on when the PaSD is
            under MCCS control.
        """
        return self.component_manager.smartbox_desired_power_online

    @attribute(
        dtype=("DevBoolean",),
        max_dim_x=NUMBER_OF_SMARTBOXES_PER_STATION,
        label="smartboxesDesiredPowerOffline",
    )
    def smartboxDesiredPowerOffline(self: MccsPasdBus) -> list[bool]:
        """
        Return whether each smartbox should be on when MCCS control of the PaSD is lost.

        :return: whether each smartbox should be on when MCCS control of
            the PaSD is lost.
        """
        return self.component_manager.smartbox_desired_power_offline

    @attribute(
        dtype=("DevBoolean",),
        max_dim_x=NUMBER_OF_ANTENNAS_PER_STATION,
        label="antennasOnline",
    )
    def antennasOnline(self: MccsPasdBus) -> list[bool]:
        """
        Return whether each antenna is online.

        :return: a list of booleans indicating whether each antenna is
            online
        """
        return self.component_manager.antennas_online

    @attribute(
        dtype=("DevBoolean",),
        max_dim_x=NUMBER_OF_ANTENNAS_PER_STATION,
        label="antennasForced",
    )
    def antennasForced(self: MccsPasdBus) -> list[bool]:
        """
        Return whether each antenna is forced.

        :return: a list of booleans indicating whether each antenna is
            forces
        """
        return [
            forcing is not None for forcing in self.component_manager.antenna_forcings
        ]

    @attribute(
        dtype=("DevBoolean",),
        max_dim_x=NUMBER_OF_ANTENNAS_PER_STATION,
        label="antennasTripped",
    )
    def antennasTripped(self: MccsPasdBus) -> list[bool]:
        """
        Return whether each antenna has had its breaker tripped.

        :return: a list of booleans indicating whether each antenna has
            had its breaker tripped
        """
        return self.component_manager.antennas_tripped

    @attribute(
        dtype=("DevBoolean",),
        max_dim_x=NUMBER_OF_ANTENNAS_PER_STATION,
        label="antennaPowerStates",
    )
    def antennasPowerSensed(self: MccsPasdBus) -> list[bool]:
        """
        Return whether each antenna is currently powered on.

        :return: a list of booleans indicating whether each antenna is
            currently powered on
        """
        return self.component_manager.antennas_power_sensed

    @attribute(
        dtype=("DevBoolean",),
        max_dim_x=NUMBER_OF_ANTENNAS_PER_STATION,
        label="antennasDesiredPowerOnline",
    )
    def antennasDesiredPowerOnline(self: MccsPasdBus) -> list[bool]:
        """
        Return whether each antenna is desired to be on when it is online.

        :return: a list of booleans indicating whether each antenna is
            desired to be on when it is online.
        """
        return self.component_manager.antennas_desired_on_online

    @attribute(
        dtype=("DevBoolean",),
        max_dim_x=NUMBER_OF_ANTENNAS_PER_STATION,
        label="antennasDesiredPowerOffline",
    )
    def antennasDesiredPowerOffline(self: MccsPasdBus) -> list[bool]:
        """
        Return whether each antenna is desired to be on when it is offline.

        :return: a list of booleans indicating whether each antenna is
            desired to be on when it is offline.
        """
        return self.component_manager.antennas_desired_on_offline

    @attribute(
        dtype=("float",),
        max_dim_x=NUMBER_OF_ANTENNAS_PER_STATION,
        label="antennaCurrents",
    )
    def antennaCurrents(self: MccsPasdBus) -> list[float]:
        """
        Return the current at each antenna's power port, in amps.

        :return: the current at each antenna's power port, in amps
        """
        return self.component_manager.antenna_currents

    # ----------
    # Commands
    # ----------
    class ReloadDatabaseCommand(ResponseCommand):
        """Class for handling the ReloadDatabase command."""

        def do(  # type: ignore[override]
            self: MccsPasdBus.ReloadDatabaseCommand,
        ) -> tuple[ResultCode, str]:
            """
            Implement py:meth:`.MccsPasdBus.ReloadDatabase` command.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            component_manager = self.target
            success = component_manager.reload_database()
            return create_return(success, "database reload")

    @command(dtype_out="DevVarLongStringArray")
    def ReloadDatabase(self: MccsPasdBus) -> DevVarLongStringArrayType:
        """
        Return information about the FNDH.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("ReloadDatabase")
        (result_code, message) = handler()
        return ([result_code], [message])

    class GetFndhInfoCommand(BaseCommand):
        """Class for handling the GetFndhInfo command."""

        def do(self: MccsPasdBus.GetFndhInfoCommand) -> dict:  # type: ignore[override]
            """
            Implement py:meth:`.MccsPasdBus.GetFndhInfo` command.

            :return: A dictionary containing information about the FNDH.
            """
            component_manager = self.target
            return component_manager.get_fndh_info()

    @command(dtype_out=str)
    def GetFndhInfo(self: MccsPasdBus) -> str:
        """
        Return information about the FNDH.

        :return: a JSON string encoding a dictionary containing
            information about the FNDH.
        """
        handler = self.get_command_object("GetFndhInfo")
        fndh_info = handler()
        return json.dumps(fndh_info)

    class TurnFndhServiceLedOnCommand(ResponseCommand):
        """The command class for the TurnFndhServiceLedOn command."""

        def do(  # type: ignore[override]
            self: MccsPasdBus.TurnFndhServiceLedOnCommand,
        ) -> tuple[ResultCode, str]:
            """
            Implement TurnFndhServiceLedOn command functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            component_manager = self.target
            success = component_manager.set_fndh_service_led_on(True)
            return create_return(success, "FNDH service LED on")

    @command(dtype_out="DevVarLongStringArray")
    def TurnFndhServiceLedOn(self: MccsPasdBus) -> DevVarLongStringArrayType:
        """
        Turn on an FNDH's blue service LED.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("TurnFndhServiceLedOn")
        (result_code, message) = handler()
        return ([result_code], [message])

    class TurnFndhServiceLedOffCommand(ResponseCommand):
        """The command class for the TurnFndhServiceLedOff command."""

        def do(  # type: ignore[override]
            self: MccsPasdBus.TurnFndhServiceLedOffCommand,
        ) -> tuple[ResultCode, str]:
            """
            Implement TurnFndhServiceLedOff command functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            component_manager = self.target
            success = component_manager.set_fndh_service_led_on(False)
            return create_return(success, "FNDH service LED off")

    @command(dtype_out="DevVarLongStringArray")
    def TurnFndhServiceLedOff(self: MccsPasdBus) -> DevVarLongStringArrayType:
        """
        Turn off an FNDH's blue service LED.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("TurnFndhServiceLedOff")
        (result_code, message) = handler()
        return ([result_code], [message])

    class GetSmartboxInfoCommand(BaseCommand):
        """Class for handling the GetSmartboxInfo command."""

        def do(  # type: ignore[override]
            self: MccsPasdBus.GetSmartboxInfoCommand, argin: int
        ) -> dict:
            """
            Implement py:meth:`.MccsPasdBus.GetSmartboxInfo` command.

            :param argin: the smartbox id

            :return: A dictionary containing information about the
                smartbox.
            """
            component_manager = self.target
            return component_manager.get_smartbox_info(argin)

    @command(dtype_in="DevULong", dtype_out=str)
    def GetSmartboxInfo(self: MccsPasdBus, argin: int) -> str:
        """
        Return information about a smartbox.

        :param argin: the smartbox id

        :return: a JSON string encoding a dictionary containing
            information about the smartbox.
        """
        handler = self.get_command_object("GetSmartboxInfo")
        smartbox_info = handler(argin)
        return json.dumps(smartbox_info)

    class TurnSmartboxOnCommand(ResponseCommand):
        """The command class for the TurnSmartboxOn command."""

        def do(  # type: ignore[override]
            self: MccsPasdBus.TurnSmartboxOnCommand, argin: int
        ) -> tuple[ResultCode, str]:
            """
            Implement TurnSmartboxOn command functionality.

            :param argin: the logical id of the smartbox that is to be
                turned off

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            component_manager = self.target
            success = component_manager.turn_smartbox_on(argin)
            return create_return(success, f"smartbox {argin} on")

    @command(dtype_in="DevULong", dtype_out="DevVarLongStringArray")
    def TurnSmartboxOn(self: MccsPasdBus, argin: int) -> DevVarLongStringArrayType:
        """
        Turn on a smartbox.

        :param argin: id of the smartbox to be turned on

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("TurnSmartboxOn")
        (result_code, message) = handler(argin)
        return ([result_code], [message])

    class TurnSmartboxOffCommand(ResponseCommand):
        """The command class for the TurnSmartboxOff command."""

        def do(  # type: ignore[override]
            self: MccsPasdBus.TurnSmartboxOffCommand, argin: int
        ) -> tuple[ResultCode, str]:
            """
            Implement TurnSmartboxOff command functionality.

            :param argin: the logical id of the smartbox that is to be
                turned off

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            component_manager = self.target
            success = component_manager.turn_smartbox_off(argin)
            return create_return(success, f"smartbox {argin} off")

    @command(dtype_in="DevULong", dtype_out="DevVarLongStringArray")
    def TurnSmartboxOff(self: MccsPasdBus, argin: int) -> DevVarLongStringArrayType:
        """
        Turn off a smartbox.

        :param argin: id of the smartbox to be turned off

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("TurnSmartboxOff")
        (result_code, message) = handler(argin)
        return ([result_code], [message])

    class TurnSmartboxServiceLedOnCommand(ResponseCommand):
        """The command class for the TurnSmartboxServiceLedOn command."""

        def do(  # type: ignore[override]
            self: MccsPasdBus.TurnSmartboxServiceLedOnCommand, argin: int
        ) -> tuple[ResultCode, str]:
            """
            Implement TurnSmartboxServiceLedOn command functionality.

            :param argin: the logical id of the smartbox whose blue
                service LED is to be turned on

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            component_manager = self.target
            success = component_manager.turn_smartbox_service_led_on(argin)
            return create_return(success, f"smartbox {argin} service LED on")

    @command(dtype_in="DevULong", dtype_out="DevVarLongStringArray")
    def TurnSmartboxServiceLedOn(
        self: MccsPasdBus, argin: int
    ) -> DevVarLongStringArrayType:
        """
        Turn on a smartbox's blue service LED.

        :param argin: id of the smartbox whose blue service LED is to be
            turned on

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("TurnSmartboxServiceLedOn")
        (result_code, message) = handler(argin)
        return ([result_code], [message])

    class TurnSmartboxServiceLedOffCommand(ResponseCommand):
        """The command class for the TurnSmartboxServiceLedOff command."""

        def do(  # type: ignore[override]
            self: MccsPasdBus.TurnSmartboxServiceLedOffCommand, argin: int
        ) -> tuple[ResultCode, str]:
            """
            Implement TurnSmartboxServiceLedOff command functionality.

            :param argin: the logical id of the smartbox whose blue
                service LED is to be turned off

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            component_manager = self.target
            success = component_manager.turn_smartbox_service_led_off(argin)
            return create_return(success, f"smartbox {argin} service LED off")

    @command(dtype_in="DevULong", dtype_out="DevVarLongStringArray")
    def TurnSmartboxServiceLedOff(
        self: MccsPasdBus, argin: int
    ) -> DevVarLongStringArrayType:
        """
        Turn off a smartbox's blue service LED.

        :param argin: id of the smartbox whose blue service LED is to be
            turned off

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("TurnSmartboxServiceLedOff")
        (result_code, message) = handler(argin)
        return ([result_code], [message])

    class GetAntennaInfoCommand(BaseCommand):
        """Class for handling the GetAntennaInfo command."""

        def do(  # type: ignore[override]
            self: MccsPasdBus.GetAntennaInfoCommand, argin: int
        ) -> dict:
            """
            Implement py:meth:`.MccsPasdBus.GetAntennaInfo` command.

            :param argin: the antenna id

            :return: A dictionary containing information about the
                antenna.
            """
            component_manager = self.target
            return component_manager.get_antenna_info(argin)

    @command(dtype_in="DevULong", dtype_out=str)
    def GetAntennaInfo(self: MccsPasdBus, argin: int) -> str:
        """
        Return information about relationship of an antenna to other PaSD components.

        :param argin: the antenna id

        :return: a JSON string encoding a dictionary containing the
            antenna's smartbox number, port number, TPM number and TPM input number.
        """
        handler = self.get_command_object("GetAntennaInfo")
        antenna_info = handler(argin)
        return json.dumps(antenna_info)

    class ResetAntennaBreakerCommand(ResponseCommand):
        """The command class for the ResetAntennaBreaker command."""

        def do(  # type: ignore[override]
            self: MccsPasdBus.ResetAntennaBreakerCommand, argin: int
        ) -> tuple[ResultCode, str]:
            """
            Implement ResetAntennaBreaker command functionality.

            :param argin: the logical id of the antenna whose breaker is
                to be reset

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            component_manager = self.target
            success = component_manager.reset_antenna_breaker(argin)
            return create_return(success, f"antenna {argin} breaker reset")

    @command(dtype_in="DevULong", dtype_out="DevVarLongStringArray")
    def ResetAntennaBreaker(self: MccsPasdBus, argin: int) -> DevVarLongStringArrayType:
        """
        Reset a tripped antenna breaker.

        :param argin: id of the antenna for which a breaker trip is to
            be reset

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("ResetAntennaBreaker")
        (result_code, message) = handler(argin)
        return ([result_code], [message])

    class TurnAntennaOnCommand(ResponseCommand):
        """The command class for the TurnAntennaOn command."""

        def do(  # type: ignore[override]
            self: MccsPasdBus.TurnAntennaOnCommand, argin: int
        ) -> tuple[ResultCode, str]:
            """
            Implement TurnAntennaOn command functionality.

            :param argin: the logical id of the antenna that is to be
                turned off

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            component_manager = self.target
            success = component_manager.turn_antenna_on(argin)
            return create_return(success, f"antenna {argin} on")

    @command(dtype_in="DevULong", dtype_out="DevVarLongStringArray")
    def TurnAntennaOn(self: MccsPasdBus, argin: int) -> DevVarLongStringArrayType:
        """
        Turn on an antenna.

        :param argin: id of the antenna to be turned on

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("TurnAntennaOn")
        (result_code, message) = handler(argin)
        return ([result_code], [message])

    class TurnAntennaOffCommand(ResponseCommand):
        """The command class for the TurnAntennaOff command."""

        def do(  # type: ignore[override]
            self: MccsPasdBus.TurnAntennaOffCommand, argin: int
        ) -> tuple[ResultCode, str]:
            """
            Implement TurnAntennaOff command functionality.

            :param argin: the logical id of the antenna that is to be
                turned off

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            component_manager = self.target
            success = component_manager.turn_antenna_off(argin)
            return create_return(success, f"antenna {argin} off")

    @command(dtype_in="DevULong", dtype_out="DevVarLongStringArray")
    def TurnAntennaOff(self: MccsPasdBus, argin: int) -> DevVarLongStringArrayType:
        """
        Turn off an antenna.

        :param argin: id of the antenna to be turned off

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("TurnAntennaOff")
        (result_code, message) = handler(argin)
        return ([result_code], [message])


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
    return MccsPasdBus.run_server(args=args or None, **kwargs)


if __name__ == "__main__":
    main()
