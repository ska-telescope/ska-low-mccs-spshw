"""This module contains a placeholder for a transient buffer component."""
from __future__ import annotations

import logging

from ska_low_mccs.component import ObjectComponent


__all__ = ["TransientBuffer"]


class TransientBuffer(ObjectComponent):
    """A placeholder for a transient buffer."""

    def __init__(
        self: TransientBuffer,
        logger: logging.Logger,
    ) -> None:
        """
        Initialise a new instance.

        :param logger: a logger for this component to use
        """
        self._logger = logger

        self._station_id = ""
        self._transient_buffer_job_id = ""
        self._resampling_bits = 0
        self._n_stations = 0
        self._transient_frequency_window = (0.0,)
        self._station_ids = [
            "",
        ]

    @property
    def station_id(self: TransientBuffer) -> str:
        """
        Return the station id.

        :return: the station id.
        """
        return self._station_id

    @property
    def transient_buffer_job_id(self: TransientBuffer) -> str:
        """
        Return the transient buffer job id.

        :return: the transient buffer job id.
        """
        return self._transient_buffer_job_id

    @property
    def resampling_bits(self: TransientBuffer) -> int:
        """
        Return the resampling bit depth.

        :return: the resampling bit depth.
        """
        return self._resampling_bits

    @property
    def n_stations(self: TransientBuffer) -> int:
        """
        Return the number of stations.

        :return: the number of stations
        """
        return self._n_stations

    @property
    def transient_frequency_window(self: TransientBuffer) -> tuple[float]:
        """
        Return the transient frequency window.

        :return: the transient frequency window
        """
        return self._transient_frequency_window

    @property
    def station_ids(self: TransientBuffer) -> list[str]:
        """
        Return the station ids.

        :return: the station ids.
        """
        return list(self._station_ids)
