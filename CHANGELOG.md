# Version History

## Unreleased

* [THORN-261] Alarms added to adc_pll_status, fpga0_station_beamformer_error_count, fpga1_station_beamformer_error_count, fpga0_station_beamformer_flagged_count, fpga1_station_beamformer_flagged_count, fpga0_crc_error_count, fpga1_crc_error_count, fpga0_bip_error_count, fpga1_bip_error_count, fpga0_decode_error_count, fpga1_decode_error_count, fpga0_linkup_loss_count, fpga1_linkup_loss_count, fpga0_data_router_status, fpga1_data_router_status, fpga0_ddr_reset_counter, fpga1_ddr_reset_counter, f2f_soft_errors, f2f_hard_errors, fpga0_resync_count, fpga1_resync_count, fpga0_lane_error_count, fpga1_lane_error_count, fpga0_clock_managers_count, fpga1_clock_managers_count, fpga0_clock_managers_status, fpga1_clock_managers_status, fpga0_clocks, fpga1_clocks, adc_sysref_counter, adc_sysref_timing_requirements, fpga0_qpll_status, fpga0_qpll_counter, fpga1_qpll_status, fpga1_qpll_counter, f2f_pll_status, f2f_pll_counter, timing_pll_status, timing_pll_count, timing_pll_40g_status, timing_pll_40g_count, station_beamformer_status, tile_beamformer_status, arp, udp_status, ddr_initialisation, lane_status, link_status
* [THORN-261] attribute adc_pll_status converted from string to 2d array. first list representing is the lock of pll is up the second list representing if no loss of pll lock has been observed per adc channel.
* [THORN-261] station_beamformer_error_count converted to a fpga0_station_beamformer_error_count and fpga1_station_beamformer_error_count containing a int representing errors detected.
* [THORN-261] station_beamformer_flagged_count converted to a fpga0_station_beamformer_flagged_count and fpga1_station_beamformer_flagged_count containing a int representing flag count.
* [THORN-261] crc_error_count converted to a fpga0_crc_error_count and fpga1_crc_error_count containing a int representing errors detected.
* [THORN-261] bip_error_count converted to a fpga0_bip_error_count and fpga1_bip_error_count containing a list of lane status
* [THORN-261] decode_error_count converted to a fpga0_decode_error_count and fpga1_decode_error_count containing a int
* [THORN-261] linkup_loss_count converted to a fpga0_linkup_loss_count and fpga1_linkup_loss_count containing a int
* [THORN-261] data_router_status converted to a fpga0_data_router_status and fpga1_data_router_status containing a int
* [THORN-261] ddr_reset_counter converted to a fpga0_ddr_reset_counter and fpga1_ddr_reset_counter containing a int
* [THORN-261] resync_count converted to a fpga0_resync_count and fpga1_resync_count containing a int
* [THORN-261] lane_error_count converted to a fpga0_lane_error_count and fpga1_lane_error_count containing a 2d array of count per lane per core.
* [THORN-261] attribute clocks converted to fpga1_clocks and fpga1_clocks each containing the status of respective clocks
* [THORN-261] Add abs_change and archive_abs_change configuration to
attributes.
* [THORN-261] Split attribute timing_pll_40g_status into timing_pll_40g_status and timing_pll_40g_count.
* [THORN-261] Split attribute timing_pll_status into timing_pll_status and
timing_pll_count
* [THORN-261] Split attribute f2f_pll_status into f2f_pll_status and
f2f_pll_counter
* [THORN-261] Split attribute qll_status into fpga1_qpll_counter, fpga1_qpll_status, fpga0_qpll_status, fpga0_qpll_counter
* [THORN-261] attribute clock_managers converted fpga0_clock_managers_status and fpga0_clock_managers_count,
fpga1_clock_managers_status and fpga1_clock_managers_count countaining a list of the clocks. "C2C_MMCM", "JESD_MMCM", "DSP_MMCM"

## 9.1.0

* [THORN-249] Add attribute pfb_version to MccsTile.
* [THORN-249] Bump firmware version 6.6.1 -> 6.7.1
* [SKB-1035] Added tile programming state to the health rollup

## 9.0.0

* [JANUS-38] Adopting changes made in ska-low-sps-tpm-api 1.0.0 - Simplified tile 40G ethernet configuration

## 8.0.2

