import requests
from azure.identity import DefaultAzureCredential
from typing import List, Dict, Any

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

    def list_workspaces(self) -> List[Dict[str, Any]]:
        """
        List all workspaces the user has access to.
        Returns a list of workspace dictionaries containing id, displayName, description, etc.
        """
        url = f"{self.base_url}/workspaces"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        
        # The API returns a JSON object with a 'value' key containing the list
        data = response.json()
        return data.get("value", [])

    def update_workspace_from_git(self, workspace_id: str, remote_commit_hash: str = None) -> Dict[str, Any]:
        """
        Triggers a 'Update from Git' operation on the specified workspace.
        This syncs the workspace content with the connected Git branch.
        """
        url = f"{self.base_url}/workspaces/{workspace_id}/git/updateFromGit"
        
        body = {
            "remoteCommitHash": remote_commit_hash
        } if remote_commit_hash else {}

        response = requests.post(url, headers=self._get_headers(), json=body)
        response.raise_for_status()
        
        # Returns an operation ID (long running operation)
        return response.json()

# Singleton instance for easy import
client = FabricClient()
