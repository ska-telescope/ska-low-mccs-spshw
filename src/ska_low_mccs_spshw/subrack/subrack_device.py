# -*- coding: utf-8 -*-
#
# (c) 2022 CSIRO.
#
# Distributed under the terms of the CSIRO Open Source Software Licence
# Agreement
# See LICENSE.txt for more info.

"""This module provides a Tango device for a PSI-Low subrack."""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

import tango
from ska_control_model import CommunicationStatus, PowerState
from ska_tango_base.base import BaseComponentManager, SKABaseDevice
from ska_tango_base.commands import (
    CommandTrackerProtocol,
    DeviceInitCommand,
    ResultCode,
    SubmittedSlowCommand,
)
from tango.server import attribute, command, device_property, run

from .subrack_component_manager import SubrackComponentManager
from .subrack_data import FanMode, SubrackData

__all__ = ["MccsSubrack", "main"]


# pylint: disable-next=too-few-public-methods
class _SetSubrackFanSpeedCommand(SubmittedSlowCommand):
    """
    Class for handling the SetSubrackFanSpeed command.

    This command sets the selected subrack fan speed.
    """

    def __init__(
        self: _SetSubrackFanSpeedCommand,
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
        super().__init__(
            "SetSubrackFanSpeed",
            command_tracker,
            component_manager,
            "set_subrack_fan_speed",
            callback=None,
            logger=logger,
        )

    def do(  # type: ignore[override]
        self: _SetSubrackFanSpeedCommand,
        *args: Any,
        subrack_fan_id: Optional[int] = None,
        speed_percent: Optional[float] = None,
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

        :raises ValueError: if the JSON input lacks of mandatory parameters
        """
        assert (
            not args and not kwargs
        ), f"do method has unexpected arguments: {args}, {kwargs}"

        if subrack_fan_id is None:
            self.logger.error("subrack_fan_id key is mandatory.")
            raise ValueError("subrack_fan_id key is mandatory.")
        if speed_percent is None:
            self.logger.error("speed_percent key is mandatory.")
            raise ValueError("speed_percent key is mandatory.")

        return super().do(subrack_fan_id, speed_percent)


# pylint: disable-next=too-few-public-methods
class _SetSubrackFanModeCommand(SubmittedSlowCommand):
    """
    Class for handling the SetSubrackFanMode command.

    This command set the selected subrack fan mode.
    """

    def __init__(
        self: _SetSubrackFanModeCommand,
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
        super().__init__(
            "SetSubrackFanMode",
            command_tracker,
            component_manager,
            "set_subrack_fan_mode",
            callback=None,
            logger=logger,
        )

    def do(  # type: ignore[override]
        self: _SetSubrackFanModeCommand,
        *args: Any,
        fan_id: Optional[int] = None,
        mode: Optional[int] = None,
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

        :raises ValueError: if the JSON input lacks of mandatory parameters
        """
        assert (
            not args and not kwargs
        ), f"do method has unexpected arguments: {args}, {kwargs}"

        if fan_id is None:
            self.logger.error("fan_id key is mandatory.")
            raise ValueError("fan_id key is mandatory.")
        if mode is None:
            self.logger.error("mode key is mandatory.")
            raise ValueError("mode key is mandatory.")

        return super().do(fan_id, FanMode(mode))


# pylint: disable-next=too-few-public-methods
class _SetPowerSupplyFanSpeedCommand(SubmittedSlowCommand):
    """
    Class for handling the SetPowerSupplyFanSpeed command.

    This command set the selected power supply fan speed.
    """

    def __init__(
        self: _SetPowerSupplyFanSpeedCommand,
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
        super().__init__(
            "SetPowerSupplyFanSpeed",
            command_tracker,
            component_manager,
            "set_power_supply_fan_speed",
            callback=None,
            logger=logger,
        )

    def do(  # type: ignore[override]
        self: _SetPowerSupplyFanSpeedCommand,
        *args: Any,
        power_supply_fan_id: Optional[int] = None,
        speed_percent: Optional[float] = None,
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

        :raises ValueError: if the JSON input lacks of mandatory parameters
        """
        assert (
            not args and not kwargs
        ), f"do method has unexpected arguments: {args}, {kwargs}"

        if power_supply_fan_id is None:
            self.logger.error("power_supply_fan_id key is mandatory.")
            raise ValueError("power_supply_fan_id key is mandatory.")
        if speed_percent is None:
            self.logger.error("speed_percent key is mandatory.")
            raise ValueError("speed_percent key is mandatory.")

        return super().do(power_supply_fan_id, speed_percent)


class MccsSubrack(SKABaseDevice):  # pylint: disable=too-many-public-methods
    """A Tango device for monitor and control of the PSI-Low subrack."""

    # A map from the compnent manager argument to the name of the Tango attribute.
    # This only includes one-to-one mappings. It lets us boilerplate these cases.
    # Attributes that don't map one-to-one are handled individually.
    # For example, tpm_on_off is not included here because it unpacks into eight
    # Tango attributes of the form tpmNPowerState.
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
        "subrack_fan_modes": "subrackFanModes",
        "tpm_currents": "tpmCurrents",
        "tpm_powers": "tpmPowers",
        "tpm_temperatures": "tpmTemperatures",
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

        self._attribute_quality = tango.AttrQuality.ATTR_INVALID
        self._tpm_present: Optional[list[bool]] = None
        self._tpm_count: Optional[int] = None
        self._tpm_power_states = [PowerState.UNKNOWN] * SubrackData.TPM_BAY_COUNT

        self._hardware_attributes: dict[str, Any] = {}

    # ----------
    # Properties
    # ----------
    SubrackIp = device_property(dtype=str)
    SubrackPort = device_property(dtype=int, default_value=8081)
    UpdateRate = device_property(dtype=float, default_value=15.0)

    # pylint: disable-next=too-few-public-methods
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
            self._device._attribute_quality = tango.AttrQuality.ATTR_INVALID

            self._device._tpm_present = None
            self._device._tpm_count = None
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
    def create_component_manager(self) -> SubrackComponentManager:
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

    def init_command_objects(self) -> None:
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
            ("SetSubrackFanSpeed", _SetSubrackFanSpeedCommand),
            ("SetSubrackFanMode", _SetSubrackFanModeCommand),
            ("SetPowerSupplyFanSpeed", _SetPowerSupplyFanSpeedCommand),
        ]:
            self.register_command_object(
                command_name,
                command_class(
                    self._command_tracker, self.component_manager, logger=self.logger
                ),
            )

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
        kwargs = json.loads(argin)
        handler = self.get_command_object("SetSubrackFanSpeed")
        result_code, message = handler(**kwargs)
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
        kwargs = json.loads(argin)
        handler = self.get_command_object("SetSubrackFanMode")
        result_code, message = handler(**kwargs)
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
        kwargs = json.loads(argin)
        handler = self.get_command_object("SetPowerSupplyFanSpeed")
        result_code, message = handler(**kwargs)
        return ([result_code], [message])

    # ----------
    # Attributes
    # ----------
    @attribute(dtype=int, label="TPM count", abs_change=1)
    def tpmCount(self: MccsSubrack, attr: tango.Attribute) -> None:
        """
        Handle a Tango attribute read of TPM count.

        :param attr: the Tango attribute to be updated
        """
        if self._tpm_count is None:
            attr.set_quality(tango.AttrQuality.ATTR_INVALID)
        else:
            attr.set_value(self._tpm_count)
            attr.set_quality(self._attribute_quality)

    @attribute(dtype=("DevBoolean",), max_dim_x=8, label="TPM present")
    def tpmPresent(  # pylint: disable=invalid-name
        self: MccsSubrack, attr: tango.Attribute
    ) -> None:
        """
        Handle a Tango attribute read of which TPMs are present in the subrack.

        :param attr: the Tango attribute to be updated
        """
        if self._tpm_present is None:
            attr.set_quality(tango.AttrQuality.ATTR_INVALID)
        else:
            attr.set_value(self._tpm_present)
            attr.set_quality(self._attribute_quality)

    @attribute(dtype=PowerState, label="TPM 1 power state", abs_change=1)
    def tpm1PowerState(  # pylint: disable=invalid-name
        self: MccsSubrack, attr: tango.Attribute
    ) -> None:
        """
        Handle a Tango attribute read of the power state of TPM 1.

        :param attr: the Tango attribute to be updated
        """
        self._get_tpm_power_state(attr, 1)

    @attribute(dtype=PowerState, label="TPM 2 power state")
    def tpm2PowerState(  # pylint: disable=invalid-name
        self: MccsSubrack, attr: tango.Attribute
    ) -> None:
        """
        Handle a Tango attribute read of the power state of TPM 2.

        :param attr: the Tango attribute to be updated
        """
        self._get_tpm_power_state(attr, 2)

    @attribute(dtype=PowerState, label="TPM 3 power state")
    def tpm3PowerState(  # pylint: disable=invalid-name
        self: MccsSubrack, attr: tango.Attribute
    ) -> None:
        """
        Handle a Tango attribute read of the power state of TPM 3.

        :param attr: the Tango attribute to be updated
        """
        self._get_tpm_power_state(attr, 3)

    @attribute(dtype=PowerState, label="TPM 4 power state")
    def tpm4PowerState(  # pylint: disable=invalid-name
        self: MccsSubrack, attr: tango.Attribute
    ) -> None:
        """
        Handle a Tango attribute read of the power state of TPM 4.

        :param attr: the Tango attribute to be updated
        """
        self._get_tpm_power_state(attr, 4)

    @attribute(dtype=PowerState, label="TPM 5 power state")
    def tpm5PowerState(  # pylint: disable=invalid-name
        self: MccsSubrack, attr: tango.Attribute
    ) -> None:
        """
        Handle a Tango attribute read of the power state of TPM 5.

        :param attr: the Tango attribute to be updated
        """
        self._get_tpm_power_state(attr, 5)

    @attribute(dtype=PowerState, label="TPM 6 power state")
    def tpm6PowerState(  # pylint: disable=invalid-name
        self: MccsSubrack, attr: tango.Attribute
    ) -> None:
        """
        Handle a Tango attribute read of the power state of TPM 6.

        :param attr: the Tango attribute to be updated
        """
        self._get_tpm_power_state(attr, 6)

    @attribute(dtype=PowerState, label="TPM 7 power state")
    def tpm7PowerState(  # pylint: disable=invalid-name
        self: MccsSubrack, attr: tango.Attribute
    ) -> None:
        """
        Handle a Tango attribute read of the power state of TPM 7.

        :param attr: the Tango attribute to be updated
        """
        self._get_tpm_power_state(attr, 7)

    @attribute(dtype=PowerState, label="TPM 8 power state")
    def tpm8PowerState(  # pylint: disable=invalid-name
        self: MccsSubrack, attr: tango.Attribute
    ) -> None:
        """
        Handle a Tango attribute read of the power state of TPM 8.

        :param attr: the Tango attribute to be updated
        """
        self._get_tpm_power_state(attr, 8)

    def _get_tpm_power_state(
        self: MccsSubrack, attr: tango.Attribute, tpm_number: int
    ) -> None:
        attr.set_value(self._tpm_power_states[tpm_number - 1])

        # TODO: https://gitlab.com/tango-controls/pytango/-/issues/498
        # Cannot set quality here
        # attribute.set_quality(self._attribute_quality)

    @attribute(
        dtype=(float,),
        max_dim_x=2,
        label="Backplane temperatures",
        unit="Celsius",
        abs_change=0.1,
    )
    def backplaneTemperatures(self: MccsSubrack, attr: tango.Attribute) -> None:
        """
        Handle a Tango attribute read of the subrack backplane temperature.

        Two values are returned, respectively for the first (bays 1-4)
        and second (bays 5-8) halves of the backplane.

        :param attr: the Tango attribute to be updated
        """
        self._get_hardware_attribute("backplaneTemperatures", attr)

    @attribute(
        dtype=(float,),
        max_dim_x=2,
        label="Subrack board temperatures",
        unit="Celsius",
        abs_change=0.1,
    )
    def boardTemperatures(self: MccsSubrack, attr: tango.Attribute) -> None:
        """
        Handle a Tango attribute read of the subrack board temperature.

        Two values are returned.

        :param attr: the Tango attribute to be updated
        """
        self._get_hardware_attribute("boardTemperatures", attr)

    @attribute(
        dtype=float,
        label="Board current",
        abs_change=0.1,
    )
    def boardCurrent(self: MccsSubrack, attr: tango.Attribute) -> None:
        """
        Handle a Tango attribute read of subrack management board current.

        Total current provided by the two power supplies.

        :param attr: the Tango attribute to be updated
        """
        self._get_hardware_attribute("boardCurrent", attr)

    @attribute(
        dtype=(float,), max_dim_x=2, label="power supply currents", abs_change=0.1
    )
    def powerSupplyCurrents(self: MccsSubrack, attr: tango.Attribute) -> None:
        """
        Handle a Tango attribute read of the power supply currents.

        :param attr: the Tango attribute to be updated
        """
        self._get_hardware_attribute("powerSupplyCurrents", attr)

    @attribute(
        dtype=(float,), max_dim_x=3, label="power supply fan speeds", abs_change=0.1
    )
    def powerSupplyFanSpeeds(self: MccsSubrack, attr: tango.Attribute) -> None:
        """
        Handle a Tango attribute read of the power supply fan speeds.

        Values expressed in percent of maximum.

        :param attr: the Tango attribute to be updated
        """
        self._get_hardware_attribute("powerSupplyFanSpeeds", attr)

    @attribute(dtype=(float,), max_dim_x=2, label="power supply powers", abs_change=0.1)
    def powerSupplyPowers(self: MccsSubrack, attr: tango.Attribute) -> None:
        """
        Handle a Tango attribute read of the power supply powers.

        :param attr: the Tango attribute to be updated
        """
        self._get_hardware_attribute("powerSupplyPowers", attr)

    @attribute(
        dtype=(float,), max_dim_x=2, label="power supply voltages", abs_change=0.1
    )
    def powerSupplyVoltages(self: MccsSubrack, attr: tango.Attribute) -> None:
        """
        Handle a Tango attribute read of the power supply voltages.

        :param attr: the Tango attribute to be updated
        """
        self._get_hardware_attribute("powerSupplyVoltages", attr)

    @attribute(dtype=(float,), max_dim_x=4, label="subrack fan speeds", abs_change=0.1)
    def subrackFanSpeeds(self: MccsSubrack, attr: tango.Attribute) -> None:
        """
        Handle a Tango attribute read of the subrack fan speeds, in RPM.

        :param attr: the Tango attribute to be updated
        """
        self._get_hardware_attribute("subrackFanSpeeds", attr)

    @attribute(
        dtype=(float,), max_dim_x=4, label="subrack fan speeds (%)", abs_change=0.1
    )
    def subrackFanSpeedsPercent(self: MccsSubrack, attr: tango.Attribute) -> None:
        """
        Handle a Tango attribute read of the subrack fan speeds, in percent.

        This is the commanded setpoint; the relation between this level and
        the actual RPMs is not linear. Subrack speed is managed
        automatically by the controller, by default (see
        subrack_fan_modes).

        Commanded speed is the same for fans 1-2 and 3-4.

        :param attr: the Tango attribute to be updated
        """
        self._get_hardware_attribute("subrackFanSpeedsPercent", attr)

    # TODO: https://gitlab.com/tango-controls/pytango/-/issues/483
    # Once this is fixed, we can use dtype=(FanMode,).
    @attribute(dtype=(int,), max_dim_x=4, label="subrack fan modes", abs_change=1)
    def subrackFanModes(self: MccsSubrack, attr: tango.Attribute) -> None:
        """
        Handle a Tango attribute read of the subrack fan modes.

        :param attr: the Tango attribute to be updated
        """
        self._get_hardware_attribute("subrackFanModes", attr)

    @attribute(dtype=(float,), max_dim_x=8, label="TPM currents", abs_change=0.1)
    def tpmCurrents(self: MccsSubrack, attr: tango.Attribute) -> None:
        """
        Handle a Tango attribute read of the TPM currents.

        :param attr: the Tango attribute to be updated
        """
        self._get_hardware_attribute("tpmCurrents", attr)

    @attribute(dtype=(float,), max_dim_x=8, label="TPM powers", abs_change=0.1)
    def tpmPowers(self: MccsSubrack, attr: tango.Attribute) -> None:
        """
        Handle a Tango attribute read of the TPM powers.

        :param attr: the Tango attribute to be updated
        """
        self._get_hardware_attribute("tpmPowers", attr)

    @attribute(dtype=(float,), max_dim_x=8, label="TPM temperatures", abs_change=0.1)
    def tpmTemperatures(self: MccsSubrack, attr: tango.Attribute) -> None:
        """
        Handle a Tango attribute read of the TPM temperatures.

        :param attr: the Tango attribute to be updated
        """
        self._get_hardware_attribute("tpmTemperatures", attr)

    @attribute(dtype=(float,), max_dim_x=8, label="TPM voltages", abs_change=0.1)
    def tpmVoltages(self: MccsSubrack, attr: tango.Attribute) -> None:
        """
        Handle a Tango attribute read of the TPM voltages.

        :param attr: the Tango attribute to be updated
        """
        self._get_hardware_attribute("tpmVoltages", attr)

    def _get_hardware_attribute(
        self: MccsSubrack, name: str, attr: tango.Attribute
    ) -> None:
        if name not in self._hardware_attributes:
            attr.set_quality(tango.AttrQuality.ATTR_INVALID)
        else:
            attr.set_value(self._hardware_attributes[name])
            attr.set_quality(self._attribute_quality)

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
        if communication_state == CommunicationStatus.ESTABLISHED:
            self._attribute_quality = tango.AttrQuality.ATTR_VALID
        elif communication_state == CommunicationStatus.NOT_ESTABLISHED:
            # If comms temporarily drop out, do not overwrite the last known
            # value, but mark it INVALID.
            self._attribute_quality = tango.AttrQuality.ATTR_INVALID
        else:
            # If comms are disabled, we set attribute values to UNKNOWN.
            self._attribute_quality = tango.AttrQuality.ATTR_VALID
            self._tpm_power_states = [PowerState.UNKNOWN] * SubrackData.TPM_BAY_COUNT

        super()._communication_state_changed(communication_state)

    def _component_state_changed(
        self: MccsSubrack,
        fault: Optional[bool] = None,
        power: Optional[PowerState] = None,
        **kwargs: Any,
    ) -> None:
        super()._component_state_changed(fault=fault, power=power)

        for key, value in kwargs.items():
            special_update_method = getattr(self, f"_update_{key}", None)
            if special_update_method is None:
                tango_attribute_name = self._ATTRIBUTE_MAP[key]
                self._hardware_attributes[tango_attribute_name] = value
                self.push_change_event(tango_attribute_name, value)
            else:
                special_update_method(value)

    def _update_tpm_present(self: MccsSubrack, tpm_present: list[bool]) -> None:
        if self._tpm_present == tpm_present:
            return
        self._tpm_present = tpm_present
        self.push_change_event("tpmPresent", tpm_present)

        tpm_count = tpm_present.count(True)
        if self._tpm_count == tpm_count:
            return
        self._tpm_count = tpm_count
        self.push_change_event("tpmCount", tpm_count)

    def _update_tpm_on_off(self: MccsSubrack, tpm_on_off: list[bool]) -> None:
        for tpm_number in range(1, SubrackData.TPM_BAY_COUNT + 1):
            power_state = (
                PowerState.ON if tpm_on_off[tpm_number - 1] else PowerState.OFF
            )
            if self._tpm_power_states[tpm_number - 1] != power_state:
                self._tpm_power_states[tpm_number - 1] = power_state
                self.push_change_event(f"tpm{tpm_number}PowerState", power_state)


# ----------
# Run server
# ----------
def main(args: Any = None, **kwargs: Any) -> int:
    """
    Launch a `MccsSubrack` Tango device server instance.

    :param args: arguments to the Tango device.
    :param kwargs: keyword arguments to the server

    :returns: the Tango server exit code
    """
    return run((MccsSubrack,), args=args, **kwargs)


if __name__ == "__main__":
    main()
