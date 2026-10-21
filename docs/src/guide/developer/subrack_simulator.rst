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
     - ✓
   * - ``get_pps_phase_window``
     - –
     - ✓
     - –
     - ✓
   * - ``set_pll_phase_offset``
     - –
     - ✓
     - –
     - ✓
   * - ``set_pps_phase_window``
     - –
     - ✓
     - –
     - ✓
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
     - ✓
     - ✓
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

Checking the simulator against the API
--------------------------------------

The tests in ``tests/functional/test_subrack_simultor_api_parity.py``
check the responses of a subrack web API against what the API is
expected to provide. They do not know whether they are talking to a real
subrack or to the simulator, so the same tests check that the simulator
behaves like the real API, and that the expectations match real subracks.

Selecting a target
~~~~~~~~~~~~~~~~~~

The tests are marked ``subrack_api`` and are deselected unless pytest is
given a target with ``--subrack-api=HOST:PORT``: the web API of a real
subrack or of a subrack simulator, at HOST:PORT (the subrack web API
listens on port 8081). The tests treat every target alike.

The tests choose their expectations from the subrack's SMM BIOS version,
in its ``board_info`` attribute: the expectations of the highest
version not newer than the BIOS. So BIOS 1.7.0 gets those of 1.6.0, and
a BIOS older than 1.6.0 fails every test.

Running against the simulator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Start a simulator, emulating API version ``1.6.0`` or ``1.8.0``::

    SUBRACK_SIMULATOR_API_VERSION=1.8.0 SUBRACK_SIMULATOR_PORT=8081 \
        uv run subrackSimulator

Then, in another terminal::

    uv run pytest tests/functional/test_subrack_simultor_api_parity.py \
        --subrack-api=localhost:8081 --no-cov -rfs

A failure is a difference between the simulator and the API, for
example a command or an attribute that the simulator does not provide
(see the tables above).

Running against a real subrack
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The tests never change the hardware: they read attributes, and send only
the commands in ``SAFE_COMMANDS``. Running them does reset the peak-hold
values and counters of the 1.8.0 health status, which other clients
(MCCS, dashboards) report.

If the subrack is not reachable directly, forward its web API port over
SSH, from where the tests will run (for example inside the
devcontainer, which cannot reach a tunnel opened on the host)::

    ssh -N -L 18081:localhost:8081 USER@SUBRACK_HOST
    ssh -N -L 18081:SUBRACK_HOST:8081 USER@JUMP_HOST  # through a jump host

Then, in another terminal::

    uv run pytest tests/functional/test_subrack_simultor_api_parity.py \
        --subrack-api=localhost:18081 -n 0 --no-cov -rfs

``-n 0`` runs the tests one at a time, for readable output; the tests
send one request at a time anyway, because the subrack's web server can
only answer one. ``--no-cov`` skips the coverage report, and ``-rfs``
lists the failures and skipped tests, with reasons.

Reading the results
~~~~~~~~~~~~~~~~~~~

Most tests are parametrised by every command or attribute of every API
version, and skip those that do not apply to the version under test, or
that are never sent. A failure against a real subrack is a difference
between it and the expectations in the test module; a failure against
the simulator is a difference between the simulator and the API.

Running in the pipeline
~~~~~~~~~~~~~~~~~~~~~~~

To run these tests in the pipeline, pass the target to pytest, for
example with ``K8S_PYTEST_EXTRA_ARGUMENTS=--subrack-api=HOST:PORT``.
