# type: ignore
#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements a class to convert from-to unix time."""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from .tile_data import TileData

__all__ = [
    "TileTime",
]


class TileTime(object):
    """
    Library to convert from rfc3339 strings to internal Tile time and back.

    Frame time is the time expressed as an offset in frames from a
    timestamp. Unix time is used for the timestamp. It is expressed in
    integrer seconds from 1970-01-01T01:00:00.000000Z. Time is otherwise
    expressed as a ISO-8601 (RFC3339) string, e.g.
    2021-03-02T12:34.56.789000Z.
    """

    RFC_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

    def __init__(self: TileTime, reference_time: int = 0) -> None:
        """
        Set the internal reference time. To be used each time it is reset.

        :param reference_time: Unix timestamp of the (integer) reference time
        """
        self._ref_time = reference_time

    def set_reference_time(self: TileTime, reference_time: int) -> None:
        """
        Set the internal reference time. To be used each time it is reset.

        :param reference_time: Unix timestamp of the (integer) reference time
        """
        self._ref_time = reference_time

    def format_time_from_frame(self: TileTime, frame_count: int) -> str:
        """
        Format a time expressed as frame count into ISO-8601 (RFC3339) string.

        e.g. 2021-03-02T12:34.56.789000Z. Returns the Unix zero time if
        the object is not yet initialised.

        :param frame_count: Frame number expressed as a multiple of
                256 channelised samples
        :return: ISO-8601 formatted time
        """
        time = datetime.fromtimestamp(
            self._ref_time + TileData.FRAME_PERIOD * frame_count, tz=timezone.utc
        )
        return datetime.strftime(time, self.RFC_FORMAT)

    def frame_from_utc_time(self: TileTime, utc_time: str) -> int:
        """
        Return first frame after specified time.

        :param utc_time: Utc Time in standard rfc3339 format
        :return: frame number equal or after specified time. -1 if error
        """
        if self._ref_time == 0:
            return -1
        try:
            dt = datetime.strptime(utc_time, self.RFC_FORMAT)
            timestamp = dt.replace(tzinfo=timezone.utc).timestamp() - self._ref_time
        except ValueError:
            timestamp = -1

        if timestamp < 0:
            return -1
        frame = int(np.ceil(timestamp / TileData.FRAME_PERIOD))
        return frame

    def timestamp_from_utc_time(self: TileTime, utc_time: str) -> int:
        """
        Return first timestamp (Unix) second after specified time.

        Does not account for leap seconds, utc_time must avoid them.

        :param utc_time: Utc Time in standard rfc3339 format
        :return: Unix timestamp equal or after specified time. -1 if error
        """
        try:
            dt = datetime.strptime(utc_time, self.RFC_FORMAT)
            timestamp = dt.replace(tzinfo=timezone.utc).timestamp()
        except ValueError:
            timestamp = -1

        if timestamp < 0:
            return -1
        timestamp = int(np.ceil(timestamp))
        return timestamp

    def format_time_from_timestamp(self: TileTime, timestamp: int) -> str:
        """
        Format a time expressed as a frame count into ISO-8601.

        Format a time expressed as a frame count into a properly formatted ISO-8601
        (RFC3339) string, e.g. 2021-03-02T12:34.56.789000Z.

        :param timestamp: Unix timestamp of the (integer) reference time
        :return: ISO-8601 formatted time
        :rtype: str
        """
        time = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        return datetime.strftime(time, self.RFC_FORMAT)
