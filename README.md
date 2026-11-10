# Weather Alerts MCP Server

Ask an AI assistant about US weather alerts and get answers based on live data from the National Weather Service.

## What is this?

AI assistants know a lot, but they can't see today's weather. This project gives them a way to look it up.

It is an MCP server. MCP (Model Context Protocol) is a standard way to connect an AI assistant to outside tools, a bit like a USB port for AI. This server plugs three weather tools into the assistant. The data comes from the free National Weather Service (NWS) API, so no API key is needed.

## Example

> **You:** Are there any serious weather alerts in California right now?
>
> **Assistant:** *(calls `get_alerts` with state = CA)* There are 12 active alerts. None are severe today. The strongest ones are Beach Hazards Statements for the San Diego and Santa Barbara coasts, with dangerous rip currents and surf of 3 to 6 feet.

The assistant picks the tool, the server fetches fresh data, and the assistant explains the result in plain language.

## How it works

```
You  →  AI assistant  →  MCP server  →  NWS API
                         (this project)
```

## Tools

| Tool | What it does |
|---|---|
| `get_alerts(state, min_severity, limit)` | Active alerts for a state (`CA` or `California`), most severe first |
| `get_alerts_for_point(latitude, longitude)` | Alerts for one exact location |
| `get_forecast(latitude, longitude, periods)` | Forecast for a US location |

Coverage is the United States and its territories.

## Quick start

You need [uv](https://docs.astral.sh/uv/) installed.

```bash
git clone https://github.com/Hamed-Ghaseminezhad/weather-alerts-mcp-server
cd weather-alerts-mcp-server
uv sync

# NWS asks for a contact in the User-Agent. Use your own email.
export NWS_USER_AGENT="weather-alerts-mcp-server (you@example.com)"

# Try it:
uv run python examples/client.py
```

You should see the three tool names followed by the current alerts for California.

### Use it with Claude Desktop

Add this to your Claude Desktop config, then restart the app:

```json
{
  "mcpServers": {
    "weather": {
      "command": "uv",
      "args": ["--directory", "/ABSOLUTE/PATH/weather-alerts-mcp-server", "run", "weather-alerts-mcp-server"],
      "env": { "NWS_USER_AGENT": "weather-alerts-mcp-server (you@example.com)" }
    }
  }
}
```

### Run as an HTTP server

```bash
uv run weather-alerts-mcp-server --transport streamable-http
```

The server listens on `http://127.0.0.1:8000/mcp`.

## Details

- Network errors are reported to the assistant instead of being hidden, and failed requests are retried up to 3 times, because the NWS API sometimes returns temporary errors.
- Long alert descriptions are shortened so they fit comfortably in the assistant's context.
- 17 automated tests run without internet access: `uv run pytest`.
- Built with the official Python MCP SDK (2.x). I started from Krish Naik's MCP crash course and then restructured the code and added the extra tools and tests.

## Disclaimer

For safety decisions, check [weather.gov](https://www.weather.gov) or your local emergency services. This project is a learning project and is not an official alert system.