/**
 * Weather MCP Server for the Orchid Weather Example
 *
 * Exposes weather forecast and current-conditions tools via Streamable HTTP.
 * Wraps the free Open-Meteo API — no API key required.
 *
 * Tools:
 *   - get_forecast:     7-day daily forecast for any location
 *   - get_current_weather:  Current conditions for any location
 *
 * Usage:
 *   node index.js
 *   MCP endpoint: http://localhost:3002/mcp
 *   Health check: http://localhost:3002/health
 */

import express from "express";

// ── Configuration ──────────────────────────────────────────────
const PORT = parseInt(process.env.MCP_PORT || "3002", 10);
const OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast";
const OPEN_METEO_GEOCODING = "https://geocoding-api.open-meteo.com/v1/search";
const USER_AGENT = "orchid-weather-example/0.1.0";

// ── Helpers ────────────────────────────────────────────────────

/**
 * Resolve a city name to lat/lon via Open-Meteo Geocoding API.
 */
async function geocode(city) {
  const url = new URL(OPEN_METEO_GEOCODING);
  url.searchParams.set("name", city);
  url.searchParams.set("count", "1");
  url.searchParams.set("language", "en");

  const res = await fetch(url, { headers: { "User-Agent": USER_AGENT } });
  if (!res.ok) throw new Error(`Geocoding API error: ${res.status}`);

  const data = await res.json();
  if (!data.results || data.results.length === 0) {
    throw new Error(`Location not found: "${city}"`);
  }

  const r = data.results[0];
  return {
    lat: r.latitude,
    lon: r.longitude,
    name: r.name,
    country: r.country || "",
    admin1: r.admin1 || "",
  };
}

/**
 * WMO weather code → human-readable description.
 * https://www.nodc.noaa.gov/archive/arc0021/0002199/1.1/data/0-data/HTML/WMO-CODE/WMO4677.HTM
 */
const WMO_CODES = {
  0:  "Clear sky",
  1:  "Mainly clear",
  2:  "Partly cloudy",
  3:  "Overcast",
  45: "Foggy",
  48: "Depositing rime fog",
  51: "Light drizzle",
  53: "Moderate drizzle",
  55: "Dense drizzle",
  56: "Light freezing drizzle",
  57: "Dense freezing drizzle",
  61: "Slight rain",
  63: "Moderate rain",
  65: "Heavy rain",
  66: "Light freezing rain",
  67: "Heavy freezing rain",
  71: "Slight snowfall",
  73: "Moderate snowfall",
  75: "Heavy snowfall",
  77: "Snow grains",
  80: "Slight rain showers",
  81: "Moderate rain showers",
  82: "Violent rain showers",
  85: "Slight snow showers",
  86: "Heavy snow showers",
  95: "Thunderstorm",
  96: "Thunderstorm with slight hail",
  99: "Thunderstorm with heavy hail",
};

function weatherDescription(code) {
  return WMO_CODES[code] || `Weather code ${code}`;
}

// ── Tool registrations (handlers as plain async functions) ──────

const TOOLS = {};

TOOLS["get_forecast"] = {
  schema: {
    name: "get_forecast",
    description: "Get a 7-day weather forecast for a given city. Returns daily high/low temperature, precipitation probability, wind speed, weather conditions, and UV index.",
    inputSchema: {
      type: "object",
      properties: {
        city: { type: "string", description: "City name (e.g. 'London', 'Tokyo', 'New York')" },
        days: { type: "integer", minimum: 1, maximum: 7, default: 7, description: "Number of forecast days (1-7)" },
      },
      required: ["city"],
    },
  },
  async handler(args) {
    const city = args.city;
    const days = args.days || 7;
    const loc = await geocode(city);

    const url = new URL(OPEN_METEO_FORECAST);
    url.searchParams.set("latitude", loc.lat.toString());
    url.searchParams.set("longitude", loc.lon.toString());
    url.searchParams.set("daily", [
      "temperature_2m_max", "temperature_2m_min",
      "apparent_temperature_max", "apparent_temperature_min",
      "precipitation_probability_max", "precipitation_sum",
      "weather_code", "wind_speed_10m_max", "uv_index_max",
    ].join(","));
    url.searchParams.set("timezone", "auto");
    url.searchParams.set("forecast_days", days.toString());

    const res = await fetch(url, { headers: { "User-Agent": USER_AGENT } });
    if (!res.ok) throw new Error(`Forecast API error: ${res.status}`);

    const data = await res.json();
    const daily = data.daily;

    const forecast = [];
    for (let i = 0; i < daily.time.length; i++) {
      forecast.push({
        date: daily.time[i],
        temperature_max_c: daily.temperature_2m_max[i],
        temperature_min_c: daily.temperature_2m_min[i],
        apparent_max_c: daily.apparent_temperature_max[i],
        apparent_min_c: daily.apparent_temperature_min[i],
        precipitation_probability_pct: daily.precipitation_probability_max[i],
        precipitation_mm: daily.precipitation_sum[i],
        wind_speed_max_kmh: daily.wind_speed_10m_max[i],
        uv_index_max: daily.uv_index_max[i],
        weather_code: daily.weather_code[i],
        condition: weatherDescription(daily.weather_code[i]),
      });
    }

    return {
      location: { city: loc.name, country: loc.country, region: loc.admin1, lat: loc.lat, lon: loc.lon },
      forecast_days: days,
      forecast,
    };
  },
};

