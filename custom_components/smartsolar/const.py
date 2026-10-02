"""Constants for the SmartSolar integration."""

from __future__ import annotations

from datetime import timedelta
import logging

DOMAIN = "smartsolar"
LOGGER = logging.getLogger(__package__)

BASE_URL = "https://smartsolar.net.pk"
MANUFACTURER = "SmartSolar"

# The API allows 30 requests/minute per device. Exceeding it disables the
# device for an hour, and three violations revoke API access permanently,
# so we enforce a much lower local ceiling.
MAX_REQUESTS_PER_MINUTE = 20
RATE_LIMIT_BACKOFF_SECONDS = 3600

CONF_SCAN_INTERVAL = "scan_interval"
CONF_HIDE_GRID_ALERTS = "hide_grid_alerts"
CONF_ENABLE_CONTROL = "enable_control"

DEFAULT_SCAN_INTERVAL = 30  # seconds, real-time status
MIN_SCAN_INTERVAL = 15
MAX_SCAN_INTERVAL = 600
DEFAULT_HIDE_GRID_ALERTS = False
DEFAULT_ENABLE_CONTROL = True

USAGE_INTERVAL = timedelta(minutes=5)  # 2 requests (today + this month)
FAULTS_INTERVAL = timedelta(minutes=30)
SETTINGS_INTERVAL = timedelta(minutes=15)
