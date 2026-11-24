from mcp.server.fastmcp import FastMCP

mcp = FastMCP("notes")


@mcp.tool()
def search_notes(query: str) -> list[str]:
    """Find notes that mention a word."""
    return []


@mcp.tool()
def add_note(text: str) -> str:
    """Save a note."""
    return text
