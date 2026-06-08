"""HTTP transport layer for Football API calls."""

import httpx
import asyncio
import time
from typing import Any, Dict

from core.config import get_settings


class FootballAPIError(Exception):
    """Raised on Football API errors (HTTP or API-level)."""
    pass


class FootballHTTPClient:
    """
    Low-level async HTTP client for api-sports.io.

    Single responsibility: make authenticated, rate-limited GET requests
    and surface errors uniformly. No caching, no parsing.
    """

    MIN_INTERVAL = 1.0  # seconds between requests

    def __init__(self):
        settings = get_settings()
        self.base_url = settings.api_football_base.rstrip("/")
        self._headers = {"x-apisports-key": settings.api_football_key}
        self._last_request_time = 0.0

    async def request(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make a GET request, enforcing rate limit, returning parsed JSON."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.MIN_INTERVAL:
            await asyncio.sleep(self.MIN_INTERVAL - elapsed)

        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        async with httpx.AsyncClient() as client:
            try:
                self._last_request_time = time.time()
                response = await client.get(url, headers=self._headers, params=params or {})
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPError as exc:
                raise FootballAPIError(f"HTTP error on {endpoint}: {exc}") from exc

        errors = data.get("errors")
        if errors:
            if "rateLimit" in errors:
                raise FootballAPIError(f"Rate limit: {errors['rateLimit']}")
            raise FootballAPIError(f"API errors: {errors}")

        return data
