#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains base data/facts about a tile."""


from __future__ import annotations  # allow forward references in type hints

import copy
import importlib.resources
from typing import Any

import yaml

__all__ = ["TileData"]


class TileData:
    """
    This class contain data/facts about a tile needed by multiple classes.

    For example the channelized sample and beamformer frame period, the
    number of antennas per tile. So rather than store this fact in
    separate places, we store it here.
    """

    CHANNELISER_OUTPUT_FRAME_LENGTH = 1024
    CHANNELISER_OVERSAMPLING_FACTOR = 32 / 27
    ADC_FRAME_LENGTH = CHANNELISER_OUTPUT_FRAME_LENGTH / CHANNELISER_OVERSAMPLING_FACTOR
    ADC_SAMPLING_FREQ = 800e6
    ADC_SAMPLING_PERIOD = 1 / ADC_SAMPLING_FREQ
    TOTAL_BANDWIDTH = ADC_SAMPLING_FREQ / 2
    SAMPLE_PERIOD = ADC_SAMPLING_PERIOD * ADC_FRAME_LENGTH
    FRAME_PERIOD = SAMPLE_PERIOD * 256
    CSP_FRAME_PERIOD = SAMPLE_PERIOD * 2048
    ANTENNA_COUNT = 16
    POLS_PER_ANTENNA = 2
    ADC_CHANNELS = ANTENNA_COUNT * POLS_PER_ANTENNA
    NUM_FREQUENCY_CHANNELS = 512
    NUM_BEAMFORMER_CHANNELS = 384
    FIRST_FREQUENCY_CHANNEL = 50e6
    CHANNEL_WIDTH = TOTAL_BANDWIDTH / NUM_FREQUENCY_CHANNELS
    FIRST_BEAMFORMER_CHANNEL: int = int(FIRST_FREQUENCY_CHANNEL / CHANNEL_WIDTH)
    BEAMFORMER_BANDWIDTH = NUM_BEAMFORMER_CHANNELS * CHANNEL_WIDTH
    NUM_FPGA = 2
    BEAMF_BIT_SHIFT = 4  # Hardcoded into the pattern generator, can only shift by 4.
    STATION_BEAM_DATA_RATE_PER_HZ = (
        CHANNELISER_OVERSAMPLING_FACTOR * 2 * 2
    )  # bytes / Hz (bandwidth) / s
    FULL_STATION_BEAM_DATA_RATE = (
        BEAMFORMER_BANDWIDTH * STATION_BEAM_DATA_RATE_PER_HZ
    )  # bytes / s

    min_max_string = importlib.resources.read_text(
        __package__, "tpm_monitoring_min_max.yaml"
    )
    MIN_MAX_MONITORING_POINTS = (
        yaml.load(min_max_string, Loader=yaml.Loader)["tpm_monitoring_points"] or {}
    )

    TILE_MONITORING_POINTS = {
        "temperatures": {"board": None, "FPGA0": None, "FPGA1": None},
        "voltages": {
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
            "VM_PLL": None,
            "VM_DDR1_VTT": None,
            "VM_DDR1_VDD": None,
            "VM_DVDD": None,
        },
        "currents": {"FE0_mVA": None, "FE1_mVA": None},
        "alarms": {
            "I2C_access_alm": 0,
            "temperature_alm": 0,
            "voltage_alm": 0,
            "SEM_wd": 0,
            "MCU_wd": 0,
        },
        "adcs": {
            "pll_status": {
                "ADC0": None,
                "ADC1": None,
                "ADC2": None,
                "ADC3": None,
                "ADC4": None,
                "ADC5": None,
                "ADC6": None,
                "ADC7": None,
                "ADC8": None,
                "ADC9": None,
                "ADC10": None,
                "ADC11": None,
                "ADC12": None,
                "ADC13": None,
                "ADC14": None,
                "ADC15": None,
            },
            "sysref_timing_requirements": {
                "ADC0": None,
                "ADC1": None,
                "ADC2": None,
                "ADC3": None,
                "ADC4": None,
                "ADC5": None,
                "ADC6": None,
                "ADC7": None,
                "ADC8": None,
                "ADC9": None,
                "ADC10": None,
                "ADC11": None,
                "ADC12": None,
                "ADC13": None,
                "ADC14": None,
                "ADC15": None,
            },
            "sysref_counter": {
                "ADC0": None,
                "ADC1": None,
                "ADC2": None,
                "ADC3": None,
                "ADC4": None,
                "ADC5": None,
                "ADC6": None,
                "ADC7": None,
                "ADC8": None,
                "ADC9": None,
                "ADC10": None,
                "ADC11": None,
                "ADC12": None,
                "ADC13": None,
                "ADC14": None,
                "ADC15": None,
            },
        },
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
            "pll": None,
        },
        "info": {
            "hardware": {
                "ip_address_eep": None,
                "netmask_eep": None,
                "gateway_eep": None,
                "SN": None,
                "PN": None,
                "bios": None,
                "BOARD_MODE": None,
                "LOCATION": None,
                "HARDWARE_REV": None,
                "DDR_SIZE_GB": None,
            },
            "fpga_firmware": {
                "design": None,
                "build": None,
                "version": None,
                "compile_time": None,
                "compile_user": None,
                "compile_host": None,
                "git_branch": None,
                "git_commit": None,
            },
            "network": {
                "1g_ip_address": None,
                "1g_mac_address": None,
                "1g_netmask": None,
                "1g_gateway": None,
                "40g_ip_address_p1": None,
                "40g_mac_address_p1": None,
                "40g_gateway_p1": None,
                "40g_netmask_p1": None,
                "40g_ip_address_p2": None,
                "40g_mac_address_p2": None,
                "40g_gateway_p2": None,
                "40g_netmask_p2": None,
            },
        },
        "io": {
            "jesd_interface": {
                "link_status": None,
                "lane_error_count": {
                    "FPGA0": {
                        "Core0": {
                            "lane0": None,
                            "lane1": None,
                            "lane2": None,
                            "lane3": None,
                            "lane4": None,
                            "lane5": None,
                            "lane6": None,
                            "lane7": None,
                        },
                        "Core1": {
                            "lane0": None,
                            "lane1": None,
                            "lane2": None,
                            "lane3": None,
                            "lane4": None,
                            "lane5": None,
                            "lane6": None,
                            "lane7": None,
                        },
                    },
                    "FPGA1": {
                        "Core0": {
                            "lane0": None,
                            "lane1": None,
                            "lane2": None,
                            "lane3": None,
                            "lane4": None,
                            "lane5": None,
                            "lane6": None,
                            "lane7": None,
                        },
                        "Core1": {
                            "lane0": None,
                            "lane1": None,
                            "lane2": None,
                            "lane3": None,
                            "lane4": None,
                            "lane5": None,
                            "lane6": None,
                            "lane7": None,
                        },
                    },
                },
                "lane_status": True,
                "resync_count": {"FPGA0": None, "FPGA1": None},
                "qpll_status": {"FPGA0": None, "FPGA1": None},
            },
            "ddr_interface": {
                "initialisation": None,
                "reset_counter": {"FPGA0": None, "FPGA1": None},
                # "rd_cnt": {"FPGA0": None, "FPGA1": None},
                # "wr_cnt": {"FPGA0": None, "FPGA1": None},
                # "rd_dat_cnt": {"FPGA0": None, "FPGA1": None},
            },
            "f2f_interface": {
                "pll_status": None,
                "soft_error": None,
                "hard_error": None,
            },
            "udp_interface": {
                "arp": None,
                "status": None,
                "linkup_loss_count": {"FPGA0": None, "FPGA1": None},
                "crc_error_count": {"FPGA0": None, "FPGA1": None},
                "bip_error_count": {
                    "FPGA0": {
                        "lane0": None,
                        "lane1": None,
                        "lane2": None,
                        "lane3": None,
                    },
                    "FPGA1": {
                        "lane0": None,
                        "lane1": None,
                        "lane2": None,
                        "lane3": None,
                    },
                },
                "decode_error_count": {
                    "FPGA0": {
                        "lane0": None,
                        "lane1": None,
                        "lane2": None,
                        "lane3": None,
                    },
                    "FPGA1": {
                        "lane0": None,
                        "lane1": None,
                        "lane2": None,
                        "lane3": None,
                    },
                },
            },
            "data_router": {
                "status": {
                    "FPGA0": 0,
                    "FPGA1": 0,
                },
                "discarded_packets": {
                    "FPGA0": [0, 0],
                    "FPGA1": [0, 0],
                },
            },
        },
        "dsp": {
            "tile_beamf": None,
            "station_beamf": {
                "status": None,
                "ddr_parity_error_count": {
                    "FPGA0": 0,
                    "FPGA1": 0,
                },
                "discarded_or_flagged_packet_count": {
                    "FPGA0": 0,
                    "FPGA1": 0,
                },
            },
        },
    }

    _TILE_DEFAULTS = None

    @classmethod
    def get_tile_defaults(cls) -> dict[str, Any]:
        """
        Get the defaults for tile monitoring points.

        If these have not been computed, compute them first.

        :return: the defaults for tile monitoring points.
        """
        if cls._TILE_DEFAULTS is None:
            cls._TILE_DEFAULTS = cls.generate_tile_defaults()
        return cls._TILE_DEFAULTS

    @classmethod
    def generate_tile_defaults(cls) -> dict[str, Any]:
        """
        Compute the default values for tile monitoring points.

        These are computed to be halfway between the minimum and maximum values.
        In cases where there is a permitted value instead, the permitted value is used

        :return: the default values for tile monitoring points
        """
        tile_structure = copy.deepcopy(cls.TILE_MONITORING_POINTS)
        expected_values = copy.deepcopy(cls.MIN_MAX_MONITORING_POINTS)
        return cls._generate_tile_defaults(tile_structure, expected_values)

    @classmethod
    def _generate_tile_defaults(
        cls, tile_structure: dict, expected_values: dict
    ) -> dict:
        for p in tile_structure:
            if isinstance(tile_structure[p], dict):
                tile_structure[p] = cls._generate_tile_defaults(
                    tile_structure[p], expected_values[p]
                )
            else:
                if isinstance(expected_values[p], dict):
                    if p == "voltage_alm":
                        # The value being generated for
                        # voltage_alm is 0.5 following mccs-1530 prompted by an
                        # issue in bios tracked by SPRTS-141. The value of 0.5 is
                        # not valid for this monitoring point. Here we are patching
                        # a valid default of 0 (int). This is a bit smelly, but it
                        # seemed better to pollute the `_generate_tile_defaults` used
                        # by only the simulator than the tpm_monitoring_min_max.yaml
                        # shared by both the health rules and the simulator.
                        tile_structure[p] = 0
                    else:
                        tile_structure[p] = round(
                            (expected_values[p]["min"] + expected_values[p]["max"]) / 2,
                            3,
                        )
                else:
                    tile_structure[p] = expected_values[p]
        return tile_structure
