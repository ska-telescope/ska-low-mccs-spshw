#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
This module contains an implementation of a simulator for APIU hardware.

Since access to antennas is via physical cables from the APIU, it is
assumed impossible for a real APIU to work with a simulated antenna, or
a simulated APIU with real antennas. Therefore this module simulates an
APIU and its antennas together.
"""

from __future__ import annotations  # allow forward references in type hints

import functools
from typing import Any, Callable, Optional, TypeVar, cast

from ska_control_model import PowerState, ResultCode
from ska_low_mccs_common.component import ObjectComponent
from typing_extensions import Final

Wrapped = TypeVar("Wrapped", bound=Callable[..., Any])


def check_antenna_id(func: Wrapped) -> Wrapped:
    """
    Return a function that checks the antenna id before calling a function.

    This function is intended to be used as a decorator. It can only
    be used to decorate methods whose first argument (after self) is the
    antenna id:

    .. code-block:: python

        @check_antenna_id
        def simulate_antenna_voltage(self, antenna_id, voltage):
            ...

    :param func: the wrapped function

    :return: the wrapped function
    """

    @functools.wraps(func)
    def _wrapper(
        apiu_simulator: ApiuSimulator,
        antenna_id: int,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Check power_state before calling the function.

        This is a wrapper function that implements the functionality of
        the decorator.

        :param apiu_simulator: the apiu simulator ("self" in the method
            call)
        :param antenna_id: this APIU's internal id for the antenna to be
            turned off
        :param args: positional arguments to the wrapped function
        :param kwargs: keyword arguments to the wrapped function

        :raises ValueError: if the component is not powered on on.

        :return: whatever the wrapped function returns
        """
        if antenna_id < 1 or antenna_id > apiu_simulator.antenna_count:
            raise ValueError(
                f"Cannot access antenna {antenna_id}; "
                f"this APIU has {apiu_simulator.antenna_count} antennas."
            )
        return func(apiu_simulator, antenna_id, *args, **kwargs)

    return cast(Wrapped, _wrapper)


