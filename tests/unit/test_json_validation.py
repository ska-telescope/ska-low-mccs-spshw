# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""Tests of the stopgap cache for JSON command argument schemas."""
from __future__ import annotations

import json
import unittest.mock
from typing import Any

import jsonschema
import pytest
import ska_tango_base.validators
from ska_tango_base.faults import ValidateJSONArgsError

from ska_low_mccs_spshw import json_validation

SCHEMA = json.loads(
    """
{
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {"value": {"type": "integer", "minimum": 0}},
    "required": ["value"]
}
"""
)


@pytest.fixture(autouse=True, name="empty_cache")
def empty_cache_fixture() -> None:
    """Start each test with no cached validators."""
    json_validation._validators.clear()


def test_schema_checked_once() -> None:
    """Test the schema is only checked against its metaschema on first use."""
    cls = jsonschema.validators.validator_for(SCHEMA)
    with unittest.mock.patch.object(
        cls, "check_schema", wraps=cls.check_schema
    ) as check_schema:
        for value in range(5):
            json_validation.cached_validate({"value": value}, SCHEMA)
    check_schema.assert_called_once_with(SCHEMA)


@pytest.mark.parametrize(
    "instance", [{}, {"value": -1}, {"value": "1"}, [], {"value": 1}]
)
def test_same_result_as_jsonschema(instance: Any) -> None:
    """
    Test the cached validator raises exactly what jsonschema.validate does.

    :param instance: the decoded JSON to validate.
    """
    try:
        jsonschema.validate(instance, SCHEMA)
        expected = None
    except jsonschema.ValidationError as exc:
        expected = exc.message

    try:
        json_validation.cached_validate(instance, SCHEMA)
        actual = None
    except jsonschema.ValidationError as exc:
        actual = exc.message

    assert actual == expected


def test_invalid_schema_raises_every_time() -> None:
    """Test an invalid schema is not cached, so it fails on every call."""
    bad_schema = {"type": 12}
    for _ in range(2):
        with pytest.raises(jsonschema.SchemaError):
            json_validation.cached_validate({}, bad_schema)
    assert not json_validation._validators


def test_validate_json_args_uses_cache() -> None:
    """Test ska-tango-base's decorator validates through the cache once installed."""
    json_validation.install()  # also done on package import; repeat is harmless

    # pylint: disable=too-few-public-methods
    class _Device:
        @ska_tango_base.validators.validate_json_args(schema=SCHEMA)
        def command(self: _Device, value: int) -> int:
            """
            Command to decorate.

            :param value: the value

            :return: the value
            """
            return value

    device = _Device()
    assert device.command(json.dumps({"value": 3})) == 3
    assert id(SCHEMA) in json_validation._validators

    with pytest.raises(ValidateJSONArgsError):
        device.command(json.dumps({"value": -1}))
