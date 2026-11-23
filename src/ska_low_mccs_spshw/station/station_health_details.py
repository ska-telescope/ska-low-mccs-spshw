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
        "dstip40gfpga1 and dstip40gfpga2 can be read."
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

    # The beamformer daisy chain cannot be verified: a tile has not reported
    # its destination IPs.
    DAISY_CHAIN_MISSING_REASON = (
        "Tile {tile_id} has not reported its beamformer destination IPs: "
        "got ({ip1!r}, {ip2!r})"
    )
    DAISY_CHAIN_MISSING_REMEDY = (
        "Check that tile {tile_id} is ON and communicating, and that its "
        "dstip40gfpga1 and dstip40gfpga2 can be read. If they are empty, "
        "Initialise the station to configure the tiles' 40G ports."
    )
    # The beamformer daisy chain is broken: a tile sends to the wrong IPs.
    DAISY_CHAIN_WRONG_REASON = (
        "Tile {tile_id} has incorrect beamformer destination IPs: "
        "Expected ({expected_ip1}, {expected_ip2}), got ({ip1}, {ip2})"
    )
    DAISY_CHAIN_WRONG_REMEDY = (
        "Initialise the station, which sets every tile's beamformer "
        "destination IPs. If the error returns, check the SdnFirstInterface "
        "device property, and whether the tile's 40G destination was "
        "changed by hand."
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
