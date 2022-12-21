#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements an antenna Tango device for MCCS."""
from __future__ import annotations

from typing import Any, Optional, cast

import tango
from ska_control_model import (  # SimulationMode,
    CommunicationStatus,
    HealthState,
    PowerState,
    ResultCode,
    SimulationMode,
)
from ska_tango_base.base import SKABaseDevice
from ska_tango_base.commands import DeviceInitCommand, SubmittedSlowCommand
from tango.server import attribute, command, device_property

from ska_low_mccs.antenna.antenna_component_manager import AntennaComponentManager
from ska_low_mccs.antenna.antenna_health_model import AntennaHealthModel

__all__ = ["MccsAntenna", "main"]

DevVarLongStringArrayType = tuple[list[ResultCode], list[Optional[str]]]


# pylint: disable=too-many-public-methods, too-many-instance-attributes
class MccsAntenna(SKABaseDevice):
    """An implementation of an antenna Tango device for MCCS."""

    # -----------------
    # Device Properties
    # -----------------
    ApiuId = device_property(dtype=int)
    LogicalApiuAntennaId = device_property(dtype=int)
    TileId = device_property(dtype=int)
    LogicalTileAntennaId = device_property(dtype=int)

    # ---------------
    # Initialisation
    # ---------------
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Initialise this device object.

        :param args: positional args to the init
        :param kwargs: keyword args to the init
        """
        # We aren't supposed to define initialisation methods for Tango
        # devices; we are only supposed to define an `init_device` method. But
        # we insist on doing so here, just so that we can define some
        # attributes, thereby stopping the linters from complaining about
        # "attribute-defined-outside-init" etc. We still need to make sure that
        # `init_device` re-initialises any values defined in here.
        super().__init__(*args, **kwargs)

        self._health_state: HealthState = HealthState.UNKNOWN
        self._health_model: AntennaHealthModel
        self.component_manager: AntennaComponentManager
        self._antennaId: int
        self._xDisplacement: float
        self._yDisplacement: float
        self._zDisplacement: float

    def init_device(self: MccsAntenna) -> None:
        """
        Initialise the device.

        This is overridden here to change the Tango serialisation model.
        """
        util = tango.Util.instance()
        util.set_serial_model(tango.SerialModel.NO_SYNC)
        self._max_workers = 1
        super().init_device()

    def _init_state_model(self: MccsAntenna) -> None:
        super()._init_state_model()
        self._health_state = HealthState.UNKNOWN  # InitCommand.do() does this too late.
        self._health_model = AntennaHealthModel(self.component_state_changed_callback)
        self.set_change_event("healthState", True, False)

    def create_component_manager(
        self: MccsAntenna,
    ) -> AntennaComponentManager:
        """
        Create and return a component manager for this device.

        :return: a component manager for this device.
        """
        return AntennaComponentManager(
            f"low-mccs/apiu/{self.ApiuId}",
            self.LogicalApiuAntennaId,
            f"low-mccs/tile/{self.TileId}",
            self.LogicalTileAntennaId,
            self.logger,
            self._max_workers,
            self._communication_state_changed_callback,
            self.component_state_changed_callback,
        )

    def init_command_objects(self: MccsAntenna) -> None:
        """Initialise the command handlers for commands supported by this device."""
        super().init_command_objects()
        for (command_name, method_name) in [
            ("Configure", "configure"),
        ]:
            self.register_command_object(
                command_name,
                SubmittedSlowCommand(
                    command_name,
                    self._command_tracker,
                    self.component_manager,
                    method_name,
                    callback=None,
                    logger=None,
                ),
            )

    # pylint: disable=too-few-public-methods
    class InitCommand(DeviceInitCommand):
        """Class that implements device initialisation for the MCCS antenna device."""

        def do(
            self: MccsAntenna.InitCommand,
            *args: Any,
            **kwargs: Any,
        ) -> tuple[ResultCode, str]:
            """
            Stateless hook for device initialisation.

            Initialises the attributes and properties of the :py:class:`.MccsAntenna`.

            :param args: positional args to the component manager method
            :param kwargs: keyword args to the component manager method

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            self._device._antennaId = 0
            self._device._gain = 0.0
            self._device._rms = 0.0
            self._device._xPolarisationFaulty = False
            self._device._yPolarisationFaulty = False
            self._device._xDisplacement = 0.0
            self._device._yDisplacement = 0.0
            self._device._zDisplacement = 0.0
            self._device._timestampOfLastSpectrum = ""
            self._device._logicalAntennaId = 0
            self._device._xPolarisationScalingFactor = [0]
            self._device._yPolarisationScalingFactor = [0]
            self._device._calibrationCoefficient = [0.0]
            self._device._pointingCoefficient = [0.0]
            self._device._spectrumX = [0.0]
            self._device._spectrumY = [0.0]
            self._device._position = [0.0]
            self._device._delays = [0.0]
            self._device._delayRates = [0.0]
            self._device._bandpassCoefficient = [0.0]
            self._device._first = True
            self._device._altitude = 0.0
            self._device._fieldNodeLatitude = 0.0
            self._device._fieldNodeLongitude = 0.0

            event_names = [
                "voltage",
                "temperature",
                "xPolarisationFaulty",
                "yPolarisationFaulty",
            ]
            for name in event_names:
                self._device.set_change_event(name, True, True)
                self._device.set_archive_event(name, True, True)

            return (ResultCode.OK, "Init command completed OK")

    # --------------
    # Callback hooks
    # --------------
    def _communication_state_changed_callback(
        self: MccsAntenna,
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

    def component_state_changed_callback(
        self: MccsAntenna,
        state_change: dict[str, Any],
        fqdn: Optional[str] = None,
    ) -> None:
        """
        Handle change in the state of the component.

        This is a callback hook, called by the component manager when
        the state of the component changes.

        :param state_change: a dict containing the state change(s)
            of the component.
        :param fqdn: fully qualified domain name of the device whos state
            has changed. None if the device is an antenna.

        :raises ValueError: unknown fqdn
        """
        #        if fqdn is None:
        health_state_changed_callback = self._health_changed
        power_state_changed_callback = self._component_power_state_changed
        #        else:
        if fqdn is not None:
            device_family = fqdn.split("/")[1]
            if device_family == "apiu":
                # health_state_changed_callback = self._health_model.apiu_health_changed
                power_state_changed_callback = (
                    self.component_manager._apiu_power_state_changed
                )
            elif device_family == "tile":
                # health_state_changed_callback = functools.partial(
                #     self._health_model.tile_health_changed, fqdn
                # )
                # power_state_changed_callback = functools.partial(
                #     self.component_manager._tile_power_state_changed, fqdn
                # )
                pass
            else:
                raise ValueError(
                    f"unknown fqdn '{fqdn}', should be None or belong to antenna, "
                    "tile or apiu"
                )

        if "fault" in state_change.keys():
            is_fault = state_change.get("fault")
            if is_fault:
                self.op_state_model.perform_action("component_fault")
                self._health_model.component_fault(True)
            else:
                if self.component_manager.power_state:
                    power_state_changed_callback(self.component_manager.power_state)
                self._health_model.component_fault(False)

        if "health_state" in state_change.keys():
            health = cast(HealthState, state_change.get("health_state"))
            health_state_changed_callback(health)

        if "power_state" in state_change.keys():
            power_state = cast(PowerState, state_change.get("power_state"))
            with self.component_manager.power_state_lock:
                self.component_manager.set_power_state(power_state, fqdn=fqdn)
                if power_state:
                    power_state_changed_callback(power_state)
        if "configuration_changed" in state_change.keys():
            configuration = state_change.get("configuration_changed")
            assert isinstance(configuration, dict)
            self._configure_antenna(configuration)

    def _component_power_state_changed(
        self: MccsAntenna,
        power_state: PowerState,
    ) -> None:
        """
        Handle change in the power mode of the component.

        This is a callback hook, called by the component manager when
        the power mode of the component changes. It is implemented here
        to drive the op_state.

        :param power_state: the power mode of the component.
        """
        action_map = {
            PowerState.OFF: "component_off",
            PowerState.STANDBY: "component_standby",
            PowerState.ON: "component_on",
            PowerState.UNKNOWN: "component_unknown",
        }

        self.op_state_model.perform_action(action_map[power_state])

    def _health_changed(self: MccsAntenna, health: HealthState) -> None:
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

    def _configure_antenna(self: MccsAntenna, config: dict) -> None:
        """
        Configure the antenna attributes.

        :param config: the configuration settings for this antenna.
        """

        def apply_if_valid(attribute_name: str, default: Any) -> Any:
            value = config.get(attribute_name)
            if isinstance(value, type(default)):
                return value
            return default

        self._antennaId = apply_if_valid("antennaId", self._antennaId)
        self._xDisplacement = apply_if_valid("xDisplacement", self._xDisplacement)
        self._yDisplacement = apply_if_valid("yDisplacement", self._yDisplacement)
        self._zDisplacement = apply_if_valid("zDisplacement", self._zDisplacement)

    # ----------
    # Attributes
    # ----------
    @attribute(
        dtype=SimulationMode,
        memorized=True,
        hw_memorized=True,
    )
    def simulationMode(self):
        """
        Return the simulation mode of this device.

        This overrides the base class as the antenna device cannot be put into
        simulation mode TRUE

        :return: the simulation mode of this device
        """
        return SimulationMode.FALSE

    # pylint: disable=arguments-differ
    @simulationMode.write  # type: ignore [no-redef]
    def simulationMode(self: MccsAntenna, value: SimulationMode) -> None:
        """
        Set the simulation mode of this device.

        :param value: the new simulation mode

        :raises ValueError: because this device cannot be put into simulation mode.
        """
        if value == SimulationMode.TRUE:
            raise ValueError("MccsAntenna cannot be put into simulation mode.")

    @attribute(dtype="int", label="AntennaID")
    def antennaId(self: MccsAntenna) -> int:
        """
        Return the antenna ID attribute.

        :return: antenna ID
        """
        return self._antennaId

    @attribute(dtype="float", label="gain")
    def gain(self: MccsAntenna) -> float:
        """
        Return the gain attribute.

        :return: the gain
        """
        return self._gain

    @attribute(dtype="float", label="rms")
    def rms(self: MccsAntenna) -> float:
        """
        Return the measured RMS of the antenna.

        :return: the measured rms
        """
        return self._rms

    @attribute(
        dtype="float",
        label="voltage",
        unit="volts",
        abs_change=0.05,
        min_value=2.5,
        max_value=5.5,
        min_alarm=2.75,
        max_alarm=5.45,
    )
    def voltage(self: MccsAntenna) -> float:
        """
        Return the voltage attribute.

        :return: the voltage
        """
        return self.component_manager.voltage

    @attribute(dtype="float", label="current", unit="amperes")
    def current(self: MccsAntenna) -> float:
        """
        Return the current attribute.

        :return: the current
        """
        return self.component_manager.current

    @attribute(dtype="float", label="temperature", unit="DegC")
    def temperature(self: MccsAntenna) -> float:
        """
        Return the temperature attribute.

        :return: the temperature
        """
        return self.component_manager.temperature

    @attribute(dtype="bool", label="xPolarisationFaulty")
    def xPolarisationFaulty(self: MccsAntenna) -> bool:
        """
        Return the xPolarisationFaulty attribute.

        :return: the x-polarisation faulty flag
        """
        return self._xPolarisationFaulty

    @attribute(dtype="bool", label="yPolarisationFaulty")
    def yPolarisationFaulty(self: MccsAntenna) -> bool:
        """
        Return the yPolarisationFaulty attribute.

        :return: the y-polarisation faulty flag
        """
        return self._yPolarisationFaulty

    @attribute(dtype="float", label="fieldNodeLongitude")
    def fieldNodeLongitude(self: MccsAntenna) -> float:
        """
        Return the fieldNodeLongitude attribute.

        :return: the Longitude of field node centre
        """
        return self._fieldNodeLongitude

    @attribute(dtype="float", label="fieldNodeLatitude")
    def fieldNodeLatitude(self: MccsAntenna) -> float:
        """
        Return the fieldNodeLatitude attribute.

        :return: the Latitude of field node centre
        """
        return self._fieldNodeLatitude

    @attribute(dtype="float", label="altitude", unit="meters")
    def altitude(self: MccsAntenna) -> float:
        """
        Return the altitude attribute.

        :return: the altitude of the antenna
        """
        return self._altitude

    @attribute(dtype="float", label="xDisplacement", unit="meters")
    def xDisplacement(self: MccsAntenna) -> float:
        """
        Return the horizontal displacement east attribute.

        :return: the horizontal displacement eastwards from station reference position
        """
        return self._xDisplacement

    @attribute(dtype="float", label="yDisplacement", unit="meters")
    def yDisplacement(self: MccsAntenna) -> float:
        """
        Return the horizontal displacement north attribute.

        :return: the horizontal displacement northwards from station reference position
        """
        return self._yDisplacement

    @attribute(dtype="float", label="zDisplacement", unit="meters")
    def zDisplacement(self: MccsAntenna) -> float:
        """
        Return the vertical displacement attribute.

        :return: the vertical displacement upwards from station reference position
        """
        return self._zDisplacement

    @attribute(dtype="str", label="timestampOfLastSpectrum")
    def timestampOfLastSpectrum(self: MccsAntenna) -> str:
        """
        Return the timestampOfLastSpectrum attribute.

        :return: the timestamp of the last spectrum
        """
        return self._timestampOfLastSpectrum

    @attribute(dtype="int", label="logicalAntennaId")
    def logicalAntennaId(self: MccsAntenna) -> int:
        """
        Return the logical antenna ID attribute.

        :return: the logical antenna ID
        """
        return self._logicalAntennaId

    @attribute(dtype=("int",), max_dim_x=100, label="xPolarisationScalingFactor")
    def xPolarisationScalingFactor(self: MccsAntenna) -> list[int]:
        """
        Return the logical antenna ID attribute.

        :return: the x polarisation scaling factor
        """
        return self._xPolarisationScalingFactor

    @attribute(dtype=("int",), max_dim_x=100, label="yPolarisationScalingFactor")
    def yPolarisationScalingFactor(self: MccsAntenna) -> list[int]:
        """
        Return the yPolarisationScalingFactor attribute.

        :return: the y polarisation scaling factor
        """
        return self._yPolarisationScalingFactor

    @attribute(dtype=("float",), max_dim_x=100, label="calibrationCoefficient")
    def calibrationCoefficient(self: MccsAntenna) -> list[float]:
        """
        Get the Calibration coefficients.

        The coefficients to be applied for the next frequency channel
        in the calibration cycle.

        :return: the calibration coefficients
        """
        return self._calibrationCoefficient

    @attribute(dtype=("float",), max_dim_x=100)
    def pointingCoefficient(self: MccsAntenna) -> list[float]:
        """
        Return the pointingCoefficient attribute.

        :return: the pointing coefficients
        """
        return self._pointingCoefficient

    @attribute(dtype=("float",), max_dim_x=100, label="spectrumX")
    def spectrumX(self: MccsAntenna) -> list[float]:
        """
        Return the spectrumX attribute.

        :return: x spectrum
        """
        return self._spectrumX

    @attribute(dtype=("float",), max_dim_x=100, label="spectrumY")
    def spectrumY(self: MccsAntenna) -> list[float]:
        """
        Return the spectrumY attribute.

        :return: y spectrum
        """
        return self._spectrumY

    @attribute(dtype=("float",), max_dim_x=100, label="position")
    def position(self: MccsAntenna) -> list[float]:
        """
        Return the position attribute.

        :return: positions
        """
        return self._position

    @attribute(dtype=("float",), max_dim_x=100, label="delays")
    def delays(self: MccsAntenna) -> list[float]:
        """
        Return the delays attribute.

        :return: delay for each beam
        """
        return self._delays

    @attribute(dtype=("float",), max_dim_x=100, label="delayRates")
    def delayRates(self: MccsAntenna) -> list[float]:
        """
        Return the delayRates attribute.

        :return: delay rate for each beam
        """
        return self._delayRates

    @attribute(dtype=("float",), max_dim_x=100, label="bandpassCoefficient")
    def bandpassCoefficient(self: MccsAntenna) -> list[float]:
        """
        Return the bandpassCoefficient attribute.

        :return: bandpass coefficients
        """
        return self._bandpassCoefficient

    @attribute(dtype="bool", label="first")
    def first(self: MccsAntenna) -> bool:
        """
        Return the first attribute.

        :return: the first faulty flag
        """
        return self._first

    # --------
    # Commands
    # --------
    def is_On_allowed(self: MccsAntenna) -> bool:
        """
        Check if command `On` is allowed in the current device state.

        :return: ``True`` if the command is allowed
        """
        return self.get_state() in [
            tango.DevState.OFF,
            tango.DevState.STANDBY,
            tango.DevState.ON,
            tango.DevState.UNKNOWN,
            tango.DevState.FAULT,
        ]

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    def Configure(self: MccsAntenna, argin: str) -> DevVarLongStringArrayType:
        """
        Configure the antenna device attributes.

        Also configures children device that are connected to the antenna.

        :param argin: Configuration parameters encoded in a json string

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:
            >>> dp = tango.DeviceProxy("mccs/antenna/00001")
            >>> dp.command_inout("Configure", json_str)
        """
        handler = self.get_command_object("Configure")
        (return_code, message) = handler(argin)
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
    return MccsAntenna.run_server(args=args or None, **kwargs)


if __name__ == "__main__":
    main()
