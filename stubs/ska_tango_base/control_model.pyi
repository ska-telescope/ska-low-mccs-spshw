# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
import enum

class HealthState(enum.IntEnum):
    OK = 0
    DEGRADED = 1
    FAILED = 2
    UNKNOWN = 3

class AdminMode(enum.IntEnum):
    ONLINE = 0
    OFFLINE = 1
    MAINTENANCE = 2
    NOT_FITTED = 3
    RESERVED = 4

class ObsState(enum.IntEnum):
    EMPTY = 0
    RESOURCING = 1
    IDLE = 2
    CONFIGURING = 3
    READY = 4
    SCANNING = 5
    ABORTING = 6
    ABORTED = 7
    RESETTING = 8
    FAULT = 9
    RESTARTING = 10

class ObsMode(enum.IntEnum):
    IDLE = 0
    IMAGING = 1
    PULSAR_SEARCH = 2
    PULSAR_TIMING = 3
    DYNAMIC_SPECTRUM = 4
    TRANSIENT_SEARCH = 5
    VLBI = 6
    CALIBRATION = 7

class ControlMode(enum.IntEnum):
    REMOTE = 0
    LOCAL = 1

class SimulationMode(enum.IntEnum):
    FALSE = 0
    TRUE = 1

class TestMode(enum.IntEnum):
    NONE = 0
    TEST = 1

class LoggingLevel(enum.IntEnum):
    OFF = 0
    FATAL = 1
    ERROR = 2
    WARNING = 3
    INFO = 4
    DEBUG = 5

class PowerState(enum.IntEnum):
    UNKNOWN = 0
    OFF = 1
    STANDBY = 2
    ON = 3
