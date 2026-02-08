"""Config flow for Midea M-Control integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .aircontrolbase import (
    AirControlBaseApi,
    AirControlBaseApiError,
    AuthenticationError,
    LocalApi,
)
from .const import CONF_EMAIL, CONF_HOST, CONF_PASSWORD, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_HOST): str,
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
            host = user_input.get(CONF_HOST, "").strip()

            # Prevent duplicate entries
            await self.async_set_unique_id(email.lower())
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass)

            # Test cloud credentials
            api = AirControlBaseApi(
                email=email,
                password=password,
                session=session,
            )

            try:
                success = await api.test_connection()
                if not success:
                    errors["base"] = "invalid_auth"
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except AirControlBaseApiError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during config flow")
                errors["base"] = "unknown"

            # Test local connection if provided
            if not errors and host:
                local_api = LocalApi(host=host, session=session)
                local_ok = await local_api.test_connection()
                if not local_ok:
                    errors["base"] = "local_unreachable"

            if not errors:
                entry_data = {
                    CONF_EMAIL: email,
                    CONF_PASSWORD: password,
                }
                if host:
                    entry_data[CONF_HOST] = host

                return self.async_create_entry(
                    title=f"M-Control ({email})",
                    data=entry_data,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
