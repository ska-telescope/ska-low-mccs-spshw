##################################
 Tango Tile attributes and methods
##################################

********************************
 Tango Tile Device Construction
********************************

The TPM (or simulator) is created during the Tile's Init command, and initialised as 
part of the *On()* command. Initialization is performed using parameters specified
in the Tango device properties, specified in the Tango devices database, loaded from
the chart file *data/tile.yaml*. 
In the production version, the initialisation will be performed using a configuration 
database. 

Important parameters for initialisation are: 

* *TpmVersion*: Either ``tpm_v1_2`` or ``tpm_v1_6`` Specifies the hardware version of the TPM

* *TpmIp*: The IP address for the TPM

* *SubrackFQDN*: The Tango device name for the subrack controlling the tile

* *SubrackBay*: The bay number (1-8) in which the tile is hosted, in the subrack

* *TileId*: The ID of the tile. 

This command is executed automatically during construction of the Tile Tango device.
The decision whether to use the TPM simulator or a real hardware driver is made
with the *simulation_mode* flag. This is currently hardcoded to *SimulationMode.TRUE*
in ``tile_device.py``. This means that either the TPM simulator or the real hardware
driver is available as soon as the Tile Tango device is ready for use.
You can swicth between simulation and real TPM driver by writing to the Tile device's
*simulation_mode* attribute. This will reset the Tile's TPM object.

*****************************
Tango Tile device attributes
*****************************

Attributes specific to the Tile device are listed here. Most attributes are read only, to 
monitor the associated quantities or parameters. Writable attributes are explicitly marked 
as *RW*.

  * *stationId*: *(RW)* ID of the station device to which the tile belongs. 

  * *firmwareName*: *(RW)* filename of the FPGA firmware bitfile. 

  * *firmwareVersion*: Timestamp and version number of the loaded firmware, both for the 
    FPGA and the CPLD. 

  * *isProgrammed*: Boolean, True if the FPGAs are programmed.

  * *tileProgrammingState*: a string describing the programing state of the TPM. 
    It may assume one of the values: 

    * ``Unknown``: the state cannot be determined

    * ``Off``: the tile is powered off

    * ``Unconnected``: the connection with the tile is not established

    * ``NotProgrammed``: the TPM is powered on but the FPGAs have not been programmed

    * ``Programmed``: The TPM is on, FPGAs have been programmed but the firmware has 
      not been initialised. 

    * ``Initialised``: The TPM firmware modules have been initialised. 
      The 40G interfaces are up and running, ARP protocol has set the interface 
      MAC addresses, the internal PPS is synchronsed with the 
      distributed PPS signal, the internal coarse clock is syncrhonous with UTC

    * ``Synchronised``: Tje ADCs have been synchronised. The internal timestamp 
      counter is synchronised among TPMs, and can be used to infer sample time

  * *antennaIds*: List of the ID's of the 16 antennas managed by the Tile.

  * *fortyGbDestinationIps*: List of the destination IPs of the first 2 cores 
    (beamformer and LMC) for the 2 FPGAs, as list of strings.

  * *fortyGbDestinationPorts*: List of the destination ports (int) of the first 2 cores 
    (beamformer and LMC) for the 2 FPGAs

  * *adcPower*: RMS level of the signals in the 32 inputs. Each consecutive pair of values 
    refer to the X and Y polarisations of one antenna. In ADC units. 

  * *currentTileBeamformerFrame*: Vale of the frame currently being processed by the Tile 
    beamformer, in units of 256 frames (276,48 us) 

  * *pendingDataRequests*: Bool, True if a SendData request is still being processed
    by the LMC data transmitter. 

  * *isBeamformerRunning*: Bool, True if the **station** beamformer is running. The tile 
    beamformer is always running after the *StartAcquisition* command.

  * *ppsDelay*: delay between PPS and 10 MHz clock in 200 MHz cycles

  * *fpgaTime*: Time of the TPM second counter. String in UTC format, with seconds 
    component always integer. Time is synchronised to
    the telescope time during Tile initialisation. 

  * *fpgaFrameTime*: Time corresponding to the current frame.  String in UTC format, 
    in steps of 276 us. The time is valid only after  the *StartAcquisition* command.

  * *fpgaReferenceTime*: Time at which the TPM has been synnchronised. String in UTC
    format. As synchronisation occurs at a second boundary, the seconds part is always
    integer. Before the *StartAcquisition* command 

  * *fpgasUnixTime*: Time in Unix seconds for the two FPGAs. Array of 2 integers. Time 
    should be consistent with the integer part of the time returned by the Python 
    ``time.time()`` method. String in UTC format

  * *testGeneratorActive*: Bool True if at least one of the TPM inputs is being sourced
    by the internal test signal generator. 

