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

# PyTango imports
from tango import DebugIt
from tango.server import attribute, command
from tango import DevState

# Additional import

from ska.mccs import MccsGroupDevice


class MccsTile(MccsGroupDevice):
    """
    The Tile Device represents the TANGO interface to a Tile (TPM) unit

    **Properties:**

    - Device Property
    """

    # -----------------
    # Device Properties
    # -----------------

    # ---------------
    # General methods
    # ---------------

    def init_device(self):
        """Initialises the attributes and properties of the Mccs."""
        super().init_device()

        self.set_state(DevState.INIT)
        self._programmed = False
        self._tile_id = -1
        self._subarray_id = -1
        self._station_id = -1
        self._logical_tpm_id = -1
        self._ip_address = ""
        self._lmc_ip = ""
        self._lmc_port = 0
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
        self.set_state(DevState.ON)
        print("MccsTile init_device complete")

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

    @attribute(dtype="DevDouble")
    def voltage(self):
        """Return the voltage attribute."""
        return self._voltage

    @attribute(dtype="DevDouble")
    def current(self):
        """Return the current attribute."""
        return self._current

    @attribute(
        dtype="DevBoolean",
        doc="Return True if the all FPGAs are programmed, False otherwise",
    )
    def isProgrammed(self):
        """Return the isProgrammed attribute."""
        return self._programmed

    @attribute(dtype="DevDouble", doc="The board temperature")  # force warp
    def board_temperature(self):
        """Return the board_temperature attribute."""
        return self._board_temperature

    @attribute(dtype="DevDouble")
    def fpga1_temperature(self):
        """Return the fpga1_temperature attribute."""
        return self._fpga1_temperature

    @attribute(dtype="DevDouble")
    def fpga2_temperature(self):
        """Return the fpga2_temperature attribute."""
        return self._fpga2_temperature

    @attribute(dtype="DevLong", doc="The identifier of the associated station.")
    def stationId(self):
        """Return the stationId attribute."""
        return self._station_id

    @stationId.write
    def stationId(self, value):
        """Set the stationId attribute."""
        self._station_id = value

    @attribute(dtype="DevDouble")
    def fpga1_time(self):
        """Return the fpga1_time attribute."""
        return self._fpga1_time

    @fpga1_time.write
    def fpga1_time(self, value):
        """Set the fpga1_time attribute."""
        self._fpga1_time = value

    @attribute(dtype="DevDouble")
    def fpga2_time(self):
        """Return the fpga2_time attribute."""
        return self._fpga2_time

    @fpga2_time.write
    def fpga2_time(self, value):
        """Set the fpga2_time attribute."""
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
    )
    def adcPower(self):
        """Return the adcPower attribute."""
        return self._adc_power

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
        pass

    @command(dtype_in="DevBoolean", doc_in="Initialise")
    @DebugIt()
    def Connect(self, argin):

        """
        Creates connection to board. When True the initialise function is
        called immediately after connection (board must be programmed)

        :param argin: Initialise True = initialise immediately after connection
        :type argin: DevBoolean

        :return: None
        """
        if argin and self._programmed:
            self.Initialise()

    @command()
    @DebugIt()
    def Disconnect(self):

        """
        Disconnects from the board, the internal state needs to be reset

        :return: None
        """
        pass

    @command(dtype_in="DevString", doc_in="bitfile location")
    @DebugIt()
    def DownloadFirmware(self, argin):
        """
        Downloads the firmware contained in bitfile to all FPGAs on the board.
        This should also updatethe internal register mapping, such that
        registers become available for use. bitfile can either be the ?design?
        name returned from get_firmware_list(), or a path to a file

        :param argin: bitfile location
        :type argin: 'DevString'

        :return: None
        """
        pass

    @command(dtype_in="DevString", doc_in="bitfile location")
    @DebugIt()
    def ProgramCPLD(self, argin):

        """
        If the TPM has a CPLD (or other management chip which need firmware),
        this function program it with the provided bitfile.
        bitfile is the path to a file containing the required CPLD firmware

        :param argin: 'DevString'

        :return: None
        """
        pass

    @command()
    @DebugIt()
    def WaitPPSEvent(self):

        """
        Block until a PPS edge is detected, then return from function

        :return: None
        """
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

    @command(dtype_in="DevVarLongArray", doc_in="mode, payload_length, src_ip, lmc_mac")
    @DebugIt()
    def SetLMCDownload(self, argin):

        """
        Specify whether control data will be transmitted over 1G or 40G
        networks
        mode: ?1G? or ?40G? payload_length:
        Size in bytes in UDP packet src_ip:
        Set 40g lane source IP (required only for 40G mode)
        lmc_mac: Set destination MAC for 40G lane (required only for 40G mode)

        :return: None
        """
        pass

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
        region_arrayis defined as a 2D array, for a maximum of 16 regions.
        Each element in the array defines a region, with:
        start_channel: region starting channel
        nof_channels: size of the region, must be a multiple of 8
        beam_index: beam used for this region with range [0:8) Total number of
        channels must be <= 384

        :return: None
        """
        pass

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
        pass

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

        :return: None
        """
        pass

    @command(dtype_in="DevVarDoubleArray", doc_in="tapering coefficients")
    @DebugIt()
    def LoadAntennaTapering(self, argin):

        """
        tapering_coeffs is a vector contains a value for each antenna the TPM
        processes. Default is 1.

        :return: None
        """
        pass

    @command(dtype_in="DevDouble", doc_in="switch time")
    @DebugIt()
    def SwitchCalibrationBank(self, argin):

        """
        Load the calibration coefficients at the specified time delay

        :return: None
        """
        pass

    @command(dtype_in="DevVarLongArray", doc_in="delay_array, beam_index")
    @DebugIt()
    def SetPointingDelay(self, argin):

        """
        Specifies the delay in seconds and the delay rate in seconds/seconds.
        The delay_array specifies the delay and delay rate for each antenna.
        beam_index specifies which beam is desired (range 0-7)

        :return: None
        """
        pass

    @command(dtype_in="DevDouble", doc_in="load_time")
    @DebugIt()
    def LoadPointingDelay(self, argin):

        """
        Loads the pointing delays at the specified time delay

        :return: None
        """
        pass

    @command(dtype_in="DevDouble", doc_in="start_time")
    @DebugIt()
    def StartBeamformer(self, argin):

        """
        Start the beamformer at the specified time delay

        :return: None
        """
        pass

    @command()
    @DebugIt()
    def StopBeamformer(self):

        """
        Stop the beamformer

        :return: None
        """
        pass

    @command(dtype_in="DevDouble", doc_in="Integration time")
    @DebugIt()
    def ConfigureIntegratedChannelData(self, argin):

        """
        Configure the transmission of integrated channel data with the
        provided integration time

        :return: None
        """
        pass

    @command(dtype_in="DevDouble", doc_in="Integration time")
    @DebugIt()
    def ConfigureIntegratedBeamData(self, argin):

        """
        Configure the transmission of integrated beam data with the provided
        integration time

        :return: None
        """
        pass

    @command()
    @DebugIt()
    def SendRawData(self):

        """
        Transmit a snapshot containing raw antenna data

        :return: None
        """
        pass

    @command(dtype_in="DevLong", doc_in="number of samples")
    @DebugIt()
    def SendChannelisedData(self, argin):

        """
        Transmit a snapshot containing channelized data totalling
        number_of_samples spectra.

        :return: None
        """
        pass

    @command(dtype_in="DevLong", doc_in="Channel")
    @DebugIt()
    def SendChannelisedDataContinuous(self, argin):

        """
        Send data from channel channel continuously (until stopped)

        :param argin: Channel from which data will be sent
        :type argin: DevLong

        :return: None
        """
        pass

    @command()
    @DebugIt()
    def SendBeamData(self):

        """
        Transmit a snapshot containing beamformed data

        :return: None
        """
        pass

    @command()
    @DebugIt()
    def StopDataTransmission(self):

        """
        Stop data transmission from board

        :return: None
        """
        pass


# ----------
# Run server
# ----------
def main(args=None, **kwargs):
    """Main function of the MccsTile module."""

    return MccsTile.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
