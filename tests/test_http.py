"""Unit tests for the retrying HTTP layer (requests is mocked — no network)."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from imdfetch import http
from imdfetch.exceptions import NetworkError


def _ok_response():
    resp = MagicMock(spec=requests.Response)
    resp.raise_for_status.return_value = None
    return resp


class TestSafeGet:
    @patch("imdfetch.http.requests.request")
    def test_success_first_try_verifies_tls(self, mock_request):
        resp = _ok_response()
        mock_request.return_value = resp

        assert http.safe_get("https://example.test") is resp
        assert mock_request.call_count == 1
        _, kwargs = mock_request.call_args
        assert kwargs["verify"] is True

    @patch("imdfetch.http.requests.request")
    def test_ssl_error_falls_back_to_no_verify(self, mock_request):
        resp = _ok_response()
        mock_request.side_effect = [requests.exceptions.SSLError("bad cert"), resp]

        assert http.safe_get("https://example.test") is resp
        assert mock_request.call_count == 2
        assert mock_request.call_args_list[0].kwargs["verify"] is True
        assert mock_request.call_args_list[1].kwargs["verify"] is False

    @patch("imdfetch.http.requests.request")
    def test_raises_network_error_after_exhaustion(self, mock_request):
        mock_request.side_effect = requests.exceptions.ConnectionError("down")

        with pytest.raises(NetworkError):
            http.safe_get("https://example.test", max_retries=0)


class TestSafePost:
    @patch("imdfetch.http.requests.request")
    def test_sends_post_with_data_and_merged_headers(self, mock_request):
        resp = _ok_response()
        mock_request.return_value = resp

        out = http.safe_post(
            "https://example.test",
            data={"ID": 42182},
            extra_headers={"Referer": "https://ref.test"},
        )
        assert out is resp
        args, kwargs = mock_request.call_args
        assert args[0] == "POST"
        assert kwargs["data"] == {"ID": 42182}
        assert kwargs["headers"]["Referer"] == "https://ref.test"
        # Default headers are still merged in.
        assert "User-Agent" in kwargs["headers"]
