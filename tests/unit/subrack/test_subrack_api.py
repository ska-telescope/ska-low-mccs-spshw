"""Tests of the SubrackApi."""
import unittest

import fastapi
import pytest
from fastapi.testclient import TestClient

from ska_low_mccs_spshw.subrack.subrack_api import SubrackProtocol, router


@pytest.fixture(name="backend")
def backend_fixture() -> unittest.mock.Mock:
    """
    Return a mock backend to test the API against.

    :return: a mock backend to test the API against.
    """
    return unittest.mock.Mock()


@pytest.fixture(name="client")
def client_fixture(backend: SubrackProtocol) -> TestClient:
    """
    Return an API client for use in testing.

    :param backend: a mock backend to test the API against.

    :return: an API client for use in testing.
    """
    subrack_api = fastapi.FastAPI()
    subrack_api.state.backend = backend
    subrack_api.include_router(router)
    return TestClient(subrack_api)


def test_bad_path(client: TestClient) -> None:
    """
    Test handling of a request with an unknown path.

    :param client: a test client to test the API with.
    """
    response = client.get("/")
    assert response.status_code == 404
    assert response.json() == {"detail": "Path '/' not found"}


def test_missing_type(client: TestClient) -> None:
    """
    Test handling of a request with unspecified type.

    :param client: a test client to test the API with.
    """
    response = client.get("/json.htm")
    assert response.status_code == 200
    assert response.json() == {
        "info": "Missing keyword: type",
        "status": "ERROR",
    }


def test_invalid_type(client: TestClient) -> None:
    """
    Test handling of a request of invalid type.

    That is, a request that is not of type "getattribute",
    "setattribute" or "command".

    :param client: a test client to test the API with.
    """
    response = client.get("/json.htm?type=foo")
    assert response.status_code == 200
    assert response.json() == {
        "info": "Invalid type: foo",
        "status": "ERROR",
    }


def test_getattribute_with_no_name(client: TestClient) -> None:
    """
    Test handling of a getattribute request without an attribute name.

    :param client: a test client to test the API with.
    """
    response = client.get("/json.htm?type=getattribute")
    assert response.status_code == 404
    assert response.json() == {
        "detail": "Messages of type 'getattribute' require a 'param' field."
    }


def test_getattribute_with_bad_name(
    client: TestClient, backend: unittest.mock.Mock
) -> None:
    """
    Test handling of a getattribute request for a non-existent attribute.

    :param client: a test client to test the API with.
    :param backend: a mock backend to test the API against.
    """
    bad_name = "foo"

    # Set up the backend mock to raise an AttributeError when we call
    # get_attribute().
    backend.get_attribute.side_effect = AttributeError(f"{bad_name} not present")

    response = client.get(f"/json.htm?type=getattribute&param={bad_name}")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ERROR",
        "info": f"{bad_name} not present",
        "attribute": bad_name,
        "value": "",
    }


def test_good_getattribute(client: TestClient, backend: unittest.mock.Mock) -> None:
    """
    Test handling of a well-formed getattribute request.

    :param client: a test client to test the API with.
    :param backend: a mock backend to test the API against.
    """
    name = "tpm_on_off"
    value = [False] * 8

    # Set up the backend mock to return this value when we call # get_attribute().
    backend.get_attribute.return_value = value

    response = client.get(f"/json.htm?type=getattribute&param={name}")
    assert response.status_code == 200
    assert response.json() == {
        "status": "OK",
        "info": "",
        "attribute": name,
        "value": value,
    }


def test_setattribute_with_no_name(client: TestClient) -> None:
    """
    Test handling of a setattribute attempt without an attribute name provided.

    :param client: a test client to test the API with.
    """
    response = client.get("/json.htm?type=setattribute")
    assert response.status_code == 404
    assert response.json() == {
        "detail": "Messages of type 'setattribute' require a 'param' field."
    }


def test_setattribute_with_no_value(client: TestClient) -> None:
    """
    Test handling of a setattribute attempt without a value provided.

    :param client: a test client to test the API with.
    """
    response = client.get("/json.htm?type=setattribute&param=foo")
    assert response.status_code == 404
    assert response.json() == {
        "detail": "Messages of type 'setattribute' require a 'value' field."
    }


