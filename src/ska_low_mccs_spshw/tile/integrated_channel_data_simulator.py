#  -*- coding: utf-8 -*
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
"""An implementation of a IntegratedChannelDataSimulator."""

from __future__ import annotations

import socket
import struct
import time
from typing import Any, Optional

import numpy as np

__all__ = ["IntegratedChannelDataSimulator"]


# pylint: disable=too-many-instance-attributes
class IntegratedChannelDataSimulator:
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
        self: IntegratedChannelDataSimulator,
    ) -> None:
        """Init simulator."""
        self._ip: Optional[str] = None
        self._port: Optional[int] = None
        self._nof_tiles: int = 1

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

        # Generate test data
        self._packet_data = np.zeros(
            (
                self._nof_tiles,
                self._nof_fpgas,
                self._nof_ants_per_fpga,
                self._nof_channel_packets,
                self._nof_channels_per_packet * 2,
            ),
            dtype=np.uint16,
        )

        for tpm in range(self._nof_tiles):
            for fpga in range(self._nof_fpgas):
                for antenna in range(self._nof_ants_per_fpga):
                    for channel in range(self._nof_channel_packets):
                        self._packet_data[tpm][fpga][antenna][
                            channel
                        ] = self._generate_data(tpm, fpga, antenna, channel)

        # Create socket
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send_data(
        self: IntegratedChannelDataSimulator, sleep_between_antennas: int
    ) -> None:
        """
        Generate integrated channel data.

        :param sleep_between_antennas: time in seconds.
        """
        for tile in range(self._nof_tiles):

            for ant in range(self._nof_ants_per_fpga):

                for chan in range(
                    int(self._nof_channels / self._nof_channels_per_packet)
                ):
                    for fpga in range(self._nof_fpgas):
                        self._transmit_packet(
                            tile,
                            fpga,
                            self._timestamp,
                            ant + fpga * self._nof_ants_per_fpga,
                            chan * self._nof_channels_per_packet,
                        )

                time.sleep(sleep_between_antennas)

        self._timestamp += 1

    def _transmit_packet(  # pylint: disable=too-many-locals
        self: IntegratedChannelDataSimulator,
        tpm_id: int,
        fpga_id: int,
        timestamp: int,
        start_antenna: int,
        start_channel: int,
    ) -> None:
        """
        Generate a packet.

        :param tpm_id: Id of the TPM
        :param fpga_id: Id of the FPGA
        :param timestamp: Time
        :param start_antenna: start antenna
        :param start_channel: start channel
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
            + self._packet_data[tpm_id][fpga_id][
                start_antenna // self._nof_ants_per_fpga
            ][start_channel // self._nof_channels_per_packet].tobytes()
        )

        self._socket.sendto(packet, (self._ip, self._port))

    def _generate_data(
        self: IntegratedChannelDataSimulator,
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
        self: IntegratedChannelDataSimulator,
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
