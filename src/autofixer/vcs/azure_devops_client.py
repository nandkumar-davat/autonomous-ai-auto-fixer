from typing import List, Optional
from azure.devops.connection import Connection
from msrest.authentication import BasicAuthentication
from azure.devops.v7_1.git.models import GitPullRequest, GitPullRequestSearchCriteria
from autofixer.vcs.base_vcs import BaseVCSClient
from structlog import get_logger

logger = get_logger()

class AzureDevOpsClient(BaseVCSClient):
    """Client for Azure DevOps Repos."""

    def __init__(self, org_url: str, project: str, personal_access_token: str):
        self.org_url = org_url
        self.project = project
        self.credentials = BasicAuthentication('', personal_access_token)
        self.connection = Connection(base_url=org_url, creds=self.credentials)
        self.git_client = self.connection.get_client('azure.devops.v7_1.git.git_client.GitClient')

    def create_pull_request(
        self, 
        repo_name: str, 
        branch_name: str, 
        title: str, 
        body: str, 
        base_branch: str = "main"
    ) -> str:
        """Creates a PR in Azure Repos."""
        logger.info("Creating Azure DevOps PR", repo=repo_name, branch=branch_name)
        
        # Find the repository ID
        repo = self.git_client.get_repository(repo_name, project=self.project)
        
        pr_to_create = GitPullRequest(
            title=title,
            description=body,
            source_ref_name=f"refs/heads/{branch_name}",
            target_ref_name=f"refs/heads/{base_branch}"
        )
        
        created_pr = self.git_client.create_pull_request(pr_to_create, repository_id=repo.id, project=self.project)
        logger.info("Azure DevOps PR created", pr_url=created_pr.url)
        return created_pr.url

    def get_pr_comments(self, pr_id: str) -> List[dict]:
        """Retrieves PR threads/comments."""
        # Azure DevOps uses threads for PR comments
        # pr_id in Azure DevOps is an integer
        repo_id = None # Would need to be stored or fetched
        # This is a simplified implementation
        threads = self.git_client.get_threads(repository_id="TODO", pull_request_id=int(pr_id), project=self.project)
        comments = []
        for thread in threads:
            for comment in thread.comments:
                comments.append({
                    "author": comment.author.display_name,
                    "content": comment.content,
                    "published_date": comment.published_date
                })
        return comments

    def add_pr_comment(self, pr_id: str, body: str) -> None:
        """Adds a comment/thread to the PR."""
        from azure.devops.v7_1.git.models import GitPullRequestCommentThread, Comment
        
        thread = GitPullRequestCommentThread(
            comments=[Comment(content=body)],
            status='active'
        )
        self.git_client.create_thread(thread, repository_id="TODO", pull_request_id=int(pr_id), project=self.project)

    def check_build_status(self, pr_id: str) -> Optional[str]:
        """Checks associated build status/statuses."""
        # In Azure DevOps, this often involves the Build client and checking statuses on the commit
        return "Not Implemented"
