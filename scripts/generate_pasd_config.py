# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
This script generates a YAML file that specifies a PaSD configuraton;
that is, what antennas are plugged into what ports of what smartboxes,
and what smartboxes are plugged into what ports of the FNDH.

The generated config file can be copied to 
src/ska_low_mccs/pasd/pasd_configuration.yaml, in which case the PaSD
simulator / driver / tests, etc., will use this configuration.

This static configuration is a short-term measure. In the long run we
will need to dynamically pull the configuration from a configuration
manager.

Usage::

> python3 generate_pasd_config.py configuration.yaml

Note that this script randomly plugs antennas into smartbox ports, and
smartboxes into FNDH ports, so each time you run this script you will
get a different configuration.
"""
from __future__ import annotations
import random

import argparse
import yaml

NUMBER_OF_ANTENNAS_PER_STATION = 256
NUMBER_OF_SMARTBOXES_PER_STATION = 24
NUMBER_OF_ANTENNA_PORTS_PER_SMARTBOX = 12
NUMBER_OF_SMARTBOX_PORTS_PER_FNDH = 28
NUMBER_OF_TPMS_PER_STATION = 16
NUMBER_OF_INPUTS_PER_TPM = 16

# NUMBER_OF_STATIONS should be 512,
# but by the time we need more than 3,
# we'll have a better approach to configuration management
# than this silly script.
NUMBER_OF_STATIONS = 3


def get_smartbox_config_for_station() -> list[dict]:
    """
    Return a list of smartbox config specs, one for each smartbox. Each
    smartbox config spec indicates what FNDH port the corresponding
    smartbox is plugged into.

    :return: a list of smartbox config specs, one for each smartbox.
    """
    population = range(1, NUMBER_OF_SMARTBOX_PORTS_PER_FNDH+1)
    sample = random.sample(population, k=NUMBER_OF_SMARTBOXES_PER_STATION)
    return [{"smartbox_id": index+1, "fndh_port": port} for index, port in enumerate(sample)]


def get_antenna_config_for_station(station_id) -> list[dict]:
    """
    Return a list of antenna config specs, one for each antenna. Each
    smartbox config spec indicates which port of which smartbox the
    antenna is plugged into.
    """
    smartbox_port_population = [(port, smartbox) for port in range(1, NUMBER_OF_ANTENNA_PORTS_PER_SMARTBOX+1) for smartbox in range(1, NUMBER_OF_SMARTBOXES_PER_STATION+1)]
    smartbox_port_sample = random.sample(smartbox_port_population, k=NUMBER_OF_ANTENNAS_PER_STATION)

    tpm_input_population = [((station_id-1)*NUMBER_OF_TPMS_PER_STATION + tpm_offset,  tpm_input) for tpm_input in range(1, NUMBER_OF_INPUTS_PER_TPM+1) for tpm_offset in range(1, NUMBER_OF_TPMS_PER_STATION+1)]
    tpm_input_sample = random.sample(tpm_input_population, k=NUMBER_OF_ANTENNAS_PER_STATION)

    return [{"antenna_id": index+1, "smartbox_port": port, "smartbox_id": smartbox, "tpm_id": tpm_id, "tpm_input": tpm_input} for index, ((port, smartbox), (tpm_id, tpm_input)) in enumerate(zip(smartbox_port_sample, tpm_input_sample))]


def main(config_path):
    """
    Generate a PaSD configuration and write to file in YAML format.

    :param config_path: target file path for the configuration file.
    """
    config = {
        "stations": [
            {
                "station_id": station_id,
                "smartboxes": get_smartbox_config_for_station(),
                "antennas": get_antenna_config_for_station(station_id),
            } for station_id in range(1, NUMBER_OF_STATIONS+1)
        ]
    }
    
    with open(config_path, 'w') as config_file:
        config_file.write("# This file was generated by scripts/generate_pasd_config.py.\n")
        config_file.write(yaml.dump(config))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description = 'Generate a configuration file for the PaSD simulator',
    )
    parser.add_argument('config_path', help='path to the config to be written')
    args = parser.parse_args()

    main(args.config_path)