* [THORN-289] Add ResetCspIngest command to SpsStation. Improve message in SetCspIngest. Add cspIngestConfig attribute to SpsStation.
* [THORN-298] Fix issue where last attribute was being marked as invalid
* [SKB-872] Fix the response code for a number of commands that we incorrectly reporting ResultCode.OK when failing
* [SKB-999] fix the mapping of fitted preADUs to ADC channels when verifying preADU attenuation hardware readback.
* [THORN-239] MccsSubrack now has internal voltage attributes and actively polls health status attributes
* [LOW-1745] Bump ska-tango-devices to 0.10.0, with support for suppressing the deployment of check-dependencies initContainers that wait for databaseDS, when deploying to a persistent platform.
* [THORN-307] Small bug fix for station_component_manager set_lmc_download and set_lmc_integrated_download

## 8.0.1

* [SKB-872] MccsTile now only polls a subset of health values on each poll.
* [SKB-872] MccsTile attributes which do a hardware read are now only allowed if the TPM is programmed.

## 8.0.0

* [THORN-172] The old two pod DAQ version has been removed.

## 7.4.2

* [SKB-1033] Bumping TPM firmware to 6.6.1 to resolve bug with subarray ID and substation ID
  Bug was introduced in TPM firmware 6.4.0
* [SPRTS-487] Move boardTemperature attribute higher up the list (workaround no longer necessary due to cppTango fix).

## 7.4.1

* [THORN-248] Update to new ska-low-mccs-common MccsCommandProxy interface.

## 7.4.0

* [LOW-1593] Eliminate dependency on bitnami images / charts.
* [THORN-244] Update yaml configuration for RAL.
* [THORN-207] Add HW readback for channeliser truncation.
* [SKB-999] Correct PreAduPresent property to account for both preadu.renamed to array property PreAduFitted (default [True, True])
* [SKB-955] Correct transient transition to ON when MccsTile is turning OFF.

## 7.3.0

* [THORN-218] Added 51 monitoring points as tango device attributes in tile. (ADC temperatures, FE currents and voltages)
* [THORN-241] Add cleanup code to delete_device. This fixes an issue where multiple calls to init() lead to multiple polling threads.
* [SKB-928] Remove configuration attributes from polling. Configuration is now 'read_on_connect' or 'read_on_change'
* [SKB-928] SpsStation staticTimeDelay now raised RuntimeError when information for TPM mapping not present
* [SKB-928] Expose exceptions to tango API for MccsTile methods staticTimeDelays and ConfigureStationBeamformer.
* [SKB-928] stationId no longer has an initial value (this was software only and was not necessarilty True. It is now read from TPM as soon as possible.) (NOTE: property StationID will be used as the value to initialise the TPM with and writing to stationId will take precedence over the property but will not be persisted.)
* [SKB-928] logicalTileId no longer has an initial value (this was software only and was not necessarilty True. It is now read from TPM as soon as possible.) (NOTE: property TileId will be used as the value to initialise the TPM with and writing to LogicalTileId will take precedence over the property but will not be persisted.)

## 7.2.0

* [THORN-195] Add HardwareVerificationError.
* [THORN-214] Added HardwareVersion property to MccsTile. If not defined ADC0 -> ADC15 temperature attributes are not evaluated in health
* [THORN-214] Added BiosVersion property to MccsTile. If not defined pll_40g attribute is not evaluated in health
* [THORN-214] Added PreAduPresent property to MccsTile (default == True). When false we expect currents FE0_mVA and FE1_mVA to be 0 with some tolerance.

## 7.1.0

* [THORN-238] Add SpsStation.BandpassIntegrationTime device property for setting bandpass integration time in Initialise().
* [THORN-238] Update chart.yaml to allow for separate DAQ chart version.
* [JANUS-215] Support for TPM API to 0.6.0, manage whole TPM external label
* [THORN-206] Clarify when Tile is sending data
* [THORN-183] changed health threshold for tpm and subrack using updated values: <https://jira.skatelescope.org/browse/SPRTS-274>

## 7.0.1

* [THORN-214] Correct HealthRules to account for new monitoring points.
* [THORN-214] Correct runningBeams KeyError

## 7.0.0

* [THORN-175] Added beamfomer control on individual beams.
* [THORN-175] MccsTile.StartBeamformer and StopBeamformer accepts `channel_groups` parameter
* [THORN-175] Added command MccsTile.BeamformerRunningForChannels and attribute RunningBeams
* [THORN-175] Added commands SpsStation.BeamformerRunningForChannels and StopBeamformerForChannels
* [THORN-214] Correct SpsStation healthstate update to evaluate only when the power of spstation changes.
* [THORN-214] Reset initial pps_delay after initialisation.
* [THORN-214] Improve hardware test visibility and reliability.

## 6.5.2

* [THORN-220] Add cleanup for proxies and component managers.
* [THORN-215] Add validation to Daq Configure command.

## 6.5.1

* [THORN-214] make PduTrl optional in componentmanager.

## 6.5.0

* [THORN-133] SpsStation to StartAcquisition during Initialise

## 6.4.0