***************************
Tango Tile device commands
***************************
Commands are grouped by category. Some less used commands, targeted for removal, are 
not included. 

Low level firmware access
--------------------------
These commands are used for accessing hardware functions which are not normally used 
and should be available only in maintenance mode. These commands allow to 
re-initialise the FPGA, to reprogram the FPGAs with different personalities, and
to access individual hardware registers. 

  * *GetFirmwareAvailable*: lists the firmware currently loaded in the FPGAs and CPLD.

  * *DownloadFirmware*: Download a specific bitfile in the TPM FPGAs. 

  * *Initialise*: Complete FPGA initialisation. This is automatically performed when the 
    Tile enters ``PowerState.ON``

    * Check if the TPM is programmed If not, program it using the crurrently specified 
      bitfile, or the default one for the TPM version

    * Execute the base initialization sequence for the hardware. 

        * Loads all firmware plugins, initialising each one 

        * synchronises the internal clock (PPS counter) with the system PPS and initializes
          the Unix time counter in each FPGA to Unix time

        * sets the IP address for the 40G interfaces to a default value, computed from 
          the 1G IP address. The interface connectivity is determined if these can talk 
          to each other.

    * initialise the tile and station beamformer to a default state: each tile working 
      as a separate beamformer, with a 6.25 MHz bandwidth starting at 100 MHz. 

    * sets the station ID. If the station ID is different from 0, initialisation has been
      successfully completed.

    The initialisation required to set up a complete station involves further steps, 
    performed by the Station device. 

  * *GetRegisterList*: Returns a list of all the TPM register names (about 3 thousand names). 

  * *ReadRegister*: Reads the value of one named register. Each register is a 32 bit integer. 
    Register may return a list of values if so defined in the xml register description. 
    Parameter is the full qualified hyerarchic register name (string)

    Returns a list of ione or more unsigned 32 bit values.

  * *WriteRegister*: Write into one or more registers. Each register is a 32 bit integer.
    If is possible to specify an offset from the given addreess, in words, and a number of
    consecutive registers to read. Parameters given as a json string:

    * register_name: (mandatory string) Name of the register to read

    * values - (int or list(int) ) Values to write. Values are written into consecutive 
      register addresses.

  * *ReadAddress*: Reads one or more values at a specific address. Parameter is a list 
    of one or two integers. First value is the absolute address in the TPM AXI4 memory
    mapped address space. If 2 values are specified the second is the number of words read.

    Returns a list of unsigned 32 bit values.

  * *WriteAddress*: Writes one or more values to hardware address. Parameter: list of
    integer values, first the address, followed by the values to be written. If more than
    one value is specified, these are written in consecutive word (4 byte) addresses. 


