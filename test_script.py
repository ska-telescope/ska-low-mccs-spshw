# from typing import Generator, Optional

# from ska_telmodel.data import TMData  # type: ignore

# tmdata = TMData(
#     ["gitlab://gitlab.com/ska-telescope/mccs/ska-low-mccs?mccs-2056#tmdata"]
# )
# full_dict = tmdata["instrument/mccs-configuration/aavs3.yaml"].get_dict()

# # print(full_dict)

# example_dict = {"key1": {"key2": 1}, "key3": 2}


# def _get_all_keys(
#     nested_dict: dict, key_to_find: str, keys: Optional[list[str]] = None
# ) -> Generator:
#     if keys is None:
#         keys = []
#     for key, value in nested_dict.items():
#         # print(f"my current value pair is {key}, {value}")
#         # keys.append(key)
#         if key == key_to_find:
#             keys.append(key)
#             yield keys
#         elif isinstance(value, dict):
#             # print("ooh nested")
#             # print(key)
#             keys.append(key)
#             yield from _get_all_keys(value, key_to_find, keys)
#         else:
#             # print(f"searched {keys}. didn't find it")
#             keys = []


# def _find_by_key(data: dict, target: str) -> Generator:
#     """
#     Return all entries for given key in generic dictionary.
#     """
#     for key, value in data.items():
#         if key == target:
#             yield value
#         elif isinstance(value, dict):
#             yield from _find_by_key(value, target)


# # Dig through the yaml we loaded in intil we find the stations key.
# # For each time we find a station config, check the station id,
# # if the station id is correct, get the antenna config of that station
# # we assume there's only 1 antennas entry for each station.
# station_clusters = []
# stations = []
# # Get all the station clusters.
# for station_cluster in _find_by_key(full_dict, "station_clusters"):
#     station_clusters.append(station_cluster)
# for station_cluster in station_clusters:
#     for station_cluster_id, station_cluster_config in station_cluster.items():
#         if station_cluster_id == "ci":
#             for station in _find_by_key(station_cluster_config, "stations"):
#                 stations.append(station)
# for station in stations:
#     for station_id, station_config in station.items():
#         if station_id == "1":
#             antennas = next(_find_by_key(station_config, "antennas"))

# print(antennas)
# # for station_cluster_id, station_cluster_config in station_clusters.items():
# #     if station_cluster_id == station_cluster:
# #         for stations in _find_by_key(station_cluster_config, "stations"):
# #             for station_id, station_config in stations.items():
# #                 if station_id == str(self._station_id):
# #                     antennas = next(_find_by_key(station_config, "antennas"))
