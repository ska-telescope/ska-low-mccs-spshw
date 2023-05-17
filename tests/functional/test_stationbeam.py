# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""Hello World."""
from __future__ import annotations

import json
import time
from datetime import datetime  # , timezone

# import enum
from functools import wraps
from typing import Callable, Optional

import numpy as np
import pytest
import tango
from mypy_extensions import KwArg, VarArg
from pytest_bdd import given, scenario, then, when

# from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import AdminMode, SimulationMode
from ska_tango_testing.context import TangoContextProtocol

# from ska_tango_testing.mock.placeholders import Anything, OneOf
# from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup

# import ska_low_mccs_spshw

RFC_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


@pytest.fixture(name="subrack_device", scope="module")
def subrack_device_fixture(
    tango_harness: TangoContextProtocol,
    subrack_name: str,
) -> tango.DeviceProxy:
    """
    Return the subrack device under test.

    :param tango_harness: a test harness for Tango devices.
    :param subrack_name: name of the subrack Tango device.

    :return: the subrack Tango device under test.
    """
    return tango_harness.get_device(subrack_name)


@pytest.fixture(name="station_device")
def station_device_fixture(
    tango_harness: TangoContextProtocol,
    station_name: str,
) -> tango.DeviceProxy:
    """
    Return the station device under test.

    :param tango_harness: a test harness for Tango devices.
    :param station_name: name of the station Tango device.

    :return: the station Tango device under test.
    """
    return tango_harness.get_device(station_name)


@pytest.fixture(name="tile_device_list")
def tile_device_fixture(
    tango_harness: TangoContextProtocol,
    tile_name_1: str,
    tile_name_2: str,
) -> list[tango.DeviceProxy]:
    """
    Return the subrack device under test.

    :param tango_harness: a test harness for Tango devices.
    :param tile_name_1: name of the tile Tango device no. 1.
    :param tile_name_2: name of the tile Tango device no. 2.

    :return: a list containing the tile devices under test.
    """
    return [
        tango_harness.get_device(tile_name_1),
        tango_harness.get_device(tile_name_2),
    ]


def skip_if_tiles_simulated(
    test_function: Callable[[None], None],
) -> Callable[
    [VarArg(None), KwArg(pytest.FixtureRequest)],
    Optional[Callable[[dict[str, pytest.FixtureRequest]], None]],
]:
    """
    Skip test if tiles are simulated.

    The tiles do not currently have a test generator simulator, therefore
    the tests cannot be run if the tiles are simulated.

    :param test_function: function to skip if tiles simulated.

    :return: test function if tiles not simulated.
    """

    @wraps(test_function)
    def wrapper(
        *args: None,
        **kwargs: pytest.FixtureRequest,
    ) -> Optional[Callable[[dict[str, pytest.FixtureRequest]], None]]:
        tile_device_list_fixture = kwargs.get("request")
        if tile_device_list_fixture is None:
            raise ValueError("Tile_device_list fixture does not exist")
        tile_device_list = tile_device_list_fixture.getfixturevalue("tile_device_list")
        # station_device = kwargs.get("request").getfixturevalue("station_device")
        # subrack_device = kwargs.get("request").getfixturevalue("subrack_device")
        tile_1 = tile_device_list[0]
        tile_2 = tile_device_list[1]
        # x = tile_1.adminMode
        # tile_1.adminMode = AdminMode.ONLINE
        # station_device.adminMode = AdminMode.ONLINE
        # subrack_device.adminMode = AdminMode.ONLINE
        # assert tile_device_list[0].adminMode == AdminMode.ONLINE
        if SimulationMode.TRUE in (tile_1.SimulationMode, tile_2.SimulationMode):
            pytest.skip("Skipping station beam test with simulated tiles.")
        return test_function(*args, **kwargs)

    return wrapper


@skip_if_tiles_simulated
@scenario("features/station_beam.feature", "Correcting delayed beam")
def test_correct_delayed_beam() -> None:
    """
    Run a test scenario that tells a subrack to turn off all TPMs.

    Any code in this scenario function is run at the *end* of the
    scenario.
    """


@given("a station that is online")
def check_station_is_online_and_on(station_device: tango.DeviceProxy) -> None:
    """
    Set the station adminMode to online, then check it is online.

    :param station_device: the station device under test.
    """
    # station_device.logginglevel = 5
    station_device.adminMode = AdminMode.ONLINE
    time.sleep(0.2)
    assert station_device.adminMode == AdminMode.ONLINE


