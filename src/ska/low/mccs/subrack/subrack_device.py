# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""
This module contains an implementation of the MCCS Subrack Management
Board Tango device and related classes.
"""
import threading
import json

from tango import DebugIt, EnsureOmniThread
from tango.server import attribute, command, device_property

from ska.base import SKABaseDevice
from ska.base.commands import BaseCommand, ResponseCommand, ResultCode
from ska.base.control_model import HealthState, SimulationMode
from ska.low.mccs.hardware import (
    HardwareHealthEvaluator,
    OnOffHardwareManager,
    SimulableHardwareFactory,
    SimulableHardwareManager,
)
from ska.low.mccs.health import HealthModel
from ska.low.mccs.power import PowerManager
from ska.low.mccs.subrack.subrack_simulator import SubrackBoardSimulator
from ska.low.mccs.subrack.subrack_driver import SubrackBoardDriver

__all__ = [
    "SubrackHardwareHealthEvaluator",
    "SubrackHardwareManager",
    "MccsSubrack",
    "main",
]


def create_return(success, action):
    """
    Helper function to package up a boolean result into a
    (:py:class:`~ska.base.commands.ResultCode`, message) tuple.

    :param success: whether execution of the action was successful. This
        may be None, in which case the action was not performed due to
        redundancy (i.e. it was already done).
    :type success: bool or None
    :param action: Informal description of the action that the command
        performs, for use in constructing a message
    :type action: str

    :return: A tuple containing a return code and a string
        message indicating status. The message is for
        information purpose only.
    :rtype: (:py:class:`ska.base.commands.ResultCode`, str)

    """
    if success is None:
        return (ResultCode.OK, f"Subrack {action} is redundant")
    elif success:
        return (ResultCode.OK, f"Subrack {action} successful")
    else:
        return (ResultCode.FAILED, f"Subrack {action} failed")


class SubrackHardwareHealthEvaluator(HardwareHealthEvaluator):
    """
    A placeholder for a class that implements a policy by which the
    subrack hardware manager evaluates the health of the subrack
    management board hardware that it manages.

    At present this just inherits from the base class unchanged.

    """

    pass


class SubrackHardwareFactory(SimulableHardwareFactory):
    """
    A hardware factory for Subrack hardware.

    At present, this returns a :py:class:`SubrackSimulator` object when
    in simulation mode, and raises :py:exc:`NotImplementedError` if the
    hardware is sought whilst not in simulation mode

    """

    def __init__(self, simulation_mode):
        """
        Create a new factory instance.

        :param simulation_mode: the initial simulation mode of this
            hardware manager
        :type simulation_mode:
            :py:class:`~ska.base.control_model.SimulationMode`

        """
        super().__init__(simulation_mode)

    def _create_simulator(self):
        """
        Returns a hardware simulator.

        :return: a hardware simulator for the tile
        :rtype:
            :py:class:`.SubrackHardwareSimulator`

        """
        return SubrackBoardSimulator()

    def _create_driver(self):
        """
        Returns a hardware driver.

        :return: a hardware driver for the subrack
        :rtype:
            :py:class:`.SubrackHardwareDriver`

        """
        return SubrackBoardDriver()

class SubrackHardwareManager(OnOffHardwareManager, SimulableHardwareManager):
    """
    This class manages MCCS subrack hardware.

    :todo:

    """

    def __init__(self, simulation_mode, _factory=None):
        """
        Initialise a new SubrackHardwareManager instance.

        :param simulation_mode: the initial simulation mode of this
            hardware manager
        :type simulation_mode: :py:class:`~ska.base.control_model.SimulationMode`

        """
        hardware_factory = _factory or SubrackHardwareFactory(
            simulation_mode == SimulationMode.TRUE #FALSE for the driver?
        )
        super().__init__(hardware_factory, SubrackHardwareHealthEvaluator())

    @property
    def backplane_temperature(self):
        """
        Return the temperature of this subrack's backplane from sensor 1 and 2.

        :return: the backplane temperature, in degrees celsius
        :rtype: list of float

        """
        return self._factory.hardware.backplane_temperature

    @property
    def board_temperature(self):
        """
        Return the temperature of this subrack's management board.

        :return: the board temperature, in degrees celsius, from sensor 1 and 2
        :rtype: list of float

        """
        return self._factory.hardware.board_temperature

    @property
    def board_current(self):
        """
        Return the current of this subrack's management board bays
        (hence the currents of the TPMs housed in those bays).

        :return: the board current
        :rtype: list of float

        """
        return self._factory.hardware.board_current

    @property
    def fan_speed(self):
        """
        Return this subrack's fan speed.

        :return: the fan speed, in RPMs
        :rtype: list of float

        """
        return self._factory.hardware.fan_speed

    @property
    def fan_speed_perc(self):
        """
        Return this subrack's fan speed in  percent

        :return: the fan speed, in percent
        :rtype: list of float

        """
        return self._factory.hardware.fan_speed_perc

    @property
    def fan_mode(self):
        """
        Return the subrack fan Mode .
        :return: subrack fan mode AUTO or MANUAL
        :rtype: str
        """
        return self.hardware_manager.fan_mode

    @property
    def tpm_count(self):
        """
        Return the number of TPMs managed by this subrack.

        :return: the number of TPMs managed by this subrack
        :rtype: int

        """
        return self._factory.hardware.tpm_count

    @property
    def tpm_temperatures(self):
        """
        Return a list of bay temperatures for this subrack.

        :return: a list of bay temperatures, in degrees celsius
        :rtype: list of float

        """
        return self._factory.hardware.tpm_temperatures

    @property
    def tpm_power(self):
        """
        Return a list of bay powers for this subrack.

        :return: a list of bay powers, in Watt
        :rtype: list of float

        """
        return self._factory.hardware.tpm_power

    @property
    def tpm_voltage(self):
        """
        Return a list of bay voltagess for this subrack.

        :return: a list of bay voltages, in volt
        :rtype: list of float

        """
        return self._factory.hardware.tpm_voltage

    @property
    def ps_fanspeed(self):
        """
        Return the ps FanSpeed for this subrack.

        :return: the ps fan speed
        :rtype: list of float

        """
        return self._factory.hardware.tpm_voltage

    @property
    def ps_current(self):
        """
        Return the ps current for this subrack.

        :return: the ps current
        :rtype: list of float
        """
        return self.hardware_manager.ps_current

    @property
    def ps_power(self):
        """
        Return the pps power for this subrack.

        :return: the ps power
        :rtype: list of float
        """
        return self.hardware_manager.ps_power

    @property
    def ps_voltage(self):
        """
        Return the ps voltage for this subrack.

        :return: the ps voltages
        :rtype: list of float
        """
        return self.hardware_manager.ps_voltage

    @property
    def tpm_currents(self):
        """
        Return a list of bay currents for this subrack.

        :return: a list of bay currents
        :rtype: list of float

        """
        return self._factory.hardware.tpm_currents

    def is_tpm_on(self, logical_tpm_id):
        """
        Check whether this subrack is supplying power to a specified
        TPM.

        :param logical_tpm_id: this subrack's internal id for the
            TPM being queried
        :type logical_tpm_id: int

        :return: whether this subrack is supplying power to the specified TPM
        :rtype: bool

        """
        return self._factory.hardware.is_tpm_on(logical_tpm_id)

    def turn_on_tpm(self, logical_tpm_id):
        """
        Turn on a specified TPM.

        :param logical_tpm_id: the subrack's internal id for the
            TPM to be turned on
        :type logical_tpm_id: int

        :return: whether successful, or None if there was nothing to do
        :rtype: bool or None

        """
        if self._factory.hardware.is_tpm_on(logical_tpm_id):
            return None
        self._factory.hardware.turn_on_tpm(logical_tpm_id)
        return self._factory.hardware.is_tpm_on(logical_tpm_id)

    def turn_off_tpm(self, logical_tpm_id):
        """
        Turn off a specified TPM.

        :param logical_tpm_id: the subrack's internal id for the
            TPM to be turned off
        :type logical_tpm_id: int

        :return: whether successful, or None if there was nothing to do
        :rtype: bool or None

        """
        if not self._factory.hardware.is_tpm_on(logical_tpm_id):
            return None
        self._factory.hardware.turn_off_tpm(logical_tpm_id)
        return not self._factory.hardware.is_tpm_on(logical_tpm_id)

    def turn_on_tpms(self):
        """
        Turn on all TPMs.

        :return: whether the action was successful, or None if there was nothing to do
        :rtype: bool

        """
        for logical_tpm_id in range(self.tpm_count):
            if not self._factory.hardware.is_tpm_on(logical_tpm_id):
                break
        else:
            return None

        self._factory.hardware.turn_on_tpms()

        for logical_tpm_id in range(self.tpm_count):
            if not self._factory.hardware.is_tpm_on(logical_tpm_id):
                return False
        return True

    def turn_off_tpms(self):
        """
        Turn off all TPMs.

        :return: whether the action was successful, or None if there was nothing to do
        :rtype: bool

        """
        for logical_tpm_id in range(self.tpm_count):
            if self._factory.hardware.is_tpm_on(logical_tpm_id):
                break
        else:
            return None

        self._factory.hardware.turn_off_tpms()

        for logical_tpm_id in range(self.tpm_count):
            if self._factory.hardware.is_tpm_on(logical_tpm_id):
                return False
        return True

    def set_backplane_fan_speed(self,fan_id,speed_pwn_perc):
        """


        """

        self._factory.hardware.set_backplane_fan_speed(fan_id,speed_pwn_perc)


    def set_fan_mode(self,fan_id,mode):
        """

        """

        self._factory.hardware.set_fan_mode(fan_id,mode)


    def set_ps_fan_speed(state,ps_fan_id,speed_per):
        """

        """
        self._factory.hardware.set_ps_fan_speed(ps_fan_id,speed_per)


class MccsSubrack(SKABaseDevice):
    """
    An implementation of MCCS Subrack device.

    This class is a subclass of :py:class:`ska.base.SKABaseDevice`.

    """

    TileFQDNs = device_property(dtype=(str,))

    def init_command_objects(self):
        """
        Initialises the command handlers for commands supported by this
        device.
        """
        # Technical debt -- forced to register base class stuff rather than
        # calling super(), because Disable(), Standby() and Off() are registered on a
        # thread, and we don't want the super() method clobbering them.
        args = (self, self.state_model, self.logger)
        self.register_command_object("On", self.OnCommand(*args))
        self.register_command_object("Reset", self.ResetCommand(*args))
        self.register_command_object(
            "GetVersionInfo", self.GetVersionInfoCommand(*args)
        )

    class InitCommand(SKABaseDevice.InitCommand):
        """
        Class that implements device initialisation for the MCCS Subrack
        device.
        """

        def __init__(self, target, state_model, logger=None):
            """
            Create a new InitCommand.

            :param target: the object that this command acts upon; for
                example, the device for which this class implements the
                command
            :type target: object
            :param state_model: the state model that this command uses
                 to check that it is allowed to run, and that it drives
                 with actions.
            :type state_model:
                :py:class:`~ska.base.DeviceStateModel`
            :param logger: the logger to be used by this Command. If not
                provided, then a default module logger will be used.
            :type logger: :py:class:`logging.Logger`

            """
            super().__init__(target, state_model, logger)

            self._thread = None
            self._lock = threading.Lock()
            self._interrupt = False

        def do(self):
            """
            Initialises the attributes and properties of the
            :py:class:`.MccsSubrack`.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`ska.base.commands.ResultCode`, str)
            """
            super().do()
            device = self.target

            # TODO: the default value for simulationMode should be
            # FALSE, but we don't have real hardware to test yet, so we
            # can't take our devices out of simulation mode. However,
            # simulationMode is a memorized attribute, and
            # pytango.test_context.MultiDeviceTestContext will soon
            # support memorized attributes. Once it does, we should
            # figure out how to inject memorized values into our real
            # tango deployment, then start honouring the default of
            # FALSE by removing this next line.
            device._simulation_mode = SimulationMode.TRUE
            device.hardware_manager = None

            self._thread = threading.Thread(
                target=self._initialise_connections, args=(device,)
            )
            with self._lock:
                self._thread.start()
                return (ResultCode.STARTED, "Init command started")

        def _initialise_connections(self, device):
            """
            Thread target for asynchronous initialisation of connections
            to external entities such as hardware and other devices.

            :param device: the device being initialised
            :type device: :py:class:`~ska.base.SKABaseDevice`

            """
            # https://pytango.readthedocs.io/en/stable/howto.html
            # #using-clients-with-multithreading
            with EnsureOmniThread():
                self._initialise_hardware_management(device)
                if self._interrupt:
                    self._thread = None
                    self._interrupt = False
                    return
                self._initialise_health_monitoring(device)
                if self._interrupt:
                    self._thread = None
                    self._interrupt = False
                    return
                self._initialise_power_management(device)
                if self._interrupt:
                    self._thread = None
                    self._interrupt = False
                    return
                with self._lock:
                    self.succeeded()

        def _initialise_hardware_management(self, device):
            """
            Initialise the connection to the hardware being managed by
            this device. May also register commands that depend upon a
            connection to that hardware.

            :param device: the device for which a connection to the
                hardware is being initialised
            :type device: :py:class:`~ska.base.SKABaseDevice`

            """
            device.hardware_manager = SubrackHardwareManager(device._simulation_mode)
            device.hardware_manager.on()

            args = (device.hardware_manager, device.state_model, self.logger)

            device.register_command_object("IsTpmOn", device.IsTpmOnCommand(*args))
            device.register_command_object(
                "PowerOnTpm", device.PowerOnTpmCommand(*args)
            )
            device.register_command_object(
                "PowerOffTpm", device.PowerOffTpmCommand(*args)
            )
            device.register_command_object("PowerUp", device.PowerUpCommand(*args))
            device.register_command_object("PowerDown", device.PowerDownCommand(*args))
            device.register_command_object(
                "SetBackplnFanSpeed", device.SetBackplnFanSpeedCommand(*args)
                )
            device.register_command_object(
                "SetFanMode", device.SetFanModeCommand(*args)
                )
            device.register_command_object(
                "SetPSFanSpeed", device.SetPSFanSpeedCommand(*args)
                )

        def _initialise_health_monitoring(self, device):
            """
            Initialise the health model for this device.

            :param device: the device for which the health model is
                being initialised
            :type device: :py:class:`~ska.base.SKABaseDevice`

            """
            device._health_state = HealthState.UNKNOWN
            device.set_change_event("healthState", True, False)
            device.health_model = HealthModel(
                device.hardware_manager,
                None,
                None,
                device.health_changed,
            )

        def _initialise_power_management(self, device):
            """
            Initialise power management for this device.

            :param device: the device for which power management is
                being initialised
            :type device: :py:class:`~ska.base.SKABaseDevice`

            """
            device.power_manager = PowerManager(device.hardware_manager, None)
            power_args = (device.power_manager, device.state_model, device.logger)
            device.register_command_object(
                "Disable", device.DisableCommand(*power_args)
            )
            device.register_command_object(
                "Standby", device.StandbyCommand(*power_args)
            )
            device.register_command_object("Off", device.OffCommand(*power_args))

        def interrupt(self):
            """
            Interrupt the initialisation thread (if one is running)

            :return: whether the initialisation thread was interrupted
            :rtype: bool

            """
            if self._thread is None:
                return False
            self._interrupt = True
            return True

    def always_executed_hook(self):
        """
        Method always executed before any TANGO command is executed.
        """
        if self.hardware_manager is not None:
            self.hardware_manager.poll()

    def delete_device(self):
        """
        Hook to delete resources allocated in the
        :py:meth:`~.MccsSubrack.InitCommand.do` method of the nested
        :py:class:`~.MccsSubrack.InitCommand` class.

        This method allows for any memory or other resources allocated
        in the :py:meth:`~.MccsSubrack.InitCommand.do` method to be
        released. This method is called by the device destructor, and by
        the Init command when the Tango device server is re-initialised.
        """

    # ----------
    # Attributes
    # ----------

    def health_changed(self, health):
        """
        Callback to be called whenever the HealthModel's health state
        changes; responsible for updating the tango side of things i.e.
        making sure the attribute is up to date, and events are pushed.

        :param health: the new health value
        :type health: :py:class:`~ska.base.control_model.HealthState`

        """
        if self._health_state == health:
            return
        self._health_state = health
        self.push_change_event("healthState", health)

    @attribute(dtype="Devfloat",max_dim_x=2, label="Backplane temperature", unit="Celsius",
               doc="get backplane temperature from sensor 1 and sensor 2")
    def backplaneTemperature(self):
        """
        Return the temperature of the subrack backplane.

        :return: the temperature of the subrack backplane
        :rtype: list of float
        """
        return self.hardware_manager.backplane_temperature

    @attribute(dtype="Devfloat",max_dim_x=2, label="Subrack board temperature", unit="Celsius",
               doc="get subrack-management temperature from sensor 1 and sensor 2")
    def boardTemperature(self):
        """
        Return the temperature of the subrack management board.

        :return: the temperature of the subrack management board
        :rtype: float

        """
        return self.hardware_manager.board_temperature

    @attribute(dtype="Devfloat",max_dim_x=8, label="Board current",
               doc="Method to get current consumption in Ampere for each TPM in "
                   "each slot of subrack, values read from TPM control "
                   "chip on backplane board")
    def boardCurrent(self):
        """
        Return the currents of the subrack bays (hence the currents of
        the TPMs housed in those bays).

        :return: the TPM currents
        :rtype: list of float

        """
        return self.hardware_manager.board_current

    @attribute(dtype="Devfloat",max_dim_x=4, label="Subrack fans speed (RPM)",
               doc="Rotation speed in RPM of each fan of subrack")
    def SubrackFanSpeed(self):
        """
        Return the subrack fan speed.

        :return: the subrack fan speed
        :rtype: list of float

        """
        return self.hardware_manager.fan_speed

    @attribute(dtype="Devfloat", max_dim_x=4, label="Subrack fans speed (%)",
               doc="PWM in percentage of each Fan of Subrack")
    def SubrackFanSpeedperc(self):
        """
        Return the subrack fan speed.

        :return: the subrack fan speed in percent
        :rtype: list of float

        """
        return self.hardware_manager.fan_speed_perc

    @attribute(dtype="DevString",max_dim_x=4,label="Subrack Fan Mode",
        doc="Operation mode of each Fan of Subrack: AUTO or MANUAL")
    def subrackFanMode(self):
        """
        Return the subrackFansMode attribute.
        :return: the subrack fan mode
        :rtype: str
        """
        return self.hardware_manager.fan_mode

    @attribute(dtype="Devfloat", label="TPM temperatures", max_dim_x=8)
    def tpmTemperatures(self):
        """
        Return the temperatures of the subrack bays (hence the
        temperatures of the TPMs housed in those bays).

        :return: the TPM temperatures
        :rtype: list of float

        """
        return self.hardware_manager.tpm_temperatures

    @attribute(dtype="DevFloat",max_dim_x=8,label="TPM power",
        doc="Method to get power consumption of selected tpm")
    def tpmPower(self):
        """
        Return the tpmPower attribute.
        :return: the TPM powers
        :rtype: list of float
        """
        return self.hardware_manager.tpm_power

    @attribute(dtype="DevFloat",max_dim_x=8,label="TPM voltage",
        doc="Method to get voltage consumption of selected tpm")
    def tpmVoltage(self):
        """
        Return the tpmVoltage attribute.
        :return: the TPM voltages
        :rtype: list of float
        """
        return self.hardware_manager.tpm_voltage

    @attribute(dtype="DevFloat",max_dim_x=3,label="PS fan speed",
        doc="Method to get the power supply fan speed")
    def psFanSpeed(self):
        """
        Return the psFanSpeed attribute.
        :return: the ps fan speed
        :rtype: list of float
        """
        return self.hardware_manager.ps_fanspeed

    @attribute(dtype="DevFloat",max_dim_x=3,label="PS current",
               doc="Method to get the power supply current")
    def psIout(self):
        """
        Return the ps Iout attribute.
        :return: the ps current
        :rtype: list of float
        """
        return self.hardware_manager.ps_current

    @attribute(dtype="DevFloat",max_dim_x=3,label="PS Power",
        doc="Method to get the PS power")
    def psPout(self):
        """
        Return the psPout attribute.
        :return: the ps power
        :rtype: list of float
        """
        return self.hardware_manager.ps_power

    @attribute(dtype="DevFloat",max_dim_x=3,label="PS voltage",
               doc="Method to get the power supply voltage")
    def psVout(self):
        """
        Return the psVout attribute.
        :return: the ps voltages
        :rtype: list of float
        """
        return self.hardware_manager.ps_voltage

    # --------
    # Commands
    # --------

    class DisableCommand(SKABaseDevice.DisableCommand):
        """
        Class for handling the Disable() command.

        :todo: We assume for now that the Subrack hardware has control of
            its own power mode i.e. is able to turn itself off and on.
            Actually it is more likely that some upstream hardware would
            turn the subrack off and on, in which case this command would be
            implemented by passing the command to the tango device that manages
            the upstream hardware

        """

        def do(self):
            """
            Stateless hook implementing the functionality of the
            (inherited) :py:meth:`ska.base.SKABaseDevice.Disable`
            command for this :py:class:`.MccsSubrack` device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

            """
            hardware_manager = self.target
            success = (
                hardware_manager.off()
            )  # because DISABLE is the state of lowest device readiness
            return create_return(success, "disable")

    class StandbyCommand(SKABaseDevice.StandbyCommand):
        """
        Class for handling the Standby() command.

        Actually the subrack hardware has no standby mode, so when this
        device is told to go to standby mode, it switches on / remains
        on.

        :todo: We assume for now that the subrack hardware has control of
            its own power mode i.e. is able to turn itself off and on.
            Actually it is more likely that some upstream hardware would
            turn the subrack off and on, in which case this command would
            be implemented by passing the command to the tango device
            that manages the upstream hardware.

        """

        def do(self):
            """
            Stateless hook implementing the functionality of the
            (inherited) :py:meth:`ska.base.SKABaseDevice.Standby`
            command for this :py:class:`.MccsSubrack` device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

            """
            hardware_manager = self.target
            success = hardware_manager.on()
            return create_return(success, "standby")

    class OffCommand(SKABaseDevice.OffCommand):
        """
        Class for handling the Off() command.

        :todo: We assume for now that the subrack hardware has control of
            its own power mode i.e. is able to turn itself off and on.
            Actually it is more likely that some upstream hardware
            would turn the subrack off and on, in which case this command
            would be implemented by passing the command to the tango
            device that manages the upstream hardware.

        """

        def do(self):
            """
            Stateless hook implementing the functionality of the
            (inherited) :py:meth:`ska.base.SKABaseDevice.Off` command
            for this :py:class:`.MccsSubrack` device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

            """
            hardware_manager = self.target
            success = (
                hardware_manager.on()
            )  # because the OFF state is a state of high device readiness
            return create_return(success, "off")

    class IsTpmOnCommand(BaseCommand):
        """
        The command class for the IsTpmOn command.
        """

        def do(self, argin):
            """
            Stateless hook for implementation of
            :py:meth:`.MccsSubrack.IsTpmOn` command functionality.

            :param argin: the logical tpm id of the TPM to power
                up
            :type argin: int

            :return: whether the specified TPM is on or not
            :rtype: bool
            """
            hardware_manager = self.target
            return hardware_manager.is_tpm_on(argin)

    @command(dtype_in="DevULong", doc_in="logicalTpmId", dtype_out=bool)
    @DebugIt()
    def IsTpmOn(self, argin):
        """
        Power up the TPM.

        :param argin: the logical TPM id of the TPM to power
            up
        :type argin: int

        :return: whether the specified TPM is on or not
        :rtype: bool

        """
        handler = self.get_command_object("IsTpmOn")
        return handler(argin)

    class PowerOnTpmCommand(ResponseCommand):
        """
        The command class for the PowerOnTpm command.
        """

        def do(self, argin):
            """
            Stateless hook for implementation of
            :py:meth:`.MccsSubrack.PowerOnTpm`
            command functionality.

            :param argin: the logical TPM id of the TPM to power
                up
            :type argin: int

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            success = hardware_manager.turn_on_tpm(argin)
            return create_return(success, f"TPM {argin} power-up")

    @command(dtype_in="DevULong",doc_in="logicalTpmId",dtype_out="DevVarLongStringArray",
             doc_out="(ResultCode, 'informational message')")
    @DebugIt()
    def PowerOnTpm(self, argin):
        """
        Power up the TPM.

        :param argin: the logical id of the TPM to power
            up
        :type argin: int

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

        """
        handler = self.get_command_object("PowerOnTpm")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class PowerOffTpmCommand(ResponseCommand):
        """
        The command class for the PowerOffTpm command.
        """

        def do(self, argin):
            """
            Stateless hook for implementation of
            :py:meth:`.MccsSubrack.PowerOffTpm`
            command functionality.

            :param argin: the logical id of the TPM to power
                down
            :type argin: int

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            success = hardware_manager.turn_off_tpm(argin)
            print(f"success: {success}")
            return create_return(success, f"TPM {argin} power-down")

    @command(
        dtype_in="DevULong",
        doc_in="logicalTpmId",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def PowerOffTpm(self, argin):
        """
        Power down the TPM.

        :param argin: the logical id of the TPM to power
            down
        :type argin: int

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

        """
        handler = self.get_command_object("PowerOffTpm")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class PowerUpCommand(ResponseCommand):
        """
        Class for handling the PowerUp() command.

        The PowerUp command turns on all of the TPMs that are powered by
        this subrack.

        """

        def do(self):
            """
            Stateless hook for implementation of
            :py:meth:`.MccsSubrack.PowerUp` command
            functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            success = hardware_manager.turn_on_tpms()
            return create_return(success, "power-up")

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def PowerUp(self):
        """
        Power up.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

        """
        handler = self.get_command_object("PowerUp")
        (return_code, message) = handler()
        return [[return_code], [message]]

    class PowerDownCommand(ResponseCommand):
        """
        Class for handling the PowerDown() command.

        The PowerDown command turns off all of the TPMs that are powered
        by this subrack.

        """

        def do(self):
            """
            Stateless hook for implementation of
            :py:meth:`.MccsSubrack.PowerDown`
            command functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            success = hardware_manager.turn_off_tpms()
            return create_return(success, "power-down")

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def PowerDown(self):
        """
        Power down.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

        """
        handler = self.get_command_object("PowerDown")
        (return_code, message) = handler()
        return [[return_code], [message]]

    class SetBackplnFanSpeedCommand(ResponseCommand):
        """
        Class for handling the SetBackplnFanSpeed() command.
        This command set the backplane fan speed.
        """

        def do(self,argin):
            """
            Hook for implementation of
            :py:meth:`.MccsSubrack.SetBackplnFanSpeed`
            command functionality.
            
            :param argin: a JSON-encoded dictionary of arguments
            :type argin: str
            
            :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
            :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)
            
            :raises ValueError: if the JSON input lacks
            mandatory parameters
            """
            hardware_manager = self.target
            
            params = json.loads(argin)
            fan_id = params.get("FanID", None)
            speed_pwm_perc = params.get("SpeedPWN%", None)
            if fan_id or speed_pwm_perc is None:
                self.logger.error("fan_ID and fan speed are mandatory parameters")
                raise ValueError("fan_ID and fan speed are mandatory parameters")
            
            hardware_manager.set_backplane_fan_speed(fan_id,speed_pwn_perc)
            message = 'Set backplane fan speed command completed'
            return create_return(success, message)

    @command(
        dtype_in='DevString',
        doc_in="json dictionary with keywords:\n"
               "fan_id, speed_pwm_perc",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def SetBackplnFanSpeed(self, argin):
        """
        :param argin: json dictionary with mandatory keywords:

        * fan_id - (int) id of the selected fan accepted value: 1-4
        * speed_pwm_perc - (int) percentage value of fan RPM(MIN 0=0% - MAX 100=100%) 

        :type argin: str

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)
        
        """
        handler = self.get_command_object("SetBackplnFanSpeed")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class SetFanModeCommand(ResponseCommand):
        """
        Class for handling the SetFanMode() command.
        
        This command can set the selected fan to manual or auto mode.
        
        """
        def do(self,argin):
            """ 
            Hook for the implementation of
            py:meth:`.MccsSubrack.SetFanMode`
            command functionality.
            
            :param argin: a JSON-encoded dictionary of arguments
            :type argin: str
            
            :return: A tuple containing a return code and a string
                    message indicating status. The message is for
                    information purpose only.
            :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)
            :raises ValueError: if the JSON input lacks of mandatory parameters
            
            """
            hardware_manager = self.target
            params = json.loads(argin)
            fan_id = params.get("fan_id",None)
            mode =    params.get("mode",None)
            if fan_id or mode is None:
                self.logger.error("Fan_id and mode are mandatory parameters")
                raise ValueError("Fan_id and mode are mandatory parameter")
            
            hardware_manager.set_fan_mode(fan_id,mode)
            return (ResultCode.OK, "SetFanMode command completed")
            
    @command(
            dtype_in='DevString',
            doc_in="json dictionary with keywords:\n"
            "fan_id,auto_mode",
            dtype_out="DevVarLongStringArray",
            doc_out="(ResultCode, 'informational message')",
        )
    @DebugIt()
    def SetFanMode(self, argin):
        """
        Set Fan Operational Mode: 1 AUTO, 0 MANUAL
        
        :param argin: json dictionary with mandatory keywords:

        *fan_id - (int) id of the selected fan accepted value: 1-4
        *mode - (int) 1 AUTO, 0 MANUAL

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("SetFanMode")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class SetPSFanSpeed(ResponseCommand):
        """
        Class for handling the SetPSFanSpeed command.
        This command set the selected power supply fan speed.
        """
        def do(self,argin):
            """
            Hook for the implementation of
            py:meth:`.MccsSubrack.SetPSFanSpeed`
            command functionality.
            
            :param argin: a JSON-encoded dictionary of arguments
            :type argin: str
            
            :return: A tuple containing a return code and a string
                    message indicating status. The message is for
                    information purpose only.
            :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)
            :raises ValueError: if the JSON input lacks of mandatory parameters            
            """
            hardware_manager = self.target
            
            params = json.loads(argin)
            ps_fan_id = params.get("ps_fan_id",None)
            speed_per = params.get("speed_%",None)
            if ps_fan_id or mode is None:
                self.logger.error("ps_fan_id and speed_per are mandatory parameters")
                raise ValueError("ps_fan_id and speed_per are mandatory parameters")
            
            hardware_manager.set_ps_fan_speed(ps_fan_id,speed_per)
            return (ResultCode.OK, "SetPSFanSpeed command completed")
    @command(
        dtype_in='DevString',
        doc_in="json dictionary with keywords:\n"
        "ps_fan_id,speed_per",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def SetPSFanSpeed(self, argin):
        """
        Set the selected power supply fan speed

        :param argin: json dictionary with mandatory keywords:
        
        *ps_id - (int) power supply id from 0 to 2
        *speed_per - (int) fanspeed in percent

        :type argin: str

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("SetPSFanSpeed")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    def _update_health_state(self, health_state):
        """
        Update and push a change event for the healthState attribute.

        :param health_state: The new health state
        :type health_state: :py:class:`ska.base.control_model.HealthState`

        """
        self.push_change_event("healthState", health_state)
        self._health_state = health_state
        self.logger.info("health state = " + str(health_state))


# ----------
# Run server
# ----------


def main(args=None, **kwargs):
    """
    Entry point for module.

    :param args: positional arguments
    :type args: list
    :param kwargs: named arguments
    :type kwargs: dict

    :return: exit code
    :rtype: int

    """

    return MccsSubrack.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
