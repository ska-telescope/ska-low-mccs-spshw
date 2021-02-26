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

from tango import DebugIt, EnsureOmniThread, SerialModel, Util
from tango.server import attribute, command, device_property

from ska.base import SKABaseDevice
from ska.base.commands import BaseCommand, ResponseCommand, ResultCode
from ska.base.control_model import HealthState, SimulationMode
from ska.low.mccs.hardware import (
    HardwareHealthEvaluator,
    OnOffHardwareManager,
    PowerMode,
    SimulableHardwareFactory,
    SimulableHardwareManager,
)
from ska.low.mccs.health import HealthModel
from ska.low.mccs.subrack.subrack_simulator import SubrackBoardSimulator


__all__ = [
    "SubrackHardwareFactory",
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

    At present, this returns a
    :py:class:`~ska.low.mccs.subrack.subrack_simulator.SubrackBoardSimulator`
    object when in simulation mode, and raises
    :py:exc:`NotImplementedError` if the hardware is sought whilst not
    in simulation mode
    """

    def __init__(self, simulation_mode, tpm_count):
        """
        Create a new factory instance.

        :param tpm_count: number of TPMs that are attached to the
            subrack
        :type tpm_count: int
        :param simulation_mode: the initial simulation mode of this
            hardware manager
        :type simulation_mode:
            :py:class:`~ska.base.control_model.SimulationMode`
        """
        self._tpm_count = tpm_count
        super().__init__(simulation_mode)

    def _create_simulator(self):
        """
        Returns a hardware simulator.

        :return: a hardware simulator for the tile
        :rtype:
            :py:class:`.SubrackHardwareSimulator`
        """
        return SubrackBoardSimulator(self._tpm_count)


class SubrackHardwareManager(OnOffHardwareManager, SimulableHardwareManager):
    """
    This class manages MCCS subrack hardware.

    :todo:
    """

    def __init__(
        self, simulation_mode, tpm_count, are_tpms_on_change_callback, _factory=None
    ):
        """
        Initialise a new SubrackHardwareManager instance.

        :param simulation_mode: the initial simulation mode of this
            hardware manager
        :type simulation_mode: :py:class:`~ska.base.control_model.SimulationMode`
        :param tpm_count: number of TPMs that are attached to the
            subrack
        :type tpm_count: int
        :param are_tpms_on_change_callback: a callback to be called when
            the are_tpms_on property changes
        :type are_tpms_on_change_callback: callable
        :param _factory: allows for substitution of a hardware factory.
            This is useful for testing, but generally should not be used
            in operations.
        :type _factory: :py:class:`.SubrackHardwareFactory`
        """
        hardware_factory = _factory or SubrackHardwareFactory(
            simulation_mode == SimulationMode.TRUE, tpm_count
        )
        super().__init__(hardware_factory, SubrackHardwareHealthEvaluator())

        self._are_tpms_on = None
        self._are_tpms_on_change_callback = are_tpms_on_change_callback
        self._update_are_tpms_on()

    @property
    def backplane_temperature(self):
        """
        Return the temperature of this subrack's backplane.

        :return: the backplane temperature, in degrees celcius
        :rtype: float
        """
        return self._factory.hardware.backplane_temperature

    @property
    def board_temperature(self):
        """
        Return the temperature of this subrack's management board.

        :return: the board temperature, in degrees celcius
        :rtype: float
        """
        return self._factory.hardware.board_temperature

    @property
    def board_current(self):
        """
        Return the current of this subrack's management board.

        :return: the board current
        :rtype: float
        """
        return self._factory.hardware.board_current

    @property
    def fan_speed(self):
        """
        Return this subrack's fan speed.

        :return: the fan speed, in RPMs
        :rtype: float
        """
        return self._factory.hardware.fan_speed

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

        :return: a list of bay temperatures, in degrees celcius
        :rtype: list(float)
        """
        return self._factory.hardware.tpm_temperatures

    @property
    def tpm_currents(self):
        """
        Return a list of bay currents for this subrack.

        :return: a list of bay currents
        :rtype: list(float)
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
        self._update_are_tpms_on()
        return self._are_tpms_on is not None and self._are_tpms_on[logical_tpm_id - 1]

    def are_tpms_on(self):
        """
        Returns whether each TPM is powered or not.

        :return: whether each TPM is powered or not.
        :rtype: list(bool)
        """
        self._update_are_tpms_on()
        return self._are_tpms_on

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
        self._update_are_tpms_on()
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
        self._update_are_tpms_on()
        return not self._factory.hardware.is_tpm_on(logical_tpm_id)

    def turn_on_tpms(self):
        """
        Turn on all TPMs.

        :return: whether the action was successful, or None if there was nothing to do
        :rtype: bool
        """
        if all(self.are_tpms_on()):
            return None
        self._factory.hardware.turn_on_tpms()
        self._update_are_tpms_on()
        return all(self.are_tpms_on())

    def turn_off_tpms(self):
        """
        Turn off all TPMs.

        :return: whether the action was successful, or None if there was nothing to do
        :rtype: bool
        """
        if not any(self.are_tpms_on()):
            return None
        self._factory.hardware.turn_off_tpms()
        self._update_are_tpms_on()
        return not any(self.are_tpms_on())

    def _update_are_tpms_on(self):
        """
        Update our record of which TPMs are off/on, ensureing that
        registered callbacks are called.
        """
        are_tpms_on = self._factory.hardware.are_tpms_on()
        if are_tpms_on is None:
            are_tpms_on = [False] * self.tpm_count

        if self._are_tpms_on != are_tpms_on:
            self._are_tpms_on = list(are_tpms_on)
            self._are_tpms_on_change_callback(self._are_tpms_on)

    def poll(self):
        """
        Poll the hardware.
        """
        super().poll()
        self._update_are_tpms_on()


class MccsSubrack(SKABaseDevice):
    """
    An implementation of MCCS Subrack device.

    This class is a subclass of :py:class:`ska.base.SKABaseDevice`.
    """

    TileFQDNs = device_property(dtype=(str,), default_value=[])

    def init_device(self):
        """
        Initialise the device; overridden here to change the Tango
        serialisation model.
        """
        util = Util.instance()
        util.set_serial_model(SerialModel.NO_SYNC)
        super().init_device()

    def init_command_objects(self):
        """
        Initialises the command handlers for commands supported by this
        device.
        """
        # TODO: Technical debt -- forced to register base class stuff rather than
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
            device._tile_fqdns = list(device.TileFQDNs)

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

            device._are_tpms_on = None
            device.set_change_event("areTpmsOn", True, False)

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
            device.hardware_manager = SubrackHardwareManager(
                device._simulation_mode,
                len(device._tile_fqdns),
                device.are_tpms_on_changed,
            )

            args = (device.hardware_manager, device.state_model, self.logger)

            device.register_command_object("Disable", device.DisableCommand(*args))
            device.register_command_object("Standby", device.StandbyCommand(*args))
            device.register_command_object("Off", device.OffCommand(*args))

            device.register_command_object("IsTpmOn", device.IsTpmOnCommand(*args))
            device.register_command_object(
                "PowerOnTpm", device.PowerOnTpmCommand(*args)
            )
            device.register_command_object(
                "PowerOffTpm", device.PowerOffTpmCommand(*args)
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

        def succeeded(self):
            """
            Called when initialisation completes.

            Here we override the base class default implementation to
            ensure that MccsSubrack transitions to a state that reflects
            the state of its hardware
            """
            device = self.target
            if device.hardware_manager.power_mode == PowerMode.OFF:
                action = "init_succeeded_disable"
            else:
                action = "init_succeeded_off"
            self.state_model.perform_action(action)

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
        pass

    # ----------
    # Callbacks
    # ----------
    def are_tpms_on_changed(self, are_tpms_on):
        """
        Callback to be called whenever power to the TPMs changes;
        responsible for updating the tango side of things i.e. making
        sure the attribute is up to date, and events are pushed.

        :param are_tpms_on: whether each TPM is pwoered
        :type are_tpms_on: list(bool)
        """
        if self._are_tpms_on == are_tpms_on:
            return
        self._are_tpms_on = list(are_tpms_on)
        self.push_change_event("areTpmsOn", self._are_tpms_on)

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

    # ----------
    # Attributes
    # ----------

    @attribute(dtype="float", label="Backplane temperature", unit="Celsius")
    def backplaneTemperature(self):
        """
        Return the temperature of the subrack backplane.

        :return: the temperature of the subrack backplane
        :rtype: float
        """
        return self.hardware_manager.backplane_temperature

    @attribute(dtype="float", label="Board temperature", unit="Celsius")
    def boardTemperature(self):
        """
        Return the temperature of the subrack management board.

        :return: the temperature of the subrack management board
        :rtype: float
        """
        return self.hardware_manager.board_temperature

    @attribute(dtype="float", label="Board current")
    def boardCurrent(self):
        """
        Return the subrack management board current.

        :return: the subrack management board current
        :rtype: float
        """
        return self.hardware_manager.board_current

    @attribute(dtype="float", label="Fan speed")
    def fanSpeed(self):
        """
        Return the subrack fan speed.

        :return: the subrack fan speed
        :rtype: float
        """
        return self.hardware_manager.fan_speed

    @attribute(dtype=(float,), label="TPM temperatures", max_dim_x=8)
    def tpmTemperatures(self):
        """
        Return the temperatures of the subrack bays (hence the
        temperatures of the TPMs housed in those bays).

        :return: the TPM temperatures
        :rtype: list(float)
        """
        return self.hardware_manager.tpm_temperatures

    @attribute(dtype=(float,), label="TPM currents", max_dim_x=8)
    def tpmCurrents(self):
        """
        Return the currents of the subrack bays (hence the currents of
        the TPMs housed in those bays).

        :return: the TPM currents
        :rtype: list(float)
        """
        return self.hardware_manager.tpm_currents

    @attribute(dtype=int, label="TPM count")
    def tpmCount(self):
        """
        Return the number of TPMs connected to this subrack.

        :return: the number of TPMs connected to this subrack
        :rtype: int
        """
        return self.hardware_manager.tpm_count

    @attribute(dtype=(bool,), max_dim_x=256, label="Are TPMs On")
    def areTpmsOn(self):
        """
        Return whether each TPM is powered or not.

        The main reason this attribute exists is so that individual Tile
        devices can subscribe to change events on it. From this they can
        figure out when the subrack has turned off/on power to their
        TPM.

        :return: whether each TPM is powered or not
        :rtype: list(bool)
        """
        return self.hardware_manager.are_tpms_on()

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
            success = hardware_manager.off()

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
            # TODO: For now, OFF represents the highest state of device
            # readiness for a device that is not actually on. i.e. state
            # OFF means the hardware is on. This is a
            # counterintuitive mess that will be fixed in SP-1501.
            hardware_manager = self.target
            success = hardware_manager.on()
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
            try:
                return hardware_manager.is_tpm_on(argin)
            except ValueError:
                # The subrack itself is not on. We don't want o
                return None

        def is_allowed(self):
            """
            Whether this command is allowed to run.

            :returns: whether this command is allowed to run
            :rtype: bool
            """
            return self.target.power_mode in [PowerMode.OFF, PowerMode.ON]

    def is_IsTpmOn_allowed(self):
        """
        Whether the ``Reset()`` command is allowed to be run in the
        current state.

        :returns: whether the ``Reset()`` command is allowed to be run in the
            current state
        :rtype: bool
        """
        handler = self.get_command_object("IsTpmOn")
        return handler.is_allowed()

    @command(dtype_in="DevULong", dtype_out=bool)
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
            return create_return(success, f"TPM {argin} power-on")

        def is_allowed(self):
            """
            Whether this command is allowed to run.

            :returns: whether this command is allowed to run
            :rtype: bool
            """
            return self.target.power_mode in [PowerMode.OFF, PowerMode.ON]

    def is_PowerOnTpm_allowed(self):
        """
        Whether the ``PowerOnTpm()`` command is allowed to be run in the
        current state.

        :returns: whether the ``PowerOnTpm()`` command is allowed to be run in the
            current state
        :rtype: bool
        """
        handler = self.get_command_object("PowerOnTpm")
        return handler.is_allowed()

    @command(
        dtype_in="DevULong",
        dtype_out="DevVarLongStringArray",
    )
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
            return create_return(success, f"TPM {argin} power-off")

        def is_allowed(self):
            """
            Whether this command is allowed to run.

            :returns: whether this command is allowed to run
            :rtype: bool
            """
            return self.target.power_mode in [PowerMode.OFF, PowerMode.ON]

    def is_PowerOffTpm_allowed(self):
        """
        Whether the ``PowerOffTpm()`` command is allowed to be run in
        the current state.

        :returns: whether the ``PowerOffTpm()`` command is allowed to be run in the
            current state
        :rtype: bool
        """
        handler = self.get_command_object("PowerOffTpm")
        return handler.is_allowed()

    @command(
        dtype_in="DevULong",
        dtype_out="DevVarLongStringArray",
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
