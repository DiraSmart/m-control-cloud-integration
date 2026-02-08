"""Data update coordinator for Midea M-Control."""

from __future__ import annotations

from datetime import timedelta
import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .aircontrolbase import (
    AirControlBaseApi,
    AirControlBaseApiError,
    LocalApi,
    LocalDeviceState,
)
from .const import DEFAULT_CLOUD_SCAN_INTERVAL, DEFAULT_LOCAL_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

# After sending a control command, ignore status polls for this many seconds
# to prevent the old state from overwriting the optimistic update.
COMMAND_COOLDOWN_SECONDS = 15


class MideaMControlCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Coordinator that polls locally for fast status and uses cloud for control.

    Data is a dict keyed by device ID, with each value being the full device dict
    in cloud-compatible format.
    """

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        cloud_api: AirControlBaseApi,
        local_api: LocalApi | None = None,
    ) -> None:
        """Initialize the coordinator."""
        self._local_api = local_api
        self.cloud_api = cloud_api

        # Use fast interval if local, slower if cloud-only
        interval = (
            DEFAULT_LOCAL_SCAN_INTERVAL
            if local_api
            else DEFAULT_CLOUD_SCAN_INTERVAL
        )

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )

        # Mapping: cloud device ID -> local addr (built during initial cloud fetch)
        self._id_to_addr: dict[str, int] = {}
        # Store cloud device data for control operations (preserves all fields)
        self._cloud_device_cache: dict[str, dict[str, Any]] = {}
        # Track last command time to avoid overwriting optimistic state
        self._last_command_time: float = 0

    @property
    def has_local(self) -> bool:
        """Return True if local polling is configured."""
        return self._local_api is not None

    def notify_command_sent(self) -> None:
        """Record that a control command was just sent.

        This starts a cooldown period during which polls are skipped
        so the optimistic state is preserved.
        """
        self._last_command_time = time.monotonic()

    def _in_cooldown(self) -> bool:
        """Return True if we're in the post-command cooldown period."""
        if self._last_command_time == 0:
            return False
        elapsed = time.monotonic() - self._last_command_time
        return elapsed < COMMAND_COOLDOWN_SECONDS

    async def async_initial_cloud_fetch(self) -> dict[str, dict[str, Any]]:
        """Fetch initial cloud data and build addr mapping.

        Must be called once during setup before the first local poll.
        """
        try:
            devices = await self.cloud_api.get_devices()
        except AirControlBaseApiError as err:
            raise UpdateFailed(f"Error fetching cloud data: {err}") from err

        result: dict[str, dict[str, Any]] = {}
        for device in devices:
            if "id" in device:
                device_id = device["id"]
                result[device_id] = device
                self._cloud_device_cache[device_id] = device

        # Build addr mapping if local is available
        if self._local_api:
            await self._build_addr_mapping(result)

        return result

    async def _build_addr_mapping(
        self, cloud_devices: dict[str, dict[str, Any]]
    ) -> None:
        """Build mapping between cloud IDs and local addresses.

        Matches by comparing setTemp and factTemp between cloud and local.
        """
        if not self._local_api:
            return

        local_states = await self._local_api.get_status()
        if not local_states:
            _LOGGER.warning("No local devices found for addr mapping")
            return

        cloud_list = list(cloud_devices.items())
        local_list = sorted(local_states, key=lambda x: x.addr)

        # Strategy 1: Match by temperature values
        matched_cloud: set[str] = set()
        matched_local: set[int] = set()

        for device_id, cloud_data in cloud_list:
            cloud_temp = cloud_data.get("factTemp")
            cloud_set = cloud_data.get("setTemp")

            for local_state in local_list:
                if local_state.addr in matched_local:
                    continue

                local_temp = str(local_state.temperature)
                local_set = str(local_state.temperature_setpoint)

                if cloud_temp == local_temp and cloud_set == local_set:
                    self._id_to_addr[device_id] = local_state.addr
                    matched_cloud.add(device_id)
                    matched_local.add(local_state.addr)
                    _LOGGER.debug(
                        "Mapped cloud ID %s -> local addr %d (by temp match)",
                        device_id,
                        local_state.addr,
                    )
                    break

        # Strategy 2: Match remaining by order
        unmatched_cloud = [
            (did, d) for did, d in cloud_list if did not in matched_cloud
        ]
        unmatched_local = [s for s in local_list if s.addr not in matched_local]

        for (device_id, _), local_state in zip(unmatched_cloud, unmatched_local):
            self._id_to_addr[device_id] = local_state.addr
            _LOGGER.debug(
                "Mapped cloud ID %s -> local addr %d (by order)",
                device_id,
                local_state.addr,
            )

        _LOGGER.info(
            "Address mapping complete: %d devices mapped", len(self._id_to_addr)
        )

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch data - locally if available, cloud as fallback.

        Skips polling during cooldown after a command to preserve
        the optimistic state shown in the UI.
        """
        if self._in_cooldown():
            _LOGGER.debug(
                "Skipping poll (%.0fs remaining in cooldown)",
                COMMAND_COOLDOWN_SECONDS
                - (time.monotonic() - self._last_command_time),
            )
            # Return current data unchanged
            return self.data or {}

        if self._local_api and self._id_to_addr:
            return await self._update_from_local()
        return await self._update_from_cloud()

    async def _update_from_local(self) -> dict[str, dict[str, Any]]:
        """Fast update using local CCM21-i API."""
        try:
            local_states = await self._local_api.get_status()
        except Exception as err:
            _LOGGER.warning("Local poll failed, falling back to cloud: %s", err)
            return await self._update_from_cloud()

        # Build addr -> local state lookup
        addr_to_state: dict[int, LocalDeviceState] = {
            s.addr: s for s in local_states
        }

        result: dict[str, dict[str, Any]] = {}

        for device_id, addr in self._id_to_addr.items():
            # Start from cached cloud data (has id, name, lock values, etc.)
            cached = self._cloud_device_cache.get(device_id, {})
            device_data = dict(cached)

            # Overlay local status if available
            local_state = addr_to_state.get(addr)
            if local_state:
                device_data.update(local_state.to_cloud_format())

            result[device_id] = device_data

        return result

    async def _update_from_cloud(self) -> dict[str, dict[str, Any]]:
        """Fallback update using cloud API."""
        try:
            devices = await self.cloud_api.get_devices()
        except AirControlBaseApiError as err:
            raise UpdateFailed(f"Error fetching cloud data: {err}") from err

        result: dict[str, dict[str, Any]] = {}
        for device in devices:
            if "id" in device:
                device_id = device["id"]
                result[device_id] = device
                self._cloud_device_cache[device_id] = device

        return result

    def get_cloud_device_data(self, device_id: str) -> dict[str, Any]:
        """Get the full cached cloud data for a device (for control commands)."""
        return dict(self._cloud_device_cache.get(device_id, {}))
