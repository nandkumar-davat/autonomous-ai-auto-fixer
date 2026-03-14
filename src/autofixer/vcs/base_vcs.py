from abc import ABC, abstractmethod
from typing import List, Optional
from autofixer.models.finding import Finding

class BaseVCSClient(ABC):
    """Abstract base class for Version Control System clients."""

    @abstractmethod
    def create_pull_request(
        self, 
        repo_name: str, 
        branch_name: str, 
        title: str, 
        body: str, 
        base_branch: str = "main"
    ) -> str:
        """Creates a pull request and returns the PR identifier/URL."""
        pass

    @abstractmethod
    def get_pr_comments(self, pr_id: str) -> List[dict]:
        """Retrieves comments for a specific pull request."""
        pass

    @abstractmethod
    def add_pr_comment(self, pr_id: str, body: str) -> None:
        """Adds a comment to a specific pull request."""
        pass

    @abstractmethod
    def check_build_status(self, pr_id: str) -> Optional[str]:
        """Checks the build status of a PR. Returns status string or None."""
        pass
