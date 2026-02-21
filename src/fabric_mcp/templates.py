import os
import shutil
import json
from typing import List, Dict

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')

def list_templates() -> List[Dict[str, str]]:
    """Lists available report templates from the local directory."""
    # Dynamically list folders in TEMPLATE_DIR
    templates = []
    if os.path.exists(TEMPLATE_DIR):
        for name in os.listdir(TEMPLATE_DIR):
            path = os.path.join(TEMPLATE_DIR, name)
            if os.path.isdir(path):
                templates.append({
                    "name": name,
                    "description": f"Standard {name.replace('-', ' ')} template."
                })
    
    if not templates:
         return [
            {"name": "executive-summary", "description": "High-level KPIs for C-suite."},
            {"name": "sales-performance", "description": "Regional sales breakdown and trends."},
            {"name": "finance-overview", "description": "P&L statement and cash flow analysis."}
        ]
    return templates

def apply_template(template_name: str, destination_path: str, report_name: str) -> Dict[str, str]:
    """
    Copies a template to a local destination directory (git repo).
    
    Args:
        template_name: Name of the template (e.g., 'sales-performance')
        destination_path: Local path to the Fabric Git repository root
        report_name: Name for the new report (will create report_name.pbip)
    """
    src_path = os.path.join(TEMPLATE_DIR, template_name)
    
    if not os.path.exists(src_path):
        raise ValueError(f"Template '{template_name}' not found at {src_path}")

    # Destination: destination_path / report_name
    # PBIP folders typically contain the .pbip file and the .Report folder.
    # We rename the folder to match the report name.
    
    dest_full_path = os.path.join(destination_path, report_name)
    
    if os.path.exists(dest_full_path):
        raise FileExistsError(f"Destination '{dest_full_path}' already exists.")
        
    shutil.copytree(src_path, dest_full_path)
    
    # Rename internal files if necessary (e.g. sales.pbip -> NewReport.pbip)
    # For simplicity, we just copy the folder structure for now.
    # In a real app, we might parse the .pbip and update references.

    return {
        "status": "success",
        "message": f"Created report '{report_name}' at '{dest_full_path}' using template '{template_name}'.",
        "path": dest_full_path
    }
