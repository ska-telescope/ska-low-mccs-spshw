========================
MccsDaq Configure schema
========================

**********
Properties
**********

* **nof_antennas** (integer): Number of antennas per tile. Default: 16.

* **nof_channels** (integer): Number of channels. Default: 512.

* **nof_beams** (integer): Number of beams. Default: 1.

* **nof_polarisations** (integer): Number of polarisations. Default: 2.

* **nof_tiles** (integer): Number of tiles in the station. Default: 1.

* **nof_raw_samples** (integer): Number of raw antennas samples per buffer (requires different firmware to change). Default: 32768.

* **raw_rms_threshold** (integer): Only save raw data if RMS exceeds provided threshold; -1 disables thresholding. Default: -1.

* **nof_channel_samples** (integer): Number of channelised spectra per buffer. Default: 1024.

* **nof_correlator_samples** (integer): Number of channel samples for correlation per buffer. Default: 1835008.

* **nof_correlator_channels** (integer): Number of channels to channelise into before correlation; used only in correlator mode. Default: 1.

* **continuous_period** (integer): Seconds between successive dumps of continuous channel data; 0 means dump everything. Default: 0.

* **nof_beam_samples** (integer): Number of beam samples per buffer (requires different firmware to change). Default: 42.

* **nof_beam_channels** (integer): Number of channels in beam data. Default: 384.

* **nof_station_samples** (integer): Number of station beam samples per buffer. Default: 262144.

* **integrated_channel_bitwidth** (integer): Bit width of integrated channel data. Default: 16.

* **continuous_channel_bitwidth** (integer): Bit width of continuous channel data. Default: 16.

* **append_integrated** (boolean): Append integrated data in the same file. Default: true.

* **persist_all_buffers** (boolean): Persist all buffers. When false, we ignore the first 3 received buffers for continuous channel data. Default: false.

* **sampling_time** (number): Sampling time in seconds. Time per sample. Default: 1.1325.

* **sampling_rate** (number): FPGA sampling rate. Default: 925925.925926.

* **oversampling_factor** (number): Oversampling factor [default: 32/27]. Default: 1.1851851851851851.

* **receiver_ports**: UDP port(s) to listen on; can be a single string or integer, or an array of them. Default: "4660".

  **One of**
    * : A single UDP port as a string or integer.

      **Any of**
        * string: Must match pattern ``/^[0-9]+$/``.

        * integer: Minimum: 0. Maximum: 65535.

    * array: A list of UDP ports as strings or integers.

      * **Items**

        **Any of**
          * string: Must match pattern ``/^[0-9]+$/``.

          * integer: Minimum: 0. Maximum: 65535.

* **receiver_interface** (string): Receiver interface. Default: "eth0".

* **receiver_ip** (string): IP to bind to in case of multiple virtual interfaces. Default: "".

* **receiver_frame_size** (integer): Receiver frame size. Default: 8500.

* **receiver_frames_per_block** (integer): Receiver frames per block. Default: 32.

* **receiver_nof_blocks** (integer): Receiver number of blocks. Default: 256.

* **receiver_nof_threads** (integer): Receiver number of threads. Default: 1.

* **description** (string): Observation description patched into observation_metadata. Default: "".

* **station_config** (['object', 'null']): Station configuration file to extract additional metadata. Default: null.

* **station_id** (integer): Station ID.

* **max_filesize** (['number', 'null']): Maximum file size in GB; set 0 to save each data set to a separate HDF5 file. Default: null.

* **acquisition_duration** (integer): Duration of data acquisition in seconds. Default: -1.

* **acquisition_start_time** (integer): Specify acquisition start time; only for continuous channelised data. Default: -1.

* **station_beam_source** (string): Station beam observed source. Default: "".

* **station_beam_start_channel** (integer): Start channel ID for raw station beam. Default: 0.

* **station_beam_dada** (boolean): Save raw station beam data as DADA files. Default: false.

* **station_beam_individual_channels** (boolean): Store raw station beam channels individually. Default: false.

* **logging** (boolean): Enable or disable logging. Default: true.

* **write_to_disk** (boolean): Write files to disk. Default: true.

* **observation_metadata** (object): Metadata related to the observation; accepts arbitrary key-value pairs. Can contain additional properties. Default: {}.

* **directory** (string): Directory where data is saved. Default: ".".

