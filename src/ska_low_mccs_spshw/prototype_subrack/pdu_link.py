#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
The link between the prototype subrack device and the PDU that powers it.

:py:class:`PduLink` follows the power state of each PDU port that feeds the
subrack, and switches those ports. It is the only part of the device that talks
to ``MccsPdu``.

The link changes no device state. The device reads the port states on each
poll, so the device state still changes only on the poll thread.
"""
from __future__ import annotations

import functools
import logging
import threading
import time
from typing import Any, Final, Sequence

import numpy
import tango
from ska_control_model import PowerState, ResultCode
from ska_low_mccs_common.component.command_proxy import MccsCommandProxy
from ska_tango_base.callback_scheduler import CallbackScheduler

from .constants import PDU_ABORT_CHECK_INTERVAL, CommandOutcome

__all__ = ["PduLink", "combined_power_state", "port_power_state"]

# The PDU2-MIB onOff sensor states that a Raritan PDU reports for a port.
_RARITAN_ON: Final = 7
_RARITAN_OFF: Final = 8


def port_power_state(value: Any) -> PowerState:
    """
    Return the power state that one ``pduPort{N}State`` value gives.

    The attribute type depends on the PDU model. An Enlogic PDU reports a
    ``bool``. A Raritan PDU reports the PDU2-MIB onOff sensor state, which is
    7 for on and 8 for off. The ``bool`` test comes first, because a ``bool``
    is also an ``int``. Any other value gives ``UNKNOWN``.

    :param value: the value of the attribute.

    :return: the power state of the port.
    """
    if isinstance(value, (bool, numpy.bool_)):
        return PowerState.ON if value else PowerState.OFF
    if value == _RARITAN_ON:
        return PowerState.ON
    if value == _RARITAN_OFF:
        return PowerState.OFF
    return PowerState.UNKNOWN


def combined_power_state(port_states: Sequence[PowerState]) -> PowerState:
    """
    Return the power state of a subrack fed by these ports.

    The subrack PSUs are redundant, so one port that is on powers the board.

    :param port_states: the power state of each port that feeds the subrack.

    :return: ``ON`` if any port is on, ``OFF`` if every port is off, and
        ``UNKNOWN`` otherwise.
    """
    if PowerState.ON in port_states:
        return PowerState.ON
    if port_states and all(state == PowerState.OFF for state in port_states):
        return PowerState.OFF
    return PowerState.UNKNOWN


class PduLink:
    """
    Follow and switch the PDU ports that feed one subrack.

    The link subscribes to ``pduPort{N}State`` for each port, through the
    device's :py:class:`~ska_tango_base.callback_scheduler.CallbackScheduler`.
    The scheduler retries the PDU proxy, so a PDU that is down when the link is
    built is tolerated. The subscriptions last as long as the scheduler does.

    The link never reads the ports, so it knows only what the events say.
    ``MccsPdu`` pushes no event when it loses contact with its PDU, so a port
    can keep a stale state then. The device trusts its own poll over the PDU,
    so a stale state matters only while the board does not answer.

    The scheduler has one worker thread, so it is the only writer of the port
    states. Each update replaces the whole dictionary, so a reader on another
    thread never sees it part way through.
    """

    def __init__(
        self: PduLink,
        pdu_trl: str,
        ports: Sequence[int],
        callback_scheduler: CallbackScheduler,
        logger: logging.Logger,
    ) -> None:
        """
        Initialise a new instance, and subscribe to the PDU.

        :param pdu_trl: the TRL of the ``MccsPdu`` device.
        :param ports: the one-based numbers of the PDU ports that feed the
            subrack.
        :param callback_scheduler: the device's scheduler, which runs the
            event callbacks.
        :param logger: the logger to use.
        """
        self._pdu_trl = pdu_trl
        self._logger = logger
        self._port_states = dict.fromkeys(ports, PowerState.UNKNOWN)

        # A proxy rather than the TRL, because the scheduler resolves a short TRL
        # through the Tango database, which a test context does not have. It
        # reads the full TRL from the proxy instead, and builds its own proxy.
        proxy = tango.DeviceProxy(pdu_trl)
        for port in self._port_states:
            callback_scheduler.register_event_callback(
                proxy,
                f"pduPort{port}State",
                tango.EventType.CHANGE_EVENT,
                functools.partial(self._port_event, port),
            )

    # ----------
    # Properties
    # ----------
    @property
    def port_states(self: PduLink) -> list[PowerState]:
        """
        Return the power state of each port, in the order the ports were given.

        :return: the power state of each port.
        """
        return list(self._port_states.values())

    @property
    def power_state(self: PduLink) -> PowerState:
        """
        Return the power state of the subrack that these ports feed.

        :return: the combined power state of the ports.
        """
        return combined_power_state(self.port_states)

    # ---------------
    # PDU commands
    # ---------------
    def set_ports(self: PduLink, on: bool) -> tuple[ResultCode, str]:
        """
        Switch every port on or off.

        ``MccsPdu`` only queues each write, so this returns before the ports
        switch. Use :py:meth:`wait_for` to wait for them. The first port the
        PDU refuses ends the call, so later ports are not switched.

        :param on: true to switch the ports on, false to switch them off.

        :return: the result code and message of the first port that failed,
            or ``OK`` if the PDU accepted every port.
        """
        command = MccsCommandProxy(
            self._pdu_trl, "pduPortOn" if on else "pduPortOff", self._logger
        )
        for port in self._port_states:
            (result_code, message) = command(port, is_lrc=False)
            if result_code != ResultCode.OK:
                return (result_code, message)
        return (ResultCode.OK, f"The PDU accepted every port {'on' if on else 'off'}.")

    def wait_for(
        self: PduLink,
        target: PowerState,
        timeout: float,
        abort_event: threading.Event,
    ) -> tuple[CommandOutcome, str]:
        """
        Wait until every port reports the target power state.

        The ports and the abort event are checked every
        ``PDU_ABORT_CHECK_INTERVAL`` seconds. A timeout is a failure.

        :param target: the power state every port must reach.
        :param timeout: the longest time to wait, in seconds.
        :param abort_event: an event that ends the wait when it is set.

        :return: what became of the wait, and a message that says so.
        """
        deadline = time.monotonic() + timeout
        while not all(state == target for state in self.port_states):
            if abort_event.wait(PDU_ABORT_CHECK_INTERVAL):
                return (
                    CommandOutcome.ABORTED,
                    f"Aborted while the PDU ports switched {target.name}.",
                )
            if time.monotonic() >= deadline:
                return (
                    CommandOutcome.FAILED,
                    f"The PDU ports did not all switch {target.name} within "
                    f"{timeout}s.",
                )
        return (CommandOutcome.COMPLETED, f"The PDU ports are {target.name}.")

    # ---------------
    # Event callbacks
    # ---------------
    def _port_event(self: PduLink, port: int, event: tango.EventData) -> None:
        """
        Take the new state of one port from its change event.

        An invalid value, which ``MccsPdu`` gives for a port it has no value
        for, reads as ``None`` and so makes the port ``UNKNOWN``. So does an
        error event, such as one the scheduler gives while the PDU device is
        down.

        :param port: the port the event is for.
        :param event: the change event.
        """
        state = (
            PowerState.UNKNOWN
            if event.err
            else port_power_state(event.attr_value.value)
        )
        if self._port_states[port] == state:
            return
        self._port_states = {**self._port_states, port: state}
        self._logger.info(f"PDU {self._pdu_trl} port {port} is {state.name}.")