# pylint: disable=too-many-instance-attributes,too-many-public-methods
class ApiuSimulator(ObjectComponent):
    """A simulator of APIU hardware."""

    DEFAULT_VOLTAGE = 3.2
    DEFAULT_CURRENT = 20.2
    DEFAULT_TEMPERATURE = 23.6
    DEFAULT_HUMIDITY = 24.9
    DEFAULT_ANTENNA_VOLTAGE: Final[float] = 3.4
    DEFAULT_ANTENNA_CURRENT: Final[float] = 20.5
    DEFAULT_ANTENNA_TEMPERATURE: Final[float] = 23.8

    def __init__(
        self: ApiuSimulator,
        antenna_count: int,
        component_state_changed_callback: Callable[[dict[str, Any]], None],
        initial_fault: bool = False,
    ) -> None:
        """
        Initialise a new instance.

        :param antenna_count: number of antennas that are attached to
            this APIU simulator
        :param initial_fault: whether the simulator should start by
            simulating a fault.
        :param component_state_changed_callback: callback to be called when the
            component faults (or stops faulting)
        """
        self._is_faulty = initial_fault
        self._fault_callback: Optional[
            Callable[[dict[str, Any]], None]
        ] = component_state_changed_callback
        self._antenna_power_changed_callback: Optional[
            Callable[[dict[str, Any]], None]
        ] = component_state_changed_callback

        self._voltage = self.DEFAULT_VOLTAGE
        self._current = self.DEFAULT_CURRENT
        self._temperature = self.DEFAULT_TEMPERATURE
        self._humidity = self.DEFAULT_HUMIDITY

        self._antenna_data = [
            {
                "power_state": PowerState.OFF,
                "voltage": self.DEFAULT_ANTENNA_VOLTAGE,
                "current": self.DEFAULT_ANTENNA_CURRENT,
                "temperature": self.DEFAULT_ANTENNA_TEMPERATURE,
            }
            for i in range(antenna_count)
        ]

    def set_fault_callback(
        self: ApiuSimulator, fault_callback: Optional[Callable[[dict[str, Any]], None]]
    ) -> None:
        """
        Set the callback to be called when the component faults.

        If a callback is provided (i.e. not None), then this method
        registers it, then calls it immediately.

        If the value provided is None, then any set callback is removed.

        :param fault_callback: the callback to be called when a fault
            occurs
        """
        self._fault_callback = fault_callback
        if fault_callback is not None:
            fault_callback({"fault": self._is_faulty})

    @property
    def faulty(self: ApiuSimulator) -> bool:
        """
        Return whether this component is faulty.

        :return: whether this component is faulty.
        """
        return self._is_faulty

    def _update_fault(self: ApiuSimulator, is_faulty: bool) -> None:
        """
        Update whether this component is faulty, ensuring callbacks are called.

        :param is_faulty: whether this component is faulty.
        """
        if self._is_faulty != is_faulty:
            self._is_faulty = is_faulty
            if self._fault_callback is not None:
                self._fault_callback({"fault": is_faulty})

    def simulate_fault(self: ApiuSimulator, is_faulty: bool) -> None:
        """
        Simulate an unspecified fault in the APIU (or recovery from a fault).

        :param is_faulty: whether this component is faulty.
        """
        self._update_fault(is_faulty)

    @property
    def voltage(self: ApiuSimulator) -> float:
        """
        Return my voltage.

        :return: my voltage
        """
        return self._voltage

    def simulate_voltage(self: ApiuSimulator, voltage: float) -> None:
        """
        Simulate a change in APIU voltage.

        :param voltage: the new APIU voltage value to be simulated
        """
        self._voltage = voltage

    @property
    def current(self: ApiuSimulator) -> float:
        """
        Return my current.

        :return: my current
        """
        return self._current

    def simulate_current(self: ApiuSimulator, current: float) -> None:
        """
        Simulate a change in APIU current.

        :param current: the new APIU current value to be simulated
        """
        self._current = current

    @property
    def temperature(self: ApiuSimulator) -> float:
        """
        Return my temperature.

        :return: my temperature
        """
        return self._temperature

    def simulate_temperature(self: ApiuSimulator, temperature: float) -> None:
        """
        Simulate a change in APIU temperature.

        :param temperature: the new APIU temperature value to be
            simulated
        """
        self._temperature = temperature

    @property
    def humidity(self: ApiuSimulator) -> float:
        """
        Return my humidity.

        :return: my humidity
        """
        return self._humidity

    def simulate_humidity(self: ApiuSimulator, humidity: float) -> None:
        """
        Simulate a change in APIU humidity.

        :param humidity: the new APIU humidity value to be simulated
        """
        self._humidity = humidity

    def set_antenna_power_changed_callback(
        self: ApiuSimulator,
        antenna_power_changed_callback: Optional[Callable[[dict[str, Any]], None]],
    ) -> None:
        """
        Set the power changed callback.

        To be called when there is a change to the power mode of one or
        more antennas.

        If a callback is provided (i.e. not None), then this method
        registers it, then calls it immediately.

        If the value provided is None, then any set callback is removed.

        :param antenna_power_changed_callback: the callback to be called
            when the power mode of an antenna changes
        """
        self._antenna_power_changed_callback = antenna_power_changed_callback
        self._antenna_power_changed()

    def _antenna_power_changed(self: ApiuSimulator) -> None:
        """
        Handle a change in antenna power.

        This is a helper method that calls the callback if it exists.
        """
        if self._antenna_power_changed_callback is not None:
            self._antenna_power_changed_callback(
                {"are_antennas_on": self.are_antennas_on()}
            )

    @property
    def antenna_count(self: ApiuSimulator) -> int:
        """
        Return the number of antennas attached to this APIU.

        :return: the number of antennas attached to this APIU.
        """
        return len(self._antenna_data)

    def are_antennas_on(self: ApiuSimulator) -> list[bool]:
        """
        Return whether each antenna is powered or not.

        :return: whether each antenna is powered or not.
        """
        return [
            antenna["power_state"] == PowerState.ON for antenna in self._antenna_data
        ]

    @check_antenna_id
    def is_antenna_on(self: ApiuSimulator, antenna_id: int) -> bool:
        """
        Return whether a specified antenna is turned on.

        :param antenna_id: this APIU's internal id for the antenna to be
            turned off

        :return: whether the antenna is on
        """
        return self._antenna_data[antenna_id - 1]["power_state"] == PowerState.ON

    @check_antenna_id
    def turn_off_antenna(self: ApiuSimulator, antenna_id: int) -> ResultCode | None:
        """
        Turn off a specified antenna.

        :param antenna_id: this APIU's internal id for the antenna to be
            turned off

        :return: a result code, or None if there was nothing to do
        """
        if self._antenna_data[antenna_id - 1]["power_state"] == PowerState.OFF:
            return None

        self._antenna_data[antenna_id - 1]["power_state"] = PowerState.OFF
        self._antenna_power_changed()
        return ResultCode.OK

    @check_antenna_id
    def turn_on_antenna(self: ApiuSimulator, antenna_id: int) -> ResultCode | None:
        """
        Turn on a specified antenna.

        :param antenna_id: this APIU's internal id for the antenna to be
            turned on

        :return: a result code, or None if there was nothing to do
        """
        if self._antenna_data[antenna_id - 1]["power_state"] == PowerState.ON:
            return None

        self._antenna_data[antenna_id - 1]["power_state"] = PowerState.ON
        self._antenna_power_changed()
        return ResultCode.OK

    def turn_off_antennas(self: ApiuSimulator) -> ResultCode | None:
        """
        Turn off all antennas.

        :return: a result code, or None if there was nothing to do
        """
        if all(
            antenna["power_state"] == PowerState.OFF for antenna in self._antenna_data
        ):
            return None

        for antenna in self._antenna_data:
            antenna["power_state"] = PowerState.OFF
        self._antenna_power_changed()
        return ResultCode.OK

    def turn_on_antennas(self: ApiuSimulator) -> ResultCode | None:
        """
        Turn on all antennas.

        :return: a result code, or None if there was nothing to do
        """
        if all(
            antenna["power_state"] == PowerState.ON for antenna in self._antenna_data
        ):
            return None

        for antenna in self._antenna_data:
            antenna["power_state"] = PowerState.ON
        self._antenna_power_changed()
        return ResultCode.OK

    @check_antenna_id
    def get_antenna_current(self: ApiuSimulator, antenna_id: int) -> float:
        """
        Get the current of a specified antenna.

        :param antenna_id: this APIU's internal id for the
            antenna for which the current is requested

        :return: the antenna current

        :raises ValueError: if the antenna is not powered on.
        """
        if not self.is_antenna_on(antenna_id):
            raise ValueError("Antenna is not powered on.")

        return self._antenna_data[antenna_id - 1]["current"]

    @check_antenna_id
    def simulate_antenna_current(
        self: ApiuSimulator, antenna_id: int, current: float
    ) -> None:
        """
        Simulate a change in antenna current.

        :param antenna_id: this APIU's internal id for the
            antenna for which the current is to be simulated
        :param current: the new antenna current value to be simulated

        :raises ValueError: if the antenna is not powered on.
        """
        if not self.is_antenna_on(antenna_id):
            raise ValueError("Antenna is not powered on.")

        self._antenna_data[antenna_id - 1]["current"] = current

    @check_antenna_id
    def get_antenna_voltage(self: ApiuSimulator, antenna_id: int) -> float:
        """
        Get the voltage of a specified antenna.

        :param antenna_id: this APIU's internal id for the
            antenna for which the voltage is requested

        :return: the antenna voltage

        :raises ValueError: if the antenna is not powered on.
        """
        if not self.is_antenna_on(antenna_id):
            raise ValueError("Antenna is not powered on.")

        return self._antenna_data[antenna_id - 1]["voltage"]

    @check_antenna_id
    def simulate_antenna_voltage(
        self: ApiuSimulator, antenna_id: int, voltage: float
    ) -> None:
        """
        Simulate a change in antenna voltage.

        :param antenna_id: this APIU's internal id for the
            antenna for which the voltage is to be simulated
        :param voltage: the new antenna voltage value to be simulated

        :raises ValueError: if the antenna is not powered on.
        """
        if not self.is_antenna_on(antenna_id):
            raise ValueError("Antenna is not powered on.")

        self._antenna_data[antenna_id - 1]["voltage"] = voltage

    @check_antenna_id
    def get_antenna_temperature(self: ApiuSimulator, antenna_id: int) -> float:
        """
        Get the temperature of a specified antenna.

        :param antenna_id: this APIU's internal id for the
            antenna for which the temperature is requested

        :return: the antenna temperature

        :raises ValueError: if the antenna is not powered on.
        """
        if not self.is_antenna_on(antenna_id):
            raise ValueError("Antenna is not powered on.")

        return self._antenna_data[antenna_id - 1]["temperature"]

    @check_antenna_id
    def simulate_antenna_temperature(
        self: ApiuSimulator, antenna_id: int, temperature: float
    ) -> None:
        """
        Simulate a change in antenna temperature.

        :param antenna_id: this APIU's internal id for the
            antenna for which the temperature is to be simulated
        :param temperature: the new antenna temperature value to be
            simulated

        :raises ValueError: if the antenna is not powered on.
        """
        if not self.is_antenna_on(antenna_id):
            raise ValueError("Antenna is not powered on.")

        self._antenna_data[antenna_id - 1]["temperature"] = temperature
