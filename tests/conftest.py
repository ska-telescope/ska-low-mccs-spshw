"""
This module contains pytest fixtures and other test setups common to
all ska.low.mccs tests: unit, integration and functional (BDD)
"""
from collections import defaultdict
import json
import logging

import pytest


def pytest_addoption(parser):
    """
    Pytest hook; implemented to add the `--true-context` option, used to
    indicate that a true Tango subsystem is available, so there is no
    need for a MultiDeviceTestContext

    :param parser: the command line options parser
    :type parser: :py:class:`argparse.ArgumentParser`
    """
    parser.addoption(
        "--true-context",
        action="store_true",
        help=(
            "Tell pytest that you have a true Tango context and don't "
            "need to spin up a Tango test context"
        ),
    )


def _load_data_from_json(path):
    """
    Loads a dataset from a named json file.

    :param path: path to the JSON file from which the dataset is to be
        loaded.
    :type path: str

    :return: data loaded and deserialised from a JSON data file
    :rtype: anything JSON-serialisable
    """
    with open(path, "r") as json_file:
        return json.load(json_file)


def _load_devices(path, device_names):
    """
    Loads device configuration data for specified devices from a
    specified JSON configuration file.

    :param path: path to the JSON configuration file
    :type path: str
    :param device_names: names of the devices for which configuration
        data should be loaded
    :type device_names: list(str)

    :return: a devices_info spec in a format suitable for use by as
        input to a :py:class:`tango.test_context.MultiDeviceTestContext`
    :rtype: dict
    """
    configuration = _load_data_from_json(path)
    devices_by_class = {}

    servers = configuration["servers"]
    for server in servers:
        for device_name in servers[server]:
            if device_name in device_names:
                for class_name, device_info in servers[server][device_name].items():
                    if class_name not in devices_by_class:
                        devices_by_class[class_name] = []
                    for fqdn, device_specs in device_info.items():
                        devices_by_class[class_name].append(
                            {"name": fqdn, **device_specs}
                        )

    devices_info = []
    for device_class in devices_by_class:
        device_info = []
        for device in devices_by_class[device_class]:
            device_info.append(device)

        devices_info.append({"class": device_class, "devices": device_info})

    return devices_info


@pytest.fixture()
def device_info(device_to_load):
    """
    Constructs a device_info dictionary in the form required by
    tango.test_context.DeviceTestContext, with the device as specified
    by the device_to_load fixture

    :param device_to_load: fixture that provides a specification of the
        device that is to be included in the devices_info dictionary
    :type device_to_load: dictionary

    :return: a specification of devices
    :rtype: dict
    """
    devices = _load_devices(
        path=device_to_load["path"], device_names=[device_to_load["device"]]
    )

    if "patch" in device_to_load:
        device_class = device_to_load["patch"]
    else:
        class_to_import = devices[0]["class"]
        package = __import__(device_to_load["package"], fromlist=class_to_import)
        device_class = getattr(package, devices[0]["class"])

    return {"class": device_class, "properties": devices[0]["devices"][0]["properties"]}


@pytest.fixture()
def devices_info(devices_to_load):
    """
    Constructs a devices_info dictionary in the form required by
    tango.test_context.MultiDeviceTestContext, with devices as specified
    by the devices_to_load fixture

    :param devices_to_load: fixture that provides a specification of the
        devices that are to be included in the devices_info dictionary
    :type devices_to_load: dictionary

    :return: a specification of devices
    :rtype: dict
    """
    devices = _load_devices(
        path=devices_to_load["path"], device_names=devices_to_load["devices"]
    )

    patches = devices_to_load["patch"] if "patch" in devices_to_load else {}

    devices_to_patch = defaultdict(list)
    devices_to_import = defaultdict(list)

    for group in devices:
        for device in group["devices"]:
            if device["name"] in patches:
                patch = patches[device["name"]]
                devices_to_patch[patch].append(device)
            else:
                devices_to_import[group["class"]].append(device)

    patched_devices = [
        {"class": cls, "devices": devices_to_patch[cls]} for cls in devices_to_patch
    ]

    package = __import__(devices_to_load["package"], fromlist=devices_to_import.keys())
    imported_devices = [
        {"class": getattr(package, cls), "devices": devices_to_import[cls]}
        for cls in devices_to_import
    ]

    return imported_devices + patched_devices


@pytest.fixture()
def logger():
    """
    Fixture that returns a default logger

    :return: a logger
    :rtype logger: :py:class:`logging.Logger`
    """
    return logging.getLogger()
