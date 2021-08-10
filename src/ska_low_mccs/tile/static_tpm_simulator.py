# type: ignore
# -*- coding: utf-8 -*-
"""An implementation of a static TPM simulator."""
from __future__ import annotations

import logging

from ska_low_mccs.tile.base_tpm_simulator import BaseTpmSimulator


class StaticTpmSimulator(BaseTpmSimulator):
    """A simulator for a TPM."""

    VOLTAGE = 4.7
    CURRENT = 0.4
    BOARD_TEMPERATURE = 36.0
    FPGA1_TEMPERATURE = 38.0
    FPGA2_TEMPERATURE = 37.5

    def __init__(
        self: StaticTpmSimulator,
        logger: logging.Logger,
    ) -> None:
        """
        Initialise a new TPM simulator instance.

        :param logger: a logger for this simulator to use
        """
        self._voltage = self.VOLTAGE
        self._current = self.CURRENT
        self._board_temperature = self.BOARD_TEMPERATURE
        self._fpga1_temperature = self.FPGA1_TEMPERATURE
        self._fpga2_temperature = self.FPGA2_TEMPERATURE

        super().__init__(logger)

    @property
    def board_temperature(self):
        """
        Return the temperature of the TPM.

        :return: the temperature of the TPM
        :rtype: float
        """
        return self._board_temperature

    @property
    def voltage(self):
        """
        Return the voltage of the TPM.

        :return: the voltage of the TPM
        :rtype: float
        """
        return self._voltage

    @property
    def current(self):
        """
        Return the current of the TPM.

        :return: the current of the TPM
        :rtype: float
        """
        return self._current

    @property
    def fpga1_temperature(self):
        """
        Return the temperature of FPGA 1.

        :return: the temperature of FPGA 1
        :rtype: float
        """
        return self._fpga1_temperature

    @property
    def fpga2_temperature(self):
        """
        Return the temperature of FPGA 2.

        :return: the temperature of FPGA 2
        :rtype: float
        """
        return self._fpga2_temperature
