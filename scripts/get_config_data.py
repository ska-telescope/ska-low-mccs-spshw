"""Script to retrieve the geojson configuration files
Converts the geojson formated data into a format that can be
used by the tango devices.

Important note is that the format of the geojson files is not
final and contains some errors, so expect these conversion scripts
to change.
"""
from ska_telmodel.data import TMData


def antenna_geojson_to_config(full_config: dict) -> dict:
    """Converts antenna geojson config to dict usable by tango device."""
    features = full_config.get('features')

    new_config = {}
    for feature in features:
        antenna_config = feature.get('properties')
        antenna_fqdn = f'low-mccs/antenna/00000{antenna_config["antenna_station_id"] + 1}'
        antenna_config.get('antenna_station_id')
        new_config[antenna_fqdn] = {}

        antenna_config_formatted = {
            "station_id": antenna_config.get('station_id'),
            "xDisplacement": antenna_config.get('x_pos'),
            "yDisplacement": antenna_config.get('y_pos'),
        }
        tile_config = {"delays": [antenna_config.get('delay_x'), antenna_config.get('delay_y')]}

        new_config[antenna_fqdn]["antenna"] = antenna_config_formatted
        new_config[antenna_fqdn]["tile"] = tile_config

    return new_config

def station_geojson_to_config(full_config: dict) -> dict:
    """Converts station geojson config to dict usable by tango device."""
    features = full_config.get('features')

    new_config = {}
    for feature in features:
        station_config = feature.get('properties')
        station_geometry = feature.get('geometry')
        station_fqdn = f'low-mccs/station/00{station_config["station_num"]}'

        station_config_formatted = {
            "nof_antennas": station_config.get('nof_antennas'),
            "refLatitude": station_geometry.get('coordinates')[0],
            "refLongitude": station_geometry.get('coordinates')[1],
        }

        new_config[station_fqdn]["station"] = station_config_formatted

    return new_config


tmdata = TMData()

antenna_layout = tmdata['mccs-configuration/antenna_export_w2.geojson'].get_dict()
station_layout = tmdata['mccs-configuration/station_export_w2.geojson'].get_dict()

new_antenna_config = antenna_geojson_to_config(antenna_layout)
new_station_config = station_geojson_to_config(station_layout)
