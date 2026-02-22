# Fabric MCP Server 🚀

**Create Power BI reports by talking to AI — no manual clicking required.**

A Model Context Protocol (MCP) server that lets AI agents deploy complete Power BI solutions to Microsoft Fabric. Skip the Power BI Desktop learning curve and describe what you want instead.

## 💡 The Big Idea

**Traditional workflow:** Open Power BI Desktop → Learn the interface → Click through menus → Build visuals → Configure data sources → Publish → Hope it works.

**With this MCP server:** Tell your AI agent what you want → AI generates everything → Deploys directly to Fabric → Done.

### Why This Matters

1. **Zero UI Required** — You never touch Power BI Desktop. The AI writes all the JSON/TMDL definitions.
2. **Conversational Iteration** — Want to change the chart colors? Add a filter? Just say so.
3. **Screenshot-to-Report** — Share a screenshot of a report you like, and AI will mimic the layout and style.
4. **Full Automation** — From raw CSV to live dashboard in one conversation.

### Example Conversations

```
You: "Create a sales dashboard from this CSV with revenue by region and monthly trends"
AI: [uploads data, creates model, builds report with bar chart + line chart, deploys to Fabric]

You: "Make it look like this" [attaches screenshot]
AI: [adjusts colors, layout, adds similar visuals to match the screenshot]

You: "Add a slicer for product category"
AI: [adds slicer, redeploys]
```

## 🔄 How It Works

The server automates the complete data-to-report workflow:

1. **Upload CSV Data** → Write to Lakehouse OneLake storage (ADLS Gen2)
2. **Create Delta Tables** → Load CSV into queryable Lakehouse tables
3. **Deploy Semantic Model** → Push TMDL definitions to Git
4. **Deploy Report** → Push PBIR report with visuals to Git
5. **Sync to Fabric** → Trigger "Update from Git" to create workspace items
6. **Refresh Model** → Load data into semantic model via Power BI API

## ✨ Capabilities

| Category | Features |
|----------|----------|
| **Data Loading** | Upload CSV to OneLake, create Delta tables |
| **Semantic Models** | Generate TMDL with Direct Lake connection, measures, relationships |
| **Reports** | Generate PBIR with cards, bar charts, line charts, tables, slicers |
| **Git Operations** | Push to Azure DevOps, sync workspace from Git |
| **Workspace Management** | List workspaces, check Git status, refresh models |
| **Themes** | Generate Power BI JSON themes from hex colors |

## 📦 Installation

### Prerequisites

- **Python 3.10+**
- **Azure CLI** (for authentication): `az login`
- **Azure SDK**: `pip install azure-storage-file-datalake azure-identity`
- **Fabric Workspace** connected to Azure DevOps Git repo (one-time setup in Fabric portal)

### Install from Source

```bash
git clone https://github.com/yourorg/fabric-mcp-server-powerbi-creator.git
cd fabric-mcp-server-powerbi-creator

# Create virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1  # Windows PowerShell

# Install
pip install -e .
pip install azure-storage-file-datalake azure-identity
```

### Verify Installation

```bash
python -c "import fabric_mcp; print('OK')"
```

## 🚀 Quick Start

### 1. Authenticate with Azure (REQUIRED)

You MUST authenticate before using the MCP server:

```bash
az login
```

This uses Azure CLI for authentication. Without this step, all API calls will fail.

### 2. Get Your Fabric Information

The MCP server will ask you for:

| Information | How to Get It |
|-------------|---------------|
| **Workspace URL** | Go to Fabric portal → Open your workspace → Copy URL from browser<br>`https://app.fabric.microsoft.com/groups/<WORKSPACE_ID>/...` |
| **Lakehouse** | The server will list available Lakehouses for you to choose |
| **Azure DevOps Repo URL** | Go to Azure DevOps → Repos → Clone → Copy HTTPS URL<br>`https://org.visualstudio.com/project/_git/repo` |

### 3. Configure MCP Client

Add to your AI agent's MCP configuration:

