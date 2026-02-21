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

    def connect_workspace_to_git(
        self, 
        workspace_id: str, 
        git_provider_type: str,
        organization_name: str,
        project_name: str,
        repository_name: str,
        branch_name: str,
        directory_name: str = "/"
    ) -> Dict[str, Any]:
        """
        Connects a workspace to a Git repository.
        This enables the workspace to sync with templates/reports stored in Git.
        
        Args:
            workspace_id: The Fabric workspace ID
            git_provider_type: "AzureDevOps" or "GitHub"
            organization_name: Git organization/account name
            project_name: Project name (for Azure DevOps) or repo owner (for GitHub)
            repository_name: Name of the Git repository
            branch_name: Branch to connect to (e.g., "main")
            directory_name: Subfolder path in the repo (default: "/")
        """
        url = f"{self.base_url}/workspaces/{workspace_id}/git/connect"
        
        body = {
            "gitProviderDetails": {
                "gitProviderType": git_provider_type,
                "organizationName": organization_name,
                "projectName": project_name,
                "repositoryName": repository_name,
                "branchName": branch_name,
                "directoryName": directory_name
            }
        }
        
        response = requests.post(url, headers=self._get_headers(), json=body)
        response.raise_for_status()
        return response.json()

    def get_workspace_git_status(self, workspace_id: str) -> Dict[str, Any]:
        """
        Gets the Git connection status for a workspace.
        Shows if workspace is connected and what changes are pending.
        """
        url = f"{self.base_url}/workspaces/{workspace_id}/git/status"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()

# Singleton instance for easy import
client = FabricClient()