* [THORN-11] New self check test added 'TestAntennaBuffer'
* [THORN-11] Attribute ddr_write_size added to the MccsTile device
* [THORN-11] ska-low-mccs-daq-interface dependency 1.0.0-> 1.0.1
* [THORN-11] Update helm ska-low-mccs-daq dependency 2.0.0 -> 2.0.4-dev.c6b8c425d
* [THORN-214] Update RAL platform spec.
* [THORN-68] Added stationBeamFlagEnabled attribute

## 6.3.0

* [THORN-11] ska-low-sps-tpm-api dependency 0.2.2 -> 0.3.0
* [THORN-11] Add ability to configure a ramp in ConfigurePatternGenerator.
* [THORN-214] Update RAL pipeline k8s runner tango host.
* [THORN-214] Update RAL pipeline to run on schedule.
* [THORN-71] Update to include command schemas in docs

## 6.2.2

* [THORN-182] Update TPM current thresholds to 10.5/10A

## 6.2.1

* [SKB-804] HotFix: Revert changes to force reprogramming.

## 6.2.0

* [SKB-804] ska-low-sps-tpm-api dependency 0.1.2 -> 0.2.2 (allow re-configuring of LMC routing.)
* [SKB-804] Only force reprogramming if programmed.
* [SKB-804] Improve logging for INVALID attributes.
* [SKB-804] Add missing attributes to attr_map.
* [SKB-804] Speedup subrack tests.
* [SPRTS-364] fix tile hardware lock TimeoutError message
* [THORN-93] Link PDU device to subrack via TANGO commands
* [SPRTS-441] added a VerifyEvents boolean property to MccsTile,
  which defaults to True and determines whether pushed archive and change events
  are verified by Tango against the rel_change and abs_change attribute properties.

## 6.1.3

* [THORN-117] Correct claiming of lock in ping method.
* [SPRTS-436] add 2Gi memory limit to spshw Pods.

## 6.1.2

* [THORN-165] Add missing hardware_lock to methods.
* [SKB-816] Remove subrack tpm_power_state attribute cache upon RequestError.

## 6.1.1

* [SPRTS-436] Update to sps-tpm-api (0.1.0 -> 0.1.2) to include fix for memory leak.

## 6.1.0

* [SPRTS-433] The timeout for acquiring access to the HW in MccsTile is now a device property, configurable from deployment.

## 6.0.0

* [THORN-97] SpsStation.Initialise() reverted to not taking arguments. The version of initialise which
  does is SpsStation.ReInitialise(json_arg)
* [SKB-816] Changed _component_state_changed() callback to keep track of previous tpm states when subrack looses conection to device

## 5.0.2

* [THORN-152] Remove daqs from log message.

## 5.0.1

* [THORN-152] Handle missing DAQ TRL.

## 5.0.0

* [SKB-872] MccsTile.StartBeamformer/StopBeamformer commands are now long running commands,
  they are submitted to the polling loop to be picked up on the next poll, but the command returns
  before the beamformer has actually started/stopped.

## 4.0.0

* [THORN-97] Update SpsStation.Initialise() to route general LMC data to DAQ and
  bandpasses to the bandpass DAQ. This means we now have a 'BandpassDAQ'
  property to populate on SpsStation.
* [THORN-97] SpsStation also has the 'StartBandpassesInInitialise',
  this is optional, defaults to True. If set to false we won't send integrated data during
  SpsStation.Initialise()
* [THORN-97] SpsStation.Initialise() now accepts a json argument, at present it only has one
  optional argument 'start_bandpasses' which is a boolean, if not given the value in the device
  property is used.
  
## 3.1.1

* [THORN-110] Updated daq refs after repo reorganisation, updated imports.
* [THORN-149] Migrate from AAVSSystem and PyFabil to ska-low-sps-tpm-api

## 3.1.0

* [SKB-861] Add optional argument start_time to AcquireDataForCalibration
* [SKB-861] Update AcquireDataForCalibration default start_time to 2 seconds in future.

## 3.0.3

* [THORN-144] Re-release of 3.0.2 with correct image.

## 3.0.2

* [THORN-144] DAQ was going to ON before doing its automatic starting/stopping of receivers, this meant code waiting on DAQ turning to ON would think the DAQ is ready too soon. Now DAQ reports ON after it has finished automatically starting/stopping consumers.

## 3.0.1