**Claude Desktop** (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "fabric": {
      "command": "fabric-mcp-server-powerbi-creator"
    }
  }
}
```

**Cursor** (`.cursor/mcp.json`):
```json
{
  "mcpServers": {
    "fabric": {
      "command": "C:/path/to/project/.venv/Scripts/fabric-mcp-server-powerbi-creator.exe"
    }
  }
}
```

## 🛠️ Available Tools

### Workspace Management

| Tool | Description |
|------|-------------|
| `list_workspaces` | List all Fabric workspaces you have access to |
| `get_git_status` | Check Git connection and pending changes for a workspace |
| `sync_workspace` | Trigger "Update from Git" to pull changes into Fabric |

### Data Loading

| Tool | Description |
|------|-------------|
| `list_lakehouses` | List all Lakehouses in a workspace |
| `list_lakehouse_tables` | List Delta tables in a Lakehouse |
| `upload_csv_to_lakehouse` | Upload local CSV to Lakehouse OneLake storage |
| `load_csv_to_lakehouse` | Load CSV from Files into a Delta table |

### Deployment

| Tool | Description |
|------|-------------|
| `deploy_semantic_model` | Deploy TMDL semantic model to Git |
| `deploy_report_with_model` | Deploy semantic model + report together to Git |
| `refresh_semantic_model` | Refresh model to load data from Lakehouse |

### Utilities

| Tool | Description |
|------|-------------|
| `generate_theme` | Generate Power BI JSON theme from hex colors |
| `deploy_report` | Deploy a simple report template (legacy) |

## 📖 Workflow Examples

### Basic: Describe What You Want

```
You: "Create a sales dashboard from sales-data.csv. Show revenue by region 
     as a bar chart and monthly trends as a line chart."

AI: "I'll need your Fabric workspace URL and Azure DevOps repo URL."

You: [paste URLs]

AI: [uploads CSV → creates Delta table → builds semantic model → 
     generates report with bar chart + line chart → deploys to Fabric]

"Done! Your report 'SalesReport' is live in Fabric."
```

### Advanced: Start from a Screenshot

```
You: "I want my report to look like this:" [attaches screenshot of existing report]

AI: "I can see a dark theme with card KPIs at top, donut chart on left, 
     and trend line on right. I'll create something similar."

[AI analyzes the screenshot and generates visuals that mimic the layout, 
 colors, and chart types]

"Deployed! Check Fabric to see the report."

You: "The colors are too bright. Use #1a1a2e as background."

AI: [regenerates theme, redeploys]

"Updated with darker background."
```

### Pro Tip: Iterative Refinement

The real power is **iteration**. Unlike manual Power BI work, you can rapidly experiment:

- "Add a date slicer"
- "Change the bar chart to horizontal"  
- "Add a YoY growth measure"
- "Make the fonts bigger"

Each change: AI modifies the JSON → pushes to Git → syncs to Fabric → done.

---

## 🔧 What Happens Under the Hood

When you deploy a report, the MCP server:

```
1. list_workspaces() → Extract workspace ID from URL
2. list_lakehouses(workspace_id) → Find available Lakehouses
3. upload_csv_to_lakehouse(workspace_id, lakehouse_id, "sales-data.csv")
   → Writes to OneLake Files/
4. load_csv_to_lakehouse(workspace_id, lakehouse_id, "fact_Sales", "Files/sales-data.csv")
   → Creates Delta table
5. deploy_report_with_model(repo_url, branch, model_name, report_name, ...)
   → Pushes TMDL + PBIR to Git
6. sync_workspace(workspace_id)
   → Triggers "Update from Git" in Fabric (async polling)
7. refresh_semantic_model(workspace_id, model_name)
   → Loads data from Lakehouse into model

