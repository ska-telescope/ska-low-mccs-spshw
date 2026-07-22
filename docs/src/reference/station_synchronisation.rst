###########################
 SpsStation synchronisation
###########################

This page describes how the ``SpsStation`` brings its Tiles up to a
synchronised state via the ``On`` and ``Initialise`` commands.

*********************************
 On and Initialise command steps
*********************************

On command
==========

The ``On`` command (``SpsStationComponentManager._on``) performs the
following steps, in order:

1. If all Tiles are already ``Initialised`` or ``Synchronised``, the command
   completes immediately.

2. Turn on all subracks (``_turn_on_subracks``), if not already on.

3. Set the tile source IPs (``_set_tile_source_ips``). 
   Loop through the stations TPMs and set the source IP from the science data network first address.

4. Set the global reference time (``_set_global_reference_time``).
   With the updated SPEAD header in MCCS-2170, this reference time is global to a station and distributed to its tiles. 
   Its use is detailed in https://developer.skao.int/projects/ska-low-mccs-spshw/en/thorn-595/reference/tile_brief_overview.html#synchronization-procedure.

5. Turn on all tiles (``_turn_on_tiles``), if not already on. As part of
   bringing a Tile to ``PowerState.ON``, the Tile is also initialised - see
   the MccsTile general overview page linked below for what this involves.

6. Initialise the tile parameters (``_initialise_tile_parameters``). e.g.
   ``staticTimeDelays``, ``channeliserRounding``, ``cspRounding``, ``preaduLevels``, ``ppsDelayCorrection``.
   Also configure control data using ``SetLmcDownload`` and initialise the beamformer ``ConfigureStationBeamformer``

7. Initialise the station (``_initialise_station``). Confiure the CSP, LMC and LMC integrated data routing.
   Internally using ``SetCspDownload``, ``SetLmcDownload`` and ``SetLmcIntegratedDownload``.

8. Wait for the ARP table to be populated (``_wait_for_arp_table``).

9.  Route data to the DAQ/CSP destinations (``_route_data``). Route data streams to the relevant DAQ endpoints,
   Internally uses ``SetLmcDownload``, ``SetLmcIntegratedDownload`` and ``ConfigureIntegratedChannelData``.

10. Check station synchronisation (``_check_station_synchronisation``).

Initialise command
====================

The ``Initialise`` command (``SpsStationComponentManager.initialise``) is
used when the station is already ``On``, and resets it to the
``Initialised`` state. It performs the following steps, in order:

1. Check that all subracks and tiles are already on; fail otherwise.

2. Set the tile source IPs (``_set_tile_source_ips``).

3. Set the global reference time (``_set_global_reference_time``). 
   With the updated SPEAD header in MCCS-2170, this reference time is global to a station and distributed to its tiles. 
   Its use is detailed in https://developer.skao.int/projects/ska-low-mccs-spshw/en/thorn-595/reference/tile_brief_overview.html#synchronization-procedure.

4. Re-initialise the tiles (``_reinitialise_tiles``): send ``initialise()``
   to each Tile and wait for ``tileProgrammingState`` to reach
   ``Initialised``/``Synchronised`` for all tiles.

5. Initialise the tile parameters (``_initialise_tile_parameters``). e.g.
   ``staticTimeDelays``, ``channeliserRounding``, ``cspRounding``, ``preaduLevels``, ``ppsDelayCorrection``.
   Also configure control data using ``SetLmcDownload`` and initialise the beamformer ``ConfigureStationBeamformer``

6. Initialise the station (``_initialise_station``). Confiure the CSP, LMC and LMC integrated data routing.
   Internally using ``SetCspDownload``, ``SetLmcDownload`` and ``SetLmcIntegratedDownload``.

7. Wait for the ARP table to be populated (``_wait_for_arp_table``).

8. Route data to the DAQ/CSP destinations (``_route_data``). Route data streams to the relevant DAQ endpoints,
   Internally uses ``SetLmcDownload``, ``SetLmcIntegratedDownload`` and ``ConfigureIntegratedChannelData``.

9.  Check station synchronisation (``_check_station_synchronisation``).

Further reading
=================

Steps 4-6 of ``Initialise`` (and the equivalent step 5 of ``On``) are where
each Tile is actually brought from ``Programmed`` through to
``Initialised``/``Synchronised``. For a detailed description of that
procedure - PPS alignment, ADC synchronisation, the ``globalReferenceTime``
attribute, and the two supported ways of synchronising a Tile - see the
`Synchronization Procedure` section of the MccsTile general overview page:
https://developer.skao.int/projects/ska-low-mccs-spshw/en/latest/reference/tile_brief_overview.html#synchronization-procedure

*********************************
 SAT WhiteRabbit integration
*********************************

.. warning::
   This section describes a **prototype** integration. It is not the
   current default behaviour of ``SpsStation``, and the interfaces
   described here are subject to change.

For details about the SAT (Signal And Timing) subsystem please see https://developer.skao.int/projects/ska-sat-lmc/en/latest/.

White Rabbit is responsible for distributing timing signals that keep the RPFs (Remote Processing Facilities) 
synchronised with the CPF (Central Processing Facility), as well as for timing distribution within the CPF.

Each SPS rack contains one EndNode, which distributes the 10 MHz and 1PPS signals to the subracks via coax. 
The subrack then distributes these signals to the TPMs, which synchronise their own clocks accordingly. 
Again, please see: https://developer.skao.int/projects/ska-low-mccs-spshw/en/latest/reference/tile_brief_overview.html#synchronization-procedure.

Our SpsStation ON and initialisation procedure is therefore gated on having good, 
stable input timing. We verify this by observing the HealthState of the WREN.

Our SpsStation device will have an optional DeviceProperty, "WREN_TRL" (name TBC). 
If this is supplied, the device will wait for this signal before attempting synchronisation. 
The wait time will be configurable, but as a ballpark figure, 
it can take 5 minutes to indicate it is OK if WR EN is powered up after WR GM. 
If powered up before, it can take longer.

We define a property, "wait_time" (name TBC), 
that can be configured; if the HealthState is not OK within that period, 
we do not attempt initialisation and the command fails.

Concretely, in this prototype, a single wait step is inserted at the very start of each command, 
before anything is turned on or re-initialised:

* ``On``: the wait for the WREN ``healthState`` to reach
  ``HealthState.OK`` (or for the configured ``wait_time`` to elapse) is
  inserted before ``_turn_on_subracks`` is called. If the wait times out
  without the WREN reaching ``OK``, the ``On`` command fails immediately
  and no subrack or Tile action is attempted.

* ``Initialise``: the same wait is inserted before ``_set_tile_source_ips``
  is called. If the wait times out without the WREN reaching ``OK``, the
  ``Initialise`` command fails immediately and no re-initialisation is
  attempted.

In both cases, the remainder of the sequence described above is
unchanged.

The sequence diagram below shows both commands with this new WhiteRabbit
wait step:

.. uml:: sat_wren_prototype_sequence.uml
