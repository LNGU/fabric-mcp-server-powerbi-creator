import os
from typing import List, Dict

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')

def list_templates() -> List[Dict[str, str]]:
    """Lists available report templates from the local directory."""
    # For now, return a static list until we have actual files
    return [
        {"name": "executive-summary", "description": "High-level KPIs for C-suite."},
        {"name": "sales-performance", "description": "Regional sales breakdown and trends."},
        {"name": "finance-overview", "description": "P&L statement and cash flow analysis."}
    ]

def apply_template(template_name: str, workspace_id: str, report_name: str) -> Dict[str, str]:
    """
    Simulates applying a template to a workspace.
    In a real implementation, this would:
    1. Read the .pbip template.
    2. Replace dataset connections with workspace-specific ones.
    3. Upload the files to Fabric via Git integration or API.
    """
    # Validation
    valid_names = [t["name"] for t in list_templates()]
    if template_name not in valid_names:
        raise ValueError(f"Template '{template_name}' not found. Available: {valid_names}")

    # TODO: Implement actual Fabric Git API call here
    return {
        "status": "success",
        "message": f"Created report '{report_name}' in workspace '{workspace_id}' using template '{template_name}'.",
        "action": "git_push_simulated"
    }
