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
from tango.server import attribute, command
from tango import AttrWriteType
from tango import DebugIt

# Additional imports
from ska.base.commands import ResponseCommand, ResultCode
from ska.low.mccs import MccsGroupDevice
from ska.base import SKABaseDevice

# PyTango imports
# import tango
# from tango import DebugIt
# from tango.server import run
# from tango.server import Device
# from tango.server import attribute, command
# from tango.server import device_property
# from tango import AttrQuality, DispLevel, DevState
# from tango import AttrWriteType, PipeWriteType
# import enum
# from MccsGroupDevice import MccsGroupDevice
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

    # ---------------
    # General methods
    # ---------------

    class InitCommand(SKABaseDevice.InitCommand):
        """
        Class that implements device initialisation for the MCCS Group Device

        """

        def do(self):
            """Initialises the attributes and properties of the MccsGroupDevice."""
            super().do()
            device = self.target
            device._voltage = 0.0
            device._current = 0.0
            device._temperature = 0.0
            device._humidity = 0.0
            device._isAlive = True
            device._overCurrentThreshold = 0.0
            device._overVoltageThreshold = 0.0
            device._humidityThreshold = 0.0
            device._logicalAntennaId = [0]
            return (ResultCode.OK, "Init command succeeded")

    def always_executed_hook(self):
        """Method always executed before any TANGO command is executed."""

    def delete_device(self):
        """Hook to delete resources allocated in init_device.

        This method allows for any memory or other resources allocated in the
        init_device method to be released.  This method is called by the device
        destructor and by the device Init command.
        """

    # ----------
    # Attributes
    # ----------

    @attribute(
        dtype="DevDouble",
        access=AttrWriteType.READ_WRITE,
        label="Voltage",
        unit="Volts",
    )
    def voltage(self):
        """Return the voltage attribute."""
        return self._voltage

    @attribute(
        dtype="DevDouble",
        access=AttrWriteType.READ_WRITE,
        label="Current",
        unit="Amps",
    )
    def current(self):
        """Return the current attribute."""
        return self._current

    @attribute(
        dtype="DevDouble",
        access=AttrWriteType.READ_WRITE,
        label="Temperature",
        unit="degC",
    )
    def temperature(self):
        """Return the temperature attribute."""
        return self._temperature

    @attribute(
        dtype="DevDouble",
        access=AttrWriteType.READ_WRITE,
        label="Humidity",
        unit="percent",
        max_value=0,
        min_value=100,
    )
    def humidity(self):
        """Return the humidity attribute."""
        return self._humidity

    @attribute(
        dtype="DevBoolean", access=AttrWriteType.READ_WRITE, label="Is alive?",
    )
    def isAlive(self):
        """Return the isAlive attribute"""
        return self._isAlive

    @attribute(
        dtype="DevDouble",
        access=AttrWriteType.READ_WRITE,
        label="Over current threshold",
        unit="Amp",
    )
    def overCurrentThreshold(self):
        """Return the overCurrentThreshold attribute"""
        return self._overCurrentThreshold

    @attribute(
        dtype="DevDouble",
        access=AttrWriteType.READ_WRITE,
        label="Over Voltage threshold",
        unit="Volt",
    )
    def overVoltageThreshold(self):
        """Return the overVoltageThreshold attribute"""
        return self._overVoltageThreshold

    @attribute(
        dtype="DevDouble",
        access=AttrWriteType.READ_WRITE,
        label="Humidity threshold",
        unit="percent",
    )
    def humidityThreshold(self):
        """Return the humidityThreshold attribute"""
        return self._humidityThreshold

    @attribute(
        dtype=("DevULong",), access=AttrWriteType.READ_WRITE, max_dim_x=100,
    )
    def logicalAntennaId(self):
        """Return the logicalAntennaId attribute"""
        return self._logicalAntennaId

    # --------
    # Commands
    # --------

    def init_command_objects(self):

        """
        Initialises the command handlers for commands supported by this
        device.
        """
        super().init_command_objects()

        args = (self, self.state_model, self.logger)

        self.register_command_object(
            "PowerUpAntenna", self.PowerUpAntennaCommand(*args)
        )
        self.register_command_object(
            "PowerDownAntenna", self.PowerDownAntennaommand(*args)
        )
        self.register_command_object("PowerUp", self.RunCommand(*args))
        self.register_command_object("PowerDown", self.RunCommand(*args))

    class PowerUpAntennaCommand(ResponseCommand):
        def do(self, argin):
            """
            Stateless hook for implementation of ExceptionCallback()
            command functionality.
            """
            # device = self.target
            # logicalAntennaId = argin
            return (ResultCode.OK, "Stub implementation, does nothing")

    @command(
        dtype_in="DevULong",
        doc_in="logicalAntennaId",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def PowerUpAntenna(self, argin):
        handler = self.get_command_object("PowerUpAntenna")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class PowerDownAntennaCommand(ResponseCommand):
        def do(self, argin):
            """
            Stateless hook for implementation of ExceptionCallback()
            command functionality.
            """
            # device = self.target
            # logicalAntennaId = argin
            return (ResultCode.OK, "Stub implementation, does nothing")

    @command(
        dtype_in="DevULong",
        doc_in="logicalAntennaId",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def PowerDownAntenna(self, argin):
        handler = self.get_command_object("PowerDownAntenna")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class PowerUpCommand(ResponseCommand):
        def do(self):
            """
            Stateless hook for implementation of ExceptionCallback()
            command functionality.
            """
            return (ResultCode.OK, "Stub implementation, does nothing")

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def PowerUp(self):
        handler = self.get_command_object("PowerUp")
        (return_code, message) = handler()
        return [[return_code], [message]]

    class PowerDownCommand(ResponseCommand):
        def do(self):
            """
            Stateless hook for implementation of ExceptionCallback()
            command functionality.
            """
            return (ResultCode.OK, "Stub implementation, does nothing")

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def PowerDown(self):
        handler = self.get_command_object("PowerDown")
        (return_code, message) = handler()
        return [[return_code], [message]]


# ----------
# Run server
# ----------


def main(args=None, **kwargs):
    """Main function of the MccsAPIU module."""

    return MccsAPIU.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
