"""Small async client for the National Weather Service (NWS) API."""

from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx

NWS_API_BASE = "https://api.weather.gov"
# NWS asks for a User-Agent that identifies the app and gives a way to contact you.
DEFAULT_USER_AGENT = "weather-alerts-mcp-server/0.2 (set NWS_USER_AGENT to your email)"

US_STATES = {
    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
    "DC": "District of Columbia",
    "PR": "Puerto Rico",
    "GU": "Guam",
    "VI": "U.S. Virgin Islands",
}
_NAME_TO_CODE = {name.lower(): code for code, name in US_STATES.items()}

SEVERITY_ORDER = {"Extreme": 0, "Severe": 1, "Moderate": 2, "Minor": 3, "Unknown": 4}


class NWSError(Exception):
    """Raised when the NWS API cannot be reached or returns an error."""


def normalize_state(value: str) -> str:
    """Accept 'CA', 'ca' or 'California' and return 'CA'. Raise ValueError otherwise."""
    text = value.strip()
    code = text.upper()
    if code in US_STATES:
        return code
    if text.lower() in _NAME_TO_CODE:
        return _NAME_TO_CODE[text.lower()]
    raise ValueError(f"'{value}' is not a valid US state code or name (example: CA or California).")


class NWSClient:
    def __init__(
        self,
        *,
        user_agent: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        retries: int = 3,
        backoff: float = 0.5,
    ) -> None:
        self._retries = retries
        self._backoff = backoff
        self._client = httpx.AsyncClient(
            base_url=NWS_API_BASE,
            headers={
                "User-Agent": user_agent or os.getenv("NWS_USER_AGENT", DEFAULT_USER_AGENT),
                "Accept": "application/geo+json",
            },
            timeout=httpx.Timeout(20.0, connect=10.0),
            transport=transport,
            follow_redirects=True,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_json(self, url: str) -> dict[str, Any]:
        """GET a path or absolute NWS URL. Retry on network errors and 5xx/429."""
        last_error = "unknown error"
        for attempt in range(self._retries):
            try:
                response = await self._client.get(url)
                if response.status_code in (429, 500, 502, 503, 504):
                    last_error = f"NWS API returned HTTP {response.status_code}"
                elif response.status_code == 404:
                    raise NWSError("NWS has no data for this request (HTTP 404).")
                else:
                    response.raise_for_status()
                    return response.json()
            except httpx.HTTPStatusError as exc:
                raise NWSError(f"NWS API returned HTTP {exc.response.status_code}.") from exc
            except httpx.TransportError as exc:
                last_error = f"network problem ({type(exc).__name__}: {exc})"
            if attempt < self._retries - 1:
                await asyncio.sleep(self._backoff * 2**attempt)
        raise NWSError(f"Could not reach the NWS API after {self._retries} tries: {last_error}")

    async def alerts_for_state(self, state: str) -> list[dict[str, Any]]:
        data = await self.get_json(f"/alerts/active/area/{state}")
        return data.get("features", [])

    async def alerts_for_point(self, lat: float, lon: float) -> list[dict[str, Any]]:
        data = await self.get_json(f"/alerts/active?point={lat:.4f},{lon:.4f}")
        return data.get("features", [])

    async def forecast(self, lat: float, lon: float) -> list[dict[str, Any]]:
        points = await self.get_json(f"/points/{lat:.4f},{lon:.4f}")
        forecast_url = points.get("properties", {}).get("forecast")
        if not forecast_url:
            raise NWSError("NWS returned no forecast for these coordinates (outside US coverage?).")
        data = await self.get_json(forecast_url)
        return data.get("properties", {}).get("periods", [])


def sort_and_filter_alerts(
    features: list[dict[str, Any]], min_severity: str | None = None
) -> list[dict[str, Any]]:
    """Most severe first. If min_severity is given, drop anything milder."""
    limit = SEVERITY_ORDER.get(min_severity, 4) if min_severity else 4
    kept = [
        f
        for f in features
        if SEVERITY_ORDER.get(f.get("properties", {}).get("severity", "Unknown"), 4) <= limit
    ]
    return sorted(
        kept,
        key=lambda f: SEVERITY_ORDER.get(f.get("properties", {}).get("severity", "Unknown"), 4),
    )


def format_alert(feature: dict[str, Any], max_chars: int = 700) -> str:
    props = feature.get("properties", {})
    description = " ".join((props.get("description") or "No description available").split())
    if len(description) > max_chars:
        description = description[:max_chars].rstrip() + "..."
    instruction = " ".join((props.get("instruction") or "None provided").split())
    return (
        f"Event: {props.get('event', 'Unknown')}\n"
        f"Severity: {props.get('severity', 'Unknown')}\n"
        f"Area: {props.get('areaDesc', 'Unknown')}\n"
        f"Expires: {props.get('expires', 'Unknown')}\n"
        f"Description: {description}\n"
        f"Instructions: {instruction}"
    )


def format_period(period: dict[str, Any]) -> str:
    return (
        f"{period.get('name', 'Unknown')}: "
        f"{period.get('temperature', 'N/A')}°{period.get('temperatureUnit', 'F')}, "
        f"wind {period.get('windSpeed', 'N/A')} {period.get('windDirection', '')}. "
        f"{period.get('detailedForecast', '')}"
    ).strip()
