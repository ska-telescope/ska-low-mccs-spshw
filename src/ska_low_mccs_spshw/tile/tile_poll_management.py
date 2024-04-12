# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements polling management for a TileComponentManager."""

import time
from typing import Any, Iterator, Optional

from .tpm_status import TpmStatus


def off_tpm_read_request_iterator() -> Iterator[str]:
    """
    Return an iterator yielding attributes to be polled when TpmStatus is OFF.

    :yields: the name of an request group to be read from the device.
    """
    while True:
        yield "CONNECT"


def unconnected_tpm_read_request_iterator() -> Iterator[str]:
    """
    Return an iterator yielding attributes to be polled when TpmStatus is NotConnected.

    :yields: the name of an attribute group to be read from the device.
    """
    while True:
        yield "CONNECT"


def unknown_tpm_read_request_iterator() -> Iterator[str]:
    """
    Return an iterator yielding attributes to be polled when TpmStatus is Unknown.

    :yields: the name of an attribute group to be read from the device.
    """
    while True:
        yield "CHECK_CPLD_COMMS"
        yield "CONNECT"
        yield "FIRMWARE_AVALIABLE"


def unprogrammed_tpm_read_request_iterator() -> Iterator[str]:
    """
    Return an iterator yielding attributes to be polled when TpmStatus is NotProgrammed.

    :yields: the name of an attribute group to be read from the device.
    """
    while True:
        yield "CHECK_CPLD_COMMS"
        yield "CONNECT"
        yield "FIRMWARE_AVALIABLE"


def programmed_tpm_read_request_iterator() -> Iterator[str]:
    """
    Return an iterator yielding attributes to be polled when TpmStatus is Programmed.

    :yields: the name of an attribute group to be read from the device.
    """
    while True:
        yield "CHECK_CPLD_COMMS"
        yield "CSP_ROUNDING"
        yield "CHANNELISER_ROUNDING"
        yield "IS_PROGRAMMED"
        yield "HEALTH_STATUS"
        yield "PLL_LOCKED"
        yield "FIRMWARE_AVALIABLE"


def initialised_tpm_read_request_iterator() -> Iterator[str]:
    """
    Return an iterator yielding attributes to be polled when TpmStatus is Initialised.

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
        yield "FIRMWARE_AVALIABLE"


def synchronised_tpm_read_request_iterator() -> Iterator[str]:
    """
    Return an iterator yielding attributes to be polled when TpmStatus is Initialised.

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
        yield "FIRMWARE_AVALIABLE"
        yield "TILE_BEAMFORMER_FRAME"


class TileRequestProvider:  # pylint: disable=too-many-instance-attributes
    """
    A class that determines the next communication with the TpmDriver.

    It ensures that:

    * commands get executed as promptly as possible

    * only attributes allowed to be polled given a TpmStatus are returned.
    """

    def __init__(self) -> None:
        """Initialise a new instance."""
        self._programmed_tpm_read_request_iterator = (
            programmed_tpm_read_request_iterator()
        )
        self._initialised_tpm_read_request_iterator = (
            initialised_tpm_read_request_iterator()
        )
        self._synchronised_tpm_read_request_iterator = (
            synchronised_tpm_read_request_iterator()
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
        self.download_firmware_request: Optional[Any] = None
        self.start_acquisition_request: Optional[Any] = None

        self._desire_connection = False
        self._check_global_alarms = False
        self.command_wipe_time: dict[str, float] = {}

    def desire_connection(self) -> None:
        """Register a request to initialize a device."""
        self._desire_connection = True

    def check_global_status_alarms(self) -> None:
        """Register a request to initialize a device."""
        self._check_global_alarms = True

    def desire_initialise(
        self, request: Any, wipe_time: Optional[float] = None
    ) -> None:
        """
        Register a request to initialize a device.

        :param request: The initialise command to execute on
            a poll.
        :param wipe_time: the approx time at which to wipe this command.
        """
        self.initialise_request = request
        if wipe_time is None:
            wipe_time = time.time() + 60
        self.command_wipe_time["initialise"] = wipe_time

    def desire_download_firmware(
        self, request: Any, wipe_time: Optional[float] = None
    ) -> None:
        """
        Register a request to download new firmware to a device.

        :param request: The initialise command to execute on
            a poll.
        :param wipe_time: the approx time at which to wipe this command.
        """
        self.download_firmware_request = request
        if wipe_time is None:
            wipe_time = time.time() + 60
        self.command_wipe_time["download_firmware"] = wipe_time

    def desire_start_acquisition(
        self, request: Any, wipe_time: Optional[float] = None
    ) -> None:
        """
        Register a request to download new firmware to a device.

        :param request: The initialise command to execute on
            a poll.
        :param wipe_time: the approx time at which to wipe this command.
        """
        self.start_acquisition_request = request
        if wipe_time is None:
            wipe_time = time.time() + 60
        self.command_wipe_time["start_acquisition"] = wipe_time

    def get_request(  # pylint: disable=too-many-return-statements, too-many-branches
        self, tpm_status: TpmStatus
    ) -> tuple[str, Any] | None:
        """
        Get a description of the next communication with the PaSD bus.

        :param tpm_status: the tpm_status at the time of the request.

        :return: a tuple consisting of the name of the communication
            and any arguments or extra information.
        """
        # Check if the initialise LRC need to be aborted.
        for command, wipe_time in self.command_wipe_time.items():
            if time.time() > wipe_time:
                match command:
                    case "initialise":
                        if self.initialise_request:
                            self.initialise_request.abort()
                            self.initialise_request = None
                    case "download_firmware":
                        if self.download_firmware_request:
                            self.download_firmware_request.abort()
                            self.download_firmware_request = None
                    case "start_acquisition":
                        if self.start_acquisition_request:
                            self.start_acquisition_request.abort()
                            self.start_acquisition_request = None

        # Key connection commands come first
        if self._desire_connection:
            self._desire_connection = False
            return "CONNECT", None
        if self._check_global_alarms:
            self._check_global_alarms = False
            return "CHECK_CPLD_COMMS", None

        match tpm_status:
            case TpmStatus.OFF:
                return next(self._off_tpm_read_request_iterator), None
            case TpmStatus.UNKNOWN:
                return next(self._unknown_tpm_read_request_iterator), None
            case TpmStatus.UNCONNECTED:
                return next(self._unconnected_tpm_read_request_iterator), None
            case TpmStatus.UNPROGRAMMED:
                if self.initialise_request:
                    request = self.initialise_request
                    self.initialise_request = None
                    return request
                if self.download_firmware_request:
                    request = self.download_firmware_request
                    self.download_firmware_request = None
                    return request
                return next(self._unprogrammed_tpm_read_request_iterator), None
            case TpmStatus.PROGRAMMED:
                if self.initialise_request:
                    request = self.initialise_request
                    self.initialise_request = None
                    return request
                if self.download_firmware_request:
                    request = self.download_firmware_request
                    self.download_firmware_request = None
                    return request
                return next(self._programmed_tpm_read_request_iterator), None
            case TpmStatus.INITIALISED:
                if self.initialise_request:
                    request = self.initialise_request
                    self.initialise_request = None
                    return request
                if self.download_firmware_request:
                    request = self.download_firmware_request
                    self.download_firmware_request = None
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
                if self.download_firmware_request:
                    request = self.download_firmware_request
                    self.download_firmware_request = None
                    return request
                if self.start_acquisition_request:
                    request = self.start_acquisition_request
                    self.start_acquisition_request = None
                    return request
                return next(self._synchronised_tpm_read_request_iterator), None
            case _:
                return "RAISE_UNKNOWN_TPM_STATUS", None
