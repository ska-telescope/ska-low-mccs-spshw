#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module provides a HTTP server that acts as front end to a subrack."""
from __future__ import annotations

import dataclasses
from typing import Any, Optional, Protocol

from fastapi import APIRouter, HTTPException, Query, Request, status
from ska_low_mccs_common.component import HardwareClientResponseStatusCodes

# https://github.com/python/typing/issues/182
JsonSerializable = Any


@dataclasses.dataclass(frozen=True)
class CommandResult:
    """
    The result of a command whose response has more than a return value.

    A backend's ``execute_command`` returns one of these instead of a bare
    return value when the response needs other fields as well, such as the
    "failed" field of ``command_completed`` from API 1.8.0.
    """

    retvalue: JsonSerializable
    """The return value of the command."""

    fields: dict[str, JsonSerializable] = dataclasses.field(default_factory=dict)
    """Further fields of the response, which override the defaults."""


class SubrackProtocol(Protocol):
    """
    Structural subtyping protocol for a subrack.

    That is, specification of the interface that subrack hardware or
    simulator must fulfil in order that the web server defined here can
    interact with it.
    """

    @property
    def bios_version(self: SubrackProtocol) -> str:
        """
        Return the SMM BIOS version of the subrack, e.g. "1.8.0".

        :return: the SMM BIOS version.
        """  # noqa: DAR202

    def execute_command(
        self: SubrackProtocol, name: str, argument: Optional[JsonSerializable]
    ) -> JsonSerializable:
        """
        Execute a command on the subrack hardware/simulator.

        :param name: name of the command to execute.
        :param argument: argument to the command.

        :return: a status information dictionary
        """  # noqa: DAR202

    def set_attribute(
        self: SubrackProtocol, name: str, value: JsonSerializable
    ) -> JsonSerializable:
        """
        Set an attribute value on the subrack hardware/simulator.

        :param name: name of the attribute to be set.
        :param value: values to be set.

        :return: the new value for the attribute
        """  # noqa: DAR202

    def get_attribute(self: SubrackProtocol, name: str) -> JsonSerializable:
        """
        Get an attribute value on the subrack hardware/simulator.

        :param name: name of the attribute to be set.

        :return: a status information dictionary
        """  # noqa: DAR202


router = APIRouter()


def _handle_getattribute(
    subrack: SubrackProtocol, name: str | None
) -> dict[str, JsonSerializable]:
    if name is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Messages of type 'getattribute' require a 'param' field.",
        )

    try:
        value = subrack.get_attribute(name)
    except AttributeError as exception:
        # The API answers an attribute it does not have with "retvalue",
        # not "value", in every version.
        return {
            "status": HardwareClientResponseStatusCodes.ERROR.name,
            "info": str(exception),
            "attribute": name,
            "retvalue": "",
        }
    except Exception as exception:  # pylint: disable=broad-except
        # We want to catch all exceptions here, so that the server
        # always lets us know when something went wrong
        return {
            "status": HardwareClientResponseStatusCodes.ERROR.name,
            "info": str(exception),
            "attribute": name,
            # API 1.8.0 reports the value of a failed read as null
            "value": None if subrack.bios_version == "1.8.0" else "",
        }
    return {
        "status": HardwareClientResponseStatusCodes.OK.name,
        "info": "",
        "attribute": name,
        "value": value,
    }


def _handle_setattribute(
    subrack: SubrackProtocol, name: str | None, value: str | None
) -> dict[str, JsonSerializable]:
    if name is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Messages of type 'setattribute' require a 'param' field.",
        )
    if value is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Messages of type 'setattribute' require a 'value' field.",
        )

    try:
        set_value = subrack.set_attribute(name, value)
    except AttributeError as exception:
        # The API answers an attribute it does not have with "retvalue",
        # not "value", in every version.
        return {
            "status": HardwareClientResponseStatusCodes.ERROR.name,
            "info": str(exception),
            "attribute": name,
            "retvalue": "",
        }
    except Exception as exception:  # pylint: disable=broad-except
        # We want to catch all exceptions here, so that the server
        # always lets us know when something went wrong
        return {
            "status": HardwareClientResponseStatusCodes.ERROR.name,
            "info": str(exception),
            "attribute": name,
            "value": "",
        }
    return {
        "status": HardwareClientResponseStatusCodes.OK.name,
        "info": "",
        "attribute": name,
        "value": set_value,
    }


def _handle_command(
    subrack: SubrackProtocol, name: str | None, argument: str | None
) -> dict[str, JsonSerializable]:
    if name is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Messages of type 'command' require a 'param' field.",
        )
    if argument is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Messages of type 'command' require a 'value' field.",
        )

    try:
        return_value = subrack.execute_command(name, argument)
    except Exception as exception:  # pylint: disable=broad-except
        # We want to catch all exceptions here, so that the server
        # always lets us know when something went wrong
        return {
            "status": HardwareClientResponseStatusCodes.ERROR.name,
            "info": str(exception),
            "command": name,
            "retvalue": "",
        }
    if isinstance(return_value, CommandResult):
        return {
            "status": HardwareClientResponseStatusCodes.OK.name,
            "info": "",
            "command": name,
            "retvalue": return_value.retvalue,
            **return_value.fields,
        }
    return {
        "status": HardwareClientResponseStatusCodes.OK.name,
        "info": "",
        "command": name,
        "retvalue": return_value,
    }


@router.get("/get/json.htm")
async def get_json(
    request: Request,
    type_parameter: str | None = Query(None, alias="type"),
    param: str | None = None,
    value: str | None = None,
) -> dict[str, JsonSerializable]:
    """
    Handle a GET request for the path "/get/json.htm".

    :param request: information about this request (used to get access
        to the backend subrack controller/simulator)
    :param type_parameter: value of the "type" argument.
    :param param: value of the "param" argument.
    :param value: value of the "value" argument.

    :return: a result dictionary
    """
    subrack = request.app.state.backend

    if type_parameter is None:
        return {
            "info": "Missing keyword: type",
            "status": HardwareClientResponseStatusCodes.HTTP_ERROR.name,
        }
    if type_parameter == "getattribute":
        return _handle_getattribute(subrack, param)
    if type_parameter == "setattribute":
        return _handle_setattribute(subrack, param, value)
    if type_parameter == "command":
        return _handle_command(subrack, param, value)

    return {
        "info": f"Invalid type: {type_parameter}",
        "status": HardwareClientResponseStatusCodes.HTTP_ERROR.name,
    }


@router.get("{path:path}")
async def get_bad_path(path: str) -> None:
    """
    Handle a GET request for any path not handled by one of the above routes.

    The above routes handle all valid paths, so any path not already
    handled must be an invalid path. Therefore this method raises a 404
    HTTP exception.

    :param path: the requested path.

    :raises HTTPException: because this path is not valid.
    """
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail=f"Path '{path}' not found"
    )
