"""The Midea M-Control (Cloud) integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .aircontrolbase import AirControlBaseApi, LocalApi
from .const import CONF_EMAIL, CONF_HOST, CONF_PASSWORD, DOMAIN
from .coordinator import MideaMControlCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Midea M-Control from a config entry."""
    session = async_get_clientsession(hass)

    cloud_api = AirControlBaseApi(
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
        session=session,
    )

    # Login to cloud
    await cloud_api.login()

    # Set up local API if host is configured
    local_api: LocalApi | None = None
    host = entry.data.get(CONF_HOST)
    if host:
        local_api = LocalApi(host=host, session=session)
        _LOGGER.info("Local CCM21-i polling enabled at %s", host)

    coordinator = MideaMControlCoordinator(hass, cloud_api, local_api)

    # Initial cloud fetch (discovers devices and builds addr mapping)
    initial_data = await coordinator.async_initial_cloud_fetch()
    coordinator.async_set_updated_data(initial_data)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
