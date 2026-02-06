"""API client for aircontrolbase.com (Midea M-Control cloud)."""

from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp

from .const import (
    BASE_URL,
    CONTROL_PATH,
    DETAILS_PATH,
    LOGIN_PATH,
    SESSION_EXPIRED_CODE,
)

_LOGGER = logging.getLogger(__name__)


class AirControlBaseApiError(Exception):
    """Base exception for API errors."""


class AuthenticationError(AirControlBaseApiError):
    """Authentication failed."""


class AirControlBaseApi:
    """Client for the aircontrolbase.com cloud API."""

    def __init__(
        self,
        email: str,
        password: str,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize the API client."""
        self._email = email
        self._password = password
        self._session = session
        self._user_id: str | None = None
        self._cookie: str | None = None
        self._owns_session = session is None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure we have an aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        """Close the session if we own it."""
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    async def login(self) -> bool:
        """Authenticate with aircontrolbase.com. Returns True on success."""
        session = await self._ensure_session()

        data = {
            "account": self._email,
            "password": self._password,
        }

        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/x-www-form-urlencoded",
            "Connection": "keep-alive",
        }

        try:
            async with session.post(
                f"{BASE_URL}{LOGIN_PATH}",
                data=data,
                headers=headers,
            ) as resp:
                if resp.status != 200:
                    raise AuthenticationError(
                        f"Login failed with HTTP status {resp.status}"
                    )

                # Extract session cookie
                cookies = resp.headers.getall("Set-Cookie", [])
                if cookies:
                    self._cookie = cookies[0]
                else:
                    # Try from cookie jar
                    for cookie in session.cookie_jar:
                        if cookie.key:
                            self._cookie = f"{cookie.key}={cookie.value}"
                            break

                response_data = await resp.json()

                if (
                    response_data
                    and "result" in response_data
                    and "id" in response_data["result"]
                ):
                    self._user_id = str(response_data["result"]["id"])
                    _LOGGER.debug("Login successful, user_id: %s", self._user_id)
                    return True

                _LOGGER.error("Login response missing user id: %s", response_data)
                raise AuthenticationError("Login response missing user id")

        except aiohttp.ClientError as err:
            raise AirControlBaseApiError(f"Connection error during login: {err}") from err

    async def _api_call(
        self,
        path: str,
        data: dict[str, Any] | None = None,
        retry_on_expired: bool = True,
    ) -> dict[str, Any]:
        """Make an authenticated API call."""
        if not self._user_id or not self._cookie:
            await self.login()

        session = await self._ensure_session()

        post_data: dict[str, Any] = {"userId": self._user_id}
        if data:
            post_data.update(data)

        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/x-www-form-urlencoded",
            "Connection": "keep-alive",
            "Cookie": self._cookie or "",
        }

        try:
            async with session.post(
                f"{BASE_URL}{path}",
                data=post_data,
                headers=headers,
            ) as resp:
                if resp.status != 200:
                    raise AirControlBaseApiError(
                        f"API call to {path} failed with HTTP {resp.status}"
                    )

                response_data = await resp.json()

                # Handle session expired
                if response_data.get("code") == SESSION_EXPIRED_CODE:
                    if retry_on_expired:
                        _LOGGER.debug("Session expired, re-authenticating")
                        await self.login()
                        return await self._api_call(
                            path, data, retry_on_expired=False
                        )
                    raise AuthenticationError("Session expired and re-login failed")

                return response_data

        except aiohttp.ClientError as err:
            raise AirControlBaseApiError(
                f"Connection error calling {path}: {err}"
            ) from err

    async def get_devices(self) -> list[dict[str, Any]]:
        """Fetch all devices from all areas.

        Returns a list of device dicts with keys:
            id, name, power, mode, setTemp, wind, swing, lock,
            factTemp, modeLockValue, coolLockValue, heatLockValue,
            windLockValue, unlock
        """
        response = await self._api_call(DETAILS_PATH)

        devices: list[dict[str, Any]] = []
        result = response.get("result")
        if not result:
            _LOGGER.warning("No result in device response: %s", response)
            return devices

        areas = result.get("areas", [])
        for area in areas:
            area_devices = area.get("data", [])
            for device in area_devices:
                devices.append(device)

        _LOGGER.debug("Found %d devices", len(devices))
        return devices

    async def control_device(self, device_state: dict[str, Any]) -> None:
        """Send a control command to a device.

        device_state should be a full device dict including the 'id' field.
        """
        control_json = json.dumps(device_state)

        data = {
            "control": control_json,
            "operation": control_json,
        }

        await self._api_call(CONTROL_PATH, data)
        _LOGGER.debug(
            "Controlled device %s: mode=%s, temp=%s, wind=%s, power=%s",
            device_state.get("id"),
            device_state.get("mode"),
            device_state.get("setTemp"),
            device_state.get("wind"),
            device_state.get("power"),
        )

    async def test_connection(self) -> bool:
        """Test the connection and credentials. Returns True on success."""
        try:
            await self.login()
            return True
        except (AirControlBaseApiError, AuthenticationError):
            return False
