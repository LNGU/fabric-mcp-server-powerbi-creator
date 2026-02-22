"""
Lakehouse Operations for Fabric.

Provides functions to:
1. Upload CSV files to Lakehouse (OneLake Files)
2. Load CSV files into Delta tables
3. List tables in a Lakehouse

Requires:
  - Azure CLI logged in (az login)
  - pip install azure-storage-file-datalake azure-identity

Usage:
    from fabric_mcp.lakehouse import LakehouseClient
    
    client = LakehouseClient(workspace_id="...", lakehouse_id="...")
    
    # Upload CSVs
    client.upload_csv("data/sales.csv", "uploads/sales.csv")
    
    # Load into Delta table
    client.load_table("sales", "Files/uploads/sales.csv")
"""

import json
import os
import subprocess
import time
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple


# Azure CLI path (Windows-specific)
AZ_CMD = r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"
if not os.path.exists(AZ_CMD):
    AZ_CMD = "az"


def _get_fabric_token() -> str:
    """Get Fabric API token using Azure CLI."""
    cmd = f'"{AZ_CMD}" account get-access-token --resource https://api.fabric.microsoft.com --query accessToken -o tsv'
    result = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to get Fabric token: {result.stderr}")
    return result.stdout.strip()


def _api(method: str, url: str, token: str, data: dict = None) -> Tuple[int, dict, dict]:
    """Make Fabric REST API call."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            txt = resp.read().decode()
            return resp.status, json.loads(txt) if txt.strip() else {}, dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode()[:2000]}, dict(e.headers) if hasattr(e, "headers") else {}


class LakehouseClient:
    """Client for Lakehouse operations."""
    
    def __init__(
        self,
        workspace_id: str,
        lakehouse_id: str,
        onelake_url: str = "https://onelake.dfs.fabric.microsoft.com"
    ):
        """
        Initialize the Lakehouse client.
        
        Args:
            workspace_id: Workspace ID containing the Lakehouse
            lakehouse_id: Lakehouse ID
            onelake_url: OneLake URL (default: https://onelake.dfs.fabric.microsoft.com)
        """
        self.workspace_id = workspace_id
        self.lakehouse_id = lakehouse_id
        self.onelake_url = onelake_url
        self._token: Optional[str] = None
    
    def _get_token(self) -> str:
        """Get or refresh the Fabric API token."""
        if not self._token:
            self._token = _get_fabric_token()
        return self._token
    
    def upload_csv(
        self,
        local_path: str,
        remote_path: str
    ) -> bool:
        """
        Upload a CSV file to the Lakehouse Files folder.
        
        Args:
            local_path: Path to local CSV file
            remote_path: Destination path in Files folder (e.g., "uploads/data.csv")
        
        Returns:
            True if successful
        """
        # Import here to avoid requiring the package if not used
        from azure.storage.filedatalake import DataLakeServiceClient
        from azure.identity import DefaultAzureCredential
        
        local_file = Path(local_path)
        if not local_file.exists():
            raise FileNotFoundError(f"File not found: {local_path}")
        
        credential = DefaultAzureCredential()
        service_client = DataLakeServiceClient(
            account_url=self.onelake_url,
            credential=credential
        )
        
        # Workspace ID is the filesystem
        fs_client = service_client.get_file_system_client(self.workspace_id)
        
        # Build full path: {lakehouse_id}/Files/{remote_path}
        full_path = f"{self.lakehouse_id}/Files/{remote_path}"
        
        # Ensure parent directory exists
        parent_dir = str(Path(full_path).parent)
        dir_client = fs_client.get_directory_client(parent_dir)
        try:
            dir_client.create_directory()
        except Exception:
            pass  # Directory may already exist
        
        # Upload file
        file_client = fs_client.get_file_client(full_path)
        with open(local_file, "rb") as f:
            file_client.upload_data(f, overwrite=True)
        
        return True
    
    def upload_csvs_from_directory(
        self,
        local_directory: str,
        remote_folder: str = "uploads",
        pattern: str = "*.csv"
    ) -> Dict[str, bool]:
        """
        Upload all CSV files from a directory.
        
        Args:
            local_directory: Directory containing CSV files
            remote_folder: Destination folder in Files (e.g., "uploads")
            pattern: Glob pattern for files (default: *.csv)
        
        Returns:
            Dict of {filename: success}
        """
        results = {}
        local_dir = Path(local_directory)
        
        for csv_file in local_dir.glob(pattern):
            remote_path = f"{remote_folder}/{csv_file.name}"
            try:
                self.upload_csv(str(csv_file), remote_path)
                results[csv_file.name] = True
            except Exception as e:
                results[csv_file.name] = False
        
        return results
    
    def load_table(
        self,
        table_name: str,
        file_path: str,
        mode: str = "Overwrite",
        file_format: str = "Csv",
        has_header: bool = True,
        delimiter: str = ","
    ) -> bool:
        """
        Load a file from Files into a Delta table.
        
        Args:
            table_name: Name of the Delta table to create/update
            file_path: Path to file in Files folder (e.g., "Files/uploads/data.csv")
            mode: "Overwrite" or "Append"
            file_format: "Csv" or "Parquet"
            has_header: Whether CSV has header row
            delimiter: CSV delimiter
        
        Returns:
            True if successful
        """
        token = self._get_token()
        
        load_body = {
            "relativePath": file_path,
            "pathType": "File",
            "mode": mode,
            "formatOptions": {
                "format": file_format,
                "header": has_header,
                "delimiter": delimiter,
            },
        }
        
        url = (f"https://api.fabric.microsoft.com/v1/workspaces/{self.workspace_id}"
               f"/lakehouses/{self.lakehouse_id}/tables/{table_name}/load")
        
        code, data, headers = _api("POST", url, token, load_body)
        
        if code == 202:
            # Poll for completion
            op_url = headers.get("Location", "")
            if op_url:
                return self._poll_operation(op_url, token)
            return True
        elif code == 200:
            return True
        else:
            raise RuntimeError(f"Load table failed ({code}): {data}")
    
    def load_tables_from_csvs(
        self,
        table_file_mapping: Dict[str, str],
        mode: str = "Overwrite"
    ) -> Dict[str, bool]:
        """
        Load multiple CSVs into Delta tables.
        
        Args:
            table_file_mapping: Dict of {table_name: file_path}
                               e.g., {"sales": "Files/uploads/sales.csv"}
            mode: "Overwrite" or "Append"
        
        Returns:
            Dict of {table_name: success}
        """
        results = {}
        
        for table_name, file_path in table_file_mapping.items():
            try:
                self.load_table(table_name, file_path, mode)
                results[table_name] = True
            except Exception as e:
                results[table_name] = False
        
        return results
    
    def list_tables(self) -> List[Dict[str, Any]]:
        """
        List all tables in the Lakehouse.
        
        Returns:
            List of table info dicts with 'name', 'type', etc.
        """
        token = self._get_token()
        
        url = (f"https://api.fabric.microsoft.com/v1/workspaces/{self.workspace_id}"
               f"/lakehouses/{self.lakehouse_id}/tables")
        
        code, data, _ = _api("GET", url, token)
        
        if code == 200:
            return data.get("data", [])
        else:
            raise RuntimeError(f"List tables failed ({code}): {data}")
    
    def _poll_operation(
        self,
        op_url: str,
        token: str,
        max_polls: int = 30,
        interval: int = 5
    ) -> bool:
        """Poll a long-running operation until completion."""
        for _ in range(max_polls):
            time.sleep(interval)
            code, data, _ = _api("GET", op_url, token)
            status = data.get("status", "Unknown")
            
            if status in ("Succeeded", "Completed"):
                return True
            elif status in ("Failed", "Cancelled"):
                raise RuntimeError(f"Operation failed: {data}")
        
        raise RuntimeError("Operation timed out")


def get_lakehouse_info(workspace_id: str, lakehouse_id: str) -> Dict[str, Any]:
    """
    Get Lakehouse information.
    
    Args:
        workspace_id: Workspace ID
        lakehouse_id: Lakehouse ID
    
    Returns:
        Lakehouse info dict
    """
    token = _get_fabric_token()
    
    url = (f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}"
           f"/lakehouses/{lakehouse_id}")
    
    code, data, _ = _api("GET", url, token)
    
    if code == 200:
        return data
    else:
        raise RuntimeError(f"Get lakehouse failed ({code}): {data}")


def list_lakehouses(workspace_id: str) -> List[Dict[str, Any]]:
    """
    List all Lakehouses in a workspace.
    
    Args:
        workspace_id: Workspace ID
    
    Returns:
        List of Lakehouse info dicts
    """
    token = _get_fabric_token()
    
    url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/lakehouses"
    
    code, data, _ = _api("GET", url, token)
    
    if code == 200:
        return data.get("value", [])
    else:
        raise RuntimeError(f"List lakehouses failed ({code}): {data}")
