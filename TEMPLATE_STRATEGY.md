# Template Strategy for Fabric MCP Server

## How Templates Should Work With Fabric Git Integration

### Current Understanding:

Based on Microsoft documentation research, Power BI templates in a Fabric context should work as follows:

## ✅ Correct Approach: Git-Based Templates

### Template Format:
- **Use .pbip (Power BI Project) format**, not .pbit
- Structure: Folder containing:
  - `{reportname}.pbip` - Main project file
  - `{reportname}.Report/` - Report definition folder
    - `definition.pbir` - Report metadata
    - `report.json` - Report layout
    - `.platform` - System metadata
  - `{reportname}.SemanticModel/` - Data model folder (optional)
    - `definition.pbism` - Model metadata  
    - `definition/` - TMDL files

### Publishing Workflow:

1. **Template Repository Setup:**
   ```
   GitHub/Azure DevOps Repository:
   ├── templates/
   │   ├── sales-dashboard/
   │   │   ├── SalesDashboard.pbip
   │   │   ├── SalesDashboard.Report/
   │   │   │   ├── definition.pbir
   │   │   │   ├── report.json
   │   │   │   └── .platform
   │   │   └── SalesDashboard.SemanticModel/
   │   └── executive-overview/
   │       └── ...
   ```

2. **User Gets Template:**
   - User's workspace connects to the template Git repository (branch/folder)
   - User calls `sync_workspace()` → Triggers `updateFromGit` 
   - Template items appear in their workspace
   - User customizes with their own data connections

3. **Template Updates:**
   - Template maintainer commits improvements to Git
   - Users call `sync_workspace()` again to get latest version

## ❌ What DOESN'T Work:

- Uploading `.pbit` files via Power BI REST API
- Storing templates locally in the MCP server
- Using Import Report APIs (old Power BI Service approach)

## 🛠️ Recommended Implementation:

### Add to fabric_api.py:

```python
def connect_workspace_to_git(
    self, 
    workspace_id: str, 
    git_provider_type: str,  # "AzureDevOps" or "GitHub"
    organization_name: str,
    project_name: str,
    repository_name: str,
    branch_name: str,
    directory_name: str = "/"
) -> Dict[str, Any]:
    """
    Connects a workspace to a Git repository.
    This enables the workspace to sync with templates stored in Git.
    """
    url = f"{self.base_url}/workspaces/{workspace_id}/git/connect"
    
    body = {
        "gitProviderDetails": {
            "gitProviderType": git_provider_type,
            "organizationName": organization_name,
            "projectName": project_name,
            "repositoryName": repository_name,
            "branchName": branch_name,
            "directoryName": directory_name
        }
    }
    
    response = requests.post(url, headers=self._get_headers(), json=body)
    response.raise_for_status()
    return response.json()


def get_workspace_git_status(self, workspace_id: str) -> Dict[str, Any]:
    """
    Gets the Git connection status for a workspace.
    Shows if workspace is connected and what changes are pending.
    """
    url = f"{self.base_url}/workspaces/{workspace_id}/git/status"
    response = requests.get(url, headers=self._get_headers())
    response.raise_for_status()
    return response.json()
```

### Add to server.py:

```python
@server.tool()
async def connect_workspace_to_git(
    workspace_id: str,
    git_provider: str,
    repository_url: str,
    branch: str = "main",
    folder: str = "/"
) -> TextContent:
    """
    Connect a workspace to a Git repository containing Power BI templates.
    
    After connection, use sync_workspace() to pull templates into the workspace.
    
    Args:
        workspace_id: The Fabric workspace ID
        git_provider: "AzureDevOps" or "GitHub"
        repository_url: Full URL to the Git repository
        branch: Git branch name (default: "main")
        folder: Subfolder path in the repo (default: "/")
    """
    # Parse repository_url to extract org/project/repo
    # Call fabric_api.client.connect_workspace_to_git()
    # Return success message
    pass


@server.tool()
async def get_git_status(workspace_id: str) -> TextContent:
    """
    Check Git sync status for a workspace.
    Shows connected repository and any pending changes.
    """
    # Call fabric_api.client.get_workspace_git_status()
    pass
```

## 📖 Usage Example:

```
User: "I want to use the Sales Dashboard template"

Agent workflow:
1. Calls connect_workspace_to_git()
   - workspace_id: user's workspace
   - repository_url: https://github.com/yourorg/powerbi-templates
   - folder: "/templates/sales-dashboard"
   
2. Calls sync_workspace(workspace_id)
   - Triggers updateFromGit
   - Sales Dashboard template appears in workspace
   
3. User customizes in Power BI Desktop or Web
   - Connects to their own data sources
   - Modifies visuals as needed
```

## 🎯 Benefits:

- ✅ **Git-native**: Templates are version controlled
- ✅ **No file uploads**: Leverage existing Git infrastructure  
- ✅ **Automatic updates**: Users can pull latest template versions
- ✅ **Works with current code**: Uses existing `sync_workspace()` function
- ✅ **Fabric-compatible**: Follows Microsoft's recommended approach

## 📚 References:

- [Fabric Git Integration Overview](https://learn.microsoft.com/en-us/fabric/cicd/git-integration/intro-to-git-integration)
- [Git Integration Source Code Format](https://learn.microsoft.com/en-us/fabric/cicd/git-integration/source-code-format)
- [Power BI Project (.pbip) Format](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-overview)
