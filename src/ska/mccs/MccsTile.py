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

# PyTango imports
import tango
from tango import DebugIt
from tango.server import run
from tango.server import Device
from tango.server import attribute, command
from tango.server import device_property
from tango import AttrQuality, DispLevel, DevState
from tango import AttrWriteType, PipeWriteType


# Additional import
# PROTECTED REGION ID(Mccs.additionnal_import) ENABLED START #
from ska.base import SKABaseDevice

# PROTECTED REGION END #    //  Mccs.additionnal_import

__all__ = ["MccsTile", "main"]


class MccsTile(SKABaseDevice):
    """
    The Tile Device represents the TANGO interface to a Tile (TPM) unit

    **Properties:**

    - Device Property
    """

    # PROTECTED REGION ID(Mccs.class_variable) ENABLED START #
    # PROTECTED REGION END #    //  Mccs.class_variable

    # -----------------
    # Device Properties
    # -----------------

    # ----------
    # Attributes
    # ----------

    tileId = attribute(
        dtype="DevLong",
        access=AttrWriteType.READ_WRITE,
        doc="The global tile identifier",
    )

    logicalTpmId = attribute(
        dtype="DevLong",
        access=AttrWriteType.READ_WRITE,
        doc="Logical tile identifier within a station",
    )

    subarrayId = attribute(
        dtype="DevLong",
        access=AttrWriteType.READ_WRITE,
        doc="The identifier of the associated subarray.",
    )

    ipAddress = attribute(
        dtype="DevString",
        access=AttrWriteType.READ_WRITE,
        doc="LMC address (and global identifier) of Tile",
    )

    lmcIp = attribute(
        dtype="DevString",
        access=AttrWriteType.READ_WRITE,
        doc="LMC IP address to (and from) which LMC data will flow",
    )

    lmcPort = attribute(
        dtype="DevLong",
        access=AttrWriteType.READ_WRITE,
        doc="LMC port to (and from) which LMC data will flow",
    )

    cspDestinationIp = attribute(
        dtype="DevString",
        access=AttrWriteType.READ_WRITE,
        doc="CSP ingest node IP address for station beam (use if Tile is last\none in the beamforming chain)",
    )

    cspDestinationMac = attribute(
        dtype="DevString",
        access=AttrWriteType.READ_WRITE,
        doc="CSP ingest node MAC address for station beam (use if Tile is\nlast one in the beamforming chain)",
    )

    cspDestinationPort = attribute(
        dtype="DevLong",
        access=AttrWriteType.READ_WRITE,
        doc="CSP ingest node port address for station beam (use if Tile is\nlast one in the beamforming chain)",
    )

    firmwareName = attribute(
        dtype="DevString",
        access=AttrWriteType.READ_WRITE,
        doc="Name and identifier of currently running firmware",
    )

    firmwareVersion = attribute(
        dtype="DevString",
        access=AttrWriteType.READ_WRITE,
        doc="Version of currently running firmware",
    )

    voltage = attribute(dtype="DevDouble", access=AttrWriteType.READ_WRITE)

    current = attribute(dtype="DevDouble", access=AttrWriteType.READ_WRITE)

    isProgrammed = attribute(
        dtype="DevBoolean",
        doc="Return True if the all FPGAs are programmed, False otherwise",
    )

    board_temperature = attribute(dtype="DevDouble", doc="The board temperature")

    fpga1_temperature = attribute(dtype="DevDouble")

    fpga2_temperature = attribute(dtype="DevDouble")

    stationId = attribute(
        dtype="DevLong",
        access=AttrWriteType.READ_WRITE,
        doc="The identifier of the associated station.",
    )

    fpga1_time = attribute(dtype="DevDouble", access=AttrWriteType.READ_WRITE)

    fpga2_time = attribute(dtype="DevDouble", access=AttrWriteType.READ_WRITE)

    antennaIds = attribute(
        dtype=("DevLong",),
        access=AttrWriteType.READ_WRITE,
        max_dim_x=8,
        label="Antenna ID's",
        doc="Array holding the logical ID`s of the antenna associated with the Tile device",
    )

    fortyGbDestinationIps = attribute(
        dtype=("DevString",),
        max_dim_x=256,
        doc="40Gb destination IP for all 40Gb ports on the Tile (source\nautomatically set during initialization)",
    )

    fortyGbDestinationMacs = attribute(
        dtype=("DevString",),
        max_dim_x=256,
        doc="40Gb destination MACs for all 40Gb ports on the Tile (source\nautomatically set during initialization)",
    )

    fortyGbDestinationPorts = attribute(
        dtype=("DevLong",),
        access=AttrWriteType.READ_WRITE,
        max_dim_x=256,
        doc="40Gb destination ports for all 40Gb ports on the Tile (source\nautomatically set during initialization)",
    )

    adcPower = attribute(
        dtype=("DevDouble",),
        access=AttrWriteType.READ_WRITE,
        max_dim_x=32,
        doc="Return the RMS power of every ADC signal (so a TPM processes 16 antennas, this should return 32 RMS values)",
    )

    # ---------------
    # General methods
    # ---------------

    def init_device(self):
        """Initialises the attributes and properties of the Mccs."""
        SKABaseDevice.init_device(self)
        # PROTECTED REGION ID(Mccs.init_device) ENABLED START #
        self.set_state(DevState.INIT)
        self._programmed = False
        self._tile_id = None
        self._subarray_id = None
        self._station_id = None
        self._logical_tpm_id = None
        self._ip_address = ""
        self._lmc_ip = ""
        self._lmc_port = None
        self._csp_destination_ip = ""
        self._csp_destination_mac = ""
        self._csp_destination_port = None
        self._forty_g_core_list = []
        self.set_state(DevState.ON)
        print("init_device complete")
        # PROTECTED REGION END #    //  Mccs.init_device

    def always_executed_hook(self):
        """Method always executed before any TANGO command is executed."""
        # PROTECTED REGION ID(Mccs.always_executed_hook) ENABLED START #
        # PROTECTED REGION END #    //  Mccs.always_executed_hook

    def delete_device(self):
        """Hook to delete resources allocated in init_device.

        This method allows for any memory or other resources allocated in the
        init_device method to be released.  This method is called by the device
        destructor and by the device Init command.
        """
        # PROTECTED REGION ID(Mccs.delete_device) ENABLED START #
        # PROTECTED REGION END #    //  Mccs.delete_device

    # ------------------
    # Attributes methods
    # ------------------

    def read_tileId(self):
        # PROTECTED REGION ID(Mccs.tileId_read) ENABLED START #
        """Return the tileId attribute."""
        return self._tile_id
        # PROTECTED REGION END #    //  Mccs.tileId_read

    def write_tileId(self, value):
        # PROTECTED REGION ID(Mccs.tileId_write) ENABLED START #
        """Set the tileId attribute."""
        self._tile_id = value
        # PROTECTED REGION END #    //  Mccs.tileId_write

    def read_logicalTpmId(self):
        # PROTECTED REGION ID(Mccs.logicalTpmId_read) ENABLED START #
        """Return the logicalTpmId attribute."""
        return self._logical_tpm_id
        # PROTECTED REGION END #    //  Mccs.logicalTpmId_read

    def write_logicalTpmId(self, value):
        # PROTECTED REGION ID(Mccs.logicalTpmId_write) ENABLED START #
        """Set the logicalTpmId attribute."""
        self._logical_tpm_id = value
        # PROTECTED REGION END #    //  Mccs.logicalTpmId_write

    def read_subarrayId(self):
        # PROTECTED REGION ID(Mccs.subarrayId_read) ENABLED START #self._tile_id
        """Return the subarrayId attribute."""
        return self._subarray_id
        # PROTECTED REGION END #    //  Mccs.subarrayId_read

    def write_subarrayId(self, value):
        # PROTECTED REGION ID(Mccs.subarrayId_write) ENABLED START #
        """Set the subarrayId attribute."""
        self._subarray_id = value
        # PROTECTED REGION END #    //  Mccs.subarrayId_write

    def read_ipAddress(self):
        # PROTECTED REGION ID(Mccs.ipAddress_read) ENABLED START #
        """Return the ipAddress attribute."""
        return self._ip_address
        # PROTECTED REGION END #    //  Mccs.ipAddress_read

    def write_ipAddress(self, value):
        # PROTECTED REGION ID(Mccs.ipAddress_write) ENABLED START #
        """Set the ipAddress attribute."""
        self._ip_address = value
        # PROTECTED REGION END #    //  Mccs.ipAddress_writeself._tile_id

    def read_lmcIp(self):
        # PROTECTED REGION ID(Mccs.lmcIp_read) ENABLED START #
        """Return the lmcIp attribute."""
        return self._lmc_ip
        # PROTECTED REGION END #    //  Mccs.lmcIp_read

    def write_lmcIp(self, value):
        # PROTECTED REGION ID(Mccs.lmcIp_write) ENABLED START #
        """Set the lmcIp attribute."""
        self._lmc_ip = value
        # PROTECTED REGION END #    //  Mccs.lmcIp_write

    def read_lmcPort(self):
        # PROTECTED REGION ID(Mccs.lmcPort_read) ENABLED START #
        """Return the lmcPort attribute."""
        return self._lmc_port
        # PROTECTED REGION END #    //  Mccs.lmcPort_read

    def write_lmcPort(self, value):
        # PROTECTED REGION ID(Mccs.lmcPort_write) ENABLED START #
        """Set the lmcPort attribute."""
        self._lmc_port = value
        # PROTECTED REGION END #    //  Mccs.lmcPort_write

    def read_cspDestinationIp(self):
        # PROTECTED REGION ID(Mccs.cspDestinationIp_read) ENABLED START #
        """Return the cspDestinationIp attribute."""
        return self._csp_destination_ip
        # PROTECTED REGION END #    //  Mccs.cspDestinationIp_readself._tile_id

    def write_cspDestinationIp(self, value):
        # PROTECTED REGION ID(Mccs.cspDestinationIp_write) ENABLED START #
        """Set the cspDestinationIp attribute."""
        self._csp_destination_ip = value
        # PROTECTED REGION END #    //  Mccs.cspDestinationIp_write

    def read_cspDestinationMac(self):
        # PROTECTED REGION ID(Mccs.cspDestinationMac_read) ENABLED START #
        """Return the cspDestinationMac attribute."""
        return self._csp_destination_mac
        # PROTECTED REGION END #    //  Mccs.cspDestinationMac_read

    def write_cspDestinationMac(self, value):
        # PROTECTED REGION ID(Mccs.cspDestinationMac_write) ENABLED START #
        """Set the cspDestinationMac attribute."""
        self._csp_destination_mac = value
        # PROTECTED REGION END #    //  Mccs.cspDestinationMac_write

    def read_cspDestinationPort(self):
        # PROTECTED REGION ID(Mccs.cspDestinationPort_read) ENABLED START #
        """Return the cspDestinationPort attribute."""
        return self._csp_destination_port
        # PROTECTED REGION END #    //  Mccs.cspDestinationPort_read

    def write_cspDestinationPort(self, value):
        # PROTECTED REGION ID(Mccs.cspDestinationPort_write) ENABLED START #
        """Set the cspDestinationPort attribute."""
        self._csp_destination_port = value
        # PROTECTED REGION END #    //  Mccs.cspDestinationPort_writeself._csp_destination_mac

    def read_firmwareName(self):
        # PROTECTED REGION ID(Mccs.firmwareName_read) ENABLED START #
        """Return the firmwareName attribute."""
        return ""
        # PROTECTED REGION END #    //  Mccs.firmwareName_read

    def write_firmwareName(self, value):
        # PROTECTED REGION ID(Mccs.firmwareName_write) ENABLED START #
        """Set the firmwareName attribute."""
        pass
        # PROTECTED REGION END #    //  Mccs.firmwareName_write

    def read_firmwareVersion(self):
        # PROTECTED REGION ID(Mccs.firmwareVersion_read) ENABLED START #
        """Return the firmwareVersion attribute."""
        return ""
        # PROTECTED REGION END #    //  Mccs.firmwareVersion_read

    def write_firmwareVersion(self, value):
        # PROTECTED REGION ID(Mccs.firmwareVersion_write) ENABLED START #
        """Set the firmwareVersion attribute."""
        pass
        # PROTECTED REGION END #    //  Mccs.firmwareVersion_write

    def read_voltage(self):
        # PROTECTED REGION ID(Mccs.voltage_read) ENABLED START #
        """Return the voltage attribute."""
        return 0.0
        # PROTECTED REGION END #    //  Mccs.voltage_read

    def write_voltage(self, value):
        # PROTECTED REGION ID(Mccs.voltage_write) ENABLED START #
        """Set the voltage attribute."""
        pass
        # PROTECTED REGION END #    //  Mccs.voltage_write

    def read_current(self):
        # PROTECTED REGION ID(Mccs.current_read) ENABLED START #
        """Return the current attribute."""
        return 0.0
        # PROTECTED REGION END #    //  Mccs.current_read

    def write_current(self, value):
        # PROTECTED REGION ID(Mccs.current_write) ENABLED START #
        """Set the current attribute."""
        pass
        # PROTECTED REGION END #    //  Mccs.current_write

    def read_isProgrammed(self):
        # PROTECTED REGION ID(Mccs.isProgrammed_read) ENABLED START #
        """Return the isProgrammed attribute."""
        return self._programmed
        # PROTECTED REGION END #    //  Mccs.isProgrammed_read

    def read_board_temperature(self):
        # PROTECTED REGION ID(Mccs.board_temperature_read) ENABLED START #
        """Return the board_temperature attribute."""
        return 0.0
        # PROTECTED REGION END #    //  Mccs.board_temperature_read

    def read_fpga1_temperature(self):
        # PROTECTED REGION ID(Mccs.fpga1_temperature_read) ENABLED START #
        """Return the fpga1_temperature attribute."""
        return 0.0
        # PROTECTED REGION END #    //  Mccs.fpga1_temperature_read

    def read_fpga2_temperature(self):
        # PROTECTED REGION ID(Mccs.fpga2_temperature_read) ENABLED START #
        """Return the fpga2_temperature attribute."""
        return 0.0
        # PROTECTED REGION END #    //  Mccs.fpga2_temperature_read

    def read_stationId(self):
        # PROTECTED REGION ID(Mccs.stationId_read) ENABLED START #
        """Return the stationId attribute."""
        return self._station_id
        # PROTECTED REGION END #    //  Mccs.stationId_read

    def write_stationId(self, value):
        # PROTECTED REGION ID(Mccs.stationId_write) ENABLED START #
        """Set the stationId attribute."""
        self._station_id = value
        # PROTECTED REGION END #    //  Mccs.stationId_write

    def read_fpga1_time(self):
        # PROTECTED REGION ID(Mccs.fpga1_time_read) ENABLED START #
        """Return the fpga1_time attribute."""
        return 0.0
        # PROTECTED REGION END #    //  Mccs.fpga1_time_read

    def write_fpga1_time(self, value):
        # PROTECTED REGION ID(Mccs.fpga1_time_write) ENABLED START #
        """Set the fpga1_time attribute."""
        pass
        # PROTECTED REGION END #    //  Mccs.fpga1_time_write

    def read_fpga2_time(self):
        # PROTECTED REGION ID(Mccs.fpga2_time_read) ENABLED START #
        """Return the fpga2_time attribute."""
        return 0.0
        # PROTECTED REGION END #    //  Mccs.fpga2_time_read

    def write_fpga2_time(self, value):
        # PROTECTED REGION ID(Mccs.fpga2_time_write) ENABLED START #
        """Set the fpga2_time attribute."""
        pass
        # PROTECTED REGION END #    //  Mccs.fpga2_time_write

    def read_antennaIds(self):
        # PROTECTED REGION ID(Mccs.antennaIds_read) ENABLED START #
        """Return the antennaIds attribute."""
        return (0,)
        # PROTECTED REGION END #    //  Mccs.antennaIds_read

    def write_antennaIds(self, value):
        # PROTECTED REGION ID(Mccs.antennaIds_write) ENABLED START #
        """Set the antennaIds attribute."""
        pass
        # PROTECTED REGION END #    //  Mccs.antennaIds_write

    def read_fortyGbDestinationIps(self):
        # PROTECTED REGION ID(Mccs.fortyGbDestinationIps_read) ENABLED START #
        """Return the fortyGbDestinationIps attribute."""
        return ("",)
        # PROTECTED REGION END #    //  Mccs.fortyGbDestinationIps_read

    def read_fortyGbDestinationMacs(self):
        # PROTECTED REGION ID(Mccs.fortyGbDestinationMacs_read) ENABLED START #
        """Return the fortyGbDestinationMacs attribute."""
        return ("",)
        # PROTECTED REGION END #    //  Mccs.fortyGbDestinationMacs_read

    def read_fortyGbDestinationPorts(self):
        # PROTECTED REGION ID(Mccs.fortyGbDestinationPorts_read) ENABLED START #
        """Return the fortyGbDestinationPorts attribute."""
        return (0,)
        # PROTECTED REGION END #    //  Mccs.fortyGbDestinationPorts_read

    def write_fortyGbDestinationPorts(self, value):
        # PROTECTED REGION ID(Mccs.fortyGbDestinationPorts_write) ENABLED START #
        """Set the fortyGbDestinationPorts attribute."""
        pass
        # PROTECTED REGION END #    //  Mccs.fortyGbDestinationPorts_write

    def read_adcPower(self):
        # PROTECTED REGION ID(Mccs.adcPower_read) ENABLED START #
        """Return the adcPower attribute."""
        return (0.0,)
        # PROTECTED REGION END #    //  Mccs.adcPower_read

    def write_adcPower(self, value):
        # PROTECTED REGION ID(Mccs.adcPower_write) ENABLED START #
        """Set the adcPower attribute."""
        pass
        # PROTECTED REGION END #    //  Mccs.adcPower_write

    # --------
    # Commands
    # --------

    @command()
    @DebugIt()
    def Initialise(self):
        # PROTECTED REGION ID(Mccs.Initialise) ENABLED START #
        """
        Performs all required initialisation (switches on on-board devices,
        locks PLL, performs synchronisation and other operations required
        to start configuring the signal processing functions of the firmware,
        such as channelisation and beamforming)

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  Mccs.Initialise

    @command(dtype_in="DevBoolean", doc_in="Initialise")
    @DebugIt()
    def Connect(self, argin):
        # PROTECTED REGION ID(Mccs.Connect) ENABLED START #
        """
        Creates connection to board. When True the initialise function is called
        immediately after connection (board must be programmed)

        :param argin: Initialise True = initialise immediately after connection
        :type argin: DevBoolean

        :return:None
        """
        if argin and self._programmed:
            self.Initialise()
        # PROTECTED REGION END #    //  Mccs.Connect

    @command()
    @DebugIt()
    def Disconnect(self):
        # PROTECTED REGION ID(Mccs.Disconnect) ENABLED START #
        """
        Disconnects from the board, the internal state needs to be reset

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  Mccs.Disconnect

    @command(dtype_in="DevString", doc_in="bitfile location")
    @DebugIt()
    def DownloadFirmware(self, argin):
        # PROTECTED REGION ID(Mccs.DownloadFirmware) ENABLED START #
        """
        Downloads the firmware contained in bitfile to all FPGAs on the board.
        This should also updatethe internal register mapping, such that registers
        become available for use. bitfile can either be the ?design? name
        returned from get_firmware_list(), or a path to a file

        :param argin: 'DevString'
        bitfile location

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  Mccs.DownloadFirmware

    @command(dtype_in="DevString", doc_in="bitfile location")
    @DebugIt()
    def ProgramCPLD(self, argin):
        # PROTECTED REGION ID(Mccs.ProgramCPLD) ENABLED START #
        """
        If the TPM has a CPLD (or other management chip which need firmware),
        this function program it with the provided bitfile.
        bitfile is the path to a file containing the required CPLD firmware

        :param argin: 'DevString'

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  Mccs.ProgramCPLD

    @command()
    @DebugIt()
    def WaitPPSEvent(self):
        # PROTECTED REGION ID(Mccs.WaitPPSEvent) ENABLED START #
        """
        Block until a PPS edge is detected, then return from function

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  Mccs.WaitPPSEvent

    @command(dtype_out="DevEnum")
    @DebugIt()
    def GetRegisterList(self):
        # PROTECTED REGION ID(Mccs.GetRegisterList) ENABLED START #
        """
        Return a list containing description of the exposed firmware (and CPLD) registers

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  Mccs.GetRegisterList

    @command(
        dtype_in="DevVarLongArray",
        doc_in="register_name, n, offset, devic",
        dtype_out="DevVarLongArray",
        doc_out="values",
    )
    @DebugIt()
    def ReadRegister(self, argin):
        # PROTECTED REGION ID(Mccs.ReadRegister) ENABLED START #
        """
        Return the value of the specified register. register_name is the string
        representation of the register, n is the number of 32-bit words to read,
        offset is the address offset within the register to read from and
        device is the FPGA to read from (from Device enumeration).
        Returns a list of values (unsigned 32-bit

        :return: a list of register values
        :rtype: DevVarUlongArray
        """
        pass
        # PROTECTED REGION END #    //  Mccs.ReadRegister

    @command(dtype_in="DevVarLongArray", doc_in="register_name, values, offset, device")
    @DebugIt()
    def WriteRegister(self, argin):
        # PROTECTED REGION ID(Mccs.WriteRegister) ENABLED START #
        """
        Write values to the specified register. register_name is the string
        representation of the register, values is a list containing the 32-bit
        values to write, offset is the address offset within the register
        to write to and device is the FPGA to write to (from Device enumeration).

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  Mccs.WriteRegister

    @command(
        dtype_in="DevVarLongArray",
        doc_in="address, n",
        dtype_out="DevVarULongArray",
        doc_out="values",
    )
    @DebugIt()
    def ReadAddress(self, argin):
        # PROTECTED REGION ID(Mccs.ReadAddress) ENABLED START #
        """
        Read n 32-bit values from address

        :return:'DevVarULongArray'
        """
        return [0]
        # PROTECTED REGION END #    //  Mccs.ReadAddress

    @command(dtype_in="DevVarULongArray", doc_in="address, values")
    @DebugIt()
    def WriteAddress(self, argin):
        # PROTECTED REGION ID(Mccs.WriteAddress) ENABLED START #
        """
        Write list of values at addres

        :param argin: 'DevVarULongArray'

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  Mccs.WriteAddress

    @command(
        dtype_in="DevVarULongArray",
        doc_in="core_id, src_mac, src_ip, dst_mac, dst_ip, src_port, dst_port",
    )
    @DebugIt()
    def Configure40GCore(self, argin):
        # PROTECTED REGION ID(Mccs.Configure40GCore) ENABLED START #
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

        :return:None
        """
        if len(argin) < 7:
            raise ValueError
        self._forty_g_core_list.append(
            {
                "core_id": argin[0],
                "src_mac": argin[1],
                "src_ip": argin[2],
                "dst_mac": argin[3],
                "dst_ip": argin[4],
                "src_port": argin[5],
                "dst_port": argin[6],
            }
        )

        # PROTECTED REGION END #    //  Mccs.Configure40GCore

    @command(
        dtype_in="DevLong",
        doc_in="coreId",
        dtype_out="DevVarULongArray",
        doc_out="configuration",
    )
    @DebugIt()
    def Get40GCoreConfiguration(self, argin):
        # PROTECTED REGION ID(Mccs.Get40GCoreConfiguration) ENABLED START #
        """
        Get 10g core configuration for core_id.
        This is required to chain up TPMs to form a station

        :return: the configuration as an array comprising:
                 src_mac, src_ip, src_port, dest_mac, dest_ip, dest_port
        :rtype: DevVarUlongArray
        """
        for item in self._forty_g_core_list:
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
        # PROTECTED REGION END #    //  Mccs.Get40GCoreConfiguration

    @command(dtype_in="DevVarLongArray", doc_in="mode, payload_length, src_ip, lmc_mac")
    @DebugIt()
    def SetLMCDownload(self, argin):
        # PROTECTED REGION ID(Mccs.SetLMCDownload) ENABLED START #
        """
        Specify whether control data will be transmitted over 1G or 40G networks
        mode: ?1G? or ?40G? payload_length:
        Size in bytes in UDP packet src_ip:
        Set 40g lane source IP (required only for 40G mode)
        lmc_mac: Set destination MAC for 40G lane (required only for 40G mode)

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  Mccs.SetLMCDownload

    @command(dtype_in="DevVarLongArray", doc_in="truncation array")
    @DebugIt()
    def SetChanneliserTruncation(self, argin):
        # PROTECTED REGION ID(Mccs.SetChanneliserTruncation) ENABLED START #
        """
        Set the coefficients to modify (flatten) the bandpass.
        truncation is a N x M array, where N is the number of input channels
        and M is the number of frequency channel

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  Mccs.SetChanneliserTruncation

    @command(dtype_in="DevVarLongArray", doc_in="region_array")
    @DebugIt()
    def SetBeamFormerRegions(self, argin):
        # PROTECTED REGION ID(Mccs.SetBeamFormerRegions) ENABLED START #
        """
        Set the frequency regions which are going to be beamformed into a single beam.
        region_arrayis defined as a 2D array, for a maximum of 16 regions.
        Each element in the array defines a region, with:
        start_channel: region starting channel
        nof_channels: size of the region, must be a multiple of 8
        beam_index: beam used for this region with range [0:8) Total number of channels must be <= 384

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  Mccs.SetBeamFormerRegions

    @command(
        dtype_in="DevVarLongArray", doc_in="n_of_tiles, first_tile=False, start=False"
    )
    @DebugIt()
    def ConfigureStationBeamformer(self, argin):
        # PROTECTED REGION ID(Mccs.ConfigureStationBeamformer) ENABLED START #
        """
        Initialise and start the station beamformer.
        nof_tiles is the number of tiles in the station,
        first_tile specifies whether the tile is the first one in the station,and start,
        when True, starts the beamformer

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  Mccs.ConfigureStationBeamformer

    @command(dtype_in="DevEncoded", doc_in="antenna, calibration_coefficients")
    @DebugIt()
    def LoadCalibrationCoefficients(self, argin):
        # PROTECTED REGION ID(Mccs.LoadCalibrationCoefficients) ENABLED START #
        """
        Loads calibration coefficients (but does not apply them, this is performed
        by switch_calibration_bank). antenna is the antenna to which the coefficients
        will be applied. calibration_coefficients is a bidimensional complex array of
        the form calibration_coefficients[channel, polarization], with each element
        representing a normalized coefficient, with (1.0, 0.0) being the normal,
        expected response for an ideal antenna. channel is the index specifying the channels
        at the beamformer output, i.e. considering only those channels actually processed
        and beam assignments. The polarization index ranges from 0 to 3.
            0: X polarization direct element
            1: X->Y polarization cross element
            2: Y->X polarization cross element
            3: Y polarization direct element
        The calibration coefficients may include any rotation matrix (e.g. the parallactic angle),
        but do not include the geometric delay

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  Mccs.LoadCalibrationCoefficients

    @command(dtype_in="DevVarDoubleArray", doc_in="angle_coefficients")
    @DebugIt()
    def LoadBeamAngle(self, argin):
        # PROTECTED REGION ID(Mccs.LoadBeamAngle) ENABLED START #
        """
        angle_coefs is an array of one element per beam, specifying a rotation angle, in radians,
        for the specified beam. The rotation is the same for all antennas.
        Default is 0 (no rotation). A positive pi/4 value transfers the X polarization
        to the Y polarization. The rotation is applied after regular calibration.

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  Mccs.LoadBeamAngle

    @command(dtype_in="DevVarDoubleArray", doc_in="tapering coefficients")
    @DebugIt()
    def LoadAntennaTapering(self, argin):
        # PROTECTED REGION ID(Mccs.LoadAntennaTapering) ENABLED START #
        """
        tapering_coeffs is a vector contains a value for each antenna the TPM processes. Default is 1.

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  Mccs.LoadAntennaTapering

    @command(dtype_in="DevDouble", doc_in="switch time")
    @DebugIt()
    def SwitchCalibrationBank(self, argin):
        # PROTECTED REGION ID(Mccs.SwitchCalibrationBank) ENABLED START #
        """
        Load the calibration coefficients at the specified time delay

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  Mccs.SwitchCalibrationBank

    @command(dtype_in="DevVarLongArray", doc_in="delay_array, beam_index")
    @DebugIt()
    def SetPointingDelay(self, argin):
        # PROTECTED REGION ID(Mccs.SetPointingDelay) ENABLED START #
        """
        Specifies the delay in seconds and the delay rate in seconds/seconds.
        The delay_array specifies the delay and delay rate for each antenna.
        beam_index specifies which beam is desired (range 0-7)

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  Mccs.SetPointingDelay

    @command(dtype_in="DevDouble", doc_in="load_time")
    @DebugIt()
    def LoadPointingDelay(self, argin):
        # PROTECTED REGION ID(Mccs.LoadPointingDelay) ENABLED START #
        """
        Loads the pointing delays at the specified time delay

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  Mccs.LoadPointingDelay

    @command(dtype_in="DevDouble", doc_in="start_time")
    @DebugIt()
    def StartBeamformer(self, argin):
        # PROTECTED REGION ID(Mccs.StartBeamformer) ENABLED START #
        """
        Start the beamformer at the specified time delay

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  Mccs.StartBeamformer

    @command()
    @DebugIt()
    def StopBeamformer(self):
        # PROTECTED REGION ID(Mccs.StopBeamformer) ENABLED START #
        """
        Stop the beamformer

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  Mccs.StopBeamformer

    @command(dtype_in="DevDouble", doc_in="Integration time")
    @DebugIt()
    def ConfigureIntegratedChannelData(self, argin):
        # PROTECTED REGION ID(Mccs.ConfigureIntegratedChannelData) ENABLED START #
        """
        Configure the transmission of integrated channel data with the provided integration time

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  Mccs.ConfigureIntegratedChannelData

    @command(dtype_in="DevDouble", doc_in="Integration time")
    @DebugIt()
    def ConfigureIntegratedBeamData(self, argin):
        # PROTECTED REGION ID(Mccs.ConfigureIntegratedBeamData) ENABLED START #
        """
        Configure the transmission of integrated beam data with the provided integration time

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  Mccs.ConfigureIntegratedBeamData

    @command()
    @DebugIt()
    def SendRawData(self):
        # PROTECTED REGION ID(Mccs.SendRawData) ENABLED START #
        """
        Transmit a snapshot containing raw antenna data

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  Mccs.SendRawData

    @command(dtype_in="DevLong", doc_in="number of samples")
    @DebugIt()
    def SendChannelisedData(self, argin):
        # PROTECTED REGION ID(Mccs.SendChannelisedData) ENABLED START #
        """
        Transmit a snapshot containing channelized data totalling number_of_samples spectra.

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  Mccs.SendChannelisedData

    @command(dtype_in="DevLong", doc_in="Channel")
    @DebugIt()
    def SendChannelisedDataContinuous(self, argin):
        # PROTECTED REGION ID(Mccs.SendChannelisedDataContinuous) ENABLED START #
        """
        Send data from channel channel continuously (until stopped)

        :param argin: Channel from which data will be sent
        :type argin: DevLong

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  Mccs.SendChannelisedDataContinuous

    @command()
    @DebugIt()
    def SendBeamData(self):
        # PROTECTED REGION ID(Mccs.SendBeamData) ENABLED START #
        """
        Transmit a snapshot containing beamformed data

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  Mccs.SendBeamData

    @command()
    @DebugIt()
    def StopDataTransmission(self):
        # PROTECTED REGION ID(Mccs.StopDataTransmission) ENABLED START #
        """
        Stop data transmission from board

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  Mccs.StopDataTransmission


# ----------
# Run server
# ----------


def main(args=None, **kwargs):
    """Main function of the MccsTile module."""
    # PROTECTED REGION ID(Mccs.main) ENABLED START #
    return run((MccsTile,), args=args, **kwargs)
    # PROTECTED REGION END #    //  Mccs.main


if __name__ == "__main__":
    main()
