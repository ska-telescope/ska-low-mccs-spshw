"""This module provides a orchestrator for the tile component manager."""
from __future__ import annotations

import enum
import logging
import threading
from typing import Any, Callable, Optional, Tuple
import yaml

from ska_tango_base.control_model import PowerMode

from ska_low_mccs.component import CommunicationStatus, ExtendedPowerMode


@enum.unique
class OperatorDesire(enum.IntEnum):
    """
    An enumerated type for the operator's desired state for the tile.

    TODO: This is only public because it is exposed for testing purposes
    through the API, so sphinx needs it to be public when building the
    docs. We should refactor so that we can hide this.
    """

    OFFLINE = 1
    """The operator wants this device not to monitor its component."""

    ONLINE = 2
    """The operator wants this device to monitor its component"""

    OFF = 3
    """The operator wants this device to turn its component off (implies online)."""

    ON = 4
    """The operator wants this device to turn its component on (implies online)."""


@enum.unique
class Stimulus(enum.IntEnum):
    """
    An enumerated type for a stimulus upon which this orchestrator acts.

    TODO: This is only public because it is exposed for testing purposes
    through the API, so sphinx needs it to be public when building the
    docs. We should refactor so that we can hide this.
    """

    DESIRE_OFFLINE = 1
    """The tile device has been asked to start communicating with the TPM."""

    DESIRE_ONLINE = 2
    """The tile device has been asked to stop communicating with the TPM."""

    DESIRE_ON = 3
    """The tile device has been asked to turn on the TPM."""

    DESIRE_OFF = 4
    """The tile device has been asked to turn off the TPM."""

    SUBRACK_COMMS_DISABLED = 5
    """Communications with the subrack device is disabled."""

    SUBRACK_COMMS_NOT_ESTABLISHED = 6
    """Communications with the subrack device is not established."""

    SUBRACK_COMMS_ESTABLISHED = 7
    """Communications with the subrack device is established."""

    SUBRACK_SAYS_TPM_UNKNOWN = 8
    """The subrack reports that power mode of the TPM is unknown."""

    SUBRACK_SAYS_TPM_NO_SUPPLY = 9
    """
    The subrack reports that the TPM has no power supply.

    That is, the subrack itself is off. Thus, the TPM is off, and it
    cannot be commanded on
    """

    SUBRACK_SAYS_TPM_OFF = 10
    """
    The subrack reports that the TPM is off.

    However the subrack itself is on, so the TPM can be commanded on.
    """

    SUBRACK_SAYS_TPM_ON = 11
    """The subrack reports that the TPM is powered on."""

    TPM_COMMS_DISABLED = 12
    """Communications with the TPM is disabled."""

    TPM_COMMS_NOT_ESTABLISHED = 13
    """Communications with the TPM is not established."""

    TPM_COMMS_ESTABLISHED = 16
    """Communications with the TPM is established."""


