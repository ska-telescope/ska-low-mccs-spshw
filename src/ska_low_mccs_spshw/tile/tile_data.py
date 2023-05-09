#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains base data/facts about a tile."""


from __future__ import annotations  # allow forward references in type hints

import importlib.resources
import yaml

__all__ = ["TileData"]


# pylint: disable=too-few-public-methods
class TileData:
    """
    This class contain data/facts about a tile needed by multiple classes.

    For example the channelized sample and beamformer frame period, the
    number of antennas per tile. So rather than store this fact in
    separate places, we store it here.
    """

    SAMPLE_PERIOD = 1.08e-6
    FRAME_PERIOD = 1.08e-6 * 256
    CSP_FRAME_PERIOD = 1.08e-6 * 2048
    ANTENNA_COUNT = 16
    NUM_FREQUENCY_CHANNELS = 512
    NUM_BEAMFORMER_CHANNELS = 384

    min_max_string = importlib.resources.read_text(
        __package__, "tpm_monitoring_min_max.yaml"
    )
    MIN_MAX_MONITORING_POINTS = yaml.load(min_max_string, Loader=yaml.Loader) or {}

    TILE_MONITORING_POINTS = {
        "temperature": {"board": None, "FPGA0": None, "FPGA1": None},
        "voltage": {
            "VREF_2V5": None,
            "MGT_AVCC": None,
            "VM_SW_AMP": None,
            "MGT_AVTT": None,
            "SW_AVDD1": None,
            "SW_AVDD2": None,
            "AVDD3": None,
            "MAN_1V2": None,
            "DDR0_VREF": None,
            "DDR1_VREF": None,
            "VM_DRVDD": None,
            "VIN": None,
            "MON_3V3": None,
            "MON_1V8": None,
            "MON_5V0": None,
            "VM_FE0": None,
            "VM_FE1": None,
            "VM_DDR0_VTT": None,
            "VM_AGP0": None,
            "VM_AGP1": None,
            "VM_AGP2": None,
            "VM_AGP3": None,
            "VM_AGP4": None,
            "VM_AGP5": None,
            "VM_AGP6": None,
            "VM_AGP7": None,
            "VM_CLK0B": None,
            "VM_CLK1B": None,
            "VM_MGT0_AUX": None,
            "VM_MGT1_AUX": None,
            "VM_ADA0": None,
            "VM_ADA1": None,
            "VM_PLL": None,
            "VM_DDR1_VTT": None,
            "VM_DDR1_VDD": None,
            "VM_DVDD": None,
        },
        "current": {"FE0_mVA": None, "FE1_mVA": None},
        "timing": {
            "clocks": {
                "FPGA0": {"JESD": None, "DDR": None, "UDP": None},
                "FPGA1": {"JESD": None, "DDR": None, "UDP": None},
            },
            "clock_managers": {
                "FPGA0": {"C2C_MMCM": None, "JESD_MMCM": None, "DSP_MMCM": None},
                "FPGA1": {"C2C_MMCM": None, "JESD_MMCM": None, "DSP_MMCM": None},
            },
            "pps": {"status": None},
        },
        "io": {
            "jesd_if": {
                "lanes": None,
                "error_count": None,
                "resync_count": {"FPGA0": None, "FPGA1": None},
                "qpll_lock_loss_count": {"FPGA0": None, "FPGA1": None},
            },
            "ddr_if": {
                "initialisation": None,
                "reset_counter": {"FPGA0": None, "FPGA1": None},
            },
            "f2f_if": {"pll_lock_loss_count": {"Core0": None}},
            "udp_if": {
                "arp": None,
                "status": None,
                "linkup_loss_count": {"FPGA0": None, "FPGA1": None},
            },
        },
        "dsp": {"tile_beamf": None, "station_beamf": None},
    }
