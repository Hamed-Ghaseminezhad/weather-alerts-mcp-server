import httpx
import pytest
from mcp.server.mcpserver.exceptions import ToolError

from weather_alerts_mcp_server import server
from weather_alerts_mcp_server.nws import (
    NWSClient,
    NWSError,
    format_alert,
    normalize_state,
    sort_and_filter_alerts,
)


def alert(event, severity, desc="Some text"):
    return {
        "properties": {"event": event, "severity": severity, "areaDesc": "LA", "description": desc}
    }


def make_client(handler, **kw):
    return NWSClient(transport=httpx.MockTransport(handler), backoff=0, **kw)


@pytest.mark.parametrize(
    "raw,expected", [("CA", "CA"), ("ca", "CA"), (" California ", "CA"), ("new york", "NY")]
)
def test_normalize_state_ok(raw, expected):
    assert normalize_state(raw) == expected


@pytest.mark.parametrize("raw", ["XX", "", "Atlantis", "CA/../x"])
def test_normalize_state_rejects(raw):
    with pytest.raises(ValueError):
        normalize_state(raw)


def test_sort_and_filter():
    feats = [alert("a", "Minor"), alert("b", "Extreme"), alert("c", "Severe")]
    assert [f["properties"]["event"] for f in sort_and_filter_alerts(feats)] == ["b", "c", "a"]
    assert [f["properties"]["event"] for f in sort_and_filter_alerts(feats, "Severe")] == ["b", "c"]


def test_format_alert_truncates():
    out = format_alert(alert("Wind", "Severe", "x " * 2000))
    assert out.count("x") < 400 and "..." in out


async def test_retries_then_succeeds():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503)
        return httpx.Response(200, json={"features": [alert("Wind", "Severe")]})

    client = make_client(handler)
    assert len(await client.alerts_for_state("CA")) == 1
    assert calls["n"] == 3


async def test_gives_clear_error_after_retries():
    client = make_client(lambda r: httpx.Response(500))
    with pytest.raises(NWSError, match="after 3 tries"):
        await client.alerts_for_state("CA")


async def test_network_error_is_reported_not_swallowed():
    def handler(request):
        raise httpx.ConnectError("Name or service not known")

    with pytest.raises(NWSError, match="network problem"):
        await make_client(handler).alerts_for_state("CA")


async def test_forecast_two_step():
    def handler(request):
        if request.url.path.startswith("/points/"):
            return httpx.Response(
                200,
                json={
                    "properties": {
                        "forecast": "https://api.weather.gov/gridpoints/LOX/1,1/forecast"
                    }
                },
            )
        return httpx.Response(
            200,
            json={
                "properties": {
                    "periods": [
                        {
                            "name": "Today",
                            "temperature": 70,
                            "temperatureUnit": "F",
                            "windSpeed": "5 mph",
                            "windDirection": "N",
                            "detailedForecast": "Sunny.",
                        }
                    ]
                }
            },
        )

    periods = await make_client(handler).forecast(34.05, -118.24)
    assert periods[0]["name"] == "Today"


async def test_tool_returns_sorted_text(monkeypatch):
    def handler(request):
        return httpx.Response(
            200, json={"features": [alert("Minor thing", "Minor"), alert("Big thing", "Extreme")]}
        )

    monkeypatch.setattr(server, "_client", make_client(handler))
    text = await server.get_alerts("California")
    assert text.index("Big thing") < text.index("Minor thing")
    assert "2 active alert(s)" in text


async def test_tool_bad_state_raises_toolerror():
    with pytest.raises(ToolError, match="not a valid US state"):
        await server.get_alerts("Narnia")


async def test_tool_bad_coordinates():
    with pytest.raises(ToolError):
        await server.get_forecast(200, 0)
