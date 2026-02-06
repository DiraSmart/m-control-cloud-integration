"""Config flow for Midea M-Control integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .aircontrolbase import AirControlBaseApi, AuthenticationError, AirControlBaseApiError
from .const import CONF_EMAIL, CONF_PASSWORD, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class MideaMControlConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Midea M-Control."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]

            # Prevent duplicate entries
            await self.async_set_unique_id(email.lower())
            self._abort_if_unique_id_configured()

            # Test credentials
            api = AirControlBaseApi(
                email=email,
                password=password,
                session=async_get_clientsession(self.hass),
            )

            try:
                success = await api.test_connection()
                if success:
                    return self.async_create_entry(
                        title=f"M-Control ({email})",
                        data={
                            CONF_EMAIL: email,
                            CONF_PASSWORD: password,
                        },
                    )
                errors["base"] = "invalid_auth"
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except AirControlBaseApiError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during config flow")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