def test_setattribute_with_bad_name(
    client: TestClient, backend: unittest.mock.Mock
) -> None:
    """
    Test handling of a setattribute attempt on a non-existent attribute.

    :param client: a test client to test the API with.
    :param backend: a mock backend to test the API against.
    """
    bad_name = "foo"

    # Set up the backend mock to raise an AttributeError when we call
    # set_attribute().
    backend.set_attribute.side_effect = AttributeError(f"{bad_name} not present")

    response = client.get(f"/json.htm?type=setattribute&param={bad_name}&value=0")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ERROR",
        "info": f"{bad_name} not present",
        "attribute": bad_name,
        "value": "",
    }


def test_setattribute_on_readonly_attribute(
    client: TestClient, backend: unittest.mock.Mock
) -> None:
    """
    Test handling of an attempt to set a readonly attribute.

    :param client: a test client to test the API with.
    :param backend: a mock backend to test the API against.
    """
    name = "foo"

    # Set up the backend mock to raise an AttributeError when we call
    # set_attribute().
    backend.set_attribute.side_effect = TypeError(
        f"Attempt to write read-only attribute {name}"
    )

    response = client.get(f"/json.htm?type=setattribute&param={name}&value=0")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ERROR",
        "info": f"Attempt to write read-only attribute {name}",
        "attribute": name,
        "value": "",
    }


def test_setattribute_with_wrong_length(
    client: TestClient, backend: unittest.mock.Mock
) -> None:
    """
    Test handling of a setattribute with the wrong attribute length.

    :param client: a test client to test the API with.
    :param backend: a mock backend to test the API against.
    """
    name = "foo"

    # Set up the backend mock to raise an AttributeError when we call
    # set_attribute().
    backend.set_attribute.side_effect = ValueError(
        f"Wrong number of values for attribute {name}"
    )

    response = client.get(f"/json.htm?type=setattribute&param={name}&value=0")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ERROR",
        "info": f"Wrong number of values for attribute {name}",
        "attribute": name,
        "value": "",
    }


def test_good_setattribute(client: TestClient, backend: unittest.mock.Mock) -> None:
    """
    Test handling of a well-formed setattribute request.

    :param client: a test client to test the API with.
    :param backend: a mock backend to test the API against.
    """
    name = "foo"
    value = 1

    # Set up the backend mock to return this value when we call get_attribute().
    backend.set_attribute.return_value = value

    response = client.get(f"/json.htm?type=setattribute&param={name}&value={value}")
    assert response.status_code == 200
    assert response.json() == {
        "status": "OK",
        "info": "",
        "attribute": name,
        "value": value,
    }


def test_command_with_no_name(client: TestClient) -> None:
    """
    Test handling of a command invokation without a provided command name.

    :param client: a test client to test the API with.
    """
    response = client.get("/json.htm?type=command")
    assert response.status_code == 404
    assert response.json() == {
        "detail": "Messages of type 'command' require a 'param' field."
    }


def test_command_with_no_value(client: TestClient) -> None:
    """
    Test handling of a command with an unprovided required value.

    :param client: a test client to test the API with.
    """
    response = client.get("/json.htm?type=command&param=foo")
    assert response.status_code == 404
    assert response.json() == {
        "detail": "Messages of type 'command' require a 'value' field."
    }


def test_command_with_bad_name(client: TestClient, backend: unittest.mock.Mock) -> None:
    """
    Test handling of invokation of a non-existent command.

    :param client: a test client to test the API with.
    :param backend: a mock backend to test the API against.
    """
    bad_name = "foo"

    # Set up the backend mock to raise an AttributeError when we call
    # set_attribute().
    backend.execute_command.side_effect = AttributeError(f"{bad_name} not present")

    response = client.get(f"/json.htm?type=command&param={bad_name}&value=0")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ERROR",
        "info": f"{bad_name} not present",
        "command": bad_name,
        "retvalue": "",
    }


def test_good_command(client: TestClient, backend: unittest.mock.Mock) -> None:
    """
    Test handling of a well-formed command.

    :param client: a test client to test the API with.
    :param backend: a mock backend to test the API against.
    """
    name = "foo"
    return_value = 1

    # Set up the backend mock to return this value when we call get_attribute().
    backend.execute_command.return_value = return_value

    response = client.get(f"/json.htm?type=command&param={name}&value=bah")
    assert response.status_code == 200
    assert response.json() == {
        "status": "OK",
        "info": "",
        "command": name,
        "retvalue": return_value,
    }
