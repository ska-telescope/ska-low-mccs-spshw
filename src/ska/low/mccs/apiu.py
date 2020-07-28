# -*- coding: utf-8 -*-
#
# This file is part of the MccsAPIU project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

""" MCCS MVP

An implementation of MCCS APIU device
"""

# PyTango imports
import tango
from tango import DebugIt
from tango.server import run
from tango.server import Device
from tango.server import attribute, command
from tango.server import device_property
from tango import AttrQuality, DispLevel, DevState
from tango import AttrWriteType, PipeWriteType
import enum
from MccsGroupDevice import MccsGroupDevice
# Additional import
# PROTECTED REGION ID(MccsAPIU.additionnal_import) ENABLED START #
# PROTECTED REGION END #    //  MccsAPIU.additionnal_import

__all__ = ["MccsAPIU", "main"]


class MccsAPIU(MccsGroupDevice):
    """
    An implementation of MCCS APIU device

    **Properties:**

    - Device Property
    """
    # PROTECTED REGION ID(MccsAPIU.class_variable) ENABLED START #
    # PROTECTED REGION END #    //  MccsAPIU.class_variable

    # -----------------
    # Device Properties
    # -----------------

    # ----------
    # Attributes
    # ----------

    voltage = attribute(
        dtype='DevDouble',
        access=AttrWriteType.READ_WRITE,
        label="Voltage",
        unit="Volts",
    )

    current = attribute(
        dtype='DevDouble',
        access=AttrWriteType.READ_WRITE,
        label="Current",
        unit="Amp",
    )

    temperature = attribute(
        dtype='DevDouble',
        access=AttrWriteType.READ_WRITE,
        label="Temperature",
        unit="degC",
    )

    humidity = attribute(
        dtype='DevDouble',
        access=AttrWriteType.READ_WRITE,
        label="Humidity",
        unit="percent",
        max_value=0,
        min_value=100,
    )

    isAlive = attribute(
        dtype='DevBoolean',
        access=AttrWriteType.READ_WRITE,
        label="Is alive?",
    )

    overCurrentThreshold = attribute(
        dtype='DevDouble',
        access=AttrWriteType.READ_WRITE,
        label="Over current threshold",
        unit="Amp",
    )

    overVoltageThreshold = attribute(
        dtype='DevDouble',
        access=AttrWriteType.READ_WRITE,
        label="Over Voltage threshold",
        unit="Volt",
    )

    humidityThreshold = attribute(
        dtype='DevDouble',
        access=AttrWriteType.READ_WRITE,
        label="Humidity threshold",
        unit="percent",
    )

    logicalAntennaId = attribute(
        dtype=('DevULong',),
        access=AttrWriteType.READ_WRITE,
        max_dim_x=100,
        display_level=DispLevel.EXPERT,
    )

    # ---------------
    # General methods
    # ---------------

    def init_device(self):
        """Initialises the attributes and properties of the MccsAPIU."""
        MccsGroupDevice.init_device(self)
        self.set_change_event("voltage", True, False)
        self.set_archive_event("voltage", True, False)
        self.set_change_event("current", True, False)
        self.set_archive_event("current", True, False)
        self.set_change_event("temperature", True, False)
        self.set_archive_event("temperature", True, False)
        self.set_change_event("humidity", True, False)
        self.set_archive_event("humidity", True, False)
        self.set_change_event("isAlive", True, False)
        self.set_archive_event("isAlive", True, False)
        self.set_change_event("overCurrentThreshold", True, False)
        self.set_archive_event("overCurrentThreshold", True, False)
        self.set_change_event("overVoltageThreshold", True, False)
        self.set_archive_event("overVoltageThreshold", True, False)
        self.set_change_event("humidityThreshold", True, False)
        self.set_archive_event("humidityThreshold", True, False)
        self.set_change_event("logicalAntennaId", True, False)
        self.set_archive_event("logicalAntennaId", True, False)
        # PROTECTED REGION ID(MccsAPIU.init_device) ENABLED START #
        self._voltage = 0.0
        self._current = 0.0
        self._temperature = 0.0
        self._humidity = 0.0
        self._is_alive = False
        self._over_current_threshold = 0.0
        self._over_voltage_threshold = 0.0
        self._humidity_threshold = 0.0
        self._logical_antenna_id = (0,)
        # PROTECTED REGION END #    //  MccsAPIU.init_device

    def always_executed_hook(self):
        """Method always executed before any TANGO command is executed."""
        # PROTECTED REGION ID(MccsAPIU.always_executed_hook) ENABLED START #
        # PROTECTED REGION END #    //  MccsAPIU.always_executed_hook

    def delete_device(self):
        """Hook to delete resources allocated in init_device.

        This method allows for any memory or other resources allocated in the
        init_device method to be released.  This method is called by the device
        destructor and by the device Init command.
        """
        # PROTECTED REGION ID(MccsAPIU.delete_device) ENABLED START #
        # PROTECTED REGION END #    //  MccsAPIU.delete_device
    # ------------------
    # Attributes methods
    # ------------------

    def read_voltage(self):
        # PROTECTED REGION ID(MccsAPIU.voltage_read) ENABLED START #
        """Return the voltage attribute."""
        return self._voltage
        # PROTECTED REGION END #    //  MccsAPIU.voltage_read

    def write_voltage(self, value):
        # PROTECTED REGION ID(MccsAPIU.voltage_write) ENABLED START #
        """Set the voltage attribute."""
        pass
        # PROTECTED REGION END #    //  MccsAPIU.voltage_write

    def read_current(self):
        # PROTECTED REGION ID(MccsAPIU.current_read) ENABLED START #
        """Return the current attribute."""
        return self._current
        # PROTECTED REGION END #    //  MccsAPIU.current_read

    def write_current(self, value):
        # PROTECTED REGION ID(MccsAPIU.current_write) ENABLED START #
        """Set the current attribute."""
        pass
        # PROTECTED REGION END #    //  MccsAPIU.current_write

    def read_temperature(self):
        # PROTECTED REGION ID(MccsAPIU.temperature_read) ENABLED START #
        """Return the temperature attribute."""
        return self._temperature
        # PROTECTED REGION END #    //  MccsAPIU.temperature_read

    def write_temperature(self, value):
        # PROTECTED REGION ID(MccsAPIU.temperature_write) ENABLED START #
        """Set the temperature attribute."""
        pass
        # PROTECTED REGION END #    //  MccsAPIU.temperature_write

    def read_humidity(self):
        # PROTECTED REGION ID(MccsAPIU.humidity_read) ENABLED START #
        """Return the humidity attribute."""
        return self._humidity
        # PROTECTED REGION END #    //  MccsAPIU.humidity_read

    def write_humidity(self, value):
        # PROTECTED REGION ID(MccsAPIU.humidity_write) ENABLED START #
        """Set the humidity attribute."""
        pass
        # PROTECTED REGION END #    //  MccsAPIU.humidity_write

    def read_isAlive(self):
        # PROTECTED REGION ID(MccsAPIU.isAlive_read) ENABLED START #
        """Return the isAlive attribute."""
        return self._is_alive
        # PROTECTED REGION END #    //  MccsAPIU.isAlive_read

    def write_isAlive(self, value):
        # PROTECTED REGION ID(MccsAPIU.isAlive_write) ENABLED START #
        """Set the isAlive attribute."""
        pass
        # PROTECTED REGION END #    //  MccsAPIU.isAlive_write

    def read_overCurrentThreshold(self):
        # PROTECTED REGION ID(MccsAPIU.overCurrentThreshold_read) ENABLED START #
        """Return the overCurrentThreshold attribute."""
        return self._over_current_threshold
        # PROTECTED REGION END #    //  MccsAPIU.overCurrentThreshold_read

    def write_overCurrentThreshold(self, value):
        # PROTECTED REGION ID(MccsAPIU.overCurrentThreshold_write) ENABLED START #
        """Set the overCurrentThreshold attribute."""
        pass
        # PROTECTED REGION END #    //  MccsAPIU.overCurrentThreshold_write

    def read_overVoltageThreshold(self):
        # PROTECTED REGION ID(MccsAPIU.overVoltageThreshold_read) ENABLED START #
        """Return the overVoltageThreshold attribute."""
        return self._over_voltage_threshold
        # PROTECTED REGION END #    //  MccsAPIU.overVoltageThreshold_read

    def write_overVoltageThreshold(self, value):
        # PROTECTED REGION ID(MccsAPIU.overVoltageThreshold_write) ENABLED START #
        """Set the overVoltageThreshold attribute."""
        pass
        # PROTECTED REGION END #    //  MccsAPIU.overVoltageThreshold_write

    def read_humidityThreshold(self):
        # PROTECTED REGION ID(MccsAPIU.humidityThreshold_read) ENABLED START #
        """Return the humidityThreshold attribute."""
        return self._humidity_threshold
        # PROTECTED REGION END #    //  MccsAPIU.humidityThreshold_read

    def write_humidityThreshold(self, value):
        # PROTECTED REGION ID(MccsAPIU.humidityThreshold_write) ENABLED START #
        """Set the humidityThreshold attribute."""
        pass
        # PROTECTED REGION END #    //  MccsAPIU.humidityThreshold_write

    def read_logicalAntennaId(self):
        # PROTECTED REGION ID(MccsAPIU.logicalAntennaId_read) ENABLED START #
        """Return the logicalAntennaId attribute."""
        return self._logical_antenna_id
        # PROTECTED REGION END #    //  MccsAPIU.logicalAntennaId_read

    def write_logicalAntennaId(self, value):
        # PROTECTED REGION ID(MccsAPIU.logicalAntennaId_write) ENABLED START #
        """Set the logicalAntennaId attribute."""
        pass
        # PROTECTED REGION END #    //  MccsAPIU.logicalAntennaId_write

    # --------
    # Commands
    # --------

    @command(
        dtype_in='DevULong',
        doc_in="logicalAntennaId",
    )
    @DebugIt()
    def PowerUpAntenna(self, argin):
        # PROTECTED REGION ID(MccsAPIU.PowerUpAntenna) ENABLED START #
        """
        Powers up an antenna, given logical antenna ID

        :param argin: 'DevULong'
        logicalAntennaId

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  MccsAPIU.PowerUpAntenna

    @command(
        dtype_in='DevULong',
        doc_in="logicalAntennaId",
    )
    @DebugIt()
    def PowerDownAntenna(self, argin):
        # PROTECTED REGION ID(MccsAPIU.PowerDownAntenna) ENABLED START #
        """
        Powers down an antenna, given logical antenna ID

        :param argin: 'DevULong'
        logicalAntennaId

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  MccsAPIU.PowerDownAntenna

    @command(
    )
    @DebugIt()
    def PowerUp(self):
        # PROTECTED REGION ID(MccsAPIU.PowerUp) ENABLED START #
        """
        Powers up the APIU

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  MccsAPIU.PowerUp

    @command(
    )
    @DebugIt()
    def PowerDown(self):
        # PROTECTED REGION ID(MccsAPIU.PowerDown) ENABLED START #
        """
        Powers down the APIU

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  MccsAPIU.PowerDown

# ----------
# Run server
# ----------


def main(args=None, **kwargs):
    """Main function of the MccsAPIU module."""
    # PROTECTED REGION ID(MccsAPIU.main) ENABLED START #
    return run((MccsAPIU,), args=args, **kwargs)
    # PROTECTED REGION END #    //  MccsAPIU.main


if __name__ == '__main__':
    main()
