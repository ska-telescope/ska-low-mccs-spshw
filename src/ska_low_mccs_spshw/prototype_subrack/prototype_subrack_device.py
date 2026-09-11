#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
A Tango device for an SPS subrack, built on the prototype subrack client.

The device holds one :py:class:`~.subrack_client.Subrack` and one
:py:class:`~.subrack_client.SubrackPoller` built around it. There is no
component manager, no driver and no health model between the device and the
board.

The device monitors only. It defines no commands, so the board commands that
:py:meth:`~.subrack_client.Subrack.run_board_command` supports are not reachable
through this interface.
"""
from __future__ import annotations

import sys
from typing import Any, Final, Optional, cast

from ska_control_model import HealthState
from ska_low_mccs_common.component import WebHardwareClient
from ska_tango_base import BaseInterface
from ska_tango_base.base import ControlLevel
from tango import AttrQuality, DevState
from tango.server import device_property

from .constants import RequestError
from .prototype_subrack_attributes import (
    ALL_SIGNALS,
    HEALTH_PATH_TO_SIGNAL,
    READ_KEY_TO_SIGNAL,
    VALUE_CONVERTERS,
    SubrackAttributes,
)
from .subrack_client import Subrack, SubrackPoller, SubrackPollResponse

__all__ = ["MccsPrototypeSubrack", "main"]


_PSU_NAMES: Final[tuple[str, ...]] = ("PSU1", "PSU2")

_PSU_DEAD_VOLTAGE_THRESHOLD: Final[float] = 1.0
"""A PSU below this output voltage, in Volts, is supplying nothing."""


def _walk(health_status: Optional[dict], path: tuple[str, ...]) -> Any:
    """
    Follow a path into the health status dictionary.

    :param health_status: the polled health status, or ``None`` when the board
        did not give one.
    :param path: the keys to follow, outermost first.

    :return: the value at the end of the path, or ``None`` when any level of
        the path is missing.
    """
    value: Any = health_status
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


# pylint: disable=too-many-ancestors
class MccsPrototypeSubrack(SubrackAttributes, BaseInterface):
    """
    A Tango device that monitors an SPS subrack management board.

    The device owns a :py:class:`~.subrack_client.Subrack` and the
    :py:class:`~.subrack_client.SubrackPoller` that drives it. Polling starts
    and stops with ``adminMode``, through
    :py:meth:`change_control_level`. Each poll response is emitted onto the
    signal bus, which pushes the change and archive events for every attribute.

    A value the board could not supply is emitted as ``None``, so the
    corresponding attribute reads back with ``ATTR_INVALID`` quality rather
    than a stale or invented number.
    """

    # ----------
    # Properties
    # ----------
    SubrackIp = device_property(dtype=str)
    SubrackPort = device_property(dtype=int, default_value=8081)
    UpdateRate = device_property(dtype=float, default_value=15.0)
    MaxFanErrors = device_property(dtype=int, default_value=5)
    MaxFanRpmDelta = device_property(dtype=int, default_value=25)
    AttributeFilterType = device_property(dtype=str, default_value="none")
    AttributeFilterMaxSamples = device_property(dtype=int, default_value=5)

    # --------------
    # Initialisation
    # --------------
    _client: WebHardwareClient
    _subrack: Subrack
    _poller: SubrackPoller

    def assemble(self: MccsPrototypeSubrack) -> None:
        """
        Build the hardware client, the poll model and the poller.

        Paired with :py:meth:`disassemble`. ``Init()`` runs
        :py:meth:`delete_device` before :py:meth:`init_device`, so
        :py:meth:`disassemble` reclaims the running poller before this builds
        its replacement.
        """
        self._client = self._web_hardware_client_factory(
            self.SubrackIp, self.SubrackPort
        )
        self._subrack = self._subrack_factory(
            self._client,
            name=self.get_name(),
            logger=self.logger,
            data_callback=self._poll_succeeded,
            error_callback=self._poll_failed,
            max_fan_errors=self.MaxFanErrors,
            max_fan_rpm_delta=self.MaxFanRpmDelta,
            attribute_filter_type=self.AttributeFilterType,
            attribute_filter_max_samples=self.AttributeFilterMaxSamples,
        )
        self._poller = self._subrack_poller_factory(
            self._subrack, self.UpdateRate, self.logger
        )

    def disassemble(self: MccsPrototypeSubrack) -> None:
        """Stop the poller and reclaim its thread."""
        self._poller.stop_polling()
        self._poller.kill_polling_thread()

    def init_device(self: MccsPrototypeSubrack) -> None:
        """Initialise the device, building the client and the poller."""
        super().init_device()

        self.assemble()

        self._version_id = sys.modules["ska_low_mccs_spshw"].__version__
        self._build_state = sys.modules["ska_low_mccs_spshw"].__version_info__

        self.logger.info(
            "Initialised %s for subrack %s:%s at an update rate of %ss.",
            self.__class__.__name__,
            self.SubrackIp,
            self.SubrackPort,
            self.UpdateRate,
        )
        self.init_completed()

    def delete_device(self: MccsPrototypeSubrack) -> None:
        """Delete the device, reclaiming the polling thread."""
        self.disassemble()
        super().delete_device()

    # ----------------
    # Monitoring hook
    # ----------------
    def change_control_level(
        self: MccsPrototypeSubrack, control_level: ControlLevel
    ) -> None:
        """
        Start or stop monitoring the subrack.

        This is the hook ``BaseInterface`` calls when ``adminMode`` is written.
        ``OFFLINE`` arrives as :py:const:`ControlLevel.NO_CONTACT`, and both
        ``ONLINE`` and ``ENGINEERING`` arrive as
        :py:const:`ControlLevel.FULL_CONTROL`.

        :param control_level: how the device should now interact with the
            subrack.

        """
        if control_level == ControlLevel.NO_CONTACT:
            self._poller.stop_polling()
            self._invalidate_all()
            self.report_health(HealthState.FAILED, ["adminMode is OFFLINE."])
            self.component_disconnected()
        else:
            # UNKNOWN until a poll succeeds, because nothing has been read from
            # the board yet.
            self.component_unknown()
            self.report_health(
                HealthState.FAILED,
                ["Establishing communication with the subrack."],
            )
            self._poller.start_polling()

    # ----------------
    # Poll callbacks
    # ----------------
    def _poll_succeeded(
        self: MccsPrototypeSubrack, poll_response: SubrackPollResponse
    ) -> None:
        """
        Emit a successful poll response onto the signal bus.

        Called on the polling thread, which ``Poller`` already wraps in a
        :py:class:`tango.EnsureOmniThread`.

        :param poll_response: the response to the poll.
        """
        timestamp = poll_response.timestamp
        for key, signal_name in READ_KEY_TO_SIGNAL.items():
            self._emit(signal_name, poll_response.values.get(key), timestamp)
        self._emit_health_status(poll_response.health_status, timestamp)

        self.component_on()
        self.component_no_fault()
        self.report_health(HealthState.OK, [])

    def _poll_failed(self: MccsPrototypeSubrack, exception: Exception) -> None:
        """
        Invalidate every attribute after a failed poll.

        A request that never reached the board leaves the subrack in an unknown
        state. So does a board error before any poll has succeeded, because
        nothing has been read to say the subrack is there at all. A board error
        after that is the subrack itself failing.

        :param exception: the exception raised by the poll.
        """
        self._invalidate_all()
        # TODO: Jank to be removed when we upgrade ska-tango-base.
        if isinstance(exception, RequestError) or self.get_state() == DevState.UNKNOWN:
            self.component_unknown()
        else:
            self.component_fault()
        self.logger.warning(f"Poll failed with {type(exception).__name__}. {exception}")
        self.report_health(
            HealthState.FAILED,
            [f"Poll failed with {type(exception).__name__}. {exception}"],
        )

    # ----------------
    # Emission helpers
    # ----------------
    def _emit(
        self: MccsPrototypeSubrack, signal_name: str, value: Any, timestamp: float
    ) -> None:
        """
        Emit one value for one signal.

        Emitting ``None`` is what gives the linked attribute ``ATTR_INVALID``
        quality, which is how a value the board could not supply is reported.

        :param signal_name: the name of the signal to emit for.
        :param value: the value to emit, or ``None`` when it is unknown.
        :param timestamp: the wall clock time the value was read at.
        """
        if value is None:
            setattr(self, signal_name, None)
            return
        converter = VALUE_CONVERTERS.get(signal_name)
        if converter is not None:
            value = converter(value)
        setattr(self, signal_name, (value, timestamp, AttrQuality.ATTR_VALID))

    def _emit_health_status(
        self: MccsPrototypeSubrack,
        health_status: Optional[dict],
        timestamp: float,
    ) -> None:
        """
        Unpack the polled health status and emit each value it holds.

        :param health_status: the polled health status, or ``None`` when this
            poll did not read it.
        :param timestamp: the wall clock time the health status was read at.
        """
        for signal_name, path in HEALTH_PATH_TO_SIGNAL.items():
            self._emit(signal_name, _walk(health_status, path), timestamp)
        self._emit("_psu_dead_count", self._count_dead_psus(health_status), timestamp)

    def _invalidate_all(self: MccsPrototypeSubrack) -> None:
        """Mark every attribute invalid, so no stale value is readable."""
        for signal_name in ALL_SIGNALS:
            setattr(self, signal_name, None)

    @staticmethod
    def _count_dead_psus(health_status: Optional[dict]) -> Optional[int]:
        """
        Count the PSUs that are present and fed but supplying nothing.

        :param health_status: the polled health status, or ``None`` when this
            poll did not read it.

        :return: the number of dead PSUs, or ``None`` when the health status
            does not say enough to tell.
        """
        if health_status is None:
            return None

        dead_count = 0
        for psu in _PSU_NAMES:
            present = _walk(health_status, ("psus", "present", psu))
            voltage_in = _walk(health_status, ("psus", "voltage_in", psu))
            voltage_out = _walk(health_status, ("psus", "voltage_out", psu))
            if voltage_in is None or voltage_out is None:
                continue
            if present and voltage_out < _PSU_DEAD_VOLTAGE_THRESHOLD < voltage_in:
                dead_count += 1
        return dead_count


# ----------
# Run server
# ----------


def subrack_factory(
    web_hardware_client: Any = WebHardwareClient,
    subrack: Any = Subrack,
    subrack_poller: Any = SubrackPoller,
) -> type[MccsPrototypeSubrack]:
    """
    Build the device class, choosing what :py:meth:`~.assemble` builds with.

    :param web_hardware_client: builds the hardware client, from a host and a
        port.
    :param subrack: builds the poll model, from a client and the device's
        settings.
    :param subrack_poller: builds the poller, from a poll model, a poll rate
        and a logger.

    :return: the device class to serve.
    """
    return type(
        "MccsPrototypeSubrack",
        (MccsPrototypeSubrack,),
        {
            "_web_hardware_client_factory": web_hardware_client,
            "_subrack_factory": subrack,
            "_subrack_poller_factory": subrack_poller,
        },
    )


def main(*args: str, **kwargs: str) -> int:  # pragma: no cover
    """
    Entry point for module.

    :param args: positional arguments.
    :param kwargs: named arguments.

    :return: exit code.
    """
    return cast(
        int,
        subrack_factory().run_server(args=args or None, **kwargs),
    )


if __name__ == "__main__":
    main()
