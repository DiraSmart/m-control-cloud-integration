"""Climate platform for Midea M-Control integration."""

from __future__ import annotations

import copy
import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.climate.const import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    SWING_OFF,
    SWING_ON,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    MAX_TEMP,
    MIN_TEMP,
    MODE_AUTO,
    MODE_COOL,
    MODE_DRY,
    MODE_FAN,
    MODE_HEAT,
    POWER_OFF,
    POWER_ON,
    WIND_AUTO,
    WIND_HIGH,
    WIND_LOW,
    WIND_MID,
)
from .coordinator import MideaMControlCoordinator

_LOGGER = logging.getLogger(__name__)

# Mapping from cloud API mode strings to HA HVACMode
CLOUD_TO_HVAC_MODE: dict[str, HVACMode] = {
    MODE_COOL: HVACMode.COOL,
    MODE_HEAT: HVACMode.HEAT,
    MODE_AUTO: HVACMode.AUTO,
    MODE_FAN: HVACMode.FAN_ONLY,
    MODE_DRY: HVACMode.DRY,
}

# Reverse mapping
HVAC_MODE_TO_CLOUD: dict[HVACMode, str] = {v: k for k, v in CLOUD_TO_HVAC_MODE.items()}

# Mapping from cloud API wind strings to HA fan modes
CLOUD_TO_FAN_MODE: dict[str, str] = {
    WIND_AUTO: FAN_AUTO,
    WIND_LOW: FAN_LOW,
    WIND_MID: FAN_MEDIUM,
    WIND_HIGH: FAN_HIGH,
}

# Reverse mapping
FAN_MODE_TO_CLOUD: dict[str, str] = {v: k for k, v in CLOUD_TO_FAN_MODE.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up climate entities from a config entry."""
    coordinator: MideaMControlCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        MideaMControlClimate(coordinator, device_id, device_data)
        for device_id, device_data in coordinator.data.items()
    ]

    async_add_entities(entities, update_before_add=False)


class MideaMControlClimate(CoordinatorEntity[MideaMControlCoordinator], ClimateEntity):
    """Representation of a Midea M-Control AC unit."""

    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = MIN_TEMP
    _attr_max_temp = MAX_TEMP
    _attr_target_temperature_step = 1.0
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.COOL,
        HVACMode.HEAT,
        HVACMode.AUTO,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
    ]
    _attr_fan_modes = [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]
    _attr_swing_modes = [SWING_ON, SWING_OFF]

    def __init__(
        self,
        coordinator: MideaMControlCoordinator,
        device_id: str,
        device_data: dict[str, Any],
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{DOMAIN}_{device_id}"
        self._attr_name = "Climate"
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
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC mode."""
        data = self._device_data
        power = data.get("power", POWER_OFF)
        if power != POWER_ON:
            return HVACMode.OFF

        cloud_mode = data.get("mode", MODE_AUTO)
        return CLOUD_TO_HVAC_MODE.get(cloud_mode, HVACMode.AUTO)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        data = self._device_data
        fact_temp = data.get("factTemp")
        if fact_temp is not None:
            try:
                return float(fact_temp)
            except (ValueError, TypeError):
                return None
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        data = self._device_data
        set_temp = data.get("setTemp")
        if set_temp is not None:
            try:
                return float(set_temp)
            except (ValueError, TypeError):
                return None
        return None

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan mode."""
        data = self._device_data
        cloud_wind = data.get("wind", WIND_AUTO)
        return CLOUD_TO_FAN_MODE.get(cloud_wind, FAN_AUTO)

    @property
    def swing_mode(self) -> str | None:
        """Return the current swing mode."""
        data = self._device_data
        swing = data.get("swing", "")
        # The cloud API returns swing state as a string
        if swing and swing not in ("0", "off", "n", ""):
            return SWING_ON
        return SWING_OFF

    async def _send_control(self, **overrides: Any) -> None:
        """Build a device state dict and send it via cloud API."""
        # Use cached cloud data as base (has all fields the API expects)
        state = self.coordinator.get_cloud_device_data(self._device_id)
        if not state:
            state = copy.deepcopy(self._device_data)
        state.update(overrides)

        # Start cooldown BEFORE sending so polls don't overwrite
        self.coordinator.notify_command_sent()

        await self.coordinator.cloud_api.control_device(state)

        # Optimistically update local state - this stays visible
        # for 15 seconds until the cooldown expires and real data is polled
        if self.coordinator.data:
            self.coordinator.data[self._device_id] = state
        self._last_device_data = state
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            await self._send_control(power=POWER_OFF)
        else:
            cloud_mode = HVAC_MODE_TO_CLOUD.get(hvac_mode, MODE_AUTO)
            await self._send_control(power=POWER_ON, mode=cloud_mode)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        overrides: dict[str, Any] = {"setTemp": str(int(temperature))}

        # If HVAC mode is also provided, set it too
        hvac_mode = kwargs.get("hvac_mode")
        if hvac_mode is not None:
            if hvac_mode == HVACMode.OFF:
                overrides["power"] = POWER_OFF
            else:
                overrides["power"] = POWER_ON
                overrides["mode"] = HVAC_MODE_TO_CLOUD.get(hvac_mode, MODE_AUTO)

        await self._send_control(**overrides)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode."""
        cloud_wind = FAN_MODE_TO_CLOUD.get(fan_mode, WIND_AUTO)
        await self._send_control(wind=cloud_wind)

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set the swing mode."""
        swing_value = "1" if swing_mode == SWING_ON else "0"
        await self._send_control(swing=swing_value)

    async def async_turn_on(self) -> None:
        """Turn the AC on."""
        await self._send_control(power=POWER_ON)

    async def async_turn_off(self) -> None:
        """Turn the AC off."""
        await self._send_control(power=POWER_OFF)
