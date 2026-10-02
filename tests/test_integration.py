"""Tests for the SmartSolar integration, using the sample payloads from the API docs."""

from __future__ import annotations

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import entity_registry as er

from custom_components.smartsolar import api
from custom_components.smartsolar.const import DOMAIN

BASE = "https://smartsolar.net.pk/api/inverter"
DEV_ID = "FFFFFFFFFFFF"

STATUS = {
    "status": 200,
    "message": "Device fetched successfully",
    "data": {
        "Dev_Error": "No Error",
        "Dev_ID": DEV_ID,
        "AC_Volt": "238.5 V",
        "Output_Volt": "229.9 V",
        "AC_Freq": "50.2 HZ",
        "Output_Freq": "50.2 HZ",
        "PV_Volt": "126.6 V",
        "PV_Watt": "1173 W",
        "PV_Amp": "9.2 A",
        "Inv_Temp": "48 C, 43 C",
        "AC_Watt": "0 W",
        "AC_Amp": "0 A",
        "PV_Efi": "39 %",
        "Output_Load_W": "884 W",
        "Output_Load_VA": "1011 VA",
        "Output_Load_P": "39 %",
        "Output_Load_A": "4.4 A",
        "Batt_Volt": "27.10 V",
        "Batt_Status": "97 %",
        "Batt_Charge_A": "9 A",
        "Batt_Charge_W": "244 W",
        "Batt_Discharge_A": "0 A",
        "Batt_Discharge_W": "0 W",
        "Batt_Charg_Mode": "Float",
        "Inv_Fan": "82 %",
        "Inv_Mode": "Solar Mode",
        "Last_Update": "Update: 12:00 12-Apr-25",
    },
}
USAGE_TODAY = {
    "status": 200,
    "dev_id": DEV_ID,
    "data": {
        "Dev_Notice": None,
        "T_Inverter_Efi": "55.01 %",
        "T_Peak_PV": "1207 W",
        "T_Peak_Load": "916 W",
        "T_PV_Watt": "3.90 KWh",
        "T_PV_Batt_Charge": "2.11 KWh",
        "T_Grid_Batt_Charge": "0.00 KWh",
        "T_Battery_Load": "0.17 KWh",
        "T_Grid_Load": "0.42 KWh",
        "T_Output_Load": "2.47 KWh",
        "T_Tree_Plant": "0.046 Tree(s)",
        "T_Savings": "253 PKR",
    },
}
USAGE_MONTH = {"status": 200, "dev_id": DEV_ID, "data": {"Dev_Notice": "No Device Usage Found"}}
FAULTS = {
    "status": 200,
    "dev_id": DEV_ID,
    "data": {
        "dev_fault": [
            {"f_date": "15 April 2025", "f_t_start": "13:16", "f_t_end": "13:18", "f_fault": "Alert: Grid Line Fail"}
        ]
    },
}
SETTINGS = {
    "status": 200,
    "dev_id": DEV_ID,
    "data": [
        {"key": "output_volt", "label": "Output Volt", "value": "230.0", "options": ["220", "230", "240"]},
        {
            "key": "output_source_priority",
            "label": "Output Source Priority",
            "value": "SBU",
            "options": ["Utility", "Solar", "SBU"],
        },
    ],
}


@pytest.fixture(autouse=True)
def reset_limiters():
    api._LIMITERS.clear()
    yield
    api._LIMITERS.clear()


def mock_api(aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.get(f"{BASE}/status.php", json=STATUS)
    aioclient_mock.get(f"{BASE}/usage.php", params={"period": "today"}, json=USAGE_TODAY)
    aioclient_mock.get(f"{BASE}/usage.php", params={"period": "this_month"}, json=USAGE_MONTH)
    aioclient_mock.get(f"{BASE}/fault.php", json=FAULTS)
    aioclient_mock.get(f"{BASE}/isetting.php", json=SETTINGS)
    aioclient_mock.post(f"{BASE}/isetting.php", json={"status": 200, "message": "ok", "dev_id": DEV_ID})


async def setup_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DEV_ID, data={CONF_API_KEY: "secret"})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def entity_id(hass: HomeAssistant, platform: str, key: str) -> str:
    return er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{DEV_ID}_{key}")


