# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements polling management for a PaSD bus."""

import logging
import time
from typing import Any, Callable, Iterator, Optional, Sequence

from .tpm_status import TpmStatus


def off_tpm_read_request_iterator() -> Iterator[str]:
    """
    Return an iterator that says what attributes should be read next on the FNDH.

    It starts by reading static information attributes,
    then moves on to writable attributes that are otherwise static,
    and then loops forever, alternating between status attributes and port attributes.

    :yields: the name of an attribute group to be read from the device.
    """
    while True:
        yield "CHECK_CPLD_COMMS"
        yield "CONNECT"


def unconnected_tpm_read_request_iterator() -> Iterator[str]:
    """
    Return an iterator that says what attributes should be read next on the FNDH.

    It starts by reading static information attributes,
    then moves on to writable attributes that are otherwise static,
    and then loops forever, alternating between status attributes and port attributes.

    :yields: the name of an attribute group to be read from the device.
    """
    while True:
        yield "CHECK_CPLD_COMMS"
        yield "CONNECT"


def unknown_tpm_read_request_iterator() -> Iterator[str]:
    """
    Return an iterator that says what attributes should be read next on the FNDH.

    It starts by reading static information attributes,
    then moves on to writable attributes that are otherwise static,
    and then loops forever, alternating between status attributes and port attributes.

    :yields: the name of an attribute group to be read from the device.
    """
    while True:
        yield "CHECK_CPLD_COMMS"
        yield "CONNECT"


def unprogrammed_tpm_read_request_iterator() -> Iterator[str]:
    """
    Return an iterator that says what attributes should be read next on the FNDH.

    It starts by reading static information attributes,
    then moves on to writable attributes that are otherwise static,
    and then loops forever, alternating between status attributes and port attributes.

    :yields: the name of an attribute group to be read from the device.
    """
    while True:
        yield "CHECK_CPLD_COMMS"
        yield "CSP_ROUNDING"
        yield "CONNECT"


def programmed_tpm_read_request_iterator() -> Iterator[str]:
    """
    Return an iterator that says what attributes should be read next on the FNDH.

    It starts by reading static information attributes,
    then moves on to writable attributes that are otherwise static,
    and then loops forever, alternating between status attributes and port attributes.

    :yields: the name of an attribute group to be read from the device.
    """
    while True:
        yield "CHECK_CPLD_COMMS"
        yield "CSP_ROUNDING"
        yield "CHANNELISER_ROUNDING"
        yield "IS_PROGRAMMED"
        yield "HEALTH_STATUS"
        yield "PLL_LOCKED"


def initialised_tpm_read_request_iterator() -> Iterator[str]:
    """
    Return an iterator that says what attributes should be read next on the FNDH.

    It starts by reading static information attributes,
    then moves on to writable attributes that are otherwise static,
    and then loops forever, alternating between status attributes and port attributes.

    :yields: the name of an attribute group to be read from the device.
    """
    while True:
        yield "CHECK_CPLD_COMMS"
        yield "CSP_ROUNDING"
        yield "CHANNELISER_ROUNDING"
        yield "IS_PROGRAMMED"
        yield "HEALTH_STATUS"
        yield "PLL_LOCKED"
        yield "HEALTH_STATUS"
        yield "ADC_RMS"
        yield "PLL_LOCKED"
        yield "PENDING_DATA_REQUESTS"
        yield "PPS_DELAY"
        yield "PPS_DELAY_CORRECTION"
        yield "IS_BEAMFORMER_RUNNING"
        yield "FPGA_REFERENCE_TIME"
        yield "PHASE_TERMINAL_COUNT"
        yield "PREADU_LEVELS"
        yield "STATIC_DELAYS"
        yield "STATION_ID"
        yield "TILE_ID"
        yield "BEAMFORMER_TABLE"


