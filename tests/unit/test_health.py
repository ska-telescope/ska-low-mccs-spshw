########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA ska-low-mccs project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
########################################################################
"""
This module contains the tests for the ska.low.mccs.health module
"""
import pytest

from tango import DevState
from tango import AttrQuality

from ska.base.control_model import HealthState
from ska.low.mccs.health import HealthMonitor, LocalHealthMonitor, HealthRollupPolicy

fqdns = ["low/elt/station_1", "low/elt/station_2"]
attrs = ["voltage", "current"]


class TestHealthMonitor:
    """
    This class contains the tests the default ska.low.mccs.health.HealthMonitor
    """

    def test_initialise_table(self):
        """
        Test the healthmonitor table initialisation
        """
        hm = HealthMonitor(fqdns, None)
        dct = hm.get_healthstate_table()
        assert dct == {
            "low/elt/station_1": {
                "State": DevState.UNKNOWN,
                "healthstate": HealthState.OK,
            },
            "low/elt/station_2": {
                "State": DevState.UNKNOWN,
                "healthstate": HealthState.OK,
            },
        }

    @pytest.fixture(
        params=[
            HealthState.DEGRADED,
            HealthState.FAILED,
            HealthState.UNKNOWN,
            HealthState.OK,
        ]
    )
    def test_update_health(self, request):
        hm = HealthMonitor(fqdns, None)
        hm.update_health_table(fqdns[0], "healthstate", request, AttrQuality.ATTR_VALID)
        dct = hm.get_healthstate_table()
        assert dct == {
            "low/elt/station_1": {
                "State": DevState.UNKNOWN,
                "healthstate": HealthState.OK,
            },
            "low/elt/station_2": {
                "State": DevState.UNKNOWN,
                "healthstate": HealthState.OK,
            },
        }

        hm.update_health_table(
            "low/elt/station_2", "healthstate", request, AttrQuality.ATTR_VALID
        )
        dct = hm.get_healthstate_table()
        assert dct == {
            "low/elt/station_1": {"State": DevState.UNKNOWN, "healthstate": request},
            "low/elt/station_2": {"State": DevState.UNKNOWN, "healthstate": request},
        }

    def test_health_with_rollup(self):
        rollup_policy = HealthRollupPolicy(None)
        hm = HealthMonitor(fqdns, rollup_policy.rollup_health)
        ret = hm.update_health_table(
            "low/elt/station_1",
            "healthstate",
            HealthState.DEGRADED,
            AttrQuality.ATTR_VALID,
        )
        assert ret == HealthState.DEGRADED
        ret = hm.update_health_table(
            "low/elt/station_2",
            "healthstate",
            HealthState.FAILED,
            AttrQuality.ATTR_VALID,
        )
        assert ret == HealthState.FAILED

    @pytest.fixture(
        params=[
            DevState.ON,
            DevState.OFF,
            DevState.CLOSE,
            DevState.OPEN,
            DevState.INSERT,
            DevState.EXTRACT,
            DevState.MOVING,
            DevState.STANDBY,
            DevState.FAULT,
            DevState.INIT,
            DevState.RUNNING,
            DevState.ALARM,
            DevState.DISABLE,
            DevState.UNKNOWN,
        ]
    )
    def test_update_state(self, request):
        hm = HealthMonitor(fqdns, None)
        hm.update_health_table(fqdns[0], "State", request, AttrQuality.ATTR_VALID)
        dct = hm.get_healthstate_table()
        assert dct == {
            "low/elt/station_1": {"State": request, "healthstate": HealthState.OK},
            "low/elt/station_2": {
                "State": DevState.UNKNOWN,
                "healthstate": HealthState.OK,
            },
        }

        hm.update_health_table(fqdns[1], "State", request, AttrQuality.ATTR_VALID)
        dct = hm.get_healthstate_table()
        assert dct == {
            "low/elt/station_1": {"State": request, "healthstate": HealthState.OK},
            "low/elt/station_2": {"State": request, "healthstate": HealthState.OK},
        }

    def test_state_with_rollup(self):
        rollup_policy = HealthRollupPolicy(None)
        hm = HealthMonitor(fqdns, rollup_policy.rollup_health)
        ret = hm.update_health_table(
            "low/elt/station_1", "State", DevState.ALARM, AttrQuality.ATTR_VALID
        )
        assert ret == HealthState.FAILED
        ret = hm.update_health_table(
            "low/elt/station_2", "State", DevState.FAULT, AttrQuality.ATTR_VALID
        )
        assert ret == HealthState.FAILED

    def test_local_health_monitor(self):
        hm = LocalHealthMonitor(fqdns, None, event_names=attrs)
        dct = hm.get_healthstate_table()
        assert dct == {
            "low/elt/station_1": {"voltage": HealthState.OK, "current": HealthState.OK},
            "low/elt/station_2": {"voltage": HealthState.OK, "current": HealthState.OK},
        }

    @pytest.fixture(
        params=[
            AttrQuality.ATTR_VALID,
            AttrQuality.ATTR_INVALID,
            AttrQuality.ATTR_ALARM,
            AttrQuality.ATTR_CHANGING,
            AttrQuality.ATTR_WARNING,
        ]
    )
    def test_update_local_table(self, request):
        hm = LocalHealthMonitor(fqdns, None, event_names=attrs)
        hm.update_health_table(fqdns[0], "voltage", 12.0, request)
        dct = hm.get_healthstate_table()
        expected_health = hm.quality_to_healthstate(request)
        assert dct == {
            "low/elt/station_1": {
                "voltage": expected_health,
                "current": HealthState.OK,
            },
            "low/elt/station_2": {"voltage": HealthState.OK, "current": HealthState.OK},
        }

        hm.update_health_table(fqdns[1], "voltage", 12.0, request)
        dct = hm.get_healthstate_table()
        assert dct == {
            "low/elt/station_1": {
                "voltage": expected_health,
                "current": HealthState.OK,
            },
            "low/elt/station_2": {
                "voltage": expected_health,
                "current": HealthState.OK,
            },
        }

        hm.update_health_table(fqdns[0], "current", 2.0, request)
        dct = hm.get_healthstate_table()
        assert dct == {
            "low/elt/station_1": {
                "voltage": expected_health,
                "current": expected_health,
            },
            "low/elt/station_2": {
                "voltage": expected_health,
                "current": HealthState.OK,
            },
        }

        hm.update_health_table(fqdns[1], "current", 2.0, request)
        dct = hm.get_healthstate_table()
        assert dct == {
            "low/elt/station_1": {
                "voltage": expected_health,
                "current": expected_health,
            },
            "low/elt/station_2": {
                "voltage": expected_health,
                "current": expected_health,
            },
        }
