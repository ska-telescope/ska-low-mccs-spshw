# -*- coding: utf-8 -*-
#
# This file is part of the MccsStation project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

""" MCCS Station

MccsStation is the Tango device class for the MCCS Station prototype.
"""
__all__ = ["MccsStation", "main"]

import threading

# PyTango imports
import tango
from tango import DebugIt, DevState, EnsureOmniThread
from tango.server import device_property
from tango.server import attribute, command

# additional imports
from ska.base import SKABaseDevice, SKAObsDevice
from ska.base.commands import ResponseCommand, ResultCode
from ska.base.control_model import HealthState

from ska.low.mccs.power import PowerManager, PowerManagerError
import ska.low.mccs.release as release
from ska.low.mccs.utils import LazyInstance
from ska.low.mccs.events import EventManager
from ska.low.mccs.health import HealthModel


class StationHardware:
    """
    A stub class to take the place of actual station hardware
    """

    def __init__(self):
        """
        Initialise a new StationHardware instance
        """
        self._is_on = False

    def off(self):
        """
        Turn me off
        """
        self._is_on = False

    def on(self):
        """
        Turn me on
        """
        self._is_on = True

    @property
    def is_on(self):
        """
        Return whether I am on or off

        :return: whether I am on or off
        :rtype: bool
        """
        return self._is_on


class StationHardwareManager:
    """
    This class manages station hardware.

    :todo: So far all we can do with station hardware is turn it off and
        on. We need to implement monitoring.
    """

    def __init__(self, hardware=None):
        """
        Initialise a new StationHardwareManager instance

        At present, hardware is simulated by stub software, and so the
        only argument is an optional "hardware" instance. In future, its
        arguments will allow connection to the actual hardware

        :param hardware: the hardware itself, defaults to None. This only
            exists to facilitate testing.
        :type hardware: :py:class:`StationHardware`
        """
        self._hardware = StationHardware() if hardware is None else hardware

        # polled hardware attributes
        self._is_on = None

        self._health = None
        self._health_callbacks = []

        self.poll_hardware()

    def off(self):
        """
        Turn the hardware off

        :return: whether successful
        :rtype: boolean, or None if there was nothing to do.
        """
        if not self._hardware.is_on:
            return
        self._hardware.off()
        self.poll_hardware()
        return not self.is_on

    def on(self):
        """
        Turn the hardware on

        :return: whether successful
        :rtype: boolean, or None if there was nothing to do.
        """
        if self._hardware.is_on:
            return
        self._hardware.on()
        self.poll_hardware()
        return self.is_on

    def poll_hardware(self):
        """
        Poll the hardware and update local attributes with values
        reported by the hardware.
        """
        self._is_on = self._hardware.is_on
        self._evaluate_health()

    @property
    def is_on(self):
        """
        Whether the hardware is on or not

        :return: whether the hardware is on or not
        :rtype: boolean
        """
        return self._is_on

    @property
    def health(self):
        """
        The health of the hardware, as evaluated by this manager

        :return: the health of the hardware
        :rtype: :py:class:`ska.base.control_model.HealthState`
        """
        return self._health

    def _evaluate_health(self):
        """
        Evaluate the health of the hardware
        """
        # TODO: look at the polled hardware values and maybe further
        # poke the hardware to check that it is okay. But for now:
        evaluated_health = HealthState.OK

        self._update_health(evaluated_health)

    def _update_health(self, health):
        """
        Update the health of this hardware, ensuring that any registered
        callbacks are called

        :param health: the new health value
        :type health: :py:class:`ska.base.control_model.HealthState`
        """
        if self._health == health:
            return
        self._health = health
        for callback in self._health_callbacks:
            callback(health)

    def register_health_callback(self, callback):
        """
        Register a callback to be called when the health of the hardware
        changes

        :param callback: A callback to be called when the health of the
            hardware changes
        :type callback: callable
        """
        self._health_callbacks.append(callback)
        callback(self._health)


class StationPowerManager(PowerManager):
    """
    This class that implements the power manager for the MCCS Station
    device.
    """

    def __init__(self, hardware_manager, fqdns):
        """
        Initialise a new StationPowerManager

        :param hardware_manager: an object that manages this station's
            hardware
        :type hardware_manager: object
        :param fqdns: the FQDNs of the devices that this controller
            device manages
        :type fqdns: list of string
        """
        super().__init__(
            hardware_manager, [LazyInstance(tango.DeviceProxy, fqdn) for fqdn in fqdns]
        )


