"""Inverter settings exposed as select entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import SmartSolarClient, SmartSolarError
from .coordinator import SmartSolarConfigEntry, SmartSolarCoordinator
from .entity import SmartSolarEntity
from .parsing import match_option

ICONS = {
    "buzzer": "mdi:volume-high",
    "overload_bypass": "mdi:electric-switch",
    "output_volt": "mdi:flash",
    "ac_input_range": "mdi:transmission-tower",
    "output_source_priority": "mdi:source-branch",
    "charger_source_priority": "mdi:battery-charging",
    "battery_type": "mdi:car-battery",
    "battery_cut-off_volt": "mdi:battery-alert",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartSolarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a select entity for every setting the inverter reports."""
    data = entry.runtime_data
    coordinator = data.settings
    if coordinator is None:
        return

    known: set[str] = set()

    # Settings are discovered from the API, so add entities whenever new keys
    # appear (including after a failed first refresh).
    @callback
    def _add_new_settings() -> None:
        new = []
        for item in coordinator.data or []:
            key = item.get("key")
            if key and key not in known and item.get("options"):
                known.add(key)
                new.append(SmartSolarSettingSelect(coordinator, entry, data.client, key, item.get("label") or key))
        if new:
            async_add_entities(new)

    _add_new_settings()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_settings))


class SmartSolarSettingSelect(SmartSolarEntity[SmartSolarCoordinator], SelectEntity):
    """One inverter setting."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: SmartSolarCoordinator,
        entry: SmartSolarConfigEntry,
        client: SmartSolarClient,
        key: str,
        label: str,
    ) -> None:
        super().__init__(coordinator, entry, f"setting_{key}")
        self._client = client
        self._key = key
        self._attr_name = label
        self._attr_icon = ICONS.get(key, "mdi:cog")

    def _item(self) -> dict[str, Any] | None:
        return next((i for i in self.coordinator.data or [] if i.get("key") == self._key), None)

    @property
    def available(self) -> bool:
        return super().available and self._item() is not None

    @property
    def options(self) -> list[str]:
        item = self._item()
        return [str(o) for o in item.get("options", [])] if item else []

    @property
    def current_option(self) -> str | None:
        item = self._item()
        return match_option(item.get("value"), self.options) if item else None

    async def async_select_option(self, option: str) -> None:
        try:
            await self._client.set_setting(self._key, option)
        except SmartSolarError as err:
            raise HomeAssistantError(f"Could not set {self.name}: {err}") from err
        # Reflect the change now; the next scheduled settings poll confirms it.
        # We don't refresh immediately to conserve the API request budget.
        if item := self._item():
            item["value"] = option
        self.coordinator.async_update_listeners()
