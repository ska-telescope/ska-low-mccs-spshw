# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module provides a orchestrator for the tile component manager."""
from __future__ import annotations

import enum
import importlib.resources
import logging
import threading
from typing import Any, Callable, NoReturn, Optional, Tuple, Union, cast

import yaml
from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import CommunicationStatus, PowerState
from ska_tango_base.executor import TaskStatus


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

    SUBRACK_COMMS_NOT_ESTABLISHED = 5
    """Communications with the subrack device is not established."""

    SUBRACK_COMMS_ESTABLISHED = 6
    """Communications with the subrack device is established."""

    SUBRACK_SAYS_TPM_UNKNOWN = 7
    """The subrack reports that power state of the TPM is unknown."""

    SUBRACK_SAYS_TPM_NO_SUPPLY = 8
    """
    The subrack reports that the TPM has no power supply.

    That is, the subrack itself is off. Thus, the TPM is off, and it
    cannot be commanded on
    """

    SUBRACK_SAYS_TPM_OFF = 9
    """
    The subrack reports that the TPM is off.

    However the subrack itself is on, so the TPM can be commanded on.
    """

    SUBRACK_SAYS_TPM_ON = 10
    """The subrack reports that the TPM is powered on."""

    TPM_COMMS_NOT_ESTABLISHED = 11
    """Communications with the TPM is not established."""

    TPM_COMMS_ESTABLISHED = 12
    """Communications with the TPM is established."""


StateTupleType = Union[
    Tuple[CommunicationStatus],
    Tuple[
        CommunicationStatus,
        Optional[bool],
        PowerState,
    ],
    Tuple[
        CommunicationStatus,
        Optional[bool],
        PowerState,
        CommunicationStatus,
    ],
]


