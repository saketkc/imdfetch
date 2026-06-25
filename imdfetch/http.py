"""HTTP layer: retrying GET/POST with an SSL-verification fallback."""

import logging
import time
from typing import Optional

import requests
import urllib3

from .constants import (
    DEFAULT_BACKOFF_FACTOR,
    DEFAULT_HEADERS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
)
from .exceptions import NetworkError

logger = logging.getLogger(__name__)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

__all__ = ["make_robust_request", "safe_get", "safe_post"]


def _request(
    method: str,
    url: str,
    data: Optional[dict] = None,
    extra_headers: Optional[dict] = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    timeout: int = DEFAULT_TIMEOUT,
) -> requests.Response:
    """Issue an HTTP request with retry + SSL-verification fallback.
    """
    headers = {**DEFAULT_HEADERS, **(extra_headers or {})}
    last_err: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        for verify in (True, False):
            try:
                resp = requests.request(
                    method,
                    url,
                    data=data,
                    headers=headers,
                    timeout=timeout,
                    verify=verify,
                )
                resp.raise_for_status()
                return resp
            except requests.exceptions.SSLError as e:
                last_err = e
                logger.warning(
                    "SSL error for %s %s; retrying without verification", method, url
                )
                continue
            except requests.exceptions.RequestException as e:
                last_err = e
                logger.warning(
                    "Request error on attempt %d/%d for %s %s: %s",
                    attempt + 1,
                    max_retries + 1,
                    method,
                    url,
                    e,
                )
                break
        if attempt < max_retries:
            time.sleep(DEFAULT_BACKOFF_FACTOR * (2**attempt))
    raise NetworkError(
        f"{method} {url} failed after {max_retries + 1} attempts: {last_err}"
    )


def make_robust_request(
    url: str,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    timeout: int = DEFAULT_TIMEOUT,
    verify_ssl: bool = True,
) -> requests.Response:
    """GET with retry and SSL fallback. ``backoff_factor``/``verify_ssl`` are
    accepted for backward compatibility; the SSL fallback is always applied."""
    return _request("GET", url, max_retries=max_retries, timeout=timeout)


def safe_get(
    url: str, max_retries: int = DEFAULT_MAX_RETRIES, timeout: int = DEFAULT_TIMEOUT
) -> requests.Response:
    """requests.get() with retry logic."""
    return _request("GET", url, max_retries=max_retries, timeout=timeout)


def safe_post(
    url: str,
    data: dict,
    extra_headers: Optional[dict] = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    timeout: int = DEFAULT_TIMEOUT,
) -> requests.Response:
    """POST a form-encoded body with retry + SSL fallback (mirrors safe_get)."""
    return _request(
        "POST",
        url,
        data=data,
        extra_headers=extra_headers,
        max_retries=max_retries,
        timeout=timeout,
    )
