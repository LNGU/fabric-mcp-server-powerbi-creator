# Server Logic
# Exposes MCP tools for Power BI template deployment via Git.
#
# Workflow:
# 1. Fabric workspace is pre-connected to Git repo (manual one-time setup)
# 2. MCP pushes report template directly via Azure DevOps REST API
# 3. MCP triggers "Update from Git" to pull into Fabric workspace

from mcp.server.fastmcp import FastMCP
import uuid
import json
import re
import subprocess
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

import fabric_mcp.theme_generator as themes
import fabric_mcp.fabric_api as fabric_api

mcp = FastMCP("fabric-mcp")

# Bundled template path (relative to package)
TEMPLATE_DIR = Path(__file__).parent.parent.parent / "test-templates"


# =============================================================================
# Azure DevOps REST API Helpers
# =============================================================================

def _parse_ado_url(repo_url: str) -> tuple[str, str, str]:
    """
    Parse Azure DevOps Git URL to extract org, project, repo.
    Supports:
      - https://dev.azure.com/org/project/_git/repo
      - https://org.visualstudio.com/project/_git/repo
    """
    # Pattern for dev.azure.com
    match = re.match(r"https://dev\.azure\.com/([^/]+)/([^/]+)/_git/([^/?]+)", repo_url)
    if match:
        return match.group(1), match.group(2), match.group(3)
    
    # Pattern for *.visualstudio.com
    match = re.match(r"https://([^.]+)\.visualstudio\.com/([^/]+)/_git/([^/?]+)", repo_url)
    if match:
        return match.group(1), match.group(2), match.group(3)
    
    raise ValueError(f"Could not parse Azure DevOps URL: {repo_url}")


