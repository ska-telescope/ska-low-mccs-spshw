"""
This module contains pytest fixtures and other test setups common to
all ska.low.mccs tests: unit, integration and functional (BDD)
"""
import json
import pytest


def pytest_addoption(parser):
    """
    Pytest hook; implemented to add the `--true-context` option, used to
    indicate that a true Tango subsystem is available, so there is no
    need for a MultiDeviceTestContext

    :param parser: the command line options parser
    :type parser: an argparse parser
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
    :type name: string
    """
    with open(path, "r") as json_file:
        return json.load(json_file)


def _load_devices(path, device_names):
    """
    Loads device configuration data for specified devices from a
    specified JSON configuration file.

    :param path: path to the JSON configuration file
    :type path: string
    :param device_names: names of the devices for which configuration
        data should be loaded
    :type device_names: list of string
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


@pytest.fixture(scope="module")
def devices_to_load(request):
    """
    Fixture that returns the "devices_to_load" variable from the module
    under test. This variable is a dictionary containing three entries:

    * "path": the path to a JSON file containing device configuration
      information in dsconfig format
    * "package": the package from which classes will be loaded; for
      example, if the package is "ska.low.mccs", then if the JSON
      configuration file refers to a class named "MccsMaster", then this
      will be interpretated as the ska.low.mccs.MccsMaster class
    * "devices": a list of names of the devices that are to be loaded.

    """
    return getattr(request.module, "devices_to_load")


@pytest.fixture(scope="module")
def device_to_load(request):
    """
    Fixture that returns the "device_to_load" variable from the module
    under test. This variable is a dictionary containing three entries:

    * "path": the path to a JSON file containing device configuration
      information in dsconfig format
    * "package": the package from which classes will be loaded; for
      example, if the package is "ska.low.mccs", then if the JSON
      configuration file refers to a class named "MccsMaster", then this
      will be interpretated as the ska.low.mccs.MccsMaster class
    * "device": the name of the devices that is to be loaded.

    """
    return getattr(request.module, "device_to_load", None)


@pytest.fixture(scope="module")
def device_info(device_to_load):
    """
    Constructs a device_info dictionary in the form required by
    tango.test_context.DeviceTestContext, with the device as specified
    by the device_to_load fixture

    :param device_to_load: fixture that provides a specification of the
        device that is to be included in the devices_info dictionary
    :type device_to_load: specification of devices to be loaded
    :type device_to_load: dictionary
    """
    devices = _load_devices(
        path=device_to_load["path"], device_names=[device_to_load["device"]]
    )
    # print(devices)
    class_to_import = devices[0]["class"]
    package = __import__(device_to_load["package"], fromlist=class_to_import)

    return {
        "class": getattr(package, devices[0]["class"]),
        "properties": devices[0]["devices"][0]["properties"],
    }


@pytest.fixture(scope="module")
def devices_info(devices_to_load):
    """
    Constructs a devices_info dictionary in the form required by
    tango.test_context.MultiDeviceTestContext, with devices as specified
    by the devices_to_load fixture

    :param devices_to_load: fixture that provides a specification of the
        devices that are to be included in the devices_info dictionary
    :type devices_to_load: specification of devices to be loaded
    :type devices_to_load: dictionary
    """
    devices = _load_devices(
        path=devices_to_load["path"], device_names=devices_to_load["devices"]
    )

    classes_to_import = list(set(device["class"] for device in devices))
    package = __import__(devices_to_load["package"], fromlist=classes_to_import)

    for device in devices:
        device["class"] = getattr(package, device["class"])

    return devices