class TileRequestProvider:
    """
    A class that determines the next communication with the PaSD, across all devices.

    It ensures that:

    * a certain number of ticks are guaranteed to have passed between
      communications with any single device.

    * commands get executed as promptly as possible

    * device attributes are polled as frequently as possible,
      given the above constraints
    """

    def __init__(self) -> None:
        """
        Initialise a new instance.

        :param min_ticks: minimum number of ticks between communications
            with any given device
        :param logger: a logger.
        """
        self._programmed_tpm_read_request_iterator = (
            programmed_tpm_read_request_iterator()
        )
        self._initialised_tpm_read_request_iterator = (
            initialised_tpm_read_request_iterator()
        )
        self._off_tpm_read_request_iterator = off_tpm_read_request_iterator()
        self._unknown_tpm_read_request_iterator = unknown_tpm_read_request_iterator()
        self._unconnected_tpm_read_request_iterator = (
            unconnected_tpm_read_request_iterator()
        )
        self._unprogrammed_tpm_read_request_iterator = (
            unprogrammed_tpm_read_request_iterator()
        )
        self.initialise_request: Optional[Any] = None
        self.start_acquisition_request = None
        self._desire_connection = False
        self._firmware_download_request = None
        self._check_global_alarms = False
        self.command_wipe_time: dict[str, float] = {}

    def desire_connection(self) -> None:
        """
        Register a request to initialize a device.

        :param device_id: the device number.
            This is 0 for the FNDH, otherwise a smartbox number.
        """
        self._desire_connection = True

    def firmware_download_request(self, request: Any) -> None:
        """Register a request to initialize a device."""
        self._firmware_download_request = request

    def check_global_status_alarms(self) -> None:
        """Register a request to initialize a device."""
        self._check_global_alarms = True

    def desire_initialise(
        self, request: Any, wipe_time: Optional[float] = None
    ) -> None:
        """
        Register a request to initialize a device.

        :param device_id: the device number.
            This is 0 for the FNDH, otherwise a smartbox number.
        :param wipe_time: the approx time at which to wipe this command.
        """
        self.initialise_request = request
        if wipe_time is None:
            wipe_time = time.time() + 60
        self.command_wipe_time["initialise"] = wipe_time

    def desire_start_acquisition(self, request: Any) -> None:
        """
        Register a request to initialize a device.

        :param device_id: the device number.
            This is 0 for the FNDH, otherwise a smartbox number.
        """
        self.start_acquisition_request = request

    def get_request(self, tpm_status: TpmStatus) -> tuple[str, Any] | None:
        """
        Get a description of the next communication with the PaSD bus.

        :return: a tuple consisting of the name of the communication
            and any arguments or extra information.
        """
        for command, wipe_time in self.command_wipe_time.items():
            if time.time() > wipe_time:
                match command:
                    case "initialise":
                        if self.initialise_request:
                            print("dsdsdsdsd ALLL")
                            self.initialise_request.abort()
                            self.initialise_request = None
        if self._desire_connection:
            self._desire_connection = False
            return "CONNECT", None
        if self._check_global_alarms:
            self._check_global_alarms = False
            return "CHECK_CPLD_COMMS", None
        # we can always attempt a connection to TPM.

        match tpm_status:
            case TpmStatus.OFF:
                return next(self._off_tpm_read_request_iterator), None
            case TpmStatus.UNKNOWN:
                return next(self._unknown_tpm_read_request_iterator), None
            case TpmStatus.UNCONNECTED:
                return next(self._unconnected_tpm_read_request_iterator), None
            case TpmStatus.UNPROGRAMMED:
                if self._firmware_download_request:
                    request = self._firmware_download_request
                    self._firmware_download_request = None
                    return request
                if self.initialise_request:
                    request = self.initialise_request
                    self.initialise_request = None
                    return request
                return next(self._unprogrammed_tpm_read_request_iterator), None
            case TpmStatus.PROGRAMMED:
                if self.initialise_request:
                    request = self.initialise_request
                    self.initialise_request = None
                    return request
                if self._firmware_download_request:
                    request = self._firmware_download_request
                    self._firmware_download_request = None
                    return request
                return next(self._programmed_tpm_read_request_iterator), None
            case TpmStatus.INITIALISED:
                if self.initialise_request:
                    request = self.initialise_request
                    self.initialise_request = None
                    return request
                if self._firmware_download_request:
                    request = self._firmware_download_request
                    self._firmware_download_request = None
                    return request
                if self.start_acquisition_request:
                    request = self.start_acquisition_request
                    self.start_acquisition_request = None
                    return request
                return next(self._initialised_tpm_read_request_iterator), None
            case TpmStatus.SYNCHRONISED:
                if self.initialise_request:
                    request = self.initialise_request
                    self.initialise_request = None
                    return request
                if self._firmware_download_request:
                    request = self._firmware_download_request
                    self._firmware_download_request = None
                    return request
                if self.start_acquisition_request:
                    request = self.start_acquisition_request
                    self.start_acquisition_request = None
                    return request
                return next(self._initialised_tpm_read_request_iterator), None
            case _:
                return "RAISE_UNKNOWN_TPM_STATUS", None