def _get_ado_token() -> str:
    """Get Azure DevOps token using Azure CLI."""
    import os
    # Azure DevOps resource ID
    ado_resource = "499b84ac-1321-427f-aa17-267ca6975798"
    
    # Use az.cmd on Windows
    az_cmd = r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"
    if not os.path.exists(az_cmd):
        az_cmd = "az"
    
    # Build command - use string for shell=True on Windows
    cmd = f'"{az_cmd}" account get-access-token --resource {ado_resource} --query accessToken -o tsv'
    
    result = subprocess.run(
        cmd,
        capture_output=True, text=True, timeout=30,
        shell=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to get ADO token via Azure CLI: {result.stderr}")
    return result.stdout.strip()


def _ado_api(method: str, url: str, token: str, data: dict = None) -> tuple[int, dict]:
    """Make Azure DevOps REST API call."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            txt = resp.read().decode()
            return resp.status, json.loads(txt) if txt.strip() else {}
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode()[:2000]}


def _get_branch_tip(token: str, org: str, project: str, repo: str, branch: str) -> str:
    """Get the current commit hash (tip) for a branch."""
    url = (f"https://dev.azure.com/{org}/{urllib.parse.quote(project)}"
           f"/_apis/git/repositories/{urllib.parse.quote(repo)}"
           f"/refs?filter=heads/{urllib.parse.quote(branch)}&api-version=7.0")
    code, data = _ado_api("GET", url, token)
    if code != 200:
        raise RuntimeError(f"Failed to get branch tip: {data}")
    for ref in data.get("value", []):
        if ref["name"] == f"refs/heads/{branch}":
            return ref["objectId"]
    raise RuntimeError(f"Branch '{branch}' not found")


def _list_files_in_path(token: str, org: str, project: str, repo: str, branch: str, path: str) -> list[str]:
    """List existing files in a path (for determining add vs edit)."""
    url = (f"https://dev.azure.com/{org}/{urllib.parse.quote(project)}"
           f"/_apis/git/repositories/{urllib.parse.quote(repo)}"
           f"/items?scopePath={urllib.parse.quote(path)}"
           f"&recursionLevel=Full"
           f"&versionDescriptor.version={urllib.parse.quote(branch)}"
           f"&versionDescriptor.versionType=branch&api-version=7.0")
    code, data = _ado_api("GET", url, token)
    if code != 200:
        return []  # Path doesn't exist yet
    return [item["path"] for item in data.get("value", []) if not item.get("isFolder")]


def _push_files_to_ado(token: str, org: str, project: str, repo: str, branch: str,
                       folder_path: str, files: dict[str, str], old_commit: str,
                       commit_message: str) -> tuple[bool, dict]:
    """
    Push files to Azure DevOps in a single commit.
    
    Args:
        files: dict of {relative_path: content} within folder_path
    """
    # Get existing files to determine add vs edit
    existing = set(_list_files_in_path(token, org, project, repo, branch, folder_path))
    
    # Build changes
    changes = []
    for rel_path, content in files.items():
        full_path = f"{folder_path}/{rel_path}" if folder_path else rel_path
        change_type = "edit" if full_path in existing else "add"
        changes.append({
            "changeType": change_type,
            "item": {"path": full_path},
            "newContent": {"content": content, "contentType": "rawtext"},
        })
    
    push_body = {
        "refUpdates": [{"name": f"refs/heads/{branch}", "oldObjectId": old_commit}],
        "commits": [{"comment": commit_message, "changes": changes}],
    }
    
    url = (f"https://dev.azure.com/{org}/{urllib.parse.quote(project)}"
           f"/_apis/git/repositories/{urllib.parse.quote(repo)}"
           f"/pushes?api-version=7.0")
    
    code, data = _ado_api("POST", url, token, push_body)
    if code in (200, 201):
        return True, data
    return False, data


def _generate_pbip_structure(report_name: str, display_name: str = None) -> dict:
    """Generate the .pbip file structure for a report."""
    return {
        "version": "1.0",
        "artifacts": [
            {
                "report": {
                    "path": f"{report_name}.Report",
                    "displayName": display_name or report_name
                }
            }
        ],
        "settings": {
            "enableAutoRecovery": True
        }
    }


def _generate_platform_file(report_name: str, display_name: str = None) -> dict:
    """Generate the .platform metadata file."""
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {
            "type": "Report",
            "displayName": display_name or report_name
        },
        "config": {
            "version": "2.0",
            "logicalId": str(uuid.uuid4())
        }
    }


def _generate_definition_pbir() -> dict:
    """Generate the definition.pbir file."""
    return {
        "version": "1.0",
        "datasetReference": {
            "byPath": None,
            "byConnection": None
        }
    }


# Define tools
@mcp.tool()
async def list_workspaces() -> str:
    """List all Microsoft Fabric workspaces available to the user."""
    try:
        workspaces = fabric_api.client.list_workspaces()
        result_text = "Found Workspaces:\n"
        for ws in workspaces:
            result_text += f"- {ws.get('displayName')} (ID: {ws.get('id')})\n"
            if ws.get('description'):
                result_text += f"  Description: {ws.get('description')}\n"
        return result_text
    except Exception as e:
        return f"Error listing workspaces: {str(e)}"


@mcp.tool()
async def deploy_report(
    repo_url: str,
    branch: str,
    report_name: str,
    target_folder: str = "",
    commit_message: str = "",
    template: str = "sales-dashboard"
) -> str:
    """
    Deploy a Power BI report template to a Git repository.
    
    Uses Azure DevOps REST API to push files directly (no git clone required).
    
    Args:
        repo_url: Git repository URL (e.g., "https://dev.azure.com/org/project/_git/repo")
        branch: Branch name to push to (e.g., "main", "PowerBI")
        report_name: Name for the report (e.g., "SalesDashboard")
        target_folder: Optional subfolder in the repo (default: repo root)
        commit_message: Commit message (default: "Deploy {report_name}")
        template: Bundled template to use: "sales-dashboard" (default) or "blank"
    
    After deploying, use sync_workspace() to pull changes into Fabric.
    """
    try:
        # Parse repo URL
        org, project, repo = _parse_ado_url(repo_url)
        
        # Get ADO token
        token = _get_ado_token()
        
        # Get current branch tip
        old_commit = _get_branch_tip(token, org, project, repo, branch)
        
        # Build file contents
        files = {}
        
        # .pbip file
        pbip_content = _generate_pbip_structure(report_name)
        files[f"{report_name}.pbip"] = json.dumps(pbip_content, indent=2)
        
        # .platform file
        platform_content = _generate_platform_file(report_name)
        files[f"{report_name}.Report/.platform"] = json.dumps(platform_content, indent=2)
        
        # definition.pbir file
        pbir_content = _generate_definition_pbir()
        files[f"{report_name}.Report/definition.pbir"] = json.dumps(pbir_content, indent=2)
        
        # report.json from template or blank
        if template == "sales-dashboard":
            template_report = TEMPLATE_DIR / "sales-dashboard" / "SalesDashboard.Report" / "report.json"
            if template_report.exists():
                files[f"{report_name}.Report/report.json"] = template_report.read_text(encoding="utf-8")
            else:
                return f"Error: Template not found at {template_report}"
        else:
            # Blank report template
            blank_report = {
                "config": json.dumps({"version": "5.51", "themeCollection": {"baseTheme": {"name": "CY24SU08"}}}),
                "layoutOptimization": 0,
                "sections": [{
                    "name": "ReportSection",
                    "displayName": "Page 1",
                    "width": 1280,
                    "height": 720,
                    "visualContainers": []
                }]
            }
            files[f"{report_name}.Report/report.json"] = json.dumps(blank_report, indent=2)
        
        # Push to ADO
        msg = commit_message or f"Deploy {report_name}"
        folder = target_folder.strip("/") if target_folder else ""
        
        ok, result = _push_files_to_ado(token, org, project, repo, branch, folder, files, old_commit, msg)
        
        if not ok:
            return f"Error pushing to Git: {result.get('error', result)}"
        
        new_commit = result.get("commits", [{}])[0].get("commitId", "unknown")
        return (f"Successfully deployed '{report_name}' to {repo_url}\n"
                f"Branch: {branch}\n"
                f"Folder: {folder or '/'}\n"
                f"Commit: {new_commit[:12]}...\n\n"
                f"Next: Use sync_workspace(workspace_id) to pull into Fabric.")
        
    except ValueError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error deploying report: {str(e)}"


@mcp.tool()
async def sync_workspace(workspace_id: str) -> str:
    """
    Trigger 'Update from Git' sync for a Fabric workspace.
    
    This pulls the latest report definitions from the connected Git branch
    into the Fabric workspace. The workspace must already be connected to Git
    (done once via Fabric UI or API).
    
    Args:
        workspace_id: The Fabric workspace ID (use list_workspaces() to find it)
    """
    try:
        # First check if workspace is connected to Git
        connection = fabric_api.client.get_workspace_git_connection(workspace_id)
        
        if connection.get('gitConnectionState') != "ConnectedAndInitialized":
            return f"Error: Workspace Git state is '{connection.get('gitConnectionState')}'. Please connect it first via the Fabric portal."
        
        # Get git status to find commit hashes
        status = fabric_api.client.get_workspace_git_status(workspace_id)
        
        workspace_head = status.get('workspaceHead', '')
        remote_commit_hash = status.get('remoteCommitHash', '')
        changes = status.get('changes', [])
        
        if not remote_commit_hash:
            return "Error: Could not determine remote commit hash."
        
        if not changes:
            return "Workspace is already in sync with Git. No changes to pull."
        
        # Trigger update from Git
        result = fabric_api.client.update_workspace_from_git(
            workspace_id, remote_commit_hash, workspace_head)
        
        return f"Sync initiated successfully.\nChanges: {len(changes)}\nStatus: {result.get('status', 'InProgress')}"
    except Exception as e:
        return f"Error syncing workspace: {str(e)}"


@mcp.tool()
async def get_git_status(workspace_id: str) -> str:
    """
    Check Git sync status for a workspace.
    Shows connected repository and any pending changes.
    """
    try:
        # Get connection info
        connection = fabric_api.client.get_workspace_git_connection(workspace_id)
        git_state = connection.get('gitConnectionState', 'Unknown')
        git_details = connection.get('gitProviderDetails', {})
        
        result_text = "Git Connection:\n"
        result_text += f"  State: {git_state}\n"
        
        if git_state == "ConnectedAndInitialized":
            result_text += f"  Org: {git_details.get('organizationName')}\n"
            result_text += f"  Project: {git_details.get('projectName')}\n"
            result_text += f"  Repo: {git_details.get('repositoryName')}\n"
            result_text += f"  Branch: {git_details.get('branchName')}\n"
            result_text += f"  Directory: {git_details.get('directoryName', '/')}\n\n"
            
            # Get sync status
            status = fabric_api.client.get_workspace_git_status(workspace_id)
            workspace_head = status.get('workspaceHead', '')[:12] if status.get('workspaceHead') else 'N/A'
            remote_commit = status.get('remoteCommitHash', '')[:12] if status.get('remoteCommitHash') else 'N/A'
            changes = status.get('changes', [])
            
            result_text += f"Sync Status:\n"
            result_text += f"  Workspace Head: {workspace_head}...\n"
            result_text += f"  Remote Commit: {remote_commit}...\n"
            result_text += f"  Pending Changes: {len(changes)}\n"
            
            for c in changes[:5]:
                meta = c.get('itemMetadata', {})
                result_text += f"    - {c.get('remoteChange', '?')}: {meta.get('itemType', '?')} - {meta.get('displayName', '?')}\n"
        
        return result_text
    except Exception as e:
        return f"Error getting Git status: {str(e)}"

@mcp.tool()
async def generate_theme(name: str, bg_color: str, text_color: str) -> str:
    """Generate a Power BI JSON theme file."""
    config = themes.ThemeConfig(name=name, background=bg_color, foreground=text_color)
    theme_json = themes.generate_theme(config)
    return theme_json


# =============================================================================
# Semantic Model + Report Deployment Tools
# =============================================================================

@mcp.tool()
async def deploy_semantic_model(
    repo_url: str,
    branch: str,
    model_name: str,
    lakehouse_workspace_id: str,
    lakehouse_id: str,
    tables_json: str,
    relationships_json: str = "[]",
    measures_json: str = "[]",
    target_folder: str = "",
    commit_message: str = ""
) -> str:
    """
    Deploy a semantic model (Direct Lake) to a Git repository.
    
    Creates a TMDL semantic model that connects to Lakehouse tables via Direct Lake.
    
    Args:
        repo_url: Git repository URL (e.g., "https://dev.azure.com/org/project/_git/repo")
        branch: Branch name to push to (e.g., "main", "PowerBI")
        model_name: Name for the semantic model
        lakehouse_workspace_id: Workspace ID containing the Lakehouse
        lakehouse_id: Lakehouse ID for Direct Lake connection
        tables_json: JSON array of table definitions:
                    [{"name": "Sales", "columns": [{"name": "Date", "dataType": "DateTime"}, ...]}]
        relationships_json: JSON array of relationships (optional):
                           [{"fromTable": "Sales", "fromColumn": "DateKey", "toTable": "Calendar", "toColumn": "DateKey"}]
        measures_json: JSON array of measures (optional):
                      [{"table": "Sales", "name": "Total Revenue", "expression": "SUM(Sales[Revenue])", "formatString": "#,##0"}]
        target_folder: Optional subfolder in the repo
        commit_message: Commit message (default: "Deploy {model_name}")
    
    After deploying, use sync_workspace() to pull changes into Fabric.
    """
    try:
        from fabric_mcp.semantic_model import SemanticModelBuilder
        
        # Parse inputs
        tables = json.loads(tables_json)
        relationships = json.loads(relationships_json)
        measures = json.loads(measures_json)
        
        # Parse repo URL
        org, project, repo = _parse_ado_url(repo_url)
        
        # Get ADO token
        token = _get_ado_token()
        
        # Get current branch tip
        old_commit = _get_branch_tip(token, org, project, repo, branch)
        
        # Build semantic model
        builder = SemanticModelBuilder(
            model_name=model_name,
            lakehouse_workspace_id=lakehouse_workspace_id,
            lakehouse_id=lakehouse_id
        )
        
        # Add tables
        for table in tables:
            builder.add_table(table["name"], table.get("columns", []))
        
        # Add relationships
        for rel in relationships:
            builder.add_relationship(
                rel["fromTable"], rel["fromColumn"],
                rel["toTable"], rel["toColumn"],
                cross_filter=rel.get("crossFilter", "single"),
                is_active=rel.get("isActive", True),
                many_to_many=rel.get("manyToMany", False)
            )
        
        # Add measures
        for m in measures:
            builder.add_measure(
                m["table"], m["name"], m["expression"],
                m.get("formatString")
            )
        
        # Build files
        sm_files = builder.build_all_files()
        
        # Prepend model folder to paths
        files = {}
        for path, content in sm_files.items():
            files[f"{model_name}.SemanticModel/{path}"] = content
        
        # Push to ADO
        msg = commit_message or f"Deploy {model_name} semantic model"
        folder = target_folder.strip("/") if target_folder else ""
        
        ok, result = _push_files_to_ado(token, org, project, repo, branch, folder, files, old_commit, msg)
        
        if not ok:
            return f"Error pushing to Git: {result.get('error', result)}"
        
        new_commit = result.get("commits", [{}])[0].get("commitId", "unknown")
        return (f"Successfully deployed semantic model '{model_name}'\n"
                f"Tables: {len(tables)}\n"
                f"Relationships: {len(relationships)}\n"
                f"Measures: {len(measures)}\n"
                f"Commit: {new_commit[:12]}...\n\n"
                f"Next: Use sync_workspace(workspace_id) to pull into Fabric.")
        
    except json.JSONDecodeError as e:
        return f"Error parsing JSON: {str(e)}"
    except Exception as e:
        return f"Error deploying semantic model: {str(e)}"


@mcp.tool()
async def deploy_report_with_model(
    repo_url: str,
    branch: str,
    model_name: str,
    report_name: str,
    lakehouse_workspace_id: str,
    lakehouse_id: str,
    tables_json: str,
    relationships_json: str = "[]",
    measures_json: str = "[]",
    pages_json: str = "[]",
    target_folder: str = "",
    commit_message: str = ""
) -> str:
    """
    Deploy both a semantic model AND a report together.
    
    The report references the semantic model via byPath, and both must be
    deployed together so Fabric can resolve the dependency.
    
    Args:
        repo_url: Git repository URL
        branch: Branch name
        model_name: Name for the semantic model
        report_name: Name for the report
        lakehouse_workspace_id: Workspace ID containing the Lakehouse
        lakehouse_id: Lakehouse ID for Direct Lake connection
        tables_json: JSON array of table definitions
        relationships_json: JSON array of relationships (optional)
        measures_json: JSON array of measures (optional)
        pages_json: JSON array of report pages (optional):
                   [{"name": "Overview", "visuals": [...]}]
        target_folder: Optional subfolder in the repo
        commit_message: Commit message
    
    After deploying, use sync_workspace() to pull changes into Fabric.
    """
    try:
        from fabric_mcp.semantic_model import SemanticModelBuilder
        from fabric_mcp.report_builder import ReportBuilder
        
        # Parse inputs
        tables = json.loads(tables_json)
        relationships = json.loads(relationships_json)
        measures = json.loads(measures_json)
        pages = json.loads(pages_json)
        
        # Parse repo URL
        org, project, repo = _parse_ado_url(repo_url)
        
        # Get ADO token
        token = _get_ado_token()
        
        # Get current branch tip
        old_commit = _get_branch_tip(token, org, project, repo, branch)
        
        # Build semantic model
        sm_builder = SemanticModelBuilder(
            model_name=model_name,
            lakehouse_workspace_id=lakehouse_workspace_id,
            lakehouse_id=lakehouse_id
        )
        
        for table in tables:
            sm_builder.add_table(table["name"], table.get("columns", []))
        
        for rel in relationships:
            sm_builder.add_relationship(
                rel["fromTable"], rel["fromColumn"],
                rel["toTable"], rel["toColumn"],
                cross_filter=rel.get("crossFilter", "single"),
                is_active=rel.get("isActive", True),
                many_to_many=rel.get("manyToMany", False)
            )
        
        for m in measures:
            sm_builder.add_measure(
                m["table"], m["name"], m["expression"],
                m.get("formatString")
            )
        
        sm_files = sm_builder.build_all_files()
        
        # Build report
        rpt_builder = ReportBuilder(
            report_name=report_name,
            semantic_model_name=model_name
        )
        
        # Add pages (or default blank page)
        if pages:
            for page in pages:
                # Basic page support - TODO: add visual builders
                rpt_builder.add_blank_page(page.get("name", "Page"))
        else:
            rpt_builder.add_blank_page("Overview")
        
        rpt_files = rpt_builder.build_all_files()
        
        # Combine all files
        files = {}
        for path, content in sm_files.items():
            files[f"{model_name}.SemanticModel/{path}"] = content
        for path, content in rpt_files.items():
            files[f"{report_name}.Report/{path}"] = content
        
        # Push to ADO
        msg = commit_message or f"Deploy {model_name} + {report_name}"
        folder = target_folder.strip("/") if target_folder else ""
        
        ok, result = _push_files_to_ado(token, org, project, repo, branch, folder, files, old_commit, msg)
        
        if not ok:
            return f"Error pushing to Git: {result.get('error', result)}"
        
        new_commit = result.get("commits", [{}])[0].get("commitId", "unknown")
        return (f"Successfully deployed semantic model + report\n"
                f"Model: {model_name} ({len(tables)} tables, {len(measures)} measures)\n"
                f"Report: {report_name}\n"
                f"Commit: {new_commit[:12]}...\n\n"
                f"Next: Use sync_workspace(workspace_id) to pull into Fabric.")
        
    except json.JSONDecodeError as e:
        return f"Error parsing JSON: {str(e)}"
    except Exception as e:
        return f"Error deploying: {str(e)}"


# =============================================================================
# Lakehouse Tools
# =============================================================================

@mcp.tool()
async def list_lakehouses(workspace_id: str) -> str:
    """
    List all Lakehouses in a workspace.
    
    Args:
        workspace_id: The Fabric workspace ID
    
    Returns:
        List of Lakehouses with IDs
    """
    try:
        from fabric_mcp.lakehouse import list_lakehouses as _list_lakehouses
        
        lakehouses = _list_lakehouses(workspace_id)
        
        if not lakehouses:
            return "No Lakehouses found in this workspace."
        
        result = "Lakehouses:\n"
        for lh in lakehouses:
            result += f"- {lh.get('displayName')} (ID: {lh.get('id')})\n"
        
        return result
    except Exception as e:
        return f"Error listing lakehouses: {str(e)}"


@mcp.tool()
async def list_lakehouse_tables(workspace_id: str, lakehouse_id: str) -> str:
    """
    List all Delta tables in a Lakehouse.
    
    Args:
        workspace_id: The Fabric workspace ID
        lakehouse_id: The Lakehouse ID
    
    Returns:
        List of tables with types
    """
    try:
        from fabric_mcp.lakehouse import LakehouseClient
        
        client = LakehouseClient(workspace_id, lakehouse_id)
        tables = client.list_tables()
        
        if not tables:
            return "No tables found in this Lakehouse."
        
        result = "Lakehouse Tables:\n"
        for t in tables:
            result += f"- {t.get('name')} ({t.get('type', 'unknown')})\n"
        
        return result
    except Exception as e:
        return f"Error listing tables: {str(e)}"


@mcp.tool()
async def load_csv_to_lakehouse(
    workspace_id: str,
    lakehouse_id: str,
    table_name: str,
    file_path: str,
    mode: str = "Overwrite"
) -> str:
    """
    Load a CSV file from Lakehouse Files into a Delta table.
    
    The CSV must already be uploaded to the Lakehouse Files folder.
    
    Args:
        workspace_id: The Fabric workspace ID
        lakehouse_id: The Lakehouse ID
        table_name: Name for the Delta table
        file_path: Path to CSV in Files folder (e.g., "Files/uploads/data.csv")
        mode: "Overwrite" or "Append"
    
    Returns:
        Status of the load operation
    """
    try:
        from fabric_mcp.lakehouse import LakehouseClient
        
        client = LakehouseClient(workspace_id, lakehouse_id)
        client.load_table(table_name, file_path, mode)
        
        return f"Successfully loaded '{file_path}' into table '{table_name}'"
    except Exception as e:
        return f"Error loading table: {str(e)}"


@mcp.tool()
async def upload_csv_to_lakehouse(
    workspace_id: str,
    lakehouse_id: str,
    local_file_path: str,
    remote_folder: str = "uploads"
) -> str:
    """
    Upload a local CSV file to Lakehouse OneLake storage.
    
    Uses Azure Data Lake Storage Gen2 SDK to write directly to OneLake.
    After uploading, use load_csv_to_lakehouse() to create a Delta table.
    
    Args:
        workspace_id: The Fabric workspace ID
        lakehouse_id: The Lakehouse ID
        local_file_path: Path to local CSV file
        remote_folder: Folder in Lakehouse Files (default: "uploads")
    
    Returns:
        Status and remote path of uploaded file
    """
    try:
        from fabric_mcp.lakehouse import LakehouseClient
        from pathlib import Path
        
        local_path = Path(local_file_path)
        if not local_path.exists():
            return f"Error: File not found: {local_file_path}"
        
        remote_path = f"{remote_folder}/{local_path.name}"
        
        client = LakehouseClient(workspace_id, lakehouse_id)
        client.upload_csv(str(local_path), remote_path)
        
        return (f"Successfully uploaded '{local_path.name}' to Lakehouse.\n"
                f"Remote path: Files/{remote_path}\n\n"
                f"Next: Use load_csv_to_lakehouse() with file_path='Files/{remote_path}' to create a Delta table.")
    except Exception as e:
        return f"Error uploading file: {str(e)}"


@mcp.tool()
async def refresh_semantic_model(
    workspace_id: str,
    model_name: str
) -> str:
    """
    Refresh a semantic model to load data from Lakehouse.
    
    Direct Lake semantic models need to be refreshed after deployment
    to sync data from their connected Lakehouse tables.
    
    Args:
        workspace_id: The Fabric workspace ID
        model_name: Name of the semantic model to refresh
    
    Returns:
        Status of the refresh operation
    """
    import os
    import time
    
    try:
        # Get Power BI API token
        az_cmd = r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"
        if not os.path.exists(az_cmd):
            az_cmd = "az"
        
        cmd = f'"{az_cmd}" account get-access-token --resource https://analysis.windows.net/powerbi/api --query accessToken -o tsv'
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=30)
        if result.returncode != 0:
            return f"Error getting Power BI token: {result.stderr}"
        pbi_token = result.stdout.strip()
        
        # Find model ID
        url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets"
        headers = {"Authorization": f"Bearer {pbi_token}"}
        req = urllib.request.Request(url, headers=headers, method="GET")
        
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
        
        model_id = None
        for ds in data.get("value", []):
            if ds.get("name") == model_name:
                model_id = ds.get("id")
                break
        
        if not model_id:
            return f"Error: Semantic model '{model_name}' not found in workspace."
        
        # Trigger refresh
        url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{model_id}/refreshes"
        body = json.dumps({"type": "Full"}).encode()
        req = urllib.request.Request(url, data=body, headers={
            "Authorization": f"Bearer {pbi_token}",
            "Content-Type": "application/json"
        }, method="POST")
        
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                pass
        except urllib.error.HTTPError as e:
            if e.code != 202:
                return f"Error triggering refresh: {e.code} - {e.read().decode()[:500]}"
        
        # Poll for completion
        for i in range(30):
            time.sleep(5)
            url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{model_id}/refreshes?$top=1"
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {pbi_token}"}, method="GET")
            
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode())
            
            vals = data.get("value", [])
            if vals:
                status = vals[0].get("status", "Unknown")
                if status == "Completed":
                    return f"Refresh completed successfully for '{model_name}'."
                elif status in ("Failed", "Cancelled"):
                    error = vals[0].get("serviceExceptionJson", "Unknown error")
                    return f"Refresh {status}: {error}"
        
        return "Refresh timed out - check Fabric portal for status."
        
    except Exception as e:
        return f"Error refreshing model: {str(e)}"


def main():
    """Entry point for console script."""
    mcp.run(transport="stdio")

# Start server
if __name__ == "__main__":
    main()
