# Server Logic
# Exposes MCP tools and resources for Fabric management.

from mcp.server import Server, Notification
from mcp.types import Tool, TextContent
from pydantic import BaseModel, Field

import fabric_mcp.templates as templates
import fabric_mcp.theme_generator as themes

server = Server("fabric-mcp")

# Define tools
@server.tool()
async def list_templates() -> list[TextContent]:
    """List available report templates (e.g., Executive, Sales)."""
    t = templates.list_templates()
    return [TextContent(type="text", text=str(t))]

@server.tool()
async def apply_template(template_name: str, workspace: str, report_name: str) -> TextContent:
    """Create a new report using a template."""
    result = templates.apply_template(template_name, workspace, report_name)
    return TextContent(type="text", text=str(result))

@server.tool()
async def generate_theme(name: str, bg_color: str, text_color: str) -> TextContent:
    """Generate a Power BI JSON theme file."""
    config = themes.ThemeConfig(name=name, background=bg_color, foreground=text_color)
    theme_json = themes.generate_theme(config)
    return TextContent(type="text", text=theme_json)

# Start server
if __name__ == "__main__":
    server.run(transport="stdio")
