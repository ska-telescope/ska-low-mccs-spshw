MccsTile health
===============

Tango attributes and their configuration
-----------------------------------------

Every monitoring point on ``MccsTile`` (temperatures, voltages, currents, PLL
lock status, and so on) is exposed as a Tango attribute. Alongside its value,
every Tango attribute carries a **quality factor**
(``tango.AttrQuality``), which is one of:

- ``ATTR_VALID`` - the value is within its configured normal range.
- ``ATTR_WARNING`` - the value has crossed a configured warning threshold.
- ``ATTR_ALARM`` - the value has crossed a configured alarm threshold.
- ``ATTR_INVALID`` - the value is not currently valid (for example, not yet
  read from hardware).

For numeric attributes, the thresholds that drive this quality factor are
configured on the attribute itself, via the ``min_alarm``, ``max_alarm``,
``min_warning`` and ``max_warning`` parameters. These are the same
parameters returned by
`DeviceProxy.get_attribute_config_ex <https://tango-controls.readthedocs.io/projects/pytango/en/latest/api/client_api/device_proxy.html#tango.DeviceProxy.get_attribute_config_ex>`_,
and they can be inspected or changed at runtime using the standard PyTango
attribute configuration API. **Tango itself** is responsible for comparing
each new value against these thresholds and computing the resulting quality
factor whenever the attribute is updated - ``MccsTile`` does not compute
this quality factor itself. The thresholds are stored as **configuration in
the Tango database**, not hardcoded in ``MccsTile``, so they can be inspected or
retuned per-deployment without a code change.

Some non-numeric attributes (for example boolean status flags) do not have
alarm/warning thresholds in the Tango sense. For these, ``MccsTile``
computes the quality factor in software, for example treating a boolean
flag as ``ATTR_ALARM`` when it is in an unexpected state.

Every configured threshold and computed quality factor feeds into the
device's overall ``healthState``, via ``HealthRecorder``, described below.

HealthRecorder
--------------

``MccsTile`` does not derive ``healthState`` by re-evaluating raw monitoring
point values against a separate set of rules. Instead, it delegates this to
`HealthRecorder, documented here <https://developer.skao.int/projects/ska-low-mccs-common/en/latest/reference_material/health_recorder.html>`_,
a class in ``ska_low_mccs_common`` that derives a device's ``healthState``
and ``healthReport`` purely from the Tango **quality factors** of a
configured set of that device's own attributes.

``MccsTile`` uses ``TileHealthRecorder``
(``ska_low_mccs_spshw.tile.tile_health_recorder.TileHealthRecorder``), a
subclass that extends ``HealthRecorder`` to additionally derive **per-group**
health for each of its monitoring groups (temperature, voltage, current,
ADC, timing, I/O and DSP), exposed as the intermediate ``*Health`` attributes
(for example ``temperatureHealth``, ``voltageHealth``) mentioned under
`healthState`_ below. Which attributes belong to which group is itself
derived from ``attribute_monitoring_point_map``, described next.

Everything on this page only applies when the ``UseAttributesForHealth``
device property is ``True`` (the default, per ADR-115). When it is ``False``,
``MccsTile`` instead falls back to the legacy ``TileHealthModel``, which
re-evaluates raw values against its own rules rather than using
``HealthRecorder``. ``UseAttributesForHealth=False`` is **deprecated** and
due to be removed soon, along with ``TileHealthModel``.

Monitored attributes and their TPM monitoring points
-----------------------------------------------------

``MccsTile`` reads raw hardware values from the TPM via the tpm-api's
``get_health_status()`` call, which returns a nested dictionary of
monitoring points (stored on the device as ``tile_health_structure``). To
know which raw monitoring point feeds which Tango attribute, ``MccsTile``
keeps a dictionary, ``attribute_monitoring_point_map``:

- the **key** is the Tango attribute name (for example
  ``fpga1Temperature``);
- the **value** is the dictionary traversal path (a list of keys) used to
  look up that monitoring point in the tpm-api monitoring point lookup
  table (for example ``["temperatures", "FPGA0"]``).

Each time new values are polled from hardware, ``MccsTile`` walks this path
into ``tile_health_structure`` to fetch the current value for every mapped
attribute, and pushes it as that attribute's new value.

