"""Sensors for SmartSolar."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .coordinator import SmartSolarConfigEntry, SmartSolarCoordinator
from .entity import SmartSolarEntity
from .parsing import parse_last_update, parse_number, parse_text

MAX_FAULTS_IN_ATTRIBUTES = 20


@dataclass(frozen=True, kw_only=True)
class SmartSolarSensorDescription(SensorEntityDescription):
    """Describes a SmartSolar sensor."""

    value_fn: Callable[[Any], StateType | datetime]
    attrs_fn: Callable[[Any], dict[str, Any]] | None = None


def _num(field: str, index: int = 0) -> Callable[[dict], float | None]:
    return lambda data: parse_number(data.get(field), index)


def _text(field: str) -> Callable[[dict], str | None]:
    return lambda data: parse_text(data.get(field))


def _usage(period: str, field: str) -> Callable[[dict], float | None]:
    return lambda data: parse_number((data.get(period) or {}).get(field))


def _voltage(key: str, field: str, name: str, **kwargs: Any) -> SmartSolarSensorDescription:
    return SmartSolarSensorDescription(
        key=key,
        name=name,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_num(field),
        **kwargs,
    )


def _current(key: str, field: str, name: str, **kwargs: Any) -> SmartSolarSensorDescription:
    return SmartSolarSensorDescription(
        key=key,
        name=name,
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_num(field),
        **kwargs,
    )


def _power(key: str, field: str, name: str, **kwargs: Any) -> SmartSolarSensorDescription:
    return SmartSolarSensorDescription(
        key=key,
        name=name,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_num(field),
        **kwargs,
    )


def _percent(key: str, field: str, name: str, **kwargs: Any) -> SmartSolarSensorDescription:
    return SmartSolarSensorDescription(
        key=key,
        name=name,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_num(field),
        **kwargs,
    )


def _frequency(key: str, field: str, name: str) -> SmartSolarSensorDescription:
    return SmartSolarSensorDescription(
        key=key,
        name=name,
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_num(field),
    )


def _temperature(key: str, index: int, name: str) -> SmartSolarSensorDescription:
    return SmartSolarSensorDescription(
        key=key,
        name=name,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_num("Inv_Temp", index),
    )


STATUS_SENSORS: tuple[SmartSolarSensorDescription, ...] = (
    # Solar
    _power("pv_power", "PV_Watt", "PV power", icon="mdi:solar-power"),
    _voltage("pv_voltage", "PV_Volt", "PV voltage", icon="mdi:solar-panel"),
    _current("pv_current", "PV_Amp", "PV current", icon="mdi:solar-panel"),
    _percent("pv_efficiency", "PV_Efi", "PV efficiency", icon="mdi:solar-power-variant"),
    # Grid (AC input)
    _voltage("grid_voltage", "AC_Volt", "Grid voltage", icon="mdi:transmission-tower"),
    _frequency("grid_frequency", "AC_Freq", "Grid frequency"),
    _power("grid_power", "AC_Watt", "Grid power", icon="mdi:transmission-tower"),
    _current("grid_current", "AC_Amp", "Grid current", icon="mdi:transmission-tower"),
    # Output / load
    _voltage("output_voltage", "Output_Volt", "Output voltage"),
    _frequency("output_frequency", "Output_Freq", "Output frequency"),
    _power("load_power", "Output_Load_W", "Load power", icon="mdi:home-lightning-bolt"),
    SmartSolarSensorDescription(
        key="load_apparent_power",
        name="Load apparent power",
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_num("Output_Load_VA"),
    ),
    _percent("load_percentage", "Output_Load_P", "Load percentage", icon="mdi:gauge"),
    _current("load_current", "Output_Load_A", "Load current"),
    # Battery
    SmartSolarSensorDescription(
        key="battery_level",
        name="Battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_num("Batt_Status"),
    ),
    _voltage("battery_voltage", "Batt_Volt", "Battery voltage"),
    _current("battery_charge_current", "Batt_Charge_A", "Battery charge current"),
    _power("battery_charge_power", "Batt_Charge_W", "Battery charge power", icon="mdi:battery-arrow-up"),
    _current("battery_discharge_current", "Batt_Discharge_A", "Battery discharge current"),
    _power(
        "battery_discharge_power", "Batt_Discharge_W", "Battery discharge power", icon="mdi:battery-arrow-down"
    ),
    SmartSolarSensorDescription(
        key="battery_charge_mode",
        name="Battery charge mode",
        icon="mdi:battery-charging",
        value_fn=_text("Batt_Charg_Mode"),
    ),
    # Inverter
    SmartSolarSensorDescription(
        key="inverter_mode", name="Inverter mode", icon="mdi:sine-wave", value_fn=_text("Inv_Mode")
    ),
    _temperature("inverter_temperature", 0, "Inverter temperature"),
    _temperature("inverter_temperature_2", 1, "Inverter temperature 2"),
    _percent("fan_speed", "Inv_Fan", "Fan speed", icon="mdi:fan", entity_category=EntityCategory.DIAGNOSTIC),
    SmartSolarSensorDescription(
        key="device_error",
        name="Device error",
        icon="mdi:alert-circle-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_text("Dev_Error"),
    ),
    SmartSolarSensorDescription(
        key="last_update",
        name="Last update",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: parse_last_update(data.get("Last_Update"), dt_util.get_default_time_zone()),
    ),
)


# (key suffix, API field, name, icon) for energy totals reported by usage.php
_ENERGY_FIELDS = (
    ("pv_energy", "T_PV_Watt", "Solar energy", "mdi:solar-power"),
    ("pv_battery_charge_energy", "T_PV_Batt_Charge", "Solar to battery energy", "mdi:battery-arrow-up"),
    ("grid_battery_charge_energy", "T_Grid_Batt_Charge", "Grid to battery energy", "mdi:battery-arrow-up"),
    ("battery_load_energy", "T_Battery_Load", "Battery to load energy", "mdi:battery-arrow-down"),
    ("grid_load_energy", "T_Grid_Load", "Grid to load energy", "mdi:transmission-tower-export"),
    ("load_energy", "T_Output_Load", "Load energy", "mdi:home-lightning-bolt"),
)
_PERIODS = (("today", "today"), ("month", "this month"))


def _usage_sensors() -> tuple[SmartSolarSensorDescription, ...]:
    sensors: list[SmartSolarSensorDescription] = []
    for period, label in _PERIODS:
        for suffix, field, name, icon in _ENERGY_FIELDS:
            # Totals reset daily/monthly; TOTAL_INCREASING handles the reset.
            sensors.append(
                SmartSolarSensorDescription(
                    key=f"{period}_{suffix}",
                    name=f"{name} {label}",
                    icon=icon,
                    device_class=SensorDeviceClass.ENERGY,
                    native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                    state_class=SensorStateClass.TOTAL_INCREASING,
                    suggested_display_precision=2,
                    value_fn=_usage(period, field),
                )
            )
        sensors += [
            SmartSolarSensorDescription(
                key=f"{period}_peak_pv_power",
                name=f"Peak PV power {label}",
                icon="mdi:solar-power",
                device_class=SensorDeviceClass.POWER,
                native_unit_of_measurement=UnitOfPower.WATT,
                value_fn=_usage(period, "T_Peak_PV"),
            ),
            SmartSolarSensorDescription(
                key=f"{period}_peak_load_power",
                name=f"Peak load power {label}",
                icon="mdi:home-lightning-bolt",
                device_class=SensorDeviceClass.POWER,
                native_unit_of_measurement=UnitOfPower.WATT,
                value_fn=_usage(period, "T_Peak_Load"),
            ),
            SmartSolarSensorDescription(
                key=f"{period}_inverter_efficiency",
                name=f"Inverter efficiency {label}",
                icon="mdi:percent",
                native_unit_of_measurement=PERCENTAGE,
                value_fn=_usage(period, "T_Inverter_Efi"),
            ),
            SmartSolarSensorDescription(
                key=f"{period}_savings",
                name=f"Savings {label}",
                icon="mdi:cash",
                device_class=SensorDeviceClass.MONETARY,
                native_unit_of_measurement="PKR",
                value_fn=_usage(period, "T_Savings"),
            ),
            SmartSolarSensorDescription(
                key=f"{period}_trees_planted",
                name=f"Trees planted equivalent {label}",
                icon="mdi:tree",
                suggested_display_precision=3,
                value_fn=_usage(period, "T_Tree_Plant"),
            ),
        ]
    return tuple(sensors)


USAGE_SENSORS = _usage_sensors()


def _fault_attributes(faults: list[dict[str, Any]]) -> dict[str, Any]:
    recent = faults[-MAX_FAULTS_IN_ATTRIBUTES:]
    latest = faults[-1] if faults else None
    return {
        "latest_fault": latest.get("f_fault") if latest else None,
        "latest_fault_date": latest.get("f_date") if latest else None,
        "faults": [
            {
                "date": f.get("f_date"),
                "start": f.get("f_t_start"),
                "end": f.get("f_t_end"),
                "fault": f.get("f_fault"),
            }
            for f in recent
        ],
    }


FAULT_SENSORS: tuple[SmartSolarSensorDescription, ...] = (
    SmartSolarSensorDescription(
        key="faults_this_month",
        name="Faults this month",
        icon="mdi:alert",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=len,
        attrs_fn=_fault_attributes,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartSolarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SmartSolar sensors."""
    data = entry.runtime_data
    async_add_entities(
        [SmartSolarSensor(data.status, entry, d) for d in STATUS_SENSORS]
        + [SmartSolarSensor(data.usage, entry, d) for d in USAGE_SENSORS]
        + [SmartSolarSensor(data.faults, entry, d) for d in FAULT_SENSORS]
    )


class SmartSolarSensor(SmartSolarEntity[SmartSolarCoordinator], SensorEntity):
    """A SmartSolar sensor."""

    entity_description: SmartSolarSensorDescription

    def __init__(
        self,
        coordinator: SmartSolarCoordinator,
        entry: SmartSolarConfigEntry,
        description: SmartSolarSensorDescription,
    ) -> None:
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType | datetime:
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None or self.coordinator.data is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)
