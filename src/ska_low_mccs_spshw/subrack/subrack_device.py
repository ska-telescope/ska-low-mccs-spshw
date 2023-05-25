# pylint: disable=too-many-lines
# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module provides a Tango device for a PSI-Low subrack."""
from __future__ import annotations

import importlib
import json
import logging
from typing import Any, Callable, Final, Optional

from ska_control_model import CommunicationStatus, HealthState, PowerState
from ska_tango_base.base import BaseComponentManager, SKABaseDevice
from ska_tango_base.commands import (
    CommandTrackerProtocol,
    DeviceInitCommand,
    JsonValidator,
    ResultCode,
    SubmittedSlowCommand,
)
from tango.server import attribute, command, device_property

from ska_low_mccs_spshw.subrack.subrack_health_model import SubrackHealthModel

from .subrack_component_manager import SubrackComponentManager
from .subrack_data import FanMode, SubrackData


class SetSubrackFanSpeedCommand(SubmittedSlowCommand):
    # pylint: disable=line-too-long
    """
    Class for handling the SetSubrackFanSpeed command.

    This command sets the selected subrack fan speed.

    This command takes as input a JSON string that conforms to the
    following schema:

    .. literalinclude:: /../../src/ska_low_mccs_spshw/subrack/schemas/MccsSubrack_SetSubrackFanSpeed.json
       :language: json
    """  # noqa: E501

    SCHEMA: Final = json.loads(
        importlib.resources.read_text(
            "ska_low_mccs_spshw.subrack.schemas",
            "MccsSubrack_SetSubrackFanSpeed.json",
        )
    )

    def __init__(
        self: SetSubrackFanSpeedCommand,
        command_tracker: CommandTrackerProtocol,
        component_manager: BaseComponentManager,
        fan_speed_set: Callable,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        """
        Initialise a new instance.

        :param command_tracker: the device's command tracker
        :param component_manager: the component manager on which this
            command acts.
        :param fan_speed_set: callback to be called when fan speed is set.
        :param logger: a logger for this command to use.
        """
        validator = JsonValidator("SetSubrackFanSpeed", self.SCHEMA, logger)
        self._fan_speed_set = fan_speed_set
        super().__init__(
            "SetSubrackFanSpeed",
            command_tracker,
            component_manager,
            "set_subrack_fan_speed",
            callback=None,
            logger=logger,
            validator=validator,
        )

    # pylint: disable=arguments-differ
    def do(  # type: ignore[override]
        self: SetSubrackFanSpeedCommand,
        *args: Any,
        subrack_fan_id: int,
        speed_percent: float,
        **kwargs: Any,
    ) -> tuple[ResultCode, str]:
        """
        Implement :py:meth:`.MccsSubrack.SetSubrackFanSpeed` command.

        :param args: unspecified positional arguments. This should be
            empty and is provided for typehinting purposes only.
        :param subrack_fan_id: id of the subrack (1-4).
        :param speed_percent: fan speed in percent
        :param kwargs: unspecified keyword arguments. This should be
            empty and is provided for typehinting purposes only.

        :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
        """
        assert (
            not args and not kwargs
        ), f"do method has unexpected arguments: {args}, {kwargs}"

        self._fan_speed_set(subrack_fan_id, speed_percent)

        return super().do(subrack_fan_id, speed_percent)


class SetSubrackFanModeCommand(SubmittedSlowCommand):
    # pylint: disable=line-too-long
    """
    Class for handling the SetSubrackFanMode command.

    This command set the selected subrack fan mode.

    This command takes as input a JSON string that conforms to the
    following schema:

    .. literalinclude:: /../../src/ska_low_mccs_spshw/subrack/schemas/MccsSubrack_SetSubrackFanMode.json
       :language: json
    """  # noqa: E501

    SCHEMA: Final = json.loads(
        importlib.resources.read_text(
            "ska_low_mccs_spshw.subrack.schemas",
            "MccsSubrack_SetSubrackFanMode.json",
        )
    )

    def __init__(
        self: SetSubrackFanModeCommand,
        command_tracker: CommandTrackerProtocol,
        component_manager: BaseComponentManager,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        """
        Initialise a new instance.

        :param command_tracker: the device's command tracker
        :param component_manager: the component manager on which this
            command acts.
        :param logger: a logger for this command to use.
        """
        validator = JsonValidator("SetSubrackFanMode", self.SCHEMA, logger)
        super().__init__(
            "SetSubrackFanMode",
            command_tracker,
            component_manager,
            "set_subrack_fan_mode",
            callback=None,
            logger=logger,
            validator=validator,
        )

    # pylint: disable=arguments-differ
    def do(  # type: ignore[override]
        self: SetSubrackFanModeCommand,
        *args: Any,
        fan_id: int,
        mode: int,
        **kwargs: Any,
    ) -> tuple[ResultCode, str]:
        """
        Implement :py:meth:`.MccsSubrack.SetSubrackFanMode` command.

        :param args: unspecified positional arguments. This should be
            empty and is provided for typehinting purposes only.
        :param fan_id: id of the subrack (1-4).
        :param mode: fan mode
        :param kwargs: unspecified keyword arguments. This should be
            empty and is provided for typehinting purposes only.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        assert (
            not args and not kwargs
        ), f"do method has unexpected arguments: {args}, {kwargs}"

        return super().do(fan_id, FanMode(mode))


class SetPowerSupplyFanSpeedCommand(SubmittedSlowCommand):
    # pylint: disable=line-too-long
    """
    Class for handling the SetPowerSupplyFanSpeed command.

    This command set the selected power supply fan speed.

    This command takes as input a JSON string that conforms to the
    following schema:

    .. literalinclude:: /../../src/ska_low_mccs_spshw/subrack/schemas/MccsSubrack_SetPowerSupplyFanSpeed.json
       :language: json
    """  # noqa: E501

    SCHEMA: Final = json.loads(
        importlib.resources.read_text(
            "ska_low_mccs_spshw.subrack.schemas",
            "MccsSubrack_SetPowerSupplyFanSpeed.json",
        )
    )

    def __init__(
        self: SetPowerSupplyFanSpeedCommand,
        command_tracker: CommandTrackerProtocol,
        component_manager: BaseComponentManager,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        """
        Initialise a new instance.

        :param command_tracker: the device's command tracker
        :param component_manager: the component manager on which this
            command acts.
        :param logger: a logger for this command to use.
        """
        validator = JsonValidator("SetPowerSupplyFanSpeed", self.SCHEMA, logger)
        super().__init__(
            "SetPowerSupplyFanSpeed",
            command_tracker,
            component_manager,
            "set_power_supply_fan_speed",
            callback=None,
            logger=logger,
            validator=validator,
        )

    # pylint: disable=arguments-differ
    def do(  # type: ignore[override]
        self: SetPowerSupplyFanSpeedCommand,
        *args: Any,
        power_supply_fan_id: int,
        speed_percent: float,
        **kwargs: Any,
    ) -> tuple[ResultCode, str]:
        """
        Implement :py:meth:`.MccsSubrack.SetPowerSupplyFanSpeed` command.

        :param args: unspecified positional arguments. This should be
            empty and is provided for typehinting purposes only.
        :param power_supply_fan_id: id of the power supply (1 or 2).
        :param speed_percent: fan speed in percent
        :param kwargs: unspecified keyword arguments. This should be
            empty and is provided for typehinting purposes only.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        assert (
            not args and not kwargs
        ), f"do method has unexpected arguments: {args}, {kwargs}"

        return super().do(power_supply_fan_id, speed_percent)


# pylint: disable=too-many-public-methods, too-many-instance-attributes
class MccsSubrack(SKABaseDevice[SubrackComponentManager]):
    """A Tango device for monitor and control of the PSI-Low subrack."""

    # A map from the compnent manager argument to the name of the Tango attribute.
    # This only includes one-to-one mappings. It lets us boilerplate these cases.
    # Attributes that don't map one-to-one are handled individually.
    # For example, tpm_on_off is not included here because it unpacks into eight
    # Tango attributes of the form tpm{N}PowerState.
    _ATTRIBUTE_MAP = {
        "backplane_temperatures": "backplaneTemperatures",
        "board_temperatures": "boardTemperatures",
        "board_current": "boardCurrent",
        "power_supply_currents": "powerSupplyCurrents",
        "power_supply_powers": "powerSupplyPowers",
        "power_supply_voltages": "powerSupplyVoltages",
        "power_supply_fan_speeds": "powerSupplyFanSpeeds",
        "subrack_fan_speeds": "subrackFanSpeeds",
        "subrack_fan_speeds_percent": "subrackFanSpeedsPercent",
        "subrack_fan_mode": "subrackFanModes",
        "tpm_currents": "tpmCurrents",
        "tpm_powers": "tpmPowers",
        # "tpm_temperatures": "tpmTemperatures",  # Not implemented on SMB
        "tpm_voltages": "tpmVoltages",
    }

    def __init__(self: MccsSubrack, *args: Any, **kwargs: Any) -> None:
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

        self._health_model: SubrackHealthModel
        self._health_state: HealthState

        self._tpm_present: list[bool] = []
        self._tpm_count = 0
        self._tpm_power_states = [PowerState.UNKNOWN] * SubrackData.TPM_BAY_COUNT

        self._hardware_attributes: dict[str, Any] = {}

        self._desired_fan_speeds: list[float] = [0.0] * 4
        self.clock_presence = ["10MHz", "1PPS", "10_MHz_PLL_lock"]
        self._update_health_data()

    # ----------
    # Properties
    # ----------
    SubrackIp = device_property(dtype=str)
    SubrackPort = device_property(dtype=int, default_value=8081)
    UpdateRate = device_property(dtype=float, default_value=15.0)

    class InitCommand(DeviceInitCommand):
        """Initialisation command class for this base device."""

        # pylint: disable=protected-access
        def do(
            self: MccsSubrack.InitCommand, *args: Any, **kwargs: Any
        ) -> tuple[ResultCode, str]:
            """
            Initialise the attributes of this MccsSubrack.

            :param args: additional positional arguments; unused here
            :param kwargs: additional keyword arguments; unused here
            :return: a resultcode, message tuple
            """
            self._device._tpm_present = None
            self._device._tpm_count = 0
            self._device._tpm_power_states = [
                PowerState.UNKNOWN
            ] * SubrackData.TPM_BAY_COUNT
            self._device._hardware_attributes = {}

            self._device.set_change_event("tpmPresent", True)
            self._device.set_change_event("tpmCount", True)
            for tpm_number in range(1, SubrackData.TPM_BAY_COUNT + 1):
                self._device.set_change_event(f"tpm{tpm_number}PowerState", True)
            for attribute_name in MccsSubrack._ATTRIBUTE_MAP.values():
                self._device.set_change_event(attribute_name, True)

            message = "MccsSubrack init complete."
            self._device.logger.info(message)
            self._completed()
            return (ResultCode.OK, message)

    # --------------
    # Initialization
    # --------------
    def _init_state_model(self: MccsSubrack) -> None:
        super()._init_state_model()
        self._health_state = HealthState.UNKNOWN  # InitCommand.do() does this too late.
        self._health_model = SubrackHealthModel(self._health_changed)
        self.set_change_event("healthState", True, False)

    def create_component_manager(self: MccsSubrack) -> SubrackComponentManager:
        """
        Create and return a component manager for this device.

        :return: a component manager for this device.
        """
        return SubrackComponentManager(
            self.SubrackIp,
            self.SubrackPort,
            self.logger,
            self._communication_state_changed,
            self._component_state_changed,
            update_rate=self.UpdateRate,
        )

    def init_command_objects(self: MccsSubrack) -> None:
        """Initialise the command handlers for this device."""
        super().init_command_objects()

        for (command_name, method_name) in [
            ("PowerOnTpm", "turn_on_tpm"),
            ("PowerOffTpm", "turn_off_tpm"),
            ("PowerUpTpms", "turn_on_tpms"),
            ("PowerDownTpms", "turn_off_tpms"),
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
        for (command_name, command_class) in [
            ("SetSubrackFanMode", SetSubrackFanModeCommand),
            ("SetPowerSupplyFanSpeed", SetPowerSupplyFanSpeedCommand),
        ]:
            self.register_command_object(
                command_name,
                command_class(
                    self._command_tracker, self.component_manager, logger=self.logger
                ),
            )
        self.register_command_object(
            "SetSubrackFanSpeed",
            SetSubrackFanSpeedCommand(
                self._command_tracker,
                self.component_manager,
                self._fan_speed_set,
                logger=self.logger,
            ),
        )

    def _fan_speed_set(self: MccsSubrack, fan_id: int, fan_speed_set: float) -> None:
        self._desired_fan_speeds[fan_id] = fan_speed_set
        self._update_health_data()

    # ----------
    # Commands
    # ----------
    @command(dtype_in="DevULong", dtype_out="DevVarLongStringArray")
    def PowerOnTpm(  # pylint: disable=invalid-name
        self: MccsSubrack, argin: int
    ) -> tuple[list[ResultCode], list[Optional[str]]]:
        """
        Power up a TPM.

        :param argin: the logical id of the TPM to power up

        :return: A tuple containing a return code and a string message
            indicating status. The message is for information purposes
            only.
        """
        handler = self.get_command_object("PowerOnTpm")
        result_code, message = handler(argin)
        return ([result_code], [message])

    @command(dtype_in="DevULong", dtype_out="DevVarLongStringArray")
    def PowerOffTpm(  # pylint: disable=invalid-name
        self: MccsSubrack, argin: int
    ) -> tuple[list[ResultCode], list[Optional[str]]]:
        """
        Power down a TPM.

        :param argin: the logical id of the TPM to power down

        :return: A tuple containing a return code and a string message
            indicating status. The message is for information purposes
            only.
        """
        handler = self.get_command_object("PowerOffTpm")
        result_code, message = handler(argin)
        return ([result_code], [message])

    @command(dtype_out="DevVarLongStringArray")
    def PowerUpTpms(  # pylint: disable=invalid-name
        self: MccsSubrack,
    ) -> tuple[list[ResultCode], list[Optional[str]]]:
        """
        Power up all TPMs.

        :return: A tuple containing a return code and a string message
            indicating status. The message is for information purposes
            only.
        """
        handler = self.get_command_object("PowerUpTpms")
        result_code, message = handler()
        return ([result_code], [message])

    @command(dtype_out="DevVarLongStringArray")
    def PowerDownTpms(  # pylint: disable=invalid-name
        self: MccsSubrack,
    ) -> tuple[list[ResultCode], list[Optional[str]]]:
        """
        Power down all TPMs.

        :return: A tuple containing a return code and a string message
            indicating status. The message is for information purposes
            only.
        """
        handler = self.get_command_object("PowerDownTpms")
        result_code, message = handler()
        return ([result_code], [message])

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def SetSubrackFanSpeed(  # pylint: disable=invalid-name
        self: MccsSubrack, argin: str
    ) -> tuple[list[ResultCode], list[Optional[str]]]:
        """
        Set the selected subrack backplane fan speed.

        :param argin: json dictionary with mandatory keywords

            * `subrack_fan_id` (int) fan id from 1 to 4
            * `speed_percent` - (float) fan speed in percent

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("SetSubrackFanSpeed")
        result_code, message = handler(argin)
        return ([result_code], [message])

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def SetSubrackFanMode(  # pylint: disable=invalid-name
        self: MccsSubrack, argin: str
    ) -> tuple[list[ResultCode], list[Optional[str]]]:
        """
        Set the selected subrack backplane fan mode.

        :param argin: json dictionary with mandatory keywords

            * `fan_id` (int) fan id from 1 to 4
            * `mode` - (int) mode: 1=MANUAL, 2=AUTO

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("SetSubrackFanMode")
        result_code, message = handler(argin)
        return ([result_code], [message])

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def SetPowerSupplyFanSpeed(  # pylint: disable=invalid-name
        self: MccsSubrack, argin: str
    ) -> tuple[list[ResultCode], list[Optional[str]]]:
        """
        Set the selected power supply fan speed.

        :param argin: json dictionary with mandatory keywords

            * `power_supply_id` (int) power supply id from 1 to 2
            * `speed_percent` - (float) fan speed in percent

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("SetPowerSupplyFanSpeed")
        result_code, message = handler(argin)
        return ([result_code], [message])

    # ----------
    # Attributes
    # ----------
    @attribute(
        dtype="DevString",
        format="%s",
    )
    def healthModelParams(self: MccsSubrack) -> str:
        """
        Get the health params from the health model.

        :return: the health params
        """
        return json.dumps(self._health_model.health_params)

    @healthModelParams.write  # type: ignore[no-redef]
    def healthModelParams(self: MccsSubrack, argin: str) -> None:
        """
        Set the params for health transition rules.

        :param argin: JSON-string of dictionary of health states
        """
        self._health_model.health_params = json.loads(argin)

    @attribute(dtype=int, label="TPM count", abs_change=1)
    def tpmCount(self: MccsSubrack) -> int:
        """
        Handle a Tango attribute read of TPM count.

        :return: the number of TPMs present in the subrack.
            When communication with the subrack is not established,
            this returns 0.
        """
        return self._tpm_count

    @attribute(dtype=(bool,), max_dim_x=8, label="TPM present")
    def tpmPresent(self: MccsSubrack) -> list[bool]:  # pylint: disable=invalid-name
        """
        Handle a Tango attribute read of which TPMs are present in the subrack.

        :return: whether a TPM is present in each bay.
            When communication with the subrack is not established,
            this returns an empty list.
        """
        return self._tpm_present or []

    @attribute(dtype=PowerState, label="TPM 1 power state")
    def tpm1PowerState(self: MccsSubrack) -> PowerState:  # pylint: disable=invalid-name
        """
        Handle a Tango attribute read of the power state of TPM 1.

        :return: the power state of TPM 1.
        """
        return self._tpm_power_states[0]

    @attribute(dtype=PowerState, label="TPM 2 power state")
    def tpm2PowerState(self: MccsSubrack) -> PowerState:  # pylint: disable=invalid-name
        """
        Handle a Tango attribute read of the power state of TPM 2.

        :return: the power state of TPM 2.
        """
        return self._tpm_power_states[1]

    @attribute(dtype=PowerState, label="TPM 3 power state")
    def tpm3PowerState(self: MccsSubrack) -> PowerState:  # pylint: disable=invalid-name
        """
        Handle a Tango attribute read of the power state of TPM 3.

        :return: the power state of TPM 3.
        """
        return self._tpm_power_states[2]

    @attribute(dtype=PowerState, label="TPM 4 power state")
    def tpm4PowerState(self: MccsSubrack) -> PowerState:  # pylint: disable=invalid-name
        """
        Handle a Tango attribute read of the power state of TPM 4.

        :return: the power state of TPM 4.
        """
        return self._tpm_power_states[3]

    @attribute(dtype=PowerState, label="TPM 5 power state")
    def tpm5PowerState(self: MccsSubrack) -> PowerState:  # pylint: disable=invalid-name
        """
        Handle a Tango attribute read of the power state of TPM 5.

        :return: the power state of TPM 5.
        """
        return self._tpm_power_states[4]

    @attribute(dtype=PowerState, label="TPM 6 power state")
    def tpm6PowerState(self: MccsSubrack) -> PowerState:  # pylint: disable=invalid-name
        """
        Handle a Tango attribute read of the power state of TPM 6.

        :return: the power state of TPM 6.
        """
        return self._tpm_power_states[5]

    @attribute(dtype=PowerState, label="TPM 7 power state")
    def tpm7PowerState(self: MccsSubrack) -> PowerState:  # pylint: disable=invalid-name
        """
        Handle a Tango attribute read of the power state of TPM 7.

        :return: the power state of TPM 7.
        """
        return self._tpm_power_states[6]

    @attribute(dtype=PowerState, label="TPM 8 power state")
    def tpm8PowerState(self: MccsSubrack) -> PowerState:  # pylint: disable=invalid-name
        """
        Handle a Tango attribute read of the power state of TPM 8.

        :return: the power state of TPM 8.
        """
        return self._tpm_power_states[7]

    @attribute(
        dtype=(float,),
        max_dim_x=2,
        label="Backplane temperatures",
        unit="Celsius",
        abs_change=0.1,
    )
    def backplaneTemperatures(self: MccsSubrack) -> list[float]:
        """
        Handle a Tango attribute read of the subrack backplane temperature.

        Two values are returned, respectively for the first (bays 1-4)
        and second (bays 5-8) halves of the backplane.

        :return: the backplane temperatures.
            When communication with the subrack is not established,
            this returns an empty list.
        """
        return self._backplane_temperatures()

    def _backplane_temperatures(self: MccsSubrack) -> list[float]:
        """
        Handle a Tango attribute read of the subrack backplane temperature.

        Two values are returned, respectively for the first (bays 1-4)
        and second (bays 5-8) halves of the backplane.

        :return: the backplane temperatures.
            When communication with the subrack is not established,
            this returns an empty list.
        """
        return self._hardware_attributes.get("backplaneTemperatures", None) or []

    @attribute(
        dtype=(float,),
        max_dim_x=2,
        label="Subrack board temperatures",
        unit="Celsius",
        abs_change=0.1,
    )
    def boardTemperatures(self: MccsSubrack) -> list[float]:
        """
        Handle a Tango attribute read of the subrack board temperature.

        Two values are returned.

        :return: the board temperatures.
            When communication with the subrack is not established,
            this returns an empty list.
        """
        return self._board_temperatures()

    def _board_temperatures(self: MccsSubrack) -> list[float]:
        """
        Handle a Tango attribute read of the subrack board temperature.

        Two values are returned.

        :return: the board temperatures.
            When communication with the subrack is not established,
            this returns an empty list.
        """
        return self._hardware_attributes.get("boardTemperatures", None) or []

    @attribute(
        dtype=(float,),
        label="Board current",
        abs_change=0.1,
    )
    def boardCurrent(self: MccsSubrack) -> list[float]:
        """
        Handle a Tango attribute read of subrack management board current.

        Total current provided by the two power supplies.

        :return: total board current, in a list of length 1.
            When communication with the subrack is not established,
            this returns an empty list.
        """
        return self._board_current()

    def _board_current(self: MccsSubrack) -> list[float]:
        """
        Handle a Tango attribute read of subrack management board current.

        Total current provided by the two power supplies.

        :return: total board current, in a list of length 1.
            When communication with the subrack is not established,
            this returns an empty list.
        """
        return self._hardware_attributes.get("boardCurrent", None) or []

    @attribute(
        dtype=(float,), max_dim_x=2, label="power supply currents", abs_change=0.1
    )
    def powerSupplyCurrents(self: MccsSubrack) -> list[float]:
        """
        Handle a Tango attribute read of the power supply currents.

        :return: the power supply currents.
            When communication with the subrack is not established,
            this returns an empty list.
        """
        return self._power_supply_currents()

    def _power_supply_currents(self: MccsSubrack) -> list[float]:
        """
        Handle a Tango attribute read of the power supply currents.

        :return: the power supply currents.
            When communication with the subrack is not established,
            this returns an empty list.
        """
        return self._hardware_attributes.get("powerSupplyCurrents", None) or []

    @attribute(
        dtype=(float,), max_dim_x=3, label="power supply fan speeds", abs_change=0.1
    )
    def powerSupplyFanSpeeds(self: MccsSubrack) -> list[float]:
        """
        Handle a Tango attribute read of the power supply fan speeds.

        Values expressed in percent of maximum.

        :return: the power supply fan speeds.
            When communication with the subrack is not established,
            this returns an empty list.
        """
        return self._powersupply_fan_speeds()

    def _powersupply_fan_speeds(self: MccsSubrack) -> list[float]:
        """
        Handle a Tango attribute read of the power supply fan speeds.

        Values expressed in percent of maximum.

        :return: the power supply fan speeds.
            When communication with the subrack is not established,
            this returns an empty list.
        """
        return self._hardware_attributes.get("powerSupplyFanSpeeds", None) or []

    @attribute(dtype=(float,), max_dim_x=2, label="power supply powers", abs_change=0.1)
    def powerSupplyPowers(self: MccsSubrack) -> list[float]:
        """
        Handle a Tango attribute read of the power supply powers.

        :return: the power supply powers.
            When communication with the subrack is not established,
            this returns an empty list.
        """
        return self._power_supply_powers()

    def _power_supply_powers(self: MccsSubrack) -> list[float]:
        """
        Handle a Tango attribute read of the power supply powers.

        :return: the power supply powers.
            When communication with the subrack is not established,
            this returns an empty list.
        """
        return self._hardware_attributes.get("powerSupplyPowers", None) or []

    @attribute(
        dtype=(float,), max_dim_x=2, label="power supply voltages", abs_change=0.1
    )
    def powerSupplyVoltages(self: MccsSubrack) -> list[float]:
        """
        Handle a Tango attribute read of the power supply voltages.

        :return: the power supply voltages.
            When communication with the subrack is not established,
            this returns an empty list.
        """
        return self._power_supply_voltages()

    def _power_supply_voltages(self: MccsSubrack) -> list[float]:
        """
        Handle a Tango attribute read of the power supply voltages.

        :return: the power supply voltages.
            When communication with the subrack is not established,
            this returns an empty list.
        """
        return self._hardware_attributes.get("powerSupplyVoltages", None) or []

    @attribute(dtype=(float,), max_dim_x=4, label="subrack fan speeds", abs_change=0.1)
    def subrackFanSpeeds(self: MccsSubrack) -> list[float]:
        """
        Handle a Tango attribute read of the subrack fan speeds, in RPM.

        :return: the subrack fan speeds.
            When communication with the subrack is not established,
            this returns an empty list.
        """
        return self._subrack_fan_speeds()

    def _subrack_fan_speeds(self: MccsSubrack) -> list[float]:
        """
        Handle a Tango attribute read of the subrack fan speeds, in RPM.

        :return: the subrack fan speeds.
            When communication with the subrack is not established,
            this returns an empty list.
        """
        return self._hardware_attributes.get("subrackFanSpeeds", None) or []

    @attribute(
        dtype=(float,), max_dim_x=4, label="subrack fan speeds (%)", abs_change=0.1
    )
    def subrackFanSpeedsPercent(self: MccsSubrack) -> list[float]:
        """
        Handle a Tango attribute read of the subrack fan speeds, in percent.

        This is the commanded setpoint; the relation between this level and
        the actual RPMs is not linear. Subrack speed is managed
        automatically by the controller, by default (see
        subrack_fan_mode).

        Commanded speed is the same for fans 1-2 and 3-4.

        :return: the subrack fan speed setpoints in percent.
            When communication with the subrack is not established,
            this returns an empty list.
        """
        return self._hardware_attributes.get("subrackFanSpeedsPercent", None) or []

    # TODO: https://gitlab.com/tango-controls/pytango/-/issues/483
    # Once this is fixed, we can use dtype=(FanMode,).
    @attribute(dtype=(int,), max_dim_x=4, label="subrack fan modes", abs_change=1)
    def subrackFanModes(self: MccsSubrack) -> list[int]:
        """
        Handle a Tango attribute read of the subrack fan modes.

        :return: the subrack fan modes.
            When communication with the subrack is not established,
            this returns an empty list.
        """
        return self._hardware_attributes.get("subrackFanModes", None) or []

    @attribute(dtype=(float,), max_dim_x=8, label="TPM currents", abs_change=0.1)
    def tpmCurrents(self: MccsSubrack) -> list[float]:
        """
        Handle a Tango attribute read of the TPM currents.

        :return: the TPM currents.
            When communication with the subrack is not established,
            this returns an empty list.
        """
        return self._tpm_currents()

    def _tpm_currents(self: MccsSubrack) -> list[float]:
        """
        Handle a Tango attribute read of the TPM currents.

        :return: the TPM currents.
            When communication with the subrack is not established,
            this returns an empty list.
        """
        return self._hardware_attributes.get("tpmCurrents", None) or []

    @attribute(dtype=(float,), max_dim_x=8, label="TPM powers", abs_change=0.1)
    def tpmPowers(self: MccsSubrack) -> list[float]:
        """
        Handle a Tango attribute read of the TPM powers.

        :return: the TPM powers.
            When communication with the subrack is not established,
            this returns an empty list.
        """
        return self._tpm_powers()

    def _tpm_powers(self: MccsSubrack) -> list[float]:
        """
        Handle a Tango attribute read of the TPM powers.

        :return: the TPM powers.
            When communication with the subrack is not established,
            this returns an empty list.
        """
        return self._hardware_attributes.get("tpmPowers", None) or []

    # Not implemented on SMB
    # @attribute(dtype=(float,), max_dim_x=8, label="TPM temperatures", abs_change=0.1)
    # def tpmTemperatures(self: MccsSubrack) -> list[float]:
    #     """
    #     Handle a Tango attribute read of the TPM temperatures.

    #     :return: the TPM temperatures.
    #         When communication with the subrack is not established,
    #         this returns an empty list.
    #     """
    #     return self._hardware_attributes.get("tpmTemperatures", None) or []

    @attribute(dtype=(float,), max_dim_x=8, label="TPM voltages", abs_change=0.1)
    def tpmVoltages(self: MccsSubrack) -> list[float]:
        """
        Handle a Tango attribute read of the TPM voltages.

        :return: the TPM voltages
        """
        return self._tpm_voltages()

    def _tpm_voltages(self: MccsSubrack) -> list[float]:
        """
        Handle a Tango attribute read of the TPM voltages.

        :return: the TPM voltages
        """
        return self._hardware_attributes.get("tpmVoltages", None) or []

    def _clear_hardware_attributes(self: MccsSubrack) -> None:
        # TODO: It should would be nice to push change events here,
        # but it seems pytango does not permit pushing change events
        # for None / invalid values.
        self._hardware_attributes.clear()
        self._update_tpm_present(None)

    # ----------
    # Callbacks
    # ----------
    def _communication_state_changed(
        self: MccsSubrack, communication_state: CommunicationStatus
    ) -> None:
        self.logger.debug(
            "Device received notification from component manager that communication "
            f"with the component is {communication_state.name}."
        )
        if communication_state != CommunicationStatus.ESTABLISHED:
            self._update_tpm_power_states(
                [PowerState.UNKNOWN] * SubrackData.TPM_BAY_COUNT
            )
            self._clear_hardware_attributes()

        super()._communication_state_changed(communication_state)
        self._health_model.update_state(
            communicating=(communication_state == CommunicationStatus.ESTABLISHED)
        )

    def _component_state_changed(
        self: MccsSubrack,
        fault: Optional[bool] = None,
        power: Optional[PowerState] = None,
        **kwargs: Any,
    ) -> None:
        super()._component_state_changed(fault=fault, power=power)
        self._health_model.update_state(fault=fault, power=power)

        for key, value in kwargs.items():
            special_update_method = getattr(self, f"_update_{key}", None)
            if special_update_method is None:
                tango_attribute_name = self._ATTRIBUTE_MAP[key]
                self._hardware_attributes[tango_attribute_name] = value
                self.push_change_event(tango_attribute_name, value)
            else:
                special_update_method(value)

        tpm_power_state = None
        if power == PowerState.OFF:
            tpm_power_state = PowerState.NO_SUPPLY
        elif power == PowerState.UNKNOWN:
            tpm_power_state = PowerState.UNKNOWN
        if tpm_power_state is not None:
            self._update_tpm_power_states([tpm_power_state] * SubrackData.TPM_BAY_COUNT)
            self._clear_hardware_attributes()
        self._update_health_data()

    def _health_changed(self: MccsSubrack, health: HealthState) -> None:
        """
        Handle change in this device's health state.

        This is a callback hook, called whenever the HealthModel's
        evaluated health state changes. It is responsible for updating
        the tango side of things i.e. making sure the attribute is up to
        date, and events are pushed.

        :param health: the new health value
        """
        if self._health_state != health:
            self._health_state = health
            self.push_change_event("healthState", health)

    def _update_board_current(self: MccsSubrack, board_current: float) -> None:
        if board_current is None:
            self._hardware_attributes["boardCurrent"] = None
            self.push_change_event("boardCurrent", [])
        else:
            self._hardware_attributes["boardCurrent"] = [board_current]
            self.push_change_event("boardCurrent", [board_current])
        self._update_health_data()

    def _update_tpm_present(
        self: MccsSubrack, tpm_present: Optional[list[bool]]
    ) -> None:
        if tpm_present is None:
            tpm_present = []
        if self._tpm_present == tpm_present:
            return
        self._tpm_present = tpm_present
        self.push_change_event("tpmPresent", tpm_present)

        tpm_count = tpm_present.count(True)
        if self._tpm_count == tpm_count:
            return
        self._tpm_count = tpm_count
        self.push_change_event("tpmCount", tpm_count)
        self._update_health_data()

    def _update_tpm_on_off(self: MccsSubrack, tpm_on_off: Optional[list[bool]]) -> None:
        if tpm_on_off is None:
            power_states = [PowerState.UNKNOWN] * SubrackData.TPM_BAY_COUNT
        else:
            power_states = [
                PowerState.ON if is_on else PowerState.OFF for is_on in tpm_on_off
            ]
        self._update_tpm_power_states(power_states)

    def _update_tpm_power_states(
        self: MccsSubrack, tpm_power_states: list[PowerState]
    ) -> None:
        changed = False
        for index, power_state in enumerate(tpm_power_states):
            if self._tpm_power_states[index] != power_state:
                changed = True
                self._tpm_power_states[index] = power_state
                self.push_change_event(f"tpm{index+1}PowerState", power_state)
        if changed:
            self._update_health_data()

    def _update_health_data(self: MccsSubrack) -> None:
        """Update the data points for the health model."""
        data = {
            "board_temps": self._board_temperatures(),
            "backplane_temps": self._backplane_temperatures(),
            "subrack_fan_speeds": self._subrack_fan_speeds(),
            "board_currents": self._board_current(),
            "tpm_currents": self._tpm_currents(),
            "power_supply_currents": self._power_supply_currents(),
            "tpm_voltages": self._tpm_voltages(),
            "power_supply_voltages": self._power_supply_voltages(),
            "tpm_power_states": self._tpm_power_states,
            "desired_fan_speeds": self._desired_fan_speeds,
            "clock_reqs": self.clock_presence,
        }
        self._health_model.update_data(data)


# ----------
# Run server
# ----------
def main(*args: str, **kwargs: str) -> int:
    """
    Launch an `MccsSubrack` Tango device server instance.

    :param args: positional arguments, passed to the Tango device
    :param kwargs: keyword arguments, passed to the sever

    :return: the Tango server exit code
    """
    return MccsSubrack.run_server(args=args or None, **kwargs)


if __name__ == "__main__":
    main()
