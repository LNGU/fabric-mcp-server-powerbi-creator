"""
End-to-end example: Upload data → Create Delta table → Deploy semantic model + report.

BEFORE RUNNING:
1. Run `az login` to authenticate with Azure
2. Fill in the configuration below with YOUR values:
   - WORKSPACE_ID: Go to your Fabric workspace in browser, copy the ID from the URL
     Example URL: https://app.fabric.microsoft.com/groups/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx/
     The ID is the GUID after /groups/
   - LAKEHOUSE_ID: Go to your Lakehouse in Fabric, copy the ID from the URL
   - REPO_URL: Your Azure DevOps Git repository URL
     Example: https://org.visualstudio.com/project/_git/repo
   - BRANCH: The branch connected to your Fabric workspace

This demonstrates the COMPLETE workflow:
1. Upload CSV to Lakehouse OneLake storage
2. Load CSV into Delta table via Fabric API
3. Build semantic model (TMDL) referencing the table
4. Build report (PBIR) with visuals
5. Push to Azure DevOps Git
6. Sync workspace from Git
7. Refresh semantic model to load data
"""
import json
import os
import subprocess
import time
import urllib.request
import urllib.parse
import urllib.error
import re
from pathlib import Path

# =============================================================================
# CONFIGURATION - FILL IN YOUR VALUES
# =============================================================================
# Get Workspace ID from Fabric URL: https://app.fabric.microsoft.com/groups/<WORKSPACE_ID>/...
WORKSPACE_ID = ""  # YOUR workspace ID (GUID)

# Get Lakehouse ID from Fabric URL when viewing your Lakehouse
LAKEHOUSE_ID = ""  # YOUR lakehouse ID (GUID)

# Your Azure DevOps Git repo URL (must be connected to Fabric workspace)
REPO_URL = ""  # e.g., https://org.visualstudio.com/project/_git/repo

# Branch connected to Fabric workspace
BRANCH = "main"  # or "PowerBI", etc.

ONELAKE_URL = "https://onelake.dfs.fabric.microsoft.com"

MODEL_NAME = "SalesModel"
REPORT_NAME = "SalesReport"
TABLE_NAME = "fact_Sales"
CSV_FILE = Path(__file__).parent.parent / "test-templates" / "sales-dashboard" / "sales-data.csv"

# =============================================================================
# VALIDATION - Check configuration before running
# =============================================================================
def validate_config():
    """Check that all required configuration values are filled in."""
    errors = []
    if not WORKSPACE_ID:
        errors.append("WORKSPACE_ID is empty. Get it from your Fabric workspace URL.")
    if not LAKEHOUSE_ID:
        errors.append("LAKEHOUSE_ID is empty. Get it from your Lakehouse URL in Fabric.")
    if not REPO_URL:
        errors.append("REPO_URL is empty. Enter your Azure DevOps repo URL.")
    if errors:
        print("=" * 60)
        print("ERROR: Configuration incomplete!")
        print("=" * 60)
        print("\nPlease edit this file and fill in the configuration values:\n")
        for err in errors:
            print(f"  - {err}")
        print("\nSee instructions at the top of this file.")
        print("Make sure you have run 'az login' first!")
        raise SystemExit(1)

validate_config()

AZ_CMD = r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"
if not os.path.exists(AZ_CMD):
    AZ_CMD = "az"


def get_token(resource):
    cmd = [AZ_CMD, "account", "get-access-token", "--resource", resource,
           "--query", "accessToken", "-o", "tsv"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, 
                           shell=AZ_CMD.endswith(".cmd"))
    if result.returncode != 0:
        raise RuntimeError(f"Failed to get token: {result.stderr}")
    return result.stdout.strip()


def api(method, url, token, data=None):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            txt = resp.read().decode()
            return resp.status, json.loads(txt) if txt.strip() else {}, dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode()[:2000]}, {}


def poll_operation(url, token, max_polls=30, interval=5):
    """Poll a long-running operation."""
    for i in range(max_polls):
        time.sleep(interval)
        code, data, _ = api("GET", url, token)
        status = data.get("status", "unknown")
        print(f"    Poll {i+1}: {status}")
        if status in ("Succeeded", "Completed"):
            return True, data
        if status in ("Failed", "Cancelled"):
            return False, data
    return False, {"error": "timeout"}


