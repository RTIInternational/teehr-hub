"""Example: call the TEEHR API with an API key using requests.

Usage:
  export TEEHR_API_URL=https://api.teehr.local.app.garden
  export TEEHR_API_KEY=your-api-key
  python call_teehr_api_with_api_key.py

The API expects the key in the `x-api-key` header.
"""

from __future__ import annotations

import os
from typing import Any

import requests
import urllib3


API_URL = os.getenv("TEEHR_API_URL", "https://api.teehr.local.app.garden")
API_KEY = os.getenv("TEEHR_API_KEY", "thk_OteEVJb4uonO-CvfUSwi3BLXJiA5UZ0NF9r3y2xWrHc")
SKIP_SSL_VERIFY = "local" in API_URL

if SKIP_SSL_VERIFY:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def call_api(path: str) -> dict[str, Any]:
    """Call a teehr-api endpoint with the configured API key."""
    if not API_KEY:
        raise RuntimeError("Set TEEHR_API_KEY before running this example.")

    url = f"{API_URL.rstrip('/')}{path}"
    response = requests.get(
        url,
        headers={"x-api-key": API_KEY},
        verify=not SKIP_SSL_VERIFY,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def main() -> None:
    payload = call_api("/collections/locations/items?limit=5")
    print("Configurations:")
    print(payload)


if __name__ == "__main__":
    main()