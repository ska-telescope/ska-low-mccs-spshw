=================
Subrack simulator
=================

The subrack simulator stands in for the subrack management board (SMB) web API.
It emulates API version ``1.6.0`` (the default) or ``1.8.0``,
selected with the ``api_version`` argument,
the ``SUBRACK_SIMULATOR_API_VERSION`` environment variable,
or ``api_version`` in the Helm chart's ``simulators.subracks`` values.

The tables below show which commands and attributes of the SMB web API the simulator provides.
"API master" is the SMB web API before 1.8.0, which simulator version ``1.6.0`` emulates.

* ✓ provided
* ✗ provided by the API, but not simulated
* – not provided by that version

.. list-table:: Commands
   :header-rows: 1

   * - Name
     - API master
     - API 1.8.0
     - Simulator 1.6.0
     - Simulator 1.8.0
   * - ``abort_command``
     - ✓
     - ✓
     - ✓
     - ✓
   * - ``are_tpms_on``
     - ✓
     - ✓
     - ✗
     - ✗
   * - ``command_completed``
     - ✓
     - ✓
     - ✓
     - ✓
   * - ``get_all_attributes``
     - ✓
     - ✓
     - ✗
     - ✗
   * - ``get_default_pll_source``
     - ✓
     - ✓
     - ✗
     - ✗
   * - ``get_default_ps_redundancy``
     - ✓
     - ✓
     - ✗
     - ✗
   * - ``get_health_dictionary``
     - ✓
     - ✓
     - ✗
     - ✗
   * - ``get_health_status``
     - ✓
     - ✓
     - ✓
     - ✓
   * - ``is_tpm_on``
     - ✓
     - ✓
     - ✗
     - ✗
   * - ``list_attributes``
     - ✓
     - ✓
     - ✗
     - ✗
   * - ``list_commands``
     - ✓
     - ✓
     - ✓
     - ✓
   * - ``poweroff_subrack``
     - ✓
     - ✓
     - ✗
     - ✗
   * - ``re_init_pll``
     - ✓
     - ✓
     - ✗
     - ✗
   * - ``set_default_pll_source``
     - ✓
     - ✓
     - ✗
     - ✗
   * - ``set_default_ps_redundancy``
     - ✓
     - ✓
     - ✗
     - ✗
   * - ``set_fan_mode``
     - ✓
     - ✓
     - ✓
     - ✓
   * - ``set_subrack_fan_speed``
     - ✓
     - ✓
     - ✓
     - ✓
   * - ``turn_off_tpm``
     - ✓
     - ✓
     - ✓
     - ✓
   * - ``turn_off_tpms``
     - ✓
     - ✓
     - ✓
     - ✓
   * - ``turn_on_tpm``
     - ✓
     - ✓
     - ✓
     - ✓
   * - ``turn_on_tpms``
     - ✓
     - ✓
     - ✓
     - ✓
   * - ``set_power_supply_fan_speed``
     - ✓
     - –
     - ✓
     - –
   * - ``tpm_info``
     - ✓
     - –
     - ✗
     - –
   * - ``get_pll_phase_offset``
     - –
     - ✓
     - –
     - ✗
   * - ``get_pps_phase_window``
     - –
     - ✓
     - –
     - ✗
   * - ``set_pll_phase_offset``
     - –
     - ✓
     - –
     - ✗
   * - ``set_pps_phase_window``
     - –
     - ✓
     - –
     - ✗
   * - ``set_watchdog_enabled``
     - –
     - ✓
     - –
     - ✗
   * - ``set_watchdog_timeout_minutes``
     - –
     - ✓
     - –
     - ✗

.. list-table:: Attributes
   :header-rows: 1

   * - Name
     - API master
     - API 1.8.0
     - Simulator 1.6.0
     - Simulator 1.8.0
   * - ``api_version``
     - ✓
     - ✓
     - ✗
     - ✗
   * - ``assigned_tpm_ip_adds``
     - ✓
     - ✓
     - ✗
     - ✗
   * - ``backplane_temperatures``
     - ✓
     - ✓
     - ✓
     - ✓
   * - ``board_current``
     - ✓
     - ✓
     - ✓
     - ✓
   * - ``board_info``
     - ✓
     - ✓
     - ✓
     - ✓
   * - ``board_temperatures``
     - ✓
     - ✓
     - ✓
     - ✓
   * - ``cpld_pll_locked``
     - ✓
     - ✓
     - ✓
     - ✓
   * - ``power_supply_currents``
     - ✓
     - ✓
     - ✓
     - ✓
   * - ``power_supply_fan_speeds``
     - ✓
     - ✓
     - ✓
     - ✓
   * - ``power_supply_powers``
     - ✓
     - ✓
     - ✓
     - ✓
   * - ``power_supply_voltages``
     - ✓
     - ✓
     - ✓
     - ✓
   * - ``subrack_fan_mode``
     - ✓
     - ✓
     - ✓
     - ✓
   * - ``subrack_fan_speeds``
     - ✓
     - ✓
     - ✓
     - ✓
   * - ``subrack_fan_speeds_percent``
     - ✓
     - ✓
     - ✓
     - ✓
   * - ``subrack_pll_locked``
     - ✓
     - ✓
     - ✓
     - ✓
   * - ``subrack_timestamp``
     - ✓
     - ✓
     - ✓
     - ✓
   * - ``tpm_ips``
     - ✓
     - ✓
     - ✗
     - ✗
   * - ``tpm_on_off``
     - ✓
     - ✓
     - ✓
     - ✓
   * - ``tpm_powers``
     - ✓
     - ✓
     - ✓
     - ✓
   * - ``tpm_present``
     - ✓
     - ✓
     - ✓
     - ✓
   * - ``tpm_supply_fault``
     - ✓
     - ✓
     - ✗
     - ✗
   * - ``tpm_voltages``
     - ✓
     - ✓
     - ✓
     - ✓
   * - ``tpm_currents``
     - ✓
     - –
     - ✓
     - –
   * - ``tpm_mcu_temperatures``
     - ✓
     - –
     - ✗
     - –
   * - ``tpms_temp_alarms``
     - ✓
     - –
     - ✗
     - –
   * - ``tpms_temperatures``
     - ✓
     - –
     - ✗
     - –
   * - ``tpms_voltage_alarms``
     - ✓
     - –
     - ✗
     - –
   * - ``get_watchdog_status``
     - –
     - ✓
     - –
     - ✗
