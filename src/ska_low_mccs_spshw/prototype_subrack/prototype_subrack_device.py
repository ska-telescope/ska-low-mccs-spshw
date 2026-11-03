#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
A Tango device for an SPS subrack, built on the prototype subrack client.

The device holds one :py:class:`~.subrack_client.SubrackPoller`, which holds the
:py:class:`~.subrack_client.Subrack` it drives. There is no component manager
and no driver between the device and the board. A
:py:class:`~ska_low_mccs_common.HealthRecorder` turns the quality of the
device's own attributes into its health.

The commands live in :py:class:`~.prototype_subrack_commands.SubrackCommands`,
which the device mixes in. The device supplies the subrack that the board
commands run through, and the poller that reads it. It also supplies the
:py:class:`~.pdu_link.PduLink` that ``On`` and ``Off`` switch the PDU ports
through.
"""
from __future__ import annotations

import enum
import sys
import time
from typing import Any, Final, Optional, cast

from ska_control_model import AdminMode, HealthState, PowerState
from ska_low_mccs_common import HealthRecorder, MccsBaseInterface
from ska_low_mccs_common.component import WebHardwareClient
from ska_tango_base.base import ControlLevel
from ska_tango_base.callback_scheduler import CallbackScheduler
from tango import AttrQuality, DevState
from tango.server import device_property

from utils import walk

from ..subrack.subrack_data import SubrackData
from .constants import HEALTH_NO_VALUE_REASON, HEALTH_STATUS_KEY, ReadKey, RequestError
from .derived_values import DerivedValues
from .pdu_link import PduLink
from .prototype_subrack_attributes import (
    ALL_SIGNALS,
    HEALTH_ATTRIBUTES,
    HEALTH_PATH_TO_SIGNAL,
    READ_KEY_TO_SIGNAL,
    TPM_POWER_STATE_SIGNALS,
    VALUE_CONVERTERS,
    SubrackAttributes,
)
from .prototype_subrack_commands import SubrackCommands
from .subrack_client import Subrack, SubrackPoller, SubrackPollResponse

__all__ = ["MccsPrototypeSubrack", "main"]

# The control level each admin mode asks for. A mode that is absent leaves the
# control level as it is, the same as a write to ``adminMode`` does.
_CONTROL_LEVELS: Final[dict[AdminMode, ControlLevel]] = {
    AdminMode.OFFLINE: ControlLevel.NO_CONTACT,
    AdminMode.ONLINE: ControlLevel.FULL_CONTROL,
    AdminMode.ENGINEERING: ControlLevel.FULL_CONTROL,
}


class _PollOutcome(enum.Enum):
    """What one poll found out about the board."""

    OK = enum.auto()
    """The board answered."""

    UNREACHABLE = enum.auto()
    """The request never reached the board."""

    BOARD_ERROR = enum.auto()
    """The board answered with an error."""


# pylint: disable=too-many-ancestors, too-many-instance-attributes
class MccsPrototypeSubrack(SubrackAttributes, SubrackCommands, MccsBaseInterface):
    """
    A Tango device that monitors and commands an SPS subrack management board.

    The device owns the :py:class:`~.subrack_client.SubrackPoller`, and through
    it the :py:class:`~.subrack_client.Subrack` that answers each poll. The
    device keeps the subrack too, because the board commands run through it
    rather than through the poll loop.Polling starts and stops with ``adminMode``,
    through :py:meth:`change_control_level`. Each poll response is emitted onto the
    signal bus, which pushes the change and archive events for every attribute.

    A value the board could not supply is emitted as ``None``, so the
    corresponding attribute reads back with ``ATTR_INVALID`` quality rather
    than a stale or invented number. The TPM power states are the exception.
    They read back ``UNKNOWN`` instead, the same as on ``MccsSubrack``.

    Health reflects only the hardware. It comes from the
    :py:class:`~ska_low_mccs_common.HealthRecorder`, which subscribes to the
    attributes in ``HEALTH_ATTRIBUTES``. An attribute in warning
    makes the device ``DEGRADED``, and one in alarm makes it ``FAILED``. An
    invalid attribute also makes it ``FAILED``, because ``report_health`` does
    not accept ``UNKNOWN``. Whether the device can poll the subrack shows in
    the state, not the health. A device that cannot poll invalidates every
    attribute, and so its health fails through them.

    When ``PduTrl`` and ``PduPorts`` are both set, the device follows those PDU
    ports through a :py:class:`~.pdu_link.PduLink`. Every port off makes the
    state ``OFF``, whatever the poll found. The device reads the link on each
    poll, so the state still changes only on a poll.
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
    PduTrl = device_property(dtype=str, default_value="")
    PduPorts = device_property(dtype=(int,), default_value=[])

    # --------------
    # Initialisation
    # --------------
    _poller: Optional[SubrackPoller] = None
    _subrack: Optional[Subrack] = None
    _health_recorder: Optional[HealthRecorder] = None
    _pdu_link: Optional[PduLink] = None
    _callback_scheduler: Optional[CallbackScheduler] = None
    _tpm_power_states: list[PowerState]
    _pdu_port_states_cache: Optional[list[PowerState]]
    _evaluated_state: DevState
    _web_hardware_client_factory: type[WebHardwareClient]
    _derived_values_factory: type[DerivedValues]
    _subrack_factory: type[Subrack]
    _subrack_poller_factory: type[SubrackPoller]
    _health_recorder_factory: type[HealthRecorder]
    _pdu_link_factory: type[PduLink]

    def assemble(self: MccsPrototypeSubrack) -> None:
        """
        Build the hardware client, the poll model and the poller.

        Paired with :py:meth:`disassemble`. ``Init()`` runs
        :py:meth:`delete_device` before :py:meth:`init_device`, so
        :py:meth:`disassemble` reclaims the running poller before this builds
        its replacement.

        The poller, the subrack and the PDU link are dropped before anything
        is built, so a failure part way through leaves each as ``None`` rather
        than the reclaimed one. A reclaimed poller would accept
        ``start_polling`` and then never poll, and a reclaimed subrack would
        accept a command and reach a board the device no longer monitors.

        The PDU link is not built here. :py:meth:`change_control_level` builds
        it the first time full control is asked for.
        """
        self._poller = None
        self._subrack = None
        self._pdu_link = None

        client = self._web_hardware_client_factory(self.SubrackIp, self.SubrackPort)
        derived = self._derived_values_factory(
            self.logger,
            max_fan_errors=self.MaxFanErrors,
            max_fan_rpm_delta=self.MaxFanRpmDelta,
            attribute_filter_type=self.AttributeFilterType,
            attribute_filter_max_samples=self.AttributeFilterMaxSamples,
        )
        self._subrack = self._subrack_factory(
            client,
            derived=derived,
            logger=self.logger,
            data_callback=self._poll_succeeded,
            error_callback=self._poll_failed,
            stopped_callback=self._polling_stopped,
        )
        self._poller = self._subrack_poller_factory(
            self._subrack, self.UpdateRate, self.logger
        )

    def disassemble(self: MccsPrototypeSubrack) -> None:
        """Reclaim the poller's thread, if there is one to reclaim."""
        if self._poller is not None:
            self._poller.kill_polling_thread()

    @property
    def subrack(self: MccsPrototypeSubrack) -> Subrack:
        """
        Return the client the board commands run through.

        :raises ValueError: if the device did not finish initialising.

        :return: the subrack client.
        """
        if self._subrack is None:
            raise ValueError(
                "The device did not finish initialising, try running Init()."
            )
        return self._subrack

    @property
    def pdu_link(self: MccsPrototypeSubrack) -> PduLink:
        """
        Return the link to the PDU that feeds the subrack.

        :raises ValueError: if the device has no PDU to follow.

        :return: the PDU link.
        """
        if self._pdu_link is None:
            raise ValueError(
                "The subrack has no PDU link. The link needs PduTrl and PduPorts, "
                "and is built when the device goes online."
            )
        return self._pdu_link

    def init_device(self: MccsPrototypeSubrack) -> None:
        """Initialise the device, building the client and the poller."""
        super().init_device()

        # Emitted once here, so a subscriber gets UNKNOWN rather than an
        # invalid value before the first poll.
        self._tpm_power_states = [PowerState.UNKNOWN] * SubrackData.TPM_BAY_COUNT
        for signal_name in TPM_POWER_STATE_SIGNALS:
            self._emit(signal_name, PowerState.UNKNOWN, time.time())
        self._pdu_port_states_cache = None
        self._evaluated_state = DevState.UNKNOWN

        # Built before assembly, because the PDU link subscribes through it.
        self._callback_scheduler = CallbackScheduler(
            name=f"{self.get_name()}-callbacks", logger=self.logger
        )
        self.assemble()

        self._health_recorder = self._health_recorder_factory(
            self.get_name(),
            self.logger,
            attributes=list(HEALTH_ATTRIBUTES),
            health_callback=self._health_changed,
            attr_conf_callback=self._attribute_config_changed,
        )

        # The parent can pass on its admin mode before the poller exists, and
        # then the poller never starts. So the admin mode is applied again here.
        # A late inherited mode that also starts polling does no harm, because
        # starting the poller is idempotent.
        if _CONTROL_LEVELS.get(self._admin_mode) == ControlLevel.FULL_CONTROL:
            self.change_control_level(ControlLevel.FULL_CONTROL)

        self._version_id = sys.modules["ska_low_mccs_spshw"].__version__
        # The Tango class name can be MccsSubrack, so the build state names
        # the implementation as well.
        self._build_state = (
            f"{sys.modules['ska_low_mccs_spshw'].__version_info__}, "
            f"implementation {MccsPrototypeSubrack.__name__}"
        )

        self.logger.info(
            "Initialised %s as Tango class %s for subrack %s:%s at an update "
            "rate of %ss.",
            MccsPrototypeSubrack.__name__,
            self.__class__.__name__,
            self.SubrackIp,
            self.SubrackPort,
            self.UpdateRate,
        )
        self.init_completed()

    def delete_device(self: MccsPrototypeSubrack) -> None:
        """Delete the device, reclaiming the polling, health and callback threads."""
        self.disassemble()
        if self._health_recorder is not None:
            self._health_recorder.cleanup()
            self._health_recorder = None
        # Shutting the scheduler down also ends the PDU link's subscriptions.
        if self._callback_scheduler is not None:
            self._callback_scheduler.shutdown()
            self._callback_scheduler = None
        super().delete_device()

    # ----------------
    # Monitoring hook
    # ----------------
    def change_control_level(
        self: MccsPrototypeSubrack, control_level: ControlLevel
    ) -> None:
        """
        Start or stop monitoring the subrack.

        Stopping also aborts the running board command and every queued one,
        so the device makes no further contact with the board.

        This is the hook ``BaseInterface`` calls when ``adminMode`` is written.
        ``OFFLINE`` arrives as :py:const:`ControlLevel.NO_CONTACT`, and both
        ``ONLINE`` and ``ENGINEERING`` arrive as
        :py:const:`ControlLevel.FULL_CONTROL`.

        :param control_level: how the device should now interact with the
            subrack.

        """
        if self._poller is None:
            self.logger.error(
                "Cannot change control level, because the device did not "
                "finish initialising. Fix the cause and run Init()."
            )
            return

        if control_level == ControlLevel.NO_CONTACT:
            self.abort_board_commands()
            # Stopping does not block, so a poll already in flight still
            # reports back. The device goes offline in :py:meth:`_polling_stopped`,
            # which the poller calls after that last report.
            self._poller.stop_polling()
            self.logger.info("Stopping polling the subrack.")
        else:
            # UNKNOWN until a poll succeeds, because nothing has been read from
            # the board yet.
            self.component_unknown()
            self._evaluated_state = DevState.UNKNOWN
            self._connect_pdu()
            self._poller.start_polling()
            self.logger.info("Starting polling the subrack.")

    def _connect_pdu(self: MccsPrototypeSubrack) -> None:
        """
        Build the PDU link, the first time full control is asked for.

        The link is built only when ``PduTrl`` and ``PduPorts`` are both set.
        Without it the device follows no PDU, and refuses ``On`` and ``Off``.
        The link reaches the PDU device as it is built, so it is not built in
        :py:meth:`assemble`, where the PDU device may not be running yet.
        Once built, it lasts until the scheduler is shut down.
        """
        if self._pdu_link is not None or not (self.PduTrl and self.PduPorts):
            return
        assert self._callback_scheduler is not None  # for the type checker
        self._pdu_link = self._pdu_link_factory(
            self.PduTrl,
            list(self.PduPorts),
            self._callback_scheduler,
            self.logger,
        )

    def wake_poller(self: MccsPrototypeSubrack) -> None:
        """
        Make the next poll run now, rather than at the update rate.

        A stopped poller stays stopped, so this is safe at any admin mode.
        """
        if self._poller is not None:
            self._poller.wake()

    def _admin_mode_changed(self: MccsPrototypeSubrack, admin_mode: AdminMode) -> None:
        """
        Take on the admin mode of the parent device.

        ``MccsBaseInterface`` only updates the admin mode model, so the
        control level is changed here, in the same way that a write to
        ``adminMode`` changes it.

        :param admin_mode: the admin mode of the parent device.
        """
        previous_admin_mode = self._admin_mode
        super()._admin_mode_changed(admin_mode)
        control_level = _CONTROL_LEVELS.get(admin_mode)
        if admin_mode != previous_admin_mode and control_level is not None:
            self.change_control_level(control_level)

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
        values = poll_response.values
        # A key the board was too busy to read is absent, so its attribute keeps
        # its last value.
        for key, signal_name in READ_KEY_TO_SIGNAL.items():
            if key in values:
                self._emit(signal_name, values[key], timestamp)
        if HEALTH_STATUS_KEY in values:
            self._emit_health_status(values[HEALTH_STATUS_KEY], timestamp)

        # Read once, so the TPM power states and the state agree.
        pdu_power = self._pdu_power()
        if pdu_power == PowerState.OFF:
            self._update_tpm_power_states(
                [PowerState.NO_SUPPLY] * SubrackData.TPM_BAY_COUNT, timestamp
            )
        elif ReadKey.TPM_ON_OFF.value in values:
            tpm_on_off = values[ReadKey.TPM_ON_OFF.value]
            self._update_tpm_power_states(
                [PowerState.UNKNOWN] * SubrackData.TPM_BAY_COUNT
                if tpm_on_off is None
                else [
                    PowerState.ON if is_on else PowerState.OFF for is_on in tpm_on_off
                ],
                timestamp,
            )
        self._emit_pdu_port_states(timestamp)
        self._apply_state(_PollOutcome.OK, pdu_power)
        self.logger.debug("Poll succeeded")

    def _poll_failed(self: MccsPrototypeSubrack, exception: Exception) -> None:
        """
        Invalidate every attribute after a failed poll.

        A request that never reached the board leaves the subrack in an unknown
        state. A board that answered with an error is the subrack itself
        failing. :py:meth:`_apply_state` decides what each gives.

        :param exception: the exception raised by the poll.
        """
        self._invalidate_all()
        timestamp = time.time()
        pdu_power = self._pdu_power()
        self._update_tpm_power_states(
            [
                PowerState.NO_SUPPLY
                if pdu_power == PowerState.OFF
                else PowerState.UNKNOWN
            ]
            * SubrackData.TPM_BAY_COUNT,
            timestamp,
        )
        self._emit_pdu_port_states(timestamp)
        self._apply_state(
            _PollOutcome.UNREACHABLE
            if isinstance(exception, RequestError)
            else _PollOutcome.BOARD_ERROR,
            pdu_power,
        )
        self.logger.warning(f"Poll failed with {type(exception).__name__}. {exception}")

    def _polling_stopped(self: MccsPrototypeSubrack) -> None:
        """
        Take the device offline once polling has really stopped.

        Called on the polling thread after the last poll has reported back, so
        this always runs after :py:meth:`_poll_succeeded` and
        :py:meth:`_poll_failed` rather than racing them. That ordering is what
        stops a late poll from leaving the device ON after it went offline.
        """
        self._invalidate_all()
        self._update_tpm_power_states(
            [PowerState.UNKNOWN] * SubrackData.TPM_BAY_COUNT, time.time()
        )
        self._pdu_port_states_cache = None
        self._emit("_pdu_port_states", None, time.time())
        self.component_disconnected()
        self.logger.info("Stopped polling the subrack.")

    # ----------------
    # State
    # ----------------
    def _pdu_power(self: MccsPrototypeSubrack) -> Optional[PowerState]:
        """
        Return the power state the PDU ports give the subrack.

        :return: the combined power state of the PDU ports, or ``None`` when
            the device follows no PDU.
        """
        return None if self._pdu_link is None else self._pdu_link.power_state

    def _apply_state(
        self: MccsPrototypeSubrack,
        outcome: _PollOutcome,
        pdu_power: Optional[PowerState],
    ) -> None:
        """
        Set the state from what a poll found and from the PDU power.

        Called only from the poll callbacks, so the state changes only on the
        poll thread and needs no lock.

        Every PDU port off makes the subrack ``OFF``, whatever the poll found.
        Otherwise the poll decides. A board that answers is ``ON``. A board
        error is ``FAULT``, but only if the state was already ``ON`` or
        ``FAULT``. From ``UNKNOWN`` or ``OFF`` nothing has been read to say the
        subrack is there at all, and the operational state model has no
        transition into ``FAULT`` from either of them. So in that case it gives
        ``UNKNOWN``, the same as a request that never reached the board.

        :param outcome: what the poll found out about the board.
        :param pdu_power: the combined power state of the PDU ports, or
            ``None`` when the device follows no PDU.
        """
        if pdu_power == PowerState.OFF:
            self.component_off()
            self._evaluated_state = DevState.OFF
        elif outcome == _PollOutcome.OK:
            self.component_on()
            self.component_no_fault()
            self._evaluated_state = DevState.ON
        elif outcome == _PollOutcome.BOARD_ERROR and self._evaluated_state in (
            DevState.ON,
            DevState.FAULT,
        ):
            self.component_fault()
            self._evaluated_state = DevState.FAULT
        else:
            self.component_unknown()
            self._evaluated_state = DevState.UNKNOWN

    # ----------------
    # Health
    # ----------------
    def _health_changed(
        self: MccsPrototypeSubrack, health: HealthState, health_report: str
    ) -> None:
        """
        Report the health that the attribute qualities give.

        Called on the health recorder's event thread.

        :param health: the health the attribute qualities give.
        :param health_report: the recorder's reasons, one on each line.
        """
        match health:
            case HealthState.OK:
                health_info = []
            case HealthState.UNKNOWN:
                # report_health refuses UNKNOWN. The recorder gives it for an
                # invalid attribute, and before it has received any event.
                health = HealthState.FAILED
                health_info = [HEALTH_NO_VALUE_REASON]
            case _:
                health_info = health_report.splitlines()

        # Emitted first, so the report is already readable when a client hears
        # of the new health.
        self._emit(
            "_health_report", "\n".join(health_info) or "Health is OK.", time.time()
        )
        self.report_health(health, health_info)

    def _attribute_config_changed(
        self: MccsPrototypeSubrack, attribute_name: str
    ) -> None:
        """
        Ignore a change to a health attribute's configuration.

        Tango evaluates alarm thresholds only when a value is pushed, so a new
        threshold takes effect at the next poll, which pushes every value it
        reads. That is soon enough, so nothing is pushed here.

        :param attribute_name: the attribute whose configuration changed.
        """

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
            self._emit(signal_name, walk(health_status, path), timestamp)

    def _update_tpm_power_states(
        self: MccsPrototypeSubrack,
        power_states: list[PowerState],
        timestamp: float,
    ) -> None:
        """
        Emit the TPM power state of each bay whose power state changed.

        Only a change is emitted, so a tile gets one event for each transition
        rather than one for each poll. Every caller runs on the polling thread,
        so no lock is needed for the stored power states.

        :param power_states: the power state of each bay, in bay order.
        :param timestamp: the wall clock time the power states were read at.
        """
        for bay, power_state in enumerate(power_states):
            if self._tpm_power_states[bay] != power_state:
                self._tpm_power_states[bay] = power_state
                self._emit(TPM_POWER_STATE_SIGNALS[bay], power_state, timestamp)

    def _emit_pdu_port_states(self: MccsPrototypeSubrack, timestamp: float) -> None:
        """
        Emit the PDU port states, if they changed since they were last emitted.

        Only a change is emitted, the same as for the TPM power states. Every
        caller runs on the polling thread, so no lock is needed for the cache.

        :param timestamp: the wall clock time to emit the states with.
        """
        if self._pdu_link is None:
            return
        port_states = self._pdu_link.port_states
        if port_states != self._pdu_port_states_cache:
            self._pdu_port_states_cache = port_states
            self._emit(
                "_pdu_port_states", [int(state) for state in port_states], timestamp
            )

    def _invalidate_all(self: MccsPrototypeSubrack) -> None:
        """Mark every attribute invalid, so no stale value is readable."""
        for signal_name in ALL_SIGNALS:
            setattr(self, signal_name, None)


