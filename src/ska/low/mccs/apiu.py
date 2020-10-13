# -*- coding: utf-8 -*-
#
# This file is part of the MccsAPIU project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""
This module contains an implementation of the MCCS APIU device and
related classes.
"""

# PyTango imports
from tango.server import attribute, command
from tango import DebugIt

# Additional imports
from ska.base.commands import ResponseCommand, ResultCode

# from ska.low.mccs import MccsGroupDevice

# from ska.low.mccs import MccsDevice
from ska.base import SKABaseDevice

__all__ = ["MccsAPIU", "main"]


class MccsAPIU(SKABaseDevice):
    """
    An implementation of MCCS APIU device.

    This class is a subclass of :py:class:`ska.base.SKABaseDevice`.

    **Properties:**

    - Device Property
    """

    class InitCommand(SKABaseDevice.InitCommand):
        """
        Class that implements device initialisation for the MCCS APIU
        device
        """

        def do(self):
            """
            Initialises the attributes and properties of the
            :py:class:`MccsAPIU`.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`ska.base.commands.ResultCode`, str)
            """
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
            device._logicalAntennaId = []

            device.set_change_event("voltage", True, False)
            device.set_archive_event("voltage", True, False)

            return (ResultCode.OK, "Init command succeeded")

    def always_executed_hook(self):
        """Method always executed before any TANGO command is executed."""

    def delete_device(self):
        """
        Hook to delete resources allocated in the
        :py:meth:`~ska.low.mccs.apiu.MccsAPIU.InitCommand.do` method of the
        nested :py:class:`~ska.low.mccs.apiu.MccsAPIU.InitCommand` class.

        This method allows for any memory or other resources allocated in the
        :py:meth:`~ska.low.mccs.apiu.MccsAPIU.InitCommand.do` method to be
        released. This method is called by the device destructor, and by the Init
        command when the Tango device server is re-initialised.
        """

    # ----------
    # Attributes
    # ----------

    @attribute(dtype="DevDouble", label="Voltage", unit="Volts")
    def voltage(self):
        """
        Return the voltage attribute.

        :return: the voltage attribute
        :rtype: double
        """
        return self._voltage

    @attribute(dtype="DevDouble", label="Current", unit="Amps")
    def current(self):
        """
        Return the current attribute.

        :return: the current value of the current attribute
        :rtype: double
        """
        return self._current

    @attribute(dtype="DevDouble", label="Temperature", unit="degC")
    def temperature(self):
        """
        Return the temperature attribute.

        :return: the value of the temperature attribute
        :rtype: double
        """
        return self._temperature

    @attribute(
        dtype="DevDouble",
        label="Humidity",
        unit="percent",
        # max_value=0.0,
        # min_value=100.0,
    )
    def humidity(self):
        """
        Return the humidity attribute.

        :return: the value of the humidity attribute
        :rtype: double
        """
        return self._humidity

    @attribute(dtype="DevBoolean", label="Is alive?")
    def isAlive(self):
        """
        Return the isAlive attribute

        :return: the value of the isAlive attribute
        :rtype: boolean
        """
        return self._isAlive

    @attribute(dtype="DevDouble", label="Over current threshold", unit="Amp")
    def overCurrentThreshold(self):
        """
        Return the overCurrentThreshold attribute

        :return: the value of the overCurrentThreshold attribute
        :rtype: double
        """
        return self._overCurrentThreshold

    @overCurrentThreshold.write
    def overCurrentThreshold(self, value):
        """
        Set the overCurrentThreshold attribute.

        :param value: new value for the overCurrentThreshold attribute
        :type value: double
        """
        self._overCurrentThreshold = value

    @attribute(dtype="DevDouble", label="Over Voltage threshold", unit="Volt")
    def overVoltageThreshold(self):
        """
        Return the overVoltageThreshold attribute

        :return: the value of the overVoltageThreshold attribute
        :rtype: double
        """
        return self._overVoltageThreshold

    @overVoltageThreshold.write
    def overVoltageThreshold(self, value):
        """
        Set the overVoltageThreshold attribute.

        :param value: new value for the overVoltageThreshold attribute
        :type value: double
        """
        self._overVoltageThreshold = value

    @attribute(dtype="DevDouble", label="Humidity threshold", unit="percent")
    def humidityThreshold(self):
        """
        Return the humidity threshold

        :return: the value of the humidityThreshold attribute
        :rtype: double
        """
        return self._humidityThreshold

    @humidityThreshold.write
    def humidityThreshold(self, value):
        """
        Set the humidityThreshold attribute.

        :param value: new value for the humidityThreshold attribute
        :type value: double
        """
        self._humidityThreshold = value

    @attribute(dtype="DevULong", max_dim_x=100)
    def logicalAntennaId(self):
        """
        Return the logicalAntennaId attribute

        :return: the logical antenna id
        :rtype: int
        """
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
            "PowerDownAntenna", self.PowerDownAntennaCommand(*args)
        )
        self.register_command_object("PowerUp", self.PowerUpCommand(*args))
        self.register_command_object("PowerDown", self.PowerDownCommand(*args))

    class PowerUpAntennaCommand(ResponseCommand):
        def do(self, argin):
            """
            Stateless hook for implementation of
            :py:meth:`MccsAPIU.PowerUpAntenna`
            command functionality.

            :param argin: the logical antenna id of the antenna to power
                up
            :type argin: int

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`ska.base.commands.ResultCode`, str)
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
        """
        Power up the antenna

        :param argin: the logical antenna id of the antenna to power
            up
        :type argin: int

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`ska.base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("PowerUpAntenna")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class PowerDownAntennaCommand(ResponseCommand):
        def do(self, argin):
            """
            Stateless hook for implementation of
            :py:meth:`MccsAPIU.PowerDownAntenna`
            command functionality.

            :param argin: the logical antenna id of the antenna to power
                down
            :type argin: int

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`ska.base.commands.ResultCode`, str)
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
        """
        Power down the antenna

        :param argin: the logical antenna id of the antenna to power
            down
        :type argin: int

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`ska.base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("PowerDownAntenna")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class PowerUpCommand(ResponseCommand):
        """
        Class for handling the PowerUp() command.

        :todo: What is this command supposed to do? It takes no
            argument, and returns nothing.
        """

        def do(self):
            """
            Stateless hook for implementation of
            :py:meth:`MccsAPIU.PowerUp` command
            functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`ska.base.commands.ResultCode`, str)
            """
            return (ResultCode.OK, "Stub implementation, does nothing")

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def PowerUp(self):
        """
        Power up

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`ska.base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("PowerUp")
        (return_code, message) = handler()
        return [[return_code], [message]]

    class PowerDownCommand(ResponseCommand):
        """
        Class for handling the PowerDown() command.

        :todo: What is this command supposed to do? It takes no
            argument, and returns nothing.
        """

        def do(self):
            """
            Stateless hook for implementation of
            :py:meth:`MccsAPIU.PowerDown`
            command functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`ska.base.commands.ResultCode`, str)
            """
            return (ResultCode.OK, "Stub implementation, does nothing")

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def PowerDown(self):
        """
        Power down

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`ska.base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("PowerDown")
        (return_code, message) = handler()
        return [[return_code], [message]]


# ----------
# Run server
# ----------


def main(args=None, **kwargs):
    """
    Main function of the :py:mod:`ska.low.mccs.apiu` module.

    :param args: positional arguments
    :type args: list
    :param kwargs: named arguments
    :type kwargs: dict

    :return: exit code
    :rtype: int
    """

    return MccsAPIU.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
