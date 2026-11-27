#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""The text of the reasons and remedies in the SpsStation healthReport."""
from __future__ import annotations

from enum import Enum

__all__ = ["HealthDetailText"]


class HealthDetailText(str, Enum):
    """
    The text of the reasons and remedies in healthReport.

    Values in braces are filled in with ``str.format``.
    """

    # A source is not OK, and gives no reason of its own.
    GENERIC_REASON = "{source} is {state}"

    # The PPS delay spread ("self") is not OK.
    PPS_REASON = (
        "ppsDelaySpread is {spread} (DEGRADED at >= {degraded}, FAILED at > "
        "{failed}). PPS delays of Synchronised tiles, by logical tile id: "
        "{delays}"
    )
    PPS_REMEDY = (
        "Find the tiles whose PPS delay is furthest from the others, and "
        "check the PPS and timing distribution to them (see "
        "ppsPresentSummary). If their offset is expected and stable, "
        "compensate it with ppsDelayCorrections, which take effect at the "
        "next Initialise."
    )

    # The tiles are not all Off or all Synchronised.
    TILE_PROGRAMMING_STATE_REASON = (
        "Tiles should be all Off or all Synchronised. Logical tile ids by "
        "programming state: {tiles_by_state}"
    )
    TILE_PROGRAMMING_STATE_REMEDY = (
        "Mixed states are expected while the station is powering on or "
        "initialising. If they persist, Initialise the station to bring all "
        "tiles to Synchronised. A tile in state Unknown is not reporting: "
        "check that its device is running and communicating."
    )

    # The station is not evaluating its health.
    OFFLINE_REASON = (
        "SpsStation adminMode is {admin_mode}, so its health is not "
        "evaluated and every health source is UNKNOWN."
    )
    OFFLINE_REMEDY = "Set the SpsStation adminMode to ONLINE or ENGINEERING."

    # A health source has not reported since the station came online.
    AWAITING_REASON = (
        "No health update received since the station came online at {since}."
    )
    AWAITING_PPS_REMEDY = (
        "ppsDelaySpread is computed from the timing_pps_delay of the "
        "Synchronised tiles. Check that the tiles are ON, communicating "
        "and Synchronised."
    )
    AWAITING_TILE_PROGRAMMING_STATE_REMEDY = (
        "Check that the station is communicating with its tiles: it needs "
        "their tileProgrammingState."
    )
    AWAITING_DAISY_CHAIN_REMEDY = (
        "Check that the tiles are ON and communicating, and that their "
        "adminMode, tileProgrammingState, fortyGbCoreConfigurations and "
        "fortyGPacketCount can be read."
    )
    AWAITING_TILE_DATA_ROUTING_REMEDY = (
        "Check that the last tile is ON and communicating, and that its "
        "fortyGbCoreConfigurations can be read."
    )
    AWAITING_FLAGGED_COUNT_REMEDY = (
        "Check that the final tile is ON and communicating, and that its "
        "dsp_station_beamf_discarded_or_flagged_packet_count_fpga0 and "
        "_fpga1 can be read."
    )
    AWAITING_DEVICE_REMEDY = (
        "Check that {device} is running and reachable, and that its "
        "adminMode is ONLINE or ENGINEERING: the station ignores its "
        "health in any other adminMode."
    )

    # WREN is not OK. Its own reason, from its healthInfo, replaces the
    # generic one where it gives one.
    WREN_REASON = "WREN {device} reports its health as {state}."
    WREN_UNKNOWN_REASON = "No health state received from WREN {device} yet."
    WREN_REMEDY = (
        "Check {device} directly: its state, healthState, healthInfo and "
        "logs. The station's timing depends on it, so check ppsDelaySpread "
        "and the tiles' PPS too."
    )
    WREN_AWAITING_REMEDY = (
        "Check that {device} is running and reachable, and that it can "
        "reach its White Rabbit switch or node over SNMP: see its Host, "
        "Port and community properties."
    )

    # The beamformer daisy chain is checked in stages.
    # Stage: every tile is ON.
    DAISY_CHAIN_TILES_NOT_ON_REASON = (
        "Beamformer daisy chain is broken: not every tile is ON."
    )
    DAISY_CHAIN_TILES_NOT_ON_REMEDY = (
        "Turn on the tiles, e.g. by turning the station On. If a tile does "
        "not turn on, check its subrack, and the tile's healthReport."
    )
    # Stage: every tile is ONLINE or ENGINEERING.
    DAISY_CHAIN_TILES_NOT_ONLINE_REASON = (
        "Beamformer daisy chain is broken: not every tile is ONLINE or ENGINEERING."
    )
    DAISY_CHAIN_TILES_NOT_ONLINE_REMEDY = (
        "Set the adminMode of every tile to ONLINE. If a tile's adminMode "
        "cannot be read, check that the tile device is running and reachable."
    )
    # Stage: every tile is initialised.
    DAISY_CHAIN_TILES_NOT_INITIALISED_REASON = (
        "Beamformer daisy chain is broken: not every tile is Initialised or "
        "Synchronised."
    )
    DAISY_CHAIN_TILES_NOT_INITIALISED_REMEDY = (
        "Initialise the station. If a tile does not reach Initialised, check "
        "its tileProgrammingState and healthReport."
    )
    # Stage: every tile but the last sends its beamformer output to the next.
    DAISY_CHAIN_IPS_WRONG_REASON = (
        "Beamformer daisy chain is broken: a tile does not send its "
        "beamformer output to the next tile."
    )
    DAISY_CHAIN_IPS_UNKNOWN_REASON = (
        "Beamformer daisy chain cannot be verified: a tile has not reported "
        "its beamformer destination IPs."
    )
    DAISY_CHAIN_IPS_REMEDY = (
        "Initialise the station, which sets every tile's beamformer "
        "destination IPs. If they are wrong, the station logs which tile, "
        "and the IPs it expected: check the SdnFirstInterface device "
        "property, and whether the tile's 40G destination was changed by "
        "hand. If they are not reported, check that every tile's "
        "fortyGbCoreConfigurations can be read."
    )
    # Stage: while beamforming, every tile but the first receives data from
    # the previous tile.
    DAISY_CHAIN_NOT_RECEIVING_REASON = (
        "Beamformer daisy chain is broken: while beamforming, a tile is not "
        "receiving data from the previous tile."
    )
    DAISY_CHAIN_NOT_RECEIVING_REMEDY = (
        "Check every tile's fortyGPacketCount: each tile but the first should "
        "be receiving (rx_received), and the tile before it sending "
        "(tx_transmitted). If so, check the 40G links between the tiles."
    )

    # The station beam is routed from the last tile to CSP ingest. This is
    # only checked once CSP ingest is configured.
    TILE_DATA_ROUTING_WRONG_REASON = (
        "Station beam is not routed to CSP ingest: the last tile does not "
        "send its beamformer output to the CSP ingest address and port."
    )
    TILE_DATA_ROUTING_WRONG_REMEDY = (
        "Run SetCspIngest again, with the last tile ON, which sets the last "
        "tile's routes. The station logs which core and ARP table entry is "
        "wrong, and the route it expected. If the error returns, check "
        "whether the last tile's 40G destination was changed by hand."
    )
    TILE_DATA_ROUTING_UNKNOWN_REASON = (
        "Station beam routing to CSP ingest cannot be verified: the last "
        "tile has not reported its fortyGbCoreConfigurations."
    )
    TILE_DATA_ROUTING_UNKNOWN_REMEDY = (
        "Check that the last tile is communicating, and that its "
        "fortyGbCoreConfigurations can be read: the station checks the "
        "routes they report."
    )

    # The final tile's beamformer discarded or flagged packet count is not OK.
    FLAGGED_COUNT_NON_ZERO_REASON = (
        "Final tile (logical tile id {tile_id}) has a non-zero "
        "dsp_station_beamf_discarded_or_flagged_packet_count on {fpgas}"
    )
    FLAGGED_COUNT_NON_ZERO_REMEDY = (
        "The station beamformer is discarding or flagging packets (e.g. "
        "parity errors). Check the beamformer_daisy_chain and "
        "tile_programming_state health first, then compare the same counts "
        "on the other tiles to find where in the chain the errors start."
    )
    FLAGGED_COUNT_INVALID_REASON = (
        "Final tile (logical tile id {tile_id}) has an INVALID "
        "dsp_station_beamf_discarded_or_flagged_packet_count on {fpgas}"
    )
    FLAGGED_COUNT_INVALID_REMEDY = (
        "The count cannot be read. Check that the final tile is ON and "
        "communicating."
    )

    # A tile or subrack ({device_type}) is not OK. The reason is its own
    # healthReport; the remedy depends on what that says.
    SUB_DEVICE_NO_REPORT_REMEDY = (
        "The {device_type} has not given a reason. Read its healthState and "
        "healthReport directly, and check its logs. A {device_type} using the "
        "old health model (UseAttributesForHealth False) does not publish "
        "its healthReport."
    )
    SUB_DEVICE_OUT_OF_LIMITS_REMEDY = (
        "The {device_type}'s own health checks raised this: the attributes "
        "named are outside the limits in their attribute configuration. Read "
        "them for their current values, and check the {device_type}'s logs."
    )
    SUB_DEVICE_UNREADABLE_REMEDY = (
        "The {device_type} cannot read the attributes its health depends on. "
        "Check that the {device_type} is ON and communicating with its "
        "hardware, and check its logs."
    )
    SUB_DEVICE_RULES_REMEDY = (
        "The {device_type}'s health rules raised this. Investigate what the "
        "reason names on the {device_type}, and check its logs."
    )