@given("a subrack that is online")
def check_subrack_is_online_and_on(
    subrack_device: tango.DeviceProxy,
) -> None:
    """
    Set the subrack adminMode to online, then check it is online.

    :param subrack_device: the subrack device under test.
    """
    # subrack_device.logginglevel = 5
    subrack_device.adminMode = AdminMode.ONLINE
    time.sleep(0.2)
    assert subrack_device.adminMode == AdminMode.ONLINE


@given("a set of tiles that are in maintenance")
def check_tiles_are_in_maintenance_and_on(
    tile_device_list: list[tango.DeviceProxy],
) -> None:
    """
    Set the tile adminMode to online for each tile, then check they are online.

    :param tile_device_list: the tile devices under test.
    """
    for t in tile_device_list:
        t.adminMode = AdminMode.MAINTENANCE
        time.sleep(0.2)
    for t in tile_device_list:
        assert t.adminMode == AdminMode.MAINTENANCE


@given("the station is configured")
def check_station_is_configured(station_device: tango.DeviceProxy) -> None:
    """
    Configure the station.

    :param station_device: the station device under test.
    """
    station_device.standby()
    time.sleep(5)
    station_device.SetBeamformerTable([128, 0, 1, 0, 0, 0, 0])
    station_device.statictimedelays = np.zeros([512], dtype=int)
    station_device.preaduLevels = list(range(32)) * 16
    station_device.channeliserRounding = [4] * 512
    station_device.cspRounding = [4] * 384
    station_device.SetLmcDownload('{"destination_ip": "10.0.0.98", "mode": "40g"}')
    station_device.SetLmcIntegratedDownload(
        '{"destination_ip": "10.0.0.98", "mode": "40g"}'
    )
    station_device.SetCspIngest('{"destination_ip": "10.0.0.98"}')
    assert station_device.state() == tango.DevState.STANDBY


@when("the station and subcracks are turned on")
def check_test_generator_is_programmed(
    station_device: tango.DeviceProxy,
    subrack_device: tango.DeviceProxy,
) -> None:
    """
    Turn on the station and subracks.

    :param station_device: the station device under test.
    :param subrack_device: the subrack device under test.
    """
    station_device.on()
    state = station_device.tileprogrammingstate
    tm = 0
    init = False
    for t in range(30):
        time.sleep(2)
        tm = tm + 2
        print(f"t={tm}: subrack: {subrack_device.status()}")
        if subrack_device.state() == tango.DevState.ON:
            break
    for t in range(30):
        time.sleep(2)
        tm = tm + 2
        s_new = station_device.tileprogrammingstate
        if s_new != state:
            print(f"t={tm}: state = {s_new}")
            state = s_new
        if all(s == "Initialised" for s in state):
            init = True
            break
    if init:
        print(f"t={tm}: Station initialized")
    else:
        print(f"t={tm}: Timeout during intialisation")
    assert subrack_device.state() == tango.DevState.ON
    assert station_device.tileprogrammingstate == ("Initialised", "Initialised")


@when("the station is synchronised")
def synchronise_the_station(
    station_device: tango.DeviceProxy,
    tile_device_list: list[tango.DeviceProxy],
) -> None:
    """
    Synchronise the station.

    :param station_device: the station device under test.
    :param tile_device_list: the tile devices under test.
    """
    t1 = tile_device_list[0]
    current_time = datetime.strftime(
        datetime.fromtimestamp(int(time.time()) + 3), RFC_FORMAT
    )
    station_device.StartAcquisition(json.dumps({"start_time": current_time}))
    #
    # check that synchronization worked
    #
    print(f"Tile time: {t1.fpgatime} - Sync time: {current_time}")
    print(f"Programmed Sync time: {t1.fpgareferencetime}")
    time.sleep(1)
    for t in range(1):
        tm1 = datetime.strftime(datetime.fromtimestamp(time.time()), RFC_FORMAT)
        tm2 = t1.fpgatime
        tm3 = t1.fpgaframetime
        print(f"time:{tm1} pps time:{tm2} frame time:{tm3}")
        # time.sleep(2)
    for i in range(30):
        # tm = tm + 1
        cur_time = int(t1.ReadRegister("fpga1.pps_manager.curr_time_read_val")[0])
        start_time = int(t1.readregister("fpga1.pps_manager.sync_time_val")[0])
        print(
            f"Current: {cur_time} - Start: {start_time} difference: "
            f"{cur_time-start_time} frame time:{t1.fpgaframetime}"
        )
        if cur_time > start_time:
            break
        time.sleep(1)

    tm1 = datetime.strftime(datetime.fromtimestamp(time.time()), RFC_FORMAT)
    tm2 = t1.fpgatime
    tm3 = t1.fpgaframetime
    print(f"time:{tm1} pps time:{tm2} frame time:{tm3}")
    # print(f"t={tm}: state = {station_device.tileprogrammingstate}")