class TileOrchestrator:
    """
    A orchestrator for the Tile component manager.

    Orchestrators receive stimuli from the environment of their
    component manager, and decide on actions to take in response. They
    are the "brains" of the component manager.

    In this case, the stimuli consist of:

    * the actions of the operator (such as desiring the TPM to be turned
      on.
    * changes to the state of the TPM or our communications with it.
    * changes to the state of the subrack that supplies power to the
      TPM, or our communications with it.

    The actions this orchestrator can take in response to these stimuli
    include:

    * Establishing or breaking off communication with the subrack
    * Establishing or breaking off communication with the TPM
    * Telling the subrack to turn the TPM off / on
    * Calling callbacks that update the monitored state of the component

    The specific actions are defined in a YAML file as follows:

    .. literalinclude:: ../../../../src/ska_low_mccs/tile/orchestration_rules.yaml
        :language: yaml
    """

    RULES_PATH = "src/ska_low_mccs/tile/orchestration_rules.yaml"
    """Path to the rules file that specifies behaviour of this choreographer."""

    def __init__(
        self: TileOrchestrator,
        start_communicating_with_subrack_callback: Callable[[], None],
        stop_communicating_with_subrack_callback: Callable[[], None],
        start_communicating_with_tpm_callback: Callable[[], None],
        stop_communicating_with_tpm_callback: Callable[[], None],
        turn_tpm_off_callback: Callable[[], Any],
        turn_tpm_on_callback: Callable[[], Any],
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        power_mode_changed_callback: Callable[[Optional[PowerMode]], None],
        fault_callback: Callable[[Optional[bool]], None],
        logger: logging.Logger,
        _initial_state: Optional[
            Tuple[
                OperatorDesire,
                CommunicationStatus,
                ExtendedPowerMode,
                CommunicationStatus,
            ]
        ] = None,
    ) -> None:
        """
        Initialise a new instance.

        :param start_communicating_with_subrack_callback: callback to be
            called in order to initiate communication with the subrack.
        :param stop_communicating_with_subrack_callback: callback to be
            called in order to break off communication with the subrack.
        :param start_communicating_with_tpm_callback: callback to be
            called in order to initiate communication with the TPM.
        :param stop_communicating_with_tpm_callback: callback to be
            called in order to break off communication with the TPM.
        :param turn_tpm_off_callback: callback to be called in order to
            turn off the TPM
        :param turn_tpm_on_callback: callback to be called in order to
            turn on the TPM
        :param communication_status_changed_callback: callback to be
            called in order to indicate a change in the status of
            communication between the component manager and its TPM
        :param power_mode_changed_callback: callback to be called in
            order to indicate a change in the power mode of the TPM
        :param fault_callback: callback to be called in order to
            indicate a change in the fault status of the TPM
        :param logger: a logger to be used by this orchestrator.
        :param _initial_state: set the initial state of this tile
            orchestrator. This is provided for unit testing purposes
            and should not be used outside of unit tests.

        :raises yaml.YAMLError: if the configuration couldn't be loaded
            from file.
        """
        self.__lock = threading.RLock()

        self._start_communicating_with_subrack_callback = (
            start_communicating_with_subrack_callback
        )
        self._stop_communicating_with_subrack_callback = (
            stop_communicating_with_subrack_callback
        )
        self._start_communicating_with_tpm_callback = (
            start_communicating_with_tpm_callback
        )
        self._stop_communicating_with_tpm_callback = (
            stop_communicating_with_tpm_callback
        )

        self._turn_tpm_off_callback = turn_tpm_off_callback
        self._turn_tpm_on_callback = turn_tpm_on_callback

        self._communication_status_changed_callback = (
            communication_status_changed_callback
        )
        self._power_mode_changed_callback = power_mode_changed_callback
        self._fault_callback = fault_callback

        self._logger = logger

        (
            self._operator_desire,
            self._subrack_communication_status,
            self._tpm_power_mode,
            self._tpm_communication_status,
        ) = _initial_state or (
            OperatorDesire.OFFLINE,
            CommunicationStatus.DISABLED,
            ExtendedPowerMode.UNKNOWN,
            CommunicationStatus.DISABLED,
        )

        with open(self.RULES_PATH, "r") as stream:
            try:
                rules = yaml.load(stream, Loader=yaml.Loader) or {}
            except yaml.YAMLError as exception:
                self._logger.error(
                    f"Tile orchestrator could not load configuration: {exception}."
                )
                raise

        self._decision_table = {
            (
                OperatorDesire[state[0]],
                CommunicationStatus[state[1]],
                ExtendedPowerMode[state[2]],
                CommunicationStatus[state[3]],
                Stimulus[state[4]],
            ): getattr(self, f"_{action}")
            for state, action in rules.items()
        }

    def desire_online(self: TileOrchestrator) -> None:
        """Advise that the operator desires the component manager to be online."""
        with self.__lock:
            self._act(Stimulus.DESIRE_ONLINE)

    def desire_offline(self: TileOrchestrator) -> None:
        """Advise that the operator desires the component manager to be offline."""
        with self.__lock:
            self._act(Stimulus.DESIRE_OFFLINE)

    def desire_on(self: TileOrchestrator) -> None:
        """Advise that the operator desires the TPM to be on."""
        with self.__lock:
            self._act(Stimulus.DESIRE_ON)

    def desire_off(self: TileOrchestrator) -> None:
        """Advise that the operator desires the TPM to be off."""
        with self.__lock:
            self._act(Stimulus.DESIRE_OFF)

    def update_subrack_communication_status(
        self: TileOrchestrator,
        communication_status: CommunicationStatus,
    ) -> None:
        """
        Update status of communications between the component manager and the subrack.

        :param communication_status: the new current status of
            communications between the component manager and the
            subrack.

        :raises NotImplementedError: if the provided communication status
            is unsupported.
        """
        with self.__lock:
            if communication_status == CommunicationStatus.DISABLED:
                self._act(Stimulus.SUBRACK_COMMS_DISABLED)
            elif communication_status == CommunicationStatus.NOT_ESTABLISHED:
                self._act(Stimulus.SUBRACK_COMMS_NOT_ESTABLISHED)
            elif communication_status == CommunicationStatus.ESTABLISHED:
                self._act(Stimulus.SUBRACK_COMMS_ESTABLISHED)
            else:
                raise NotImplementedError()

    def update_tpm_communication_status(
        self: TileOrchestrator,
        communication_status: CommunicationStatus,
    ) -> None:
        """
        Update status of communications between the component manager and the TPM.

        :param communication_status: the new current status of
            communications between the component manager and the TPM.

        :raises NotImplementedError: if the provided communication status
            is unsupported.
        """
        with self.__lock:
            if communication_status == CommunicationStatus.DISABLED:
                self._act(Stimulus.TPM_COMMS_DISABLED)
            elif communication_status == CommunicationStatus.NOT_ESTABLISHED:
                self._act(Stimulus.TPM_COMMS_NOT_ESTABLISHED)
            elif communication_status == CommunicationStatus.ESTABLISHED:
                self._act(Stimulus.TPM_COMMS_ESTABLISHED)
            else:
                raise NotImplementedError()

    def update_tpm_power_mode(
        self: TileOrchestrator,
        power_mode: ExtendedPowerMode,
    ) -> None:
        """
        Update the current power mode of the TPM.

        :param power_mode: the current power mode of the TPM.

        :raises NotImplementedError: if the provided power mode is
            unsupported.
        """
        with self.__lock:
            if power_mode == ExtendedPowerMode.UNKNOWN:
                self._act(Stimulus.SUBRACK_SAYS_TPM_UNKNOWN)
            elif power_mode == ExtendedPowerMode.NO_SUPPLY:
                self._act(Stimulus.SUBRACK_SAYS_TPM_NO_SUPPLY)
            elif power_mode == ExtendedPowerMode.OFF:
                self._act(Stimulus.SUBRACK_SAYS_TPM_OFF)
            elif power_mode == ExtendedPowerMode.ON:
                self._act(Stimulus.SUBRACK_SAYS_TPM_ON)
            else:
                raise NotImplementedError()

    def _act(self: TileOrchestrator, stimulus: Stimulus) -> None:
        key = (
            self._operator_desire,
            self._subrack_communication_status,
            self._tpm_power_mode,
            self._tpm_communication_status,
            stimulus,
        )
        try:
            action = self._decision_table[key]
        except KeyError:
            self._logger.error(f"TileOrchestrator encountered unhandled case: {key}")
            raise
        self._logger.debug(f"TileOrchestrator: {key} ==> {action}")
        action()

    def _start_communicating_with_subrack(self: TileOrchestrator) -> None:
        self._operator_desire = OperatorDesire.ONLINE
        self._subrack_communication_status = CommunicationStatus.NOT_ESTABLISHED

        self._communication_status_changed_callback(CommunicationStatus.NOT_ESTABLISHED)
        self._start_communicating_with_subrack_callback()

    def _stop_communicating_when_tpm_communication_not_established(
        self: TileOrchestrator,
    ) -> None:
        self._operator_desire = OperatorDesire.OFFLINE

        self._communication_status_changed_callback(CommunicationStatus.DISABLED)
        self._power_mode_changed_callback(None)
        self._fault_callback(None)

        self._stop_communicating_with_subrack_callback()

    def _stop_communicating_when_tpm_communication_established(
        self: TileOrchestrator,
    ) -> None:
        self._operator_desire = OperatorDesire.OFFLINE

        self._communication_status_changed_callback(CommunicationStatus.DISABLED)
        self._power_mode_changed_callback(None)
        self._fault_callback(None)

        self._stop_communicating_with_tpm_callback()
        self._stop_communicating_with_subrack_callback()

    def _do_nothing(self: TileOrchestrator) -> None:
        pass

    def _set_subrack_communication_established(
        self: TileOrchestrator,
    ) -> None:
        self._subrack_communication_status = CommunicationStatus.ESTABLISHED
        self._communication_status_changed_callback(CommunicationStatus.ESTABLISHED)

    def _set_subrack_communication_established_and_report_tpm_power_unknown(
        self: TileOrchestrator,
    ) -> None:
        self._subrack_communication_status = CommunicationStatus.ESTABLISHED
        self._tpm_power_mode = ExtendedPowerMode.UNKNOWN

        self._communication_status_changed_callback(CommunicationStatus.ESTABLISHED)
        self._power_mode_changed_callback(PowerMode.UNKNOWN)

    def _set_subrack_communication_established_and_report_tpm_no_power_supply(
        self: TileOrchestrator,
    ) -> None:
        self._subrack_communication_status = CommunicationStatus.ESTABLISHED
        self._tpm_power_mode = ExtendedPowerMode.NO_SUPPLY

        self._communication_status_changed_callback(CommunicationStatus.ESTABLISHED)
        self._power_mode_changed_callback(PowerMode.OFF)

    def _set_subrack_communication_established_and_report_tpm_off(
        self: TileOrchestrator,
    ) -> None:
        self._subrack_communication_status = CommunicationStatus.ESTABLISHED
        self._tpm_power_mode = ExtendedPowerMode.OFF

        self._communication_status_changed_callback(CommunicationStatus.ESTABLISHED)
        self._power_mode_changed_callback(PowerMode.OFF)

    def _set_subrack_communication_established_and_report_tpm_on_and_establish_tpm_communication(
        self: TileOrchestrator,
    ) -> None:
        self._subrack_communication_status = CommunicationStatus.ESTABLISHED
        self._tpm_power_mode = ExtendedPowerMode.ON

        self._power_mode_changed_callback(PowerMode.ON)
        self._start_communicating_with_tpm_callback()

    def _set_subrack_communication_disabled(self: TileOrchestrator) -> None:
        self._subrack_communication_status = CommunicationStatus.DISABLED
        self._tpm_power_mode = ExtendedPowerMode.UNKNOWN
        self._power_mode_changed_callback(PowerMode.UNKNOWN)

    def _report_tpm_power_unknown(self: TileOrchestrator) -> None:
        self._tpm_power_mode = ExtendedPowerMode.UNKNOWN
        self._power_mode_changed_callback(PowerMode.UNKNOWN)
        # If we have established communication with our TPM, let's not
        # break if off yet -- this might just be a network issue between
        # the subrack Tango device and its subrack hardware.

    def _report_tpm_no_power_supply_when_tpm_communication_disabled(
        self: TileOrchestrator,
    ) -> None:
        self._tpm_power_mode = ExtendedPowerMode.NO_SUPPLY
        self._power_mode_changed_callback(PowerMode.OFF)

    def _report_tpm_no_power_supply_and_disable_tpm_communication(
        self: TileOrchestrator,
    ) -> None:
        self._tpm_power_mode = ExtendedPowerMode.NO_SUPPLY
        self._power_mode_changed_callback(PowerMode.OFF)
        self._stop_communicating_with_tpm_callback()

    def _report_tpm_off_when_tpm_communication_disabled(self: TileOrchestrator) -> None:
        self._tpm_power_mode = ExtendedPowerMode.OFF
        self._power_mode_changed_callback(PowerMode.OFF)

    def _report_tpm_off_and_disable_tpm_communication(self: TileOrchestrator) -> None:
        self._tpm_power_mode = ExtendedPowerMode.OFF
        self._power_mode_changed_callback(PowerMode.OFF)
        self._stop_communicating_with_tpm_callback()

    def _report_tpm_off_and_turn_tpm_on(self: TileOrchestrator) -> None:
        self._tpm_power_mode = ExtendedPowerMode.OFF
        self._operator_desire = OperatorDesire.ONLINE
        self._power_mode_changed_callback(PowerMode.OFF)
        return self._turn_tpm_on_callback()

    def _report_tpm_on_and_establish_tpm_communication(self: TileOrchestrator) -> None:
        self._tpm_power_mode = ExtendedPowerMode.ON
        self._power_mode_changed_callback(PowerMode.ON)
        self._start_communicating_with_tpm_callback()

    def _set_tpm_communication_disabled(self: TileOrchestrator) -> None:
        self._tpm_communication_status = CommunicationStatus.DISABLED
        # don't set communication status to disabled; this is now determined by status
        # of subrack communication, which is still ESTABLISHED

    def _set_tpm_communication_not_established(self: TileOrchestrator) -> None:
        self._tpm_communication_status = CommunicationStatus.NOT_ESTABLISHED
        self._communication_status_changed_callback(CommunicationStatus.NOT_ESTABLISHED)

    def _set_tpm_communication_established(self: TileOrchestrator) -> None:
        self._tpm_communication_status = CommunicationStatus.ESTABLISHED
        self._communication_status_changed_callback(CommunicationStatus.ESTABLISHED)

    def _set_desired_on(self: TileOrchestrator) -> None:
        self._operator_desire = OperatorDesire.ON

    def _turn_tpm_on(self: TileOrchestrator) -> None:
        self._operator_desire = OperatorDesire.ONLINE
        return self._turn_tpm_on_callback()

    def _turn_tpm_off(self: TileOrchestrator) -> None:
        self._operator_desire = OperatorDesire.ONLINE
        return self._turn_tpm_off_callback()
