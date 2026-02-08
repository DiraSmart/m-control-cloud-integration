"""API client for aircontrolbase.com (Midea M-Control cloud) and local CCM21-i."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import aiohttp

from .const import (
    BASE_URL,
    CONTROL_PATH,
    DETAILS_PATH,
    LOCAL_FAN_AUTO,
    LOCAL_FAN_HIGH,
    LOCAL_FAN_LOW,
    LOCAL_FAN_MEDIUM,
    LOCAL_FAN_OFF,
    LOCAL_MODE_AUTO,
    LOCAL_MODE_COOL,
    LOCAL_MODE_DRY,
    LOCAL_MODE_FAN,
    LOCAL_MODE_HEAT,
    LOCAL_MODE_OFF,
    LOCAL_STATUS_ENDPOINT,
    LOGIN_PATH,
    MODE_AUTO,
    MODE_COOL,
    MODE_DRY,
    MODE_FAN,
    MODE_HEAT,
    POWER_OFF,
    POWER_ON,
    SESSION_EXPIRED_CODE,
    WIND_AUTO,
    WIND_HIGH,
    WIND_LOW,
    WIND_MID,
)

_LOGGER = logging.getLogger(__name__)

# Map local integer modes to cloud string modes
LOCAL_MODE_TO_CLOUD = {
    LOCAL_MODE_COOL: MODE_COOL,
    LOCAL_MODE_HEAT: MODE_HEAT,
    LOCAL_MODE_DRY: MODE_DRY,
    LOCAL_MODE_FAN: MODE_FAN,
    LOCAL_MODE_OFF: None,  # Off is represented by power="n"
    LOCAL_MODE_AUTO: MODE_AUTO,
}

# Map local integer fan to cloud string fan
LOCAL_FAN_TO_CLOUD = {
    LOCAL_FAN_AUTO: WIND_AUTO,
    LOCAL_FAN_LOW: WIND_LOW,
    LOCAL_FAN_MEDIUM: WIND_MID,
    LOCAL_FAN_HIGH: WIND_HIGH,
    LOCAL_FAN_OFF: WIND_AUTO,
}


class AirControlBaseApiError(Exception):
    """Base exception for API errors."""


class AuthenticationError(AirControlBaseApiError):
    """Authentication failed."""


@dataclass
class LocalDeviceState:
    """Parsed state of one AC unit from local CCM21-i hex data."""

    addr: int
    ac_mode: int
    fan_mode: int
    temperature: int  # current room temp
    temperature_setpoint: int
    is_swing_on: bool
    error_code: int
    is_on: bool

    def to_cloud_format(self) -> dict[str, Any]:
        """Convert local state to cloud-compatible dict for merging."""
        mode = LOCAL_MODE_TO_CLOUD.get(self.ac_mode, MODE_AUTO)
        wind = LOCAL_FAN_TO_CLOUD.get(self.fan_mode, WIND_AUTO)
        power = POWER_OFF if not self.is_on else POWER_ON

        return {
            "power": power,
            "mode": mode or MODE_AUTO,
            "setTemp": str(self.temperature_setpoint),
            "wind": wind,
            "factTemp": str(self.temperature),
            "swing": "1" if self.is_swing_on else "0",
        }


def parse_hex_status(addr: int, hex_data: str) -> LocalDeviceState | None:
    """Parse 7-byte hex string from CCM21-i into a LocalDeviceState."""
    if hex_data == "-" or len(hex_data) < 14:
        return None

    hex_clean = hex_data.strip(",").strip()
    try:
        raw = bytes.fromhex(hex_clean)
    except ValueError:
        _LOGGER.warning("Invalid hex data for addr %d: %s", addr, hex_data)
        return None

    if len(raw) < 7:
        return None

    # Byte 3: ac_mode and fan_mode
    byte3 = raw[3]
    ac_mode = (byte3 >> 2) & 7
    fan_mode = (byte3 >> 5) & 7
    is_on = (byte3 & 1) != 0 or ac_mode != LOCAL_MODE_OFF

    # Byte 4: swing and setpoint
    byte4 = raw[4]
    is_swing_on = (byte4 >> 1) & 1 != 0
    temperature_setpoint = (byte4 >> 3) & 0x1F

    # Byte 2: error code
    byte2 = raw[2]
    error_code = (byte2 >> 2) & 0x3F

    # Byte 6: current temperature (signed)
    byte6 = raw[6]
    temperature = byte6 if byte6 < 128 else byte6 - 256

    # Determine power state: mode 4 = OFF
    is_on = ac_mode != LOCAL_MODE_OFF

    return LocalDeviceState(
        addr=addr,
        ac_mode=ac_mode,
        fan_mode=fan_mode,
        temperature=temperature,
        temperature_setpoint=temperature_setpoint,
        is_swing_on=is_swing_on,
        error_code=error_code,
        is_on=is_on,
    )


class LocalApi:
    """Client for the local CCM21-i HTTP API."""

    def __init__(
        self,
        host: str,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize the local API client."""
        self._host = host
        self._session = session
        self._owns_session = session is None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure we have an aiohttp session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=10)
            self._session = aiohttp.ClientSession(timeout=timeout)
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        """Close the session if we own it."""
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    async def get_status(self) -> list[LocalDeviceState]:
        """Fetch all AC statuses from the local CCM21-i device."""
        session = await self._ensure_session()
        url = f"http://{self._host}{LOCAL_STATUS_ENDPOINT}"

        try:
            async with session.post(
                url,
                data={"_web_cmd": "get_mbdata_all", "_ajax": "1"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    _LOGGER.warning("Local API returned HTTP %d", resp.status)
                    return []

                data = await resp.json(content_type=None)

        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.warning("Local API error: %s", err)
            return []

        devices: list[LocalDeviceState] = []
        for entry in data:
            addr = entry.get("addr")
            hex_data = entry.get("Data", "-")
            if addr is None or hex_data == "-":
                continue

            state = parse_hex_status(addr, hex_data)
            if state is not None:
                devices.append(state)

        _LOGGER.debug("Local poll found %d active AC units", len(devices))
        return devices

    async def test_connection(self) -> bool:
        """Test if the local device is reachable."""
        try:
            devices = await self.get_status()
            return True  # If we got a response at all, it's reachable
        except Exception:
            return False


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
