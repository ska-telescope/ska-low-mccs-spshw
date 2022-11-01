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

  * *voltage*: Internal 5V power voltage, in volt.

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

  * *boardTemperature*: Temperature measured at mid-board, in degrees Celsius.

  * *fpga1Temperature*: Temperature of the FPGA1 die, in degrees Celsius.

  * *fpga2Temperature*: Temperature of the FPGA2 die, in degrees Celsius.

  * *antennaIds*: List of the ID's of the 16 antennas managed by the Tile.

  * *fortyGbDestinationIps*: *(RO)* List of the destination IPs of the first 2 cores 
    (beamformer and LMC) for the 2 FPGAs, as list of strings.

  * *fortyGbDestinationPorts*: List of the destination ports (int) of the first 2 cores 
    (beamformer and LMC) for the 2 FPGAs

  * *adcPower*: RMS level of the signals in the 32 inputs. Each consecutive pair of values 
    refer to the X and Y polarisations of one antenna. In ADC units. 

  * *currentTileBeamformerFrame*: Vale of the frame currently being processed by the Tile 
    beamformer, in units of 256 frames (276,48 us) 

  * *checkPendingDataRequests*: Bool, True if a SendData request is still being processed
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

  * *TestGeneratorActive*: Bool True if at least one of the TPM inputs is being sourced
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
re-initialise the FPGA, to reprogram the FPGAs with different personalities, to update 
the CPLD personality (quite dangerous) and to access individual hardware registers. 

  * *GetFirmwareAvailable*: lists the firmware currently loaded in the FPGAs and CPLD.

  * *DownloadFirmware*: Download a specific bitfile in the TPM FPGAs. 

  * *ProgramCPLD*: Update the CPLD firmware. USe with extreme care. Targeted for removal, 
    using a specific program to perform CPLD firmware update. 

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

  * *ReadRegister*: Reads the value of one or more registers. Each register is a 32 bit integer. 
    If is possible to specify an offset from the given addreess, in words, and a number of 
    consecutive registers to read. Parameters given as a json string: 

    * RegisterName: (mandatory string) Name of the register to read

    * Offset - (int) Offset in words of the first register read

    * NbRead - (int) number of words (registers) to read

    Returns a list of 32 bit integers. 

  * *WriteRegister*: Write into one or more registers. Each register is a 32 bit integer.
    If is possible to specify an offset from the given addreess, in words, and a number of
    consecutive registers to read. Parameters given as a json string:

    * RegisterName: (mandatory string) Name of the register to read

    * Offset - (int) Offset in words of the first register read

    * Values - (int or list(int) ) Values to write. Values are written into consecutive 
      registers.


Ethernet interface configuration
---------------------------------

  * *Configure40GCore*: Configure one of the available cores. Parameters as a json string
    with the following keywords. All keywords are optinal, except CoreID and ArpTableEntry.

    * CoreID - (int) core id, 0 for FPGA1, 1 for FPGA2

    * ArpTableEntry - (int) ARP table entry ID. 8 entries available, only 0 and 1 
      currently used, respectively for beamformer chain (0) and LMC (1) 

    * SrcMac - (int) mac address

    * SrcIP - (string) IP dot notation for source IP

    * SrcPort - (int) source port

    * DstIP - (string) IP dot notation for destination IP

    * DstPort - (int) destination port

  * *Get40GCoreConfiguration*: retrieves the configuration for one specific port, or for all
    programmed ports. Parameter: json string with keywords CoreID and ArpTableEntry. 
    If CoreID = -1 all ports are reported. Returns a list of json dictionaries with 
    the same keywords of *Configure40GCore*:

    * CoreID - (int) core id, 0 for FPGA1, 1 for FPGA2

    * ArpTableEntry - (int) ARP table entry ID. 8 entries available, only 0 and 1
      currently used, respectively for beamformer chain (0) and LMC (1)

    * SrcMac - (int) mac address

    * SrcIP - (string) IP dot notation for source IP

    * SrcPort - (int) source port

    * DstIP - (string) IP dot notation for destination IP

    * DstPort - (int) destination port


  * *SetLmcDownload*: Specify whether control data will be transmitted over 1G or 
    40G networks, and the relavant link parameters. Parameter: a json dictionary with 
    optional keywords:

    * Mode - (string) ``1g`` or ``10g`` (Mandatory) (use ``10g`` for 40G link)

    * PayloadLength - (int) SPEAD payload length for channel data. Default 

    * DstIP - (string) Destination IP. Is mandatory for 40G link, not required
      for 1G link. 

    * SrcPort - (int) Source port for sample data streams

    * DstPort - (int) Destination port for sample data streams

  * *SetLmcIntegratedDownload*: Configure link and size of integrated data.
    Parameter: a json dictionary with optional keywords:

    * Mode - (string) ``1g`` or ``10g`` (Mandatory)

    * ChannelPayloadLength - (int) SPEAD payload length for integrated channel data

    * BeamPayloadLength - (int) SPEAD payload length for integrated beam data

    * DstIP - (string) Destination IP. Same IP and port is used for LMC and integrated
      LMC, so values should be specified only in one of *SetLmcDownload* and
      *SetLmcIntegratedDownload*. Last specified overrides IP and port for both. 

    * SrcPort - (int) Source port for integrated data streams

    * DstPort - (int) Destination port for integrated data streams

  * *GetArpTable*: returns a dictionary containing, for each 40G core, a list of the 
    ARP table entries which are populated. An example:

    ``{ "core_id0": [0, 1], "core_id1": [0], }``