TOOLS["get_current_weather"] = {
  schema: {
    name: "get_current_weather",
    description: "Get current weather conditions for a given city. Returns temperature, humidity, apparent temperature, wind speed, and weather condition.",
    inputSchema: {
      type: "object",
      properties: {
        city: { type: "string", description: "City name (e.g. 'London', 'Tokyo', 'New York')" },
      },
      required: ["city"],
    },
  },
  async handler(args) {
    const city = args.city;
    const loc = await geocode(city);

    const url = new URL(OPEN_METEO_FORECAST);
    url.searchParams.set("latitude", loc.lat.toString());
    url.searchParams.set("longitude", loc.lon.toString());
    url.searchParams.set("current", [
      "temperature_2m", "relative_humidity_2m", "apparent_temperature",
      "weather_code", "wind_speed_10m", "wind_direction_10m",
    ].join(","));
    url.searchParams.set("timezone", "auto");

    const res = await fetch(url, { headers: { "User-Agent": USER_AGENT } });
    if (!res.ok) throw new Error(`Weather API error: ${res.status}`);

    const data = await res.json();
    const c = data.current;

    return {
      location: { city: loc.name, country: loc.country, region: loc.admin1, lat: loc.lat, lon: loc.lon },
      current: {
        time: c.time,
        temperature_c: c.temperature_2m,
        apparent_temperature_c: c.apparent_temperature,
        relative_humidity_pct: c.relative_humidity_2m,
        wind_speed_kmh: c.wind_speed_10m,
        wind_direction_deg: c.wind_direction_10m,
        weather_code: c.weather_code,
        condition: weatherDescription(c.weather_code),
      },
    };
  },
};

// ── JSON-RPC handler ────────────────────────────────────────────

const SERVER_INFO = { name: "orchid-weather-mcp", version: "0.1.0" };

function jsonRpc(id, result) {
  return { jsonrpc: "2.0", id, result };
}

function jsonRpcError(id, code, message) {
  return { jsonrpc: "2.0", id, error: { code, message } };
}

async function handleJsonRpc(request) {
  const { method, params, id } = request;

  switch (method) {
    case "initialize":
      return {
        protocolVersion: "2024-11-05",
        capabilities: { tools: {} },
        serverInfo: SERVER_INFO,
      };

    case "notifications/initialized":
      return {}; // no-op ack

    case "tools/list":
      return {
        tools: Object.values(TOOLS).map((t) => t.schema),
      };

    case "tools/call": {
      const toolName = params?.name;
      const tool = TOOLS[toolName];
      if (!tool) {
        throw Object.assign(new Error(`Unknown tool: ${toolName}`), { code: -32601 });
      }
      const result = await tool.handler(params?.arguments || {});
      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
      };
    }

    case "prompts/list":
      return { prompts: [] };

    case "resources/list":
      return { resources: [] };

    case "ping":
      return {};

    default:
      throw Object.assign(new Error(`Method not found: ${method}`), { code: -32601 });
  }
}

// ── Express HTTP layer ─────────────────────────────────────────

const app = express();
app.use(express.json());

app.get("/health", (_req, res) => {
  res.json({ status: "ok", server: SERVER_INFO.name, version: SERVER_INFO.version });
});

app.post("/mcp", async (req, res) => {
  const body = req.body;
  if (!body || !body.method) {
    return res.status(400).json(jsonRpcError(null, -32600, "Invalid Request"));
  }
  try {
    const result = await handleJsonRpc(body);
    if (result === undefined) {
      res.status(202).end();
    } else {
      res.json(jsonRpc(body.id ?? null, result));
    }
  } catch (err) {
    const code = err.code || -32603;
    console.error(`[weather-mcp] RPC error [${body.method}]:`, err.message);
    res.status(500).json(jsonRpcError(body.id ?? null, code, err.message));
  }
});

// ── Start ──────────────────────────────────────────────────────

app.listen(PORT, () => {
  console.log(`[weather-mcp] Listening on http://0.0.0.0:${PORT}`);
  console.log(`[weather-mcp] MCP endpoint: http://0.0.0.0:${PORT}/mcp`);
  console.log(`[weather-mcp] Health: http://0.0.0.0:${PORT}/health`);
});
