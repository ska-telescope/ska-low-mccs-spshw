#  -*- coding: utf-8 -*
# pylint: disable=too-many-nested-blocks
#
# BSD 3-Clause License
#
# Copyright (c) 2022, Alessio Magro
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""An implementation of a SpeadDataSimulator."""

from __future__ import annotations

import bisect
import logging
import socket
import struct
import threading
import time
from collections import OrderedDict
from typing import Any, Optional

import numpy as np

__all__ = ["SpeadDataSimulator"]


# pylint: disable=too-many-instance-attributes
class SpeadDataSimulator:
    """
    A class to send simulated integrated channel data.

    TODO: do we want the generated data to be valid:
     - delays applied per antenna
     - attenuations applied per channel
     - ...

    TODO: do we want the ability to send different data
    types:
    - raw
    - channel
    - ....
    """

    # pylint: disable=too-many-arguments
    def __init__(
        self: SpeadDataSimulator,
        logger: logging.Logger,
    ) -> None:
        """
        Init simulator.

        :param logger: a logger.
        """
        self._ip: Optional[str] = None
        self._port: Optional[int] = None
        self._nof_tiles: int = 1
        self.logger = logger
        self._unix_epoch_time = int(time.time())
        self._timestamp = 0
        self._lmc_capture_mode = 0x6
        self._station_id = 0
        self._packet_payload_length = 1024
        self._data_type = np.uint16

        self._nof_fpgas = 2
        self._nof_pols = 2
        self._nof_ants_per_fpga = 8
        self._nof_ants_per_packet = 1
        self._nof_channels = 512
        self._nof_channels_per_packet = 256
        self._nof_channel_packets = self._nof_channels // self._nof_channels_per_packet
        self._nof_antenna_packets = self._nof_ants_per_fpga // self._nof_ants_per_packet

        self._timestamp = 0

        self._sample_x_powers = {
            0.0: 0.0050,
            30e6: 0.0050,
            50e6: 0.50,
            65e6: 3.15,
            136e6: 1.58,
            137e6: 3.15,
            138e6: 1.58,
            240e6: 0.39,
            250e6: 2.51,
            260e6: 0.10,
            270e6: 1.58,
            280e6: 0.25,
            360e6: 0.10,
            370e6: 0.25,
            375e6: 0.079,
            380e6: 0.20,
            390e6: 0.025,
            400e6: 0.010,
        }
        self._sample_y_powers = {
            0.0: 0.0050,
            30e6: 0.0050,
            50e6: 0.50,
            65e6: 3.15,
            136e6: 1.26,
            137e6: 3.15,
            138e6: 1.26,
            140e6: 1.26,
            240e6: 0.32,
            250e6: 2.51,
            260e6: 1.58,
            270e6: 3.15,
            280e6: 0.20,
            360e6: 0.06,
            370e6: 0.50,
            375e6: 0.10,
            380e6: 0.25,
            390e6: 0.020,
            400e6: 0.010,
        }

        # Max fractional deviation from a value due to noise
        # Set to 0 by default for ease of testing
        # For demoing, this can be set to something around 0.2
        self._noise_level = 0.0

        self._data_types = {"raw", "channel"}
        self._stop_events = {
            data_type: threading.Event() for data_type in self._data_types
        }
        # These need to be instantiated at runtime to set their args
        self._threads: dict[str, threading.Thread] = {}

        # Generate test data
        self._raw_packet_data = np.zeros(
            (
                self._nof_tiles,
                self._nof_fpgas,
                self._nof_ants_per_fpga,
                self._nof_channel_packets,
                self._nof_channels_per_packet * 2,
            ),
            # dtype=np.uint16,
            dtype=np.float32,
        )
        self._channelised_packet_data = np.zeros(
            (
                self._nof_tiles,
                self._nof_fpgas,
                self._nof_ants_per_fpga,
                self._nof_channel_packets,
                self._nof_channels_per_packet * 2,
            ),
            # dtype=np.uint16,
            dtype=np.float32,
        )
        for tpm in range(self._nof_tiles):
            for fpga in range(self._nof_fpgas):
                for antenna in range(self._nof_ants_per_fpga):
                    for channel in range(self._nof_channel_packets):
                        self._raw_packet_data[tpm][fpga][antenna][
                            channel
                        ] = self._generate_raw_data(tpm, fpga, antenna, channel)
                        self._channelised_packet_data[tpm][fpga][antenna][
                            channel
                        ] = self._generate_channelised_data(tpm, fpga, antenna, channel)

        # Create socket
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def stop_sending_data(self: SpeadDataSimulator) -> None:
        """
        Stop sending data.

        This forces each data sending thread to finish execution

        :raises RuntimeError: If a thread failed to finish
        """
        # The AAVS tile only needs to stop channel continuous here but with the
        # sleep between antennas the other data modes can end up running for a
        # long time here so having a way to stop them is useful
        for data_type, event in self._stop_events.items():
            event.set()
            if data_type in self._threads:
                self._threads[data_type].join(timeout=10)
                if self._threads[data_type].is_alive():
                    raise RuntimeError("Failed to stop thread.")

    def send_raw_data(
        self: SpeadDataSimulator,
        sleep_between_antennas: int,
    ) -> None:
        """
        Send raw data.

        However note at present the data generated is integrated channel data.

        :param sleep_between_antennas: time in seconds.
        """
        self._threads["raw"] = threading.Thread(
            target=self._send_raw_data,
            name="raw_data_thread",
            args=[sleep_between_antennas],
            daemon=True,
        )
        self._stop_events["raw"].clear()
        self._threads["raw"].start()

    def _send_raw_data(
        self: SpeadDataSimulator,
        sleep_between_antennas: int,
    ) -> None:
        """
        Send raw data.

        :param sleep_between_antennas: time in seconds.

        :raises NotImplementedError: send raw data is not implemented.
        """
        raise NotImplementedError(
            "because raw data SPEAD packets are not implemented yet."
        )

    def send_channelised_data(
        self: SpeadDataSimulator,
        sleep_between_antennas: int,
        number_of_samples: int = 128,
        first_channel: int = 0,
        last_channel: int = 511,
    ) -> None:
        """
        Send integrated channel data.

        :param sleep_between_antennas: time in seconds.
        :param number_of_samples: Number of spectra to send
        :param first_channel: First channel to send
        :param last_channel: Last channel to send
        """
        self._threads["channel"] = threading.Thread(
            target=self._send_channelised_data,
            name="channel_data_thread",
            args=[
                sleep_between_antennas,
                number_of_samples,
                first_channel,
                last_channel,
            ],
            daemon=True,
        )
        self._stop_events["channel"].clear()
        self._threads["channel"].start()

    def _send_channelised_data(
        self: SpeadDataSimulator,
        sleep_between_antennas: int,
        number_of_samples: int = 128,
        first_channel: int = 0,
        last_channel: int = 511,
    ) -> None:
        """
        Send integrated channel data.

        :param sleep_between_antennas: time in seconds.
        :param number_of_samples: Number of spectra to send
        :param first_channel: First channel to send
        :param last_channel: Last channel to send
        """
        self._stop_events["channel"].clear()
        num_channels = 1 + last_channel - first_channel
        for tile in range(self._nof_tiles):
            for ant in range(self._nof_ants_per_fpga):
                for _ in range(number_of_samples):
                    for chan in range(
                        int(num_channels / self._nof_channels_per_packet)
                    ):
                        for fpga in range(self._nof_fpgas):
                            if self._stop_events["channel"].is_set():
                                return
                            self._transmit_packet(
                                tile,
                                fpga,
                                self._timestamp,
                                ant + fpga * self._nof_ants_per_fpga,
                                first_channel + (chan * self._nof_channels_per_packet),
                                self._channelised_packet_data,
                            )
                time.sleep(sleep_between_antennas)
                self._timestamp += 1_000_000_000  # 1e9ns = 1s

    def _transmit_packet(  # pylint: disable=too-many-locals
        self: SpeadDataSimulator,
        tpm_id: int,
        fpga_id: int,
        timestamp: int,
        start_antenna: int,
        start_channel: int,
        packet_data: np.ndarray,
    ) -> None:
        """
        Generate a packet.

        :param tpm_id: Id of the TPM
        :param fpga_id: Id of the FPGA
        :param timestamp: Time
        :param start_antenna: start antenna
        :param start_channel: start channel
        :param packet_data: the data to send
        """
        header = 0x53 << 56 | 0x04 << 48 | 0x02 << 40 | 0x06 << 32 | 0x08
        heap_counter = 1 << 63 | 0x0001 << 48 | timestamp
        pkt_len = 1 << 63 | 0x0004 << 48 | self._packet_payload_length
        sync_time = 1 << 63 | 0x1027 << 48 | self._unix_epoch_time
        spead_timestamp = 1 << 63 | 0x1600 << 48 | timestamp & 0xFFFFFFFFFF
        lmc_capture_mode = 1 << 63 | 0x2004 << 48 | self._lmc_capture_mode
        lmc_info = (
            1 << 63
            | 0x2002 << 48
            | start_channel << 24
            | start_antenna << 8
            | self._nof_ants_per_packet & 0xFF
        )
        lmc_tpm_info = 1 << 63 | 0x2001 << 48 | tpm_id << 32 | self._station_id << 16
        sample_offset = 0 << 63 | 0x3300 << 48

        packet = (
            struct.pack(
                ">" + "Q" * 9,
                header,
                heap_counter,
                pkt_len,
                sync_time,
                spead_timestamp,
                lmc_capture_mode,
                lmc_info,
                lmc_tpm_info,
                sample_offset,
            )
            + packet_data[tpm_id][fpga_id][start_antenna // self._nof_ants_per_fpga][
                start_channel // self._nof_channels_per_packet
            ].tobytes()
        )

        self._socket.sendto(packet, (self._ip, self._port))

    def _generate_channelised_data(
        self: SpeadDataSimulator,
        tpm_id: int,
        fpga_id: int,
        start_antenna: int,
        start_channel: int,
    ) -> Any:
        """
        Generate samples data set.

        :param tpm_id: Id of the TPM
        :param fpga_id: Id of the FPGA
        :param start_antenna: start antenna
        :param start_channel: start channel

        :return: the packet data
        """
        start_antenna = (
            tpm_id * self._nof_ants_per_fpga * self._nof_fpgas
            + fpga_id * self._nof_ants_per_fpga
            + start_antenna
        )

        x_bandpass = self._generate_simulated_bandpass(
            0,
            start_channel * self._nof_channels_per_packet,
            ((1 + start_channel) * self._nof_channels_per_packet) - 1,
        )
        y_bandpass = self._generate_simulated_bandpass(
            1,
            start_channel * self._nof_channels_per_packet,
            ((1 + start_channel) * self._nof_channels_per_packet) - 1,
        )

        return np.ravel([x_bandpass, y_bandpass], "F")

    def _generate_simulated_bandpass(  # pylint: disable=too-many-locals
        self: SpeadDataSimulator,
        polarisation: int,
        first_channel: int,
        last_channel: int,
    ) -> np.ndarray:
        """
        Generate a simulated bandpass spectrum.

        :param polarisation: 1 for y polarisation, 0 for x polarisation
        :param first_channel: The first channel to generate for
        :param last_channel: the last channel to generate for

        :return: a bandpass spectrum between the first and last channels
        """
        channels = np.arange(first_channel, last_channel + 1, 1)
        freqs = channels * 800e6 / 1024
        powers_table = (
            self._sample_y_powers if polarisation == 1 else self._sample_x_powers
        )
        ordered_powers_table = OrderedDict(sorted(powers_table.items()))
        powers_array = np.zeros((len(channels)), dtype=np.float16)
        for channel in channels:
            # Get the highest frequency below the input channel
            # and interpolate between that and the one above
            left_index = bisect.bisect_left(
                list(ordered_powers_table.keys()), freqs[channel - first_channel]
            )
            higher_bound = list(ordered_powers_table.keys())[left_index]
            lower_bound = list(ordered_powers_table.keys())[left_index - 1]
            higher_frac = (freqs[channel - first_channel] - higher_bound) / (
                lower_bound - higher_bound
            )
            lower_frac = 1 - higher_frac
            powers_array[channel - first_channel] = (
                lower_frac * ordered_powers_table[higher_bound]
            ) + (higher_frac * ordered_powers_table[lower_bound])
        noisy_array = powers_array + (
            (np.random.rand(len(channels)) - 0.5) * 2 * self._noise_level * powers_array
        )
        return noisy_array

    def _generate_raw_data(
        self: SpeadDataSimulator,
        tpm_id: int,
        fpga_id: int,
        start_antenna: int,
        start_channel: int,
    ) -> Any:
        """
        Generate samples data set.

        :param tpm_id: Id of the TPM
        :param fpga_id: Id of the FPGA
        :param start_antenna: start antenna
        :param start_channel: start channel

        :return: the packet data
        """
        start_antenna = (
            tpm_id * self._nof_ants_per_fpga * self._nof_fpgas
            + fpga_id * self._nof_ants_per_fpga
            + start_antenna
        )
        packet_data = np.zeros(self._packet_payload_length // 2, dtype=np.uint16)

        counter = 0
        for c in range(self._nof_channels_per_packet):
            packet_data[counter] = (
                start_antenna * self._nof_channels
                + start_channel * self._nof_channels_per_packet
                + c
            )
            packet_data[counter + 1] = (
                start_antenna * self._nof_channels
                + self._nof_channels
                - (start_channel * self._nof_channels_per_packet + c)
            )
            counter += 2

        return packet_data

    def set_destination_ip(
        self: SpeadDataSimulator,
        ip: str,
        port: int,
    ) -> None:
        """
        Set the destination IP:Port to send SPEAD packets.

        :param ip: the destination ip to send SPEAD packets.
        :param port: the destination port to send SPEAD packets.
        """
        self._ip = ip
        self._port = port
