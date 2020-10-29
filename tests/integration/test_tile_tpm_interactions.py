"""
This module contains tests of MccsTile that requires the presence of a
MccsTpmDeviceSimulator interactions between ska.low.mccs classes,
particularly tango devices.
"""
import time
from ska.low.mccs.tile import TileHardware

devices_to_load = {
    "path": "charts/ska-low-mccs/data/configuration.json",
    "package": "ska.low.mccs",
    "devices": ["tile_0001", "tpmsimulator"],
}


class TestMccsTile_MccsTpmDeviceSimulator_Integration:
    """
    Integration test cases for the MccsTile's interactions with MccsTpmDeviceSimulator
    """

    def test_voltage(self, device_context):
        """
        Test for the voltage attribute.

        :param device_context: a test context for a set of tango devices
        :type device_context: :py:class:`tango.MultiDeviceTestContext`
        """
        tile = device_context.get_device("low-mccs/tile/0001")
        tile.On()
        tile.Connect(True)
        time.sleep(1)
        assert tile.voltage == TileHardware.VOLTAGE

    def test_current(self, device_context):
        """
        Test for the current attribute.

        :param device_context: a test context for a set of tango devices
        :type device_context: :py:class:`tango.MultiDeviceTestContext`
        """
        tile = device_context.get_device("low-mccs/tile/0001")
        tile.On()
        tile.Connect(True)
        time.sleep(1)
        tile.current == TileHardware.CURRENT

    def test_board_temperature(self, device_context):
        """
        Test for the board_temperature attribute.

        :param device_context: a test context for a set of tango devices
        :type device_context: :py:class:`tango.MultiDeviceTestContext`
        """
        tile = device_context.get_device("low-mccs/tile/0001")
        tile.On()
        tile.Connect(True)
        time.sleep(1)
        assert tile.board_temperature == TileHardware.BOARD_TEMPERATURE

    def test_fpga1_temperature(self, device_context):
        """
        Test for the fpga1_temperature attribute.

        :param device_context: a test context for a set of tango devices
        :type device_context: :py:class:`tango.MultiDeviceTestContext`
        """
        tile = device_context.get_device("low-mccs/tile/0001")
        tile.On()
        tile.Connect(True)
        time.sleep(1)
        assert tile.fpga1_temperature == TileHardware.FPGA1_TEMPERATURE

    def test_fpga2_temperature(self, device_context):
        """
        Test for the fpga2_temperature attribute.

        :param device_context: a test context for a set of tango devices
        :type device_context: :py:class:`tango.MultiDeviceTestContext`
        """
        tile = device_context.get_device("low-mccs/tile/0001")
        tile.On()
        tile.Connect(True)
        time.sleep(1)
        assert tile.fpga2_temperature == TileHardware.FPGA2_TEMPERATURE
