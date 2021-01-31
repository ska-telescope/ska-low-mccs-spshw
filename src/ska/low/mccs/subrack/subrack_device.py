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
from ska.low.mccs.subrack.subrack_simulator import SubrackBoardSimulator


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
            simulation_mode == SimulationMode.TRUE
        )
        super().__init__(hardware_factory, SubrackHardwareHealthEvaluator())

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
        :rtype: list of float
        """
        return self._factory.hardware.tpm_temperatures

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
            device.register_command_object("PowerUp", device.PowerUpCommand(*args))
            device.register_command_object("PowerDown", device.PowerDownCommand(*args))

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
        :rtype: list of float
        """
        return self.hardware_manager.tpm_temperatures

    @attribute(dtype=(float,), label="TPM currents", max_dim_x=8)
    def tpmCurrents(self):
        """
        Return the currents of the subrack bays (hence the currents of
        the TPMs housed in those bays).

        :return: the TPM currents
        :rtype: list of float
        """
        return self.hardware_manager.tpm_currents

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
            # because DISABLE is the state of lowest device readiness

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

            success = hardware_manager.on()
            # because the OFF state is a state of high device readiness

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
            return create_return(success, f"TPM {argin} power-on")

    @command(
        dtype_in="DevULong",
        doc_in="logicalTpmId",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
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