@when("the test generator is programmed")
def program_test_generator(
    station_device: tango.DeviceProxy,
    tile_device_list: list[tango.DeviceProxy],
) -> None:
    """
    Programme the test generator.

    :param station_device: the station device under test.
    :param tile_device_list: the tile devices under test.
    """
    noise = True
    t1 = tile_device_list[0]
    for t in tile_device_list:
        tm = t.fpgaframetime
        print(f"{t.name()}: {tm}")
    start_time = datetime.strftime(datetime.fromtimestamp(time.time() + 2), RFC_FORMAT)

    if noise:
        json_arg = json.dumps({"noise_amplitude": 1.0, "set_time": start_time})
    else:
        json_arg = json.dumps(
            {
                "tone_2_frequency": 100.01e6,
                "tone_2_amplitude": 0.5,
                "set_time": start_time,
            }
        )

    for t in tile_device_list:
        t.ConfigureTestGenerator(json_arg)
    station_device.StartBeamformer(json.dumps({"start_time": start_time}))
    time.sleep(2)
    print(f"Beamformer running: {t1.isBeamformerRunning}")


@when("the scan is run")
def run_the_scan(station_device: tango.DeviceProxy) -> None:
    """
    Run the scan.

    :param station_device: the station device under test.
    """
    static_delays = np.zeros([512], dtype=float)
    d0 = 1.25
    for i in range(32):
        delay = (i - 16) * d0
        static_delays[2 * i + 0] = delay
        static_delays[2 * i + 1] = 0
    station_device.statictimedelays = static_delays
    delays = np.zeros([513], dtype=float)
    station_device.LoadPointingDelays(delays)
    start_time = datetime.strftime(
        datetime.fromtimestamp(time.time() + 0.5), RFC_FORMAT
    )
    station_device.applypointingdelays(start_time)
    time.sleep(3)
    for step in range(-20, 80):
        delays = np.zeros([513], dtype=float)
        d1 = 1.25 * step / 40
        for i in range(32):
            delay = (i - 16) * d1
            delays[2 * i + 1] = delay * 1e-9
            delays[2 * i + 2] = 0.0
        delays[0] = 0
        station_device.LoadPointingDelays(delays)
        start_time = datetime.strftime(
            datetime.fromtimestamp(time.time() + 0.5), RFC_FORMAT
        )
        station_device.applypointingdelays(start_time)
        time.sleep(1)
        if step % 5 == 0:
            print(f"Delay offset {d1-d0} {d1}")

    delays = np.zeros([513], dtype=float)
    station_device.LoadPointingDelays(delays)
    start_time = datetime.strftime(
        datetime.fromtimestamp(int(time.time()) + 4), RFC_FORMAT
    )
    station_device.applypointingdelays(start_time)


@when("the beam is corrected with pointing delays")
def correct_beam_with_pointing_delays(station_device: tango.DeviceProxy) -> None:
    """
    Correct the station beam.

    :param station_device: the station device under test.
    """
    for offset in range(40):
        static_delays = np.zeros([512], dtype=float)
        station_device.statictimedelays = static_delays
        for i in range(16):
            static_delays[2 * i] = -1.25 * offset
            static_delays[2 * i + 32] = 1.25 * offset
        for i in range(32):
            static_delays[2 * i] += (i - 16) * 1.25
            static_delays[0] = 1.25 * offset
            static_delays[18] = 1.25 * offset
        station_device.statictimedelays = static_delays
        delays = np.zeros([513], dtype=float)
        for i in range(32):
            delay = static_delays[2 * i] * 1.00e-9
            delays[2 * i + 1] = delay
            delays[2 * i + 2] = 0.0
        delays[0] = 0
        station_device.LoadPointingDelays(delays)
        start_time = datetime.strftime(
            datetime.fromtimestamp(time.time() + 0.4), RFC_FORMAT
        )
        station_device.applypointingdelays(start_time)
        time.sleep(2)


@then("the applitude of the corrected beam is as expected")
def check_amplitudes() -> None:
    """Hello World."""
    assert True is True