Ethernet interface configuration
---------------------------------

  * *Configure40GCore*: Configure one of the available cores. Parameters as a json string
    with the following keywords. All keywords are optinal, except CoreID and ArpTableEntry.

    * core_id - (int) core id, 0 for FPGA1, 1 for FPGA2

    * arp_table_entry - (int) ARP table entry ID. 8 entries available, only 0 and 1 
      currently used, respectively for beamformer chain (0) and LMC (1) 

    * source_mac - (int) mac address

    * source_ip - (string) IP dot notation for source IP

    * source_port - (int) source port

    * destination_ip - (string) IP dot notation for destination IP

    * destination_port - (int) destination port

  * *Get40GCoreConfiguration*: retrieves the configuration for one specific port, or for all
    programmed ports. Parameter: json string with keywords core_id and arp_table_entry.
    If core_id = -1 all ports are reported. Returns a list of json dictionaries with 
    the same keywords of *Configure40GCore*:

    * core_id - (int) core id, 0 for FPGA1, 1 for FPGA2

    * arp_table_entry - (int) ARP table entry ID. 8 entries available, only 0 and 1
      currently used, respectively for beamformer chain (0) and LMC (1)

    * source_mac - (int) mac address

    * source_ip - (string) IP dot notation for source IP

    * source_port - (int) source port

    * destination_ip - (string) IP dot notation for destination IP

    * destination_port - (int) destination port


  * *SetLmcDownload*: Specify whether control data will be transmitted over 1G or 
    40G networks, and the relavant link parameters. Parameter: a json dictionary with 
    optional keywords:

    * mode - (string) ``1g`` or ``10g`` (Mandatory) (use ``10g`` for 40G link)

    * payload_length - (int) SPEAD payload length for channel data. Default 

    * destination_ip - (string) Destination IP. Is mandatory for 40G link, not required
      for 1G link. 

    * source_port - (int) Source port for sample data streams

    * destination_port - (int) Destination port for sample data streams

  * *SetLmcIntegratedDownload*: Configure link and size of integrated data.
    Parameter: a json dictionary with optional keywords:

    * mode - (string) ``1g`` or ``10g`` (Mandatory)

    * channel_payload_length - (int) SPEAD payload length for integrated channel data

    * beam_payload_length - (int) SPEAD payload length for integrated beam data

    * destination_ip - (string) Destination IP. Same IP and port is used for LMC and integrated
      LMC, so values should be specified only in one of *SetLmcDownload* and
      *SetLmcIntegratedDownload*. Last specified overrides IP and port for both. 

    * source_port - (int) Source port for integrated data streams

    * destination_port - (int) Destination port for integrated data streams

  * *GetArpTable*: returns a dictionary containing, for each 40G core, a list of the 
    ARP table entries which are populated. An example:

    ``{ "core_id0": [0, 1], "core_id1": [0], }``

LMC  generator configuration and control
-----------------------------------------