Result: Live Power BI report in Fabric!
```

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Local CSV     │───▶│  OneLake Storage │───▶│  Delta Tables   │
│   (your data)   │    │  (ADLS Gen2)     │    │  (Lakehouse)    │
└─────────────────┘    └──────────────────┘    └────────┬────────┘
                                                        │
                                                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Azure DevOps   │◀───│   MCP Server     │───▶│  Fabric API     │
│  Git Repository │    │  (this project)  │    │  (sync/refresh) │
└────────┬────────┘    └──────────────────┘    └─────────────────┘
         │
         ▼
┌─────────────────┐    ┌──────────────────┐
│  Fabric Sync    │───▶│  Workspace Items │
│  (updateFromGit)│    │  (Model + Report)│
└─────────────────┘    └──────────────────┘
```

**Key Components:**

| File | Purpose |
|------|---------|
| `server.py` | MCP server with all tools |
| `fabric_api.py` | Fabric REST API client (async polling) |
| `lakehouse.py` | OneLake upload + Delta table loading |
| `semantic_model.py` | TMDL semantic model builder (Direct Lake) |
| `report_builder.py` | PBIR report builder with visuals |
| `theme_generator.py` | Power BI JSON theme generator |

## 🔧 Configuration

### Environment Variables (Optional)

For CI/CD or service principal authentication:

```bash
# Windows PowerShell
$env:FABRIC_TENANT_ID="your-tenant-id"
$env:FABRIC_CLIENT_ID="your-client-id"
$env:FABRIC_CLIENT_SECRET="your-client-secret"
```

### Workspace Git Connection

Your Fabric workspace must be connected to an Azure DevOps Git repository:

1. Open Fabric portal → Workspace settings → Git integration
2. Connect to Azure DevOps
3. Select organization, project, repository, branch
4. Initialize sync

This is a one-time setup per workspace.

## 📁 Project Structure

```
fabric-mcp-server-powerbi-creator/
├── src/fabric_mcp/
│   ├── server.py           # MCP server + tools
│   ├── fabric_api.py       # Fabric REST API client
│   ├── lakehouse.py        # OneLake + Delta table operations
│   ├── semantic_model.py   # TMDL builder (Direct Lake)
│   ├── report_builder.py   # PBIR builder with visuals
│   └── theme_generator.py  # Power BI theme generator
├── examples/
│   └── deploy_report_e2e.py  # Complete workflow example
├── test-templates/
│   └── sales-dashboard/      # Sample data + template
├── templates/
│   └── *.json               # Power BI theme templates
├── pyproject.toml
└── README.md
```

## 🧪 Testing

Run the example script to test the full workflow:

```bash
# 1. First authenticate
az login

# 2. Edit the example file and fill in YOUR values:
#    - WORKSPACE_ID (from Fabric workspace URL)
#    - LAKEHOUSE_ID (from Lakehouse URL)
#    - REPO_URL (Azure DevOps repo)
#    - BRANCH

# 3. Run the example
cd fabric-mcp-server-powerbi-creator
$env:PYTHONPATH = "src"
python examples/deploy_report_e2e.py
```

This will:
1. Upload `test-templates/sales-dashboard/sales-data.csv` to Lakehouse
2. Create `fact_Sales` Delta table
3. Deploy `SalesModel` semantic model
4. Deploy `SalesReport` with 5 visuals
5. Sync workspace from Git
6. Refresh semantic model

## ⚠️ Troubleshooting

| Issue | Solution |
|-------|----------|
| "Failed to get token" / 401 Unauthorized | Run `az login` first to authenticate |
| `ModuleNotFoundError: azure` | `pip install azure-storage-file-datalake azure-identity` |
| "Workspace Git state is NotConnected" | Connect workspace to Git in Fabric portal |
| "DiscoverDependenciesFailed" on sync | Delete conflicting items from workspace first |
| Report shows "Error fetching data" | Run `refresh_semantic_model()` after sync |
| Visuals blank but no error | Verify Delta table has data, refresh model |
| "Invalid workspace ID" | Copy workspace ID from Fabric URL (GUID after `/groups/`) |

## 📜 License

MIT License - see LICENSE file for details.

## 🙏 Credits

Inspired by [FabricAI](https://github.com/microsoft/FabricAI) deployment patterns for Direct Lake semantic models.