* pyfabil 2.1.0 -> 2.1.1 (<https://gitlab.com/ska-telescope/pyfabil/-/releases>)
* aavs-system 2.1.3 -> 2.1.6 (<https://gitlab.com/ska-telescope/aavs-system/-/releases>)
* TPM firmware version 6.2.0 -> 6.2.1

## 3.0.0

* Update ska-tango-base 1.3.1 -> 1.3.2 (<https://gitlab.com/ska-telescope/ska-tango-base/-/releases>)
* [THORN-99] Prune logging.
* [THORN-108] Update STFC RAL ref to use persistent DB.
* [THORN-121] Add deploy stage to pipeline.
* [THORN-134] Added ska-low-mccs-common ref.
* [SKB-843] Add a NumberOfTiles property to MccsDaqReceiver
* [LOW-1272] Update to latest ska-tango-devices 0.2.0 -> 0.2.1 (<https://gitlab.com/ska-telescope/ska-tango-devices/-/releases>)
* [THORN-91] Update PDU charts to match new configuration
* [LOW-1304] Update for upstream bugfixes

## 2.0.0

* [THORN-126] Allow AcquireDataForCalibration to work when daq in Engineering AdminMode.
* [THORN-117] Reduce cpu time per poll spend on redundant evaluation of TpmStatus.
* [THORN-117] Add EvaluateTileProgrammingState command to MccsTile.
* [LOW-1216] Breaking changes to helm chart values schema.
  The `ska-low-mccs-spshw` helm chart now uses `ska-tango-devices`
  to configure and deploy its Tango devices.
  For details, see the "Direct deployment of helm charts" section of the
  "Deploying" page in the documentation.

## 1.5.0

* [THORN-103] SpsStation.AcquireDataForCalibration now launches a frequency sweep, as such the interface has changed. It now expected a json-ified dictionary containing the keys first_channel and last_channel.
* [THORN-96] Add optional property StaticTimeDelays to MccsTile.
* [THORN-123] Add FAULT when subrack reports TPM ON and TPM is not connectable.
* [THORN-86] SpsStation now uses the CommunicationManager from ska-low-mccs-common to manage it's communication status, this should
flush out issues with rapid changes of adminmode.

## 1.4.0

* [THORN-21] Added antenna buffer control methods.

## 1.3.0

* [THORN-122] HotFix issue 'devstate not accounting ppsPresent attribute'
* [THORN-122] HotFix issue 'unable with deploying MccsTile when TPM OFF state.'
* [SKB-520] Mark attributes as INVALID.
* [THORN-85] Update devices to serialise their events through the EventSerialiser. This should have no operational
changes, but an attribute EventHistory is now available on all devices to debug which events this device received,
where they came from, the order they came in, and what callbacks were executed with those events. It is a json-ified list of lists.

## 1.2.0

* [THORN-54] Update SpsStation to use new health model.

## 1.1.0

* [SKB-765] Update SpsStation.AcquireDataForCalibration to not configure DAQ, this is now done in SpsStation.ConfigureStationForCalibration
* [SKB-765] AcquireDataForCalibration now starts DAQ, sends data, waits for receipt of data then stops daq.

## 1.0.0

* [THORN-17] 1.0.0 release - all MCCS repos

## 0.25.0

* [SKB-761] Hardcode nof_antenna to number expected from library build.
* [THORN-24] Update devices to use MccsBaseDevice for mode inheritance.
* [THORN-27] Add `BandpassDaq` property to DaqReceiver. Where this is `True` these Daqs will automatically attempt to keep bandpass monitoring running.

## 0.24.0

* [SKB-766] Reject multiple calls to DAQ.Start() in a row.
* [SKB-746] MccsTile.Off() now works in DevState ALARM.

## 0.23.1

* [SKB-702] SpsStation takes multiple attempts for all calibration coefficients to be applied
* [THORN-5] Add Tile beamformer test to self-check.
* [THORN-12] Add methods/attribute to measure data rate through DAQ network interface.
* [THORN-13] Add station beam data rate test to self-check.

## 0.23.0

* [MCCS-2256] Removed cabinetbanks.

## 0.22.0

* [MCCS-2330] Seperate alarms attribute into constituents.

## 0.21.3

* [SKB-705] Allow graceful handling of DaqReceiver restart. Restart running tasks on DaqHandler
* [THORN-2] Extend Tile Control and Health Monitoring following Firmware Release 6.2.0
* [MCCS-2330] Update pytango to 10.0.0
* [THORN-10] Update self-check to mark test data

## 0.21.2

* [THORN-3] Bump TPM FPGA Firmware to version 6.2.0 in SPSHW
* [THORN-59] Fix race condition (intermittent failure in unit test)
* [THORN-48] Fix mock tile device builder by including attributes
* [THORN-64] Fix rficount change events

## 0.21.1

* [THORN-57] Fix python package build bug that prevented publication of python wheel for 0.21.0

## 0.21.0

* [SKB-687] Do not automatically initialise TPM when initialised or synchronised.
* [THORN-48] Update deploy submodule.
* [THORN-50] Add PreaduAttenuation device property to MccsTile
* [SKB-683] SpsStation initialise fails fpgatimes check
* [SKB-703] Add a thread that establishes communication with the DAQ client
* [THORN-49] Fix shared register map bug.
* [THORN-39] Update ska-low-mccs-common to 0.15.6

## 0.20.1

* [THORN-37] Pull in downstream update for proxies to use DevSource.DEV
* [THORN-40] Update RAL platform spec for new TPMs

## 0.20.0

* [THORN-47] Add CspRounding property to SpsStation

## 0.19.0

* [LOW-1131] Expose SPS Station as a LoadBalancer
* [THORN-1] Multi-class device server endpoint
* [MCCS-2026] Add RFI counters
* [MCCS-2299] Add functional test for reading attributes on hardware.
* [MCCS-2319] ddr_interface points failing health when running a scan
* [MCCS-2328] Add enable/disable ADCs, add delays to test generator

## 0.18.1

* [SKB-610] Add StationID to Daq config and propagate to HDF5 metadata.

## 0.18.0

* [MCCS-2273] Add DAQ tests so SpsStation.SelfCheck()
* [SKB-609] Revert changes made in SKB-520.
* [MCCS-2265] Fix abortCommand() when turning station on.
* [MCCS-2309] Add property "device_property" for setting arbitrary properties.
* [MCCS-2182] Deploy PDU device with MCCS
* [MCCS-2300] Add support for starting/stopping/configuring the pattern generator in MccsTile.
* [MCCS-2278] Change health and state rollup/aggregation for SpsStation to reduce frequency of it entering `DevState.UNKNOWN`.

## 0.17.7

* [SKB-596] MccsTile producing too many logs

## 0.17.6

* [SKB-507] Added `ppsDelaySpread` attribute to `SpsStation` to track `ppsDelay` drifts. This has been incorporated into the HealthModel and will result in HealthState.DEGRADED when the `ppsDelaySpread` is observed to be >4 samples and FAILED when >10. Added `ppsDelayDrift` attribute to `MccsTile` to track difference between current `ppsDelay` and its value at initialisation. Results in Tile HealthState.DEGRADED when >4 samples and FAILED when >10.

## 0.17.5

* [MCCS-2295] Mark attributes as invalid when MccsTile is OFF
* [SKB-520] Correct Tile attribute quality reporting bug.
* [MCCS-2258] Add test_ral_low manual stage to pipeline.
* [SKB-447] Subrack health board current fix

## 0.17.4

* [SKB-519] Prevent subrack from sticking in UNKNOWN after a failed poll.

## 0.17.3

* [SKB-433] Allow aborting of SendDataSamples()
* [MCCS-2259] Add channeliser rounding property

## 0.17.2

* [MCCS-1979] Correct tile health monitoring for single 40g QSFP
* [SKB-426] Remove ADA voltages from health rollup
* [SKB-526] Fix channeliser rounding ordering
* [SKB-431] Converted Daq.Stop to a LongRunningCommand to avoid CORBA timeouts.
* [SKB-433] Update SpsStation to use ThreadPools

## 0.17.1

* [SKB-524] Update ska-low-mccs-daq dependency to allow specifying resources for DAQ receiver Pods.
* [LOW-995] Speed up SpsStation initialisation by reducing delay between TPM operations.
* [LOW-991] Fix bug in platform spec parsing introduced by new spec schema.
* [MCCS-2230] Respect default receiver interface configured in DAQ receivers via environment.
* [SKB-494] Update DAQ to support new SPEAD format.

## 0.17.0

* [MCCS-2141] Update ska-tango-base to 1.0.0
* [MCCS-2222] Include MccsTile attributes added as part of MCCS-2059 in the EDA config.

## 0.16.1

* [LOW-952] Point at ska-low-tmdata for AA0.5 telmodel data
* [MCCS-2216] Support nulls in chart values
* [MCCS-2223] Fix static delay docs

## 0.16.0

* [MCCS-2135] Pull versions of aavs-system and pyfabil based on tags rather than specific commits.
* [MCCS-2014] Add support for SP-3800 in MccsTile and SpsStation.
* [MCCS-2213] Remove local platform specs and templates and instead pull them from TelModel.
* [MCCS-2215] Update to latest version of `ska-low-mccs-common`
* [MCCS-2190] Update attributes to only push change events when the value changes.
* [SKB-452] Update Tile so that if not initialised or synchronised when its subrack reports power `ON` it will initialise itself.
* [SKB-324] [SKB-387] Change subrack fan speed parameter to require an integer to avoid an exception being raised by the SMB. Update local cached value of `SpsStation.SetChanneliserRounding` properly.
* [SKB-460] Fix inconsistency in `ApplyPointingDelays` command naming. Fix an off-by-one error in `ApplyPointingDelays`. Add attributes to Tile and Station containing the last pointing delays.
* [MCCS-2202] Update to the latest platform specs, helm templates and daq version.
* [MCCS-2200] Re-order attributes to greatly reduce the chance of encountering a cpptango segfault.
* [MCCS-2191] Move a lot of Daq configuration to the Daq repo and remove from this one.
* [MCCS-2210] Fix `UpdateStaticDelays` bug to properly allow Tiles to have different delays.
* [SKB-435] Improve defaults for some parameters, cast tuples to lists when comparing with lists, add info metadata block. Generally improve Tile health issues.
* [MCCS-2200] Add `retry_command_on_exception` to improve reliability when facing timeouts.
* [MCCS-2059] Add monitoring point attributes to MccsTile.
            Update ska-tango-util to 0.4.11
            Rename 'CHANGELOG' to 'CHANGELOG.md'
* [LOW-938] Add `ska-low-deployment` as `.deploy` submodule containing all helmfile templates and remove them locally.
* [MCCS-1508] Improve monitoring of overheating event.
* [MCCS-2200] Remove tile_info from polling loop (takes too long) and add claiming of hardware lock from a bad rebase.
* [MCCS-2189] Add ability to expose Daq's data services. Update relevant helmfile templates.
* [MCCS-2197] Correct `AcquireDataForCalibration` command to properly clear the LRC queue so it doesn't fill to capacity.
* [MCCS-2195] Fix an "off by one" indexing error in station component manager.
* [MCCS-1507] Reimplement TileComponentManager as a PollingComponentManager. Removes TileOrchestrator. Fixes SKB-281.
* [SKB-408] Change polling to push archive events when a value is polled instead of only on change.
* [MCCS-2189] Update to latest daq version and 0.6.0 specs
* [MCCS-2078] Add `tile.tile_info` attribute

## 0.15.0

* [MCCS-2176] Update RAL Platform Spec
* [MCCS-2044]: Fix automerge issues
* [MCCS-2044] Add AcquireDataForCalibration method to SpsStation.
* [MCCS-1530] Add functional testing for health computation and aggregation
* [MCCS-2180] CSP ingest IP
* [MCCS-2153] Add MCCS schemas to TelModel
* [MCCS-2048] [MCCS-2114] Add InitialiseStation to the self check list + set src IP before initialise
* [SPRTS-101]: prevent subrack from staying in UNKNOWN when polling fails
* [MCCS-2116]: Fix timeout error in spsStation.StopDataTransmission
* [MCCS-2121]: Update platform spec
* [MCCS-2117] Update ska-low-mccs-daq-interface to use gRPC wait_for_ready flag.
* [MCCS-2041] remove references to pyfabil tpm
* [MCCS-2120] Support DAQ data sync
* [MCCS-2109]: Reject calls to SpsStation.Off.
* [MCCS-2041]: Add configurable shutdown temperatures.
* [MCCS-2111]: Correct TileProgrammingState pushing.
* [MCCS-2113]: Remove the postgresql dependency. No longer used.
* [MCCS-2048] StationSelfCheckManager
* [MCCS-2021]: Changes to get mccs deployed at RAL
* [MCCS-2108] Fix docs
* [MCCS-2107] remove deprecated environments
* [MCCS-1507] update test to use tile simulator
* [MCCS-2054] [MCCS-2035] Remove calibration devices
* [MCCS-2103] gateway support
* [MCCS-2037] Update Tile temperatures to push ALARM
* [MCCS-1507] update tile simulator interface
* [MCCS-2060] Add eda-config.yaml with all spshw attributes.
* [MCCS-2095] Fix antenna mapping bug
* [SPRTS-126]: expose missing health structures and fix default health parameters
* [MCCS-2089] Add PyPi as source for Poetry and update daq image used.
* [MCCS-2040] Link functional tests to requirements
* [MCCS-2084] Fix cluster domain configuration issue.
* [MCCS-1793] Update aavs system tag
* [MCCS-1883] Add bandpass attribute to sps station
* [MCCS-2070] string keys
* [MCCS-2076] Update ska-low-mccs-common dependency
* [MCCS-1988] Add SpsStation.UpdateCalibration()
* [MCCS-1998] - Update spsstation task_callback with command result
* [MCCS-2008] Fix Tile Simulator crash in timing thread
* [MCCS-2056] Make antenna config as agnostic as possible
* [MCCS-2066] station address handling
* [MCCS-1995] -dirty fix
* [MCCS-1780] Cannot stop beam data
* [MCCS-1982] Implement single 40G connection in MCCS
* [MCCS-1995] values schema
* [MCCS-1970] Fix tile state discovery and add test
* [MCCS-1961] Update rounding attributes
* [MCCS-1986] Fix delay mapping
* [MCCS-1986] Fix adc_data
* [MCCS-1551] Functional tests for the bandpass monitor process
* [MCCS-1983] Map antenna order to channel order in SpsStation.LoadPointingDelays
* [MCCS-1793] Fix pps-delay bug. It was being used for a correction and a delay incorrectly
* [MCCS-1978] infra-managed Low ITF credentials
* [MCCS-1925] Update ppsPresent to a DevBoolean, the EDA is configured for a boolean.
* [MCCS-2176] Update RAL platform spec to 0.5.0

## 0.14.0

* [MCCS-1957] Support deployment namespace override
* [SKB-280] Change type of SpsStation.preadulevels from int to float
* [SKB-278] Handle numpy arrays in SpsStationComponentManager.adc_power()
* [MCCS-1925] Update ppsPresent to push change events
* [MCCS-1880] Implement mechanism in SpsStation to retrieve antenna locations
* [MCCS-1959] Remove TaskExcecutorComponentManager base class from TpmDriver
* [MCCS-1884] Update SpsStation adcPower to push change and archive events
* [MCCS-1885] Add 'cadence' as arg to bandpass monitor
* [MCCS-1961] Update preaduLevels to push change events
* [SKB-273], [MCCS-1960] Add StationID as tango device property on MccsTile, set TileID property to be continuous 0-15
* [MCCS-1961] Fix FPGA Temperature Summary on SpsStation
* [MCCS-1966] Use infa-issued credentials for AAVS3
* [MCCS-1961] Update statis tile delays attribute to push
* [MCCS-1975] cabinet subnet handling
* [MCCS-1905] Latest TPM Firmware, AAVS-System and PyFABIL (sbf510 bitfiles)
* [MCCS-1918] Implement ADC equalisation in MCCS as tango command
* [MCCS-1764] MccsTIle bugs corrected

## 0.13.0

* [SKB-276] fix typo in MccsTile pps_delays -> pps_delay
* [SKB-274] Set SpsStation's proxies' source to DevSource.Dev

## 0.12.1

* [MCCS-1939] AAVS3 staging environment for MCCS repos
* [MCCS-1829] Helmfile cannot create more than 1 daq-server.
* [MCCS-1944] Get Chart.lock files under version control
* [MCCS-1949] Improve ska-low-mccs-spshw chart flexibility
* [MCCS-1881] Add property to SPSStation for a DAQ TRL
* [SKB-272] Tile stuck in Programmed "tileprogrammingstate"

## 0.12.0

* [LOW-637] Move pyfabil dependency from Alessio's BitBucket to SKA GitLab
* [LOW-637] Update ska-tango-util to 0.4.9
* [LOW-637] Update ska-low-mccs-daq to 0.6.0
* [LOW-612] Fix old pyfabil ref
* [LOW-637] Update makefile repo and use appVersion as default tag in Helm chart
* [MCCS-1023] Corrected On sequence in SpsStation. Added SpsStation.Initialise command to reinitialise tiles. Corrected TileSimulator to manage configuration commands
* [MCCS-1867] DAQ directory subsystem slug incorrect
* [MCCS-1859] support arbitrary helm values
* [MCCS-1857] refactor helmfile templates
* [MCCS-1797] Configure EDA for bandpass data
* [MCCS-1805] Update calibration table field to DOUBLE PRECISION
* [MCCS-1631] Add bandpass monitoring
* [MCCS-1811] - Add functional tests using daq-handler.
* [MCCS-1805] Update station calibrator chart.
* [MCCS-1830] Remove skip on test.
* [MCCS-1592] Gherkin for bandpass monitor functional tests
* [LOW-612] move preADU set/get to pyaavs

## 0.11.0

* [MCCS-1851] Update dependencies
* [MCCS-1845] Support disabling SPS
* [MCCS-1831] SKUID as a platform service
* [LOW-589] PreADU attenuations aren't set correctly
* [MCCS-1752] Dashboard for SpsStation
* [MCCS-1724] Add SPEAD test
* [MCCS-1758] Make logging ADR-55 compliant
* [MCCS-1791] ignore external stimuli when offline
* [MCCS-1783] TANGO state not being updated in MccsTile.
* [MCCS-1781] Fix indentation bug in values file.
* [MCCS-1777] Fix DAQ.Start task_callback error.
* [LOW-612] Move preADU set/get methods to pyaavs.

## 0.10.0

* [MCCS-1775] Fix bug in deployment configuration for minikube platforms
* [MCCS-1762] update to pytango 9.4.2
* [MCCS-1697] Support tangodb being provided as a platform service, so we don't need to deploy it ourselves

## 0.9.0

* [MCCS-1690] remove ska-tango-base
* [MCCS-1682] pull in daq chart
* [MCCS-1681] remote platform spec
* [MCCS-1678] pair programming updates
* [MCCS-1587] Outline plan to implement the Functional test shows DAQ metadata are
* [MCCS-1671] Fix intermittent SpsStation Initialise test
* [MCCS-1670] support multiple stations in clusters
* [MCCS-1593] Connect metadata to daq output
* [MCCS-1664] Add noise to the simulated bandpass
* [MCCS-1610] helmfile
* [MCCS-1663] Fix key error in stop_sending_data.
* [MCCS-1546] Update the IntegratedChannelDataSimulator to create simulated bandpass data

## 0.8.0

* [MCCS-1547] Tile Component Manager and TpmDriver to use the new TileSimulator
* [MCCS-1650] Updating TPM Firmware to sbf416 version

## 0.7.1

* Updated make submodule.

## 0.7.0

* [MCCS-1565] Updated TPM Driver to Support 40G Gateway
* [MCCS-1644] Update station name to spsstation
* [MCCS-1623] Update tango preadulevels type.
* [MCCS-1456] DAQ Functional Tests
* [MCCS-1623] Modified TPM driver to support TPM 1.6 preADU
* [MCCS-1636] Use ska-ser-sphinx-theme
* [MCCS-1633] Update /docs/src/_static/img/ in MCCS repos
* [MCCS-1589] Skuid added in the spshw umbrella
* [MCCS-1579] Add calibration store device, and PostgreSQL database for data storage
* [MCCS-1518] No warning given if tile device initialised without subrack fqdn
* [MCCS-1605] Fix intermittent health state test
* [MCCS-1627] Dependency update
* [MCCS-1613] Add version logging to device init

## 0.6.0

* [MCCS-1539] DAQ receiver Tango device
* [MCCS-1529] Kwargs refactor
* [MCCS-1569] [MCCS-1570] [MCCS-1572] Calibration store device, mock field station device, station calibrator device
* [MCCS-1451] Tile simulator improvements
* [mccs-1419] Jupyter notebooks to generate 4 and 8 beams.
* [MCCS-1525] Tile health model fixes
* [MCCS-1387] Subrack health

## 0.5.0

* [MCCS-1412] Chart fixes and improvements
* [MCCS-1390] Add rules for Tile health
* [MCCS-1388] Add rules for SpsStation Health
* [MCCS-1493] Bugfix: correct lmc_param keys
* [MCCS-1408] new AAVS3 and Low-ITF facility spec
* [MCCS-1501] chart template bugfix

## 0.4.0

* [MCCS-1495] Inline facility data
* [MCCS-1418] Added notebook to generate a beam from a single TPM input.
* [MCCS-1441] Update tile simulator
* [MCCS-1449] Health cleanup
* [MCCS-1267] Added Station commands to set pointing delays
* [MCCS-1427] JSON validation
* [MCCS-1081] Modify MCCS tile to support AAVS tile monitoring points
* [MCCS-1438] support enable above instance level
* [MCCS-1429] Update iTPM bitfiles to version sbf415
* [MCCS-1257] Station initialisation.
* [MCCS-1360] Fix bug in MccsTile config
* [MCCS-1325] Station test harness

## 0.3.2

* LOW-386 - UNKNOWN / OFF bugfix
* MCCS-1351 - Revert subrack_fan_speeds change
* MCCS-1346 - TPM initialisation bugfix

## 0.3.1

* LOW-386   - subrack_fan_speeds -> subrack_fan_speed

## 0.3.0

* MCCS-1343 - Final static type check of tile tests post refactor
* MCCS-1339 - use ska-tango-testing
* MCCS-1324 - Static type checking of tile in ska-low-mccs-spshw
* MCCS-1239 - xray upload
* MCCS-1216 - Add Ingress to Jupyterhub
* MCCS-1225 - k8s-test-psi-low
* MCCS-1257 - Added skeleton SpshwStation device.
* LOW-386   - use correct component manager attr in GetArpTable
* MCCS-1236 - Attach xray tickets to feature file
* MCCS-1258 - new subrack device

## 0.2.1

* MCCS-1318 - Fix pyfabil/aavs commit SHAs
* MCCS-1316/ MCCS-1319 - add facility yaml files

## 0.2.0

* MCCS-1256 - External simulator
* MCCS-1148 - Fix bug with incorrect reporting of Tile On/Off result

## 0.1.0

* MCCS-1292 - Move any changed tile & subrack files from ska-low-mccs
* MCCS-1218 - Generate new repository mccs-spshw
