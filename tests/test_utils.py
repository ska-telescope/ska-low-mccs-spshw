########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA ska-low-mccs project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
########################################################################
"""contains the tests for the ska.low.mccs.utils module"""
import json
import jsonschema
import pytest
from tango import DevFailed, ErrSeverity
from tango.server import Device, command
from tango.test_context import DeviceTestContext

from ska.low.mccs.utils import call_with_json, json_input, tango_raise


class DummyDevice(Device):
    def __init__(self, device_class, device_name):
        super().__init__(device_class, device_name)

    @command
    def method_to_raise(self):
        tango_raise("raise me")


# pylint: disable=invalid-name
class TestUtils:
    """
    Test cases for ska.low.mccs.utils module
    """

    def test_tango_raise_device(self):
        """
        Test for correct execution of `tango_raise` helper function when used
        in a tango device class method.
        """
        with DeviceTestContext(DummyDevice) as tango_device:
            with pytest.raises(DevFailed) as ex:
                tango_device.method_to_raise()
            assert ex.value.args[0].desc == "raise me"
            assert ex.value.args[0].reason == "API_CommandFailed"
            assert ex.value.args[0].origin == "DummyDevice.method_to_raise()"
            assert ex.value.args[0].severity == ErrSeverity.ERR

    def test_tango_raise_not_device(self):
        """
        Test that use of `tango_raise` helper function fails in a non-device
        class with default argument (`origin=None`)
        """

        class NonDevice:
            def illegal_use(self):
                tango_raise("Never happens")

        with pytest.raises(TypeError):
            nondevice = NonDevice()
            nondevice.illegal_use()

    @pytest.mark.parametrize(
        "origin,severity", [("here()", ErrSeverity.ERR), ("there()", ErrSeverity.WARN)]
    )
    def test_tango_raise_with_args(self, origin, severity):
        """
        Test for correct execution of `tango_raise` helper function when used
        with optional parameters
        """
        with pytest.raises(DevFailed) as ex:
            tango_raise("Raise Me", severity=severity, _origin=origin)
        assert ex.value.args[0].desc == "Raise Me"
        assert ex.value.args[0].reason == "API_CommandFailed"
        assert ex.value.args[0].origin == origin
        assert ex.value.args[0].severity == severity

    # helper methods not tests
    @json_input()
    def json_input_posargs_tester(self, stations, tiles):
        """
        Helper method, takes arguments `stations` and `tiles` but
        decorated to take them as a JSON string encoding of a dictionary
        containing these keys.
        """
        return {"stations": stations, "tiles": tiles}

    @json_input()
    def json_input_kwargs_tester(self, **args):
        """
        Helper method, takes any arguments but decorated to take them as
        a JSON string encoding of a dictionary.
        """
        return args

    @json_input("schemas/MccsMaster_Allocate_lax.json")
    def json_input_schema_tester(self, **args):
        """
        Helper method, takes any arguments but decorated to take them as
        a JSON string encoding of a dictionary. Additionally, this JSON
        string must validate against the specified schema.
        """
        return args

    def test_call_with_json_posargs(self):
        """
        Test for `call_with_json` with posargs provided
        """
        arg_dict = {"stations": ["station1", "station2"], "tiles": ["tile1", "tile2"]}

        returned = call_with_json(
            self.json_input_posargs_tester,
            stations=arg_dict["stations"],
            tiles=arg_dict["tiles"],
        )
        assert returned == arg_dict

    def test_call_with_json_kwargs(self):
        """
        Test for `call_with_json` with kwargs dictionary provided
        """
        arg_dict = {"stations": ["station1", "station2"], "tiles": ["tile1", "tile2"]}

        returned = call_with_json(self.json_input_posargs_tester, **arg_dict)
        assert returned == arg_dict

    # tests of general methods
    @pytest.mark.parametrize(
        "json_arg_string",
        ['{"stations":["station1", "station2"],"tiles":["tile1", "tile2"]}'],
    )
    def test_json_input_posargs(self, json_arg_string):
        """
        Test for json_input decorator on a method defined with posargs.
        """
        returned = self.json_input_posargs_tester(json_arg_string)
        assert returned == json.loads(json_arg_string)

    @pytest.mark.parametrize("json_arg_string", ["{}", '{"key": "value"}'])
    def test_json_input_kwargs(self, json_arg_string):
        """
        Test for json_input decorator on a method defined with kwargs.
        """
        returned = self.json_input_kwargs_tester(json_arg_string)
        assert returned == json.loads(json_arg_string)

    @pytest.mark.parametrize(
        "json_arg_string",
        [
            '{"subarray_id":1, "stations":["station1", "station2"]}',
            '{"subarray_id":16, "stations":["station1"]}',
        ],
    )
    def test_json_input_schema(self, json_arg_string):
        """
        Test for method decorated with json_input with a schema
        """
        returned = self.json_input_schema_tester(json_arg_string)
        assert returned == json.loads(json_arg_string)

    @pytest.mark.parametrize(
        "json_arg_string",
        [
            '{"subarray_id":0, "stations":["station1"]}',
            '{"subarray_id":17, "stations":["station1"]}',
            '{"subarray_id":1, "stations":[]}',
        ],
    )
    def test_json_input_schema_raises(self, json_arg_string):
        """
        Test that a method decorated with @json_input with a schema
        argument will raise an exception on input that doesn't validate.

        :todo: test for FileNotFoundException on missing schema
        :todo: test for json.JSONDecodeError on bad schema
        :todo: test for json.JSONDecodeError on bad input
        """
        with pytest.raises(jsonschema.ValidationError):
            self.json_input_schema_tester(json_arg_string)
