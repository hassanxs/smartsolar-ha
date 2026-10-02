"""Data update coordinators for SmartSolar."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SmartSolarAuthError, SmartSolarClient, SmartSolarError
from .const import DOMAIN, LOGGER


class SmartSolarCoordinator[_DataT](DataUpdateCoordinator[_DataT]):
    """Polls one SmartSolar endpoint on its own schedule."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        name: str,
        interval: timedelta,
        fetch: Callable[[], Awaitable[_DataT]],
    ) -> None:
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {name}",
            update_interval=interval,
        )
        self._fetch = fetch

    async def _async_update_data(self) -> _DataT:
        try:
            return await self._fetch()
        except SmartSolarAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except SmartSolarError as err:
            raise UpdateFailed(str(err)) from err


@dataclass
class SmartSolarData:
    """Runtime data stored on the config entry."""

    client: SmartSolarClient
    device_id: str
    status: SmartSolarCoordinator[dict[str, Any]]
    usage: SmartSolarCoordinator[dict[str, dict[str, Any]]]
    faults: SmartSolarCoordinator[list[dict[str, Any]]]
    settings: SmartSolarCoordinator[list[dict[str, Any]]] | None


type SmartSolarConfigEntry = ConfigEntry[SmartSolarData]
