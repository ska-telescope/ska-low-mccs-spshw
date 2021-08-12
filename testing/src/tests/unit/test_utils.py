# type: ignore
########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
########################################################################
"""This module contains the tests for the ska_low_mccs.utils module."""
import json

import jsonschema
import pytest

from ska_low_mccs.utils import call_with_json, json_input


class TestUtils:
    """Test cases for ska_low_mccs.utils module."""

    # helper methods not tests
    @json_input()
    def json_input_posargs_tester(self, stations, tiles):
        """
        Helper method, takes arguments `stations` and `tiles` but decorated to take them
        as a JSON string encoding of a dictionary containing these keys.

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
        Helper method, takes any arguments but decorated to take them as a JSON string
        encoding of a dictionary.

        :param kwargs: a dictionary of named arguments to this method
        :type kwargs: dict

        :return: the kwargs extracted from the json input string
        :rtype: dict
        """
        return kwargs

    @json_input("MccsController_Allocate_lax.json")
    def json_input_schema_tester(self, **kwargs):
        """
        Helper method, takes any arguments but decorated to take them as a JSON string
        encoding of a dictionary. Additionally, this JSON string must validate against
        the specified schema.

        :param kwargs: a dictionary of named arguments to this method
        :type kwargs: dict

        :return: the kwargs extracted from the json input string
        :rtype: dict
        """
        return kwargs

    def test_call_with_json_posargs(self):
        """Test for `call_with_json` with posargs provided."""
        arg_dict = {"stations": ["station1", "station2"], "tiles": ["tile1", "tile2"]}

        returned = call_with_json(
            self.json_input_posargs_tester,
            stations=arg_dict["stations"],
            tiles=arg_dict["tiles"],
        )
        assert returned == arg_dict

    def test_call_with_json_kwargs(self):
        """Test for `call_with_json` with kwargs dictionary provided."""
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
        Test that a method decorated with @json_input with a schema argument will raise
        an exception on input that doesn't validate.

        :todo: test for FileNotFoundException on missing schema
        :todo: test for json.JSONDecodeError on bad schema
        :todo: test for json.JSONDecodeError on bad input

        :param json_arg_string: a JSON string to be passed to the
            `json_input` decorator
        :type json_arg_string: str
        """
        with pytest.raises(jsonschema.ValidationError):
            self.json_input_schema_tester(json_arg_string)
