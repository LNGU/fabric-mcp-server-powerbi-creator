# Fabric MCP Server - Power BI Creator 🚀

A **Model Context Protocol (MCP)** server for Microsoft Fabric and Power BI. This tool empowers AI agents (like Claude, Cursor, OpenClaw) to manage Fabric workspaces, automate deployments via Git, and generate Power BI reports from templates.

## 🌟 Why this exists?

**Stop building Power BI reports manually.** 

Microsoft Fabric has powerful Git integration, but creating reports usually involves dragging visuals in Power BI Desktop.
**Fabric MCP Server** transforms this into an **Infrastructure-as-Code (IaC)** workflow for BI.

Instead of manual clicks, you can tell your AI agent:
> *"Generate a Sales Dashboard for Q3."*
> *"Deploy the Finance report to Prod and refresh the dataset."*
> *"Apply the Dark Executive theme to all reports in Workspace X."*

This eliminates manual `.pbix` creation and ensures every report is:
*   **Versioned:** Tracked in Git.
*   **Consistent:** Built from standard templates.
*   **Automated:** Deployed via CI/CD pipelines.

## ✨ Capabilities

- **Workspaces:** List and inspect Fabric workspaces.
- **Git Sync:** Trigger `updateFromGit` to pull changes from a connected branch (CI/CD).
- **Report Generation:** Create new reports from pre-built `.pbip` templates.
- **Theme Generator:** Dynamically create Power BI JSON themes based on brand colors.
- **Dataset Refresh:** Trigger refreshes for Semantic Models.

## 📦 Installation

```bash
pip install fabric-mcp-server-powerbi-creator
```

## 🚀 Quick Start

### 1. Configuration (Interactive Login)
Simply log in with the Azure CLI (no secrets required!):
```bash
az login
```
This automatically authenticates you as your user account.

*(Optional) Service Principal (SPN):*
For headless CI/CD pipelines, you can set environment variables:
```bash
export FABRIC_TENANT_ID="your-tenant-id"
export FABRIC_CLIENT_ID="your-client-id"
export FABRIC_CLIENT_SECRET="your-client-secret"
```

### 2. Run the Server
```bash
# Run with stdio transport (default for AI agents)
fabric-mcp-server-powerbi-creator
```

### 3. Connect to Claude Desktop / OpenClaw
Add the server configuration to your agent's config file:
```json
{
  "mcpServers": {
    "fabric-powerbi": {
      "command": "fabric-mcp-server-powerbi-creator",
      "args": []
    }
  }
}
```

## 🛠️ Available Tools

| Tool | Description |
|------|-------------|
| `list_workspaces` | Lists all workspaces the user has access to. |
| `sync_workspace` | Updates a workspace from its connected Git branch (Deploy). |
| `list_templates` | Shows available report templates (e.g., Executive, Sales). |
| `apply_template` | Creates a new report in a local directory using a template. |
| `generate_theme` | Generates a Power BI theme JSON from hex codes. |

## 🏗️ Architecture

This server acts as a bridge between the **MCP Protocol** and the **Microsoft Fabric REST API**.
It uses standard `git/updateFromGit` and `git/commitToGit` endpoints to ensure all changes are tracked and versioned.

## 🤝 Contributing

We welcome templates! If you have a great `.pbip` layout, submit a PR to `templates/`.

## 📄 License
MIT
