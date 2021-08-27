"""This module contains tests of the hardware client module."""
from __future__ import annotations

from typing import Any

import pytest
import pytest_mock
import requests

from ska_low_mccs.component import WebHardwareClient


class TestWebHardwareClient:
    """Tests of the WebHardwareClient class."""

    def test(
        self: TestWebHardwareClient,
        monkeypatch: pytest.monkeypatch,
        mocker: pytest_mock.mocker,
    ) -> None:
        """
        Test the web hardware client.

        :param monkeypatch: the pytest monkey-patching fixture
        :param mocker: a fixture that wraps unittest.mock
        """
        good_ip = "192.0.2.0"
        a_bad_ip = "192.0.2.1"

        class MockResponse:
            """A mock class to replace requests.Response."""

            status_code = requests.codes.ok

            @staticmethod
            def json() -> dict[str, str]:
                """
                A mock method to replace the patched :py:meth:`request.Response.json`.

                This implementation always returns the same key-value pair.

                :return: a dictionary with a single key-value pair in it.
                """
                return {"mock_key": "mock_value"}

        def mock_request(method: str, url: str, **kwargs: Any) -> MockResponse:
            """
            A mock method to replace requests.request.

            :param method: "GET" or "POST"
            :param url: the URL
            :param kwargs: other keyword args

            :raises RequestException: if the URL
                provided is not to the one and only good IP address
                supported by this patch mock.

            :return: a response
            """
            if good_ip in url:
                return MockResponse()
            raise requests.exceptions.RequestException(
                "Test harness has monkeypatched requests.requests so that successful "
                f"connections can only be made to {good_ip}."
            )

        def mock_get(url: str, params: Any = None, **kwargs: Any) -> MockResponse:
            """
            A mock method to replace requests.get.

            :param url: the URL
            :param params: arguments to the GET
            :param kwargs: other keyword args

            :raises RequestException: if the URL
                provided is not to the one and only good IP address
                supported by this patch mock.

            :return: a response
            """
            if good_ip in url:
                return MockResponse()
            raise requests.exceptions.RequestException(
                "Test harness has monkeypatched requests.get so that successful "
                f"connections can only be made to {good_ip}."
            )

        monkeypatch.setattr(requests, "request", mock_request)
        monkeypatch.setattr(requests, "get", mock_get)

        client = WebHardwareClient(a_bad_ip, 80)
        assert not client.connect()
        assert client.execute_command("Foo") == {
            "status": "ERROR",
            "info": "Not connected",
            "command": "Foo",
            "retvalue": "",
        }
        assert client.get_attribute("foo") == {
            "status": "ERROR",
            "info": "Not connected",
            "attribute": "foo",
            "value": None,
        }
        assert client.set_attribute("foo", "bah") == {
            "status": "ERROR",
            "info": "Not connected",
            "attribute": "foo",
            "value": None,
        }

        client = WebHardwareClient(good_ip, 80)
        assert client.connect()

        assert client.execute_command("Foo") == {
            "mock_key": "mock_value",
        }
        assert client.get_attribute("foo") == {
            "mock_key": "mock_value",
        }
        assert client.set_attribute("foo", "bah") == {
            "mock_key": "mock_value",
        }
