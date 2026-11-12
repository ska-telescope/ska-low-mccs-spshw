#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
Stopgap to stop JSON command arguments re-checking their schema on every call.

ska-tango-base's ``@validate_json_args`` calls ``jsonschema.validate`` on
every command invocation. ``jsonschema.validate`` first checks the schema
itself against its metaschema (``check_schema``), and only then validates the
argument. Our schemas never change, so that check is wasted work, and for
draft 2020-12 schemas it is expensive: the metaschema is an ``allOf`` over
several vocabularies. When a command is called at a high rate, this holds the
GIL long enough to delay polling of every device in the process.

:py:func:`install` makes ska-tango-base use a validator that is built, and
whose schema is checked, once per schema.

Remove this module once ska-tango-base caches its validators.
"""

from __future__ import annotations

import types
from typing import Any

import jsonschema
import ska_tango_base.validators

__all__ = ["cached_validate", "install"]

# id(schema) -> (schema, validator). The schema is kept so its id can't be
# reused by another object while the entry exists.
_validators: dict[int, tuple[Any, Any]] = {}


def cached_validate(instance: Any, schema: Any) -> None:
    """
    Validate ``instance`` against ``schema``, like ``jsonschema.validate``.

    Behaves the same as ``jsonschema.validate(instance, schema)``, except that
    the schema is checked and the validator built only on the first call for
    a given schema object. Schemas are cached by identity, so they must not be
    mutated after their first use.

    :param instance: the decoded JSON to validate.
    :param schema: the JSON schema to validate against.

    :raises error: most relevant error
        jsonschema.ValidationError - if the instance is invalid.
        jsonschema.SchemaError: if the schema itself is invalid. The
        schema is not cached, so this is raised on every call, as before.
    """
    entry = _validators.get(id(schema))
    if entry is None or entry[0] is not schema:
        cls = jsonschema.validators.validator_for(schema)
        cls.check_schema(schema)  # raises SchemaError; nothing cached
        entry = (schema, cls(schema))
        # A race just builds the validator twice; dict assignment is atomic.
        _validators[id(schema)] = entry
    # Same error selection as jsonschema.validate: raise the most relevant.
    error = jsonschema.exceptions.best_match(entry[1].iter_errors(instance))
    if error is not None:
        raise error


def install() -> None:
    """
    Make ska-tango-base's ``@validate_json_args`` use :py:func:`cached_validate`.

    Its module only uses ``jsonschema.validate`` and
    ``jsonschema.ValidationError``, so it is given a stand-in ``jsonschema``
    that provides those two. Safe to call more than once.
    """
    ska_tango_base.validators.jsonschema = types.SimpleNamespace(  # type: ignore
        validate=cached_validate,
        ValidationError=jsonschema.ValidationError,
    )