The full map, as of this writing, is:

.. csv-table:: Tango attribute to TPM monitoring point mapping
   :header: "Tango attribute", "TPM monitoring point path"
   :widths: 30, 40

   "``ppsPresent``", "``timing -> pps -> status``"
   "``fpga1Temperature``", "``temperatures -> FPGA0``"
   "``fpga2Temperature``", "``temperatures -> FPGA1``"
   "``boardTemperature``", "``temperatures -> board``"
   "``io``", "``io``"
   "``dsp``", "``dsp``"
   "``voltages``", "``voltages``"
   "``temperatures``", "``temperatures``"
   "``temperatureADC0``", "``temperatures -> ADC0``"
   "``temperatureADC1``", "``temperatures -> ADC1``"
   "``temperatureADC2``", "``temperatures -> ADC2``"
   "``temperatureADC3``", "``temperatures -> ADC3``"
   "``temperatureADC4``", "``temperatures -> ADC4``"
   "``temperatureADC5``", "``temperatures -> ADC5``"
   "``temperatureADC6``", "``temperatures -> ADC6``"
   "``temperatureADC7``", "``temperatures -> ADC7``"
   "``temperatureADC8``", "``temperatures -> ADC8``"
   "``temperatureADC9``", "``temperatures -> ADC9``"
   "``temperatureADC10``", "``temperatures -> ADC10``"
   "``temperatureADC11``", "``temperatures -> ADC11``"
   "``temperatureADC12``", "``temperatures -> ADC12``"
   "``temperatureADC13``", "``temperatures -> ADC13``"
   "``temperatureADC14``", "``temperatures -> ADC14``"
   "``temperatureADC15``", "``temperatures -> ADC15``"
   "``adcs``", "``adcs``"
   "``timing``", "``timing``"
   "``currents``", "``currents``"
   "``currentFE0``", "``currents -> FE0_mVA``"
   "``currentFE1``", "``currents -> FE1_mVA``"
   "``voltageAVDD3``", "``voltages -> AVDD3``"
   "``voltageVrefDDR0``", "``voltages -> DDR0_VREF``"
   "``voltageVrefDDR1``", "``voltages -> DDR1_VREF``"
   "``voltageMan1V2``", "``voltages -> MAN_1V2``"
   "``voltageMGT_AVCC``", "``voltages -> MGT_AVCC``"
   "``voltageMGT_AVTT``", "``voltages -> MGT_AVTT``"
   "``voltageMon5V0``", "``voltages -> MON_5V0``"
   "``voltageMon3V3``", "``voltages -> MON_3V3``"
   "``voltageMon1V8``", "``voltages -> MON_1V8``"
   "``voltageSW_AVDD1``", "``voltages -> SW_AVDD1``"
   "``voltageSW_AVDD2``", "``voltages -> SW_AVDD2``"
   "``voltageVIN``", "``voltages -> VIN``"
   "``voltageVM_AGP0``", "``voltages -> VM_AGP0``"
   "``voltageVM_AGP1``", "``voltages -> VM_AGP1``"
   "``voltageVM_AGP2``", "``voltages -> VM_AGP2``"
   "``voltageVM_AGP3``", "``voltages -> VM_AGP3``"
   "``voltageVM_AGP4``", "``voltages -> VM_AGP4``"
   "``voltageVM_AGP5``", "``voltages -> VM_AGP5``"
   "``voltageVM_AGP6``", "``voltages -> VM_AGP6``"
   "``voltageVM_AGP7``", "``voltages -> VM_AGP7``"
   "``voltageVM_CLK0B``", "``voltages -> VM_CLK0B``"
   "``voltageVM_CLK1B``", "``voltages -> VM_CLK1B``"
   "``voltageVM_DDR0_VTT``", "``voltages -> VM_DDR0_VTT``"
   "``voltageVM_DDR1_VDD``", "``voltages -> VM_DDR1_VDD``"
   "``voltageVM_DDR1_VTT``", "``voltages -> VM_DDR1_VTT``"
   "``voltageVM_DRVDD``", "``voltages -> VM_DRVDD``"
   "``voltageVM_DVDD``", "``voltages -> VM_DVDD``"
   "``voltageVM_FE0``", "``voltages -> VM_FE0``"
   "``voltageVM_FE1``", "``voltages -> VM_FE1``"
   "``voltageVM_MGT0_AUX``", "``voltages -> VM_MGT0_AUX``"
   "``voltageVM_MGT1_AUX``", "``voltages -> VM_MGT1_AUX``"
   "``voltageVM_PLL``", "``voltages -> VM_PLL``"
   "``voltageVM_SW_AMP``", "``voltages -> VM_SW_AMP``"
   "``adc_pll_lock_status``", "``adcs -> pll_status``"
   "``fpga0_qpll_status``", "``io -> jesd_interface -> qpll_status -> FPGA0``"
   "``fpga0_qpll_counter``", "``io -> jesd_interface -> qpll_status -> FPGA0``"
   "``fpga1_qpll_status``", "``io -> jesd_interface -> qpll_status -> FPGA1``"
   "``fpga1_qpll_counter``", "``io -> jesd_interface -> qpll_status -> FPGA1``"
   "``io_f2f_interface_pll_status_fpga0``", "``io -> f2f_interface -> pll_status -> FPGA0``"
   "``io_f2f_interface_pll_status_fpga0_counter``", "``io -> f2f_interface -> pll_status -> FPGA0``"
   "``io_f2f_interface_pll_status_fpga1``", "``io -> f2f_interface -> pll_status -> FPGA1``"
   "``io_f2f_interface_pll_status_fpga1_counter``", "``io -> f2f_interface -> pll_status -> FPGA1``"
   "``io_f2f_interface_soft_error_fpga0``", "``io -> f2f_interface -> soft_error -> FPGA0``"
   "``io_f2f_interface_soft_error_fpga1``", "``io -> f2f_interface -> soft_error -> FPGA1``"
   "``io_f2f_interface_hard_error_fpga0``", "``io -> f2f_interface -> hard_error -> FPGA0``"
   "``io_f2f_interface_hard_error_fpga1``", "``io -> f2f_interface -> hard_error -> FPGA1``"
   "``timing_pll_lock_status``", "``timing -> pll``"
   "``timing_pll_count``", "``timing -> pll``"
   "``timing_pll_40g_lock_status``", "``timing -> pll_40g``"
   "``timing_pll_40g_count``", "``timing -> pll_40g``"
   "``adc_sysref_timing_requirements``", "``adcs -> sysref_timing_requirements``"
   "``adc_sysref_counter``", "``adcs -> sysref_counter``"
   "``fpga0_clocks``", "``timing -> clocks -> FPGA0``"
   "``fpga1_clocks``", "``timing -> clocks -> FPGA1``"
   "``fpga0_clock_managers_count``", "``timing -> clock_managers -> FPGA0``"
   "``fpga0_clock_managers_status``", "``timing -> clock_managers -> FPGA0``"
   "``fpga1_clock_managers_count``", "``timing -> clock_managers -> FPGA1``"
   "``fpga1_clock_managers_status``", "``timing -> clock_managers -> FPGA1``"
   "``fpga0_lane_error_count``", "``io -> jesd_interface -> lane_error_count -> FPGA0``"
   "``fpga1_lane_error_count``", "``io -> jesd_interface -> lane_error_count -> FPGA1``"
   "``link_status``", "``io -> jesd_interface -> link_status``"
   "``fpga0_resync_count``", "``io -> jesd_interface -> resync_count -> FPGA0``"
   "``fpga1_resync_count``", "``io -> jesd_interface -> resync_count -> FPGA1``"
   "``ddr_initialisation``", "``io -> ddr_interface -> initialisation``"
   "``fpga0_ddr_reset_counter``", "``io -> ddr_interface -> reset_counter -> FPGA0``"
   "``fpga1_ddr_reset_counter``", "``io -> ddr_interface -> reset_counter -> FPGA1``"
   "``arp``", "``io -> udp_interface -> arp``"
   "``udp_status``", "``io -> udp_interface -> status``"
   "``fpga0_crc_error_count``", "``io -> udp_interface -> crc_error_count -> FPGA0``"
   "``fpga1_crc_error_count``", "``io -> udp_interface -> crc_error_count -> FPGA1``"
   "``fpga0_bip_error_count``", "``io -> udp_interface -> bip_error_count -> FPGA0``"
   "``fpga0_decode_error_count``", "``io -> udp_interface -> decode_error_count -> FPGA0``"
   "``fpga1_bip_error_count``", "``io -> udp_interface -> bip_error_count -> FPGA1``"
   "``fpga1_decode_error_count``", "``io -> udp_interface -> decode_error_count -> FPGA1``"
   "``fpga0_linkup_loss_count``", "``io -> udp_interface -> linkup_loss_count -> FPGA0``"
   "``fpga1_linkup_loss_count``", "``io -> udp_interface -> linkup_loss_count -> FPGA1``"
   "``io_data_router_status_fpga0``", "``io -> data_router -> status -> FPGA0``"
   "``io_data_router_status_fpga1``", "``io -> data_router -> status -> FPGA1``"
   "``data_router_discarded_packets``", "``io -> data_router -> discarded_packets``"
   "``tile_beamformer_status``", "``dsp -> tile_beamf``"
   "``station_beamformer_status``", "``dsp -> station_beamf -> status``"
   "``fpga0_station_beamformer_error_count``", "``dsp -> station_beamf -> ddr_parity_error_count -> FPGA0``"
   "``fpga1_station_beamformer_error_count``", "``dsp -> station_beamf -> ddr_parity_error_count -> FPGA1``"
   "``fpga0_station_beamformer_flagged_count``", "``dsp -> station_beamf -> discarded_or_flagged_packet_count -> FPGA0``"
   "``fpga1_station_beamformer_flagged_count``", "``dsp -> station_beamf -> discarded_or_flagged_packet_count -> FPGA1``"


