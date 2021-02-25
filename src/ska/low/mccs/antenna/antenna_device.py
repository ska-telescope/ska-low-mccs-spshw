# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""
This module contains an implementation of the SKA Low MCCS Antenna
Device Server, based on the architecture in SKA-TEL-LFAA-06000052-02.
"""
__all__ = [
    "AntennaApiuProxy",
    "AntennaTileProxy",
    "AntennaHardwareFactory",
    "AntennaHardwareHealthEvaluator",
    "AntennaHardwareManager",
    "MccsAntenna",
    "main",
]

import threading

from tango import DevFailed, DevState, EnsureOmniThread
from tango.server import attribute, device_property, AttrWriteType

from ska_tango_base import SKABaseDevice
from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import HealthState, SimulationMode

from ska.low.mccs.events import EventManager, EventSubscriptionHandler
from ska.low.mccs.hardware import (
    HardwareHealthEvaluator,
    HardwareFactory,
    OnOffHardwareManager,
    PowerMode,
)
from ska.low.mccs.health import HealthModel
from ska.low.mccs.utils import backoff_connect, tango_raise


def create_return(success, action):
    """
    Helper function to package up a boolean result into a
    (:py:class:`~ska_tango_base.commands.ResultCode`, message) tuple.

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
    :rtype: (:py:class:`ska_tango_base.commands.ResultCode`, str)
    """
    if success is None:
        return (ResultCode.OK, f"Antenna {action} is redundant")
    elif success:
        return (ResultCode.OK, f"Antenna {action} successful")
    else:
        return (ResultCode.FAILED, f"Antenna {action} failed")


class AntennaHardwareHealthEvaluator(HardwareHealthEvaluator):
    """
    A placeholder for a class that implements a policy by which the
    antenna hardware manager evaluates the health of its hardware.

    At present this just inherits from the base class unchanged.
    """

    def evaluate_health(self, hardware):
        """
        Evaluate the health of the "hardware".

        :param hardware: the "hardware" for which health is being
            evaluated
        :type hardware:
            :py:class:`~ska.low.mccs.hardware.HardwareDriver`

        :return: the evaluated health of the hardware
        :rtype: :py:class:`~ska_tango_base.control_model.HealthState`
        """
        return HealthState.OK


class AntennaApiuProxy:
    """
    A proxy to the APIU.

    The MccsAntenna device server manages antenna hardware, but
    indirectly, via the MccsAPIU and MccsTile devices. This class is a
    proxy to the APIU device that the MccsAntenna can use to drive the
    antenna hardware
    """

    def __init__(self, apiu_fqdn, logical_antenna_id, logger, power_callback):
        """
        Initialise a new APIU proxy instance.

        :param apiu_fqdn: the FQDN of the APIU
        :type apiu_fqdn: str
        :param logical_antenna_id: this antenna's id within the APIU
        :type logical_antenna_id: int
        :param logger: the logger to be used by this object.
        :type logger: :py:class:`logging.Logger`
        :param power_callback: to be called when the power mode of the
            antenna changes
        :type power_callback: callable

        :raises AssertionError: if parameters are out of bounds
        """
        self._logger = logger
        self._power_callback = power_callback

        assert (
            logical_antenna_id > 0
        ), "An APIU's logical antenna id must be positive integer."
        self._logical_antenna_id = logical_antenna_id
        self._apiu = backoff_connect(apiu_fqdn, logger, wait=True)

        self._power_mode = self._read_power_mode()
        self._power_callback(self._power_mode)

        self.apiu_event_handler = EventSubscriptionHandler(
            self._apiu, apiu_fqdn, "areAntennasOn", logger
        )
        self.apiu_event_handler.register_callback(self._apiu_power_changed)

    def on(self):
        """
        Turn the antenna on (by telling the APIU to turn the right
        antenna on)

        :raises NotImplementedError: if a device returns a ResultCode
            other than STARTED or FAILED

        :return: whether the command was successful, or None if there
            was nothing to do
        :rtype: bool
        """
        if self._power_mode == PowerMode.ON:
            return None  # already off

        [[result_code], [_]] = self._apiu.PowerUpAntenna(self._logical_antenna_id)
        if result_code == ResultCode.OK:
            self._update_power_mode(PowerMode.ON)
            return True
        elif result_code == ResultCode.FAILED:
            return False
        else:
            raise NotImplementedError(
                f"APIU.PowerUpAntenna returned unexpected ResultCode {result_code}."
            )

    def off(self):
        """
        Turn the antenna off (by telling the APIU to turn the right
        antenna off)

        :raises NotImplementedError: if a device returns a ResultCode
            other than STARTED or FAILED

        :return: whether the command was successful, or None if there
            was nothing to do
        :rtype: bool
        """
        if self._power_mode == PowerMode.OFF:
            return None  # already off

        [[result_code], [_]] = self._apiu.PowerDownAntenna(self._logical_antenna_id)
        if result_code == ResultCode.OK:
            self._update_power_mode(PowerMode.OFF)
            return True
        elif result_code == ResultCode.FAILED:
            return False
        else:
            raise NotImplementedError(
                f"APIU.PowerDownAntenna returned unexpected ResultCode {result_code}."
            )

    @property
    def power_mode(self):
        """
        Return the power mode of this antenna.

        :return: the power mode of this antenna
        :rtype: :py:class:`~ska.low.mccs.hardware.PowerMode`
        """
        return self._power_mode

    @property
    def current(self):
        """
        This antenna's current.

        :return: the current of this antenna
        :rtype: float
        """
        return self._apiu.get_antenna_current(self._logical_antenna_id)

    @property
    def voltage(self):
        """
        This antenna's voltage.

        :return: the voltage of this antenna
        :rtype: float
        """
        return self._apiu.get_antenna_voltage(self._logical_antenna_id)

    @property
    def temperature(self):
        """
        This antenna's temperature.

        :return: the temperature of this antenna
        :rtype: float
        """
        return self._apiu.get_antenna_temperature(self._logical_antenna_id)

    def _apiu_power_changed(self, event_name, event_value, event_quality):
        """
        Callback that this device registers with the event manager, so
        that it is informed when the APIU power changes.

        Because events may be delayed, a rapid off-on command sequence
        can result in an "off" event arriving after the on() command has
        been executed. We therefore don't put our full trust in these
        events.

        :param event_name: name of the event; will always be
            "areAntennasOn" for this callback
        :type event_name: str
        :param event_value: the new attribute value
        :type event_value: list(bool)
        :param event_quality: the quality of the change event
        :type event_quality: :py:class:`tango.AttrQuality`
        """
        assert event_name.lower() == "areAntennasOn".lower(), (
            "APIU 'areAntennasOn' attribute changed callback called but "
            f"event_name is {event_name}."
        )

        according_to_event = (
            PowerMode.ON if event_value[self._logical_antenna_id - 1] else PowerMode.OFF
        )
        according_to_command = self._read_power_mode()
        if according_to_event != according_to_command:
            self._logger.warning(
                f"Received a Antenna power change event for {according_to_event.name} "
                f"but a manual read says {according_to_command.name}; discarding."
            )
        self._update_power_mode(according_to_command)

    def _read_power_mode(self):
        """
        Helper method to read and interpret the power mode of the
        hardware.

        :return: the power mode of the hardware
        :rtype: :py:class:`ska.low.mccs.hardware.PowerMode`
        """
        try:
            apiu_state = self._apiu.state()
        except DevFailed:
            return PowerMode.UNKNOWN

        if apiu_state == DevState.DISABLE:
            return PowerMode.OFF
        elif apiu_state not in [DevState.OFF, DevState.ON]:
            return PowerMode.UNKNOWN

        try:
            is_antenna_on = self._apiu.IsAntennaOn(self._logical_antenna_id)
        except DevFailed:
            return PowerMode.UNKNOWN

        return PowerMode.ON if is_antenna_on else PowerMode.OFF

    def _update_power_mode(self, power_mode):
        """
        Update the power mode, ensuring that callbacks are called.

        :param power_mode: the power mode of the hardware
        :type power_mode: :py:class:`ska.low.mccs.hardware.PowerMode`
        """
        if self._power_mode != power_mode:
            self._power_mode = power_mode
            self._power_callback(power_mode)


class AntennaTileProxy:
    """
    A proxy to the Tile.

    The MccsAntenna device server manages antenna hardware, but
    indirectly, via the MccsAPIU and MccsTile devices. This class is a
    proxy to the MccsTile device that the MccsAntenna can use to drive
    the antenna hardware. At present it is an unused, unimplemented
    placeholder.
    """

    def __init__(self, tile_fqdn, logical_antenna_id, logger):
        """
        Create a new Tile proxy instance.

        :param tile_fqdn: the FQDN of the tile that manages the antenna
            hardware for this antenna device
        :type tile_fqdn: str
        :param logical_antenna_id: this antenna's id in tile
        :type logical_antenna_id: int
        :param logger: the logger to be used by this object.
        :type logger: :py:class:`logging.Logger`

        :raises AssertionError: if parameters are out of bounds
        """
        self._logger = logger

        assert (
            logical_antenna_id > 0
        ), "An APIU's logical antenna id must be positive integer."
        self._logical_antenna_id = logical_antenna_id
        self._tile = backoff_connect(tile_fqdn, logger)


class AntennaHardwareFactory(HardwareFactory):
    """
    A factory that returns a hardware driver for the antenna hardware...

    though really it returns a proxy to the APIU.
    """

    def __init__(
        self,
        apiu_fqdn,
        logical_apiu_antenna_id,
        power_callback,
        logger,
    ):
        """
        Create a new antenna hardware factory instance.

        :param apiu_fqdn: the FQDN of the APIU to which the antenna is
            attached
        :type apiu_fqdn: str
        :param logical_apiu_antenna_id: the APIU's id for this antenna
        :type logical_apiu_antenna_id: int
        :param power_callback: to be called when the power mode of the
            antenna changes
        :type power_callback: callable
        :param logger: the logger to be used by this object.
        :type logger: :py:class:`logging.Logger`
        """
        self._logger = logger
        self._hardware = AntennaApiuProxy(
            apiu_fqdn, logical_apiu_antenna_id, logger, power_callback
        )

    @property
    def hardware(self):
        """
        Return an antenna hardware driver created by this factory... but
        really a proxy to the APIU.

        :return: an antenna hardware driver created by this factory
        :rtype: :py:class:`.AntennaApiuProxy`
        """
        return self._hardware


class AntennaHardwareManager(OnOffHardwareManager):
    """
    This class manages antenna hardware.

    :todo: So far this antenna hardware manager can only manage antenna
        hardware via the APIU e.g. attributes voltage, current and
        temperature. It also needs to manage antenna attributes via the
        tile.
    """

    def __init__(
        self,
        apiu_fqdn,
        logical_apiu_antenna_id,
        tile_fqdn,
        logical_tile_antenna_id,
        power_callback,
        logger,
        _factory=None,
    ):
        """
        Initialise a new AntennaHardwareManager instance.

        :param apiu_fqdn: the FQDN of the APIU to which the antenna is
            attached
        :type apiu_fqdn: str
        :param logical_apiu_antenna_id: the APIU's id for this antenna
        :type logical_apiu_antenna_id: int
        :param tile_fqdn: the FQDN of the tile to which the antenna is
            attached.
        :type tile_fqdn: str
        :param logical_tile_antenna_id: the tile's id for this antenna
        :type logical_tile_antenna_id: int
        :param power_callback: to be called when the power mode of the
            antenna changes
        :type power_callback: callable
        :param logger: the logger to be used by this object.
        :type logger: :py:class:`logging.Logger`
        :param _factory: allows for substitution of a hardware factory.
            This is useful for testing, but generally should not be used
            in operations.
        :type _factory: :py:class:`.AntennaHardwareFactory`
        """
        super().__init__(
            _factory
            or AntennaHardwareFactory(
                apiu_fqdn,
                logical_apiu_antenna_id,
                power_callback,
                logger,
            ),
            AntennaHardwareHealthEvaluator(),
        )
        self._antenna_tile_proxy = (
            AntennaTileProxy(tile_fqdn, logical_tile_antenna_id, logger)
            if tile_fqdn is not None
            else None
        )

    @property
    def voltage(self):
        """
        The voltage of the hardware.

        :return: the voltage of the hardware
        :rtype: float
        """
        return self._factory.hardware.voltage

    @property
    def current(self):
        """
        The current of the hardware.

        :return: the current of the hardware
        :rtype: float
        """
        return self._factory.hardware.current

    @property
    def temperature(self):
        """
        Return the temperature of the hardware.

        :return: the temperature of the hardware
        :rtype: float
        """
        return self._factory.hardware.temperature


class MccsAntenna(SKABaseDevice):
    """
    An implementation of the Antenna Device Server for the MCCS based
    upon architecture in SKA-TEL-LFAA-06000052-02.

    This class is a subclass of
    :py:class:`ska_tango_base.SKABaseDevice`.
    """

    # -----------------
    # Device Properties
    # -----------------
    ApiuId = device_property(dtype=int)
    LogicalApiuAntennaId = device_property(dtype=int)
    TileId = device_property(dtype=int)
    LogicalTileAntennaId = device_property(dtype=int)

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

    # ---------------
    # General methods
    # ---------------
    class InitCommand(SKABaseDevice.InitCommand):
        """
        Initialises the command handlers for commands supported by this
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
                :py:class:`~ska_tango_base.DeviceStateModel`
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
            Stateless hook for device initialisation: initialises the
            attributes and properties of the :py:class:`.MccsAntenna`.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
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

            device._antennaId = 0
            device._gain = 0.0
            device._rms = 0.0
            device._xPolarisationFaulty = False
            device._yPolarisationFaulty = False
            device._fieldNodeLongitude = 0.0
            device._fieldNodeLatitude = 0.0
            device._altitude = 0.0
            device._xDisplacement = 0.0
            device._yDisplacement = 0.0
            device._timestampOfLastSpectrum = ""
            device._logicalAntennaId = 0
            device._xPolarisationScalingFactor = [0]
            device._yPolarisationScalingFactor = [0]
            device._calibrationCoefficient = [0.0]
            device._pointingCoefficient = [0.0]
            device._spectrumX = [0.0]
            device._spectrumY = [0.0]
            device._position = [0.0]
            device._delays = [0.0]
            device._delayRates = [0.0]
            device._bandpassCoefficient = [0.0]
            device._first = True

            event_names = [
                "voltage",
                "temperature",
                "xPolarisationFaulty",
                "yPolarisationFaulty",
            ]
            for name in event_names:
                device.set_change_event(name, True, True)
                device.set_archive_event(name, True, True)

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
            :type device: :py:class:`~ska_tango_base.SKABaseDevice`
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
                    self._thread = None
                    self._interrupt = False

        def _initialise_hardware_management(self, device):
            """
            Initialise the connection to the hardware being managed by
            this device. May also register commands that depend upon a
            connection to that hardware.

            :param device: the device for which a connection to the
                hardware is being initialised
            :type device: :py:class:`~ska_tango_base.SKABaseDevice`
            """
            apiu_fqdn = f"low-mccs/apiu/{device.ApiuId:03}"
            tile_fqdn = (
                f"low-mccs/tile/{device.TileId:04}"
                if device.TileId is not None
                else None
            )

            device.hardware_manager = AntennaHardwareManager(
                apiu_fqdn,
                device.LogicalApiuAntennaId,
                tile_fqdn,
                device.LogicalTileAntennaId,
                device.power_changed,
                self.logger,
            )
            hardware_args = (device.hardware_manager, device.state_model, self.logger)
            device.register_command_object("Reset", device.ResetCommand(*hardware_args))
            device.register_command_object(
                "Disable", device.DisableCommand(*hardware_args)
            )
            device.register_command_object(
                "Standby", device.StandbyCommand(*hardware_args)
            )
            device.register_command_object("Off", device.OffCommand(*hardware_args))

        def _initialise_health_monitoring(self, device):
            """
            Initialise the health model for this device.

            :param device: the device for which the health model is
                being initialised
            :type device: :py:class:`~ska_tango_base.SKABaseDevice`
            """
            device.event_manager = EventManager(self.logger)

            device._health_state = HealthState.UNKNOWN
            device.set_change_event("healthState", True, False)
            device.health_model = HealthModel(
                device.hardware_manager,
                None,
                device.event_manager,
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
            ensure that MccsTile transitions to a state that reflects
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
        :py:meth:`~.MccsAntenna.InitCommand.do` method of the nested
        :py:class:`~.MccsAntenna.InitCommand` class.

        This method allows for any memory or other resources allocated
        in the :py:meth:`~.MccsAntenna.InitCommand.do` method to be
        released. This method is called by the device destructor, and by
        the Init command when the Tango device server is re-initialised.
        """
        pass

    # ----------
    # Callbacks
    # ----------

    def health_changed(self, health):
        """
        Callback to be called whenever the HealthModel's health state
        changes; responsible for updating the tango side of things i.e.
        making sure the attribute is up to date, and events are pushed.

        :param health: the new health value
        :type health: :py:class:`~ska_tango_base.control_model.HealthState`
        """
        if self._health_state == health:
            return
        self._health_state = health
        self.push_change_event("healthState", health)

    def power_changed(self, power_mode):
        """
        Callback to be called whenever the AntennaHardwareManager's
        record of the power mode of the antenna hardware changes;
        responsible for updating the tango side of things i.e. making
        sure the attribute is up to date, and events are pushed.

        :todo: There's way too much explicit management of state in this
            callback. We need to get this into the state machine so we
            can simply
            ``self.state_model.perform_action("antenna_was_turned_off")``.

        :param power_mode: the new power_mode
        :type power_mode: :py:class:`~ska.low.mccs.hardware.PowerMode`
        """
        if self.get_state() == DevState.INIT:
            # Don't respond to power mode changes while initialising.
            # We'll worry about it when it comes time to transition out
            # of INIT.
            return

        # TODO: For now, we need to get our devices to OFF state
        # (the highest state of device readiness for a device that
        # isn't actually on) before we can put them into ON state.
        # This is a counterintuitive mess that will be fixed in
        # SP-1501.
        if power_mode == PowerMode.UNKNOWN:
            self.state_model.perform_action("fatal_error")
        elif power_mode == PowerMode.OFF:
            if self.get_state() == DevState.ON:
                self.state_model.perform_action("off_succeeded")
            self.state_model.perform_action("disable_succeeded")
        elif power_mode == PowerMode.ON:
            self.state_model.perform_action("off_succeeded")

    # ----------
    # Attributes
    # ----------

    # override from base classes so that it can be stored in the hardware manager
    @attribute(dtype=SimulationMode, access=AttrWriteType.READ_WRITE, memorized=True)
    def simulationMode(self):
        """
        Return the simulation mode of this device.

        :return: the simulation mode of this device
        :rtype: :py:class:`~ska_tango_base.control_model.SimulationMode`
        """
        return SimulationMode.FALSE

    @simulationMode.write
    def simulationMode(self, value):
        """
        Set the simulation mode of this device.

        :param value: the new simulation mode
        :type value: :py:class:`~ska_tango_base.control_model.SimulationMode`
        """
        if value == SimulationMode.TRUE:
            tango_raise(
                "Antennas cannot be put into simulation mode, but entire APIUs can."
            )

    @attribute(dtype="int", label="AntennaID")
    def antennaId(self):
        """
        Return the antenna ID attribute.

        :return: antenna ID
        :rtype: int
        """
        return self._antennaId

    @attribute(dtype="float", label="gain")
    def gain(self):
        """
        Return the gain attribute.

        :return: the gain
        :rtype: float
        """
        return self._gain

    @attribute(dtype="float", label="rms")
    def rms(self):
        """
        Return the measured RMS of the antenna.

        :return: the measured rms
        :rtype: float
        """
        return self._rms

    @attribute(
        dtype="float",
        label="voltage",
        unit="volts",
        abs_change=0.05,
        min_value=2.5,
        max_value=5.5,
        min_alarm=2.75,
        max_alarm=5.45,
        polling_period=1000,
    )
    def voltage(self):
        """
        Return the voltage attribute.

        :return: the voltage
        :rtype: float
        """
        return self.hardware_manager.voltage

    @attribute(dtype="float", label="current", unit="amperes", polling_period=1000)
    def current(self):
        """
        Return the current attribute.

        :return: the current
        :rtype: float
        """
        return self.hardware_manager.current

    @attribute(dtype="float", label="temperature", unit="DegC")
    def temperature(self):
        """
        Return the temperature attribute.

        :return: the temperature
        :rtype: float
        """
        return self.hardware_manager.temperature

    @attribute(dtype="bool", label="xPolarisationFaulty", polling_period=1000)
    def xPolarisationFaulty(self):
        """
        Return the xPolarisationFaulty attribute.

        :return: the x-polarisation faulty flag
        :rtype: bool
        """
        return self._xPolarisationFaulty

    @attribute(dtype="bool", label="yPolarisationFaulty", polling_period=1000)
    def yPolarisationFaulty(self):
        """
        Return the yPolarisationFaulty attribute.

        :return: the y-polarisation faulty flag
        :rtype: bool
        """
        return self._yPolarisationFaulty

    @attribute(
        dtype="float",
        label="fieldNodeLongitude",
    )
    def fieldNodeLongitude(self):
        """
        Return the fieldNodeLongitude attribute.

        :return: the Longitude of field node centre
        :rtype: float
        """
        return self._fieldNodeLongitude

    @attribute(
        dtype="float",
        label="fieldNodeLatitude",
    )
    def fieldNodeLatitude(self):
        """
        Return the fieldNodeLatitude attribute.

        :return: the Latitude of field node centre
        :rtype: float
        """
        return self._fieldNodeLongitude

    @attribute(dtype="float", label="altitude", unit="meters")
    def altitude(self):
        """
        Return the altitude attribute.

        :return: the altitude of the antenna
        :rtype: float
        """
        return self._altitude

    @attribute(
        dtype="float",
        label="xDisplacement",
        unit="meters",
    )
    def xDisplacement(self):
        """
        Return the Horizontal displacement attribute.

        :return: the horizontal displacement from field node centre
        :rtype: float
        """
        return self._xDisplacement

    @attribute(
        dtype="float",
        label="yDisplacement",
        unit="meters",
    )
    def yDisplacement(self):
        """
        Return the vertical displacement attribute.

        :return: the vertical displacement from field node centre
        :rtype: float
        """
        return self._yDisplacement

    @attribute(dtype="str", label="timestampOfLastSpectrum")
    def timestampOfLastSpectrum(self):
        """
        Return the timestampOfLastSpectrum attribute.

        :return: the timestamp of the last spectrum
        :rtype: str
        """
        return self._timestampOfLastSpectrum

    @attribute(
        dtype="int",
        label="logicalAntennaId",
    )
    def logicalAntennaId(self):
        """
        Return the logical antenna ID attribute.

        :return: the logical antenna ID
        :rtype: int
        """
        return self._logicalAntennaId

    @attribute(dtype=("int",), max_dim_x=100, label="xPolarisationScalingFactor")
    def xPolarisationScalingFactor(self):
        """
        Return the logical antenna ID attribute.

        :return: the x polarisation scaling factor
        :rtype: list(int)
        """
        return self._xPolarisationScalingFactor

    @attribute(dtype=("int",), max_dim_x=100, label="yPolarisationScalingFactor")
    def yPolarisationScalingFactor(self):
        """
        Return the yPolarisationScalingFactor attribute.

        :return: the y polarisation scaling factor
        :rtype: list(int)
        """
        return self._yPolarisationScalingFactor

    @attribute(
        dtype=("float",),
        max_dim_x=100,
        label="calibrationCoefficient",
    )
    def calibrationCoefficient(self):
        """
        Return theCalibration coefficient to be applied for the next
        frequency channel in the calibration cycle.

        :return: the calibration coefficients
        :rtype: list(float)
        """
        return self._calibrationCoefficient

    @attribute(dtype=("float",), max_dim_x=100)
    def pointingCoefficient(self):
        """
        Return the pointingCoefficient attribute.

        :return: the pointing coefficients
        :rtype: list(float)
        """
        return self._pointingCoefficient

    @attribute(dtype=("float",), max_dim_x=100, label="spectrumX")
    def spectrumX(self):
        """
        Return the spectrumX attribute.

        :return: x spectrum
        :rtype: list(float)
        """
        return self._spectrumX

    @attribute(dtype=("float",), max_dim_x=100, label="spectrumY")
    def spectrumY(self):
        """
        Return the spectrumY attribute.

        :return: y spectrum
        :rtype: list(float)
        """
        return self._spectrumY

    @attribute(dtype=("float",), max_dim_x=100, label="position")
    def position(self):
        """
        Return the position attribute.

        :return: positions
        :rtype: list(float)
        """
        return self._position

    @attribute(
        dtype=("float",),
        max_dim_x=100,
        label="delays",
    )
    def delays(self):
        """
        Return the delays attribute.

        :return: delay for each beam
        :rtype: list(float)
        """
        return self._delays

    @attribute(
        dtype=("float",),
        max_dim_x=100,
        label="delayRates",
    )
    def delayRates(self):
        """
        Return the delayRates attribute.

        :return: delay rate for each beam
        :rtype: list(float)
        """
        return self._delayRates

    @attribute(
        dtype=("float",),
        max_dim_x=100,
        label="bandpassCoefficient",
    )
    def bandpassCoefficient(self):
        """
        Return the bandpassCoefficient attribute.

        :return: bandpass coefficients
        :rtype: list(float)
        """
        return self._bandpassCoefficient

    # --------
    # Commands
    # --------
    class DisableCommand(SKABaseDevice.DisableCommand):
        """
        Class for handling the Disable() command.
        """

        def do(self):
            """
            Stateless hook implementing the functionality of the
            (inherited) :py:meth:`ska_tango_base.SKABaseDevice.Disable`
            command for this :py:class:`.MccsAntenna` device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            success = hardware_manager.off()
            return create_return(success, "disable")

    class StandbyCommand(SKABaseDevice.StandbyCommand):
        """
        Class for handling the Standby() command.

        Actually the Antenna hardware has no standby mode, so when this
        device is told to go to standby mode, it switches on / remains
        on.
        """

        def do(self):
            """
            Stateless hook implementing the functionality of the
            (inherited) :py:meth:`ska_tango_base.SKABaseDevice.Standby`
            command for this :py:class:`.MccsAntenna` device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            success = hardware_manager.on()
            return create_return(success, "standby")

    class OffCommand(SKABaseDevice.OffCommand):
        """
        Class for handling the Off() command.
        """

        def do(self):
            """
            Stateless hook implementing the functionality of the
            (inherited) :py:meth:`ska_tango_base.SKABaseDevice.Off`
            command for this :py:class:`.MccsAntenna` device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            hardware_manager = self.target
            success = hardware_manager.on()
            return create_return(success, "off")

    class ResetCommand(SKABaseDevice.ResetCommand):
        """
        Command class for the Reset() command.
        """

        def do(self):
            """
            Stateless hook implementing the functionality of the
            (inherited) :py:meth:`ska_tango_base.SKABaseDevice.Reset`
            command for this :py:class:`.MccsAntenna` device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """

            (result_code, message) = super().do()
            # MCCS-specific Reset functionality goes here
            return (result_code, message)


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
    return MccsAntenna.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
