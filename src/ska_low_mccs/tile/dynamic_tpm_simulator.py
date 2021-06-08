# type: ignore
# -*- coding: utf-8 -*-
"""
An implementation of a TPM simulator.
"""
from ska_low_mccs.hardware.simulable_hardware import (
    DynamicValuesGenerator,
    DynamicValuesUpdater,
)
from ska_low_mccs.tile.base_tpm_simulator import BaseTpmSimulator


class DynamicTpmSimulator(BaseTpmSimulator):
    """
    A simulator for a TPM, with dynamic value updates to certain
    attributes.

    This is useful for demoing.
    """

    def __init__(self, logger, fail_connect=False):
        """
        Initialise a new instance.

        :param logger: a logger for this simulator to use
        :type logger: an instance of :py:class:`logging.Logger`, or
            an object that implements the same interface
        :param fail_connect: whether this simulator should initially
            simulate failure to connect to the hardware
        :type fail_connect: bool
        """
        self._voltage = None
        self._current = None
        self._board_temperature = None
        self._fpga1_temperature = None
        self._fpga2_temperature = None

        self._updater = DynamicValuesUpdater(1.0)
        self._updater.add_target(
            DynamicValuesGenerator(4.55, 5.45), self._voltage_changed
        )
        self._updater.add_target(
            DynamicValuesGenerator(0.05, 2.95), self._current_changed
        )
        self._updater.add_target(
            DynamicValuesGenerator(16.0, 47.0), self._board_temperature_changed
        )
        self._updater.add_target(
            DynamicValuesGenerator(16.0, 47.0), self._fpga1_temperature_changed
        )
        self._updater.add_target(
            DynamicValuesGenerator(16.0, 47.0), self._fpga2_temperature_changed
        )
        self._updater.start()

        super().__init__(logger, fail_connect=fail_connect)

    def __del__(self):
        """
        Garbage-collection hook.
        """
        self._updater.stop()

    @property
    def board_temperature(self):
        """
        Return the temperature of the TPM.

        :return: the temperature of the TPM
        :rtype: float
        """
        return self._board_temperature

    def _board_temperature_changed(self, board_temperature):
        """
        Callback called when the board temperature changes.

        :param board_temperature: the new board temperature
        :type board_temperature: float
        """
        self._board_temperature = board_temperature

    @property
    def voltage(self):
        """
        Return the voltage of the TPM.

        :return: the voltage of the TPM
        :rtype: float
        """
        return self._voltage

    def _voltage_changed(self, voltage):
        """
        Callback called when the voltage changes.

        :param voltage: the new voltage
        :type voltage: float
        """
        self._voltage = voltage

    @property
    def current(self):
        """
        Return the current of the TPM.

        :return: the current of the TPM
        :rtype: float
        """
        return self._current

    def _current_changed(self, current):
        """
        Callback called when the current changes.

        :param current: the new current
        :type current: float
        """
        self._current = current

    @property
    def fpga1_temperature(self):
        """
        Return the temperature of FPGA 1.

        :return: the temperature of FPGA 1
        :rtype: float
        """
        return self._fpga1_temperature

    def _fpga1_temperature_changed(self, fpga1_temperature):
        """
        Callback called when the FPGA1 temperature changes.

        :param fpga1_temperature: the new FPGA1 temperature
        :type fpga1_temperature: float
        """
        self._fpga1_temperature = fpga1_temperature

    @property
    def fpga2_temperature(self):
        """
        Return the temperature of FPGA 2.

        :return: the temperature of FPGA 2
        :rtype: float
        """
        return self._fpga2_temperature

    def _fpga2_temperature_changed(self, fpga2_temperature):
        """
        Callback called when the FPGA2 temperature changes.

        :param fpga2_temperature: the new FPGA2 temperature
        :type fpga2_temperature: float
        """
        self._fpga2_temperature = fpga2_temperature
