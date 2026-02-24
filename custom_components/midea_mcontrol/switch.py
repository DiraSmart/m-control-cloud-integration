"""Switch platform for Midea M-Control integration.

Provides a Power switch for each AC unit so that voice assistants
(e.g. Alexa via Matter bridge) can use "turn on / turn off" commands.
Turning ON sets the unit to Cool mode; turning OFF powers it down.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MODE_COOL, POWER_OFF, POWER_ON
from .coordinator import MideaMControlCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities from a config entry."""
    coordinator: MideaMControlCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        MideaMControlPowerSwitch(coordinator, device_id, device_data)
        for device_id, device_data in coordinator.data.items()
    ]

    async_add_entities(entities, update_before_add=False)


class MideaMControlPowerSwitch(
    CoordinatorEntity[MideaMControlCoordinator], SwitchEntity
):
    """On/Off switch for a Midea M-Control AC unit."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MideaMControlCoordinator,
        device_id: str,
        device_data: dict[str, Any],
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{DOMAIN}_{device_id}_power"
        self._attr_name = "Power"
        device_name = device_data.get("name", f"AC {device_id}")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device_name,
            manufacturer="Midea",
            model="VRF AC Unit",
            via_device=(DOMAIN, "ccm21i"),
        )
        self._last_device_data: dict[str, Any] = device_data

    @property
    def _device_data(self) -> dict[str, Any]:
        """Get latest device data from coordinator."""
        if self.coordinator.data and self._device_id in self.coordinator.data:
            return self.coordinator.data[self._device_id]
        return self._last_device_data

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data and self._device_id in self.coordinator.data:
            self._last_device_data = self.coordinator.data[self._device_id]
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return True if the AC is on."""
        return self._device_data.get("power") == POWER_ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the AC on in Cool mode."""
        await self._send_control(power=POWER_ON, mode=MODE_COOL)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the AC off."""
        await self._send_control(power=POWER_OFF)

    async def _send_control(self, **overrides: Any) -> None:
        """Send a control command via the cloud API."""
        import copy

        state = self.coordinator.get_cloud_device_data(self._device_id)
        if not state:
            state = copy.deepcopy(self._device_data)
        state.update(overrides)

        self.coordinator.notify_command_sent()
        await self.coordinator.cloud_api.control_device(state)

        if self.coordinator.data:
            self.coordinator.data[self._device_id] = state
        self._last_device_data = state
        self.async_write_ha_state()
