#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements a class for recording intermediate healths for MccsTile."""
from logging import Logger
from typing import Callable

from ska_control_model import HealthState
from ska_low_mccs_common import HealthRecorder


class TileHealthRecorder(HealthRecorder):
    """This class manages health recording for MccsTile."""

    def __init__(
        self,
        trl: str,
        logger: Logger,
        *,
        attributes: list[str],
        health_callback: Callable[[HealthState, str], None],
        attr_conf_callback: Callable[[str], None],
        intermediate_health_callback: Callable[[str, HealthState], None],
        health_groups: dict[str, list[str]],
    ) -> None:
        """
        Initialise a new instance.

        :param trl: trl of this device, it subscribes to its own events.
        :param logger: a logger for this object to use.
        :param attributes: to subscribe to for recording attribute quality.
        :param health_callback: callback to be called
            whenever the healthstate changes.
        :param attr_conf_callback: callback to call when the attr conf changes.
            This is a workaround until implemented in Tango. If you reconfigure the
            alarms of a non-alarming attribute such that it would be in alarm, but don't
            push an event, it will be OK until the attribute is updated.
        :param intermediate_health_callback: callback to be called whenever the
            intermediate healths change.
        :param health_groups: dictionary containing health groups keyed to the
            attributes in that group.
        """
        self._intermediate_health_callback = intermediate_health_callback
        self._health_groups: dict[str, list] = health_groups
        self._intermediate_healths: dict[str, tuple] = {}
        super().__init__(
            trl,
            logger,
            attributes=attributes,
            health_callback=health_callback,
            attr_conf_callback=attr_conf_callback,
        )

    def _evaluate_intermediate_health(self) -> None:
        for group, attrs in self._health_groups.items():
            intermediate_attrs = {
                name: state
                for name, state in self._attribute_state.items()
                if name in attrs
            }
            intermediate_health, intermediate_report = self._evaluate_health(
                intermediate_attrs
            )
            (
                last_intermediate_health,
                last_intermediate_report,
            ) = self._intermediate_healths.get(
                group, (HealthState.UNKNOWN, "No attributes read")
            )
            if (
                intermediate_health != last_intermediate_health
                or intermediate_report != last_intermediate_report
            ):
                self._intermediate_health_callback(group, intermediate_health)

    def update_health(self) -> None:
        """Update the intermediate healths alongside the overall health."""
        self._evaluate_intermediate_health()
        super().update_health()
