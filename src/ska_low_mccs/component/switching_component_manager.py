# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements functionality for switching between component managers."""
from __future__ import annotations  # allow forward references in type hints

from typing import Any, Hashable, cast

from ska_tango_base.control_model import SimulationMode

from ska_low_mccs.component import MccsComponentManagerProtocol


__all__ = [
    "Switcher",
    "SwitchingComponentManager",
    "DriverSimulatorSwitchingComponentManager",
]


class Switcher:
    """
    An abstract class for a class shim that allows switching between classes.

    The envisaged use case for this is a ComponentManager that switches
    between an underlying ComponentManager that drives hardware, and an
    underlying ComponentManager that drives a hardware simulator,
    depending on the value of the simulation_mode attribute.

    This class implements the switching functionality for that, but
    independently of any use case.

    The options are specified by a dictionary that maps from mode to the
    class that implements that mode:

    .. code-block:

        switcher_options = {
            "driver": Driver(),
            "simulator": Simulator(),
        }
        switcher = Switcher(switcher_options, "simulator")
        switcher.switcher_mode = "driver"

    The mode is given in strings in the example above, but can be any
    hashable type:

    .. code-block:

        switcher_options = {
            SimulationMode.FALSE: Driver(),
            SimulationMode.TRUE: Simulator(),
        }

    Instead of a class, ``None`` may be provided as a option. This is
    used to signify that a mode is valid but not yet provided for.
    Attempts to switch to such a mode will cause a
    ``NotImplementedError`` to be raised:

    .. code-block:

        switcher_options = {
            "driver": None,
            "simulator": Simulator(),
        }
        switcher = Switcher(switcher_options, "simulator")
        switcher.switcher_mode = "driver"  # raises NotImplementedError
    """

    def __init__(
        self,
        switcher_options: dict[Hashable, Any],
        initial_switcher_mode: Hashable,
    ):
        """
        Initialise a new Switcher instance.

        :param switcher_options: a dictionary that maps from modes to
            underlying component managers
        :param initial_switcher_mode: the mode that this ``Switcher``
            should start in.
        """
        self.__options = dict(switcher_options)
        self.switcher_mode = initial_switcher_mode

    @property
    def switcher_mode(self) -> Hashable:
        """
        Get the component manager mode.

        That is, which underlying component manager is driven by this
        ``SwitchingComponentManager``.

        :return: the component manager mode.
        """
        return self.__mode

    @switcher_mode.setter
    def switcher_mode(self: Switcher, mode: Hashable) -> None:
        """
        Set the component manager mode.

        That is, specify which of the underlying component managers are
        driven by this ``SwitchingComponentManager``.

        :param mode: the new mode for this component manager.

        :raises KeyError: if the mode is unrecognised.
        :raises NotImplementedError: if the registered option for the
            mode is ``None``.
        """
        if mode not in self.__options:
            raise KeyError(f"Unrecognised switcher mode '{mode}'.")
        elif self.__options[mode] is None:
            raise NotImplementedError(f"Unimplemented switcher mode '{str(mode)}'.")
        self.__mode = mode

    def __getattr__(self: Switcher, name: str, default_value: Any = None) -> Any:
        """
        Get value of an attribute not found in the usual ways.

        The request is passed down to the underlying component manager.

        :param name: name of the requested attribute
        :param default_value: value to return if the attribute is not
            found

        :return: the requested attribute
        """
        return getattr(self.__options[self.__mode], name, default_value)


class SwitchingComponentManager(Switcher):
    """
    A base component manager that switches between underlying base component managers.

    This class implements the interface of
    :py:class:`ska_low_mccs.component.component_manager.MccsComponentManager`
    by passing commands down to an underlying component manager. This
    underlying component manager is selected from multiple available
    component
    managers.

    An example of its use would be a component manager for a device
    that monitors and controls either a hardware component, or a
    simulator of that hardware component, depending on its simulation
    mode. In such a case we could:

    * Implement a component manager for the hardware driver;
    * Implement a component manager for the simulator;
    * Use this ``SwitchingBaseComponentManager`` as a component manager
      that uses a simulation mode setting to switch between hardware
      driver and simulator.

    The switching functionality is implemented in the Switcher class.
    This class is syntactic sugar that allows us to get the multiple
    inheritance right once and for all, and then hide it from other
    classes.
    """

    def __init__(
        self,
        component_managers: dict[Hashable, MccsComponentManagerProtocol | None],
        initial_mode: Hashable,
    ):
        """
        Initialise a new ComponentManager instance.

        :param component_managers: a dictionary that maps from modes to
            underlying component managers
        :param initial_mode: the mode that this
            ``SwitchingComponentManager`` should start in.
        """
        super().__init__(component_managers, initial_mode)


class DriverSimulatorSwitchingComponentManager(SwitchingComponentManager):
    """
    A component manager that switches between driver and simulator components.

    It uses the simulation mode to determine which component to drive.
    """

    def __init__(
        self: DriverSimulatorSwitchingComponentManager,
        driver_component_manager: MccsComponentManagerProtocol | None,
        simulator_component_manager: MccsComponentManagerProtocol | None,
        initial_simulation_mode: SimulationMode,
    ):
        """
        Initialise a new instance.

        :param driver_component_manager: component manager for the
            driver component (i.e. the "real" component").
        :param simulator_component_manager: component manager for the
            simulator component.
        :param initial_simulation_mode: what simulation mode to start
            in.
        """
        super().__init__(
            {
                SimulationMode.FALSE: driver_component_manager,
                SimulationMode.TRUE: simulator_component_manager,
            },
            initial_simulation_mode,
        )

    @property
    def simulation_mode(
        self: DriverSimulatorSwitchingComponentManager,
    ) -> SimulationMode:
        """
        Return the simulation mode.

        :return: the simulation mode
        """
        return cast(SimulationMode, self.switcher_mode)

    @simulation_mode.setter
    def simulation_mode(
        self: DriverSimulatorSwitchingComponentManager,
        value: SimulationMode,
    ) -> None:
        """
        Set the simulation mode.

        :param value: the new value for the simulation mode.
        """
        if self.switcher_mode != value:
            communicating = self.is_communicating
            if communicating:
                self.stop_communicating()
            self.switcher_mode = value
            if communicating:
                self.start_communicating()
