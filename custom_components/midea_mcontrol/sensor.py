"""Sensor platform for Midea M-Control integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MideaMControlCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up temperature sensor entities from a config entry."""
    coordinator: MideaMControlCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        MideaMControlTemperatureSensor(coordinator, device_id, device_data)
        for device_id, device_data in coordinator.data.items()
    ]

    async_add_entities(entities, update_before_add=False)


class MideaMControlTemperatureSensor(
    CoordinatorEntity[MideaMControlCoordinator], SensorEntity
):
    """Temperature sensor for a Midea M-Control AC unit."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        coordinator: MideaMControlCoordinator,
        device_id: str,
        device_data: dict[str, Any],
    ) -> None:
        """Initialize the temperature sensor."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{DOMAIN}_{device_id}_temperature"
        self._attr_name = f"{device_data.get('name', f'AC {device_id}')} Temperature"
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
    def native_value(self) -> float | None:
        """Return the current temperature."""
        data = self._device_data
        fact_temp = data.get("factTemp")
        if fact_temp is not None:
            try:
                return float(fact_temp)
            except (ValueError, TypeError):
                return None
        return None
