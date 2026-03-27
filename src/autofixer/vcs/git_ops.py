import os
import shutil
from pathlib import Path
from typing import Optional
import git
from structlog import get_logger

logger = get_logger()

class GitOperations:
    """Handles local git operations like cloning, branching, and committing."""

    def __init__(self, workspace_dir: str = "workspace", github_token: Optional[str] = None):
        self.workspace_dir = Path(workspace_dir)
        self.github_token = github_token
        if not self.workspace_dir.exists():
            self.workspace_dir.mkdir(parents=True)

    def clone_repository(self, repo_url: str, repo_name: str) -> git.Repo:
        """Clones a repository into the workspace directory."""
        repo_path = self.workspace_dir / repo_name
        
        # Use authenticated URL if token is available
        if self.github_token and repo_url.startswith("https://github.com"):
            auth_url = repo_url.replace("https://github.com", f"https://{self.github_token}@github.com")
        else:
            auth_url = repo_url
            
        if repo_path.exists():
            logger.info("Repository already exists, pulling latest changes", path=repo_path)
            repo = git.Repo(repo_path)
            try:
                repo.remotes.origin.pull()
            except Exception as e:
                logger.warning("Failed to pull latest changes", error=str(e))
        else:
            logger.info("Cloning repository", url=repo_url, path=repo_path)
            repo = git.Repo.clone_from(auth_url, repo_path)
        return repo

    def create_branch(self, repo: git.Repo, branch_name: str) -> None:
        """Creates and switches to a new branch from current head."""
        logger.info("Creating new branch", branch=branch_name)
        new_branch = repo.create_head(branch_name)
        new_branch.checkout()

    def apply_patch(self, repo_path: Path, file_relative_path: str, new_content: str) -> None:
        """Overwrites the content of a file with new content."""
        full_path = repo_path / file_relative_path
        logger.info("Applying fix to file", path=full_path)
        
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(new_content)

    def commit_and_push(self, repo: git.Repo, branch_name: str, message: str) -> None:
        """Commits all changes and pushes to the remote repository."""
        logger.info("Committing changes", message=message)
        repo.git.add(A=True)
        repo.index.commit(message)
        
        logger.info("Pushing to remote", branch=branch_name)
        origin = repo.remote(name='origin')
        origin.push(branch_name)

    def cleanup_workspace(self) -> None:
        """Deletes everything in the workspace directory."""
        if self.workspace_dir.exists():
            logger.info("Cleaning up workspace", directory=self.workspace_dir)
            shutil.rmtree(self.workspace_dir)
            self.workspace_dir.mkdir()
