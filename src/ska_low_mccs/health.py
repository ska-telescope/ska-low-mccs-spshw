# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements infrastructure for health management in the MCCS subsystem."""

from __future__ import annotations  # allow forward references in type hints

from typing import Any, Callable

from ska_tango_base.control_model import HealthState

__all__ = ["HealthModel"]


class HealthModel:
    """
    A simple health model the supports.

    * HealthState.UNKNOWN -- when communication with the component is
      not established.

    * HealthState.FAILED -- when the component has faulted

    * HealthState.OK -- when neither of the above conditions holds.

    This health model does not support HealthState.DEGRADED. It is up to
    subclasses to implement support for DEGRADED if required.
    """

    def __init__(
        self: HealthModel,
        component_state_changed_callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """
        Initialise a new instance.

        :param component_state_changed_callback: callback to be called whenever
            there is a change to this this health model's evaluated
            health state.
        """
        self._communicating = False
        self._faulty = False
        self._health_state = self.evaluate_health()
        health = {"health_state": self._health_state}
        self._component_state_changed_callback = component_state_changed_callback
        self._component_state_changed_callback(health)

    @property
    def health_state(self: HealthModel) -> HealthState:
        """
        Return the health state.

        :return: the health state.
        """
        return self._health_state

    def update_health(self: HealthModel) -> None:
        """
        Update health state.

        This method calls the :py:meth:``evaluate_health`` method to
        figure out what the new health state should be, and then updates
        the ``health_state`` attribute, calling the callback if
        required.
        """
        print(f"XXXX evaluate_health()")
        health_state = self.evaluate_health()
        print(f"XXXX update_health {self._health_state} -> {health_state}")
        if self._health_state != health_state:
            self._health_state = health_state
            health = {"health_state": health_state}
            print(f"XXXX calling state_changed_callback with {health}")
            self._component_state_changed_callback(health)

    def evaluate_health(self: HealthModel) -> HealthState:
        """
        Re-evaluate the health state.

        This method contains the logic for evaluating the health. It is
        this method that should be extended by subclasses in order to
        define how health is evaluated by their particular device.

        :return: the new health state.
        """
        print(f"XXXX evaluate_health communicating?... {self._communicating}")
        if not self._communicating:
            print(f"XXXX why am I here?")
            return HealthState.UNKNOWN
        print(f"XXXX evaluate_health fauly?... {self._faulty}")
        if self._faulty:
            return HealthState.FAILED
        print(f"returning {HealthState.OK}")
        return HealthState.OK

    def component_fault(self: HealthModel, faulty: bool) -> None:
        """
        Handle a component experiencing or recovering from a fault.

        This is a callback hook that is called when the component goes
        into or out of FAULT state.

        :param faulty: whether the component has faulted or not
        """
        self._faulty = faulty
        self.update_health()

    def is_communicating(self: HealthModel, communicating: bool) -> None:
        """
        Handle change in communication with the component.

        :param communicating: whether communications with the component
            is established.
        """
        self._communicating = communicating
        self.update_health()
