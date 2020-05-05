"""
A module defining a list of fixtures that are shared across all ska.mccs tests.
"""
import importlib
import pytest

from tango.test_context import DeviceTestContext


@pytest.fixture(scope="class")
def tango_context(request):
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
            "NrSubarrays": "16",
            # 'CapabilityTypes': '',
            # 'MaxCapabilities': []
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
    tango_context = DeviceTestContext(
        class_type, properties=test_properties.get(class_name, {})
    )
    tango_context.class_name = class_name
    tango_context.start()
    yield tango_context
    tango_context.stop()


@pytest.fixture(scope="function")
def initialize_device(tango_context):
    """Re-initializes the device.

    Parameters
    ----------
    tango_context: tango.test_context.DeviceTestContext
        Context to run a device without a database.
    """
    yield tango_context.device.Init()
