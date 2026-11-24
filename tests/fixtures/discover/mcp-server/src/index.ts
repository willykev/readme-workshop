#!/usr/bin/env node
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { EXTRA_TOOLS } from "./extra.js";

const API = "https://api.example.org/weather";
const server = new McpServer({ name: "weather", version: "0.2.0" });

server.tool(
  "get_forecast",
  "Get the forecast for a city",
  { city: z.string() },
  async ({ city }) => ({ content: [{ type: "text", text: await lookup(`/forecast?city=${city}`) }] }),
);

server.registerTool(
  "get_alerts",
  { description: "Active weather alerts for a state", inputSchema: { state: z.string().length(2) } },
  async ({ state }) => ({ content: [{ type: "text", text: await lookup(`/alerts?state=${state}`) }] }),
);

// server.tool("legacy_lookup", "The old lookup", {}, async () => ({ content: [] }));

for (const extra of EXTRA_TOOLS) {
  server.tool(extra.name, extra.description, {}, extra.run);
}

async function lookup(path: string): Promise<string> {
  const response = await fetch(API + path, { headers: { "x-api-key": process.env.WEATHER_API_KEY ?? "" } });
  return response.text();
}

function _privateHelper() { return API; }

await server.connect(new StdioServerTransport());
