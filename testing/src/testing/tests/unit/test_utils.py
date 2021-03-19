########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
########################################################################
"""
This module contains the tests for the ska_low_mccs.utils module.
"""
import json

import jsonschema
import pytest
from tango import DevFailed, ErrSeverity
from tango.server import Device, command
from tango.test_context import DeviceTestContext

from ska_low_mccs.utils import call_with_json, json_input, tango_raise


class TestUtils:
    """
    Test cases for ska_low_mccs.utils module.
    """

    def test_tango_raise_device(self):
        """
        Test for correct execution of `tango_raise` helper function when
        used in a tango device class method.
        """

        class DummyDevice(Device):
            """
            A dummy device with a `method_to_raise` method that uses the
            `tango_raise` helper function to raise a DevFailed
            exception.
            """

            def __init__(self, device_class, device_name):
                """
                Initialises a new dummy device.

                :param device_class: the class of the device
                :type device_class: type
                :param device_name: the name of the device
                :type device_name: FQDN string
                """
                super().__init__(device_class, device_name)

            @command
            def method_to_raise(self):
                """
                A dummy command that uses the `tango_raise` helper
                function to raise a DevFailed exception.
                """
                tango_raise("raise me")

        with DeviceTestContext(DummyDevice) as tango_device:
            with pytest.raises(DevFailed) as ex:
                tango_device.method_to_raise()
            assert ex.value.args[0].desc == "raise me"
            assert ex.value.args[0].reason == "API_CommandFailed"
            assert ex.value.args[0].origin == "DummyDevice.method_to_raise()"
            assert ex.value.args[0].severity == ErrSeverity.ERR

    def test_tango_raise_not_device(self):
        """
        Test that use of `tango_raise` helper function fails in a non-
        device class with default argument (`origin=None`).
        """

        class NonDevice:
            """
            Dummy class, not a tango Device.
            """

            def illegal_use(self):
                """
                Dummy method that tries to use the `tango_raise` helper
                function to raise a tango DevFailed exception.
                """
                tango_raise("Never happens")

        nondevice = NonDevice()
        with pytest.raises(
            TypeError, match="Can only be used in a tango device instance"
        ):
            nondevice.illegal_use()

    @pytest.mark.parametrize(
        ("origin", "severity"),
        [("here()", ErrSeverity.ERR), ("there()", ErrSeverity.WARN)],
    )
    def test_tango_raise_with_args(self, origin, severity):
        """
        Test for correct execution of `tango_raise` helper function when
        used with optional parameters.

        :param origin: the source of this exception
        :type origin: str
        :param severity: The severity of this error
        :type severity: :py:class:`tango.ErrSeverity`
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

        :param stations: value of "stations" key in JSON string
        :type stations: list(str)
        :param tiles: value of "tiles" key in JSON string
        :type tiles: list(str)
        :return: the args extracted from the json input string
        :rtype: dict
        """
        return {"stations": stations, "tiles": tiles}

    @json_input()
    def json_input_kwargs_tester(self, **kwargs):
        """
        Helper method, takes any arguments but decorated to take them as
        a JSON string encoding of a dictionary.

        :param kwargs: a dictionary of named arguments to this method
        :type kwargs: dict

        :return: the kwargs extracted from the json input string
        :rtype: dict
        """
        return kwargs

    @json_input("MccsController_Allocate_lax.json")
    def json_input_schema_tester(self, **kwargs):
        """
        Helper method, takes any arguments but decorated to take them as
        a JSON string encoding of a dictionary. Additionally, this JSON
        string must validate against the specified schema.

        :param kwargs: a dictionary of named arguments to this method
        :type kwargs: dict

        :return: the kwargs extracted from the json input string
        :rtype: dict
        """
        return kwargs

    def test_call_with_json_posargs(self):
        """
        Test for `call_with_json` with posargs provided.
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
        Test for `call_with_json` with kwargs dictionary provided.
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

        :param json_arg_string: a JSON string to be passed to the
            `json_input` decorator
        :type json_arg_string: str
        """
        returned = self.json_input_posargs_tester(json_arg_string)
        assert returned == json.loads(json_arg_string)

    @pytest.mark.parametrize("json_arg_string", ["{}", '{"key": "value"}'])
    def test_json_input_kwargs(self, json_arg_string):
        """
        Test for json_input decorator on a method defined with kwargs.

        :param json_arg_string: a JSON string to be passed to the
            `json_input` decorator
        :type json_arg_string: str
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
        Test for method decorated with json_input with a schema.

        :param json_arg_string: a JSON string to be passed to the
            `json_input` decorator
        :type json_arg_string: str
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

        :param json_arg_string: a JSON string to be passed to the
            `json_input` decorator
        :type json_arg_string: str
        """
        with pytest.raises(jsonschema.ValidationError):
            self.json_input_schema_tester(json_arg_string)