StateStimulusTupleType = Union[
    Tuple[Stimulus, CommunicationStatus],
    Tuple[
        Stimulus,
        CommunicationStatus,
        Optional[bool],
        PowerState,
    ],
    Tuple[
        Stimulus,
        CommunicationStatus,
        Optional[bool],
        PowerState,
        CommunicationStatus,
    ],
]


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

    RULES: Optional[
        dict[tuple, list]
    ] = None  # This will be populated the first time the class gets instantiated.

    @classmethod
    def _load_rules(cls) -> dict[tuple, list]:
        # Do this slow I/O once for the whole class, instead of doing it every time we
        # initialise an instance. (We can't hardcode a relative path here, because
        # sphinx-build imports this with a different current directory.)
        if cls.RULES is None:
            rules_string = importlib.resources.read_text(
                __package__, "orchestration_rules.yaml"
            )
            cls.RULES = yaml.load(rules_string, Loader=yaml.Loader) or {}
            # we've no logger so there's no point catching any exceptions.
        return cls.RULES

    def __init__(
        self: TileOrchestrator,
        start_communicating_with_subrack_callback: Callable[[], None],
        stop_communicating_with_subrack_callback: Callable[[], None],
        start_communicating_with_tpm_callback: Callable[[], None],
        stop_communicating_with_tpm_callback: Callable[[], None],
        turn_tpm_off_callback: Callable[[], Any],
        turn_tpm_on_callback: Callable[[], Any],
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[[dict[str, Any]], None],
        logger: logging.Logger,
        _initial_state: Optional[StateTupleType] = None,
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
        :param communication_state_changed_callback: callback to be
            called in order to indicate a change in the status of
            communication between the component manager and its TPM
        :param component_state_changed_callback: callback to be
            called when the component state changes
        :param logger: a logger to be used by this orchestrator.
        :param _initial_state: set the initial state of this tile
            orchestrator. This is provided for unit testing purposes
            and should not be used outside of unit tests.
        """
        self.__lock = threading.RLock()

        self._start_communicating_with_subrack = (
            start_communicating_with_subrack_callback
        )
        self._stop_communicating_with_subrack_callback = (
            stop_communicating_with_subrack_callback
        )
        self._start_communicating_with_tpm = start_communicating_with_tpm_callback
        self._stop_communicating_with_tpm_callback = (
            stop_communicating_with_tpm_callback
        )

        self._turn_tpm_off = turn_tpm_off_callback
        self._turn_tpm_on = turn_tpm_on_callback

        self._communication_state_changed_callback = (
            communication_state_changed_callback
        )
        self._component_state_changed_callback = component_state_changed_callback

        self._logger = logger

        self._subrack_communication_state = (
            _initial_state[0]
            if _initial_state is not None and len(_initial_state) > 0
            else CommunicationStatus.DISABLED
        )
        self._operator_desire = (
            _initial_state[1]  # type: ignore[misc]
            if _initial_state is not None and len(_initial_state) > 1
            else None
        )
        self._tpm_power_state = (
            _initial_state[2]  # type: ignore[misc]
            if _initial_state is not None and len(_initial_state) > 2
            else PowerState.UNKNOWN
        )
        self._tpm_communication_state = (
            _initial_state[3]  # type: ignore[misc]
            if _initial_state is not None and len(_initial_state) > 3
            else CommunicationStatus.DISABLED
        )
        self._tpm_power_state_on = PowerState.UNKNOWN  # default state if turned on

        self._decision_table: dict[
            StateStimulusTupleType, list[Callable[[], Optional[ResultCode]]]
        ] = {}

        for state, actions in self._load_rules().items():
            action_calls = [getattr(self, f"_{action}") for action in actions]
            if len(state) == 2:
                self._decision_table[
                    Stimulus[state[0]],
                    CommunicationStatus[state[1]],
                ] = action_calls
            elif len(state) == 4:
                self._decision_table[
                    (
                        Stimulus[state[0]],
                        CommunicationStatus[state[1]],
                        state[2],
                        PowerState[state[3]],
                    )
                ] = action_calls
            else:
                self._decision_table[
                    (
                        Stimulus[state[0]],
                        CommunicationStatus[state[1]],
                        state[2],
                        PowerState[state[3]],
                        CommunicationStatus[state[4]],
                    )
                ] = action_calls

    def desire_online(self: TileOrchestrator) -> None:
        """Advise that the operator desires the component manager to be online."""
        with self.__lock:
            self._act(Stimulus.DESIRE_ONLINE)

    def desire_offline(self: TileOrchestrator) -> None:
        """Advise that the operator desires the component manager to be offline."""
        with self.__lock:
            self._act(Stimulus.DESIRE_OFFLINE)

    def desire_on(
        self: TileOrchestrator,
        task_callback: Optional[Callable] = None,
        task_abort_event: threading.Event = None,
    ) -> None:
        """
        Advise that the operator desires the TPM to be on.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None

        :raises Exception: if the TileOrchestrator encounters an
            unhandled case
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        try:
            with self.__lock:
                self._tpm_power_state_on = PowerState.ON
                result_code = cast(ResultCode, self._act(Stimulus.DESIRE_ON))
        except Exception as exc:
            if task_callback is not None:
                task_callback(status=TaskStatus.FAILED, exception=exc)
            raise exc

        if task_callback:
            if result_code == ResultCode.OK:
                task_callback(status=TaskStatus.COMPLETED, result="Tile on completed")
            else:
                task_callback(status=TaskStatus.FAILED, result="Tile on failed")

    def desire_off(
        self: TileOrchestrator,
        task_callback: Optional[Callable] = None,
        task_abort_event: threading.Event = None,
    ) -> None:
        """
        Advise that the operator desires the TPM to be off.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None

        :raises Exception: if the TileOrchestrator encounters an
            unhandled case
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        try:
            with self.__lock:
                result_code = cast(ResultCode, self._act(Stimulus.DESIRE_OFF))
        except Exception as exc:
            if task_callback is not None:
                task_callback(status=TaskStatus.FAILED, exception=exc)
            raise exc
        if task_callback:
            if result_code == ResultCode.OK:
                task_callback(status=TaskStatus.COMPLETED, result="Tile off completed")
            else:
                task_callback(status=TaskStatus.FAILED, result="Tile off failed")

    def desire_standby(
        self: TileOrchestrator,
        task_callback: Optional[Callable] = None,
        task_abort_event: threading.Event = None,
    ) -> None:
        """
        Advise that the operator desires the TPM to be standby.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None

        :raises Exception: if the TileOrchestrator encounters an
            unhandled case
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        try:
            with self.__lock:
                self._tpm_power_state_on = PowerState.STANDBY
                result_code = cast(ResultCode, self._act(Stimulus.DESIRE_ON))
        except Exception as exc:
            if task_callback is not None:
                task_callback(status=TaskStatus.FAILED, exception=exc)
            raise exc
        if task_callback:
            if result_code == ResultCode.OK:
                task_callback(
                    status=TaskStatus.COMPLETED, result="Tile standby completed"
                )
            else:
                task_callback(status=TaskStatus.FAILED, result="Tile standby failed")

    def update_subrack_communication_state(
        self: TileOrchestrator,
        communication_state: CommunicationStatus,
    ) -> None:
        """
        Update status of communications between the component manager and the subrack.

        :param communication_state: the new current status of
            communications between the component manager and the
            subrack.

        :raises NotImplementedError: if the provided communication status
            is unsupported.
        """
        with self.__lock:
            if communication_state == CommunicationStatus.DISABLED:
                pass
                # This will only occur as a result of the orchestrator calling
                # stop_communicating_with_subrack, which is synchronous and
                # deterministic, so the orchestrator already knows that communication
                # has been disabled.
            elif communication_state == CommunicationStatus.NOT_ESTABLISHED:
                self._act(Stimulus.SUBRACK_COMMS_NOT_ESTABLISHED)
            elif communication_state == CommunicationStatus.ESTABLISHED:
                self._act(Stimulus.SUBRACK_COMMS_ESTABLISHED)
            else:
                raise NotImplementedError()

    def update_tpm_communication_state(
        self: TileOrchestrator,
        communication_state: CommunicationStatus,
    ) -> None:
        """
        Update status of communications between the component manager and the TPM.

        :param communication_state: the new current status of
            communications between the component manager and the TPM.

        :raises NotImplementedError: if the provided communication status
            is unsupported.
        """
        with self.__lock:
            if communication_state == CommunicationStatus.DISABLED:
                pass
                # This will only occur as a result of the orchestrator calling
                # stop_communicating_with_tpm, which is synchronous and deterministic,
                # so the orchestrator already knows that # communication has been
                # disabled.
            elif communication_state == CommunicationStatus.NOT_ESTABLISHED:
                self._act(Stimulus.TPM_COMMS_NOT_ESTABLISHED)
            elif communication_state == CommunicationStatus.ESTABLISHED:
                self._act(Stimulus.TPM_COMMS_ESTABLISHED)
            else:
                raise NotImplementedError()

    def update_tpm_power_state(
        self: TileOrchestrator,
        power_state: PowerState,
    ) -> None:
        """
        Update the current power state of the TPM.

        :param power_state: the current power state of the TPM.

        :raises NotImplementedError: if the provided power state is
            unsupported.
        """
        with self.__lock:
            if power_state == PowerState.UNKNOWN:
                self._act(Stimulus.SUBRACK_SAYS_TPM_UNKNOWN)
            elif power_state == PowerState.NO_SUPPLY:
                self._act(Stimulus.SUBRACK_SAYS_TPM_NO_SUPPLY)
            elif power_state == PowerState.OFF:
                self._act(Stimulus.SUBRACK_SAYS_TPM_OFF)
            elif power_state == PowerState.ON:
                self._act(Stimulus.SUBRACK_SAYS_TPM_ON)
            else:
                raise NotImplementedError()

    def _get_state(self: TileOrchestrator) -> list:
        state: list[Any] = [self._subrack_communication_state]
        if self._subrack_communication_state == CommunicationStatus.DISABLED:
            return state

        state = state + [self._operator_desire, self._tpm_power_state]
        if self._tpm_power_state in [
            PowerState.NO_SUPPLY,
            PowerState.OFF,
        ]:
            return state

        state = state + [self._tpm_communication_state]
        return state

    def _act(self: TileOrchestrator, stimulus: Stimulus) -> Optional[ResultCode]:
        key = cast(StateStimulusTupleType, (stimulus,) + tuple(self._get_state()))
        try:
            actions = self._decision_table[key]
        except KeyError:
            self._logger.error(f"TileOrchestrator encountered unhandled case: {key}")
            raise
        self._logger.warning(f"TileOrchestrator: {key} ==> {actions}")
        # print(f"TileOrchestrator: {key} ==> {actions}")

        result_code = None
        for action in actions:
            action_result_code = action()
            if result_code is None:
                result_code = action_result_code
        return result_code

    def _raise_cannot_turn_off_on_when_offline(
        self: TileOrchestrator,
    ) -> NoReturn:
        raise ConnectionError("TPM cannot be turned off / on when not online.")

    def _report_communication_disabled(self: TileOrchestrator) -> None:
        self._communication_state_changed_callback(CommunicationStatus.DISABLED)

    def _report_communication_not_established(self: TileOrchestrator) -> None:
        self._communication_state_changed_callback(CommunicationStatus.NOT_ESTABLISHED)

    def _report_communication_established(self: TileOrchestrator) -> None:
        self._communication_state_changed_callback(CommunicationStatus.ESTABLISHED)

    def _report_tpm_no_power_supply(
        self: TileOrchestrator,
    ) -> None:
        self._tpm_power_state = PowerState.NO_SUPPLY
        self._component_state_changed_callback({"power_state": PowerState.OFF})

    def _report_tpm_off(self: TileOrchestrator) -> None:
        self._tpm_power_state = PowerState.OFF
        self._component_state_changed_callback({"power_state": PowerState.OFF})

    def _report_tpm_on(self: TileOrchestrator) -> None:
        self._tpm_power_state = PowerState.ON
        self._component_state_changed_callback({"power_state": PowerState.ON})

    def _report_tpm_power_unknown(self: TileOrchestrator) -> None:
        self._tpm_power_state = PowerState.UNKNOWN
        self._component_state_changed_callback({"power_state": PowerState.UNKNOWN})

    def _set_desired_off(self: TileOrchestrator) -> ResultCode:
        self._operator_desire = False
        return ResultCode.QUEUED

    def _set_desired_on(self: TileOrchestrator) -> ResultCode:
        self._operator_desire = True
        return ResultCode.QUEUED

    def _set_no_desire(self: TileOrchestrator) -> None:
        self._operator_desire = None

    def _stop_communicating_with_subrack(
        self: TileOrchestrator,
    ) -> None:
        self._subrack_communication_state = CommunicationStatus.DISABLED
        self._stop_communicating_with_subrack_callback()

    def _set_subrack_communication_established(
        self: TileOrchestrator,
    ) -> None:
        self._subrack_communication_state = CommunicationStatus.ESTABLISHED

    def _set_subrack_communication_not_established(
        self: TileOrchestrator,
    ) -> None:
        self._subrack_communication_state = CommunicationStatus.NOT_ESTABLISHED

    def _stop_communicating_with_tpm(self: TileOrchestrator) -> None:
        self._tpm_communication_state = CommunicationStatus.DISABLED
        self._stop_communicating_with_tpm_callback()

    def _set_tpm_communication_not_established(self: TileOrchestrator) -> None:
        self._tpm_communication_state = CommunicationStatus.NOT_ESTABLISHED

    def _set_tpm_communication_established(self: TileOrchestrator) -> None:
        self._tpm_communication_state = CommunicationStatus.ESTABLISHED
