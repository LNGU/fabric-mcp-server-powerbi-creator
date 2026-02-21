# Server Logic
# Exposes MCP tools and resources for Fabric management.

from mcp.server import Server, Notification
from mcp.types import Tool, TextContent
from pydantic import BaseModel, Field

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
async def connect_workspace_to_git(
    workspace_id: str,
    git_provider: str,
    organization: str,
    project: str,
    repository: str,
    branch: str = "main",
    folder: str = "/"
) -> TextContent:
    """
    Connect a workspace to a Git repository containing Power BI templates or reports.
    
    After connection, use sync_workspace() to pull content into the workspace.
    
    Args:
        workspace_id: The Fabric workspace ID
        git_provider: "AzureDevOps" or "GitHub"
        organization: Git organization/account name
        project: Project name (Azure DevOps) or repository owner (GitHub)
        repository: Repository name
        branch: Git branch name (default: "main")
        folder: Subfolder path in the repo (default: "/")
    
    Example:
        For GitHub: organization="yourorg", project="yourorg", repository="powerbi-templates"
        For Azure DevOps: organization="yourorg", project="YourProject", repository="powerbi-templates"
    """
    try:
        result = fabric_api.client.connect_workspace_to_git(
            workspace_id=workspace_id,
            git_provider_type=git_provider,
            organization_name=organization,
            project_name=project,
            repository_name=repository,
            branch_name=branch,
            directory_name=folder
        )
        return TextContent(
            type="text",
            text=f"Workspace connected to Git successfully!\nProvider: {git_provider}\nRepository: {organization}/{repository}\nBranch: {branch}\nFolder: {folder}\n\nNext step: Use sync_workspace() to pull content from Git."
        )
    except Exception as e:
        return TextContent(type="text", text=f"Error connecting workspace to Git: {str(e)}")

@server.tool()
async def get_git_status(workspace_id: str) -> TextContent:
    """
    Check Git sync status for a workspace.
    Shows connected repository and any pending changes.
    """
    try:
        status = fabric_api.client.get_workspace_git_status(workspace_id)
        
        # Format the status information
        result_text = "Git Status:\n"
        result_text += f"Connected: {status.get('isGitConnected', False)}\n"
        
        if status.get('isGitConnected'):
            git_info = status.get('gitProviderDetails', {})
            result_text += f"Provider: {git_info.get('gitProviderType')}\n"
            result_text += f"Repository: {git_info.get('organizationName')}/{git_info.get('repositoryName')}\n"
            result_text += f"Branch: {git_info.get('branchName')}\n"
            result_text += f"Folder: {git_info.get('directoryName')}\n\n"
            
            # Show pending changes if any
            changes = status.get('workspaceHead', {}).get('changes', [])
            if changes:
                result_text += f"Pending Changes: {len(changes)}\n"
                for change in changes[:5]:  # Show first 5
                    result_text += f"  - {change.get('path')} ({change.get('type')})\n"
            else:
                result_text += "No pending changes\n"
        
        return TextContent(type="text", text=result_text)
    except Exception as e:
        return TextContent(type="text", text=f"Error getting Git status: {str(e)}")

@server.tool()
async def generate_theme(name: str, bg_color: str, text_color: str) -> TextContent:
    """Generate a Power BI JSON theme file."""
    config = themes.ThemeConfig(name=name, background=bg_color, foreground=text_color)
    theme_json = themes.generate_theme(config)
    return TextContent(type="text", text=theme_json)

# Start server
if __name__ == "__main__":
    server.run(transport="stdio")
