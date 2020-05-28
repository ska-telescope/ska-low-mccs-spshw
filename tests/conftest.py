"""
A module defining a list of fixtures that are shared across all ska.mccs tests.
"""
from collections import defaultdict
import importlib
import pytest
import socket
import tango
from tango.test_context import (DeviceTestContext,
                                MultiDeviceTestContext,
                                get_host_ip)
from ska.mccs import MccsMaster, MccsSubarray, MccsStation, MccsTile


@pytest.fixture(scope="function")
def tango_device(request):
    """
    Creates and returns a DeviceProxy under a DeviceTestContext.

    :param request: A request object gives access to the requesting test
        context.
    :type request: _pytest.fixtures.SubRequest
    """
    test_properties = {
        "MccsMaster": {
            "SkaLevel": "4",
            "LoggingTargetsDefault": "",
            "GroupDefinitions": "",
            "MccsSubarrays": ["low/elt/subarray_1", "low/elt/subarray_2"],
            "MccsStations": ["low/elt/station_1", "low/elt/station_2"],
        },
        "MccsSubarray": {"CapabilityTypes": ["BAND1", "BAND2"]},
        "MccsStation": {"TileFQDNs": ["low/elt/tile_1", "low/elt/tile_2"]},
        "MccsTile": {"AntennasPerTile": "16"},
    }

    # This fixture is used to decorate classes like "TestMccsMaster" or
    # "TestMccsStation". We drop the first "Test" from the string to get the
    # class name of the device under test.
    # Similarly, the test module is like "test_MccsTile.py".  We drop the
    # first "test_" to get the module name
    test_class_name = request.cls.__name__
    class_name = test_class_name.split("Test", 1)[-1]
    module = importlib.import_module("ska.mccs", class_name)
    class_type = getattr(module, class_name)

    with DeviceTestContext(
        class_type, properties=test_properties.get(class_name, {})
    ) as tango_device:
        yield tango_device


@pytest.fixture(scope="function")
def initialize_device(tango_device):
    """Re-initializes the device.

    Parameters
    ----------
    tango_device: tango.DeviceProxy
        Context to run a device without a database.
    """
    yield tango_device.Init()


@pytest.fixture(scope="function")
def tango_context(mocker):
    """
    Creates and returns a TANGO MultiDeviceTestContext object, with a
    tango.DeviceProxy patched to a work around a name resolving issue.
    """
    def _get_open_port():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("", 0))
        s.listen(1)
        port = s.getsockname()[1]
        s.close()
        return port

    HOST = get_host_ip()
    PORT = _get_open_port()

    _DeviceProxy = tango.DeviceProxy
    mocker.patch(
        'tango.DeviceProxy',
        wraps=lambda fqdn, *args, **kwargs: _DeviceProxy(
            "tango://{0}:{1}/{2}#dbase=no".format(HOST, PORT, fqdn),
            *args,
            **kwargs
        )
    )

    devices_info = [
        {
            "class": MccsMaster,
            "devices": (
                {
                    "name": "low/elt/master",
                    "properties": {
                        "MccsSubarrays": ["low/elt/subarray_1",
                                          "low/elt/subarray_2"],
                        "MccsStations": ["low/elt/station_1",
                                         "low/elt/station_2"],
                        "MccsTiles": ["low/elt/tile_1",
                                      "low/elt/tile_2",
                                      "low/elt/tile_3",
                                      "low/elt/tile_4"],
                    }
                },
            )
        },
        {
            "class": MccsSubarray,
            "devices": [
                {
                    "name": "low/elt/subarray_1",
                    "properties": {
                    }
                },
                {
                    "name": "low/elt/subarray_2",
                    "properties": {
                    }
                }
            ]
        },
        {
            "class": MccsStation,
            "devices": [
                {
                    "name": "low/elt/station_1",
                    "properties": {
                        "TileFQDNs": ["low/elt/tile_1", "low/elt/tile_2"]
                    }
                },
                {
                    "name": "low/elt/station_2",
                    "properties": {
                        "TileFQDNs": ["low/elt/tile_3", "low/elt/tile_4"]
                    }
                },
            ]
        },
        {
            "class": MccsTile,
            "devices": [
                {
                    "name": "low/elt/tile_1",
                    "properties": {
                    }
                },
                {
                    "name": "low/elt/tile_2",
                    "properties": {
                    }
                },
                {
                    "name": "low/elt/tile_3",
                    "properties": {
                    }
                },
                {
                    "name": "low/elt/tile_4",
                    "properties": {
                    }
                },
            ]
        },
    ]

    with MultiDeviceTestContext(devices_info, host=HOST, port=PORT) as context:
        yield context


@pytest.fixture(scope="function")
def mock_device_proxy(mocker):
    """
    A fixture that mocks tango.DeviceProxy and keeps each mock in a
    dictionary keyed by FQDN, so that every time you open a DeviceProxy
    to a device specified by the same FQDN, you get the same mock.
    """
    mock_device_proxies = defaultdict(mocker.Mock)
    mocker.patch(
        'tango.DeviceProxy',
        side_effect=lambda fqdn: mock_device_proxies[fqdn]
    )
    yield mock_device_proxies
