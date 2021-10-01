# -*- coding: utf-8 -*-
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""An implementation of a TPM simulator."""

from __future__ import annotations  # allow forward references in type hints

import logging

from ska_low_mccs.tile.base_tpm_simulator import BaseTpmSimulator


class StaticTpmSimulator(BaseTpmSimulator):
    """A simulator for a TPM."""

    VOLTAGE = 4.7
    CURRENT = 0.4
    BOARD_TEMPERATURE = 36.0
    FPGA1_TEMPERATURE = 38.0
    FPGA2_TEMPERATURE = 37.5

    def __init__(self: StaticTpmSimulator, logger: logging.Logger) -> None:
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
    def board_temperature(self: StaticTpmSimulator) -> float:
        """
        Return the temperature of the TPM.

        :return: the temperature of the TPM
        """
        return self._board_temperature

    @property
    def voltage(self: StaticTpmSimulator) -> float:
        """
        Return the voltage of the TPM.

        :return: the voltage of the TPM
        """
        return self._voltage

    @property
    def current(self: StaticTpmSimulator) -> float:
        """
        Return the current of the TPM.

        :return: the current of the TPM
        """
        return self._current

    @property
    def fpga1_temperature(self: StaticTpmSimulator) -> float:
        """
        Return the temperature of FPGA 1.

        :return: the temperature of FPGA 1
        """
        return self._fpga1_temperature

    @property
    def fpga2_temperature(self: StaticTpmSimulator) -> float:
        """
        Return the temperature of FPGA 2.

        :return: the temperature of FPGA 2
        """
        return self._fpga2_temperature