# ----------
# Run server
# ----------


def subrack_factory(  # pylint: disable=too-many-arguments
    web_hardware_client: type[WebHardwareClient] = WebHardwareClient,
    derived_values: type[DerivedValues] = DerivedValues,
    subrack: type[Subrack] = Subrack,
    subrack_poller: type[SubrackPoller] = SubrackPoller,
    health_recorder: type[HealthRecorder] = HealthRecorder,
    pdu_link: type[PduLink] = PduLink,
    class_name: str = "MccsPrototypeSubrack",
) -> type[MccsPrototypeSubrack]:
    """
    Build the device class, choosing what the device builds its parts with.

    :param web_hardware_client: builds the hardware client, from a host and a
        port.
    :param derived_values: builds the computed values, from a logger and the
        device's fan and filter settings.
    :param subrack: builds the poll model, from a client, the computed values
        and the device's callbacks.
    :param subrack_poller: builds the poller, from a poll model, a poll rate
        and a logger.
    :param health_recorder: builds the health recorder, from the device name,
        a logger, the health attributes and the device's health callbacks.
    :param pdu_link: builds the PDU link, from the PDU TRL, the PDU ports, the
        device's callback scheduler and a logger.
    :param class_name: the Tango class name to serve the device under. Pass
        ``MccsSubrack`` to stand the device in for the old subrack, so that the
        Tango DB rows for the device do not change.

    :return: the device class to serve.
    """
    return type(
        class_name,
        (MccsPrototypeSubrack,),
        {
            "_web_hardware_client_factory": web_hardware_client,
            "_derived_values_factory": derived_values,
            "_subrack_factory": subrack,
            "_subrack_poller_factory": subrack_poller,
            "_health_recorder_factory": health_recorder,
            "_pdu_link_factory": pdu_link,
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