LMC  generator configuration and control
-----------------------------------------

Methods to send spigots of samples at various processing stages. Spigots are sent 
as bursts of SPEAD packets on the interface, IP address and port specified by 
*SetLmcDownload* commands. methods should be unified in a single *SendData* command, 
considering that only one transmission stream can be active at any time. 

  * *SendRawData*: Send packets of raw ADC samples. If Sync = False samples are separately 
    collected and sent for each antenna, in round robin.

    Argument: json string with keywords:

    * Sync - (bool) synchronised flag. If ``True`` the command behaves like 
      *SendRawDataSynchronised*. Default ``False``.

    * Timestamp - (int) When to start (frame number). To be changed in UTC time string.
      Default "now" plus ``Seconds`` value

    * Seconds - (float) : delay to wait after specified time

  * *SendRawDataSynchronised*: Send packets of raw ADC samples, synchronised. Samples
    are captured together from each antenna, but packet length is limited to 1024 samples

    Argument: json string with keywords:

    * Timestamp - (int) When to start (frame number). To be changed in UTC time string.
      Default "now" plus ``Seconds`` value

    * Seconds - (float) : delay to wait after specified time


  * *SendChannelisedData*: Send data samples from specified channels.

    Argument: json string with keywords:

    * NSamples - (int) number of samples to send in each channel. Default = 1024

    * FirstChannel - (int) first channel to send. Default = 0.

    * LastChannel - (int) last channel to send. Default = 511

    * Timestamp - (int) Start time (frame number). To be changed in UTC time string.
      Default "now" plus ``Seconds`` value

    * Seconds - (float) : delay to wait after specified time

  * *SendChannelisedDataContinuous*: Send a continuous stream of samples for an individual 
    frequency channel. Data sending must be stopped by the *StopDataTransmission* 
    command.

    Argument: json string with keywords:

    * ChannelId: index of channel to send
    
    * NSamples: number of samples to send, defaults to 1024
    
    * Timestamp - (int) Start time (frame number). To be changed in UTC time string.
      Default "now" plus ``Seconds`` value

    * Seconds - (float) : delay to wait after specified time

  * *SendChannelisedDataNarrowband*: Send a continuous stream of samples for an 
    individual frequency channel, with further reduced bandwidth and data rate. 
    A digital downconverter is used to select the desired portion of the channelised 
    data. The channel used and the DDC local oscillator value are selected by specifying
    the desired sky frequency. The bandwidth is 1/128 of a coarse channel band (about 
    7 kHz), with a sampling rate of 138.24 microseconds. 

    Argument: json string with keywords:

    * Frequency - (int) Sky frequency in Hz at band centre

    * RoundBits - (int) Number of bits discarded in rounding

    * NSamples -  (int) number of samples to send

    * Timestamp - (int) Start time (frame number). To be changed in UTC time string.
      Default "now" plus ``Seconds`` value

    * Seconds - (float) : delay to wait after specified time


  * *SendBeamData*: Send tile beamfomred samples

    Argument: json string with keywords:

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

    * IntegrationTime - (float) Integration time in seconds, default = 0.5

    * FirstChannel - (int) First channel in spectrum, default = 0

    * LastChannel - (int) Last channel in spectrum, default = 511

  * *ConfigureIntegratedBeamData*: Configure the total power spectrometer for
    tile beamformed data. Spectrometer provides total power only for the
    spectral regions (logical bands) specified by the *SetBeamFormerRegions*
    command, in the order defined there.

    Argument: json string with keywords:

    * IntegrationTime - (float) Integration time in seconds, default = 0.5

    * FirstChannel - (int) First channel in spectrum, default = 0

    * LastChannel - (int) Last channel in spectrum, default = 191. Channel 
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

    * StartTime - (int) start acquisition time, in Unix seconds. Default "now"
      plus *Delay* seconds.

    * Delay - (int) delay start, in seconds. Default = 2

  * *ConfigureTestGenerator*: Uses an internal test generator to generate 
    an artificial signal composed of white noise and up to 2 monochromatic tones. 
    The signal substitutes the samples from the ADCs for specific inputs. 
    It is described in a separate document page. 

    Argument: json string with keywords:

    * ToneFrequency: first tone frequency, in Hz. The frequency
      is rounded to the resolution of the generator. If this
      is not specified, the tone generator is disabled.

    * ToneAmplitude: peak tone amplitude, normalized to 31.875 ADC
      units. The amplitude is rounded to 1/8 ADC unit. Default
      is 1.0. A value of -1.0 keeps the previously set value.

    * Tone2Frequency: frequency for the second tone. Same
      as ToneFrequency.

    * Tone2Amplitude: peak tone amplitude for the second tone.
      Same as ToneAmplitude.

    * NoiseAmplitude: RMS amplitude of the pseudorandom Gaussian
      white noise, normalized to 26.03 ADC units.

    * PulseFrequency: frequency of the periodic pulse. A code
      in the range 0 to 7, corresponding to (16, 12, 8, 6, 4, 3, 2)
      times the ADC frame frequency.

    * PulseAmplitude: peak amplitude of the periodic pulse, normalized
      to 127 ADC units. Default is 1.0. A value of -1.0 keeps the
      previously set value.

    * SetTime: time at which the generator is set, for synchronization
      among different TPMs.

    * AdcChannels: list of adc channels which will be substituted with
      the generated signal. It is a 32 integer, with each bit representing
      an input channel.

    * SetTime: time at which the generator is set. Integer, in timestamp frames. 
      It is used to synchronise the generator across different tiles.
      Default = 0, for immediate load. 

  * *SetTimeDelays*: Introduces a fixed delay, as an integer number of samples, 
    in each signal. This is used to compensate for cable mismatches, and roughly 
    align the antenna signals for zenith. 

    Argument: array of 32 float values, in samples (1.25 ns), range +/-123.
    Positive delay adds delay to the signal stream

  * *SetChanneliserTruncation*: Channeliser output is re-quantised to 12 bits, 
    to allow signal processing using small integer arithmetics. As the input 
    signal has a steep spectrum, it is necessary to equalise the frequency channels, 
    in order not to loose significance. Rescaling is performed by dropping 
    0-7 least sigificant bits, and clipping the resulting value to 12 bits. 
    A truncation of 0 means just clipping the channelizer output (max. sensitivity),
    a truncation of 7 rescales the channelizer output by 1/128 (min. sensitivity). 
    A value of 4 is adequate for a flat input spectrum. 
    Input is a bidimensional array, specified as a flattened string preceded by
    the array dimensions: 

    * argin[0] - is N, the number of input channels. 

    * argin[1] - is M, the number of frequency channel. First 

    * argin[2:] - is the data, with fast index for frequency channels and slow index 
      for input channels. 

    If N=M=1 then the single truncation value is applied to all inputs and all signals.
    If N=1, M=512 the same rescaling curve is applied to all input channels. 

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

    Argument: numeric list comprises:

    * antenna - (int) is the antenna to which the coefficients will be applied.

    * calibration_coefficients - [array] a flattended bidimensional complex array 
      of (8 * *number_of_channels*) real values.

  * *SwitchCalibrationBank*: Activates the specified calibration values. Calibration 
    values are stored in a dual bank table. One bank is active at any moment, 
    while the other can be modified using *LoadCalibrationCoefficients* command. 
    When all values have been loaded for all antennas and tiles, the banks can be 
    switched at a specific time, simultaneously for all tiles. 
    Argument: load time (int, frame timestamp). Default is immediate (asynchronous 
    between tiles)

  * *SetPointingDelay*: Pointing for each beam is set by specifying delays for each
    antenna. Delay applies to both polarizations. A delay rate can be specified, 
    in which case the delay starts at the initial value, at the time specified in 
    *LoadPointingDelay*, and varies linearly with time. Values are specified in a 
    temporary storage, ad activated at a specific time. 

    Argument: array of (2 * *antennas_per_tile* + 1) values.

    argin[0]: beam index

    argin[1...]: (delay, delay rate) values, in seconds and (seconds/second)

  * *LoadPointingDelay*: Load the pointing delays at the specified time.
    Argument: load time (int, frame timestamp). Default is immediate (asynchronous
    between tiles)

  * *StartBeamformer*: Start the station beamformer. Begin sending SPEAD beamformed 
    packets to CBF. A duration can be specified 

    Argument: json string with keywords:

    * StartTime - (int) start time (int, frame timestamp). Default is immediate

    * Duration - (int) if > 0 is duration in itimestamp frames (276.48 us). (Duration/8) 
      SPEAD frames are sent to CSP for each beamformed channel. Default: -1, run forever

  * *StopBeamformer*: Stop the station beamformer. Immediate. 

  * *SetCspRounding*: Beamformed samples are re-quantised to 8 bits to be sent to CSP. 
    As for the channeliser truncation, this is performed by discarding LS bits, rounding
    and clipping the resulting value to 8 bits. Only a single value, for all channels, 
    is available in the current firmware.

    Argument: Number of discarded bits: 0 (no rounding, maximum sensitivity) to 7 (rescaling
    samples by 1/128).

