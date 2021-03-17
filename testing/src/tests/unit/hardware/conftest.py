"""
This module contains pytest fixtures and other test setups for unit
testing ska.low.mccs.hardware modules.
"""
import pytest

from ska.low.mccs.hardware import (
    HardwareFactory,
    HardwareHealthEvaluator,
    HardwareSimulator,
)


@pytest.fixture()
def hardware_health_evaluator():
    """
    Return the hardware health evaluator under test.

    :return: the hardware health evaluator under test
    :rtype: :py:class:`~ska.low.mccs.hardware.base_hardware.HardwareHealthEvaluator`
    """
    return HardwareHealthEvaluator()


@pytest.fixture()
def hardware_driver():
    """
    Return the hardware driver under test.

    Returns a HardwareSimulator, because we need to return a basic
    mock driver, and the HardwareSimulator is just that.

    :return: the hardware driver under test
    :rtype: :py:class:`~ska.low.mccs.hardware.simulable_hardware.HardwareSimulator`
    """
    return HardwareSimulator(is_connectible=True)


@pytest.fixture()
def hardware_factory(hardware_driver):
    """
    Fixture that provides a basic hardware factory that always returns a
    pre-defined hardware driver.

    :param hardware_driver: the hardware driver for this factory to
        return
    :type hardware_driver:
        :py:class:`~ska.low.mccs.hardware.base_hardware.HardwareDriver`

    :return: a hardware factory that always returns the pre-defined
        hardware driver
    :rtype: :py:class:`~ska.low.mccs.hardware.base_hardware.HardwareFactory`
    """

    class BasicHardwareFactory(HardwareFactory):
        """
        A basic hardware factory that always returns the same hardware.
        """

        def __init__(self, hardware):
            """
            Create a new instance.

            :param hardware: the hardware that this factory will always
                return
            :type hardware:
                :py:class:`~ska.low.mccs.hardware.base_hardware.HardwareDriver`
            """
            self._hardware = hardware

        @property
        def hardware(self):
            """
            Return this factory's hardware.

            :return: this factory's hardware
            :rtype:
                :py:class:`~ska.low.mccs.hardware.base_hardware.HardwareDriver`
            """
            return self._hardware

    return BasicHardwareFactory(hardware_driver)
