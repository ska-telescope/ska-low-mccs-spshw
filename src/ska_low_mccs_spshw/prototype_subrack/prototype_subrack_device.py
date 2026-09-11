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

import json
import sys
from typing import Any, Final, Optional, cast

from ska_control_model import HealthState
from ska_low_mccs_common.component import WebHardwareClient
from ska_tango_base import BaseInterface
from ska_tango_base.base import ControlLevel
from ska_tango_base.software_bus import AttrSignal, attribute_from_signal
from tango import AttrQuality
from tango.server import device_property

from ..subrack.subrack_data import SubrackData
from .constants import DerivedKey, ReadKey, RequestError
from .subrack_client import Subrack, SubrackPoller, SubrackPollResponse

__all__ = ["MccsPrototypeSubrack", "main"]


# Hardware read key to the name of the signal that carries it. Keyed off the
# enums rather than string literals, so a renamed key is a type error rather
# than an attribute that silently stops updating.
_READ_KEY_TO_SIGNAL: Final[dict[str, str]] = {
    ReadKey.TPM_PRESENT.value: "_tpm_present",
    ReadKey.TPM_ON_OFF.value: "_tpm_on_off",
    ReadKey.BACKPLANE_TEMPERATURES.value: "_backplane_temperatures",
    ReadKey.BOARD_TEMPERATURES.value: "_board_temperatures",
    ReadKey.BOARD_CURRENT.value: "_board_current",
    ReadKey.CPLD_PLL_LOCKED.value: "_cpld_pll_locked",
    ReadKey.POWER_SUPPLY_CURRENTS.value: "_power_supply_currents",
    ReadKey.POWER_SUPPLY_FAN_SPEEDS.value: "_power_supply_fan_speeds",
    ReadKey.POWER_SUPPLY_POWERS.value: "_power_supply_powers",
    ReadKey.POWER_SUPPLY_VOLTAGES.value: "_power_supply_voltages",
    ReadKey.SUBRACK_FAN_SPEEDS.value: "_subrack_fan_speeds",
    ReadKey.SUBRACK_FAN_SPEEDS_PERCENT.value: "_subrack_fan_speeds_percent",
    ReadKey.SUBRACK_FAN_MODE.value: "_subrack_fan_modes",
    ReadKey.SUBRACK_PLL_LOCKED.value: "_subrack_pll_locked",
    ReadKey.SUBRACK_TIMESTAMP.value: "_subrack_timestamp",
    ReadKey.TPM_CURRENTS.value: "_tpm_currents",
    ReadKey.TPM_POWERS.value: "_tpm_powers",
    ReadKey.TPM_VOLTAGES.value: "_tpm_voltages",
    ReadKey.BOARD_INFO.value: "_subrack_board_info",
    DerivedKey.SUBRACK_MAX_FAN_SPEEDS.value: "_subrack_max_fan_speeds",
}

# Signal name to its path inside the polled health status dictionary.
_HEALTH_PATH_TO_SIGNAL: Final[dict[str, tuple[str, ...]]] = {
    "_internal_voltages_1v1": ("internal_voltages", "V_1V1"),
    "_internal_voltages_1v5": ("internal_voltages", "V_1V5"),
    "_internal_voltages_2v5": ("internal_voltages", "V_2V5"),
    "_internal_voltages_2v8": ("internal_voltages", "V_2V8"),
    "_internal_voltages_3v": ("internal_voltages", "V_3V"),
    "_internal_voltages_3v3": ("internal_voltages", "V_3V3"),
    "_internal_voltages_5v": ("internal_voltages", "V_5V"),
    "_internal_voltages_arm": ("internal_voltages", "V_ARM"),
    "_internal_voltages_core": ("internal_voltages", "V_CORE"),
    "_internal_voltages_ddr": ("internal_voltages", "V_DDR"),
    "_internal_voltages_powerin": ("internal_voltages", "V_POWERIN"),
    "_internal_voltages_soc": ("internal_voltages", "V_SOC"),
    "_psu1_present": ("psus", "present", "PSU1"),
    "_psu2_present": ("psus", "present", "PSU2"),
    "_psu1_power_in": ("psus", "power_in", "PSU1"),
    "_psu2_power_in": ("psus", "power_in", "PSU2"),
    "_psu1_power_out": ("psus", "power_out", "PSU1"),
    "_psu2_power_out": ("psus", "power_out", "PSU2"),
    "_psu1_voltage_in": ("psus", "voltage_in", "PSU1"),
    "_psu2_voltage_in": ("psus", "voltage_in", "PSU2"),
    "_psu1_voltage_out": ("psus", "voltage_out", "PSU1"),
    "_psu2_voltage_out": ("psus", "voltage_out", "PSU2"),
}