# =============================================================================
# Step 1: Upload CSV to OneLake
# =============================================================================
print("=" * 60)
print("Step 1: Upload CSV to Lakehouse OneLake")
print("=" * 60)

from azure.storage.filedatalake import DataLakeServiceClient
from azure.identity import DefaultAzureCredential

print(f"CSV: {CSV_FILE}")
print(f"Size: {CSV_FILE.stat().st_size:,} bytes")

credential = DefaultAzureCredential()
service_client = DataLakeServiceClient(account_url=ONELAKE_URL, credential=credential)
fs_client = service_client.get_file_system_client(WORKSPACE_ID)

# Upload to Files/mcp_test/
upload_path = f"{LAKEHOUSE_ID}/Files/mcp_test/sales-data.csv"
print(f"Uploading to: {upload_path}")

# Ensure directory exists
dir_path = f"{LAKEHOUSE_ID}/Files/mcp_test"
dir_client = fs_client.get_directory_client(dir_path)
try:
    dir_client.create_directory()
    print("  Created directory")
except Exception:
    print("  Directory exists")

# Upload file
file_client = fs_client.get_file_client(upload_path)
with open(CSV_FILE, "rb") as f:
    file_client.upload_data(f, overwrite=True)
print("  [OK] Uploaded!")


# =============================================================================
# Step 2: Load CSV into Delta table
# =============================================================================
print("\n" + "=" * 60)
print("Step 2: Load CSV into Delta table")
print("=" * 60)

fabric_token = get_token("https://api.fabric.microsoft.com")
print(f"Table name: {TABLE_NAME}")

load_body = {
    "relativePath": "Files/mcp_test/sales-data.csv",
    "pathType": "File",
    "mode": "Overwrite",
    "formatOptions": {
        "format": "Csv",
        "header": True,
        "delimiter": ",",
    },
}

url = f"https://api.fabric.microsoft.com/v1/workspaces/{WORKSPACE_ID}/lakehouses/{LAKEHOUSE_ID}/tables/{TABLE_NAME}/load"
code, data, headers = api("POST", url, fabric_token, load_body)

if code == 202:
    op_url = headers.get("Location", "")
    if op_url:
        print("  Loading (async)...")
        ok, result = poll_operation(op_url, fabric_token)
        if ok:
            print("  [OK] Table loaded!")
        else:
            print(f"  [FAIL] {result}")
            exit(1)
elif code == 200:
    print("  [OK] Table loaded!")
else:
    print(f"  [FAIL] {code}: {data}")
    exit(1)


# =============================================================================
# Step 3: Build Semantic Model
# =============================================================================
print("\n" + "=" * 60)
print("Step 3: Build Semantic Model (TMDL)")
print("=" * 60)

import sys
sys.path.insert(0, str(Path(__file__).parent / "src"))
from fabric_mcp.semantic_model import SemanticModelBuilder

sm_builder = SemanticModelBuilder(
    model_name=MODEL_NAME,
    lakehouse_workspace_id=WORKSPACE_ID,
    lakehouse_id=LAKEHOUSE_ID
)

# Define table schema matching the CSV
sm_builder.add_table(TABLE_NAME, [
    {"name": "Date", "dataType": "DateTime"},
    {"name": "Region", "dataType": "String"},
    {"name": "Product", "dataType": "String"},
    {"name": "SalesAmount", "dataType": "Int64"},
    {"name": "Quantity", "dataType": "Int64"},
    {"name": "Revenue", "dataType": "Int64"},
    {"name": "Profit", "dataType": "Int64"},
    {"name": "GrowthRate", "dataType": "Double"},
])

# Add measures
sm_builder.add_measure(TABLE_NAME, "Total Revenue", f"SUM({TABLE_NAME}[Revenue])", "#,##0")
sm_builder.add_measure(TABLE_NAME, "Total Profit", f"SUM({TABLE_NAME}[Profit])", "#,##0")
sm_builder.add_measure(TABLE_NAME, "Total Quantity", f"SUM({TABLE_NAME}[Quantity])", "#,##0")
sm_builder.add_measure(TABLE_NAME, "Avg Growth", f"AVERAGE({TABLE_NAME}[GrowthRate])", "0.0%")

sm_files = sm_builder.build_all_files()
print(f"Generated {len(sm_files)} files:")
for path in sm_files:
    print(f"  - {path}")


