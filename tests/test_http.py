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


class TestRetryPolicy:
    def _failing(self, mock_request, status):
        resp = _ok_response()
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
            str(status), response=MagicMock(status_code=status)
        )
        mock_request.return_value = resp

    @pytest.mark.parametrize("status", [401, 403, 404])
    @patch("imdfetch.http.time.sleep")
    @patch("imdfetch.http.requests.request")
    def test_permanent_client_errors_are_not_retried(
        self, mock_request, mock_sleep, status
    ):
        self._failing(mock_request, status)

        with pytest.raises(NetworkError):
            http.safe_get("https://example.test")

        assert mock_request.call_count == 1
        mock_sleep.assert_not_called()

    @pytest.mark.parametrize("status", [408, 429, 500, 503])
    @patch("imdfetch.http.time.sleep")
    @patch("imdfetch.http.requests.request")
    def test_transient_statuses_are_retried(self, mock_request, _sleep, status):
        self._failing(mock_request, status)

        with pytest.raises(NetworkError):
            http.safe_get("https://example.test", max_retries=2)

        assert mock_request.call_count == 3

    @patch("imdfetch.http.time.sleep")
    @patch("imdfetch.http.requests.request")
    def test_verified_get_refuses_insecure_fallback(self, mock_request, _sleep):
        mock_request.side_effect = requests.exceptions.SSLError("bad cert")

        with pytest.raises(NetworkError):
            http.verified_get("https://example.test")

        assert all(c.kwargs["verify"] is True for c in mock_request.call_args_list)