async def test_config_flow(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    mock_api(aioclient_mock)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_API_KEY: " secret "})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == DEV_ID
    assert result["data"] == {CONF_API_KEY: "secret"}
    assert aioclient_mock.mock_calls[0][3]["X-API-KEY"] == "secret"


async def test_config_flow_invalid_key(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.get(f"{BASE}/status.php", status=401, json={"error": "Invalid API key"})
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_API_KEY: "bad"})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_sensors(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    mock_api(aioclient_mock)
    entry = await setup_entry(hass)
    assert entry.state is ConfigEntryState.LOADED

    def state(key: str):
        return hass.states.get(entity_id(hass, "sensor", key))

    assert state("pv_power").state == "1173.0"
    assert state("grid_frequency").state == "50.2"
    assert state("battery_level").state == "97.0"
    assert state("inverter_temperature_2").state == "43.0"
    assert state("inverter_mode").state == "Solar Mode"
    assert state("last_update").state.startswith("2025-04-12")
    assert state("today_pv_energy").state == "3.9"
    assert state("today_savings").state == "253.0"
    assert state("month_pv_energy").state == "unknown"  # "No Device Usage Found"
    faults = state("faults_this_month")
    assert faults.state == "1"
    assert faults.attributes["latest_fault"] == "Alert: Grid Line Fail"


async def test_select(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    mock_api(aioclient_mock)
    await setup_entry(hass)
    volt = entity_id(hass, "select", "setting_output_volt")
    assert hass.states.get(volt).state == "230"

    priority = entity_id(hass, "select", "setting_output_source_priority")
    calls_before = aioclient_mock.call_count
    await hass.services.async_call(
        "select", "select_option", {"entity_id": priority, "option": "Solar"}, blocking=True
    )
    assert aioclient_mock.call_count == calls_before + 1
    method, url, body, _ = aioclient_mock.mock_calls[-1]
    assert method == "POST" and body == {"key": "output_source_priority", "value": "Solar"}
    assert hass.states.get(priority).state == "Solar"


async def test_select_rejected(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    mock_api(aioclient_mock)
    await setup_entry(hass)
    # The first registered mock that matches wins, so register the rejection first.
    aioclient_mock.clear_requests()
    aioclient_mock.post(
        f"{BASE}/isetting.php", json={"status": 200, "dev_notice": "Not allowed", "dev_id": DEV_ID}
    )
    mock_api(aioclient_mock)

    volt = entity_id(hass, "select", "setting_output_volt")
    with pytest.raises(HomeAssistantError, match="Not allowed"):
        await hass.services.async_call(
            "select", "select_option", {"entity_id": volt, "option": "240"}, blocking=True
        )
    assert hass.states.get(volt).state == "230"


async def test_rate_limit_blocks_further_requests(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(
        f"{BASE}/status.php",
        status=403,
        json={"error": "Device access temporarily disabled for exceeding rate limit"},
    )
    client = api.SmartSolarClient(async_get_clientsession(hass), "k")
    with pytest.raises(api.SmartSolarRateLimitError):
        await client.get_status()
    with pytest.raises(api.SmartSolarRateLimitError, match="Paused"):
        await client.get_status()
    assert aioclient_mock.call_count == 1  # second call never hit the network


async def test_local_budget(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    mock_api(aioclient_mock)
    client = api.SmartSolarClient(async_get_clientsession(hass), "k")
    for _ in range(api.MAX_REQUESTS_PER_MINUTE):
        await client.get_status()
    with pytest.raises(api.SmartSolarRateLimitError, match="budget"):
        await client.get_status()
    assert aioclient_mock.call_count == api.MAX_REQUESTS_PER_MINUTE
