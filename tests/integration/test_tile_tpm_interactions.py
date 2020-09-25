"""
This module contains tests of MccsTile that requires the presence of a
MccsTpmDeviceSimulator interactions between ska.low.mccs classes,
particularly tango devices.
"""
import time

devices_to_load = {
    "path": "charts/mccs/data/configuration.json",
    "package": "ska.low.mccs",
    "devices": ["tile0001", "tpmsimulator"],
}


class TestMccsTile_MccsTpmDeviceSimulator_Integration:
    """
    Integration test cases for the MccsTile's interactions with MccsTpmDeviceSimulator
    """

    def test_voltage(self, device_context):
        """
        Test for the voltage attribute.

        :param device_context: a test context for a set of tango devices
        :type device_context: tango.MultiDeviceTestContext
        """
        tile = device_context.get_device("low/elt/tile_1")
        tile.Connect(True)
        time.sleep(1)
        assert tile.voltage == 4.7

    def test_current(self, device_context):
        """
        Test for the current attribute.

        :param device_context: a test context for a set of tango devices
        :type device_context: tango.MultiDeviceTestContext
        """
        tile = device_context.get_device("low/elt/tile_1")
        tile.Connect(True)
        time.sleep(1)
        tile.current == 0.4

    def test_board_temperature(self, device_context):
        """
        Test for the board_temperature attribute.

        :param device_context: a test context for a set of tango devices
        :type device_context: tango.MultiDeviceTestContext
        """
        tile = device_context.get_device("low/elt/tile_1")
        tile.Connect(True)
        time.sleep(1)
        assert tile.board_temperature == 36.0

    def test_fpga1_temperature(self, device_context):
        """
        Test for the fpga1_temperature attribute.

        :param device_context: a test context for a set of tango devices
        :type device_context: tango.MultiDeviceTestContext
        """
        tile = device_context.get_device("low/elt/tile_1")
        tile.Connect(True)
        time.sleep(1)
        assert tile.fpga1_temperature == 38.0

    def test_fpga2_temperature(self, device_context):
        """
        Test for the fpga2_temperature attribute.

        :param device_context: a test context for a set of tango devices
        :type device_context: tango.MultiDeviceTestContext
        """
        tile = device_context.get_device("low/elt/tile_1")
        tile.Connect(True)
        time.sleep(1)
        assert tile.fpga2_temperature == 37.5
