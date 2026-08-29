"""End-to-end check of the BobOps stack through the Nginx reverse proxy.

Requires the stack to be running:  docker compose up -d --build
"""

import json
import urllib.error
import urllib.request

import pytest

HEALTH_URL = "http://localhost/health"
TIMEOUT = 5

EXPECTED_PAYLOAD = {"status": "healthy", "service": "bobops-api"}


def get_health():
    """Return (status_code, body_bytes) for GET /health through the proxy."""
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=TIMEOUT) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()
    except urllib.error.URLError as error:
        pytest.fail(f"could not reach {HEALTH_URL}: {error.reason}")


def test_health_returns_200():
    status, _ = get_health()
    assert status == 200, f"expected 200 from {HEALTH_URL}, got {status}"


def test_health_returns_expected_payload():
    status, body = get_health()
    assert status == 200, f"expected 200 from {HEALTH_URL}, got {status}"
    assert json.loads(body) == EXPECTED_PAYLOAD
