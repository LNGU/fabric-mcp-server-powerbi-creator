# Templates Manager
# Handles listing, applying, and deploying template reports.

import os
import shutil
from pathlib import Path
from pydantic import BaseModel

TEMPLATE_DIR = Path("templates")

class ReportTemplate(BaseModel):
    name: str
    description: str
    layout_type: str  # Grid, Scrolling, Mobile

def list_templates() -> list[ReportTemplate]:
    """Scan the templates directory and return metadata."""
    templates = []
    # In a real implementation, we would scan subfolders.
    # For now, return mock data to demonstrate the structure.
    templates.append(ReportTemplate(name="Executive_Dark", description="High-contrast KPI dashboard", layout_type="Grid"))
    templates.append(ReportTemplate(name="Sales_Bright", description="Vibrant charts for marketing", layout_type="Scrolling"))
    return templates

def apply_template(template_name: str, target_workspace: str, output_name: str):
    """
    1. Clone the template folder.
    2. Update the definition.pbir to point to the correct semantic model.
    3. Generate/Inject the theme.json.
    4. Commit to Git to trigger Fabric sync.
    """
    src = TEMPLATE_DIR / template_name
    dest = Path(f"deployments/{target_workspace}/{output_name}")
    
    # 1. Clone
    # shutil.copytree(src, dest)
    
    # 2. Update config (Mock logic)
    print(f"Applied template {template_name} to {output_name} in {target_workspace}")
    return {"status": "success", "path": str(dest)}