# =============================================================================
# Step 4: Build Report
# =============================================================================
print("\n" + "=" * 60)
print("Step 4: Build Report (PBIR)")
print("=" * 60)

from fabric_mcp.report_builder import ReportBuilder

rpt_builder = ReportBuilder(
    report_name=REPORT_NAME,
    semantic_model_name=MODEL_NAME
)

# Create visuals
visuals = [
    rpt_builder.card("Total Revenue", TABLE_NAME, "Total Revenue", x=20, y=20),
    rpt_builder.card("Total Profit", TABLE_NAME, "Total Profit", x=320, y=20),
    rpt_builder.card("Total Quantity", TABLE_NAME, "Total Quantity", x=620, y=20),
    rpt_builder.bar_chart("Revenue by Region", TABLE_NAME, "Region", "Revenue", 
                          aggregation="Sum", x=20, y=180, width=450, height=350),
    rpt_builder.bar_chart("Revenue by Product", TABLE_NAME, "Product", "Revenue", 
                          aggregation="Sum", x=490, y=180, width=450, height=350),
]
rpt_builder.add_page("Sales Overview", visuals)

rpt_files = rpt_builder.build_all_files()
print(f"Generated {len(rpt_files)} files:")
for path in rpt_files:
    print(f"  - {path}")


# =============================================================================
# Step 5: Push to Azure DevOps
# =============================================================================
print("\n" + "=" * 60)
print("Step 5: Push to Azure DevOps Git")
print("=" * 60)

ado_token = get_token("499b84ac-1321-427f-aa17-267ca6975798")

# Parse repo URL
match = re.match(r"https://([^.]+)\.visualstudio\.com/([^/]+)/_git/([^/?]+)", REPO_URL)
org, project, repo = match.groups()
print(f"Repo: {org}/{project}/{repo}")

# Get branch tip
url = f"https://dev.azure.com/{org}/{urllib.parse.quote(project)}/_apis/git/repositories/{urllib.parse.quote(repo)}/refs?filter=heads/{BRANCH}&api-version=7.0"
code, data, _ = api("GET", url, ado_token)
old_commit = [r["objectId"] for r in data.get("value", []) if r["name"] == f"refs/heads/{BRANCH}"][0]
print(f"Branch tip: {old_commit[:12]}...")

# Combine all files
all_files = {}
for path, content in sm_files.items():
    all_files[f"{MODEL_NAME}.SemanticModel/{path}"] = content
for path, content in rpt_files.items():
    all_files[f"{REPORT_NAME}.Report/{path}"] = content

print(f"Total files: {len(all_files)}")

