"""Config flow for SmartSolar."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import (
    SmartSolarAuthError,
    SmartSolarClient,
    SmartSolarConnectionError,
    SmartSolarError,
    SmartSolarRateLimitError,
)
from .const import (
    CONF_ENABLE_CONTROL,
    CONF_HIDE_GRID_ALERTS,
    CONF_SCAN_INTERVAL,
    DEFAULT_ENABLE_CONTROL,
    DEFAULT_HIDE_GRID_ALERTS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

API_KEY_SCHEMA = vol.Schema(
    {vol.Required(CONF_API_KEY): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))}
)


async def _validate(hass: HomeAssistant, api_key: str) -> tuple[str | None, dict[str, str]]:
    """Return (device id, errors) for an API key."""
    client = SmartSolarClient(async_get_clientsession(hass), api_key)
    try:
        status = await client.get_status()
    except SmartSolarAuthError:
        return None, {"base": "invalid_auth"}
    except SmartSolarRateLimitError:
        return None, {"base": "rate_limited"}
    except SmartSolarConnectionError:
        return None, {"base": "cannot_connect"}
    except SmartSolarError:
        LOGGER.exception("Unexpected SmartSolar API response")
        return None, {"base": "unknown"}
    device_id = status.get("Dev_ID")
    if not device_id:
        return None, {"base": "unknown"}
    return str(device_id), {}


class SmartSolarConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SmartSolar."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            device_id, errors = await _validate(self.hass, api_key)
            if device_id:
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"SmartSolar {device_id}", data={CONF_API_KEY: api_key}
                )
        return self.async_show_form(step_id="user", data_schema=API_KEY_SCHEMA, errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            device_id, errors = await _validate(self.hass, api_key)
            if device_id:
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates={CONF_API_KEY: api_key}
                )
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=API_KEY_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> SmartSolarOptionsFlow:
        return SmartSolarOptionsFlow()


class SmartSolarOptionsFlow(OptionsFlow):
    """Polling and control options."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            user_input[CONF_SCAN_INTERVAL] = int(user_input[CONF_SCAN_INTERVAL])
            return self.async_create_entry(data=user_input)

        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL,
                        max=MAX_SCAN_INTERVAL,
                        step=1,
                        unit_of_measurement="s",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_HIDE_GRID_ALERTS,
                    default=options.get(CONF_HIDE_GRID_ALERTS, DEFAULT_HIDE_GRID_ALERTS),
                ): bool,
                vol.Required(
                    CONF_ENABLE_CONTROL,
                    default=options.get(CONF_ENABLE_CONTROL, DEFAULT_ENABLE_CONTROL),
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
