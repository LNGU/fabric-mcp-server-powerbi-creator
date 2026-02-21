# Server Logic
# Exposes MCP tools and resources for Fabric management.

from mcp.server import Server, Notification
from mcp.types import Tool, TextContent
from pydantic import BaseModel, Field

import fabric_mcp.templates as templates
import fabric_mcp.theme_generator as themes
import fabric_mcp.fabric_api as fabric_api

server = Server("fabric-mcp")

# Define tools
@server.tool()
async def list_workspaces() -> list[TextContent]:
    """List all Microsoft Fabric workspaces available to the user."""
    try:
        workspaces = fabric_api.client.list_workspaces()
        # Format the output as a readable string
        result_text = "Found Workspaces:\n"
        for ws in workspaces:
            result_text += f"- {ws.get('displayName')} (ID: {ws.get('id')})\n"
            if ws.get('description'):
                result_text += f"  Description: {ws.get('description')}\n"
        
        return [TextContent(type="text", text=result_text)]
    except Exception as e:
        return [TextContent(type="text", text=f"Error listing workspaces: {str(e)}")]

@server.tool()
async def sync_workspace(workspace_id: str) -> TextContent:
    """
    Trigger a 'Update from Git' sync for a specific workspace.
    This pulls the latest report definitions from the connected Git branch.
    """
    try:
        # We don't specify a commit hash to pull the HEAD of the connected branch
        result = fabric_api.client.update_workspace_from_git(workspace_id)
        operation_id = result.get("operationId", "unknown")
        return TextContent(
            type="text", 
            text=f"Sync started successfully.\nOperation ID: {operation_id}\nStatus: {result.get('status', 'InProgress')}"
        )
    except Exception as e:
        return TextContent(type="text", text=f"Error syncing workspace: {str(e)}")

@server.tool()
async def list_templates() -> list[TextContent]:
    """List available report templates (e.g., Executive, Sales)."""
    t = templates.list_templates()
    return [TextContent(type="text", text=str(t))]

@server.tool()
async def apply_template(template_name: str, destination_path: str, report_name: str) -> TextContent:
    """
    Create a new report in a local directory using a template.
    
    Args:
        template_name: ID of the template to use (from list_templates)
        destination_path: Local path to your Fabric Git repo
        report_name: Name of the new report folder to create
    """
    try:
        result = templates.apply_template(template_name, destination_path, report_name)
        return TextContent(type="text", text=str(result))
    except Exception as e:
        return TextContent(type="text", text=f"Error applying template: {str(e)}")

@server.tool()
async def generate_theme(name: str, bg_color: str, text_color: str) -> TextContent:
    """Generate a Power BI JSON theme file."""
    config = themes.ThemeConfig(name=name, background=bg_color, foreground=text_color)
    theme_json = themes.generate_theme(config)
    return TextContent(type="text", text=theme_json)

# Start server
if __name__ == "__main__":
    server.run(transport="stdio")
