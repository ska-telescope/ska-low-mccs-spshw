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

4. Set the global reference time (``_set_global_reference_time``).

5. Turn on all tiles (``_turn_on_tiles``), if not already on. As part of
   bringing a Tile to ``PowerState.ON``, the Tile is also initialised - see
   the MccsTile general overview page linked below for what this involves.

6. Initialise the tile parameters (``_initialise_tile_parameters``), e.g.
   ``channeliserRounding``, ``cspRounding``, ``preaduLevels``, static time
   delays.

7. Initialise the station (``_initialise_station``).

8. Wait for the ARP table to be populated (``_wait_for_arp_table``).

9. Route data to the DAQ/CSP destinations (``_route_data``).

10. Check station synchronisation (``_check_station_synchronisation``).

Initialise command
====================

The ``Initialise`` command (``SpsStationComponentManager.initialise``) is
used when the station is already ``On``, and resets it to the
``Initialised`` state. It performs the following steps, in order:

1. Check that all subracks and tiles are already on; fail otherwise.

2. Set the tile source IPs (``_set_tile_source_ips``).

3. Set the global reference time (``_set_global_reference_time``).

4. Re-initialise the tiles (``_reinitialise_tiles``): send ``initialise()``
   to each Tile and wait for ``tileProgrammingState`` to reach
   ``Initialised``/``Synchronised`` for all tiles.

5. Initialise the tile parameters (``_initialise_tile_parameters``).

6. Initialise the station (``_initialise_station``).

7. Wait for the ARP table to be populated (``_wait_for_arp_table``).

8. Route data to the DAQ/CSP destinations (``_route_data``).

9. Check station synchronisation (``_check_station_synchronisation``).

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

The WhiteRabbit is responsible for ditribution of timing signals that keep the RPFs (remote processing facilities) synchronised with CPF (central processing facility).
Each SPS rack contains one EndNode, this distributes the 10MHz and 1PPS signal to the subracks via coax. 
The subrack then distributes this to the TPM that then synchronise their own clocks, again please 
see https://developer.skao.int/projects/ska-low-mccs-spshw/en/latest/reference/tile_brief_overview.html#synchronization-procedure.

Our spsstation ON and initialisation procedure is therefore gated by having good stable input timing.
we do this by observing the HealthState of the WREN. 

Our SpsStation device will have an optional DeviceProperty "WREN_TRL" (name TBC).
If this is supplied will wait on this signal before attempting synchronisation. 
The time we wait will be configurable, but as a ballpark figure it can take 5 mins 
to indicate it is OK if WR EN is powered up after WR GM. 
If powered up before it can take longer. 
We define a property "wait_time" (name TBC) that can be configured, 
if the healthState is not OK in that period we do not attempt initialisation and the command fails.

Concretely, in this prototype a single wait step is inserted at the very
start of each command, before anything is turned on or re-initialised:

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