# Every signal this device emits, so that a lost board can invalidate the lot.
_ALL_SIGNALS: Final[tuple[str, ...]] = (
    tuple(_READ_KEY_TO_SIGNAL.values())
    + tuple(_HEALTH_PATH_TO_SIGNAL)
    + ("_psu_dead_count",)
)


def _as_spectrum(value: Any) -> list[Any]:
    """
    Wrap a scalar the board reports into the one element list Tango wants.

    :param value: the value the board reported.

    :return: the value as a list.
    """
    return list(value) if isinstance(value, (list, tuple)) else [value]


# The few signals whose board value is not already what the attribute expects.
_VALUE_CONVERTERS: Final[dict[str, Any]] = {
    # The board reports this as a nested dictionary, and the attribute is a
    # JSON string.
    "_subrack_board_info": json.dumps,
    # The board reports a single total, and the attribute is a one element
    # spectrum.
    "_board_current": _as_spectrum,
}

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
class MccsPrototypeSubrack(BaseInterface):
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
    # `_poller` carries a class level default so that `disassemble` is safe
    # even if `assemble` never ran, for instance when `init_device` raised. An
    # `__init__` cannot supply it, because `tango.server.Device.__init__` calls
    # `init_device` from inside its own `super().__init__()`, so anything
    # assigned after that call arrives too late for `init_device` to see.
    _client: WebHardwareClient
    _subrack: Subrack

    _poller: Optional[SubrackPoller] = None
    """The poller, once :py:meth:`assemble` has built it."""

    def assemble(self: MccsPrototypeSubrack) -> None:
        """
        Build the hardware client, the poll model and the poller.

        This is the only place that decides how the device reaches its board,
        so a subclass or a test can replace that decision by overriding this
        one method, rather than repeating the rest of initialisation.

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
        # The poller's thread outlives stop_polling, so one poller serves until
        # the device is re-initialised or deleted.
        self._poller = self._subrack_poller_factory(
            self._subrack, self.UpdateRate, self.logger
        )

    def disassemble(self: MccsPrototypeSubrack) -> None:
        """
        Stop the poller and reclaim its thread, if there is one.

        Safe to call when nothing has been assembled, and safe to call twice.
        """
        if self._poller is not None:
            self._poller.stop_polling()
            self._poller.kill_polling_thread()
            self._poller = None

    def init_device(self: MccsPrototypeSubrack) -> None:
        """Initialise the device, building the client and the poller."""
        super().init_device()

        self.assemble()

        self._version_id = sys.modules["ska_low_mccs_spshw"].__version__
        self._build_state = sys.modules["ska_low_mccs_spshw"].__version_info__

        # Settle in DISABLE. Tango applies a memorized adminMode only once
        # init_device has returned, so it takes the device online after this.
        self.change_control_level(ControlLevel.NO_CONTACT)

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

        :raises RuntimeError: if there is no poller to start or stop.
        """
        poller = self._poller
        if poller is None:
            raise RuntimeError(
                "change_control_level was called before assemble() built a "
                "poller. init_device assembles before Tango can write "
                "adminMode, so this should be unreachable."
            )

        if control_level == ControlLevel.NO_CONTACT:
            poller.stop_polling()
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
            poller.start_polling()

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
        for key, signal_name in _READ_KEY_TO_SIGNAL.items():
            self._emit(signal_name, poll_response.values.get(key), timestamp)
        self._emit_health_status(poll_response.health_status, timestamp)

        self.component_on()
        self.report_health(HealthState.OK, [])

    def _poll_failed(self: MccsPrototypeSubrack, exception: Exception) -> None:
        """
        Invalidate every attribute after a failed poll.

        A request that never reached the board leaves the subrack in an unknown
        state. Anything else is the board itself failing.

        :param exception: the exception raised by the poll.
        """
        self._invalidate_all()
        if isinstance(exception, RequestError):
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
        converter = _VALUE_CONVERTERS.get(signal_name)
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
        for signal_name, path in _HEALTH_PATH_TO_SIGNAL.items():
            self._emit(signal_name, _walk(health_status, path), timestamp)
        self._emit("_psu_dead_count", self._count_dead_psus(health_status), timestamp)

    def _invalidate_all(self: MccsPrototypeSubrack) -> None:
        """Mark every attribute invalid, so no stale value is readable."""
        for signal_name in _ALL_SIGNALS:
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

    # =====================================================================
    # Attribute declarations
    #
    # These sit below the logic because they are boilerplate. Each value the
    # device reports needs one signal and one attribute built from it, and the
    # two are declared in the same order throughout. Nothing above depends on
    # where they appear, because the poll callbacks reach a signal by the name
    # the mapping tables give, not by referring to it directly. A signal must
    # still be declared before the attribute that is built from it.
    # =====================================================================

    # ---------------------------
    # Signals for the board reads
    # ---------------------------
    _tpm_present: AttrSignal[list[bool]] = AttrSignal[list[bool]]()
    _tpm_on_off: AttrSignal[list[bool]] = AttrSignal[list[bool]]()
    _backplane_temperatures: AttrSignal[list[float]] = AttrSignal[list[float]]()
    _board_temperatures: AttrSignal[list[float]] = AttrSignal[list[float]]()
    _board_current: AttrSignal[list[float]] = AttrSignal[list[float]]()
    _cpld_pll_locked: AttrSignal[bool] = AttrSignal[bool]()
    _power_supply_currents: AttrSignal[list[float]] = AttrSignal[list[float]]()
    _power_supply_fan_speeds: AttrSignal[list[float]] = AttrSignal[list[float]]()
    _power_supply_powers: AttrSignal[list[float]] = AttrSignal[list[float]]()
    _power_supply_voltages: AttrSignal[list[float]] = AttrSignal[list[float]]()
    _subrack_fan_speeds: AttrSignal[list[float]] = AttrSignal[list[float]]()
    _subrack_fan_speeds_percent: AttrSignal[list[float]] = AttrSignal[list[float]]()
    _subrack_fan_modes: AttrSignal[list[int]] = AttrSignal[list[int]]()
    _subrack_max_fan_speeds: AttrSignal[list[float]] = AttrSignal[list[float]]()
    _subrack_pll_locked: AttrSignal[bool] = AttrSignal[bool]()
    _subrack_timestamp: AttrSignal[int] = AttrSignal[int]()
    _tpm_currents: AttrSignal[list[float]] = AttrSignal[list[float]]()
    _tpm_powers: AttrSignal[list[float]] = AttrSignal[list[float]]()
    _tpm_voltages: AttrSignal[list[float]] = AttrSignal[list[float]]()
    _subrack_board_info: AttrSignal[str] = AttrSignal[str]()

    # -----------------------------
    # Signals for the health status
    # -----------------------------
    _internal_voltages_1v1: AttrSignal[float] = AttrSignal[float]()
    _internal_voltages_1v5: AttrSignal[float] = AttrSignal[float]()
    _internal_voltages_2v5: AttrSignal[float] = AttrSignal[float]()
    _internal_voltages_2v8: AttrSignal[float] = AttrSignal[float]()
    _internal_voltages_3v: AttrSignal[float] = AttrSignal[float]()
    _internal_voltages_3v3: AttrSignal[float] = AttrSignal[float]()
    _internal_voltages_5v: AttrSignal[float] = AttrSignal[float]()
    _internal_voltages_arm: AttrSignal[float] = AttrSignal[float]()
    _internal_voltages_core: AttrSignal[float] = AttrSignal[float]()
    _internal_voltages_ddr: AttrSignal[float] = AttrSignal[float]()
    _internal_voltages_powerin: AttrSignal[float] = AttrSignal[float]()
    _internal_voltages_soc: AttrSignal[float] = AttrSignal[float]()
    _psu1_present: AttrSignal[bool] = AttrSignal[bool]()
    _psu2_present: AttrSignal[bool] = AttrSignal[bool]()
    _psu1_power_in: AttrSignal[float] = AttrSignal[float]()
    _psu2_power_in: AttrSignal[float] = AttrSignal[float]()
    _psu1_power_out: AttrSignal[float] = AttrSignal[float]()
    _psu2_power_out: AttrSignal[float] = AttrSignal[float]()
    _psu1_voltage_in: AttrSignal[float] = AttrSignal[float]()
    _psu2_voltage_in: AttrSignal[float] = AttrSignal[float]()
    _psu1_voltage_out: AttrSignal[float] = AttrSignal[float]()
    _psu2_voltage_out: AttrSignal[float] = AttrSignal[float]()
    _psu_dead_count: AttrSignal[int] = AttrSignal[int]()

    # ---------------------------
    # Attributes for board reads
    # ---------------------------
    tpmPresent = attribute_from_signal(
        _tpm_present,
        dtype=(bool,),
        max_dim_x=SubrackData.TPM_BAY_COUNT,
        label="TPM present",
        doc="Whether each TPM bay is occupied.",
    )

    tpmOnOff = attribute_from_signal(
        _tpm_on_off,
        dtype=(bool,),
        max_dim_x=SubrackData.TPM_BAY_COUNT,
        label="TPM on off",
        doc="Whether each TPM bay is powered on.",
    )

    backplaneTemperatures = attribute_from_signal(
        _backplane_temperatures,
        dtype=("DevFloat",),
        max_dim_x=2,
        label="Backplane temperatures",
        unit="Celsius",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Backplane temperatures in degrees Celsius.",
    )

    boardTemperatures = attribute_from_signal(
        _board_temperatures,
        dtype=("DevFloat",),
        max_dim_x=2,
        label="Subrack board temperatures",
        unit="Celsius",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Management board temperatures in degrees Celsius.",
    )

    boardCurrent = attribute_from_signal(
        _board_current,
        dtype=("DevFloat",),
        max_dim_x=1,
        label="Board current",
        unit="Ampere",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Management board current in Amperes.",
    )

    cpldPllLocked = attribute_from_signal(
        _cpld_pll_locked,
        dtype=bool,
        label="CPLD PLL locked",
        doc="Whether the CPLD PLL is locked.",
    )

    powerSupplyCurrents = attribute_from_signal(
        _power_supply_currents,
        dtype=("DevFloat",),
        max_dim_x=2,
        label="power supply currents",
        unit="Ampere",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Power supply output currents in Amperes.",
    )

    powerSupplyFanSpeeds = attribute_from_signal(
        _power_supply_fan_speeds,
        dtype=("DevFloat",),
        max_dim_x=3,
        label="power supply fan speeds",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Power supply fan speeds, as a percentage of the maximum.",
    )

    powerSupplyPowers = attribute_from_signal(
        _power_supply_powers,
        dtype=("DevFloat",),
        max_dim_x=2,
        label="power supply powers",
        unit="Watt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Power supply output powers in Watts.",
    )

    powerSupplyVoltages = attribute_from_signal(
        _power_supply_voltages,
        dtype=("DevFloat",),
        max_dim_x=2,
        label="power supply voltages",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Power supply output voltages in Volts.",
    )

    subrackFanSpeeds = attribute_from_signal(
        _subrack_fan_speeds,
        dtype=("DevFloat",),
        max_dim_x=SubrackData.FAN_COUNT,
        label="subrack fan speeds",
        unit="rpm",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Measured subrack fan speeds in rpm.",
    )

    subrackFanSpeedsPercent = attribute_from_signal(
        _subrack_fan_speeds_percent,
        dtype=("DevFloat",),
        max_dim_x=SubrackData.FAN_COUNT,
        label="subrack fan speeds (%)",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack fan pwm duty cycle setpoints, as a percentage.",
    )

    # This is (int,) rather than (FanMode,) because of pytango issue 483, which
    # prevents an enumerated spectrum attribute from working.
    subrackFanModes = attribute_from_signal(
        _subrack_fan_modes,
        dtype=(int,),
        max_dim_x=SubrackData.FAN_COUNT,
        label="subrack fan modes",
        abs_change=1,
        archive_abs_change=1,
        doc="Subrack fan modes, 0 for manual and 1 for automatic.",
    )

    subrackMaxFanSpeeds = attribute_from_signal(
        _subrack_max_fan_speeds,
        dtype=("DevFloat",),
        max_dim_x=SubrackData.FAN_COUNT,
        label="expected fan speeds at 100% pwm duty",
        unit="rpm",
        max_alarm=9750,  # 150%
        max_warning=8125,  # 125%
        min_alarm="Not specified",  # ignore faults on RAL
        min_warning="Not specified",  # ignore faults on RAL
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack fan speeds estimated at 100% pwm duty, in rpm.",
    )

    subrackPllLocked = attribute_from_signal(
        _subrack_pll_locked,
        dtype=bool,
        label="PLL locked",
        doc="Whether the subrack PLL is locked.",
    )

    subrackTimestamp = attribute_from_signal(
        _subrack_timestamp,
        dtype="DevLong",
        label="Timestamp",
        abs_change=1,
        archive_abs_change=1,
        doc="The subrack board timestamp.",
    )

    tpmCurrents = attribute_from_signal(
        _tpm_currents,
        dtype=("DevFloat",),
        max_dim_x=SubrackData.TPM_BAY_COUNT,
        label="TPM currents",
        unit="Ampere",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Per bay TPM currents in Amperes.",
    )

    tpmPowers = attribute_from_signal(
        _tpm_powers,
        dtype=("DevFloat",),
        max_dim_x=SubrackData.TPM_BAY_COUNT,
        label="TPM powers",
        unit="Watt",
        max_alarm=120.0,
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Per bay TPM powers in Watts.",
    )

    tpmVoltages = attribute_from_signal(
        _tpm_voltages,
        dtype=("DevFloat",),
        max_dim_x=SubrackData.TPM_BAY_COUNT,
        label="TPM voltages",
        unit="Volt",
        min_alarm=11.4,
        max_alarm=12.6,
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Per bay TPM voltages in Volts.",
    )

    subrackBoardInfo = attribute_from_signal(
        _subrack_board_info,
        dtype=str,
        label="Subrack Board Info",
        doc="The subrack board information, as a JSON string.",
    )

    # -------------------------------
    # Attributes for the health status
    # -------------------------------
    internalVoltages1V1 = attribute_from_signal(
        _internal_voltages_1v1,
        dtype="DevDouble",
        label="V_1V1",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack internal 1V1 supply voltage in Volts.",
    )

    internalVoltages1V5 = attribute_from_signal(
        _internal_voltages_1v5,
        dtype="DevDouble",
        label="V_1V5",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack internal 1V5 supply voltage in Volts.",
    )

    internalVoltages2V5 = attribute_from_signal(
        _internal_voltages_2v5,
        dtype="DevDouble",
        label="V_2V5",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack internal 2V5 supply voltage in Volts.",
    )

    internalVoltages2V8 = attribute_from_signal(
        _internal_voltages_2v8,
        dtype="DevDouble",
        label="V_2V8",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack internal 2V8 supply voltage in Volts.",
    )

    internalVoltages3V = attribute_from_signal(
        _internal_voltages_3v,
        dtype="DevDouble",
        label="V_3V",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack internal 3V supply voltage in Volts.",
    )

    internalVoltages3V3 = attribute_from_signal(
        _internal_voltages_3v3,
        dtype="DevDouble",
        label="V_3V3",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack internal 3V3 supply voltage in Volts.",
    )

    internalVoltages5V = attribute_from_signal(
        _internal_voltages_5v,
        dtype="DevDouble",
        label="V_5V",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack internal 5V supply voltage in Volts.",
    )

    internalVoltagesARM = attribute_from_signal(
        _internal_voltages_arm,
        dtype="DevDouble",
        label="V_ARM",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack internal ARM supply voltage in Volts.",
    )

    internalVoltagesCORE = attribute_from_signal(
        _internal_voltages_core,
        dtype="DevDouble",
        label="V_CORE",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack internal CORE supply voltage in Volts.",
    )

    internalVoltagesDDR = attribute_from_signal(
        _internal_voltages_ddr,
        dtype="DevDouble",
        label="V_DDR",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack internal DDR supply voltage in Volts.",
    )

    internalVoltagesPOWERIN = attribute_from_signal(
        _internal_voltages_powerin,
        dtype="DevDouble",
        label="V_POWERIN",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack power input voltage in Volts.",
    )

    internalVoltagesSOC = attribute_from_signal(
        _internal_voltages_soc,
        dtype="DevDouble",
        label="V_SOC",
        unit="Volt",
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="Subrack internal SOC supply voltage in Volts.",
    )

    psu1Present = attribute_from_signal(
        _psu1_present,
        dtype=bool,
        label="Psu1 Present",
        doc="Presence of PSU1.",
    )

    psu2Present = attribute_from_signal(
        _psu2_present,
        dtype=bool,
        label="Psu2 Present",
        doc="Presence of PSU2.",
    )

    psu1PowerIn = attribute_from_signal(
        _psu1_power_in,
        dtype="DevDouble",
        label="PSU1 Input Power",
        unit="Watt",
        max_alarm=600.0,
        max_warning=575.0,
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="PSU1 input power in Watts.",
    )

    psu2PowerIn = attribute_from_signal(
        _psu2_power_in,
        dtype="DevDouble",
        label="PSU2 Input Power",
        unit="Watt",
        max_alarm=600.0,
        max_warning=575.0,
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="PSU2 input power in Watts.",
    )

    psu1PowerOut = attribute_from_signal(
        _psu1_power_out,
        dtype="DevDouble",
        label="PSU1 Output Power",
        unit="Watt",
        max_alarm=1140.0,
        max_warning=600.0,
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="PSU1 output power in Watts.",
    )

    psu2PowerOut = attribute_from_signal(
        _psu2_power_out,
        dtype="DevDouble",
        label="PSU2 Output Power",
        unit="Watt",
        max_alarm=1140.0,
        max_warning=600.0,
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="PSU2 output power in Watts.",
    )

    psu1VoltageIn = attribute_from_signal(
        _psu1_voltage_in,
        dtype="DevDouble",
        label="PSU1 Input Voltage",
        unit="Volt",
        max_alarm=253.00,
        max_warning=240.0,
        min_warning=215.0,
        min_alarm=207.0,
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="PSU1 input voltage in Volts.",
    )

    psu2VoltageIn = attribute_from_signal(
        _psu2_voltage_in,
        dtype="DevDouble",
        label="PSU2 Input Voltage",
        unit="Volt",
        max_alarm=253.00,
        max_warning=240.0,
        min_warning=215.0,
        min_alarm=207.0,
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="PSU2 input voltage in Volts.",
    )

    psu1VoltageOut = attribute_from_signal(
        _psu1_voltage_out,
        dtype="DevDouble",
        label="PSU1 Output Voltage",
        unit="Volt",
        max_alarm=14.0,
        max_warning=13.0,
        min_warning=11.0,
        min_alarm=10.0,
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="PSU1 output voltage in Volts.",
    )

    psu2VoltageOut = attribute_from_signal(
        _psu2_voltage_out,
        dtype="DevDouble",
        label="PSU2 Output Voltage",
        unit="Volt",
        max_alarm=14.0,
        max_warning=13.0,
        min_warning=11.0,
        min_alarm=10.0,
        abs_change=0.1,
        archive_abs_change=0.1,
        doc="PSU2 output voltage in Volts.",
    )

    psuDeadCount = attribute_from_signal(
        _psu_dead_count,
        dtype="DevShort",
        label="Dead PSU Count",
        max_warning=1,
        max_alarm=2,
        abs_change=1,
        archive_abs_change=1,
        doc=(
            "Count of PSUs that are present and receive input voltage but "
            "supply no output voltage."
        ),
    )


# ----------
# Run server
# ----------


def subrack_factory(
    web_hardware_client=WebHardwareClient, subrack=Subrack, subrack_poller=SubrackPoller
):
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
