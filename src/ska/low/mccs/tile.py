# -*- coding: utf-8 -*-
#
# This file is part of the MccsTile project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

""" SKA MCCS Tile Device Server

The Tile Device represents the TANGO interface to a Tile (TPM) unit
"""
__all__ = ["MccsTile", "main"]

import json
import numpy as np
import threading
import time

# PyTango imports
from tango import DebugIt, DevState, AttrQuality
from tango import GreenMode
from tango.server import attribute, command
from tango.server import device_property
from tango import futures_executor

# Additional import

# from ska.low.mccs import MccsGroupDevice
from ska.low.mccs.tpm_simulator import TpmSimulator
from ska.base import SKABaseDevice
from ska.base.control_model import HealthState, SimulationMode, TestMode, LoggingLevel
from ska.base.commands import BaseCommand, ResponseCommand, ResultCode


class MccsTile(SKABaseDevice):
    """
    The Tile Device represents the TANGO interface to a Tile (TPM) unit

    **Properties:**

    - Device Property
    """

    green_mode = GreenMode.Futures

    # -----------------
    # Device Properties
    # -----------------
    TileId = device_property(dtype=int, default_value=0)
    TileIP = device_property(dtype=str, default_value="0.0.0.0")
    TpmCpldPort = device_property(dtype=int, default_value=20000)
    LmcIp = device_property(dtype=str, default_value="0.0.0.0")
    DstPort = device_property(dtype=int, default_value=30000)
    AntennasPerTile = device_property(dtype=int, default_value=16)

    # ---------------
    # General methods
    # ---------------

    class InitCommand(SKABaseDevice.InitCommand):
        """
        Class that implements device initialisation for the MCCS Tile
        State is managed under the hood; the basic sequence is:

        1. Device state is set to INIT
        2. The do() method is run
        3. Device state is set to the appropriate outgoing state,
           usually off

        """

        def do(self):
            """Initialises the attributes and properties of the Mccs Tile."""
            (result_code, message) = super().do()
            device = self.target
            device.logger.LoggingLevel = LoggingLevel.ERROR
            device._ip_address = device.TileIP
            device._port = device.TpmCpldPort
            device._lmc_ip = device.LmcIp
            device._lmc_port = device.DstPort
            device._antennas_per_tile = device.AntennasPerTile

            device._programmed = False
            device._tile_id = device.TileId
            device._subarray_id = 0
            device._station_id = 0
            device._logical_tile_id = 0
            device._csp_destination_ip = ""
            device._csp_destination_mac = ""
            device._csp_destination_port = 0
            device._firmware_name = ""
            device._firmware_version = ""
            device._voltage = 0.0
            device._current = 0.0
            device._board_temperature = 0.0
            device._fpga1_temperature = 0.0
            device._fpga2_temperature = 0.0
            device._antenna_ids = []
            device._forty_gb_destination_ips = []
            device._forty_gb_destination_macs = []
            device._forty_gb_destination_ports = []
            device._adc_power = []
            device._sampling_rate = 0.0
            device._tpm = None
            device._simulationMode = SimulationMode.TRUE
            device._default_tapering_coeffs = [
                float(1) for i in range(device.AntennasPerTile)
            ]
            device._event_names = [
                "voltage",
                "current",
                "board_temperature",
                "fpga1_temperature",
                "fpga2_temperature",
                "healthState",
            ]
            for name in device._event_names:
                device.set_change_event(name, True, True)
                device.set_archive_event(name, True, True)

            device._test_mode = TestMode.NONE
            device._is_connected = False
            device._streaming = False
            device._update_frequency = 1
            device._read_task = None
            device._lock = threading.Lock()
            device._create_long_running_task()
            device.logger.info("MccsTile init_device complete")
            return (ResultCode.OK, "Init command succeeded")

    def always_executed_hook(self):
        """Method always executed before any TANGO command is executed."""

    def delete_device(self):
        """Hook to delete resources allocated in init_device.

        This method allows for any memory or other resources allocated in the
        init_device method to be released.  This method is called by the device
        destructor and by the device Init command.
        """
        if self._read_task is not None:
            with self._lock:
                self._streaming = False
            self._read_task = None

    # ----------
    # Attributes
    # ----------

    def is_connected(self, attr_req_type):
        """
        Helper to disallow certain function calls on unconnected tiles
        """
        return self._tpm is not None and self._is_connected

    @attribute(dtype="DevLong", doc="The global tile identifier")
    def tileId(self):
        """Return the tileId attribute."""
        return self._tile_id

    @tileId.write
    def tileId(self, value):
        """Set the tileId attribute."""
        self._tile_id = value

    @attribute(dtype="DevLong", doc="Logical tile identifier within a station")
    def logicalTileId(self):
        """Return the logicalTileId attribute."""
        return self._logical_tile_id

    @logicalTileId.write
    def logicalTileId(self, value):
        """Set the logicalTileId attribute."""
        self._logical_tile_id = value

    @attribute(dtype="DevLong", doc="The identifier of the associated subarray.")
    def subarrayId(self):
        """Return the subarrayId attribute."""
        return self._subarray_id

    @subarrayId.write
    @DebugIt()
    def subarrayId(self, value):
        """Set the subarrayId attribute."""
        self._subarray_id = value

    @attribute(dtype="DevLong", doc="The identifier of the associated station.")
    def stationId(self):
        """Return the stationId attribute."""
        return self._station_id

    @stationId.write
    def stationId(self, value):
        """Set the stationId attribute."""
        self._station_id = value

    @attribute(dtype="DevString", doc="LMC address (and global identifier) of Tile")
    def ipAddress(self):
        """Return the ipAddress attribute."""
        return self._ip_address

    @ipAddress.write
    def ipAddress(self, value):
        """Set the ipAddress attribute."""
        self._ip_address = value

    @attribute(
        dtype="DevString", doc="LMC IP address to (and from) which LMC data will flow"
    )
    def lmcIp(self):
        """Return the lmcIp attribute."""
        return self._lmc_ip

    @lmcIp.write
    def lmcIp(self, value):
        """Set the lmcIp attribute."""
        self._lmc_ip = value

    @attribute(dtype="DevLong", doc="LMC port to (and from) which LMC data will flow")
    def lmcPort(self):
        """Return the lmcPort attribute."""
        return self._lmc_port

    @lmcPort.write
    def lmcPort(self, value):
        """Set the lmcPort attribute."""
        self._lmc_port = value

    @attribute(
        dtype="DevString",
        doc="""CSP ingest node IP address for station beam (use if Tile is
        last one in the beamforming chain)""",
    )
    def cspDestinationIp(self):
        """Return the cspDestinationIp attribute."""
        return self._csp_destination_ip

    @cspDestinationIp.write
    def cspDestinationIp(self, value):
        """Set the cspDestinationIp attribute."""
        self._csp_destination_ip = value

    @attribute(
        dtype="DevString",
        doc="""CSP ingest node MAC address for station beam (use if Tile is
        last one in the beamforming chain)""",
    )
    def cspDestinationMac(self):
        """Return the cspDestinationMac attribute."""
        return self._csp_destination_mac

    @cspDestinationMac.write
    def cspDestinationMac(self, value):
        """Set the cspDestinationMac attribute."""
        self._csp_destination_mac = value

    @attribute(
        dtype="DevLong",
        doc="""CSP ingest node port address for station beam (use if Tile is
        last one in the beamforming chain)""",
    )
    def cspDestinationPort(self):
        """Return the cspDestinationPort attribute."""
        return self._csp_destination_port

    @cspDestinationPort.write
    def cspDestinationPort(self, value):
        """Set the cspDestinationPort attribute."""
        self._csp_destination_port = value

    @attribute(
        dtype="DevString", doc="Name and identifier of currently running firmware"
    )
    def firmwareName(self):
        """Return the firmwareName attribute."""
        return self._firmware_name

    @firmwareName.write
    def firmwareName(self, value):
        """Set the firmwareName attribute."""
        self._firmware_name = value

    @attribute(dtype="DevString", doc="Version of currently running firmware")
    def firmwareVersion(self):
        """Return the firmwareVersion attribute."""
        return self._firmware_version

    @firmwareVersion.write
    def firmwareVersion(self, value):
        """Set the firmwareVersion attribute."""
        self._firmware_version = value

    @attribute(
        dtype="DevDouble",
        fisallowed=is_connected,
        abs_change=0.05,
        min_value=4.5,
        max_value=5.5,
        min_alarm=4.55,
        max_alarm=5.45,
    )
    def voltage(self):
        """Return the voltage attribute."""
        return self._voltage

    @attribute(
        dtype="DevDouble",
        fisallowed=is_connected,
        abs_change=0.05,
        min_value=0.0,
        max_value=3.0,
        min_alarm=0.05,
        max_alarm=2.95,
    )
    def current(self):
        """Return the current attribute."""
        return self._current

    @attribute(
        dtype="DevBoolean",
        doc="Return True if the all FPGAs are programmed, False otherwise",
    )
    def isProgrammed(self):
        """ Function that returns true if board is programmed"""
        return self._tpm.is_programmed()

    @attribute(
        dtype="DevDouble",
        doc="The board temperature",
        fisallowed=is_connected,
        abs_change=0.1,
        min_value=25.0,
        max_value=40.0,
        min_alarm=26.0,
        max_alarm=39.0,
    )
    def board_temperature(self):
        """Return the board_temperature attribute."""
        return self._board_temperature

    @attribute(
        dtype="DevDouble",
        fisallowed=is_connected,
        abs_change=0.1,
        min_value=25.0,
        max_value=40.0,
        min_alarm=26.0,
        max_alarm=39.0,
    )
    def fpga1_temperature(self):
        """Return the fpga1_temperature attribute."""
        return self._fpga1_temperature

    @attribute(
        dtype="DevDouble",
        fisallowed=is_connected,
        abs_change=0.1,
        min_value=25.0,
        max_value=40.0,
        min_alarm=26.0,
        max_alarm=39.0,
    )
    def fpga2_temperature(self):
        """Return the fpga2_temperature attribute."""
        return self._fpga2_temperature

    @attribute(dtype="DevLong", fisallowed=is_connected)
    def fpga1_time(self):
        """Return the fpga1_time attribute."""
        return self._tpm.get_fpga1_time()

    @fpga1_time.write
    def fpga1_time(self, value):
        """Set the fpga1_time attribute."""
        self._tpm.set_fpga1_time(value)

    @attribute(dtype="DevLong", fisallowed=is_connected)
    def fpga2_time(self):
        """Return the fpga2_time attribute."""
        return self._tpm.get_fpga2_time()

    @fpga2_time.write
    def fpga2_time(self, value):
        """Set the fpga2_time attribute."""
        self._tpm.set_fpga2_time(value)

    @attribute(
        dtype=("DevLong",),
        max_dim_x=8,
        label="Antenna ID's",
        doc="Array holding the logical ID`s of the antenna associated with "
        "the Tile device",
    )
    def antennaIds(self):
        """Return the antennaIds attribute."""
        return self._antenna_ids

    @antennaIds.write
    def antennaIds(self, ids):
        """Setthe antennaIds attribute."""
        self._antenna_ids = ids

    @attribute(
        dtype=("DevString",),
        max_dim_x=256,
        doc="""40Gb destination IP for all 40Gb ports on the Tile (source
        automatically set during initialization)""",
    )
    def fortyGbDestinationIps(self):
        """Return the fortyGbDestinationIps attribute."""
        dst_ips = []
        for item in self._tpm.get_40G_configuration():
            dst_ips.append(item.get("DstIP"))
        return dst_ips

    @attribute(
        dtype=("DevString",),
        max_dim_x=256,
        doc="""40Gb destination MACs for all 40Gb ports on the Tile (source
        automatically set during initialization)""",
    )
    def fortyGbDestinationMacs(self):
        """Return the fortyGbDestinationMacs attribute."""
        dst_macs = []
        for item in self._tpm.get_40G_configuration():
            dst_macs.append(item.get("DstMac"))
        return dst_macs

    @attribute(
        dtype=("DevLong",),
        max_dim_x=256,
        doc="""40Gb destination ports for all 40Gb ports on the Tile (source
        automatically set during initialization"")""",
    )
    def fortyGbDestinationPorts(self):
        """Return the fortyGbDestinationPorts attribute."""
        dst_ports = []
        for item in self._tpm.get_40G_configuration():
            dst_ports.append(item.get("DstPort"))
        return dst_ports

    @attribute(
        dtype=("DevDouble",),
        max_dim_x=32,
        doc="Return the RMS power of every ADC signal (so a TPM processes "
        "16 antennas, this should return 32 RMS values)",
        fisallowed=is_connected,
    )
    def adcPower(self):
        # Get RMS values from board
        return self._tpm.get_adc_rms()

    @attribute(
        dtype="DevLong",
        doc="Return current frame, in units of 256 ADC frames (276,48 us)",
        fisallowed=is_connected,
    )
    def currentTileBeamformerFrame(self):
        # Currently this is required, not sure if it will remain so
        return self._tpm.current_tile_beamformer_frame()

    @attribute(dtype="DevBoolean", fisallowed=is_connected)
    def checkPendingDataRequests(self):
        return self._tpm.check_pending_data_requests()

    @attribute(dtype="DevBoolean", fisallowed=is_connected)
    def isBeamformerRunning(self):
        return self._tpm.beamformer_is_running()

    @attribute(dtype="DevLong", fisallowed=is_connected)
    def phaseTerminalCount(self):
        return self._tpm.get_phase_terminal_count()

    @phaseTerminalCount.write
    def phaseTerminalCount(self, value):
        self._tpm.set_phase_terminal_count(value)

    @attribute(dtype="DevLong", fisallowed=is_connected)
    def ppsDelay(self):
        return self._tpm.get_pps_delay()

    @attribute(dtype=["DevString"], max_dim_x=32)
    def event_names(self):
        """List of event names which push change events"""
        return self._event_names

    # --------
    # Commands
    # --------
    def init_command_objects(self):
        """
        Set up the handler objects for Commands
        """
        super().init_command_objects()

        args = (self, self.state_model, self.logger)

        self.register_command_object("Initialise", self.InitialiseCommand(*args))
        self.register_command_object("Connect", self.ConnectCommand(*args))
        self.register_command_object("Disconnect", self.DisconnectCommand(*args))
        self.register_command_object(
            "GetFirmwareList", self.GetFirmwareListCommand(*args)
        )
        self.register_command_object(
            "DownloadFirmware", self.DownloadFirmwareCommand(*args)
        )
        self.register_command_object("ProgramCPLD", self.ProgramCPLDCommand(*args))
        self.register_command_object("WaitPPSEvent", self.WaitPPSEventCommand(*args))
        self.register_command_object(
            "GetRegisterList", self.GetRegisterListCommand(*args)
        )
        self.register_command_object("ReadRegister", self.ReadRegisterCommand(*args))
        self.register_command_object("WriteRegister", self.WriteRegisterCommand(*args))
        self.register_command_object("ReadAddress", self.ReadAddressCommand(*args))
        self.register_command_object("WriteAddress", self.WriteAddressCommand(*args))
        self.register_command_object(
            "Configure40GCore", self.Configure40GCoreCommand(*args)
        )
        self.register_command_object(
            "Get40GCoreConfiguration", self.Get40GCoreConfigurationCommand(*args)
        )
        self.register_command_object(
            "SetLmcDownload", self.SetLmcDownloadCommand(*args)
        )
        self.register_command_object(
            "SetChanneliserTruncation", self.SetChanneliserTruncationCommand(*args)
        )
        self.register_command_object(
            "SetBeamFormerRegions", self.SetBeamFormerRegionsCommand(*args)
        )
        self.register_command_object(
            "ConfigureStationBeamformer", self.ConfigureStationBeamformerCommand(*args)
        )
        self.register_command_object(
            "LoadCalibrationCoefficients",
            self.LoadCalibrationCoefficientsCommand(*args),
        )
        self.register_command_object("LoadBeamAngle", self.LoadBeamAngleCommand(*args))
        self.register_command_object(
            "LoadAntennaTapering", self.LoadAntennaTaperingCommand(*args)
        )
        self.register_command_object(
            "SwitchCalibrationBank", self.SwitchCalibrationBankCommand(*args)
        )
        self.register_command_object(
            "SetPointingDelay", self.SetPointingDelayCommand(*args)
        )
        self.register_command_object(
            "LoadPointingDelay", self.LoadPointingDelayCommand(*args)
        )
        self.register_command_object(
            "StartBeamformer", self.StartBeamformerCommand(*args)
        )
        self.register_command_object(
            "StopBeamformer", self.StopBeamformerCommand(*args)
        )
        self.register_command_object(
            "ConfigureIntegratedChannelData",
            self.ConfigureIntegratedChannelDataCommand(*args),
        )
        self.register_command_object(
            "ConfigureIntegratedBeamData",
            self.ConfigureIntegratedBeamDataCommand(*args),
        )
        self.register_command_object("SendRawData", self.SendRawDataCommand(*args))
        self.register_command_object(
            "SendChannelisedData", self.SendChannelisedDataCommand(*args)
        )
        self.register_command_object(
            "SendChannelisedDataContinuous",
            self.SendChannelisedDataContinuousCommand(*args),
        )
        self.register_command_object("SendBeamData", self.SendBeamDataCommand(*args))
        self.register_command_object(
            "StopDataTransmission", self.StopDataTransmissionCommand(*args)
        )
        self.register_command_object(
            "ComputeCalibrationCoefficients",
            self.ComputeCalibrationCoefficientsCommand(*args),
        )
        self.register_command_object(
            "StartAcquisition", self.StartAcquisitionCommand(*args)
        )
        self.register_command_object("SetTimeDelays", self.SetTimeDelaysCommand(*args))
        self.register_command_object(
            "SetCspRounding", self.SetCspRoundingCommand(*args)
        )
        self.register_command_object(
            "SetLmcIntegratedDownload", self.SetLmcIntegratedDownloadCommand(*args)
        )
        self.register_command_object(
            "SendRawDataSynchronised", self.SendRawDataSynchronisedCommand(*args)
        )
        self.register_command_object(
            "SendChannelisedDataNarrowband",
            self.SendChannelisedDataNarrowbandCommand(*args),
        )
        self.register_command_object(
            "TweakTransceivers", self.TweakTransceiversCommand(*args)
        )
        self.register_command_object(
            "PostSynchronisation", self.PostSynchronisationCommand(*args)
        )
        self.register_command_object("SyncFpgas", self.SyncFpgasCommand(*args))
        self.register_command_object(
            "CalculateDelay", self.CalculateDelayCommand(*args)
        )


    class InitialiseCommand(ResponseCommand):
        """
        Class for handling the Initialise() command.
        """

        def do(self):
            self.target._tpm.initialise()
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def Initialise(self):
        """
        Performs all required initialisation (switches on on-board devices,
        locks PLL, performs synchronisation and other operations required
        to start configuring the signal processing functions of the firmware,
        such as channelisation and beamforming)

        :return: (ResultCode, 'informational message')

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("Connect", False)
        >>> dp.command_inout("Initialise")
        """
        handler = self.get_command_object("Initialise")
        (return_code, message) = handler()
        return [[return_code], [message]]

    class ConnectCommand(ResponseCommand):
        """
        Class for handling the Connect() command.
        """

        def do(self, argin):
            initialise_tpm = argin
            device = self.target
            if device._simulation_mode == SimulationMode.FALSE:
                device._tpm = TpmSimulator(self.logger)
            else:
                device._tpm = Tpm(  # noqa: F821
                    device._ip_address,
                    device._port,
                    device._lmc_ip,
                    device._lmc_port,
                    device._sampling_rate,
                )

            tm = True if device._test_mode == TestMode.TEST else False
            device._tpm.connect(
                initialise=initialise_tpm, simulation=device.simulationMode, testmode=tm
            )

            # Load tpm test firmware for both FPGAs
            if not device._tpm.is_programmed() and initialise_tpm:
                device._tpm.download_firmware("TpmTestFirmware")
            elif not device._tpm.is_programmed():
                self.logger.warning("TPM is not programmed! No plugins loaded")


            if initialise_tpm:
                device.Initialise()


            device._is_connected = True
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_in="DevBoolean",
        doc_in="Initialise",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def Connect(self, argin):
        """
        Creates connection to board. When True the initialise function is
        called immediately after connection (board must be programmed)

        :param argin: When True initialise immediately after connection
        :type argin: DevBoolean

        :return: (ResultCode, 'informational message')

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("Connect", True)
        """
        handler = self.get_command_object("Connect")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class DisconnectCommand(ResponseCommand):
        """
        Class for handling the Disconnect() command.
        """

        def do(self):
            device = self.target
            with device._lock:
                device._is_connected = False
            device._tpm.disconnect()
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def Disconnect(self):
        """
        Disconnects from the board, the internal state needs to be reset

        :return: (ResultCode, 'informational message')

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("Disconnect")
        """
        handler = self.get_command_object("Disconnect")
        (return_code, message) = handler()
        return [[return_code], [message]]

    class GetFirmwareListCommand(BaseCommand):
        """
        Class for handling the GetFirmwareList() command.
        """

        def do(self):
            firmware_list = self.target._tpm.get_firmware_list()
            return json.dumps(firmware_list)

    @command(dtype_out="DevString", doc_out="list of firmware")
    @DebugIt()
    def GetFirmwareList(self):
        """Return a dictionary containing the following information for each
        firmware stored on the board (such as in Flash memory).
        For each firmware, a dictionary containing the following keys with
        their respective values should be provided: ‘design’, which is a textual
        name for the firmware, ‘major’, which is the major version number, and
        ‘minor’.

        :return: a dictionary of firmware details

        * key - (string) the firmware name
        * value - (dict) dictionary of firmware  details with keys

            * Design - (string) a textual name for the firmware
            * Major - (int) the major firmware version
            * Minor - (int) the minor firmware verion

        :rtype: DevString

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> jstr = dp.command_inout("GetFirmwareList")
        >>> dict = json.load(jstr)
        """
        handler = self.get_command_object("GetFirmwareList")
        return handler()

    class DownloadFirmwareCommand(ResponseCommand):
        """
        Class for handling the DownloadFirmware() command.
        """

        def do(self, argin):
            bitfile = argin
            device = self.target
            if device._tpm is not None:
                self.logger.info("Downloading bitfile to board")
                device._tpm.download_firmware(bitfile)
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_in="DevString",
        doc_in="bitfile location",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def DownloadFirmware(self, argin):
        """
        Downloads the firmware contained in bitfile to all FPGAs on the board.
        This should also update the internal register mapping, such that
        registers become available for use.

        :param argin: can either be the design name returned from get_firmware_list(),
                        or a path to a file
        :type argin: 'DevString'

        :return: (ResultCode, 'informational message')

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("DownloadFirmware", "/tmp/firmware/bitfile")
        """
        handler = self.get_command_object("DownloadFirmware")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class ProgramCPLDCommand(ResponseCommand):
        """
        Class for handling the ProgramCPLD() command.
        """

        def do(self, argin):
            bitfile = argin
            device = self.target
            if device._tpm is not None:
                self.logger.info("Downloading bitstream to CPLD FLASH")
                device._tpm.cpld_flash_write(bitfile)
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_in="DevString",
        doc_in="bitfile location",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def ProgramCPLD(self, argin):
        """
        If the TPM has a CPLD (or other management chip which need firmware),
        this function program it with the provided bitfile.

        :param argin: is the path to a file containing the required CPLD firmware
        :type: 'DevString'

        :return: (ResultCode, 'informational message')

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("ProgramCPLD", "/tmp/firmware/bitfile")
        """
        handler = self.get_command_object("ProgramCPLD")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class WaitPPSEventCommand(ResponseCommand):
        """
        Class for handling the WaitPPSEvent() command.
        """

        def do(self):
            device = self.target
            if device._tpm is not None:
                t0 = device._tpm.get_fpga1_time()
                while t0 == device._tpm.get_fpga1_time():
                    pass
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def WaitPPSEvent(self):
        """
        Block until a PPS edge is detected, then return from function

        :return: (ResultCode, 'informational message')

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("WaitPPSEvent")
        """
        handler = self.get_command_object("WaitPPSEvent")
        (return_code, message) = handler()
        return [[return_code], [message]]

    class GetRegisterListCommand(BaseCommand):
        """
        Class for handling the GetRegisterList() command.
        """

        def do(self):
            return self.target._tpm.get_register_list()

    @command(dtype_out="DevVarStringArray")
    @DebugIt()
    def GetRegisterList(self):
        """
        Return a list containing description of the exposed firmware (and CPLD)
        registers

        :return: a list of register names
        :rtype: DevVarStringArray

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> reglist = dp.command_inout("GetRegisterList")
        """
        handler = self.get_command_object("GetRegisterList")
        return handler()

    class ReadRegisterCommand(BaseCommand):
        """
        Class for handling the ReadRegister() command.
        """

        def do(self, argin):
            params = json.loads(argin)
            name = params.get("RegisterName", None)
            if name is None:
                self.logger.error("RegisterName is a mandatory parameter")
                raise ValueError("RegisterName is a mandatory parameter")
            nb_read = params.get("NbRead", None)
            if nb_read is None:
                self.logger.error("NbRead is a mandatory parameter")
                raise ValueError("NbRead is a mandatory parameter")
            offset = params.get("Offset", None)
            if offset is None:
                self.logger.error("Offset is a mandatory parameter")
                raise ValueError("Offset is a mandatory parameter")
            device = params.get("Device", None)
            if device is None:
                self.logger.error("Device is a mandatory parameter")
                raise ValueError("Device is a mandatory parameter")

            return self.target._tpm.read_register(name, nb_read, offset, device)

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with keywords:\n"
        "RegisterName, NbRead, Offset, Device",
        dtype_out="DevVarLongArray",
        doc_out="list of register values",
    )
    @DebugIt()
    def ReadRegister(self, argin):
        """
        Return the value(s) of the specified register.

        :param argin: json dictionary with mandatory keywords:

            * RegisterName - (string) register_name is the registers
                string representation
            * NbRead - (int) is the number of 32-bit values to read
            * Offset - (int) offset is the address offset within the
                register to write to
            * Device - (int) device is the FPGA to write to (0 or 1)

        :type argin: DevString

        :return: a list of register values
        :rtype: DevVarUlongArray

        :example:
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"RegisterName": "test-reg1", "NbRead": nb_read,
                    "Offset": offset, "Device":device}
        >>> jstr = json.dumps(dict)
        >>> values = dp.command_inout("ReadRegister", jstr)
        """
        handler = self.get_command_object("ReadRegister")
        return handler(argin)

    class WriteRegisterCommand(ResponseCommand):
        """
        Class for handling the WriteRegister() command.
        """

        def do(self, argin):
            params = json.loads(argin)
            name = params.get("RegisterName", None)
            if name is None:
                self.logger.error("RegisterName is a mandatory parameter")
                raise ValueError("RegisterName is a mandatory parameter")
            values = params.get("Values", None)
            if values is None:
                self.logger.error("Values is a mandatory parameter")
                raise ValueError("Values is a mandatory parameter")
            offset = params.get("Offset", None)
            if offset is None:
                self.logger.error("Offset is a mandatory parameter")
                raise ValueError("Offset is a mandatory parameter")
            device = params.get("Device", None)
            if device is None:
                self.logger.error("Device is a mandatory parameter")
                raise ValueError("Device is a mandatory parameter")

            self.target._tpm.write_register(name, values, offset, device)
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with keywords:\n"
        "RegisterName, Values, Offset, Device",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def WriteRegister(self, argin):
        """
        Write values to the specified register.

        :param argin: json dictionary with mandatory keywords:

        * RegisterName - (string) register_name is the registers string representation
        * Values - (list) is a list containing the 32-bit values to write
        * Offset - (int) offset is the address offset within the register to write to
        * Device - (int) device is the FPGA to write to (0 or 1)

        :type argin: DevString

        :return: (ResultCode, 'informational message')

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"RegisterName": "test-reg1", "Values": values,
                    "Offset": offset, "Device":device}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("WriteRegister", jstr)
        """
        handler = self.get_command_object("WriteRegister")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class ReadAddressCommand(BaseCommand):
        """
        Class for handling the ReadAddress() command.
        """

        def do(self, argin):
            if len(argin) < 2:
                self.logger.error("Two parameters are required")
                raise ValueError("Two parameters are required")
            address = argin[0]
            nvalues = argin[1]
            return self.target._tpm.read_address(address, nvalues)

    @command(
        dtype_in="DevVarLongArray",
        doc_in="address, n",
        dtype_out="DevVarULongArray",
        doc_out="values",
    )
    @DebugIt()
    def ReadAddress(self, argin):
        """
        Read n 32-bit values from address

        :param argin: [0] = address to read from
                      [1] = number of values to read

        :return: list of values
        :rtype: 'DevVarULongArray'

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> reglist = dp.command_inout("ReadAddress", [address, nvalues]])
        """
        handler = self.get_command_object("ReadAddress")
        return handler(argin)

    class WriteAddressCommand(ResponseCommand):
        """
        Class for handling the WriteAddress() command.
        """

        def do(self, argin):
            if len(argin) < 2:
                self.logger.error("A minimum of two parameters are required")
                raise ValueError("A minium of two parameters are required")
            address = argin[0]
            self.target._tpm.write_address(address, argin[1:])
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_in="DevVarULongArray",
        doc_in="address, values",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def WriteAddress(self, argin):
        """
        Write list of values at address

        :param argin: [0] = address to write to
                      [1..n] = list of values to write

        :return: (ResultCode, 'informational message')

        :example:

        >>> values = [.....]
        >>> address = 0xfff
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("WriteAddress", [address, values])
        """
        handler = self.get_command_object("WriteAddress")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class Configure40GCoreCommand(ResponseCommand):
        """
        Class for handling the Configure40GCore() command.
        """

        def do(self, argin):
            params = json.loads(argin)
            core_id = params.get("CoreID", None)
            if core_id is None:
                self.logger.error("CoreID is a mandatory parameter")
                raise ValueError("CoreID is a mandatory parameter")
            src_mac = params.get("SrcMac", None)
            if src_mac is None:
                self.logger.error("SrcMac is a mandatory parameter")
                raise ValueError("SrcMac is a mandatory parameter")
            src_ip = params.get("SrcIP", None)
            if src_ip is None:
                self.logger.error("SrcIP is a mandatory parameter")
                raise ValueError("SrcIP is a mandatory parameter")
            src_port = params.get("SrcPort", None)
            if src_port is None:
                self.logger.error("SrcPort is a mandatory parameter")
                raise ValueError("SrcPort is a mandatory parameter")
            dst_mac = params.get("DstMac", None)
            if dst_mac is None:
                self.logger.error("DstMac is a mandatory parameter")
                raise ValueError("DstMac is a mandatory parameter")
            dst_ip = params.get("DstIP", None)
            if dst_ip is None:
                self.logger.error("DstIP is a mandatory parameter")
                raise ValueError("DstIP is a mandatory parameter")
            dst_port = params.get("DstPort", None)
            if dst_port is None:
                self.logger.error("DstPort is a mandatory parameter")
                raise ValueError("DstPort is a mandatory parameter")
            self.target._tpm.configure_40G_core(
                core_id, src_mac, src_ip, src_port, dst_mac, dst_ip, dst_port
            )
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with keywords:\n"
        "CoreID, SrcMac, SrcIP, SrcPort, DstMac, DstIP, DstPort",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def Configure40GCore(self, argin):
        """
        Configure 40g core_id with specified parameters.

        :param argin: json dictionary with optional keywords:

        * CoreID - (int) core id
        * SrcMac - (string) mac address dot notation
        * SrcIP - (string) IP dot notation
        * SrcPort - (int) src port
        * DstMac - (string) mac address dot notation
        * DstIP - (string) IP dot notation
        * DstPort - (int) dest port

        :type argin: DevString

        :return: (ResultCode, 'informational message')

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"CoreID":2, "SrcMac":"10:fe:ed:08:0a:58", "SrcIP":"10.0.99.3",
                    "SrcPort":4000, "DstMac":"10:fe:ed:08:0a:58", "DstIP":"10.0.99.3",
                    "DstPort":5000}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("Configure40GCore", jstr)
        """
        handler = self.get_command_object("Configure40GCore")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class Get40GCoreConfigurationCommand(BaseCommand):
        """
        Class for handling the Get40GCoreConfiguration() command.
        """

        def do(self, argin):
            core_id = argin
            item = self.target._tpm.get_40G_configuration(core_id)
            if item is not None:
                return json.dumps(item.pop("CoreID"))
            raise ValueError("Invalid core id specified")

    @command(
        dtype_in="DevLong",
        doc_in="coreId",
        dtype_out="DevString",
        doc_out="configuration dict as a json string",
    )
    @DebugIt()
    def Get40GCoreConfiguration(self, argin):
        """
        Get 40g core configuration for core_id.
        This is required to chain up TPMs to form a station

        :return: the configuration is a json string comprising:
                 src_mac, src_ip, src_port, dest_mac, dest_ip, dest_port

        :rtype: DevString

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> core_id = 2
        >>> argout = dp.command_inout("Get40GCoreConfiguration, core_id)
        >>> params = json.loads(argout)
        """
        handler = self.get_command_object("Get40GCoreConfiguration")
        return handler(argin)

    class SetLmcDownloadCommand(ResponseCommand):
        """
        Class for handling the SetLmcDownload() command.
        """

        def do(self, argin):
            params = json.loads(argin)
            mode = params.get("Mode", None)
            if mode is None:
                self.logger.error("Mode is a mandatory parameter")
                raise ValueError("Mode is a mandatory parameter")
            payload_length = params.get("PayloadLength", 1024)
            dst_ip = params.get("DstIP", None)
            src_port = params.get("SrcPort", 0xf0d0)
            dst_port = params.get("DstPort", 4660)
            lmc_mac = params.get("LmcMac", None)
            self.target._tpm.set_lmc_download(
                mode, payload_length, dst_ip, src_port, dst_port, lmc_mac
            )
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with keywords:\n"
        "Mode,PayloadLength,DstIP,SrcPort,DstPort, LmcMac",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def SetLmcDownload(self, argin):
        """
        Specify whether control data will be transmitted over 1G or 40G
        networks

        :param argin: json dictionary with optional keywords:

        * Mode - (string) '1g' or '10g' (Mandatory)
        * PayloadLength - (int) SPEAD payload length for integrated channel data
        * DstIP - (string) Destination IP
        * SrcPort - (int) Source port for integrated data streams
        * DstPort - (int) Destination port for integrated data streams
        * LmcMac: - (int) LMC Mac address is required for 10G lane configuration

        :type argin: DevString

        :return: (ResultCode, 'informational message')

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"Mode": "1G", "PayloadLength":4,DstIP="10.0.1.23"}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SetLmcDownload", jstr)
        """
        handler = self.get_command_object("SetLmcDownload")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class SetChanneliserTruncationCommand(ResponseCommand):
        """
        Class for handling the SetChanneliserTruncation() command.
        """

        def do(self, argin):
            if len(argin) < 3:
                self.logger.error("Insufficient values supplied")
                raise ValueError("Insufficient values supplied")
            nb_chan = argin[0]
            nb_freq = argin[1]
            arr = np.array(argin[2:])
            np.reshape(arr, (nb_chan, nb_freq))
            self.target._tpm.set_channeliser_truncation(arr)
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_in="DevVarLongArray",
        doc_in="truncation array",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def SetChanneliserTruncation(self, argin):
        """
        Set the coefficients to modify (flatten) the bandpass.

        :param argin: truncation is a N x M array

        * argin[0] - is N, the number of input channels
        * argin[1] - is M, the number of frequency channel
        * argin[2:] - is the data

        :type: DevVarLongArray

        :return: (ResultCode, 'informational message')

        :example:

        >>> n=4
        >>> m=3
        >>> trunc = [[0, 1, 2], [3, 4, 5],[6, 7, 8], [9, 10, 11],]
        >>> arr = np.array(trunc).ravel()
        >>> argin = np.concatenate([np.array((4, 3)), arr])
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("SetChanneliserTruncation", argin)
        """
        handler = self.get_command_object("SetChanneliserTruncation")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class SetBeamFormerRegionsCommand(ResponseCommand):
        """
        Class for handling the SetBeamFormerRegions() command.
        """

        def do(self, argin):
            if len(argin) < 3:
                self.logger.error("Insufficient parameters specified")
                raise ValueError("Insufficient parameters specified")
            if len(argin) > 48:
                self.logger.error("Too many regions specified")
                raise ValueError("Too many regions specified")
            if len(argin) % 3 != 0:
                self.logger.error("Incomplete specification of region")
                raise ValueError("Incomplete specification of region")
            regions = []
            total_chan = 0
            for i in range(0, len(argin), 3):
                region = argin[i : i + 3]  # noqa: E203
                nchannels = region[1]
                if nchannels % 8 != 0:
                    self.logger.error(
                        "Nos. of channels in region must be multiple of 8"
                    )
                    raise ValueError("Nos. of channels in region must be multiple of 8")
                beam_index = region[2]
                if beam_index < 0 or beam_index > 7:
                    self.logger.error("Beam_index is out side of range 0-7")
                    raise ValueError("Beam_index is out side of range 0-7")
                total_chan += nchannels
                if total_chan > 384:
                    self.logger.error("Too many channels specified > 384")
                    raise ValueError("Too many channels specified > 384")
                regions.append(region)
            self.target._tpm.set_beamformer_regions(regions)
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_in="DevVarLongArray",
        doc_in="region_array",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def SetBeamFormerRegions(self, argin):
        """
        Set the frequency regions which are going to be beamformed into a
        single beam.
        region_array is defined as a 2D array, for a maximum of 16 regions.
        Total number of channels must be <= 384

        :param argin: list of regions. Each region comprises:

        * start_channel - (int) region starting channel
        * num_channels - (int) size of the region, must be a multiple of 8
        * beam_index - (int) beam used for this region with range 0 to 7

        :type argin: DevVarLongArray

        :return: (ResultCode, 'informational message')

        :example:

        >>> regions = [[5, 20, 1],[25, 40, 2]]
        >>> input = list(itertools.chain.from_iterable(regions))
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("SetBeamFormerRegions", input)
        """
        handler = self.get_command_object("SetBeamFormerRegions")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class ConfigureStationBeamformerCommand(ResponseCommand):
        """
        Class for handling the ConfigureStationBeamformer() command.
        """

        def do(self, argin):
            params = json.loads(argin)
            start_channel = params.get("StartChannel", None)
            if start_channel is None:
                self.logger.error("StartChannel is a mandatory parameter")
                raise ValueError("StartChannel is a mandatory parameter")
            ntiles = params.get("NumTiles", None)
            if ntiles is None:
                self.logger.error("NumTiles is a mandatory parameter")
                raise ValueError("NumTiles is a mandatory parameter")
            is_first = params.get("IsFirst", None)
            if is_first is None:
                self.logger.error("IsFirst is a mandatory parameter")
                raise ValueError("IsFirst is a mandatory parameter")
            is_last = params.get("IsLast", None)
            if is_last is None:
                self.logger.error("IsLast is a mandatory parameter")
                raise ValueError("IsLast is a mandatory parameter")
            self.target._tpm.initialise_beamformer(
                start_channel, ntiles, is_first, is_last
            )
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with mandatory keywords:\n"
        "StartChannel,Numtiles, IsFirst, IsLast",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def ConfigureStationBeamformer(self, argin):
        """
        Initialise and start the station beamformer.

        :param argin: json dictionary with mandatory keywords:

        * StartChannel - (int) start channel
        * NumTiles - (int) is the number of tiles in the station
        * IsFirst - (bool) specifies whether the tile is the first one in the station
        * IsLast - (bool) specifies whether the tile is the last one in the station

        :type argin: DevString

        :return: (ResultCode, 'informational message')

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"StartChannel":1, "NumTiles":10, "IsTile":True}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("ConfigureStationBeamformer", jstr)
        """
        handler = self.get_command_object("ConfigureStationBeamformer")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class LoadCalibrationCoefficientsCommand(ResponseCommand):
        """
        Class for handling the LoadCalibrationCoefficients() command.
        """

        def do(self, argin):
            if len(argin) < 9:
                self.logger.error("Insufficient calibration coefficients")
                raise ValueError("Insufficient calibration coefficients")
            if len(argin[1:]) % 8 != 0:
                self.logger.error("Incomplete specification of coefficient")
                raise ValueError("Incomplete specification of coefficient")
            antenna = int(argin[0])
            calib_coeffs = [
                [
                    complex(argin[i], argin[i + 1]),
                    complex(argin[i + 2], argin[i + 3]),
                    complex(argin[i + 4], argin[i + 5]),
                    complex(argin[i + 6], argin[i + 7]),
                ]
                for i in range(1, len(argin), 8)
            ]
            self.target._tpm.load_calibration_coefficients(antenna, calib_coeffs)
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_in="DevVarDoubleArray",
        doc_in="antenna, calibration_coefficients",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def LoadCalibrationCoefficients(self, argin):
        """
        Loads calibration coefficients (but does not apply them, this is
        performed by switch_calibration_bank). The calibration coefficients
        may include any rotation matrix (e.g. the parallactic angle),
        but do not include the geometric delay

        :param argin: list comprises:

        * antenna - (int) is the antenna to which the coefficients will be applied.
        * calibration_coefficients - [array] a bidimensional complex array comprising
            calibration_coefficients[channel, polarization], with each element
            representing a normalized coefficient, with (1.0, 0.0) being the
            normal, expected response for an ideal antenna.

            * channel - (int) channel is the index specifying the channels at the
                              beamformer output, i.e. considering only those channels
                              actually processed and beam assignments.
            * polarization index ranges from 0 to 3.

                * 0: X polarization direct element
                * 1: X->Y polarization cross element
                * 2: Y->X polarization cross element
                * 3: Y polarization direct element

        :type argin: DevVarDoubleArray

        :return: (ResultCode, 'informational message')

        :example:

        >>> antenna = 2
        >>> complex_coeffs = [[complex(3.4, 1.2), complex(2.3, 4.1),
        >>>            complex(4.6, 8.2), complex(6.8, 2.4)]]*5
        >>> inp = list(itertools.chain.from_iterable(complex_coeffs))
        >>> out = [[v.real, v.imag] for v in inp]
        >>> coeffs = list(itertools.chain.from_iterable(out))
        >>> coeffs.insert(0, float(antenna))
        >>> input = list(itertools.chain.from_iterable(coeffs))
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("LoadCalibrationCoefficients", input)
        """
        handler = self.get_command_object("LoadCalibrationCoefficients")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class LoadBeamAngleCommand(ResponseCommand):
        """
        Class for handling the LoadBeamAngle() command.
        """

        def do(self, argin):
            self.target._tpm.load_beam_angle(argin)
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_in="DevVarDoubleArray",
        doc_in="angle_coefficients",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def LoadBeamAngle(self, argin):
        """
        angle_coefs is an array of one element per beam, specifying a rotation
        angle, in radians, for the specified beam. The rotation is the same
        for all antennas.
        Default is 0 (no rotation). A positive pi/4 value transfers the
        X polarization to the Y polarization. The rotation is applied after
        regular calibration.

        :param argin: list of angle coefficients for each beam
        :type argin: DevVarDoubleArray

        :return: (ResultCode, 'informational message')

        :example:

        >>> angle_coeffs = [3.4] * 16
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("LoadBeamAngle", angle_coeffs)
        """
        handler = self.get_command_object("LoadBeamAngle")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class LoadAntennaTaperingCommand(ResponseCommand):
        """
        Class for handling the LoadAntennaTapering() command.
        """

        def do(self, argin):
            if len(argin) < self.AntennasPerTile:
                self.logger.error(
                    f"Insufficient coefficients should be {self.AntennasPerTile}"
                )
                raise ValueError(
                    f"Insufficient coefficients should be {self.AntennasPerTile}"
                )
            self.target._tpm.load_antenna_tapering(argin)
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_in="DevVarDoubleArray",
        doc_in="tapering coefficients",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def LoadAntennaTapering(self, argin):
        """
        tapering_coeffs is a vector contains a value for each antenna the TPM
        processes. Default at initialisation is 1.0

        :param argin: list of tapering coefficients for each antenna
        :type argin: DevVarDoubleArray

        :return: (ResultCode, 'informational message')

        :example:

        >>> tapering_coeffs = [3.4] * 16
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("LoadAntennaTapering", tapering_coeffs)
        """
        handler = self.get_command_object("LoadAntennaTapering")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class SwitchCalibrationBankCommand(ResponseCommand):
        """
        Class for handling the SwitchCalibrationBank() command.
        """

        def do(self, argin):
            switch_time = argin
            self.target._tpm.switch_calibration_bank(switch_time)
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_in="DevLong",
        doc_in="switch time",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def SwitchCalibrationBank(self, argin):
        """
        Load the calibration coefficients at the specified time delay

        :param argin: switch time
        :type argin: DevLong

        :return: (ResultCode, 'informational message')

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("SwitchCalibrationBank", 10)
        """
        handler = self.get_command_object("SwitchCalibrationBank")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class SetPointingDelayCommand(ResponseCommand):
        """
        Class for handling the SetPointingDelay() command.
        """

        def do(self, argin):
            device = self.target
            if len(argin) != device.AntennasPerTile * 2 + 1:
                self.logger.error("Insufficient parameters")
                raise ValueError("Insufficient parameters")
            beam_index = int(argin[0])
            if beam_index < 0 or beam_index > 7:
                self.logger.error("Invalid beam index")
                raise ValueError("Invalid beam index")
            delay_array = []
            for i in range(self.AntennasPerTile):
                delay_array.append([argin[i * 2 + 1], argin[i * 2 + 2]])
            self.target._tpm.set_pointing_delay(delay_array, beam_index)
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_in="DevVarDoubleArray",
        doc_in="delay_array, beam_index",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def SetPointingDelay(self, argin):
        """
        Specifies the delay in seconds and the delay rate in seconds/seconds.
        The delay_array specifies the delay and delay rate for each antenna.
        beam_index specifies which beam is desired (range 0-7)

        :return: (ResultCode, 'informational message')
        """
        handler = self.get_command_object("SetPointingDelay")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class LoadPointingDelayCommand(ResponseCommand):
        """
        Class for handling the LoadPointingDelay() command.
        """

        def do(self, argin):
            load_time = argin
            self.target._tpm.load_pointing_delay(load_time)
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_in="DevLong",
        doc_in="load_time",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def LoadPointingDelay(self, argin):
        """
        Loads the pointing delays at the specified time delay

        :param argin: time delay (default = 0)
        :type argin: DevLong

        :return: (ResultCode, 'informational message')

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("LoadPointingDelay", 10)
        """
        handler = self.get_command_object("LoadPointingDelay")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class StartBeamformerCommand(ResponseCommand):
        """
        Class for handling the StartBeamformer() command.
        """

        def do(self, argin):
            params = json.loads(argin)
            start_time = params.get("StartTime", 0)
            duration = params.get("Duration", -1)
            self.target._tpm.start_beamformer(start_time, duration)
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with keywords:\n" "StartTime, Duration",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def StartBeamformer(self, argin):
        """
        Start the beamformer at the specified time delay

        :param argin: json dictionary with optional keywords:

        * StartTime - (int) start time
        * Duration - (int) if > 0 is a duration in frames * 256 (276.48 us)
                           if == -1 run forever

        :return: (ResultCode, 'informational message')

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"StartTime":10, "Duration":20}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("StartBeamformer", jstr)
        """
        handler = self.get_command_object("StartBeamformer")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class StopBeamformerCommand(ResponseCommand):
        """
        Class for handling the StopBeamformer() command.
        """

        def do(self):
            self.target._tpm.stop_beamformer()
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def StopBeamformer(self):
        """
        Stop the beamformer

        :return: (ResultCode, 'informational message')

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("StopBeamformer")
        """
        handler = self.get_command_object("StopBeamformer")
        (return_code, message) = handler()
        return [[return_code], [message]]

    class ConfigureIntegratedChannelDataCommand(ResponseCommand):
        """
        Class for handling the ConfigureIntegratedChannelData() command.
        """

        def do(self, argin):
            integration_time = argin
            if integration_time <= 0:
                integration_time = 0.5
            self.target._tpm.configure_integrated_channel_data(integration_time)
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_in="DevDouble",
        doc_in="Integration time",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def ConfigureIntegratedChannelData(self, argin):
        """
        Configure the transmission of integrated channel data with the
        provided integration time

        :param argin: integration_time in seconds (default = 0.5)
        :type argin: DevDouble

        :return: (ResultCode, 'informational message')

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("ConfigureIntegratedChannelData", 6.284)
        """
        handler = self.get_command_object("ConfigureIntegratedChannelData")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class ConfigureIntegratedBeamDataCommand(ResponseCommand):
        """
        Class for handling the ConfigureIntegratedBeamData() command.
        """

        def do(self, argin):
            integration_time = argin
            if integration_time <= 0:
                integration_time = 0.5
            self.target._tpm.configure_integrated_beam_data(integration_time)
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_in="DevDouble",
        doc_in="Integration time",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def ConfigureIntegratedBeamData(self, argin):
        """
        Configure the transmission of integrated beam data with the provided
        integration time

        :param integration_time: time in seconds (default = 0.5)
        :type integration_time: DevDouble

        :return: (ResultCode, 'informational message')

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("ConfigureIntegratedBeamData", 3.142)
        """
        handler = self.get_command_object("ConfigureIntegratedBeamData")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class SendRawDataCommand(ResponseCommand):
        """
        Class for handling the SendRawData() command.
        """

        def do(self, argin):
            params = json.loads(argin)
            sync = params.get("Sync", False)
            period = params.get("Period", 0)
            timeout = params.get("Timeout", 0)
            timestamp = params.get("Timestamp", None)
            seconds = params.get("Seconds", 0.2)
            self.target._tpm.send_raw_data(sync, period, timeout, timestamp, seconds)
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with keywords:\n"
        "Sync,Period,Timeout,Timestamp,Seconds",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def SendRawData(self, argin):
        """
        Transmit a snapshot containing raw antenna data

        :param argin: json dictionary with optional keywords:

        * Sync - (bool) synchronised flag
        * Period - (int) in seconds to send data
        * Timeout - (int) When to stop
        * Timestamp - (int??) When to start
        * Seconds - (float) When to synchronise

        :return: (ResultCode, 'informational message')

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"Sync":True, "Period": 200, "Seconds": 0.5}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SendRawData", jstr)
        """
        handler = self.get_command_object("SendRawData")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class SendChannelisedDataCommand(ResponseCommand):
        """
        Class for handling the SendChannelisedData() command.
        """

        def do(self, argin):
            params = json.loads(argin)
            number_of_samples = params.get("NSamples", 1024)
            first_channel = params.get("FirstChannel", 0)
            last_channel = params.get("LastChannel", 511)
            period = params.get("Period", 0)
            timeout = params.get("Timeout", 0)
            timestamp = params.get("Timestamp", None)
            seconds = params.get("Seconds", 0.2)
            self.target._tpm.send_channelised_data(
                number_of_samples,
                first_channel,
                last_channel,
                period,
                timeout,
                timestamp,
                seconds,
            )
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with keywords:\n"
        "NSamples,FirstChannel,LastChannel,Period,"
        "Timeout,Timestamp,Seconds",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def SendChannelisedData(self, argin):
        """
        Transmit a snapshot containing channelized data totalling
        number_of_samples spectra.

        :param argin: json dictionary with optional keywords:

        * NSamples - (int) number of spectra to send
        * FirstChannel - (int) first channel to send
        * LastChannel - (int) last channel to send
        * Period - (int) in seconds to send data
        * Timeout - (int) When to stop
        * Timestamp - (int??) When to start
        * Seconds - (float) When to synchronise

        :return: (ResultCode, 'informational message')

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"FirstChannel":10, "LastChannel": 200, "Seconds": 0.5}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SendChannelisedData", jstr)
        """
        handler = self.get_command_object("SendChannelisedData")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class SendChannelisedDataContinuousCommand(ResponseCommand):
        """
        Class for handling the SendChannelisedDataContinuous() command.
        """

        def do(self, argin):
            params = json.loads(argin)
            channel_id = params.get("ChannelID")
            if channel_id is None:
                self.logger.error("ChannelID is a mandatory parameter")
                raise ValueError("ChannelID is a mandatory parameter")
            number_of_samples = params.get("NSamples", 128)
            wait_seconds = params.get("WaitSeconds", 0)
            timeout = params.get("Timeout", 0)
            timestamp = params.get("Timestamp", None)
            seconds = params.get("Seconds", 0.2)
            self.target._tpm.send_channelised_data_continuous(
                channel_id, number_of_samples, wait_seconds, timeout, timestamp, seconds
            )
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with keywords:\n"
        "ChannelID,NSamples,WaitSeconds,Timeout,"
        "Timestamp,Seconds",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def SendChannelisedDataContinuous(self, argin):
        """
        Send data from channel channel continuously (until stopped)

        :param argin: json dictionary with 1 mandatory and optional keywords:

        * ChannelID - (int) channel_id (Mandatory)
        * NSamples -  (int) number of spectra to send
        * WaitSeconds - (int) Wait time before sending data
        * Timeout - (int) When to stop
        * Timestamp - (int??) When to start
        * Seconds - (float) When to synchronise

        :type argin: DevString

        :return: (ResultCode, 'informational message')

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"ChannelID":2, "NSamples":256, "Period": 10, "Seconds": 0.5}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SendChannelisedDataContinuous", jstr)
        """
        handler = self.get_command_object("SendChannelisedDataContinuous")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class SendBeamDataCommand(ResponseCommand):
        """
        Class for handling the SendBeamData() command.
        """

        def do(self, argin):
            params = json.loads(argin)
            period = params.get("Period", 0)
            timeout = params.get("Timeout", 0)
            timestamp = params.get("Timestamp", None)
            seconds = params.get("Seconds", 0.2)
            self.target._tpm.send_beam_data(period, timeout, timestamp, seconds)
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with keywords:\n" "Period,Timeout,Timestamp,Seconds",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def SendBeamData(self, argin):
        """
        Transmit a snapshot containing beamformed data

        :param argin: json dictionary with optional keywords:

        * Period - (int) in seconds to send data
        * Timeout - (int) When to stop
        * Timestamp - (string??) When to send
        * Seconds - (float) When to synchronise

        :type argin: DevString

        :return: (ResultCode, 'informational message')

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"Period": 10, "Timeout":4, "Seconds": 0.5}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SendBeamData", jstr)
        """
        handler = self.get_command_object("SendBeamData")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class StopDataTransmissionCommand(ResponseCommand):
        """
        Class for handling the StopDataTransmission() command.
        """

        def do(self):
            self.target._tpm.stop_data_transmission()
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def StopDataTransmission(self):
        """
        Stop data transmission from board

        :return: (ResultCode, 'informational message')

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("StopDataTransmission")
        """
        handler = self.get_command_object("StopDataTransmission")
        (return_code, message) = handler()
        return [[return_code], [message]]

    class ComputeCalibrationCoefficientsCommand(ResponseCommand):
        """
        Class for handling the ComputeCalibrationCoefficients() command.
        """

        def do(self):
            self.target._tpm.compute_calibration_coefficients()
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def ComputeCalibrationCoefficients(self):
        """Compute the calibration coefficients and load
           them in the hardware.

        :return: (ResultCode, 'informational message')

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("ComputeCalibrationCoefficients")
        """
        handler = self.get_command_object("ComputeCalibrationCoefficients")
        (return_code, message) = handler()
        return [[return_code], [message]]

    class StartAcquisitionCommand(ResponseCommand):
        """
        Class for handling the StartAcquisition() command.
        """

        def do(self, argin):
            params = json.loads(argin)
            start_time = params.get("StartTime", None)
            delay = params.get("Delay", 2)
            self.target._tpm.start_acquisition(start_time, delay)
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with keywords:\n" "StartTime, Delay",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def StartAcquisition(self, argin):
        """ Start data acquisition

        :param argin: json dictionary with optional keywords:

        * StartTime - (int) start time
        * Delay - (int) delay start

        :type argin: DevString

        :return: (ResultCode, 'informational message')

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"StartTime":10, "Delay":20}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("StartAcquisition", jstr)
        """
        handler = self.get_command_object("StartAcquisition")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class SetTimeDelaysCommand(ResponseCommand):
        """
        Class for handling the SetTimeDelays() command.
        """

        def do(self, argin):
            delays = argin
            self.target._tpm.set_time_delays(delays)
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_in="DevVarDoubleArray",
        doc_in="time delays",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def SetTimeDelays(self, argin):
        """ Set coarse zenith delay for input ADC streams
            Delay specified in nanoseconds, nominal is 0.

        :param argin: the delay in samples, positive delay adds delay
                       to the signal stream
        :type argin: DevVarDoubleArray

        :return: (ResultCode, 'informational message')

        :example:

        >>> delays = [3.4] * n (How many & int or float : Alessio?)
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("SetTimedelays", delays)
        """
        handler = self.get_command_object("SetTimeDelays")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class SetCspRoundingCommand(ResponseCommand):
        """
        Class for handling the SetCspRounding() command.
        """

        def do(self, argin):
            rounding = argin
            self.target._tpm.set_csp_rounding(rounding)
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_in="DevDouble",
        doc_in="csp rounding",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def SetCspRounding(self, argin):
        """ Set output rounding for CSP

        :param rounding: the rounding
        :type rounding: DevDouble

        :return: (ResultCode, 'informational message')

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("SetCspRounding", 3.142)
        """
        handler = self.get_command_object("SetCspRounding")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class SetLmcIntegratedDownloadCommand(ResponseCommand):
        """
        Class for handling the SetLmcIntegratedDownload() command.
        """

        def do(self, argin):
            params = json.loads(argin)
            mode = params.get("Mode", None)
            if mode is None:
                self.logger.error("Mode is a mandatory parameter")
                raise ValueError("Mode is a mandatory parameter")
            channel_payload_length = params.get("ChannelPayloadLength", 2)
            beam_payload_length = params.get("BeamPayloadLength", 2)
            dst_ip = params.get("DstIP", None)
            src_port = params.get("SrcPort", 0xf0d0)
            dst_port = params.get("DstPort", 4660)
            lmc_mac = params.get("LmcMac", None)
            self.target._tpm.set_lmc_integrated_download(
                mode,
                channel_payload_length,
                beam_payload_length,
                dst_ip,
                src_port,
                dst_port,
                lmc_mac,
            )
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with keywords:\n"
        "Mode,ChannelPayloadLength,BeamPayloadLength|n"
        "DstIP,SrcPort,DstPort, LmcMac",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def SetLmcIntegratedDownload(self, argin):
        """ Configure link and size of control data

        :param argin: json dictionary with optional keywords:

        * Mode - (string) '1g' or '10g' (Mandatory)
        * ChannelPayloadLength - (int) SPEAD payload length for integrated channel data
        * BeamPayloadLength - (int) SPEAD payload length for integrated beam data
        * DstIP - (string) Destination IP
        * SrcPort - (int) Source port for integrated data streams
        * DstPort - (int) Destination port for integrated data streams
        * LmcMac: - (int) LMC Mac address is required for 10G lane configuration

        :type argin: DevString

        :return: (ResultCode, 'informational message')

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"Mode": "1G", "ChannelPayloadLength":4,
                    "BeamPayloadLength": 6, DstIP="10.0.1.23"}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SetLmcIntegratedDownload", jstr)
        """
        handler = self.get_command_object("SetLmcIntegratedDownload")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class SendRawDataSynchronisedCommand(ResponseCommand):
        """
        Class for handling the SendRawDataSynchronised() command.
        """

        def do(self, argin):
            params = json.loads(argin)
            period = params.get("Period", 0)
            timeout = params.get("Timeout", 0)
            timestamp = params.get("Timestamp", None)
            seconds = params.get("Seconds", 0.2)
            self.target._tpm.send_raw_data_synchronised(
                period, timeout, timestamp, seconds
            )
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with keywords:\n" "Period,Timeout,Timestamp,Seconds",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    def SendRawDataSynchronised(self, argin):
        """  Send synchronised raw data

        :param argin: json dictionary with optional keywords:

        * Period - (int) in seconds to send data
        * Timeout - (int) When to stop
        * Timestamp - (string??) When to send
        * Seconds - (float) When to synchronise

        :type argin: DevString

        :return: (ResultCode, 'informational message')

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"Period": 10, "Timeout":4, "Seconds": 0.5}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SendRawDataSynchronised", jstr)
        """
        handler = self.get_command_object("SendRawDataSynchronised")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class SendChannelisedDataNarrowbandCommand(ResponseCommand):
        """
        Class for handling the SendChannelisedDataNarrowband() command.
        """

        def do(self, argin):
            params = json.loads(argin)
            frequency = params.get("Frequency", None)
            if frequency is None:
                self.logger.error("Frequency is a mandatory parameter")
                raise ValueError("Frequency is a mandatory parameter")
            round_bits = params.get("RoundBits", None)
            if round_bits is None:
                self.logger.error("RoundBits is a mandatory parameter")
                raise ValueError("RoundBits is a mandatory parameter")
            number_of_samples = params.get("NSamples", 128)
            wait_seconds = params.get("WaitSeconds", 0)
            timeout = params.get("Timeout", 0)
            timestamp = params.get("Timestamp", None)
            seconds = params.get("Seconds", 0.2)
            self.target._tpm.send_channelised_data_narrowband(
                frequency,
                round_bits,
                number_of_samples,
                wait_seconds,
                timeout,
                timestamp,
                seconds,
            )
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with keywords:\n"
        "Frequency,RoundBits,NSamples,WaitSeconds,Timeout,Timestamp,Seconds",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def SendChannelisedDataNarrowband(self, argin):
        """
        Continuously send channelised data from a single channel end data
         from channel channel continuously (until stopped)

        This is a special mode used for UAV campaigns and not really
        part of the standard signal processing chain. I don’t know if
        this mode will be kept or not.

        :param argin: json dictionary with 2 mandatory and optional keywords:

        * Frequency - (int) Sky frequency to transmit
        * RoundBits - (int)  Specify which bits to round
        * NSamples -  (int) number of spectra to send
        * WaitSeconds - (int) Wait time before sending data
        * Timeout - (int) When to stop
        * Timestamp - (string??) When to start
        * Seconds - (float) When to synchronise

        :type argin: DevString

        :return: (ResultCode, 'informational message')

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"Frequency":2000, "RoundBits":256, "NSamples":256,
                    "WaitSeconds": 10, "Seconds": 0.5}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SendChannelisedDataNarrowband", jstr)
        """
        handler = self.get_command_object("SendChannelisedDataNarrowband")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class TweakTransceiversCommand(ResponseCommand):
        """
        Class for handling the TweakTransceivers() command.
        """

        def do(self):
            self.target._tpm.tweak_transceivers()
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def TweakTransceivers(self):
        """
        Tweak the transceivers

        :return: (ResultCode, 'informational message')

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("tweak_transceivers")
        """
        handler = self.get_command_object("TweakTransceivers")
        (return_code, message) = handler()
        return [[return_code], [message]]

    class PostSynchronisationCommand(ResponseCommand):
        """
        Class for handling the PostSynchronisation() command.
        """

        def do(self):
            self.target._tpm.post_synchronisation()
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def PostSynchronisation(self):
        """
        Post tile configuration synchronization

        :return: (ResultCode, 'informational message')

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("PostSynchronisation")
        """
        handler = self.get_command_object("PostSynchronisation")
        (return_code, message) = handler()
        return [[return_code], [message]]

    class SyncFpgasCommand(ResponseCommand):
        """
        Class for handling the SyncFpgas() command.
        """

        def do(self):
            self.target._tpm.sync_fpgas()
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def SyncFpgas(self):
        """
        Synchronise the FPGAs

        :return: (ResultCode, 'informational message')

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("SyncFpgas")
        """
        handler = self.get_command_object("SyncFpgas")
        (return_code, message) = handler()
        return [[return_code], [message]]

    class CalculateDelayCommand(ResponseCommand):
        """
        Class for handling the Configure() command.
        """

        def do(self, argin):
            params = json.loads(argin)
            current_delay = params.get("CurrentDelay", None)
            if current_delay is None:
                self.logger.error("CurrentDelay is a mandatory parameter")
                raise ValueError("CurrentDelay is a mandatory parameter")
            current_tc = params.get("CurrentTC", None)
            if current_tc is None:
                self.logger.error("CurrentTC is a mandatory parameter")
                raise ValueError("CurrentTC is a mandatory parameter")
            ref_lo = params.get("RefLo", None)
            if ref_lo is None:
                self.logger.error("RefLo is a mandatory parameter")
                raise ValueError("RefLo is a mandatory parameter")
            ref_hi = params.get("RefHi", None)
            if ref_hi is None:
                self.logger.error("RefHi is a mandatory parameter")
                raise ValueError("RefHi is a mandatory parameter")
            self.target._tpm.calculate_delay(current_delay, current_tc, ref_lo, ref_hi)
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with keywords:\n" "CurrentDelay,CurrentTC,RefLo,RefHi",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def CalculateDelay(self, argin):
        """ Calculate delay

        :param argin: json dictionary with 4 mandatory keywords:

        * CurrentDelay - (float??) Current delay
        * CurrentTC - (float??) Current phase register terminal count
        * RefLo - (float??) Low reference
        * RefHi -(float??) High reference

        :type argin: DevString

        :return: (ResultCode, 'informational message')

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"CurrentDelay":0.4, "CurrentTC":56.2, "RefLo":3.0, "RefHi":78.9}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("CalculateDelay", jstr)
        """
        handler = self.get_command_object("CalculateDelay")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    # --------------------
    # Asynchronous routine
    # --------------------
    def _create_long_running_task(self):
        self._streaming = True
        self.logger.info("create task")
        executor = futures_executor.get_global_executor()
        self._read_task = executor.delegate(self.__do_read)

    def __do_read(self):
        while self._streaming:
            try:
                # if connected read the values from tpm
                if self._tpm is not None and self._is_connected:
                    self.logger.info("stream on")
                    volts = self._tpm.voltage()
                    curr = self._tpm.current()
                    temp = self._tpm.temperature()
                    temp1 = self._tpm.get_fpga1_temperature()
                    temp2 = self._tpm.get_fpga2_temperature()

                    with self._lock:
                        # now update the attribute using lock to prevent access conflict
                        state = self.get_state()
                        if state != DevState.ALARM:
                            saved_state = state
                        self._voltage = volts
                        self._current = curr
                        self._board_temperature = temp
                        self._fpga1_temperature = temp1
                        self._fpga2_temperature = temp2
                        self.push_change_event("voltage", volts)
                        self.push_change_event("current", curr)
                        self.push_change_event("board_temperature", temp)
                        self.push_change_event("fpga1_temperature", temp1)
                        self.push_change_event("fpga2_temperature", temp2)
                        self.push_archive_event("voltage", volts)
                        self.push_archive_event("current", curr)
                        self.push_archive_event("board_temperature", temp)
                        self.push_archive_event("fpga1_temperature", temp1)
                        self.push_archive_event("fpga2_temperature", temp2)
                        if (
                            self._voltage < self.voltage.get_min_alarm()
                            or self._voltage > self.voltage.get_max_alarm()
                            or self._current < self.current.get_min_alarm()
                            or self._current > self.current.get_max_alarm()
                            or self._board_temperature
                            < self.board_temperature.get_min_alarm()
                            or self._board_temperature
                            > self.board_temperature.get_max_alarm()
                            or self._fpga1_temperature
                            < self.fpga1_temperature.get_min_alarm()
                            or self._fpga1_temperature
                            > self.fpga1_temperature.get_max_alarm()
                            or self._fpga2_temperature
                            < self.fpga2_temperature.get_min_alarm()
                            or self._fpga2_temperature
                            > self.fpga2_temperature.get_max_alarm()
                        ):
                            self.set_state(DevState.ALARM)
                            self._healthState = HealthState.DEGRADED
                        else:
                            self.set_state(saved_state)
                            self._healthState = HealthState.OK
                        self.push_change_event("healthState", self._healthState)
            except Exception as exc:
                self.set_state(DevState.FAULT)
                self.logger.error(exc.what())

            #  update every second (should be settable?)
            self.logger.debug(f"sleep {self._update_frequency}")
            time.sleep(self._update_frequency)
            if not self._streaming:
                break


# ----------
# Run server
# ----------
def main(args=None, **kwargs):
    """Main function of the MccsTile module."""

    return MccsTile.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
