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

On the SAT platform, Tile timing synchronisation is provided by a
WhiteRabbit reference clock, distributed through a WREN device. In this
prototype, the automatic Tile initialisation that normally happens as
part of turning a Tile on is deferred: ``MccsTile`` no longer initialises
itself automatically when powered on. Instead, ``SpsStation`` powers on
the subrack and its ports as before, then waits for the WREN
``healthState`` to report ``OK`` (or for a timeout to elapse) before it
explicitly triggers Tile initialisation and continues the existing
workflow.

Concretely, this splits the ``On`` sequence into three parts:

1. ``_turn_on_without_automatic_initialisation``: turn on the subrack and
   its ports, and bring the Tiles up to a powered, but not yet
   initialised, state.

2. Wait for the WREN ``healthState`` to become ``HealthState.OK``, or for a
   configured timeout to expire.

3. Initialise the TPMs, then continue with the pre-existing workflow
   (``_initialise_tile_parameters``, ``_initialise_station``,
   ``_wait_for_arp_table``, ``_route_data``,
   ``_check_station_synchronisation``).

The ``Initialise`` sequence is changed more simply: a wait for the WREN
``healthState`` to reach ``HealthState.OK`` (or timeout) is inserted
immediately before the existing ``_reinitialise_tiles`` step, and the
remainder of the sequence is unchanged.

The sequence diagram below shows both commands with this new WhiteRabbit
wait step:

.. uml:: sat_wren_prototype_sequence.uml