# Check existing files
existing = set()
for rel_path in all_files.keys():
    check_url = f"https://dev.azure.com/{org}/{urllib.parse.quote(project)}/_apis/git/repositories/{urllib.parse.quote(repo)}/items?path=/{rel_path}&versionDescriptor.version={BRANCH}&api-version=7.0"
    headers = {"Authorization": f"Bearer {ado_token}"}
    req = urllib.request.Request(check_url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status == 200:
                existing.add(rel_path)
    except:
        pass

print(f"Existing: {len(existing)} / {len(all_files)}")

# Build changes
changes = []
for rel_path, content in all_files.items():
    change_type = "edit" if rel_path in existing else "add"
    changes.append({
        "changeType": change_type,
        "item": {"path": f"/{rel_path}"},
        "newContent": {"content": content, "contentType": "rawtext"},
    })

push_body = {
    "refUpdates": [{"name": f"refs/heads/{BRANCH}", "oldObjectId": old_commit}],
    "commits": [{"comment": f"Deploy {MODEL_NAME} + {REPORT_NAME} (MCP test)", "changes": changes}],
}

url = f"https://dev.azure.com/{org}/{urllib.parse.quote(project)}/_apis/git/repositories/{urllib.parse.quote(repo)}/pushes?api-version=7.0"
code, data, _ = api("POST", url, ado_token, push_body)

if code in (200, 201):
    new_commit = data.get("commits", [{}])[0].get("commitId", "unknown")
    print(f"[OK] Pushed! Commit: {new_commit[:12]}...")
else:
    print(f"[FAIL] {code}: {data}")
    exit(1)


# =============================================================================
# Step 6: Sync Workspace from Git
# =============================================================================
print("\n" + "=" * 60)
print("Step 6: Sync Workspace from Git")
print("=" * 60)

print("Waiting for Git to propagate...")
time.sleep(3)

# Get git status
url = f"https://api.fabric.microsoft.com/v1/workspaces/{WORKSPACE_ID}/git/status"
code, status, headers = api("GET", url, fabric_token)

if code == 202:
    loc = headers.get("Location", "")
    if loc:
        ok, status = poll_operation(loc, fabric_token)

workspace_head = status.get("workspaceHead", "")
remote_commit = status.get("remoteCommitHash", "")
changes = status.get("changes", [])

print(f"Workspace head: {workspace_head[:12] if workspace_head else 'N/A'}...")
print(f"Remote commit: {remote_commit[:12] if remote_commit else 'N/A'}...")
print(f"Pending changes: {len(changes)}")

for c in changes:
    meta = c.get("itemMetadata", {})
    change_type = c.get("remoteChange") or c.get("workspaceChange")
    print(f"  {change_type}: {meta.get('displayName')} ({meta.get('itemType')})")

if not changes:
    print("\nWorkspace is up to date!")
    exit(0)

# Trigger sync
url = f"https://api.fabric.microsoft.com/v1/workspaces/{WORKSPACE_ID}/git/updateFromGit"
body = {
    "remoteCommitHash": remote_commit,
    "workspaceHead": workspace_head,
    "conflictResolution": {
        "conflictResolutionType": "Workspace",
        "conflictResolutionPolicy": "PreferRemote"
    },
    "options": {"allowOverrideItems": True}
}

print("\nSyncing...")
code, result, headers = api("POST", url, fabric_token, body)

if code == 200:
    print("[OK] Synced!")
elif code == 202:
    loc = headers.get("Location", "")
    if loc:
        ok, result = poll_operation(loc, fabric_token, max_polls=60, interval=5)
        if ok:
            print("[OK] Synced!")
        else:
            print(f"[FAIL] {result}")
            exit(1)
else:
    print(f"[FAIL] {code}: {result}")
    exit(1)


# =============================================================================
# Step 7: Refresh Semantic Model
# =============================================================================
print("\n" + "=" * 60)
print("Step 7: Refresh Semantic Model (Direct Lake)")
print("=" * 60)

# Get Power BI API token
pbi_token = get_token("https://analysis.windows.net/powerbi/api")

# Find the semantic model ID
url = f"https://api.powerbi.com/v1.0/myorg/groups/{WORKSPACE_ID}/datasets"
code, data, _ = api("GET", url, pbi_token)

model_id = None
for ds in data.get("value", []):
    if ds.get("name") == MODEL_NAME:
        model_id = ds.get("id")
        print(f"Found: {MODEL_NAME} (ID: {model_id})")
        break

if not model_id:
    print(f"[WARN] Semantic model '{MODEL_NAME}' not found - may need time to propagate")
    print("Try refreshing manually in Fabric portal")
else:
    # Trigger refresh
    print("Triggering refresh...")
    url = f"https://api.powerbi.com/v1.0/myorg/groups/{WORKSPACE_ID}/datasets/{model_id}/refreshes"
    code, data, _ = api("POST", url, pbi_token, {"type": "Full"})
    
    if code == 202:
        print("  Refresh started, polling...")
        for i in range(30):
            time.sleep(5)
            url = f"https://api.powerbi.com/v1.0/myorg/groups/{WORKSPACE_ID}/datasets/{model_id}/refreshes?$top=1"
            code, data, _ = api("GET", url, pbi_token)
            vals = data.get("value", [])
            if vals:
                status = vals[0].get("status", "?")
                print(f"    Poll {i+1}: {status}")
                if status == "Completed":
                    print("  [OK] Refresh completed!")
                    break
                elif status in ("Failed", "Cancelled"):
                    print(f"  [FAIL] Refresh {status}")
                    print(f"    Error: {vals[0].get('serviceExceptionJson', 'N/A')}")
                    break
    elif code == 200:
        print("  [OK] Refresh completed!")
    else:
        print(f"  [FAIL] Refresh failed: {code} - {data}")


print("\n" + "=" * 60)
print("SUCCESS! Complete workflow executed.")
print("=" * 60)
print(f"Semantic Model: {MODEL_NAME}")
print(f"Report: {REPORT_NAME}")
print(f"Table: {TABLE_NAME}")
print("\nOpen Fabric portal to view the report!")
