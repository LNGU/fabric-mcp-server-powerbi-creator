import requests
import time
from azure.identity import DefaultAzureCredential
from typing import List, Dict, Any, Tuple

class FabricClient:
    def __init__(self):
        self.credential = DefaultAzureCredential()
        self.base_url = "https://api.fabric.microsoft.com/v1"
        self._token = None

    def _get_token(self) -> str:
        if not self._token:
            token_object = self.credential.get_token("https://api.fabric.microsoft.com/.default")
            self._token = token_object.token
        return self._token

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json"
        }

    def _poll_operation(self, location: str, max_polls: int = 60, interval: int = 5) -> Tuple[bool, Dict]:
        """Poll a long-running operation until complete."""
        for i in range(max_polls):
            time.sleep(interval)
            response = requests.get(location, headers=self._get_headers())
            data = response.json() if response.text else {}
            status = data.get("status", "unknown")
            if status in ("Succeeded", "Completed"):
                return True, data
            if status in ("Failed", "Cancelled"):
                return False, data
        return False, {"error": "timeout", "message": "Operation timed out"}

    def list_workspaces(self) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/workspaces"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        data = response.json()
        return data.get("value", [])

    def get_workspace_git_connection(self, workspace_id: str) -> Dict[str, Any]:
        url = f"{self.base_url}/workspaces/{workspace_id}/git/connection"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()

    def get_workspace_git_status(self, workspace_id: str) -> Dict[str, Any]:
        url = f"{self.base_url}/workspaces/{workspace_id}/git/status"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        
        # Handle async response
        if response.status_code == 202:
            location = response.headers.get("Location", "")
            if location:
                ok, data = self._poll_operation(location)
                if ok:
                    return data
                raise RuntimeError(f"Git status poll failed: {data}")
        
        return response.json()

    def update_workspace_from_git(self, workspace_id: str, remote_commit_hash: str, 
                                   workspace_head: str = None,
                                   conflict_resolution_policy: str = "PreferRemote") -> Dict[str, Any]:
        url = f"{self.base_url}/workspaces/{workspace_id}/git/updateFromGit"
        body = {
            "remoteCommitHash": remote_commit_hash,
            "conflictResolution": {
                "conflictResolutionType": "Workspace",
                "conflictResolutionPolicy": conflict_resolution_policy
            },
            "options": {"allowOverrideItems": True}
        }
        if workspace_head:
            body["workspaceHead"] = workspace_head
        
        response = requests.post(url, headers=self._get_headers(), json=body)
        response.raise_for_status()
        
        if response.status_code == 200:
            return {"status": "Completed", "message": "Sync completed synchronously"}
        
        # Handle async response (202)
        if response.status_code == 202:
            location = response.headers.get("Location", "")
            if location:
                ok, data = self._poll_operation(location, max_polls=60, interval=5)
                if ok:
                    return {"status": "Completed", "data": data}
                raise RuntimeError(f"Sync failed: {data}")
        
        return response.json()

client = FabricClient()