class MccsStation(SKAObsDevice):
    """
    MccsStation is the Tango device class for the MCCS Station prototype.

    This is a subclass of :py:class:`ska.base.SKAObsDevice`.

    **Properties:**

    - Device Property
        StationId
            - MCCS station ID for this station
            - Type: int (scalar attribute)
        TileFQDNs
            - List of Tile FQDNs (Fully Qualified Domain Name)
            - Type: str (spectrum attribute)
    """

    # -----------------
    # Device Properties
    # -----------------
    StationId = device_property(dtype=int, default_value=0)
    TileFQDNs = device_property(dtype=(str,))
    AntennaFQDNs = device_property(dtype=(str,))

    # ---------------
    # General methods
    # ---------------

    class InitCommand(SKAObsDevice.InitCommand):
        """
        Class that implements device initialisation for the MCCS
        Station is managed under the hood; the basic sequence is:

        1. Device state is set to INIT
        2. The do() method is run
        3. Device state is set to the appropriate outgoing state,
           usually off
        """

        def __init__(self, target, state_model, logger=None):
            """
            Create a new InitCommand

            :param target: the object that this command acts upon; for
                example, the device for which this class implements the
                command
            :type target: object
            :param state_model: the state model that this command uses
                 to check that it is allowed to run, and that it drives
                 with actions.
            :type state_model: :py:class:`DeviceStateModel`
            :param logger: the logger to be used by this Command. If not
                provided, then a default module logger will be used.
            :type logger: a logger that implements the standard library
                logger interface
            """
            super().__init__(target, state_model, logger)

            self._thread = None
            self._lock = threading.Lock()
            self._interrupt = False

        def do(self):
            """
            Initialises the attributes and properties of the
            `MccsStation`.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`ska.base.commands.ResultCode`, str)
            """
            super().do()
            device = self.target
            device._subarray_id = 0
            device._tile_fqdns = list(device.TileFQDNs)
            device._antenna_fqdns = list(device.AntennaFQDNs)
            device._beam_fqdns = []
            device._transient_buffer_fqdn = ""
            device._delay_centre = []
            device._calibration_coefficients = []
            device._is_calibrated = False
            device._is_configured = False
            device._calibration_job_id = 0
            device._daq_job_id = 0
            device._data_directory = ""

            device._build_state = release.get_release_info()
            device._version_id = release.version
            device._station_id = device.StationId

            device.set_change_event("subarrayId", True, True)
            device.set_archive_event("subarrayId", True, True)
            device.set_change_event("beamFQDNs", True, True)
            device.set_archive_event("beamFQDNs", True, True)
            device.set_change_event("transientBufferFQDN", True, False)
            device.set_archive_event("transientBufferFQDN", True, False)

            fqdns = device._tile_fqdns + device._antenna_fqdns  # + device._beam_fqdns

            self._thread = threading.Thread(
                target=self._initialise_connections, args=(device, fqdns)
            )
            with self._lock:
                self._thread.start()
                return (ResultCode.STARTED, "Init command started")

        def _initialise_connections(self, device, fqdns):
            """
            Thread target for asynchronous initialisation of connections
            to external entities such as hardware and other devices.

            :param device: the device being initialised
            :type device: :py:class:`~ska.base.SKABaseDevice`
            :param fqdns: the fqdns of subservient devices to which
                this device must maintain connections
            :type: list of str
            """
            # https://pytango.readthedocs.io/en/stable/howto.html
            # #using-clients-with-multithreading
            with EnsureOmniThread():
                self._initialise_hardware_management(device)
                if self._interrupt:
                    self._thread = None
                    self._interrupt = False
                    return
                self._initialise_health_monitoring(device, fqdns)
                if self._interrupt:
                    self._thread = None
                    self._interrupt = False
                    return
                self._initialise_power_management(device, fqdns)
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
            connection to that hardware

            :param device: the device for which a connection to the
                hardware is being initialised
            :type device: :py:class:`~ska.base.SKABaseDevice`
            """
            device.hardware_manager = StationHardwareManager()

        def _initialise_health_monitoring(self, device, fqdns):
            """
            Initialise the health model for this device.

            :param device: the device for which the health model is
                being initialised
            :type device: :py:class:`~ska.base.SKABaseDevice`
            :param fqdns: the fqdns of subservient devices for which
                this device monitors health
            :type: list of str
            """
            device.set_change_event("healthState", True, True)
            device.set_archive_event("healthState", True, True)

            device.event_manager = EventManager()
            device.health_model = HealthModel(
                device.hardware_manager,
                fqdns,
                device.event_manager,
                device._update_health_state,
            )

        def _initialise_power_management(self, device, fqdns):
            """
            Initialise power management for this device.

            :param device: the device for which power management is
                being initialised
            :type device: :py:class:`~ska.base.SKABaseDevice`
            :param fqdns: the fqdns of subservient devices for which
                this device manages power
            :type: list of str
            """
            device.power_manager = StationPowerManager(device.hardware_manager, fqdns)

            power_args = (device.power_manager, device.state_model, device.logger)
            device.register_command_object("Off", device.OffCommand(*power_args))
            device.register_command_object("On", device.OnCommand(*power_args))

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
        self.hardware_manager.poll_hardware()

        state = self.get_state()
        if self._is_calibrated and self._is_configured:
            if state == DevState.ALARM:
                self.set_state(DevState.ON)
        else:
            if state == DevState.ON:
                self.set_state(DevState.ALARM)

    def delete_device(self):
        """
        Hook to delete resources allocated in the
        :py:meth:`~ska.low.mccs.station.MccsStation.InitCommand.do` method of the
        nested :py:class:`~ska.low.mccs.station.MccsStation.InitCommand` class.

        This method allows for any memory or other resources allocated in the
        :py:meth:`~ska.low.mccs.station.MccsStation.InitCommand.do` method to be
        released. This method is called by the device destructor, and by the Init
        command when the Tango device server is re-initialised.
        """

    # ----------
    # Attributes
    # ----------
    @attribute(
        dtype="DevLong",
        format="%i",
        max_value=16,
        min_value=0,
        doc="The ID of the Subarray to which this Station is allocated",
    )
    def subarrayId(self):
        """
        Return the subarray id.

        :return: the subarray id
        :rtype: int
        """
        return self._subarray_id

    @subarrayId.write
    @DebugIt()
    def subarrayId(self, subarray_id):
        """
        Set the ID of the Subarray to which this Station is allocated
        Note: ID propogates to each tile in this station too

        :param subarray_id: the new subarray id for this station
        :type subarray_id: int
        """
        self._subarray_id = subarray_id
        for fqdn in self._tile_fqdns:
            tile = tango.DeviceProxy(fqdn)
            tile.subarrayId = subarray_id

    @attribute(
        dtype="DevString",
        format="%s",
        doc="The fully-qualified device name of the 'transient buffer' "
        "TANGO device created by the Station",
    )
    def transientBufferFQDN(self):
        """
        Return the FQDN of the TANGO device that managers the transient
        buffer.

        :return: the FQDN of the TANGO device that managers the
            transient buffer
        :rtype: str
        """
        return self._transient_buffer_fqdn

    @attribute(
        dtype="DevBoolean",
        doc="Defined whether the calibration cycle was successful "
        "(converged, good phase centres)",
        polling_period=1000,
    )
    def isCalibrated(self):
        """
        Return a flag indicating whether this station is currently
            calibrated or not.

        :return: a flag indicating whether this station is currently
            calibrated or not.
        :rtype: boolean
        """
        return self._is_calibrated

    @attribute(
        dtype="DevBoolean",
        doc="True when the Station is configured, False when the Station "
        "is unconfigured or in the process of reconfiguring.",
        polling_period=1000,
    )
    def isConfigured(self):
        """
        Return a flag indicating whether this station is currently
            configured or not.

        :return: a flag indicating whether this station is currently
            configured or not.
        :rtype: boolean
        """
        return self._is_configured

    @attribute(
        dtype="DevLong",
        format="%i",
        doc="The job ID for calibration jobs submitted by this Station",
    )
    def calibrationJobId(self):
        """
        Return the calibration job id

        :return: the calibration job id
        :rtype: int
        """
        return self._calibration_job_id

    @attribute(
        dtype="DevLong",
        format="%i",
        doc="The job ID for DAQ jobs submitted by this Station.",
    )
    def daqJobId(self):
        """
        Return the DAQ job id

        :return: the DAQ job id
        :rtype: int
        """
        return self._daq_job_id

    @attribute(
        dtype="DevString",
        format="%s",
        doc="Parent directory for all files generated by the station.",
    )
    def dataDirectory(self):
        """
        Return the data directory (the parent directory for all files
            generated by this station)

        :return: the data directory
        :rtype: string
        """
        return self._data_directory

    @attribute(
        dtype=("DevString",),
        max_dim_x=8,
        format="%s",
        doc="Array of full-qualified device names for the Station Beams "
        "associated with this Station",
    )
    def beamFQDNs(self):
        """
        Return the FQDNs of station beams associated with this station.

        :return: the FQDNs of station beams associated with this station
        :rtype: array of str
        """
        return self._beam_fqdns

    @attribute(
        dtype=("DevFloat",),
        max_dim_x=2,
        doc="""WGS84 position of the delay centre of the Station.""",
    )
    def delayCentre(self):
        """
        Return the WGS84 position of the delay centre of the station

        :todo: WGS84 is a datum. What is the coordinate system?
            Latitude and longitude? Or is it SUTM50 eastings and
            northings? Either way, do we need to allow for elevation
            too?

        :return: the WGS84 position of the delay centre of the station
        :rtype: array of float
        """
        return self._delay_centre

    @delayCentre.write
    def delayCentre(self, value):
        """
        Set the delay centre of the station

        :param value: WGS84 position
        :type value: array of float
        """
        self._delay_centre = value

    @attribute(
        dtype=("DevFloat",),
        max_dim_x=512,
        doc="""Latest calibration coefficients for the station (split per
        channel/antenna)""",
    )
    def calibrationCoefficients(self):
        """
        Return the calibration coefficients for the station.

        :todo: How big should this array be? Gain and offset per antenna
            per channel. This station can have up to 16 tiles of up to
            16 antennas, so that is 2 x 16 x 16 = 512 coefficients per
            channel. But how many channels?

        :return: the calibration coefficients
        :rtype: array of float
        """
        return self._calibration_coefficients

    # --------
    # Commands
    # --------
    def init_command_objects(self):
        """
        Set up the handler objects for Commands
        """
        # Technical debt -- forced to register base class stuff rather than
        # calling super(), because On() and Off() are registered on a
        # thread, and we don't want the super() method clobbering them
        args = (self, self.state_model, self.logger)
        self.register_command_object("Disable", self.DisableCommand(*args))
        self.register_command_object("Standby", self.StandbyCommand(*args))
        self.register_command_object("Reset", self.ResetCommand(*args))
        self.register_command_object(
            "GetVersionInfo", self.GetVersionInfoCommand(*args)
        )

        self.register_command_object("Configure", self.ConfigureCommand(*args))

    class OnCommand(SKABaseDevice.OnCommand):
        """
        Class for handling the On() command.
        """

        def do(self):
            """
            Stateless do hook for implementing the functionality of the
            :py:meth:`MccsStation.On` command

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`ska.base.commands.ResultCode`, str)
            """
            power_manager = self.target
            try:
                if power_manager.on():
                    return (ResultCode.OK, "On command completed OK")
                else:
                    return (ResultCode.FAILED, "On command failed")
            except PowerManagerError as pme:
                return (ResultCode.FAILED, f"On command failed: {pme}")

    class OffCommand(SKABaseDevice.OffCommand):
        """
        Class for handling the Off() command.
        """

        def do(self):
            """
            Stateless do-hook for implementing the functionality of the
            :py:meth:`MccsStation.Off` command

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`ska.base.commands.ResultCode`, str)
            """
            power_manager = self.target
            try:
                if power_manager.off():
                    return (ResultCode.OK, "Off command completed OK")
                else:
                    return (ResultCode.FAILED, "Off command failed")
            except PowerManagerError as pme:
                return (ResultCode.FAILED, f"Off command failed: {pme}")

    class ConfigureCommand(ResponseCommand):
        """
        Class for handling the Configure() command.
        """

        def do(self):
            """
            Stateless hook implementing the functionality of the
            :py:meth:`MccsStation.Configure` command

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`ska.base.commands.ResultCode`, str)
            """
            device = self.target
            for tile_id, tile in enumerate(device.TileFQDNs):
                proxy = tango.DeviceProxy(tile)
                proxy.subarrayId = device._subarray_id
                proxy.stationId = device._station_id
                proxy.logicalTileId = tile_id + 1
                proxy.command_inout("Connect", True)

            #             self._beams = []
            #             for id, beam in enumerate(self._beam_fqdns):
            #                 proxy = tango.DeviceProxy(beam)
            #                 self._beam.append(proxy)
            #                 proxy.stationId = self.StationId
            #                 proxy.logicalBeamId = id + 1

            device._is_configured = True
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    def Configure(self):
        """
        Configure the station with tiles

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`ska.base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/station/01")
        >>> dp.command_inout("Configure")
        """
        handler = self.get_command_object("Configure")
        (return_code, message) = handler()
        return [[return_code], [message]]

    def _update_health_state(self, health_state):
        """
        Update and push a change event for the healthState attribute

        :param health_state: The new health state
        :type health_state: :py:class:`ska.base.control_model.HealthState`
        """
        self._health_state = health_state
        self.push_change_event("healthState", health_state)
        self.logger.info("health state = " + str(health_state))


# ----------
# Run server
# ----------
def main(args=None, **kwargs):
    """
    Main function of the :py:mod:`ska.low.mccs.station` module.

    :param args: positional arguments
    :type args: list
    :param kwargs: named arguments
    :type kwargs: dict

    :return: exit code
    :rtype: int
    """
    return MccsStation.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