Methods to send spigots of samples at various processing stages. Spigots are sent 
as bursts of SPEAD packets on the interface, IP address and port specified by 
*SetLmcDownload* commands. methods should be unified in a single *SendData* command, 
considering that only one transmission stream can be active at any time. 

  * *SendDataSamples*: Send packets of data samples. Type of samples and associated parameters 
    are specified in a json string. 

    Argument: json string. The following keywords are common to all data types: 

    * data_type - type of snapshot data (mandatory): "raw", "channel",
                    "channel_continuous", "narrowband", "beam"

    * timestamp - Time (UTC string) to start sending data. Default immediately
        
    * seconds - (float) Delay if timestamp is not specified. Default 0.2 seconds

    Depending on the data type additional keywords can (or must) be specified:

    raw: send ADC raw samples (8 bits) for all antennas. 

    * sync: bool: send synchronised samples for all antennas, vs. round robin
                larger snapshot from each antenna

    channel: send channelised samples for all antennas, and for the specified channel range.

    * n_samples: Number of samples per channel, default 1024

    * first_channel - (int) first channel to send, default 0

    * last_channel - (int) last channel to send, default 511

    channel_continuous: Send a continuous stream of channelised samples for one 
    specific channel, all antennas. Used for calibration spigots. 

    * channel_id - (int) channel_id (Mandatory)

    * n_samples -  (int) number of samples to send per packet, default 128

    narrowband: Send a continuous stream of channelised samples for one
    specific channel, further filtered and decimated around the specified frequency. 
    For all antennas. Used for tracking a monochromatic tone (e.g. transmitter on UAV drone).

    * frequency - (int) Sky frequency for band centre, in Hz (Mandatory)

    * round_bits - (int)  Specify whow many bits to round

    * n_samples -  (int) number of spectra to send

    beam: Send tile beamformed samples, for all beamformed channels. 

  * *StopDataTransmission*: Stop transmission of continuous samples 

  The following methods refer to the integrated power data. Two separate integrators
  (total power spectrometers) are present, one for channelised data, and one for tile 
  beamformed data. Channelised data integrator computes the power spectrum of one
  of the 32 input signals, in turn, in a round robin fashion. 
  Once configured, each integrator sends complete spectra at the end of the specified
  integration period. 
  Both integrators may be active at any given moment.

  * *ConfigureIntegratedChannelData*: Configure the total power spectrometer for 
    channelised data. A spectrum of the selected coarse channels is provided for each
    input signals.

    Argument: json string with keywords:

    * integration_time - (float) Integration time in seconds, default = 0.5

    * first_channel - (int) First channel in spectrum, default = 0

    * last_channel - (int) Last channel in spectrum, default = 511

  * *ConfigureIntegratedBeamData*: Configure the total power spectrometer for
    tile beamformed data. Spectrometer provides total power only for the
    spectral regions (logical bands) specified by the *SetBeamFormerRegions*
    command, in the order defined there.

    Argument: json string with keywords:

    * integration_time - (float) Integration time in seconds, default = 0.5

    * first_channel - (int) First channel in spectrum, default = 0

    * last_channel - (int) Last channel in spectrum, default = 191. Channel 
      refers to odd and even channels processed in each FPGA, the total number
      of channels is twice this value. 

  * *StopIntegratedData*: Immediately stop sending both integrated channel and 
    beam data.

