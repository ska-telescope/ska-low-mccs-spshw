"""
A module defining a list of fixtures that are shared across all ska.mccs tests.
"""
import importlib
import pytest
import socket

import tango
from tango.test_context import (DeviceTestContext,
                                MultiDeviceTestContext,
                                get_host_ip)
from ska.mccs import MccsMaster, MccsSubarray, MccsStation, MccsTile


@pytest.fixture(scope="class")
def tango_device(request):
    """Creates and returns a TANGO DeviceTestContext object.

    Parameters
    ----------
    request: _pytest.fixtures.SubRequest
        A request object gives access to the requesting test context.
    """
    test_properties = {
        "MccsMaster": {
            "SkaLevel": "4",
            "LoggingTargetsDefault": "",
            "GroupDefinitions": "",
            "MccsSubarrays": ["low/elt/subarray_1"],
            "MccsStations": ["low/elt/station_1"],
        },
        "MccsSubarray": {"CapabilityTypes": ["BAND1", "BAND2"]},
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
    tango_device: tango.test_context.DeviceTestContext.Device
        Context to run a device without a database.
    """
    yield tango_device.Init()


class MyDeviceProxy(tango.DeviceProxy):
    # @classmethod
    def _get_open_port():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("", 0))
        s.listen(1)
        port = s.getsockname()[1]
        s.close()
        return port

    HOST = get_host_ip()
    # PORT = MyDeviceProxy.get_open_port()
    PORT = _get_open_port()

    def _get_nodb_fqdn(self, device_name):
        form = 'tango://{0}:{1}/{2}#dbase=no'
        return form.format(self.HOST, self.PORT, device_name)

    def __init__(self, device_name, *args, **kwargs):
        super().__init__(self._get_nodb_fqdn(device_name), *args, **kwargs)


tango.DeviceProxy = MyDeviceProxy  # monkey-patch


@pytest.fixture(scope="class")
def tango_multidevice_context():
    """
    Creates and returns a TANGO MultiDeviceTestContext object.
    """
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
                        "MccsTiles": ["low/elt/tile_47",
                                      "low/elt/tile_129"],
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
                    }
                },
                {
                    "name": "low/elt/station_2",
                    "properties": {
                    }
                },
            ]
        },
        {
            "class": MccsTile,
            "devices": [
                {
                    "name": "low/elt/tile_47",
                    "properties": {
                    }
                },
                {
                    "name": "low/elt/tile_129",
                    "properties": {
                    }
                },
            ]
        },
    ]

    with MultiDeviceTestContext(
        devices_info,
        host=MyDeviceProxy.HOST,
        port=MyDeviceProxy.PORT
    ) as context:
        yield context
