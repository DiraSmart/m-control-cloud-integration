"""Data update coordinator for Midea M-Control."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .aircontrolbase import AirControlBaseApi, AirControlBaseApiError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class MideaMControlCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Coordinator to poll aircontrolbase.com for device states.

    Data is a dict keyed by device ID, with each value being the full device dict.
    """

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        api: AirControlBaseApi,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch data from the API."""
        try:
            devices = await self.api.get_devices()
        except AirControlBaseApiError as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err

        # Index devices by their ID for easy lookup
        return {device["id"]: device for device in devices if "id" in device}
