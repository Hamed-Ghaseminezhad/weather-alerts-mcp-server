"""MCP server exposing NWS weather alerts and forecasts."""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from .nws import (
    NWSClient,
    NWSError,
    format_alert,
    format_period,
    normalize_state,
    sort_and_filter_alerts,
)

# stdio servers talk over stdout, so all logging must go to stderr.
logging.basicConfig(stream=sys.stderr, level=logging.INFO)
log = logging.getLogger("weather-alerts")

mcp = MCPServer(
    "weather",
    instructions=(
        "Tools for US weather data from the National Weather Service. "
        "Coverage is the United States and its territories only."
    ),
)

_client: NWSClient | None = None


def get_client() -> NWSClient:
    global _client
    if _client is None:
        _client = NWSClient()
    return _client


READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=True)
Severity = Literal["Minor", "Moderate", "Severe", "Extreme"]


def _render_alerts(features: list, limit: int, min_severity: str | None) -> str:
    alerts = sort_and_filter_alerts(features, min_severity)
    if not alerts:
        return "No active alerts match this request."
    shown = alerts[:limit]
    text = "\n---\n".join(format_alert(a) for a in shown)
    if len(alerts) > len(shown):
        text += (
            f"\n---\n({len(alerts) - len(shown)} more alerts not shown. Raise `limit` to see them.)"
        )
    return f"{len(alerts)} active alert(s), most severe first.\n\n{text}"


@mcp.tool(annotations=READ_ONLY)
async def get_alerts(state: str, min_severity: Severity | None = None, limit: int = 10) -> str:
    """Get active weather alerts for a US state, most severe first.

    Args:
        state: US state code or name (e.g. "CA" or "California").
        min_severity: Only return alerts at least this severe (Minor, Moderate, Severe, Extreme).
        limit: Maximum number of alerts to return (1-50).
    """
    try:
        code = normalize_state(state)
        features = await get_client().alerts_for_state(code)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc
    except NWSError as exc:
        log.warning("alerts_for_state failed: %s", exc)
        raise ToolError(str(exc)) from exc
    return _render_alerts(features, max(1, min(limit, 50)), min_severity)


@mcp.tool(annotations=READ_ONLY)
async def get_alerts_for_point(latitude: float, longitude: float, limit: int = 10) -> str:
    """Get active weather alerts for one exact location (more precise than a whole state).

    Args:
        latitude: Latitude, e.g. 34.05 for Los Angeles.
        longitude: Longitude, e.g. -118.24 for Los Angeles.
        limit: Maximum number of alerts to return (1-50).
    """
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ToolError("Latitude must be between -90 and 90, longitude between -180 and 180.")
    try:
        features = await get_client().alerts_for_point(latitude, longitude)
    except NWSError as exc:
        raise ToolError(str(exc)) from exc
    return _render_alerts(features, max(1, min(limit, 50)), None)


@mcp.tool(annotations=READ_ONLY)
async def get_forecast(latitude: float, longitude: float, periods: int = 5) -> str:
    """Get the weather forecast for a US location.

    Args:
        latitude: Latitude, e.g. 37.77 for San Francisco.
        longitude: Longitude, e.g. -122.42 for San Francisco.
        periods: How many forecast periods to return (1-14, each is about 12 hours).
    """
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ToolError("Latitude must be between -90 and 90, longitude between -180 and 180.")
    try:
        data = await get_client().forecast(latitude, longitude)
    except NWSError as exc:
        raise ToolError(str(exc)) from exc
    if not data:
        return "No forecast periods were returned."
    return "\n---\n".join(format_period(p) for p in data[: max(1, min(periods, 14))])


def main() -> None:
    parser = argparse.ArgumentParser(description="NWS weather alerts MCP server")
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1", help="Only used with streamable-http")
    parser.add_argument("--port", type=int, default=8000, help="Only used with streamable-http")
    args = parser.parse_args()
    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="streamable-http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
