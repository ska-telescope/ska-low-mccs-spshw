# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements an antenna Tango device for MCCS."""
from __future__ import annotations

from typing import Optional, Tuple, List

import tango
from tango.server import attribute, device_property, command

from ska_tango_base.base import SKABaseDevice
from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import HealthState, PowerMode, SimulationMode

from ska_low_mccs.antenna import AntennaComponentManager, AntennaHealthModel
from ska_low_mccs.component import CommunicationStatus

__all__ = ["MccsAntenna", "main"]

DevVarLongStringArrayType = Tuple[List[ResultCode], List[Optional[str]]]


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
    def init_device(self: MccsAntenna) -> None:
        """
        Initialise the device.

        This is overridden here to change the Tango serialisation model.
        """
        util = tango.Util.instance()
        util.set_serial_model(tango.SerialModel.NO_SYNC)
        super().init_device()

    def _init_state_model(self: MccsAntenna) -> None:
        super()._init_state_model()
        self._health_state: Optional[
            HealthState
        ] = None  # SKABaseDevice.InitCommand.do() does this too late.
        self._health_model = AntennaHealthModel(self.health_changed)
        self.set_change_event("healthState", True, False)

    def create_component_manager(
        self: MccsAntenna,
    ) -> AntennaComponentManager:
        """
        Create and return a component manager for this device.

        :return: a component manager for this device.
        """
        return AntennaComponentManager(
            f"low-mccs/apiu/{self.ApiuId:03}",
            self.LogicalApiuAntennaId,
            f"low-mccs/tile/{self.TileId:04}",
            self.LogicalTileAntennaId,
            self.logger,
            self.push_change_event,
            self._component_communication_status_changed,
            self._component_power_mode_changed,
            self._component_fault,
        )

    class InitCommand(SKABaseDevice.InitCommand):
        """Class that implements device initialisation for the MCCS antenna device."""

        def do(  # type: ignore[override]
            self: MccsAntenna.InitCommand,
        ) -> tuple[ResultCode, str]:
            """
            Stateless hook for device initialisation.

            Initialises the attributes and properties of the :py:class:`.MccsAntenna`.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            super().do()

            device = self.target

            device._antennaId = 0
            device._gain = 0.0
            device._rms = 0.0
            device._xPolarisationFaulty = False
            device._yPolarisationFaulty = False
            device._xDisplacement = 0.0
            device._yDisplacement = 0.0
            device._zDisplacement = 0.0
            device._timestampOfLastSpectrum = ""
            device._logicalAntennaId = 0
            device._xPolarisationScalingFactor = [0]
            device._yPolarisationScalingFactor = [0]
            device._calibrationCoefficient = [0.0]
            device._pointingCoefficient = [0.0]
            device._spectrumX = [0.0]
            device._spectrumY = [0.0]
            device._position = [0.0]
            device._delays = [0.0]
            device._delayRates = [0.0]
            device._bandpassCoefficient = [0.0]
            device._first = True

            event_names = [
                "voltage",
                "temperature",
                "xPolarisationFaulty",
                "yPolarisationFaulty",
            ]
            for name in event_names:
                device.set_change_event(name, True, True)
                device.set_archive_event(name, True, True)

            # The health model updates our health, but then the base class super().do()
            # overwrites it with OK, so we need to update this again.
            # TODO: This needs to be fixed in the base classes.
            device._health_state = device._health_model.health_state

            return (ResultCode.OK, "Init command completed OK")

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ReturnType, 'informational message')",
    )
    def Reset(self: MccsAntenna) -> DevVarLongStringArrayType:
        """
        Reset the device from the FAULT state.

        To modify behaviour for this command, modify the do() method of
        the command class.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        # TODO Call Reset directly - DON'T USE LRC - for now.
        handler = self.get_command_object("Reset")
        (result_code, message) = handler()
        return ([result_code], [message])

    # --------------
    # Callback hooks
    # --------------
    def _component_communication_status_changed(
        self: MccsAntenna,
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
        self: MccsAntenna,
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
        self: MccsAntenna,
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
            self._component_power_mode_changed(self.component_manager.power_mode)
            self._health_model.component_fault(False)

    def health_changed(self: MccsAntenna, health: HealthState) -> None:
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
    def simulationMode(self):
        """
        Return the simulation mode of this device.

        :return: the simulation mode of this device
        """
        return SimulationMode.FALSE

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
        return self._fieldNodeLongitude

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

    # --------
    # Commands
    # --------

    class OnCommand(SKABaseDevice.OnCommand):
        """
        A class for the MccsAntenna's On() command.

        This class overrides the SKABaseDevice OnCommand to allow for an
        eventual consistency semantics. For example it is okay to call
        On() before the APIU is on; this device will happily wait for
        the APIU to come on, then tell it to turn on its Antenna. This
        change of semantics requires an override because the
        SKABaseDevice OnCommand only allows On() to be run when in OFF
        state.
        """

        def do(  # type: ignore[override]
            self: MccsAntenna.OnCommand,
        ) -> tuple[ResultCode, str]:
            """
            Stateless hook for On() command functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            # It's fine to complete this long-running command here
            # (returning ResultCode.OK), even though the component manager
            # may not actually be finished turning everything on.
            # The completion of the original On command to MccsController
            # is waiting for the various power mode callbacks to be received
            # rather than completion of the various long-running commands.
            _ = self.target.on()
            message = "Antenna On command completed OK"
            return (ResultCode.OK, message)

    def is_On_allowed(self: MccsAntenna) -> bool:
        """
        Check if command `Off` is allowed in the current device state.

        :return: ``True`` if the command is allowed
        """
        return self.get_state() in [
            tango.DevState.OFF,
            tango.DevState.STANDBY,
            tango.DevState.ON,
            tango.DevState.UNKNOWN,
            tango.DevState.FAULT,
        ]


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
