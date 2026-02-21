# Fabric MCP Server 🚀

A **Model Context Protocol (MCP)** server for Microsoft Fabric workspace management and automation. This tool empowers AI agents (like Claude, Cursor, Cline) to manage Fabric workspaces, automate Git-based deployments, and generate Power BI themes.

## 🌟 Why This Exists

**Automate Microsoft Fabric operations from your AI agent.**

Microsoft Fabric has powerful Git integration for version control, but managing workspaces and triggering deployments typically requires manual actions in the web portal or scripting.

**Fabric MCP Server** transforms this into an **AI-agent-friendly workflow**:

Instead of manual portal clicks, tell your AI agent:
> *"List all workspaces in our tenant."*
> *"Deploy the latest changes from Git to the Production workspace."*
> *"Generate a dark theme with our brand colors: #00B8D4 and #FF6F00."*

This enables:
*   **Automation:** AI agents can manage Fabric workspaces programmatically
*   **Git-based deployments:** Trigger `updateFromGit` to deploy from connected branches
*   **Version control:** All changes tracked in Git
*   **Theme generation:** Dynamically create Power BI themes from brand colors

## ✨ Capabilities

- **Workspace Management:** List and inspect all Fabric workspaces in your tenant
- **Git Sync:** Trigger `updateFromGit` to deploy changes from connected Git branches (CI/CD)
- **Theme Generator:** Dynamically create Power BI JSON themes from hex color codes
- **Dataset Refresh:** Trigger refreshes for Semantic Models (datasets)

## 📦 Installation

```bash
pip install fabric-mcp-server-powerbi-creator
```

## 🚀 Quick Start

### 1. Configure Authentication

**Option A: Azure CLI (Recommended for local development)**
```bash
az login
```

**Option B: Service Principal (For CI/CD)**
```bash
export FABRIC_TENANT_ID="your-tenant-id"
export FABRIC_CLIENT_ID="your-client-id"
export FABRIC_CLIENT_SECRET="your-client-secret"
```

### 2. Run the Server

```bash
fabric-mcp-server-powerbi-creator
```

### 3. Connect to Your AI Agent

Add to Claude Desktop, Cline, or Cursor config:
```json
{
  "mcpServers": {
    "fabric": {
      "command": "fabric-mcp-server-powerbi-creator",
      "args": []
    }
  }
}
```

## 🛠️ Available Tools

| Tool | Description | Example Use |
|------|-------------|-------------|
| `list_workspaces` | Lists all Fabric workspaces you have access to | "Show me all my workspaces" |
| `connect_workspace_to_git` | Connects a workspace to a Git repository for template/report syncing | "Connect my workspace to the PowerBI templates repo" |
| `sync_workspace` | Triggers Git sync (updateFromGit) for a workspace | "Deploy the latest changes to Production workspace" |
| `get_git_status` | Shows Git connection status and pending changes | "What's the Git status of my workspace?" |
| `generate_theme` | Generates a Power BI theme JSON from hex colors | "Create a dark theme with cyan #00E5FF and purple #D500F9" |

## 📖 Usage Examples

### List Workspaces
```
User: "Show me all my Fabric workspaces"
Agent: Calls list_workspaces() → Returns list with names, IDs, descriptions
```

### Connect Workspace to Git Repository
```
User: "Connect my workspace to the PowerBI templates repository"
Agent: Calls connect_workspace_to_git()
   - workspace_id: abc123
   - git_provider: "GitHub"
   - organization: "yourorg"
   - repository: "powerbi-templates"
   - branch: "main"
Result: Workspace linked to Git repo
```

### Deploy Templates from Git  
```
User: "Deploy the sales dashboard template to my workspace"
Agent: Calls sync_workspace(workspace_id)
   → Triggers updateFromGit
   → Sales dashboard appears in workspace
```

### Check Git Status
```
User: "What's the Git status of my workspace?"
Agent: Calls get_git_status(workspace_id)
   → Shows connected repo, branch, pending changes
```

### Generate connect` to link workspaces to Git repositories
- Calls `git/updateFromGit` to sync content from Git
- Calls `git/status` to check connection and changes
- Enables GitOps-style deployments for Fabric workspaces

**Template Workflow:**
1. Store Power BI templates (`.pbip` format) in Git repository
2. Connect Fabric workspace to Git repo using `connect_workspace_to_git()`
3. Deploy templates using `sync_workspace()`
4. Templates appear in workspace, ready to customize

## 🧪 Testing

See [test-templates/](test-templates/) folder for a sample Sales Dashboard template with dummy data.

To test:
1. Push `test-templates/` to a Git repository
2. Use `connect_workspace_to_git()` to link your workspace
3. Use `sync_workspace()` to deploy the template
4. Verify the Sales Dashboard appears in your workspace
User: "Create a dark Power BI theme with our brand colors: cyan #00E5FF and purple #D500F9"
Agent: Calls generate_theme() → Returns theme JSON file
```

## 🏗️ Architecture

This server acts as a bridge between the **MCP Protocol** and the **Microsoft Fabric REST API**.

**Key Components:**
- **fabric_api.py**: Wrapper for Fabric REST API calls (workspaces, Git operations)
- **theme_generator.py**: Generates Power BI theme JSON files
- **server.py**: MCP server exposing tools to AI agents

**Authentication:**
- Uses `azure-identity` with `DefaultAzureCredential`
- Supports Azure CLI login (for interactive use)
- Supports Service Principal (for CI/CD)

**Git Integration:**
- Calls `git/updateFromGit` endpoint to sync from connected Git repos
- Enables GitOps-style deployments for Fabric workspaces

## 🤝 Contributing

Contributions welcome! Areas for improvement:
- Additional Fabric API operations (dataset refresh, capacity management)
- Support for commitToGit (push changes back to Git)
- Enhanced error handling and retry logic
- More theme customization options

## 📄 License
MIT
