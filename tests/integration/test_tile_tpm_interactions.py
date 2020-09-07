"""
This module contains tests of MccsTile that requires the presence of a
MccsTpmDeviceSimulator interactions between ska.low.mccs classes,
particularly tango devices.
"""
from ska.low.mccs import MccsTile, MccsTpmDeviceSimulator


devices_info = [
    {
        "class": MccsTile,
        "devices": [{"name": "low/elt/tile_1", "properties": {"AntennasPerTile": "1"}}],
    },
    {
        "class": MccsTpmDeviceSimulator,
        "devices": [{"name": "low/elt/tpmsimulator", "properties": {}}],
    },
]


class TestMccsTile_MccsTpmDevicewSimulator_Integration:
    """
    Integration test cases for the MccsTile's interactions with MccsTpmDeviceSimulator
    """

    def test_voltage(self, device_context):
        """Test for the voltage attribute."""
        tile = device_context.get_device("low/elt/tile_1")
        tile.Connect(False)
        assert tile.voltage == 4.7

    def test_current(self, device_context):
        """Test for the current attribute."""
        tile = device_context.get_device("low/elt/tile_1")
        tile.Connect(False)
        tile.current == 0.4

    def test_board_temperature(self, device_context):
        """Test for the board_temperature attribute."""
        tile = device_context.get_device("low/elt/tile_1")
        tile.Connect(False)
        assert tile.board_temperature == 36.0

    def test_fpga1_temperature(self, device_context):
        """Test for the fpga1_temperature attribute."""
        tile = device_context.get_device("low/elt/tile_1")
        tile.Connect(False)
        assert tile.fpga1_temperature == 38.0

    def test_fpga2_temperature(self, device_context):
        """Test for the fpga2_temperature attribute."""
        tile = device_context.get_device("low/elt/tile_1")
        tile.Connect(False)
        assert tile.fpga2_temperature == 37.5
