# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.


"""
MCCS Station.

MccsStation is the Tango device class for the MCCS Station prototype.
"""
__all__ = ["MccsStation", "main"]

import json
import threading
from time import sleep
import tango

# PyTango imports
from tango import DebugIt, EnsureOmniThread, SerialModel, Util, DevFailed
from tango.server import attribute, command, device_property

# additional imports
from ska_tango_base import SKABaseDevice, SKAObsDevice
from ska_tango_base.commands import ResponseCommand, ResultCode
from ska_tango_base.control_model import HealthState

from ska_low_mccs import MccsDeviceProxy
from ska_low_mccs.pool import DevicePool, DevicePoolSequence
import ska_low_mccs.release as release
from ska_low_mccs.events import EventManager
from ska_low_mccs.health import HealthModel
from ska_low_mccs.message_queue import MessageQueue


class MccsStation(SKAObsDevice):
    """
    MccsStation is the Tango device class for the MCCS Station
    prototype.

    This is a subclass of :py:class:`ska_tango_base.SKAObsDevice`.

    **Properties:**

    - Device Property
        StationId
            - MCCS station ID for this station
            - Type: int (scalar attribute)
        APIUFQDNs
            - The FQDN of this station's APIU
            - Type: str (spectrum attribute)
        TileFQDNs
            - List of Tile FQDNs
            - Type: str (spectrum attribute)
        AntennaFQDNs
            - List of Antenna FQDNs
            - Type: str (spectrum attribute)
    """

    # -----------------
    # Device Properties
    # -----------------
    StationId = device_property(dtype=int, default_value=0)
    APIUFQDN = device_property(dtype=str)
    TileFQDNs = device_property(dtype=(str,), default_value=[])
    AntennaFQDNs = device_property(dtype=(str,), default_value=[])

    # ---------------
    # General methods
    # ---------------
    def init_device(self):
        """
        Initialise the device; overridden here to change the Tango
        serialisation model.
        """
        util = Util.instance()
        util.set_serial_model(SerialModel.NO_SYNC)
        super().init_device()

    class InitCommand(SKAObsDevice.InitCommand):
        """
        Class that implements device initialisation for the MCCS Station
        is managed under the hood; the basic sequence is:

        1. Device state is set to INIT
        2. The do() method is run
        3. Device state is set to the appropriate outgoing state,
           usually off
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
            self._message_queue = None
            self._qdebuglock = threading.Lock()

        def do(self):
            """
            Initialises the attributes and properties of the
            :py:class:`.MccsStation`.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            super().do()
            device = self.target
            device.queue_debug = ""
            device._heart_beat = 0
            device._progress = 0
            device._subarray_id = 0
            device._apiu_fqdn = device.APIUFQDN
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

            prerequisite_fqdns = device._tile_fqdns
            if device._apiu_fqdn is not None:
                prerequisite_fqdns.append(device._apiu_fqdn)
            prerequisite_device_pool = DevicePool(
                prerequisite_fqdns, self.logger, connect=False
            )
            antenna_pool = DevicePool(device._antenna_fqdns, self.logger, connect=False)
            device.device_pool = DevicePoolSequence(
                [prerequisite_device_pool, antenna_pool], self.logger, connect=False
            )

            # Start the Message queue for this device
            device._message_queue = MessageQueue(
                target=device, lock=self._qdebuglock, logger=self.logger
            )
            device._message_queue.start()

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
            :type device: :py:class:`ska_tango_base.SKABaseDevice`
            """
            # https://pytango.readthedocs.io/en/stable/howto.html
            # #using-clients-with-multithreading
            with EnsureOmniThread():
                self._initialise_device_pool(device)
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

        def _initialise_device_pool(self, device):
            """
            Initialise power management for this device.

            :param device: the device for which power management is
                being initialised
            :type device: :py:class:`ska_tango_base.SKABaseDevice`
            """
            device.device_pool.connect()

        def _initialise_health_monitoring(self, device):
            """
            Initialise the health model for this device.

            :param device: the device for which the health model is
                being initialised
            :type device: :py:class:`ska_tango_base.SKABaseDevice`
            """
            fqdns = device._tile_fqdns + device._antenna_fqdns
            if device._apiu_fqdn is not None:
                fqdns.append(device._apiu_fqdn)

            device.event_manager = EventManager(self.logger)

            device._health_state = HealthState.UNKNOWN
            device.set_change_event("healthState", True, False)
            device.health_model = HealthModel(
                None, fqdns, device.event_manager, device.health_changed
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

    def delete_device(self):
        """
        Hook to delete resources allocated in the
        :py:meth:`~.MccsStation.InitCommand.do` method of the nested
        :py:class:`~.MccsStation.InitCommand` class.

        This method allows for any memory or other resources allocated
        in the :py:meth:`~.MccsStation.InitCommand.do` method to be
        released. This method is called by the device destructor, and by
        the Init command when the Tango device server is re-initialised.
        """
        self._message_queue.terminate_thread()
        self._message_queue.join()

    # ----------
    # Attributes
    # ----------
    @attribute(dtype="DevULong")
    def aHeartBeat(self):
        """
        Return the Heartbeat attribute value.

        :return: heart beat as a percentage
        """
        return self._heart_beat

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

    @attribute(
        dtype="DevLong",
        format="%i",
        max_value=16,
        min_value=0,
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
            tile = MccsDeviceProxy(fqdn, self.logger)
            tile.subarrayId = subarray_id

    @attribute(
        dtype="DevString",
        format="%s",
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

    @attribute(dtype="DevBoolean")
    def isCalibrated(self):
        """
        Return a flag indicating whether this station is currently
        calibrated or not.

        :return: a flag indicating whether this station is currently
            calibrated or not.
        :rtype: bool
        """
        return self._is_calibrated

    @attribute(dtype="DevBoolean")
    def isConfigured(self):
        """
        Return a flag indicating whether this station is currently
        configured or not.

        :return: a flag indicating whether this station is currently
            configured or not.
        :rtype: bool
        """
        return self._is_configured

    @attribute(
        dtype="DevLong",
        format="%i",
    )
    def calibrationJobId(self):
        """
        Return the calibration job id.

        :return: the calibration job id
        :rtype: int
        """
        return self._calibration_job_id

    @attribute(
        dtype="DevLong",
        format="%i",
    )
    def daqJobId(self):
        """
        Return the DAQ job id.

        :return: the DAQ job id
        :rtype: int
        """
        return self._daq_job_id

    @attribute(
        dtype="DevString",
        format="%s",
    )
    def dataDirectory(self):
        """
        Return the data directory (the parent directory for all files
        generated by this station)

        :return: the data directory
        :rtype: str
        """
        return self._data_directory

    @attribute(
        dtype=("DevString",),
        max_dim_x=8,
        format="%s",
    )
    def beamFQDNs(self):
        """
        Return the FQDNs of station beams associated with this station.

        :return: the FQDNs of station beams associated with this station
        :rtype: list(str)
        """
        return self._beam_fqdns

    @attribute(
        dtype=("DevFloat",),
        max_dim_x=2,
    )
    def delayCentre(self):
        """
        Return the WGS84 position of the delay centre of the station.

        :todo: WGS84 is a datum. What is the coordinate system?
            Latitude and longitude? Or is it SUTM50 eastings and
            northings? Either way, do we need to allow for elevation
            too?

        :return: the WGS84 position of the delay centre of the station
        :rtype: list(float)
        """
        return self._delay_centre

    @delayCentre.write
    def delayCentre(self, value):
        """
        Set the delay centre of the station.

        :param value: WGS84 position
        :type value: list(float)
        """
        self._delay_centre = value

    @attribute(
        dtype=("DevFloat",),
        max_dim_x=512,
    )
    def calibrationCoefficients(self):
        """
        Return the calibration coefficients for the station.

        :todo: How big should this array be? Gain and offset per antenna
            per channel. This station can have up to 16 tiles of up to
            16 antennas, so that is 2 x 16 x 16 = 512 coefficients per
            channel. But how many channels?

        :return: the calibration coefficients
        :rtype: list(float)
        """
        return self._calibration_coefficients

    @attribute(dtype="DevString")
    def aQueueDebug(self):
        """
        Return the queueDebug attribute.

        :return: queueDebug attribute
        """
        return self.queue_debug

    @aQueueDebug.write
    def aQueueDebug(self, debug_string):
        """
        Update the queue debug attribute.

        :param debug_string: the new debug string for this attribute
        :type debug_string: str
        """
        self.queue_debug = debug_string

    @attribute(
        dtype="DevUShort",
        label="Command progress percentage",
        rel_change=2,
        abs_change=5,
        max_value=100,
        min_value=0,
    )
    def commandProgress(self):
        """
        Return the commandProgress attribute value.

        :return: command progress as a percentage
        """
        return self._progress

    # --------
    # Commands
    # --------
    def init_command_objects(self):
        """
        Set up the handler objects for Commands.
        """
        super().init_command_objects()

        args = (self, self.state_model, self.logger)
        self.register_command_object("InitialSetup", self.InitialSetupCommand(*args))
        self.register_command_object("Configure", self.ConfigureCommand(*args))
        self.register_command_object("BTest", self.BTestCommand(*args))
        self.register_command_object("On", self.OnCommand(*args))
        self.register_command_object("OnCallback", self.OnCallbackCommand(*args))

        pool_args = (self.device_pool, self.state_model, self.logger)
        self.register_command_object("Disable", self.DisableCommand(*pool_args))
        self.register_command_object("Standby", self.StandbyCommand(*pool_args))
        self.register_command_object("Off", self.OffCommand(*pool_args))

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    @DebugIt()
    def BTest(self, argin):
        """
        A test command.

        :param argin: Messaging system and command arguments
        :return: A tuple containing a return code and a string
            message indicating status. The message is for information purpose only.
        :rtype:
            (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        kwargs = json.loads(argin)
        fqdn = kwargs.get("respond_to_fqdn")
        cb = kwargs.get("callback")
        (result_code, message, _) = self._message_queue.send_message_with_response(
            command="BTest", respond_to_fqdn=fqdn, callback=cb
        )
        return [[result_code], [message]]

    class BTestCommand(ResponseCommand):
        """
        Class for handling the a test command.
        """

        SUCCEEDED_MESSAGE = "BTest command completed OK"

        def do(self, argin):
            """
            Stateless do hook for implementing the functionality of the
            :py:meth:`.MccsStation.BTest` command.

            :param argin: Messaging system and command arguments
            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            sleep(10)
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    @DebugIt()
    def On(self, json_args):
        """
        Send a message to turn the station on.

        Method returns as soon as the message has been enqueued.

        :param json_args: JSON encoded messaging system and command arguments
        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype:
            (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        self.logger.debug("Send message to Station On")

        # TODO: The callback parameters here could be empty as this "On"
        #       command is used by the StartUp command that is still
        #       executed sequentially.
        kwargs = json.loads(json_args)
        self._on_respond_to_fqdn = kwargs.get("respond_to_fqdn")
        self._on_callback = kwargs.get("callback")

        if self._on_respond_to_fqdn and self._on_callback:
            # We would usually send a message with a response here, but this is a special
            # case because Station has pools of devices. Only when all of the devices in
            # all of the pools complete can we return a message to the caller of Station.
            # Cache "On" command callback arguments
            (
                result_code,
                _,
                message_uid,
            ) = self._message_queue.send_message(command="On")
            # Because the responses back to the requester will be from a callback
            # command, we cache the message uid and return this when the pools are
            # complete.
            self._on_message_uid = message_uid
            return [[result_code], [message_uid]]
        else:
            # Call On sequentially
            handler = self.get_command_object("On")
            (result_code, message) = handler(json_args)
            return [[result_code], [message]]

    class OnCommand(SKABaseDevice.OnCommand):
        """
        Class for handling the On() command.
        """

        QUEUED_MESSAGE = "Station On command queued"
        SUCCEEDED_MESSAGE = "Station On command complete"
        FAILED_MESSAGE = "Station On command failed"

        def do(self, argin):
            """
            Stateless hook implementing the functionality of the
            (inherited) :py:meth:`ska_tango_base.SKABaseDevice.On`
            command for this :py:class:`.MccsStation` device.

            :param argin: JSON encoded messaging system and command arguments
            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            device = self.target
            device_pool = device.device_pool

            if device._on_respond_to_fqdn and device._on_callback:
                # rcltodo: Why doesn't .dev_name() work?
                self.logger.debug(
                    f"Pool invoke_command_with_callback('On', fqdn={device._station_id:03}, 'OnCallback')"
                )
                if device_pool.invoke_command_with_callback(
                    command_name="On",
                    fqdn=f"low-mccs/station/{device._station_id:03}",
                    callback="OnCallback",
                ):
                    return (ResultCode.OK, self.QUEUED_MESSAGE)
                else:
                    self.logger.error('Station device pool "On" command not queued')
                    return (ResultCode.FAILED, self.FAILED_MESSAGE)
            else:
                self.logger.debug("Calling device_pool.on()...")
                if device_pool.on():
                    return (ResultCode.OK, self.SUCCEEDED_MESSAGE)
                else:
                    return (ResultCode.FAILED, self.FAILED_MESSAGE)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    @DebugIt()
    def OnCallback(self, json_args):
        """
        On callback method.

        :param json_args: Argument containing JSON encoded command message and result
        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype:
            (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        self.logger.info(f"Station OnCallback json_args={json_args}")
        (result_code, message, _) = self._message_queue.send_message(
            command="OnCallback", json_args=json_args
        )
        return [[result_code], [message]]

    class OnCallbackCommand(ResponseCommand):
        """
        Class for handling the On Callback command.
        """

        def do(self, argin):
            """
            Stateless do hook for implementing the functionality of the
            :py:meth:`.MccsStation.OnCallback` command.

            :param argin: Argument containing JSON encoded command message and result
            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            device = self.target
            device_pool = device.device_pool

            device.logger.info("Station OnCallbackCommand class do()")
            # Defer callback to our pool device
            (command_complete, result_code, _) = device_pool.on_callback(argin)

            # Cache the original status message from the caller
            kwargs = json.loads(argin)
            status = kwargs.get("status")

            if command_complete:
                # Programming error if these aren't set
                assert device._on_respond_to_fqdn
                assert device._on_callback

                # Post response back to requestor
                try:
                    response_device = tango.DeviceProxy(device._on_respond_to_fqdn)
                except DevFailed:
                    device._qdebug(
                        f"Response device {device._on_respond_to_fqdn} not found"
                    )
                else:
                    # As this response is to the original requestor, we need to reply
                    # with the message ID that was given to the requester
                    message = MessageQueue.Message(
                        command="On",
                        json_args="",
                        message_uid=f"{device._on_message_uid}",
                        notifications=False,
                        respond_to_fqdn="",
                        callback="",
                    )
                    response = {
                        "message_object": message,
                        "result_code": result_code,
                        "status": status,
                    }
                    json_string = json.dumps(response, default=lambda obj: obj.__dict__)
                    # Call the specified command asynchronously
                    (rc, stat) = response_device.command_inout(
                        device._on_callback, json_string
                    )
                    device.logger.debug(
                        f"Station OnCallbackCommand posted message to {response_device},rc={rc},status={stat}"
                    )

                device.logger.debug(
                    f"Station OnCallbackCommand class do(),rc={result_code},status={status}"
                )
                device._on_respond_to_fqdn = None
                device._on_callback = None
                return (result_code, status)
            else:
                device.logger.debug(
                    f"Station OnCallbackCommand class do() STARTED, status={status}"
                )
                return (ResultCode.STARTED, status)

    class OffCommand(SKABaseDevice.OffCommand):
        """
        Class for handling the Off() command.
        """

        SUCCEEDED_MESSAGE = "Off command completed OK"
        FAILED_MESSAGE = "Off command failed"

        def do(self):
            """
            Stateless hook implementing the functionality of the
            (inherited) :py:meth:`ska_tango_base.SKABaseDevice.Off`
            command for this :py:class:`.MccsStation` device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            device_pool = self.target
            if device_pool.off():
                return (ResultCode.OK, self.SUCCEEDED_MESSAGE)
            else:
                return (ResultCode.FAILED, self.FAILED_MESSAGE)

    class StandbyCommand(SKABaseDevice.StandbyCommand):
        """
        Class for handling the Standby() command.
        """

        SUCCEEDED_MESSAGE = "Standby command completed OK"
        FAILED_MESSAGE = "Standby command failed"

        def do(self):
            """
            Stateless hook implementing the functionality of the
            (inherited) :py:meth:`ska_tango_base.SKABaseDevice.Standby`
            command for this :py:class:`.MccsStation` device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            device_pool = self.target

            if device_pool.standby():
                return (ResultCode.OK, self.SUCCEEDED_MESSAGE)
            else:
                return (ResultCode.FAILED, self.FAILED_MESSAGE)

    class DisableCommand(SKABaseDevice.DisableCommand):
        """
        Class for handling the Disable() command.
        """

        SUCCEEDED_MESSAGE = "Disable command completed OK"
        FAILED_MESSAGE = "Disable command failed"

        def do(self):
            """
            Stateless hook implementing the functionality of the
            (inherited) :py:meth:`ska_tango_base.SKABaseDevice.Disable`
            command for this :py:class:`.MccsStation` device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            device_pool = self.target

            if device_pool.disable():
                return (ResultCode.OK, self.SUCCEEDED_MESSAGE)
            else:
                return (ResultCode.FAILED, self.FAILED_MESSAGE)

    class ConfigureCommand(ResponseCommand):
        """
        Class for handling the Configure() command.
        """

        SUCCEEDED_MESSAGE = "Configure command completed OK"
        FAILED_WRONG_STATION_MESSAGE = "Configure failed: wrong station_id"

        def do(self, argin):
            """
            Stateless hook implementing the functionality of the
            :py:meth:`.MccsStation.Configure` command

            :param argin: Configuration specification dict as a json string
            :type argin: str

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            config_dict = json.loads(argin)
            stn_id = config_dict.get("station_id")
            device = self.target
            # Make sure we're configuring the correct station
            if stn_id != device._station_id:
                return (ResultCode.FAILED, self.FAILED_WRONG_STATION_MESSAGE)
            device._is_configured = True
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    def Configure(self, argin):
        """
        Configure the station with all relevant parameters.

        :param argin: Configuration parameters encoded in a json string
        :type argin: str

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/station/01")
        >>> dp.command_inout("Configure", json_str)
        """
        handler = self.get_command_object("Configure")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class InitialSetupCommand(ResponseCommand):
        """
        Class for handling the InitialSetup() command.
        """

        SUCCEEDED_MESSAGE = "InitialSetup command completed OK"

        def do(self):
            """
            Stateless hook implementing the functionality of the
            :py:meth:`.MccsStation.InitialSetup` command

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            device = self.target
            for tile_id, tile in enumerate(device.TileFQDNs):
                proxy = MccsDeviceProxy(tile, self.logger)
                proxy.subarrayId = device._subarray_id
                proxy.stationId = device._station_id
                proxy.logicalTileId = tile_id + 1

            #             self._beams = []
            #             for id, beam in enumerate(self._beam_fqdns):
            #                 proxy = tango.DeviceProxy(beam)
            #                 self._beam.append(proxy)
            #                 proxy.stationId = self.StationId
            #                 proxy.logicalBeamId = id + 1

            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_out="DevVarLongStringArray",
    )
    def InitialSetup(self):
        """
        Initial setup the station.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> dp = tango.DeviceProxy("mccs/station/01")
        >>> dp.command_inout("InitialSetup")
        """
        handler = self.get_command_object("InitialSetup")
        (return_code, message) = handler()
        return [[return_code], [message]]


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
    return MccsStation.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
