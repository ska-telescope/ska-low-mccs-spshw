# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests for TileTime."""
from datetime import datetime, timezone

import pytest

from ska_low_mccs_spshw.tile.tile_data import TileData
from ska_low_mccs_spshw.tile.tile_time import TileTime

RFC_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
REF_TIME = 1000


def _utc_string(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime(RFC_FORMAT)


@pytest.fixture(name="tile_time")
def tile_time_fixture() -> TileTime:
    """
    Fixture to create a TileTime with a fixed reference time.

    :return: a TileTime instance.
    """
    return TileTime(REF_TIME)


def test_frame_from_utc_time_sub_second_precision(tile_time: TileTime) -> None:
    """
    A utc_time a fraction of a second after ref_time must not be rounded up.

    :param tile_time: the TileTime fixture.
    """
    utc_time = _utc_string(REF_TIME + 0.0005)
    assert tile_time.frame_from_utc_time(utc_time) == 2


def test_frame_from_utc_time_before_ref_time(tile_time: TileTime) -> None:
    """
    A utc_time before ref_time must return exactly -1.

    :param tile_time: the TileTime fixture.
    """
    utc_time = _utc_string(REF_TIME - 500)
    assert tile_time.frame_from_utc_time(utc_time) == -1


def test_frame_from_utc_time_invalid_string(tile_time: TileTime) -> None:
    """
    An unparseable utc_time must return -1.

    :param tile_time: the TileTime fixture.
    """
    assert tile_time.frame_from_utc_time("wibble") == -1


def test_frame_from_utc_time_uninitialised() -> None:
    """A TileTime with no reference time set must return -1."""
    assert TileTime().frame_from_utc_time(_utc_string(REF_TIME)) == -1


def test_format_time_from_frame_sub_second_precision(tile_time: TileTime) -> None:
    """
    Formatting a frame count must preserve sub-second precision.

    :param tile_time: the TileTime fixture.
    """
    frame_count = 3
    expected_epoch = REF_TIME + TileData.FRAME_PERIOD * frame_count
    assert tile_time.format_time_from_frame(frame_count) == _utc_string(expected_epoch)


def test_round_trip_frame_and_format(tile_time: TileTime) -> None:
    """
    A utc_time formatted from a frame must map back to at least that frame.

    :param tile_time: the TileTime fixture.
    """
    frame_count = 100
    utc_time = tile_time.format_time_from_frame(frame_count)
    assert tile_time.frame_from_utc_time(utc_time) <= frame_count