Data processing chain configuration
-----------------------------------
TPM data processing is highly configurable. 

  * *StartAcquisition*: Starts the ADCs and the whole SDP processing chain,
    synchronizing it at the specified second boundary. The same starting time
    must be specified for all tiles in the telescope. In the current firmware it is
    not possible to stop the acquisition, re-synchronization is possible only 
    by deprogramming the FPGAs and re-initializing them. 

    Argument: json string with keywords:

    * start_time - (int) start acquisition time, in Unix seconds. Default "now"
      plus *delay* seconds.

    * delay - (int) delay start, in seconds. Default = 2

  * *aduLevels*: (attribute) Attenuator setting for ADU inputs. One (int) value 
    per input, range 0 to 31

  * *ConfigureTestGenerator*: Uses an internal test generator to generate 
    an artificial signal composed of white noise and up to 2 monochromatic tones. 
    The signal substitutes the samples from the ADCs for specific inputs. 
    It is described in a separate document page. 

    Argument: json string with keywords:

    * tone_frequency: first tone frequency, in Hz. The frequency
      is rounded to the resolution of the generator. If this
      is not specified, the tone generator is disabled.

    * tone_amplitude: peak tone amplitude, normalized to 31.875 ADC
      units. The amplitude is rounded to 1/8 ADC unit. Default
      is 1.0. A value of -1.0 keeps the previously set value.

    * tone_2_frequency: frequency for the second tone. Same
      as ToneFrequency.

    * tone_2_amplitude: peak tone amplitude for the second tone.
      Same as ToneAmplitude.

    * noise_amplitude: RMS amplitude of the pseudorandom Gaussian
      white noise, normalized to 26.03 ADC units.

    * pulse_frequency: frequency of the periodic pulse. A code
      in the range 0 to 7, corresponding to (16, 12, 8, 6, 4, 3, 2)
      times the ADC frame frequency.

    * pulse_amplitude: peak amplitude of the periodic pulse, normalized
      to 127 ADC units. Default is 1.0. A value of -1.0 keeps the
      previously set value.

    * set_time: time at which the generator is set, for synchronization
      among different TPMs. In UTC ISO format. Default: immediate load.

    * adc_channels: list of adc channels which will be substituted with
      the generated signal. It is a 32 integer, with each bit representing
      an input channel. Default: all if at least q source is specified, 
      none otherwises.

  * *staticTimeDelays* (attribute): Introduces a fixed delay, as an integer number of samples, 
    in each signal. This is used to compensate for cable mismatches, and roughly 
    align the antenna signals for zenith. 

    Argument: array of 32 float values, in nanoseconds. Rounded to nearest integer
    sample (1.25 ns), range +/-154 ns. (123 samples).
    Positive delay adds delay to the signal stream

  * *channeliserRounding* (attribute): Channeliser output is re-quantised to 12 bits, 
    to allow signal processing using small integer arithmetics. As the input 
    signal has a steep spectrum, it is necessary to equalise the frequency channels, 
    in order not to loose significance. Rescaling is performed by dropping 
    0-7 least sigificant bits, and clipping the resulting value to 12 bits. 
    A truncation of 0 means just clipping the channelizer output (max. sensitivity),
    a truncation of 7 rescales the channelizer output by 1/128 (min. sensitivity). 
    A value of 4 is adequate for a flat input spectrum. 
    Input is a linear array of 512 elements, one per physical channel. The same value is
    applied to the corresponding channel for all inputs. If only 
    one value is specified, it is extended to 512 values (same value for all channels).

  * *SetBeamFormerRegions*: The beamformer selects portions of the observed spectrum 
    for processing. Each region must start on a even channel and is composed of 
    contiguous frequency channels. The number of channels must be a multiple of 8. 
    Each region is associated to a beam (pointing direction), and has 5 associated
    metadata, which does not affect SDP processing but is included in the SPEAD
    header for subsequent processing in CSP and SDP. Thus each region is defined by 
    a set of 8 numbers (index is 0-based to comply with Python indexing convention): 

    0. start_channel - (int) region starting channel, must be even in range 0 to 510

    1. num_channels - (int) size of the region, must be a multiple of 8

    2. beam_index - (int) beam used for this region with range 0 to 47 (0 to 7 in 
       current firmware).

    3. subarray_id - (int) Subarray ID

    4. subarray_logical_channel - (int) logical channel # in the subarray for the first
       channel in the region

    5. subarray_beam_id - (int) ID of the subarray beam

    6. substation_id - (int) Substation ID. 

    7. aperture_id:  ID of the aperture (TBD, e.g. station*100+substation)

    Up to 48 regions can be defined. The command parameter is a linear list of
    (8* *number of regions*) integers, specifying each region in sequence.
    Internally to the tile, beamformer logical channels are assigned in the order they
    are defined here. This order is used for calibration coefficients, CSP rounding
    and in the total power integrator for *IntegratedBeamData* spectra.

  * *beamformerTable*: (attribute) Shows the current status of the beamformer table. This
    is a table with 7 entries for each group of 8 channels. It is returned as a linear
    array of 336 integer values. Each group of 7 consecutive values represent: 

    0. start_channel - (int) starting channel for the group

    1. beam_index - (int) beam used for this region with range 0 to 47 (0 to 7 in 
       current firmware).

    2. subarray_id - (int) Subarray ID

    3. subarray_logical_channel - (int) logical channel number in the subarray for the first
       channel in the group

    4. subarray_beam_id - (int) ID of the subarray beam

    5. substation_id - (int) Substation ID. 

    6. aperture_id:  ID of the aperture (TBD, e.g. station*100+substation)


  * *LoadCalibrationCoefficients*: Load the calibration coefficients table, but does not 
    apply them. The values are stored in a temporary table, which is activated
    atomically in the Tile hardware at the time specified by switch_calibration_bank.
    The calibration coefficients may include any rotation matrix (e.g. the parallactic 
    angle, or flipping X and Y polarization), and the residual zenith delay not 
    corrected by *SetTimeDelays*, but do not include the geometric delay for pointing.
    Calibration coefficients are specified one antenna at a time, as an array of
    Jones matrices for each of the processed logical channels. Logical channels are
    the channels specified in *SetBeamFormerRegions*, in the order in which these are
    defined there. 

    Each list element is a flattened complex matrix (8 real values) in the order: 

    0. X polarization direct element

    1. X->Y polarization cross element

    2. Y->X polarization cross element

    3. Y polarization direct element

    with each element representing a normalized coefficient, with (1.0, 0.0) being the
    normal, expected response for an ideal antenna.

    Argument: is a list with (8 * *number_of_channels* + 1) real values:

    * argument[0]: antenna - (int) is the antenna to which the coefficients will be applied.

    * argument[1:N] calibration_coefficients - a flattended bidimensional complex array 
      of (8 * *number_of_channels*) real values.

  * *ApplyCalibration*: Activates the specified calibration values. Calibration 
    values are stored in a dual bank table. One bank is active at any moment, 
    while the other can be modified using *LoadCalibrationCoefficients* command. 
    When all values have been loaded for all antennas and tiles, the banks can be 
    switched at a specific time, simultaneously for all tiles. 

    Argument: load time (string, ISO formatted UTC). Null string is immediate (asynchronous 
    between tiles)

  * *LoadPointingDelays*: Pointing for each beam is set by specifying delays for each
    antenna. Delay applies to both polarizations. A delay rate can be specified, 
    in which case the delay starts at the initial value, at the time specified in 
    *LoadPointingDelay*, and varies linearly with time. Values are specified in a 
    temporary storage, ad activated at a specific time. 

    Argument: array of (2 * *antennas_per_tile* + 1) values.

    argin[0]: beam index

    argin[1...]: (delay, delay rate) values, in seconds and (seconds/second)

  * *ApplyPointingDelays*: Load the pointing delays at the specified time.
    Argument: load time (int, frame timestamp). Default is immediate (asynchronous
    between tiles)

  * *StartBeamformer*: Start the station beamformer. Begin sending SPEAD beamformed 
    packets to CBF. A duration can be specified 

    Argument: json string with keywords:

    * start_time - (int) start time (string, ISO formatted UTC). Default is immediate

    * duration - (int) if > 0 is duration in itimestamp frames (276.48 us). (Duration/8) 
      SPEAD frames are sent to CSP for each beamformed channel. Default: -1, run forever

  * *StopBeamformer*: Stop the station beamformer. Immediate. 

  * *cspRounding*: (attribute) Beamformed samples are re-quantised to 8 bits to be sent to CSP. 
    As for the channeliser truncation, this is performed by discarding LS bits, rounding
    and clipping the resulting value to 8 bits. Array of integers, with one value per
    beamformed channel. Only a single value, for all channels, 
    is available in the current firmware (uses first element in array).

    Argument: Number of discarded bits: 0 (no rounding, maximum sensitivity) to 7 (rescaling
    samples by 1/128).

Health monitoring
=================


The following attributes are used to monitor board health status. 

  * *boardTemperature*: Temperature measured at mid-board, in degrees Celsius.

  * *fpga1Temperature*: Temperature of the FPGA1 die, in degrees Celsius.

  * *fpga2Temperature*: Temperature of the FPGA2 die, in degrees Celsius.

  * *clockPresent*: Report if 10 MHz clock signal is present at the TPM input.

  * *pllLocked*: Report if ADC clock PLL is in locked state.

  * *ppsPresent*: Report if PPS signal is present at the TPM input.

  * *sysrefPresent*: Report if SYSREF signal is present at the FPGA.

  * *voltage*: Internal 5V power voltage, in volt.

