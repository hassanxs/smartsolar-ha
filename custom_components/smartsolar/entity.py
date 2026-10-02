"""Base entity for SmartSolar."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BASE_URL, DOMAIN, MANUFACTURER
from .coordinator import SmartSolarConfigEntry, SmartSolarCoordinator


class SmartSolarEntity[_CoordT: SmartSolarCoordinator](CoordinatorEntity[_CoordT]):
    """An entity belonging to one SmartSolar inverter."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: _CoordT, entry: SmartSolarConfigEntry, key: str) -> None:
        super().__init__(coordinator)
        device_id = entry.runtime_data.device_id
        self._attr_unique_id = f"{device_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            manufacturer=MANUFACTURER,
            name="SmartSolar Inverter",
            serial_number=device_id,
            configuration_url=BASE_URL,
        )
