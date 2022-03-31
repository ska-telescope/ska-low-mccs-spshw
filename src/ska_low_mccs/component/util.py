# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements utils for component managers in MCCS."""
from __future__ import annotations  # allow forward references in type hints

import functools
from typing import Any, Callable, TypeVar, cast

from ska_tango_base.control_model import CommunicationStatus, PowerState

from ska_low_mccs.component import MccsComponentManager

__all__ = ["check_communicating", "check_on"]


Wrapped = TypeVar("Wrapped", bound=Callable[..., Any])


def check_communicating(func: Wrapped) -> Wrapped:
    """
    Return a function that checks component communication before calling a function.

    The component manager needs to have established communications with
    the component, in order for the function to be called.

    This function is intended to be used as a decorator:

    .. code-block:: python

        @check_communicating
        def scan(self):
            ...

    :param func: the wrapped function

    :return: the wrapped function
    """

    @functools.wraps(func)
    def _wrapper(
        component_manager: MccsComponentManager,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Check for component communication before calling the function.

        This is a wrapper function that implements the functionality of
        the decorator.

        :param component_manager: the component manager to check
        :param args: positional arguments to the wrapped function
        :param kwargs: keyword arguments to the wrapped function

        :raises ConnectionError: if communication with the component has
            not been established.
        :return: whatever the wrapped function returns
        """
        if component_manager.communication_status != CommunicationStatus.ESTABLISHED:
            raise ConnectionError(
                f"Cannot execute '{type(component_manager).__name__}.{func.__name__}'. "
                "Communication with component is not established."
            )
        return func(component_manager, *args, **kwargs)

    return cast(Wrapped, _wrapper)


def check_on(func: Wrapped) -> Wrapped:
    """
    Return a function that checks that a component is on before calling a function.

    The component manager will check its power mode property, which
    needs to be PowerState.OFF in order for the function to be called.

    This function is intended to be used as a decorator:

    .. code-block:: python

        @check_on
        def get_antenna_voltage(self):
            ...

    :param func: the wrapped function

    :return: the wrapped function
    """

    @functools.wraps(func)
    def _wrapper(
        component_manager: MccsComponentManager,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Check that the component is on before before calling the function.

        This is a wrapper function that implements the functionality of
        the decorator.

        :param component_manager: the component manager to check
        :param args: positional arguments to the wrapped function
        :param kwargs: keyword arguments to the wrapped function

        :raises ConnectionError: if communication with the component has
            not been established.
        :return: whatever the wrapped function returns
        """
        if component_manager.power_state != PowerState.ON:
            raise ConnectionError(
                f"Cannot execute {type(component_manager).__name__}.{func.__name__}. "
                "Component is not turned on."
            )
        return func(component_manager, *args, **kwargs)

    return cast(Wrapped, _wrapper)
