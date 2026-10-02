"""The SmartSolar integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SmartSolarClient
from .const import (
    CONF_ENABLE_CONTROL,
    CONF_HIDE_GRID_ALERTS,
    CONF_SCAN_INTERVAL,
    DEFAULT_ENABLE_CONTROL,
    DEFAULT_HIDE_GRID_ALERTS,
    DEFAULT_SCAN_INTERVAL,
    FAULTS_INTERVAL,
    SETTINGS_INTERVAL,
    USAGE_INTERVAL,
)
from .coordinator import SmartSolarConfigEntry, SmartSolarCoordinator, SmartSolarData

PLATFORMS = [Platform.SELECT, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: SmartSolarConfigEntry) -> bool:
    """Set up SmartSolar from a config entry."""
    client = SmartSolarClient(async_get_clientsession(hass), entry.data[CONF_API_KEY])
    options = entry.options
    hide_grid = options.get(CONF_HIDE_GRID_ALERTS, DEFAULT_HIDE_GRID_ALERTS)

    async def fetch_usage() -> dict:
        return {
            "today": await client.get_usage("today"),
            "month": await client.get_usage("this_month"),
        }

    status = SmartSolarCoordinator(
        hass,
        entry,
        "status",
        timedelta(seconds=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
        client.get_status,
    )
    usage = SmartSolarCoordinator(hass, entry, "usage", USAGE_INTERVAL, fetch_usage)
    faults = SmartSolarCoordinator(
        hass,
        entry,
        "faults",
        FAULTS_INTERVAL,
        lambda: client.get_faults("this_month", hide_grid),
    )
    settings = None
    if options.get(CONF_ENABLE_CONTROL, DEFAULT_ENABLE_CONTROL):
        settings = SmartSolarCoordinator(
            hass, entry, "settings", SETTINGS_INTERVAL, client.get_settings
        )

    # Only the real-time status is required for setup; the others become
    # available on their own schedule, so a failure there doesn't trigger
    # setup retries that would spend extra requests.
    await status.async_config_entry_first_refresh()
    await usage.async_refresh()
    await faults.async_refresh()
    if settings:
        await settings.async_refresh()

    entry.runtime_data = SmartSolarData(
        client=client,
        device_id=entry.unique_id or status.data.get("Dev_ID", entry.entry_id),
        status=status,
        usage=usage,
        faults=faults,
        settings=settings,
    )
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SmartSolarConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(hass: HomeAssistant, entry: SmartSolarConfigEntry) -> None:
    """Reload when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