healthState
-----------

``MccsTile`` derives its ``healthState`` from the quality factors of its
monitored attributes, via ``HealthRecorder`` (see above), rather than by
re-evaluating raw values against a separate set of rules. Its health always
reflects the **highest severity** quality factor currently reported by any
monitored attribute:

- If **any** monitored attribute is in ``tango.AttrQuality.ATTR_ALARM``,
  the device is ``FAILED``.
- If **none** are in ``ATTR_ALARM`` but **any** are in
  ``tango.AttrQuality.ATTR_WARNING``, the device is ``DEGRADED``.
- If all monitored attributes are ``ATTR_VALID``, the device is ``OK``.
- If none of the above apply (for example, attributes are ``ATTR_INVALID``
  and none are alarming or warning), the device is ``UNKNOWN``.

This severity ordering means a single alarming attribute is enough to fail
the device, regardless of how many other attributes are healthy, and a
single warning is enough to degrade it in the absence of any alarm.

The same worst-of-quality evaluation is also applied per monitoring group
(temperature, voltage, current, ADC, timing, I/O and DSP), each exposed as
its own intermediate ``*Health`` attribute (for example
``temperatureHealth``, ``voltageHealth``). The overall ``healthState`` is
the worst-of-quality result across all monitored attributes on the device.

healthReport
------------

``healthReport`` is a string attribute used to elaborate on the reason for
the current ``healthState``. Rather than being computed on demand,
``HealthRecorder`` subscribes to Tango change events on the monitored
attributes and keeps ``healthReport`` up to date as those events arrive:

- Whenever a monitored attribute pushes a change event, its latest value
  and quality factor are recorded.
- The device re-evaluates the worst-of-quality attribute(s) and, if the
  resulting ``healthState`` or report text has changed, updates
  ``healthReport`` accordingly.
- The report text identifies which attribute(s) are responsible for the
  current quality level, and their values, so that the cause of a
  ``DEGRADED`` or ``FAILED`` ``healthState`` can be identified without
  having to inspect every monitored attribute individually.

Because ``healthReport`` is driven by change events rather than polling, it
also needs to react to configuration changes that are not accompanied by a
new value - for example, tightening an alarm threshold on an attribute
whose value has not changed since it last updated. ``HealthRecorder``
handles this by also subscribing to attribute configuration change events,
and re-evaluating quality against the latest cached value whenever
thresholds are reconfigured.
