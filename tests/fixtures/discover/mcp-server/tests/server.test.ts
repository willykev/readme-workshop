import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";

const server = new McpServer({ name: "test", version: "0" });
server.tool("test_only_tool", "Only for tests", {}, async () => ({ content: [] }));
