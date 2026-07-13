# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
This module provides a prototype Tango device for an SPS subrack.

The device relies on PyTango's built-in attribute polling, driven by
:py:meth:`read_attr_hardware`, to refresh a cache of hardware values that are
read directly from the subrack management board over HTTP using a
:py:class:`~ska_low_mccs_common.component.WebHardwareClient`.
"""

# pylint: disable=too-many-lines
from __future__ import annotations

import functools
import json
import sys
import threading
import time
from typing import Any, Callable, Optional, cast

import ska_tango_base as stb
import tango
from ska_control_model import AdminMode, HealthState, PowerState, ResultCode, TaskStatus
from ska_low_mccs_common import HealthRecorder, MccsBaseInterface
from ska_low_mccs_common.component import (
    HardwareClientResponseStatusCodes,
    WebHardwareClient,
)
from ska_tango_base.base.base_interface import ControlLevel
from ska_tango_base.long_running_commands import LRCMixin
from ska_tango_base.software_bus import AttrSignal, attribute_from_signal
from tango import AttrQuality, DevFailed, DevState
from tango.server import attribute, device_property

from ..subrack.subrack_data import FanMode, SubrackData
from .constants import (
    ATTRIBUTE_MAP,
    BATCH_ATTRIBUTES,
    COMMAND_POLL_INTERVAL,
    COMMAND_TIMEOUT,
    HEALTH_BACKED_ATTRIBUTES,
    HEALTH_SIGNAL_MAP,
    HEALTH_STATUS_MAP,
    HW_BACKED_ATTRIBUTES,
    HW_KEY_FOR_ATTRIBUTE,
    POLLED_ATTRIBUTES,
    HttpError,
    RequestError,
    SetPowerSupplyFanSpeed_SCHEMA,
    SetSubrackFanMode_SCHEMA,
    SetSubrackFanSpeed_SCHEMA,
)

__all__ = ["MccsSubrackPrototype", "main"]


# pylint: disable=too-many-instance-attributes, too-many-ancestors
# pylint: disable=too-many-public-methods
class MccsSubrackPrototype(MccsBaseInterface, LRCMixin):
    """
    A prototype Tango device for monitor and control of an SPS subrack.

    It uses PyTango's built-in attribute polling (driven by
    :py:meth:`read_attr_hardware`) to refresh a cache of hardware values read
    directly over HTTP, and the
    :py:class:`~ska_tango_base.long_running_commands.LRCMixin` task executor to
    run its long running commands.
    """

    # ----------
    # Properties
    # ----------
    SubrackIp = device_property(dtype=str)
    SubrackPort = device_property(dtype=int, default_value=8081)
    UpdateRate = device_property(dtype=float, default_value=15.0)
    CommandUpdateRate = device_property(dtype=float, default_value=15.0)
    PowerMarshallerTrl = device_property(dtype=str, default_value="")
    PduTrl = device_property(dtype=str, default_value="")
    PduPorts = device_property(dtype=(int,), default_value=[])
    SimulatedPDU = device_property(dtype=bool, default_value=True)
    UseAttributesForHealth = device_property(
        doc="Use the attribute quality factor in health. ADR-115.",
        dtype=bool,
        default_value=True,
    )

    # Class-level aliases of the constants defined in ``constants``, so they can
    # be accessed as ``self._ATTRIBUTE_MAP`` / ``self._HEALTH_SIGNAL_MAP`` / etc.
    _ATTRIBUTE_MAP = ATTRIBUTE_MAP
    _HEALTH_SIGNAL_MAP = HEALTH_SIGNAL_MAP
    _HEALTH_STATUS_MAP = HEALTH_STATUS_MAP
    _POLLED_ATTRIBUTES = POLLED_ATTRIBUTES
    _HW_KEY_FOR_ATTRIBUTE = HW_KEY_FOR_ATTRIBUTE
    _HEALTH_BACKED_ATTRIBUTES = HEALTH_BACKED_ATTRIBUTES
    _COMMAND_POLL_INTERVAL = COMMAND_POLL_INTERVAL
    _COMMAND_TIMEOUT = COMMAND_TIMEOUT

    # --------------
    # Initialization
    # --------------

    def __init__(self: MccsSubrackPrototype, *args: Any, **kwargs: Any) -> None:
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

        self._stopping = False
        self._health_recorder: HealthRecorder | None = None
        self._health_report = ""
        self._health_state: HealthState = HealthState.UNKNOWN

        self._tpm_present: list[bool] = []
        self._tpm_count = 0
        self._tpm_power_states = [PowerState.UNKNOWN] * SubrackData.TPM_BAY_COUNT

        self._hardware_attributes: dict[str, Any] = {}
        self._health_status: dict[str, Any] = {}

        # The client used to talk to the subrack management board over HTTP.
        self._client: WebHardwareClient

        # Locks and refresh bookkeeping.
        self._refresh_lock = threading.Lock()
        self._last_fetch = 0.0
        self._last_health_fetch = 0.0
        self._poll_period_ms: int
        self._refresh_gate_s: float
        self._attribute_poll_periods: dict[str, int] = {}

        # BIOS gate for health-status polling.
        self._checked_bios = False
        self._poll_commands = False

        # Lazily-created proxies to the PDU and power-marshaller devices.
        self._pdu_proxy: Optional[tango.DeviceProxy] = None
        self._marshaller_proxy: Optional[tango.DeviceProxy] = None

        # Event-driven cache of this subrack's own PDU outlet power states.
        self._pdu_port_states: dict[int, bool | None] = {}
        self._pdu_event_ids: list[int] = []
        self._pdu_state_lock = threading.Lock()

    def init_device(self: MccsSubrackPrototype) -> None:
        """
        Initialise the device.

        Creates the hardware client, configures change/archive events for every
        polled attribute, and sets up the :py:class:`HealthRecorder`.
        """
        super().init_device()

        self._stopping = False
        self._hardware_attributes = {}
        self._health_status = {}
        self._last_fetch = 0.0
        self._last_health_fetch = 0.0
        self._checked_bios = False
        self._poll_commands = False
        self._tpm_present = []
        self._tpm_count = 0
        self._tpm_power_states = [PowerState.UNKNOWN] * SubrackData.TPM_BAY_COUNT
        self._pdu_port_states = {port: None for port in self.PduPorts}
        self._pdu_event_ids = []

        self._poll_period_ms = int(self.UpdateRate * 1000)
        self._refresh_gate_s = self.UpdateRate / 2.0
        self._client = WebHardwareClient(self.SubrackIp, self.SubrackPort)

        for attribute_name in self._POLLED_ATTRIBUTES:
            self.set_change_event(attribute_name, True, True)
            self.set_archive_event(attribute_name, True, True)
        for attribute_name in self._ATTRIBUTE_MAP.values():
            if attribute_name not in self._POLLED_ATTRIBUTES:
                self.set_change_event(attribute_name, True, True)
                self.set_archive_event(attribute_name, True, True)

        self._build_state = sys.modules["ska_low_mccs_spshw"].__version_info__
        self._version_id = sys.modules["ska_low_mccs_spshw"].__version__
        device_name = f'{str(self.__class__).rsplit(".", maxsplit=1)[-1][0:-2]}'
        version = f"{device_name} Software Version: {self._version_id}"
        properties = (
            f"Initialised {device_name} device with properties:\n"
            f"\tSubrackIP: {self.SubrackIp}\n"
            f"\tSubrackPort: {self.SubrackPort}\n"
            f"\tUpdateRate: {self.UpdateRate}\n"
            f"\tCommandUpdateRate: {self.CommandUpdateRate}\n"
            f"\tPowerMarshallerTrl: {self.PowerMarshallerTrl}\n"
            f"\tPduTrl: {self.PduTrl}\n"
            f"\tPduPorts: {self.PduPorts}\n"
            f"\tSimulatedPDU: {self.SimulatedPDU}\n"
            f"\tUseAttributesForHealth: {self.UseAttributesForHealth}\n"
        )
        self.logger.info(
            "\n%s\n%s\n%s", str(self.GetVersionInfo()), version, properties
        )
        self.init_completed()

    def _init_state_model(self: MccsSubrackPrototype) -> None:
        """
        Initialise the state model for the device.

        This sets up the :py:class:`HealthRecorder` used to derive the device
        health from the quality factors of the healthful attributes (ADR-115).
        """
        super()._init_state_model()
        self._health_state = HealthState.UNKNOWN

        healthful_attrs = set(self._HEALTH_STATUS_MAP.keys()) | set(
            self._ATTRIBUTE_MAP.values()
        )
        healthful_attrs = healthful_attrs - {
            "boardCurrent",
            "cpldPllLocked",
            "powerSupplyCurrents",
            "powerSupplyFanSpeeds",
            "subrackFanSpeeds",
            "subrackFanSpeedsPercent",
            "subrackFanModes",
            "subrackPllLocked",
            "subrackTimestamp",
            "tpmCurrents",
            "pduHealth",
            "pduModel",
            "pduPortStates",
            "pduPortCurrents",
            "pduPortVoltages",
            "subrackBoardInfo",
        }

        self._health_recorder = HealthRecorder(
            self.get_name(),
            logger=self.logger,
            attributes=list(healthful_attrs),
            health_callback=self._health_changed_new,
            attr_conf_callback=self._attr_conf_changed,
        )

    def delete_device(self: MccsSubrackPrototype) -> None:
        """Delete the device."""
        self._stopping = True
        self._stop_polling()
        self._unsubscribe_pdu()
        if self._health_recorder is not None:
            self._health_recorder.cleanup()
            self._health_recorder = None
        self._pdu_proxy = None
        self._marshaller_proxy = None
        super().delete_device()

    # --------------------
    # Admin / control level
    # --------------------
    def change_control_level(
        self: MccsSubrackPrototype, control_level: ControlLevel
    ) -> None:
        """
        Change how the device is interacting with the subrack.

        This is the admin-mode hook.

        On :py:const:`ControlLevel.FULL_CONTROL` the device (re-)registers Tango
        polling on every hardware attribute, transitions to ``UNKNOWN``, and
        performs one immediate refresh; if that refresh is successful it will
        move to ``ON``. On :py:const:`ControlLevel.NO_CONTACT` the device stops
        polling, clears the hardware cache (setting attribute qualities to
        ``ATTR_INVALID``) and transitions to ``DISABLE``.

        :param control_level: the requested control level.
        """
        if control_level == ControlLevel.FULL_CONTROL:
            self.logger.info("Gaining full control of subrack: starting polling.")
            self._subscribe_pdu()
            self._start_polling()
            self._set_op_state(DevState.UNKNOWN)
            self._do_refresh(force=True)
            return
        self.logger.info("Dropping contact with subrack: stopping polling.")
        self._stop_polling()
        self._unsubscribe_pdu()
        self._clear_hardware_attributes()
        if self._health_recorder is not None:
            self._health_recorder.clear_attribute_state()
        self._set_op_state(DevState.DISABLE)

    def _start_polling(self: MccsSubrackPrototype) -> None:
        """
        Enable Tango attribute polling on every polled hardware attribute.

        Each attribute is restored to whatever period ``_stop_polling`` last
        captured for it (e.g. a user customisation made via the Admin
        device/Jive), rather than always resetting it to ``UpdateRate``; an
        attribute never previously polled falls back to ``UpdateRate``.
        """
        for name in self._POLLED_ATTRIBUTES:
            try:
                if not self.is_attribute_polled(name):
                    period = self._attribute_poll_periods.get(
                        name, self._poll_period_ms
                    )
                    self.poll_attribute(name, period)
            except DevFailed:
                self.logger.warning(
                    "Failed to start polling attribute '%s'.", name, exc_info=True
                )

    def _stop_polling(self: MccsSubrackPrototype) -> None:
        """
        Disable Tango attribute polling on every polled hardware attribute.

        Each attribute's current period is captured into
        ``_attribute_poll_periods`` first, so :py:meth:`_start_polling` can
        restore it later instead of silently overwriting a user's custom
        per-attribute polling period with the default.
        """
        for name in self._POLLED_ATTRIBUTES:
            try:
                if self.is_attribute_polled(name):
                    self._attribute_poll_periods[name] = self.get_attribute_poll_period(
                        name
                    )
                    self.stop_poll_attribute(name)
            except DevFailed:
                self.logger.warning(
                    "Failed to stop polling attribute '%s'.", name, exc_info=True
                )

    # -----------------------------
    # Hardware polling / refreshing
    # -----------------------------
    @property
    def _is_online(self: MccsSubrackPrototype) -> bool:
        """
        Return whether the device is under control (admin mode online).

        :return: whether the device is under control.
        """
        return self.admin_mode_model.admin_mode in (
            AdminMode.ONLINE,
            AdminMode.ENGINEERING,
        )

    def read_attr_hardware(self: MccsSubrackPrototype, attr_list: list[int]) -> None:
        """
        Refresh the hardware cache before a batch of attribute reads.

        Tango invokes this before reading attributes (both on client reads and
        once per polled attribute per poll cycle). The refresh is only triggered
        when at least one of the attributes being read is actually sourced from a
        hardware read (the ``HW_BACKED_ATTRIBUTES`` set); reading a derived
        attribute such as ``healthState`` or ``state``, or a live-proxied ``pdu*``
        attribute, does not hit the subrack. Of the hardware-backed attributes
        being read, only those actually requested are fetched: the SMB command
        (health-status) poll runs only if a health-backed attribute
        (``internalVoltages*``/``healthStatus``) is among them, and the batched
        attribute read (see :py:meth:`_fetch_attributes`) is narrowed to just the
        hardware keys those attributes need (via ``HW_KEY_FOR_ATTRIBUTE``). A
        coalescing time-gate (``_refresh_gate_s``, half the poll period) then
        ensures the burst of per-attribute calls within one poll cycle results in
        a single refresh, while each poll cycle reliably triggers one.

        :param attr_list: the indices of the attributes about to be read.
        """
        multi_attr = self.get_device_attr()
        names = set()
        for index in attr_list:
            try:
                names.add(multi_attr.get_attr_by_ind(index).get_name())
            except DevFailed:
                continue
        hw_names = names & HW_BACKED_ATTRIBUTES
        if hw_names:
            self._do_refresh(attribute_names=frozenset(hw_names))

    def _do_refresh(
        self: MccsSubrackPrototype,
        force: bool = False,
        attribute_names: Optional[frozenset[str]] = None,
    ) -> None:
        """
        Perform a time-gated refresh of the hardware cache.

        :param force: if ``True``, bypass the time-gate and refresh immediately.
        :param attribute_names: the Tango attribute names that triggered this
            refresh, used to narrow the hardware fetch to just what they need.
            If ``None`` (the default, used by forced refreshes that aren't
            tied to a specific read, e.g. going online or after a board
            command), every hardware attribute and the health status are
            fetched.
        """
        # Never contact the hardware (or change state) when not under control:
        # a read while offline must just return the cleared cache (ATTR_INVALID).
        if not self._is_online:
            return
        # If the PDU authoritatively reports our outlets as OFF, the SMB is
        # unpowered: drive OFF and skip the SMB fetch entirely, avoiding the
        # ~10s HTTP connect-timeout against a dead board.
        if self._pdu_power_state() == "off":
            self._set_op_state(DevState.OFF)
            self._clear_hardware_attributes()
            return
        now = time.monotonic()
        if not force and (now - self._last_fetch) < self._refresh_gate_s:
            return
        # Only one refresh at a time; if another thread (or an in-progress board
        # command) holds the lock, skip this cycle and try again next time.
        # pylint: disable-next=consider-using-with
        if not self._refresh_lock.acquire(blocking=False):
            return
        try:
            self._last_fetch = time.monotonic()
            values = self._fetch_attributes(self._hw_keys_to_fetch(attribute_names))
            self._ingest_poll_values(**values)
            if force:
                self._push_hardware_events()
            else:
                self.logger.debug(
                    "Standard poll cycle updated attributes: %s",
                    sorted(attribute_names) if attribute_names else [],
                )
            needs_health = (
                attribute_names is None
                or attribute_names & self._HEALTH_BACKED_ATTRIBUTES
            )
            if needs_health:
                self._maybe_fetch_health()
            self._set_communicating()
        except RequestError as request_error:
            self._handle_request_error(request_error)
        except HttpError as http_error:
            self._handle_http_error(http_error)
        except Exception:  # pylint: disable=broad-except
            self.logger.exception("Unexpected error refreshing subrack hardware.")
        finally:
            self._refresh_lock.release()

    def _hw_keys_to_fetch(
        self: MccsSubrackPrototype, attribute_names: Optional[frozenset[str]]
    ) -> tuple[str, ...]:
        """
        Resolve the hardware read keys needed to satisfy ``attribute_names``.

        :param attribute_names: the Tango attribute names that triggered the
            refresh, or ``None`` for every batched hardware attribute.

        :return: the subset of ``BATCH_ATTRIBUTES`` to fetch, in
            ``BATCH_ATTRIBUTES`` order.
        """
        if attribute_names is None:
            return BATCH_ATTRIBUTES
        keys = {
            self._HW_KEY_FOR_ATTRIBUTE[name]
            for name in attribute_names
            if name in self._HW_KEY_FOR_ATTRIBUTE
        }
        return tuple(attr for attr in BATCH_ATTRIBUTES if attr in keys)

    @staticmethod
    def _raise_for_transport_error(response: Any) -> None:
        """
        Raise the matching exception for a transport-level failure response.

        :param response: a hardware-client response whose ``status`` is one of the
            transport-error codes.

        :raises RequestError: if the client reported a request exception.
        :raises HttpError: if the client reported an HTTP error.
        """
        if response["status"] == HardwareClientResponseStatusCodes.HTTP_ERROR.name:
            raise HttpError(f"{response['info']}")
        raise RequestError(f"{response['info']}")

    def _fetch_attributes(
        self: MccsSubrackPrototype, keys: tuple[str, ...]
    ) -> dict[str, Any]:
        """
        Issue the given hardware attribute reads to the subrack over HTTP.

        Transport-level failures propagate as :py:class:`RequestError` or
        :py:class:`HttpError` (raised by :py:meth:`_raise_for_transport_error`).

        :param keys: the hardware read keys (a subset of ``BATCH_ATTRIBUTES``)
            to fetch.

        :raises ValueError: if the client returns an unknown status code.

        :return: a mapping of hardware read key to value (``None`` on error).
        """
        values: dict[str, Any] = {}
        for attr in keys:
            response = self._client.get_attribute(attr)
            status = response["status"]
            if status == HardwareClientResponseStatusCodes.OK.name:
                values[attr] = response["value"]
            elif status in (
                HardwareClientResponseStatusCodes.ERROR.name,
                HardwareClientResponseStatusCodes.JSON_DECODE_ERROR.name,
            ):
                self.logger.warning(
                    "get_attribute '%s' returned status '%s': %s",
                    attr,
                    status,
                    response.get("info", "no details"),
                )
                values[attr] = None
            elif status in (
                HardwareClientResponseStatusCodes.REQUEST_EXCEPTION.name,
                HardwareClientResponseStatusCodes.HTTP_ERROR.name,
            ):
                # Poll failed at the transport level; the poll-failure handler in
                # ``_do_refresh`` clears the hardware cache and resolves op-state.
                self._raise_for_transport_error(response)
            elif status in (
                HardwareClientResponseStatusCodes.BUSY.name,
                HardwareClientResponseStatusCodes.STARTED.name,
            ):
                # Board busy: skip this attribute this cycle.
                pass
            else:
                raise ValueError(
                    f"UNKNOWN status code {status} returned from get_attribute "
                    "(check client)."
                )
        return values

    def _maybe_fetch_health(self: MccsSubrackPrototype) -> None:
        """
        Fetch the subrack health status, if it is time and the BIOS supports it.

        Transport-level failures propagate as :py:class:`RequestError` or
        :py:class:`HttpError` (raised by :py:meth:`_raise_for_transport_error`).
        """
        now = time.monotonic()
        if (now - self._last_health_fetch) < self.CommandUpdateRate:
            return
        self._check_bios_version()
        if not self._poll_commands:
            self._last_health_fetch = now
            return
        response = self._client.execute_command("get_health_status", "")
        status = response["status"]
        if status == HardwareClientResponseStatusCodes.OK.name:
            # ``CommandResponseType.retvalue`` is typed as ``str`` generically,
            # but ``get_health_status`` specifically returns a nested dict.
            self._store_health_status(cast(Optional[dict], response["retvalue"]))
            self._last_health_fetch = now
        elif status in (
            HardwareClientResponseStatusCodes.STARTED.name,
            HardwareClientResponseStatusCodes.BUSY.name,
        ):
            # Board busy; retry on the next cycle without advancing the timer.
            pass
        elif status in (
            HardwareClientResponseStatusCodes.REQUEST_EXCEPTION.name,
            HardwareClientResponseStatusCodes.HTTP_ERROR.name,
        ):
            self._raise_for_transport_error(response)
        else:
            self.logger.error(
                "get_health_status returned status '%s': %s",
                status,
                response.get("info", "no details"),
            )
            self._last_health_fetch = now

    def _check_bios_version(self: MccsSubrackPrototype) -> None:
        """Check that the SMB BIOS is new enough to poll health_status."""
        if self._checked_bios:
            return
        board_info = self._hardware_attributes.get("subrackBoardInfo")
        if board_info:
            try:
                bios_version = board_info["SMM"]["bios"]
                if [int(x) for x in bios_version.lstrip("v").split(".")] >= [1, 6, 0]:
                    self._poll_commands = True
            except (KeyError, TypeError, ValueError, AttributeError):
                self.logger.warning(
                    "Could not determine BIOS version from board info; "
                    "health-status polling disabled.",
                )
            self._checked_bios = True

    # Map an operational DevState to the component callback that drives it.
    _OP_STATE_TRANSITIONS = {
        DevState.DISABLE: "component_disconnected",
        DevState.OFF: "component_off",
        DevState.ON: "component_on",
        DevState.FAULT: "component_fault",
        DevState.UNKNOWN: "component_unknown",
    }

    def _set_op_state(self: MccsSubrackPrototype, target: DevState) -> None:
        """
        Drive the operational state to ``target`` if not already there.

        :param target: the desired operational :py:class:`~tango.DevState`.
        """
        if self.get_state() != target:
            getattr(self, self._OP_STATE_TRANSITIONS[target])()

    def _set_communicating(self: MccsSubrackPrototype) -> None:
        """Drive the operational state to ON on a successful hardware fetch."""
        self._set_op_state(DevState.ON)

    def _handle_request_error(self: MccsSubrackPrototype, exception: Exception) -> None:
        """
        Handle a request-exception style poll failure.

        This clears the hardware cache and classifies the failure using the PDU
        power state: a known-off PDU means the board is simply powered down
        (``OFF``); a known-on PDU means the board is powered but unresponsive
        (``FAULT``); an unknown PDU power state falls back to ``UNKNOWN``.

        :param exception: the exception that was raised.
        """
        self.logger.warning("Subrack poll failed (request error): %s", exception)
        self._clear_hardware_attributes()
        power = self._pdu_power_state()
        if power == "off":
            self._set_op_state(DevState.OFF)
        elif power == "on":
            self._set_op_state(DevState.FAULT)
        else:
            self._set_op_state(DevState.UNKNOWN)

    def _handle_http_error(self: MccsSubrackPrototype, exception: Exception) -> None:
        """
        Handle an HTTP-error style poll failure.

        The subrack is reachable but reported an HTTP error. If the PDU
        authoritatively reports our outlets as OFF we treat this as ``OFF``;
        otherwise we treat it as a fault (if we are on) or as unknown.

        :param exception: the exception that was raised.
        """
        self.logger.warning("Subrack poll failed (HTTP error): %s", exception)
        if self._pdu_power_state() == "off":
            self._set_op_state(DevState.OFF)
        elif self.get_state() == DevState.ON:
            self.component_fault()
        else:
            self._set_op_state(DevState.UNKNOWN)

    # -----------------
    # Cache ingestion
    # -----------------
    def _ingest_poll_values(self: MccsSubrackPrototype, **values: Any) -> None:
        """
        Ingest a batch of freshly-read hardware values into the cache.

        Events are not pushed here (see :py:meth:`_push_hardware_events`, called
        immediately after this by :py:meth:`_do_refresh`). Read methods set the
        attribute quality to ``ATTR_INVALID`` when the cached value is ``None``.

        :param values: keyword arguments of hardware read key to value.
        """
        for key, value in values.items():
            special_update_method = getattr(self, f"_update_{key}", None)
            if special_update_method is None:
                tango_attribute_name = self._ATTRIBUTE_MAP[key]
                self._hardware_attributes[tango_attribute_name] = value
            else:
                special_update_method(value)

    def _push_hardware_events(self: MccsSubrackPrototype) -> None:
        """
        Push change/archive events for every hardware-backed attribute with data.

        Only called by :py:meth:`_do_refresh` for a *forced* refresh (going
        online, or after a board command). A refresh triggered by
        ``read_attr_hardware`` runs as part of Tango's own poll tick, which
        pushes change events for us automatically once it reads each attribute
        right after ``read_attr_hardware`` returns (the polled attributes are
        configured with change detection), so no manual push is needed there.
        A forced refresh isn't tied to that cycle, so without this, subscribers
        would wait up to a full poll period for Tango's own tick to notice the
        change.

        Every attribute with a value is pushed unconditionally rather than
        diffing against a pre-refresh snapshot: each was configured with
        ``detect=True`` in ``init_device``, so Tango itself only actually
        delivers a push to subscribers when the value has really changed,
        making an app-level diff redundant.
        """
        self.push_change_event("tpmPresent", self._tpm_present)
        self.push_archive_event("tpmPresent", self._tpm_present)
        self.push_change_event("tpmCount", self._tpm_count)
        self.push_archive_event("tpmCount", self._tpm_count)
        for bay, power_state in enumerate(self._tpm_power_states):
            name = f"tpm{bay + 1}PowerState"
            self.push_change_event(name, power_state)
            self.push_archive_event(name, power_state)
        for name in self._POLLED_ATTRIBUTES:
            value = self._hardware_attributes.get(name)
            if value is None:
                continue
            # subrackBoardInfo is a str (JSON) attribute backed by a raw dict
            # in the cache; every other polled attribute's cached value is
            # already in the shape its Tango attribute expects.
            if name == "subrackBoardInfo":
                value = json.dumps(value)
            self.push_change_event(name, value)
            self.push_archive_event(name, value)

    def _store_health_status(
        self: MccsSubrackPrototype, health_status: Optional[dict]
    ) -> None:
        """
        Store the health-status dictionary and fan it into the signal attributes.

        :param health_status: the nested health-status dictionary from the SMB.
        """
        self._health_status = health_status or {}
        if health_status:
            for key, dict_path in self._HEALTH_STATUS_MAP.items():
                value: Any = health_status
                # health status here is a nested dictionary, so to reach the
                # expected value we take a key, find the dictionary that key
                # leads to and save that dictionary as the default. Repeat until
                # the list of keys is done and we arrive at the desired value.
                for path in dict_path:
                    if value:
                        value = value.get(path, None)
                setattr(self, self._HEALTH_SIGNAL_MAP[key], value)

    def _update_board_current(
        self: MccsSubrackPrototype, board_current: Optional[float]
    ) -> None:
        if board_current is None:
            self._hardware_attributes["boardCurrent"] = None
        else:
            self._hardware_attributes["boardCurrent"] = [board_current]

    def _update_tpm_present(
        self: MccsSubrackPrototype, tpm_present: Optional[list[bool]]
    ) -> None:
        if tpm_present is None:
            tpm_present = []
        self._tpm_present = tpm_present
        self._tpm_count = tpm_present.count(True)

    def _update_tpm_on_off(
        self: MccsSubrackPrototype, tpm_on_off: Optional[list[bool]]
    ) -> None:
        if tpm_on_off is None:
            power_states = [PowerState.UNKNOWN] * SubrackData.TPM_BAY_COUNT
        else:
            power_states = [
                PowerState.ON if is_on else PowerState.OFF for is_on in tpm_on_off
            ]
        self._update_tpm_power_states(power_states)

    def _update_tpm_power_states(
        self: MccsSubrackPrototype, tpm_power_states: list[PowerState]
    ) -> None:
        for index, power_state in enumerate(tpm_power_states):
            self._tpm_power_states[index] = power_state

    def _clear_hardware_attributes(self: MccsSubrackPrototype) -> None:
        """Clear the hardware cache, invalidating all derived attributes."""
        self._hardware_attributes.clear()
        self._health_status = {}
        for signal_name in self._HEALTH_SIGNAL_MAP.values():
            setattr(self, signal_name, None)
        self._update_tpm_present(None)
        self._update_tpm_power_states([PowerState.UNKNOWN] * SubrackData.TPM_BAY_COUNT)

    # -----------------------------
    # Board command execution
    # -----------------------------
    def _board_command_task(
        self: MccsSubrackPrototype,
        smb_command: str,
        args: str = "",
        *,
        is_health: bool = False,
    ) -> Callable:
        """
        Build a long-running-command task that runs a single SMB board command.

        The returned closure has the ``(task_callback, task_abort_event)``
        signature expected by the LRC framework and forwards to
        :py:meth:`_execute_board_command` (which serialises on ``_refresh_lock``
        and handles the async ``command_completed`` handshake).

        :param smb_command: the SMB command name.
        :param args: the SMB command argument string.
        :param is_health: whether the return value is a health-status dictionary
            that should be ingested.

        :return: the LRC task closure.
        """

        def task(
            task_callback: Optional[Callable],
            task_abort_event: Optional[threading.Event],
        ) -> None:
            self._execute_board_command(
                smb_command,
                args,
                task_callback,
                task_abort_event,
                is_health=is_health,
            )

        return task

    def _execute_board_command(
        self: MccsSubrackPrototype,
        name: str,
        args: str,
        task_callback: Optional[Callable],
        task_abort_event: Optional[threading.Event],
        *,
        is_health: bool = False,
    ) -> None:
        """
        Execute an SMB command directly, handling the async-command handshake.

        The hardware lock is held for the whole duration so that board commands
        are serialised with each other and with the polling refresh. If the SMB
        reports ``STARTED`` (an asynchronous command) the ``command_completed``
        command is polled until the command finishes or is aborted. Once the
        lock is released, a forced refresh re-fetches and pushes events for any
        state the command changed (e.g. TPM power) immediately, rather than
        leaving subscribers to wait for the next natural poll tick.

        :param name: the SMB command name.
        :param args: the SMB command argument string.
        :param task_callback: callback used to report the command status.
        :param task_abort_event: event set to request the command be aborted.
        :param is_health: whether the return value is a health-status dictionary
            that should be ingested.
        """
        if task_callback is not None:
            task_callback(status=TaskStatus.IN_PROGRESS)

        with self._refresh_lock:
            response = self._client.execute_command(name, args)
            status = response["status"]
            if status == HardwareClientResponseStatusCodes.OK.name:
                retvalue = response["retvalue"]
                if retvalue == HardwareClientResponseStatusCodes.STARTED.name:
                    self._await_command_completion(task_callback, task_abort_event)
                elif retvalue == "FAILED":
                    self._report_task_failed(
                        task_callback,
                        f"Board busy, command '{name}' was not accepted.",
                    )
                else:
                    if is_health:
                        # See the comment in ``_maybe_fetch_health``: this
                        # command's retvalue is actually a nested dict.
                        self._store_health_status(cast(Optional[dict], retvalue))
                    self._report_task_completed(task_callback)
            elif status == HardwareClientResponseStatusCodes.STARTED.name:
                self._await_command_completion(task_callback, task_abort_event)
            elif status == HardwareClientResponseStatusCodes.BUSY.name:
                self._report_task_failed(
                    task_callback,
                    f"Board busy, command '{name}' was not accepted.",
                )
            else:
                self._report_task_failed(
                    task_callback,
                    f"Command '{name}' failed with status '{status}': "
                    f"{response.get('info', 'no details')}",
                )
        self._do_refresh(force=True)

    def _await_command_completion(
        self: MccsSubrackPrototype,
        task_callback: Optional[Callable],
        task_abort_event: Optional[threading.Event],
    ) -> None:
        """
        Poll the SMB ``command_completed`` command until the command finishes.

        This must be called while holding ``self._refresh_lock``.

        :param task_callback: callback used to report the command status.
        :param task_abort_event: event set to request the command be aborted.
        """
        deadline = time.monotonic() + self._COMMAND_TIMEOUT
        while True:
            if task_abort_event is not None and task_abort_event.is_set():
                if task_callback is not None:
                    task_callback(status=TaskStatus.ABORTED)
                return
            if time.monotonic() > deadline:
                self._report_task_failed(
                    task_callback, "Timed out waiting for command to complete."
                )
                return
            time.sleep(self._COMMAND_POLL_INTERVAL)
            response = self._client.execute_command("command_completed")
            status = response["status"]
            if status == HardwareClientResponseStatusCodes.OK.name:
                if response.get("retvalue"):
                    self._report_task_completed(task_callback)
                    return
                # Command still running.
                continue
            if status == HardwareClientResponseStatusCodes.REQUEST_EXCEPTION.name:
                self._report_task_failed(task_callback, f"{response['info']}")
                return
            if status == HardwareClientResponseStatusCodes.HTTP_ERROR.name:
                self._report_task_failed(task_callback, f"{response['info']}")
                return
            # BUSY / STARTED: keep waiting.

    @staticmethod
    def _report_task_completed(task_callback: Optional[Callable]) -> None:
        if task_callback is not None:
            task_callback(
                status=TaskStatus.COMPLETED,
                result=(ResultCode.OK, "Command completed."),
            )

    @staticmethod
    def _report_task_failed(task_callback: Optional[Callable], message: str) -> None:
        if task_callback is not None:
            task_callback(
                status=TaskStatus.FAILED,
                result=(ResultCode.FAILED, message),
            )

    # -----------------------
    # PDU / marshaller proxies
    # -----------------------
    def _get_proxy(
        self: MccsSubrackPrototype,
        trl: str,
        cache_attr: str,
        description: str,
    ) -> Optional[tango.DeviceProxy]:
        """
        Lazily create, cache and return a device proxy to ``trl``.

        :param trl: the target device's TRL.
        :param cache_attr: the instance attribute used to cache the proxy.
        :param description: a human-readable name of the target, for logging.

        :return: the cached device proxy, or ``None`` if it cannot be created.
        """
        proxy = getattr(self, cache_attr)
        if proxy is None:
            try:
                proxy = tango.DeviceProxy(trl)
            except DevFailed as exc:
                self.logger.warning(
                    "Could not connect to %s '%s': %s",
                    description,
                    trl,
                    exc.args[0].desc if exc.args else exc,
                )
                return None
            setattr(self, cache_attr, proxy)
        return proxy

    def _get_pdu_proxy(self: MccsSubrackPrototype) -> Optional[tango.DeviceProxy]:
        """
        Lazily create and return a device proxy to the PDU, if configured.

        :return: a device proxy to the PDU, or ``None`` if there is no PDU (or a
            simulated one).
        """
        if self.SimulatedPDU or not self.PduTrl:
            return None
        return self._get_proxy(self.PduTrl, "_pdu_proxy", "PDU")

    def _get_marshaller_proxy(
        self: MccsSubrackPrototype,
    ) -> Optional[tango.DeviceProxy]:
        """
        Lazily create and return a device proxy to the power marshaller.

        :return: a device proxy to the power marshaller, or ``None`` if there is
            no power marshaller configured.
        """
        if not self.PowerMarshallerTrl:
            return None
        return self._get_proxy(
            self.PowerMarshallerTrl, "_marshaller_proxy", "power marshaller"
        )

    # ---------------------------
    # PDU power-state subscription
    # ---------------------------
    def _subscribe_pdu(self: MccsSubrackPrototype) -> None:
        """
        Subscribe to change events on this subrack's own PDU outlet states.

        For each port in the ``PduPorts`` property, a *stateless* change-event
        subscription is placed on the PDU's ``pduPort{n}State`` attribute so that
        the device keeps a continually-updated, event-driven view of its power
        (see :py:meth:`_pdu_port_state_changed`). Stateless subscriptions tolerate
        the PDU being down at subscription time. A simulated or unconfigured PDU,
        or a PDU proxy that cannot be created, leaves the power state "unknown"
        (the graceful fallback), so subscription failures never crash init or
        admin transitions.
        """
        if self.SimulatedPDU or not self.PduTrl:
            return
        proxy = self._get_pdu_proxy()
        if proxy is None:
            self.logger.warning(
                "Could not obtain PDU proxy '%s'; PDU power state stays unknown.",
                self.PduTrl,
            )
            return
        for port in self.PduPorts:
            try:
                eid = proxy.subscribe_event(
                    f"pduPort{port}State",
                    tango.EventType.CHANGE_EVENT,
                    functools.partial(self._pdu_port_state_changed, port),
                    stateless=True,
                )
                self._pdu_event_ids.append(eid)
            except DevFailed:
                self.logger.warning(
                    "Failed to subscribe to PDU 'pduPort%sState' events.",
                    port,
                    exc_info=True,
                )

    def _unsubscribe_pdu(self: MccsSubrackPrototype) -> None:
        """
        Unsubscribe from all PDU change events and reset the power-state cache.

        Failures to unsubscribe (e.g. the PDU is already gone) are ignored. All
        cached port states are reset to ``None`` (unknown).
        """
        for eid in self._pdu_event_ids:
            try:
                if self._pdu_proxy is not None:
                    self._pdu_proxy.unsubscribe_event(eid)
            except DevFailed:
                self.logger.debug(
                    "Failed to unsubscribe PDU event id %s (ignored).",
                    eid,
                    exc_info=True,
                )
        self._pdu_event_ids = []
        with self._pdu_state_lock:
            for port in self._pdu_port_states:
                self._pdu_port_states[port] = None

    def _pdu_port_state_changed(
        self: MccsSubrackPrototype, port: int, event: Any
    ) -> None:
        """
        Handle a change event on a PDU outlet-state attribute.

        Updates the cached power state for ``port`` and re-evaluates the device's
        operational state. Runs off the main thread (Tango event thread), so any
        Tango calls it makes are guarded by :py:class:`tango.EnsureOmniThread`.

        :param port: the PDU port number this event pertains to.
        :param event: the Tango change event.
        """
        with tango.EnsureOmniThread():
            if event.err:
                self.logger.debug(
                    "PDU 'pduPort%sState' event reported an error; "
                    "marking power state unknown.",
                    port,
                )
                with self._pdu_state_lock:
                    self._pdu_port_states[port] = None
                return
            with self._pdu_state_lock:
                self._pdu_port_states[port] = self._interpret_pdu_port_state(
                    event.attr_value.value
                )
            self._reevaluate_power_state()

    @staticmethod
    def _interpret_pdu_port_state(value: Any) -> bool | None:
        """
        Interpret a raw ``pduPort{n}State`` value as energised / not / unknown.

        The attribute is vendor-dependent: enlogic exposes a clean ``bool``
        (off 0 / on 1), whereas raritan exposes an enum whose relevant members
        are ``open(0)`` (not energised) and ``closed(1)`` (energised) but which
        also includes analogue-sensor states. So we map ``1`` -> on and ``0`` ->
        off explicitly and treat anything else as unknown rather than coercing
        with ``bool()``.

        :param value: the raw attribute value from the PDU.

        :return: ``True`` (energised), ``False`` (not energised) or ``None``
            (unknown / unrecognised).
        """
        try:
            as_int = int(value)
        except (TypeError, ValueError):
            return None
        if as_int == 1:
            return True
        if as_int == 0:
            return False
        return None

    def _pdu_power_state(self: MccsSubrackPrototype) -> str:
        """
        Return the aggregate power state of this subrack's own PDU outlets.

        :return: ``"off"`` if every tracked outlet is known-off, ``"on"`` if any
            tracked outlet is known-on, or ``"unknown"`` if there is no PDU to
            track or any outlet's state has not yet been observed.
        """
        if self.SimulatedPDU or not self.PduTrl:
            return "unknown"
        with self._pdu_state_lock:
            values = [self._pdu_port_states.get(port) for port in self.PduPorts]
        if not values or any(value is None for value in values):
            return "unknown"
        if all(value is False for value in values):
            return "off"
        return "on"

    def _reevaluate_power_state(self: MccsSubrackPrototype) -> None:
        """
        Proactively resolve operational state from a fresh PDU power reading.

        Called from the PDU event callback. When online and the PDU reports the
        subrack's outlets as OFF, this drives the operational state to OFF now
        (and clears the hardware cache) rather than waiting for the next poll to
        fail against an unpowered board. For "on"/"unknown" nothing is done
        proactively: the poll loop resolves those cases.
        """
        if not self._is_online:
            return
        if self._pdu_power_state() == "off" and self.get_state() != DevState.OFF:
            self._set_op_state(DevState.OFF)
            self._clear_hardware_attributes()

    def _power_own_pdu_ports(self: MccsSubrackPrototype, is_on: bool) -> bool:
        """
        Power the subrack's own PDU ports on or off via the PDU device proxy.

        Acts only on the ports listed in the ``PduPorts`` property (the ports
        that feed this subrack), using the PDU device's deterministic
        ``pduPortOn``/``pduPortOff`` commands.

        :param is_on: whether to power the ports on (else off).

        :return: ``True`` if the PDU was reachable and the ports were commanded;
            ``False`` if there is no reachable PDU (simulated or unconfigured).
        """
        proxy = self._get_pdu_proxy()
        if proxy is None:
            return False
        command = "pduPortOn" if is_on else "pduPortOff"
        for port in self.PduPorts:
            getattr(proxy, command)(port)
        return True

    def _schedule(
        self: MccsSubrackPrototype,
        is_turn_on: bool,
        task_callback: Optional[Callable],
    ) -> None:
        """
        Schedule the subrack on or off via the power marshaller device proxy.

        :param is_turn_on: whether to schedule on (else off).
        :param task_callback: callback used to report the command status.
        """
        if task_callback is not None:
            task_callback(status=TaskStatus.IN_PROGRESS)
        marshaller = self._get_marshaller_proxy()
        if marshaller is None:
            self.logger.warning(
                "PowerMarshaller not configured, cannot schedule power %s",
                "on" if is_turn_on else "off",
            )
            if task_callback is not None:
                task_callback(
                    status=TaskStatus.COMPLETED,
                    result=(ResultCode.OK, "No power marshaller configured."),
                )
            return
        command_str = "pduPortOn" if is_turn_on else "pduPortOff"
        for port in self.PduPorts:
            input_dict = {
                "attached_device_info": "subrack",
                "device_trl": self.PduTrl,
                "command_str": command_str,
                "command_args": str(port),
            }
            marshaller.SchedulePower(json.dumps(input_dict))
        if task_callback is not None:
            task_callback(
                status=TaskStatus.COMPLETED,
                result=(ResultCode.OK, "Power schedule requested."),
            )

    # ----------
    # Callbacks
    # ----------
    def _health_changed_new(
        self: MccsSubrackPrototype, health: HealthState, health_report: str
    ) -> None:
        """
        Handle a change in health from the health recorder.

        :param health: the new health value.
        :param health_report: the health report.
        """
        if self._stopping:
            return
        self._health_report = health_report
        self._health_state = health
        self._report_health_state(health, health_report)

    def _report_health_state(
        self: MccsSubrackPrototype, health: HealthState, health_report: str
    ) -> None:
        """
        Reflect a health state on the ``healthState``/``healthInfo`` attributes.

        The :py:meth:`BaseInterface.report_health` method does not support
        ``HealthState.UNKNOWN``, so for that case we emit ``UNKNOWN`` health
        directly on the shared bus.

        :param health: the new health value.
        :param health_report: the health report.
        """
        info = [health_report] if health_report else []
        if health == HealthState.UNKNOWN:
            timestamp = time.time()
            quality = AttrQuality.ATTR_VALID
            self.shared_bus.emit(
                "._health_state", (health, timestamp, quality), store=True
            )
            self.shared_bus.emit(
                "._health_info",
                (info or ["Health is unknown."], timestamp, quality),
            )
        elif health == HealthState.OK:
            self.report_health(HealthState.OK, [])
        else:
            self.report_health(health, info or [f"Health is {health.name}."])

    def _attr_conf_changed(self: MccsSubrackPrototype, attribute_name: str) -> None:
        """
        Handle a change in attribute configuration.

        This is a workaround: if you reconfigure a non-alarming attribute to have
        alarm/warning thresholds such that it would be alarming, Tango does not
        push an event until the attribute value changes.

        :param attribute_name: the name of the attribute whose configuration
            has changed.
        """
        if attribute_name in self._HEALTH_SIGNAL_MAP:
            attr_data = self._SignalBusMixin__attr_values.get(attribute_name)
            if attr_data is not None and attr_data.quality != AttrQuality.ATTR_INVALID:
                signal_name = self._HEALTH_SIGNAL_MAP[attribute_name]
                setattr(self, signal_name, attr_data.value)
        elif attribute_name in self._hardware_attributes:
            value_cache = self._hardware_attributes[attribute_name]
            if value_cache is not None:
                self.push_change_event(attribute_name, value_cache)
                self.push_archive_event(attribute_name, value_cache)

    # ----------------------------------------------------------------------
    # Tango commands: Standard On / Off
    # ----------------------------------------------------------------------
    def execute_On(
        self: MccsSubrackPrototype,
    ) -> tuple[list[ResultCode], list[str]]:
        """
        Turn the subrack on by powering its own PDU ports on.

        Fails (without changing operational state) if there is no reachable PDU
        to power. The board booting and becoming reachable is reflected by the
        polling loop, which drives the operational state to ON.

        :return: a result code and message.
        """
        if not self._power_own_pdu_ports(True):
            return (
                [ResultCode.FAILED],
                ["Cannot power on: no reachable PDU configured for this subrack."],
            )
        return ([ResultCode.OK], ["Subrack PDU ports powered on."])

    def execute_Off(
        self: MccsSubrackPrototype,
    ) -> tuple[list[ResultCode], list[str]]:
        """
        Turn the subrack off by powering its own PDU ports off.

        Fails (without changing operational state) if there is no reachable PDU
        to power. Once the ports are off the board becomes unreachable, which the
        polling loop reflects in the operational state.

        :return: a result code and message.
        """
        if not self._power_own_pdu_ports(False):
            return (
                [ResultCode.FAILED],
                ["Cannot power off: no reachable PDU configured for this subrack."],
            )
        return ([ResultCode.OK], ["Subrack PDU ports powered off."])

    # ----------------------
    # Long running commands
    # ----------------------

    @stb.long_running_commands.long_running_command
    def PowerOnTpm(  # pylint: disable=invalid-name
        self: MccsSubrackPrototype, tpm_number: int
    ) -> stb.type_hints.TaskFunctionType:
        """
        Power up a TPM.

        :param tpm_number: the logical id of the TPM to power up

        :return: A tuple containing a return code and a string message
            indicating status. The message is for information purposes
            only.
        """
        return self._board_command_task("turn_on_tpm", str(tpm_number))

    @stb.long_running_commands.long_running_command
    def PowerOffTpm(  # pylint: disable=invalid-name
        self: MccsSubrackPrototype, tpm_number: int
    ) -> stb.type_hints.TaskFunctionType:
        """
        Power down a TPM.

        :param tpm_number: the logical id of the TPM to power down

        :return: A tuple containing a return code and a string message
            indicating status. The message is for information purposes
            only.
        """
        return self._board_command_task("turn_off_tpm", str(tpm_number))

    @stb.long_running_commands.long_running_command
    def PowerUpTpms(  # pylint: disable=invalid-name
        self: MccsSubrackPrototype,
    ) -> stb.type_hints.TaskFunctionType:
        """
        Power up all TPMs.

        :return: A tuple containing a return code and a string message
            indicating status. The message is for information purposes
            only.
        """
        return self._board_command_task("turn_on_tpms")

    @stb.long_running_commands.long_running_command
    def PowerDownTpms(  # pylint: disable=invalid-name
        self: MccsSubrackPrototype,
    ) -> stb.type_hints.TaskFunctionType:
        """
        Power down all TPMs.

        :return: A tuple containing a return code and a string message
            indicating status. The message is for information purposes
            only.
        """
        return self._board_command_task("turn_off_tpms")

    @stb.long_running_commands.long_running_command
    @stb.validators.validate_json_args(schema=SetSubrackFanSpeed_SCHEMA)
    def SetSubrackFanSpeed(  # pylint: disable=invalid-name
        self: MccsSubrackPrototype,
        subrack_fan_id: int,
        speed_percent: int,
    ) -> stb.type_hints.TaskFunctionType:
        """
        Set the selected subrack backplane fan speed.

        A json dictionary with mandatory keywords

        :param subrack_fan_id: (int) fan id from 1 to 4
        :param speed_percent: (int) fan speed in percent

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        return self._board_command_task(
            "set_subrack_fan_speed", f"{int(subrack_fan_id)},{int(speed_percent)}"
        )

    @stb.long_running_commands.long_running_command
    @stb.validators.validate_json_args(schema=SetSubrackFanMode_SCHEMA)
    def SetSubrackFanMode(  # pylint: disable=invalid-name
        self: MccsSubrackPrototype,
        fan_id: int,
        mode: FanMode,
    ) -> stb.type_hints.TaskFunctionType:
        """
        Set the selected subrack backplane fan mode.

        A json dictionary with mandatory keywords

        :param fan_id: (int) fan id from 1 to 4
        :param mode: (int) mode: 0=MANUAL, 1=AUTO

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        return self._board_command_task(
            "set_fan_mode", f"{int(fan_id)},{FanMode(mode).value}"
        )

    @stb.long_running_commands.long_running_command
    @stb.validators.validate_json_args(schema=SetPowerSupplyFanSpeed_SCHEMA)
    def SetPowerSupplyFanSpeed(  # pylint: disable=invalid-name
        self: MccsSubrackPrototype,
        power_supply_fan_id: int,
        speed_percent: int,
    ) -> stb.type_hints.TaskFunctionType:
        """
        Set the selected power supply fan speed.

        A json dictionary with mandatory keywords

        :param power_supply_fan_id: (int) power supply fan id from 1 to 2
        :param speed_percent: (int) fan speed in percent

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        return self._board_command_task(
            "set_power_supply_fan_speed",
            f"{int(power_supply_fan_id)},{int(speed_percent)}",
        )

    @stb.long_running_commands.long_running_command
    def ScheduleOn(self: MccsSubrackPrototype) -> stb.type_hints.TaskFunctionType:
        """
        Turn self on.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """

        def task(
            task_callback: stb.type_hints.TaskCallbackType,
            task_abort_event: threading.Event,
        ) -> None:
            self._schedule(True, task_callback)

        return task

    @stb.long_running_commands.long_running_command
    def ScheduleOff(self: MccsSubrackPrototype) -> stb.type_hints.TaskFunctionType:
        """
        Turn self off.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """

        def task(
            task_callback: stb.type_hints.TaskCallbackType,
            task_abort_event: threading.Event,
        ) -> None:
            self._schedule(False, task_callback)

        return task

    @stb.long_running_commands.long_running_command
    def UpdateHealthAttributes(  # pylint: disable=invalid-name
        self: MccsSubrackPrototype,
    ) -> stb.type_hints.TaskFunctionType:
        """
        Request the subrack to poll the health status attributes.

        :return: A tuple containing a return code and a string message
            indicating status. The message is for information purposes
            only.
        """
        return self._board_command_task("get_health_status", "", is_health=True)

    # ----------
    # Tango attributes
    # ----------
    def _read_hw(self: MccsSubrackPrototype, name: str, empty: Any) -> Any:
        """
        Read a cached hardware attribute, invalidating it if the value is ``None``.

        :param name: the Tango attribute name.
        :param empty: a type-appropriate empty value to associate with the
            ``ATTR_INVALID`` quality when the cached value is ``None``.

        :return: the cached value, or ``None`` (with quality set to
            ``ATTR_INVALID``) when no value is available.
        """
        value = self._hardware_attributes.get(name, None)
        if value is None:
            self.get_device_attr().get_attr_by_name(name).set_value_date_quality(
                empty, time.time(), AttrQuality.ATTR_INVALID
            )
            return None
        return value

    @attribute(dtype="DevShort", label="TPM count", abs_change=1)
    def tpmCount(self: MccsSubrackPrototype) -> int:
        """
        Handle a Tango attribute read of TPM count.

        :return: the number of TPMs present in the subrack.
            When communication with the subrack is not established,
            this returns 0.
        """
        return self._tpm_count

    @attribute(dtype=(bool,), max_dim_x=8, label="TPM present")
    def tpmPresent(  # pylint: disable=invalid-name
        self: MccsSubrackPrototype,
    ) -> list[bool]:
        """
        Handle a Tango attribute read of which TPMs are present in the subrack.

        :return: whether a TPM is present in each bay.
            When communication with the subrack is not established,
            this returns an empty list.
        """
        return self._tpm_present

    @attribute(
        dtype=("DevFloat",),
        max_dim_x=2,
        label="Backplane temperatures",
        unit="Celsius",
        abs_change=0.1,
    )
    def backplaneTemperatures(self: MccsSubrackPrototype) -> list[float] | None:
        """
        Handle a Tango attribute read of the subrack backplane temperature.

        Two values are returned, respectively for the first (bays 1-4)
        and second (bays 5-8) halves of the backplane.

        :return: the backplane temperatures.
            When communication with the subrack is not established,
            this returns none.
        """
        return self._read_hw("backplaneTemperatures", [])

    @attribute(
        dtype=("DevFloat",),
        max_dim_x=2,
        label="Subrack board temperatures",
        unit="Celsius",
        abs_change=0.1,
    )
    def boardTemperatures(self: MccsSubrackPrototype) -> list[float] | None:
        """
        Handle a Tango attribute read of the subrack board temperature.

        Two values are returned.

        :return: the board temperatures.
            When communication with the subrack is not established,
            this returns none.
        """
        return self._read_hw("boardTemperatures", [])

    @attribute(
        dtype=("DevFloat",),
        label="Board current",
        unit="Ampere",
        abs_change=0.1,
    )
    def boardCurrent(self: MccsSubrackPrototype) -> list[float] | None:
        """
        Handle a Tango attribute read of subrack management board current.

        Total current provided by the two power supplies.

        :return: total board current, in a list of length 1.
            When communication with the subrack is not established,
            this returns none.
        """
        return self._read_hw("boardCurrent", [])

    @attribute(dtype=bool, label="CPLD PLL locked")
    def cpldPllLocked(self: MccsSubrackPrototype) -> bool | None:
        """
        Handle a Tango attribute read of the subrack CPLD PLL locked attribute.

        :return: whether the CPLD PLL is locked.
        """
        return self._read_hw("cpldPllLocked", False)

    @attribute(
        dtype=("DevFloat",), max_dim_x=2, label="power supply currents", abs_change=0.1
    )
    def powerSupplyCurrents(self: MccsSubrackPrototype) -> list[float] | None:
        """
        Handle a Tango attribute read of the power supply currents.

        :return: the power supply currents.
            When communication with the subrack is not established,
            this returns none.
        """
        return self._read_hw("powerSupplyCurrents", [])

    @attribute(
        dtype=("DevFloat",),
        max_dim_x=3,
        label="power supply fan speeds",
        abs_change=0.1,
    )
    def powerSupplyFanSpeeds(self: MccsSubrackPrototype) -> list[float] | None:
        """
        Handle a Tango attribute read of the power supply fan speeds.

        Values expressed in percent of maximum.

        :return: the power supply fan speeds.
            When communication with the subrack is not established,
            this returns none.
        """
        return self._read_hw("powerSupplyFanSpeeds", [])

    @attribute(
        dtype=("DevFloat",), max_dim_x=2, label="power supply powers", abs_change=0.1
    )
    def powerSupplyPowers(self: MccsSubrackPrototype) -> list[float] | None:
        """
        Handle a Tango attribute read of the power supply powers.

        :return: the power supply powers.
            When communication with the subrack is not established,
            this returns none.
        """
        return self._read_hw("powerSupplyPowers", [])

    @attribute(
        dtype=("DevFloat",), max_dim_x=2, label="power supply voltages", abs_change=0.1
    )
    def powerSupplyVoltages(self: MccsSubrackPrototype) -> list[float] | None:
        """
        Handle a Tango attribute read of the power supply voltages.

        :return: the power supply voltages.
            When communication with the subrack is not established,
            this returns none.
        """
        return self._read_hw("powerSupplyVoltages", [])

    @attribute(
        dtype=("DevFloat",), max_dim_x=4, label="subrack fan speeds", abs_change=0.1
    )
    def subrackFanSpeeds(self: MccsSubrackPrototype) -> list[float] | None:
        """
        Handle a Tango attribute read of the subrack fan speeds, in RPM.

        :return: the subrack fan speeds.
            When communication with the subrack is not established,
            this returns none.
        """
        return self._read_hw("subrackFanSpeeds", [])

    @attribute(
        dtype=("DevFloat",), max_dim_x=4, label="subrack fan speeds (%)", abs_change=0.1
    )
    def subrackFanSpeedsPercent(self: MccsSubrackPrototype) -> list[float] | None:
        """
        Handle a Tango attribute read of the subrack fan speeds, in percent.

        This is the commanded setpoint; the relation between this level and
        the actual RPMs is not linear. Subrack speed is managed
        automatically by the controller, by default (see
        subrack_fan_mode).

        Commanded speed is the same for fans 1-2 and 3-4.

        :return: the subrack fan speed setpoints in percent.
            When communication with the subrack is not established,
            this returns none.
        """
        return self._read_hw("subrackFanSpeedsPercent", [])

    # TODO: https://gitlab.com/tango-controls/pytango/-/issues/483
    # Once this is fixed, we can use dtype=(FanMode,).
    @attribute(dtype=(int,), max_dim_x=4, label="subrack fan modes", abs_change=1)
    def subrackFanModes(self: MccsSubrackPrototype) -> list[int] | None:
        """
        Handle a Tango attribute read of the subrack fan modes.

        :return: the subrack fan modes.
            When communication with the subrack is not established,
            this returns none.
        """
        return self._read_hw("subrackFanModes", [])

    @attribute(dtype=bool, label="PLL locked")
    def subrackPllLocked(self: MccsSubrackPrototype) -> bool | None:
        """
        Handle a Tango attribute read of the subrack PLL locked attribute.

        :return: whether the subrack PLL is locked.
        """
        return self._read_hw("subrackPllLocked", False)

    @attribute(
        dtype="DevLong",
        label="Timestamp",
        abs_change=1,
    )
    def subrackTimestamp(self: MccsSubrackPrototype) -> int | None:
        """
        Handle a Tango attribute read of the subrack timestamp attribute.

        :return: the subrack timestamp
        """
        return self._read_hw("subrackTimestamp", 0)

    @attribute(dtype=str, label="Health Status Dictionary")
    def healthStatus(self: MccsSubrackPrototype) -> str | None:
        """
        Handle a dictionary of all available monitoring points.

        :return: A dictionary containing all the monitoring points
        """
        return json.dumps(self._health_status)

    def _invalidate_pdu_attribute(
        self: MccsSubrackPrototype, name: str, empty: Any
    ) -> None:
        """
        Mark a live-proxied ``pdu*`` attribute as unavailable.

        :param name: the Tango attribute name.
        :param empty: a type-appropriate empty value to associate with the
            ``ATTR_INVALID`` quality.
        """
        self.get_device_attr().get_attr_by_name(name).set_value_date_quality(
            empty, time.time(), AttrQuality.ATTR_INVALID
        )

    @attribute(dtype=str, label="pdu_health")
    def pduHealth(self: MccsSubrackPrototype) -> str | None:
        """
        Handle a Tango attribute read of the pdu health.

        :return: the pdu health
        """
        proxy = self._get_pdu_proxy()
        if proxy is None:
            self._invalidate_pdu_attribute("pduHealth", "")
            return None
        return proxy.healthState

    @attribute(dtype=str, label="pdu_model")
    def pduModel(self: MccsSubrackPrototype) -> str | None:
        """
        Handle a Tango attribute read of the pdu model type.

        :return: the pdu model type
        """
        proxy = self._get_pdu_proxy()
        if proxy is None:
            self._invalidate_pdu_attribute("pduModel", "")
            return None
        return proxy.pduModel

    @attribute(dtype="DevShort", label="pdu number ports")
    def pduNumberPorts(self: MccsSubrackPrototype) -> int | None:
        """
        Handle a Tango attribute read of the number of pdu ports.

        :return: the number of pdu ports
        """
        proxy = self._get_pdu_proxy()
        if proxy is None:
            self._invalidate_pdu_attribute("pduNumberPorts", 0)
            return None
        return proxy.pduNumberOfPorts

    def _read_pdu_port_series(
        self: MccsSubrackPrototype, name: str, suffix: str
    ) -> list | None:
        """
        Read a per-port PDU series (state, current or voltage) from the PDU proxy.

        :param name: the Tango attribute name.
        :param suffix: the ``pduPort{n}<suffix>`` attribute suffix to read for each
            port, e.g. ``"State"``, ``"Current"`` or ``"Voltage"``.

        :return: one value per PDU port, or ``None`` when the PDU proxy is absent.
        """
        proxy = self._get_pdu_proxy()
        if proxy is None:
            self._invalidate_pdu_attribute(name, [])
            return None
        return [
            getattr(proxy, f"pduPort{port_number}{suffix}")
            for port_number in range(proxy.pduNumberOfPorts)
        ]

    @attribute(dtype=(int,), label="pdu port states")
    def pduPortStates(self: MccsSubrackPrototype) -> list[int] | None:
        """
        Handle a Tango attribute read of the state of each pdu port.

        :return: the state of each port.
        """
        return self._read_pdu_port_series("pduPortStates", "State")

    @attribute(dtype=("DevFloat",), label="pdu port currents")
    def pduPortCurrents(self: MccsSubrackPrototype) -> list[float] | None:
        """
        Handle a Tango attribute read of the current of each pdu port.

        :return: the current of each port.
        """
        return self._read_pdu_port_series("pduPortCurrents", "Current")

    @attribute(dtype=("DevFloat",), label="pdu port voltages")
    def pduPortVoltages(self: MccsSubrackPrototype) -> list[float] | None:
        """
        Handle a Tango attribute read of the voltage of each pdu port.

        :return: the voltage of each port.
        """
        return self._read_pdu_port_series("pduPortVoltages", "Voltage")

    @attribute(dtype=("DevFloat",), max_dim_x=8, label="TPM currents", abs_change=0.1)
    def tpmCurrents(self: MccsSubrackPrototype) -> list[float] | None:
        """
        Handle a Tango attribute read of the TPM currents.

        :return: the TPM currents.
            When communication with the subrack is not established,
            this returns none.
        """
        return self._read_hw("tpmCurrents", [])

    @attribute(
        dtype=("DevFloat",),
        max_dim_x=8,
        label="TPM powers",
        max_alarm=120.0,
        abs_change=0.1,
    )
    def tpmPowers(self: MccsSubrackPrototype) -> list[float] | None:
        """
        Handle a Tango attribute read of the TPM powers.

        :return: the TPM powers.
            When communication with the subrack is not established,
            this returns none.
        """
        return self._read_hw("tpmPowers", [])

    @attribute(
        dtype=("DevFloat",),
        max_dim_x=8,
        label="TPM voltages",
        min_alarm=11.4,
        max_alarm=12.6,
        abs_change=0.1,
    )
    def tpmVoltages(self: MccsSubrackPrototype) -> list[float] | None:
        """
        Handle a Tango attribute read of the TPM voltages.

        :return: the TPM voltages
        """
        return self._read_hw("tpmVoltages", [])

    @attribute(dtype=str, label="Subrack Board Info")
    def subrackBoardInfo(self: MccsSubrackPrototype) -> str | None:
        """
        Handle a Tango attribute read of the Subrack board info.

        :return: the subrack board info as a dict
        """
        return json.dumps(self._hardware_attributes.get("subrackBoardInfo", None))

    @attribute(dtype="DevString")
    def healthReport(self: MccsSubrackPrototype) -> str:
        """
        Get the health report.

        :return: the health report.
        """
        return self._health_report

    @attribute(dtype=PowerState, label="TPM 1 power state")
    def tpm1PowerState(
        self: MccsSubrackPrototype,
    ) -> PowerState:
        """
        Handle a Tango attribute read of the power state of TPM 1.

        :return: the power state of TPM 1.
        """
        return self._tpm_power_states[0]

    @attribute(dtype=PowerState, label="TPM 2 power state")
    def tpm2PowerState(
        self: MccsSubrackPrototype,
    ) -> PowerState:
        """
        Handle a Tango attribute read of the power state of TPM 2.

        :return: the power state of TPM 2.
        """
        return self._tpm_power_states[1]

    @attribute(dtype=PowerState, label="TPM 3 power state")
    def tpm3PowerState(
        self: MccsSubrackPrototype,
    ) -> PowerState:
        """
        Handle a Tango attribute read of the power state of TPM 3.

        :return: the power state of TPM 3.
        """
        return self._tpm_power_states[2]

    @attribute(dtype=PowerState, label="TPM 4 power state")
    def tpm4PowerState(
        self: MccsSubrackPrototype,
    ) -> PowerState:
        """
        Handle a Tango attribute read of the power state of TPM 4.

        :return: the power state of TPM 4.
        """
        return self._tpm_power_states[3]

    @attribute(dtype=PowerState, label="TPM 5 power state")
    def tpm5PowerState(
        self: MccsSubrackPrototype,
    ) -> PowerState:
        """
        Handle a Tango attribute read of the power state of TPM 5.

        :return: the power state of TPM 5.
        """
        return self._tpm_power_states[4]

    @attribute(dtype=PowerState, label="TPM 6 power state")
    def tpm6PowerState(
        self: MccsSubrackPrototype,
    ) -> PowerState:
        """
        Handle a Tango attribute read of the power state of TPM 6.

        :return: the power state of TPM 6.
        """
        return self._tpm_power_states[5]

    @attribute(dtype=PowerState, label="TPM 7 power state")
    def tpm7PowerState(
        self: MccsSubrackPrototype,
    ) -> PowerState:
        """
        Handle a Tango attribute read of the power state of TPM 7.

        :return: the power state of TPM 7.
        """
        return self._tpm_power_states[6]

    @attribute(dtype=PowerState, label="TPM 8 power state")
    def tpm8PowerState(
        self: MccsSubrackPrototype,
    ) -> PowerState:
        """
        Handle a Tango attribute read of the power state of TPM 8.

        :return: the power state of TPM 8.
        """
        return self._tpm_power_states[7]

    # Signals backing the internalVoltages* attributes.
    internal_voltages_1v1_signal: AttrSignal[float] = AttrSignal[float]()
    internal_voltages_1v5_signal: AttrSignal[float] = AttrSignal[float]()
    internal_voltages_2v5_signal: AttrSignal[float] = AttrSignal[float]()
    internal_voltages_2v8_signal: AttrSignal[float] = AttrSignal[float]()
    internal_voltages_3v_signal: AttrSignal[float] = AttrSignal[float]()
    internal_voltages_3v3_signal: AttrSignal[float] = AttrSignal[float]()
    internal_voltages_5v_signal: AttrSignal[float] = AttrSignal[float]()
    internal_voltages_arm_signal: AttrSignal[float] = AttrSignal[float]()
    internal_voltages_core_signal: AttrSignal[float] = AttrSignal[float]()
    internal_voltages_ddr_signal: AttrSignal[float] = AttrSignal[float]()
    internal_voltages_powerin_signal: AttrSignal[float] = AttrSignal[float]()
    internal_voltages_soc_signal: AttrSignal[float] = AttrSignal[float]()

    internalVoltages1V1 = attribute_from_signal(  # noqa: N815
        internal_voltages_1v1_signal,
        dtype="DevDouble",
        label="V_1V1",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack internal 1V1 supply voltage in Volts.",
    )

    internalVoltages1V5 = attribute_from_signal(  # noqa: N815
        internal_voltages_1v5_signal,
        dtype="DevDouble",
        label="V_1V5",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack internal 1V5 supply voltage in Volts.",
    )

    internalVoltages2V5 = attribute_from_signal(  # noqa: N815
        internal_voltages_2v5_signal,
        dtype="DevDouble",
        label="V_2V5",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack internal 2V5 supply voltage in Volts.",
    )

    internalVoltages2V8 = attribute_from_signal(  # noqa: N815
        internal_voltages_2v8_signal,
        dtype="DevDouble",
        label="V_2V8",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack internal 2V8 supply voltage in Volts.",
    )

    internalVoltages3V = attribute_from_signal(  # noqa: N815
        internal_voltages_3v_signal,
        dtype="DevDouble",
        label="V_3V",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack internal 3V supply voltage in Volts.",
    )

    internalVoltages3V3 = attribute_from_signal(  # noqa: N815
        internal_voltages_3v3_signal,
        dtype="DevDouble",
        label="V_3V3",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack internal 3V3 supply voltage in Volts.",
    )

    internalVoltages5V = attribute_from_signal(  # noqa: N815
        internal_voltages_5v_signal,
        dtype="DevDouble",
        label="V_5V",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack internal 5V supply voltage in Volts.",
    )

    internalVoltagesARM = attribute_from_signal(  # noqa: N815
        internal_voltages_arm_signal,
        dtype="DevDouble",
        label="V_ARM",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack internal ARM supply voltage in Volts.",
    )

    internalVoltagesCORE = attribute_from_signal(  # noqa: N815
        internal_voltages_core_signal,
        dtype="DevDouble",
        label="V_CORE",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack internal CORE supply voltage in Volts.",
    )

    internalVoltagesDDR = attribute_from_signal(  # noqa: N815
        internal_voltages_ddr_signal,
        dtype="DevDouble",
        label="V_DDR",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack internal DDR supply voltage in Volts.",
    )

    internalVoltagesPOWERIN = attribute_from_signal(  # noqa: N815
        internal_voltages_powerin_signal,
        dtype="DevDouble",
        label="V_POWERIN",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack power input voltage in Volts.",
    )

    internalVoltagesSOC = attribute_from_signal(  # noqa: N815
        internal_voltages_soc_signal,
        dtype="DevDouble",
        label="V_SOC",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack internal SOC supply voltage in Volts.",
    )


# ----------
# Run server
# ----------
def main(*args: str, **kwargs: str) -> int:
    """
    Launch an `MccsSubrackPrototype` Tango device server instance.

    :param args: positional arguments, passed to the Tango device
    :param kwargs: keyword arguments, passed to the server

    :return: the Tango server exit code
    """
    return MccsSubrackPrototype.run_server(args=args or None, **kwargs)


if __name__ == "__main__":
    main()
