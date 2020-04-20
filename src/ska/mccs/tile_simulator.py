# -*- coding: utf-8 -*-
#
# This file is part of the MccsTileSimulator project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

""" SKA MCCS Tile Simulator Device Server
This instance of Tile device has been adapted to pose as a Simulator.
The Tile Device represents the TANGO interface to a Tile (TPM) unit
"""
__all__ = ["MccsTileSimulator", "main"]

import os
import json

# PyTango imports
from tango import DebugIt
from tango import DevState
from tango.server import attribute, command
from tango.server import device_property, Device

# Additional import

from ska.mccs import MccsGroupDevice
from ska.mccs.tpm_simulator import TpmSimulator
from ska.base.control_model import SimulationMode, TestMode, LoggingLevel


class MccsTileSimulator(MccsGroupDevice):
    """
    The Tile Device represents the TANGO interface to a Tile (TPM) unit

    **Properties:**

    - Device Property
    """

    # -----------------
    # Device Properties
    # -----------------
    TileIP = device_property(dtype=str, default_value="0.0.0.0")
    TpmCpldPort = device_property(dtype=int, default_value=20000)
    LmcIp = device_property(dtype=str, default_value="0.0.0.0")
    DstPort = device_property(dtype=int, default_value=30000)
    AntennasPerTile = device_property(dtype=int, default_value=16)

    # ---------------
    # General methods
    # ---------------

    def init_device(self):
        """Initialises the attributes and properties of the Mccs."""
        super().init_device()

        self.logger.LoggingLevel = LoggingLevel.ERROR
        self.set_state(DevState.INIT)
        self._ip_address = self.TileIP
        self._port = self.TpmCpldPort
        self._lmc_ip = self.LmcIp
        self._lmc_port = self.DstPort
        self._antennas_per_tile = self.AntennasPerTile

        self._programmed = False
        self._tile_id = -1
        self._subarray_id = -1
        self._station_id = -1
        self._logical_tpm_id = -1
        self._csp_destination_ip = ""
        self._csp_destination_mac = ""
        self._csp_destination_port = 0
        self._firmware_name = ""
        self._firmware_version = ""
        self._voltage = 0.0
        self._current = 0.0
        self._board_temperature = 0.0
        self._fpga1_temperature = 0.0
        self._fpga2_temperature = 0.0
        self._fpga1_time = 0.0
        self._fpga2_time = 0.0
        self._antenna_ids = []
        self._forty_gb_destination_ips = []
        self._forty_gb_destination_macs = []
        self._forty_gb_destination_ports = []
        self._forty_gb_core_list = []
        self._adc_power = []
        self._sampling_rate = 0.0
        self._tpm = None
        self.simulationMode = SimulationMode.TRUE
        self._default_tapering_coeffs = [float(1) for i in range(self.AntennasPerTile)]
        self._is_connected = False
        self.set_state(DevState.OFF)
        self.logger.info("MccsTileSimulator init_device complete")

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
    def logicalTpmId(self):
        """Return the logicalTpmId attribute."""
        return self._logical_tpm_id

    @logicalTpmId.write
    def logicalTpmId(self, value):
        """Set the logicalTpmId attribute."""
        self._logical_tpm_id = value

    @attribute(dtype="DevLong", doc="The identifier of the associated subarray.")
    def subarrayId(self):
        """Return the subarrayId attribute."""
        return self._subarray_id

    @subarrayId.write
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

    @attribute(dtype="DevDouble", fisallowed=is_connected)
    def voltage(self):
        """Return the voltage attribute."""
        return self._tpm.voltage()

    @attribute(dtype="DevDouble", fisallowed=is_connected)
    def current(self):
        """Return the current attribute."""
        return self._tpm.current()

    @attribute(
        dtype="DevBoolean",
        doc="Return True if the all FPGAs are programmed, False otherwise",
    )
    def isProgrammed(self):
        """ Function that returns true if board is programmed"""
        return self._tpm.is_programmed()

    @attribute(dtype="DevDouble", doc="The board temperature", fisallowed=is_connected)
    def board_temperature(self):
        """Return the board_temperature attribute."""
        return self._tpm.temperature()

    @attribute(dtype="DevDouble", fisallowed=is_connected)
    def fpga1_temperature(self):
        """Return the fpga1_temperature attribute."""
        if self.isProgrammed:
            return self._tpm.get_fpga1_temperature()
        else:
            return 0

    @attribute(dtype="DevDouble", fisallowed=is_connected)
    def fpga2_temperature(self):
        """Return the fpga2_temperature attribute."""
        if self.isProgrammed:
            return self._tpm.get_fpga2_temperature()
        else:
            return 0

    @attribute(dtype="DevDouble", fisallowed=is_connected)
    def fpga1_time(self):

        """Return the fpga1_time attribute."""

        # return self["fpga1.pps_manager.curr_time_read_val"]
        return self._fpga1_time

    @fpga1_time.write
    def fpga1_time(self, value):
        """Set the fpga1_time attribute."""
        # self["fpga1.pps_manager.curr_time_write_val"] = value
        # self["fpga1.pps_manager.curr_time_cmd.wr_req"] = 0x1
        self._fpga1_time = value

    @attribute(dtype="DevDouble", fisallowed=is_connected)
    def fpga2_time(self):
        """Return the fpga2_time attribute."""
        # return self["fpga2.pps_manager.curr_time_read_val"]
        return self._fpga2_time

    @fpga2_time.write
    def fpga2_time(self, value):
        """Set the fpga2_time attribute."""
        # self["fpga2.pps_manager.curr_time_write_val"] = value
        # self["fpga2.pps_manager.curr_time_cmd.wr_req"] = 0x1
        self._fpga2_time = value

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

    @attribute(
        dtype=("DevString",),
        max_dim_x=256,
        doc="""40Gb destination IP for all 40Gb ports on the Tile (source
        automatically set during initialization)""",
    )
    def fortyGbDestinationIps(self):
        """Return the fortyGbDestinationIps attribute."""
        return self._forty_gb_destination_ips

    @attribute(
        dtype=("DevString",),
        max_dim_x=256,
        doc="""40Gb destination MACs for all 40Gb ports on the Tile (source
        automatically set during initialization)""",
    )
    def fortyGbDestinationMacs(self):
        """Return the fortyGbDestinationMacs attribute."""
        return self._forty_gb_destination_macs

    @attribute(
        dtype=("DevLong",),
        max_dim_x=256,
        doc="""40Gb destination ports for all 40Gb ports on the Tile (source
        automatically set during initialization"")""",
    )
    def fortyGbDestinationPorts(self):
        """Return the fortyGbDestinationPorts attribute."""
        return self._forty_gb_destination_ports

    @attribute(
        dtype=("DevDouble",),
        max_dim_x=32,
        doc="Return the RMS power of every ADC signal (so a TPM processes "
        "16 antennas, this should return 32 RMS values)",
        fisallowed=is_connected,
    )
    def adcPower(self):
        # If board is not programmed, return None
        if not self._tpm.is_programmed():
            return None

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
        self._tpm.get_pps_delay()

    # --------
    # Commands
    # --------

    @command()
    @DebugIt()
    def Initialise(self):

        """
        Performs all required initialisation (switches on on-board devices,
        locks PLL, performs synchronisation and other operations required
        to start configuring the signal processing functions of the firmware,
        such as channelisation and beamforming)

        :return: None
        """
        self._tpm.initialise()

    #         if self._tpm is None:
    #             self.logger.error("Not connected")
    #             return
    #
    #         # Before initialising, check if TPM is programmed
    #         if not self._tpm.is_programmed():
    #             self.logger.error("Cannot initialise board which is not programmed")
    #             return
    #
    #         # Initialise firmware plugin
    #         self._tpm.initialise_firmware()
    #
    #         # Set LMC IP
    #         self._tpm.set_lmc_ip(self._lmc_ip, self._lmc_port)
    #
    #         # Enable C2C streaming
    #         # self._tpm["board.regfile.c2c_stream_enable"] = 0x1
    #         # self.set_c2c_burst()
    #
    #         #         # Switch off both PREADUs
    #         #         self._tpm.preadu[0].switch_off()
    #         #         self._tpm.preadu[1].switch_off()
    #         #
    #         #         # Switch on preadu
    #         #         for preadu in self._tpm.preadu:
    #         #             preadu.switch_on()
    #         #             time.sleep(1)
    #         #             preadu.select_low_passband()
    #         #             preadu.read_configuration()
    #
    #         # Synchronise FPGAs
    #         # self.sync_fpgas()
    #
    #         # Initialize f2f link
    #         self._tpm.initialise_f2f_link()
    #
    #         # Reset test pattern generator
    #         self._tpm.reset_test_generator()
    #
    #         # Use test_generator plugin instead!
    #         if self.testMode:
    #             # Test pattern. Tones on channels 72 & 75 + pseudo-random noise
    #             self.logger.info("Enabling test pattern")
    #             self._tpm.enable_test_pattern()
    #
    #         # Set destination and source IP/MAC/ports for 10G cores
    #         # This will create a loopback between the two FPGAs
    #         ip_octets = self._ip.split(".")
    #         for n in range(8):
    #             src_ip = "10.{}.{}.{}".format(n + 1, ip_octets[2], ip_octets[3])
    #             dst_ip = "10.{}.{}.{}".format(
    #                 (1 + n) + (4 if n < 4 else -4), ip_octets[2], ip_octets[3]
    #             )
    #         #             self.Configure40GCore(n,
    #         #                                     src_mac=0x620000000000, ###+ ip2long(src_ip),
    #         #                                     src_ip=src_ip,
    #         #                                     src_port=0xF0D0,
    #         #                                     dst_mac=0x620000000000, ###+ ip2long(dst_ip),
    #         #                                     dst_ip=dst_ip,
    #         #                                     dst_port=4660)
    #
    #         # wait UDP link up
    #         self.logger.info("Waiting for 10G link...")
    #         try:
    #             times = 0
    #             while True:
    #                 linkup = 1
    #                 for n in [0, 1, 2, 4, 5, 6]:
    #                     core_status = self._tpm.get_arp_table_status(n)
    #                     if core_status & 0x4 == 0:
    #                         linkup = 0
    #                 if linkup == 1:
    #                     self.logger.info("40G Link established! ARP table populated!")
    #                     break
    #                 else:
    #                     times += 1
    #                     time.sleep(0.5)
    #                     if times == 20:
    #                         self.logger.warning(
    #                             "40G Links not established after 10 seconds! ARP table not populated!"
    #                         )
    #                         break
    #         except:
    #             time.sleep(4)
    #             # self.mii_exec_test(10, False)
    #             # self['fpga1.regfile.eth10g_ctrl'] = 0x0
    #             # self['fpga2.regfile.eth10g_ctrl'] = 0x0
    #
    #         self._tpm.check_ddr_initialisation()

    @command(dtype_in="DevBoolean", doc_in="Initialise")
    @DebugIt()
    def Connect(self, initialise):
        """
        Creates connection to board. When True the initialise function is
        called immediately after connection (board must be programmed)

        :param initialise: When True initialise immediately after connection
        :type initialise: DevBoolean

        :return: None
        """
        if self.simulationMode:
            self._tpm = TpmSimulator(self.logger)
        else:
            self._tpm = Tpm(
                self._ip_address,
                self._port,
                self._lmc_ip,
                self._lmc_port,
                self._sampling_rate,
            )

        self._tpm.connect(
            #            ip=self._ip_address,
            #            port=self._port,
            initialise=initialise,
            simulation=self.simulationMode,
            enable_ada=self.testMode,
            #            fsample=self._sampling_rate,
        )

        # Load tpm test firmware for both FPGAs (no need to load in simulation)
        if not self.simulationMode and self._tpm.is_programmed():
            self._tpm.load_plugin("TpmTestFirmware", fsample=self._sampling_rate)
        elif not self._tpm.is_programmed():
            self.logger.warning("TPM is not programmed! No plugins loaded")

        if initialise:
            self.Initialise()

        self._is_connected = True
        self.set_state(DevState.ON)

    @command()
    @DebugIt()
    def Disconnect(self):

        """
        Disconnects from the board, the internal state needs to be reset

        :return: None
        """

    pass

    @command(dtype_out="DevVarStringArray", doc_out="list of firmware")
    @DebugIt()
    def GetFirmwareList(self):
        """Return a list containing the following information for each
        firmware stored on the board (such as in Flash memory).
        For each firmware, a dictionary containing the following keys with
        their respective values should be provided: ‘design’, which is a textual
        name for the firmware, ‘major’, which is the major version number, and
        ‘minor’.
        """
        return []

    @command(dtype_in="DevString", doc_in="bitfile location")
    @DebugIt()
    def DownloadFirmware(self, bitfile):
        """
        Downloads the firmware contained in bitfile to all FPGAs on the board.
        This should also update the internal register mapping, such that
        registers become available for use.

        :param bitfile: can either be the design name returned from get_firmware_list(),
                        or a path to a file
        :type bitfile: 'DevString'

        :return: None
        """
        if not self.simulationMode and self._tpm is not None:
            self.logger.info("Downloading bitfile to board")
            self._tpm.download_firmware(bitfile)

    @command(dtype_in="DevString", doc_in="bitfile location")
    @DebugIt()
    def ProgramCPLD(self, bitfile):

        """
        If the TPM has a CPLD (or other management chip which need firmware),
        this function program it with the provided bitfile.

        :param bitfile: is the path to a file containing the required CPLD firmware
        :type: 'DevString'

        :return: None
        """
        if not self.simulationMode and self._tpm is not None:
            self.logger.info("Downloading bitstream to CPLD FLASH")
            self._tpm.cpld_flash_write(bitfile)

    @command()
    @DebugIt()
    def WaitPPSEvent(self):

        """
        Block until a PPS edge is detected, then return from function

        :return: None
        """
        if self._tpm is not None:
            t0 = self.fpga1_time()
            while t0 == self.fpga1_time():
                pass

    @command(dtype_out="DevVarStringArray")
    @DebugIt()
    def GetRegisterList(self):

        """
        Return a list containing description of the exposed firmware (and CPLD)
        registers

        :return: None
        """
        return []

    @command(
        dtype_in="DevVarLongArray",
        doc_in="register_name, n, offset, device",
        dtype_out="DevVarLongArray",
        doc_out="values",
    )
    @DebugIt()
    def ReadRegister(self, argin):

        """
        Return the value of the specified register. register_name is the string
        representation of the register, n is the number of 32-bit words to
        read, offset is the address offset within the register to read from and
        device is the FPGA to read from (from Device enumeration).
        Returns a list of values (unsigned 32-bit

        :param argin: [0] = register
                      [1] = nb_read
                      [2] = offset
                      [3] = fpga device (0,1)

        :return: a list of register values
        :rtype: DevVarUlongArray
        """
        if len(argin) < 4:
            raise ValueError
        return []

    @command(dtype_in="DevVarLongArray", doc_in="register_name, values, offset, device")
    @DebugIt()
    def WriteRegister(self, argin):

        """
        Write values to the specified register. register_name is the string
        representation of the register, values is a list containing the 32-bit
        values to write, offset is the address offset within the register
        to write to and device is the FPGA to write to (from Device
        enumeration).

        :return: None
        """
        pass

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

        :return:'DevVarULongArray'
        """
        return [0]

    @command(dtype_in="DevVarULongArray", doc_in="address, values")
    @DebugIt()
    def WriteAddress(self, argin):

        """
        Write list of values at addres

        :param argin: 'DevVarULongArray'

        :return: None
        """
        pass

    @command(
        dtype_in="DevVarULongArray",
        doc_in="core_id, src_mac, src_ip, dst_mac, dst_ip, src_port, dst_port",
    )
    @DebugIt()
    def Configure40GCore(self, argin):

        """
        Configure 40g core_id with specified parameters.
        All parameters are numeric values

        :param argin: [0] = core_id
                      [1] = src_mac
                      [2] = src_ip
                      [3] = src_port
                      [4] = dst_mac
                      [5] = dst_ip
                      [6] = dst_port
        :type argin: DevVarULongArray

        :return: None
        """
        if len(argin) < 7:
            raise ValueError
        self._forty_gb_core_list.append(
            {
                "core_id": argin[0],
                "src_mac": argin[1],
                "src_ip": argin[2],
                "src_port": argin[3],
                "dst_mac": argin[4],
                "dst_ip": argin[5],
                "dst_port": argin[6],
            }
        )

    @command(
        dtype_in="DevLong",
        doc_in="coreId",
        dtype_out="DevVarULongArray",
        doc_out="configuration",
    )
    @DebugIt()
    def Get40GCoreConfiguration(self, argin):

        """
        Get 10g core configuration for core_id.
        This is required to chain up TPMs to form a station

        :return: the configuration as an array comprising:
                 src_mac, src_ip, src_port, dest_mac, dest_ip, dest_port
        :rtype: DevVarUlongArray
        """
        for item in self._forty_gb_core_list:
            if argin == item["core_id"]:
                return [
                    item["src_mac"],
                    item["src_ip"],
                    item["src_port"],
                    item["dst_mac"],
                    item["dst_ip"],
                    item["dst_port"],
                ]
        raise ValueError("Invalid core id specified")

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with keywords:\n"
        "Mode,PayloadLength,DstIP,SrcPort,DstPort, LmcMac",
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

        :return: None

        :example:
    
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"Mode": "1G", "PayloadLength":4,DstIP="10.0.1.23"}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SetLmcDownload", jstr)
        """
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
        self._tpm.set_lmc_download(
            mode, payload_length, dst_ip, src_port, dst_port, lmc_mac
        )

    @command(dtype_in="DevVarLongArray", doc_in="truncation array")
    @DebugIt()
    def SetChanneliserTruncation(self, argin):

        """
        Set the coefficients to modify (flatten) the bandpass.
        truncation is a N x M array, where N is the number of input channels
        and M is the number of frequency channel

        :return: None
        """
        pass

    @command(dtype_in="DevVarLongArray", doc_in="region_array")
    @DebugIt()
    def SetBeamFormerRegions(self, argin):

        """
        Set the frequency regions which are going to be beamformed into a
        single beam.
        region_array is defined as a 2D array, for a maximum of 16 regions.
        Each element in the array defines a region, with:
        start_channel: region starting channel
        nof_channels: size of the region, must be a multiple of 8
        beam_index: beam used for this region with range 0 to 7
        Total number of channels must be <= 384

        :return: None
        """
        if len(argin) < 3:
            self.logger.error("Insufficient parameters")
            return
        if len(argin) > 48:
            self.logger.error("Too many regions specified")
            return
        region_array = []
        total_chan = 0
        for i in range(len(argin) / 3):
            start_channel = argin[i * 3]
            nchannels = argin[i * 3 + 1]
            if nchannels % 8 != 0:
                self.logger.error("Nos. of channels in region must be multiple of 8")
                return
            beam_index = argin[i * 3 + 2]
            if beam_index < 0 or beam_index > 7:
                self.logger.error("Beam_index is out side of range 0-7")
                return
            total_chan += nchannels
            i += 3
        if total_chan > 384:
            self.logger.error("Too many channels specified > 384")
            return
        region_array.append([start_channel, nchannnels, beam_index])
        self._tpm.set_beamfomer_regions(region_array)

    @command(
        dtype_in="DevVarLongArray", doc_in="n_of_tiles, first_tile=False, start=False"
    )
    @DebugIt()
    def ConfigureStationBeamformer(self, argin):

        """
        Initialise and start the station beamformer.
        nof_tiles is the number of tiles in the station,
        first_tile specifies whether the tile is the first one in the station,
        and start, when True, starts the beamformer

        :return: None
        """
        if len(argin) < 4:
            self.logger.error("Insufficient parameters supplied")
            return
        start_channel = argin[0]
        nof_channels = argin[1]
        is_first = argin[2]
        is_last = argin[3]
        self._tpm.initialise_beamformer(start_channel, nof_channels, is_first, is_last)

    @command(dtype_in="DevVarDoubleArray", doc_in="antenna, calibration_coefficients")
    @DebugIt()
    def LoadCalibrationCoefficients(self, argin):

        """
        Loads calibration coefficients (but does not apply them, this is
        performed by switch_calibration_bank). antenna is the antenna to which
        the coefficients will be applied. calibration_coefficients is a
        bidimensional complex array of the form
        calibration_coefficients[channel, polarization], with each element
        representing a normalized coefficient, with (1.0, 0.0) being the
        normal, expected response for an ideal antenna. channel is the index
        specifying the channels at the beamformer output, i.e. considering only
        those channels actually processed and beam assignments. The
        polarization index ranges from 0 to 3.
        0: X polarization direct element
        1: X->Y polarization cross element
        2: Y->X polarization cross element
        3: Y polarization direct element
        The calibration coefficients may include any rotation matrix (e.g. the
        parallactic angle), but do not include the geometric delay

        :return: None
        """
        pass

    @command(dtype_in="DevVarDoubleArray", doc_in="angle_coefficients")
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

        :return: None

        :example:

        >>> angle_coeffs = [3.4] * 16
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("LoadBeamAngle", angle_coeffs)
        """
        self._tpm.load_beam_angle(argin)

    @command(dtype_in="DevVarDoubleArray", doc_in="tapering coefficients")
    @DebugIt()
    def LoadAntennaTapering(self, argin):

        """
        tapering_coeffs is a vector contains a value for each antenna the TPM
        processes. Default at initialisation is 1.0

        :param argin: list of tapering coefficients for each antenna
        :type argin: DevVarDoubleArray

        :return: None

        :example:

        >>> tapering_coeffs = [3.4] * 16
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("LoadAntennaTapering", tapering_coeffs)
        """
        if len(argin) < self.AntennasPerTile:
            self.logger.error(
                f"Insufficient tapering coefficients should be {self.AntennasPerTile}"
            )
            raise ValueError(
                f"Insufficient tapering coefficients should be {self.AntennasPerTile}"
            )
        self._tpm.load_antenna_tapering(argin)

    @command(dtype_in="DevLong", doc_in="switch time")
    @DebugIt()
    def SwitchCalibrationBank(self, switch_time):

        """
        Load the calibration coefficients at the specified time delay

        :param switch_time: time
        :type switch_time: DevLong

        :return: None

        :example:
    
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("SwitchCalibrationBank", 10)
        """
        self._tpm.switch_calibration_bank(switch_time)

    @command(dtype_in="DevVarDoubleArray", doc_in="delay_array, beam_index")
    @DebugIt()
    def SetPointingDelay(self, argin):

        """
        Specifies the delay in seconds and the delay rate in seconds/seconds.
        The delay_array specifies the delay and delay rate for each antenna.
        beam_index specifies which beam is desired (range 0-7)

        :return: None
        """
        if len(argin) != self.AntennasPerTile * 2 + 1:
            self.logger.error("Insufficient parameters")
            raise ValueError("Insufficient parameters")
        beam_index = int(argin[0])
        if beam_index < 0 or beam_index > 7:
            self.logger.error("Invalid beam index")
            raise ValueError("Invalid beam index")
        delay_array = []
        for i in range(self.AntennasPerTile):
            delay_array.append([argin[i * 2 + 1], argin[i * 2 + 2]])
        self._tpm.set_pointing_delay(delay_array, beam_index)

    @command(dtype_in="DevLong", doc_in="load_time")
    @DebugIt()
    def LoadPointingDelay(self, load_time):

        """
        Loads the pointing delays at the specified time delay

        :param load_time: time delay (default = 0)
        :type load_time: DevLong

        :return: None

        :example:
    
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("LoadPointingDelay", 10)
        """
        self._tpm.load_pointing_delay(load_time)

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with keywords:\n" "StartTime, Duration",
    )
    @DebugIt()
    def StartBeamformer(self, argin):

        """
        Start the beamformer at the specified time delay

        :param argin: json dictionary with optional keywords:

        * StartTime - (int) start time
        * Duration - (int) if > 0 is a duration in frames * 256 (276.48 us)
                           if == -1 run forever

        :return: None

        :example:
    
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"StartTime":10, "Duration":20}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("StartBeamformer", jstr)
        """
        params = json.loads(argin)
        start_time = params.get("StartTime", 0)
        duration = params.get("Duration", -1)
        self._tpm.start_beamformer(start_time, duration)

    @command()
    @DebugIt()
    def StopBeamformer(self):

        """
        Stop the beamformer

        :return: None

        :example:
    
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("StopBeamformer")
        """
        self._tpm.stop_beamformer()

    @command(dtype_in="DevDouble", doc_in="Integration time")
    @DebugIt()
    def ConfigureIntegratedChannelData(self, integration_time):

        """
        Configure the transmission of integrated channel data with the
        provided integration time

        :param integration_time: time in seconds (default = 0.5)
        :type integration_time: DevDouble

        :return: None

        :example:
    
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("ConfigureIntegratedChannelData", 6.284)
        """
        if integration_time <= 0:
            integration_time = 0.5
        self._tpm.configure_integrated_channel_data(integration_time)

    @command(dtype_in="DevDouble", doc_in="Integration time")
    @DebugIt()
    def ConfigureIntegratedBeamData(self, integration_time):

        """
        Configure the transmission of integrated beam data with the provided
        integration time

        :param integration_time: time in seconds (default = 0.5)
        :type integration_time: DevDouble

        :return: None

        :example:
    
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("ConfigureIntegratedBeamData", 3.142)
        """
        if integration_time <= 0:
            integration_time = 0.5
        self._tpm.configure_integrated_beam_data(integration_time)

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with keywords:\n"
        "Sync,Period,Timeout,Timestamp,Seconds",
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

        :return: None

        :example:
    
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"Sync":True, "Period": 200, "Seconds": 0.5}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SendRawData", jstr)
        """
        params = json.loads(argin)
        sync = params.get("Sync", False)
        period = params.get("Period", 0)
        timeout = params.get("Timeout", 0)
        timestamp = params.get("Timestamp", None)
        seconds = params.get("Seconds", 0.2)
        self._tpm.send_raw_data(sync, period, timeout, timestamp, seconds)

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with keywords:\n"
        "NSamples,FirstChannel,LastChannel,Period,"
        "Timeout,Timestamp,Seconds",
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

        :return: None

        :example:
    
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"FirstChannel":10, "LastChannel": 200, "Seconds": 0.5}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SendChannelisedData", jstr)
        """
        params = json.loads(argin)
        number_of_samples = params.get("NSamples", 1024)
        first_channel = params.get("FirstChannel", 0)
        last_channel = params.get("LastChannel", 511)
        period = params.get("Period", 0)
        timeout = params.get("Timeout", 0)
        timestamp = params.get("Timestamp", None)
        seconds = params.get("Seconds", 0.2)
        self._tpm.send_channelised_data(
            number_of_samples,
            first_channel,
            last_channel,
            period,
            timeout,
            timestamp,
            seconds,
        )

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with keywords:\n"
        "ChannelID,NSamples,WaitSeconds,Timeout,"
        "Timestamp,Seconds",
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

        :return: None

        :example:
    
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"ChannelID":2, "NSamples":256, "Period": 10, "Seconds": 0.5}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SendChannelisedDataContinuous", jstr)
        """
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
        self._tpm.send_channelised_data_continuous(
            channel_id, number_of_samples, wait_seconds, timeout, timestamp, seconds
        )

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with keywords:\n" "Period,Timeout,Timestamp,Seconds",
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

        :return: None

        :example:
    
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"Period": 10, "Timeout":4, "Seconds": 0.5}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SendBeamData", jstr)
        """
        params = json.loads(argin)
        period = params.get("Period", 0)
        timeout = params.get("Timeout", 0)
        timestamp = params.get("Timestamp", None)
        seconds = params.get("Seconds", 0.2)
        self._tpm.send_beam_data(period, timeout, timestamp, seconds)

    @command()
    @DebugIt()
    def StopDataTransmission(self):

        """
        Stop data transmission from board

        :return: None

        :example:
    
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("StopDataTransmission")
        """
        self._tpm.stop_data_transmission()

    @command()
    @DebugIt()
    def ComputeCalibrationCoefficients(self):
        """Compute the calibration coefficients and load
           them in the hardware.

        :return: None

        :example:
    
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("ComputeCalibrationCoefficients")
        """
        self._tpm.compute_calibration_coefficients()

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with keywords:\n" "StartTime, Delay",
    )
    @DebugIt()
    def StartAcquisition(self, argin):
        """ Start data acquisition

        :param argin: json dictionary with optional keywords:

        * StartTime - (int) start time
        * Delay - (int) delay start

        :type argin: DevString

        :return: None

        :example:
    
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"StartTime":10, "Delay":20}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("StartAcquisition", jstr)
        """
        params = json.loads(argin)
        start_time = params.get("StartTime", None)
        delay = params.get("Delay", 2)
        self._tpm.start_acquisition(start_time, delay)

    @command(dtype_in="DevVarDoubleArray", doc_in="time delays")
    @DebugIt()
    def SetTimeDelays(self, delays):
        """ Set coarse zenith delay for input ADC streams
            Delay specified in nanoseconds, nominal is 0.

        :param delays: the delay in samples, positive delay adds delay to the signal stream
        :type argin: DevVarDoubleArray

        :return: None

        :example:

        >>> delays = [3.4] * n (How many & int or float : Alessio?)
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("SetTimedelays", delays)
        """
        self._tpm.set_time_delays(delays)

    @command(dtype_in="DevDouble", doc_in="csp rounding")
    @DebugIt()
    def SetCspRounding(self, rounding):
        """ Set output rounding for CSP
 
        :param rounding: the rounding
        :type rounding: DevDouble

        :return: None

        :example:
    
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("SetCspRounding", 3.142)
        """
        self._tpm.set_csp_rounding(rounding)

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with keywords:\n"
        "Mode,ChannelPayloadLength,BeamPayloadLength|n"
        "DstIP,SrcPort,DstPort, LmcMac",
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

        :return: None

        :example:
    
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"Mode": "1G", "ChannelPayloadLength":4,
                    "BeamPayloadLength": 6, DstIP="10.0.1.23"}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SetLmcIntegratedDownload", jstr)
        """
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
        self._tpm.set_lmc_integrated_download(
            mode,
            channel_payload_length,
            beam_payload_length,
            dst_ip,
            src_port,
            dst_port,
            lmc_mac,
        )

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with keywords:\n" "Period,Timeout,Timestamp,Seconds",
    )
    def SendRawDataSynchronised(self, argin):
        """  Send synchronised raw data

        :param argin: json dictionary with optional keywords:

        * Period - (int) in seconds to send data
        * Timeout - (int) When to stop
        * Timestamp - (string??) When to send
        * Seconds - (float) When to synchronise

        :type argin: DevString

        :return: None

        :example:
    
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"Period": 10, "Timeout":4, "Seconds": 0.5}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SendRawDataSynchronised", jstr)
        """
        params = json.loads(argin)
        period = params.get("Period", 0)
        timeout = params.get("Timeout", 0)
        timestamp = params.get("Timestamp", None)
        seconds = params.get("Seconds", 0.2)
        self._tpm.send_raw_data_synchronised(period, timeout, timestamp, seconds)

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with keywords:\n"
        "Frequency,RoundBits,NSamples,WaitSeconds,Timeout,Timestamp,Seconds",
    )
    @DebugIt()
    def SendChannelisedDataNarrowband(self, argin):
        """
        Continuously send channelised data from a single channelend data from channel channel continuously (until stopped)

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

        :return: None

        :example:
    
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"Frequency":2000, "RoundBits":256, "NSamples":256,
                    "WaitSeconds": 10, "Seconds": 0.5}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SendChannelisedDataNarrowband", jstr)
        """
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
        self._tpm.send_channelised_data_narrowband(
            frequency,
            round_bits,
            number_of_samples,
            wait_seconds,
            timeout,
            timestamp,
            seconds,
        )

    @command()
    @DebugIt()
    def TweakTransceivers(self):
        """
        Tweak the transceivers

        :return: None

        :example:
    
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("tweak_transceivers")
        """
        self._tpm.tweak_transceivers()

    @command()
    @DebugIt()
    def PostSynchronisation(self):
        """
        Post tile configuration synchronization

        :return: None

        :example:
    
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("post_synchronisation")
        """
        self._tpm.post_synchronisation()

    @command()
    @DebugIt()
    def SyncFpgas(self):
        """
        Synchronise the FPGAs

        :return: None

        :example:
    
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("SyncFpgas")
        """
        self._tpm.sync_fpgas()

    @command(
        dtype_in="DevString",
        doc_in="json dictionary with keywords:\n" "CurrentDelay,CurrentTC,RefLo,RefHi",
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

        :return: None

        :example:
    
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"CurrentDelay":0.4, "CurrentTC":56.2, "RefLo":3.0, "RefHi":78.9}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("CalculateDelay", jstr)
        """
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
        TpmSimulator.calculate_delay(current_delay, current_tc, ref_lo, ref_hi)


# ----------
# Run server
# ----------
def main(args=None, **kwargs):
    """Main function of the MccsTileSimulator module."""

    return MccsTileSimulator.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
