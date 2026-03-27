from typing import List, Optional
from github import Github, Auth
from autofixer.vcs.base_vcs import BaseVCSClient
from structlog import get_logger

logger = get_logger()

class GitHubClient(BaseVCSClient):
    """Client for GitHub Repos using PyGithub."""

    def __init__(self, token: str):
        self.token = token
        self.demo_mode = token == "demo-token"
        if not self.demo_mode:
            self.auth = Auth.Token(token)
            self.github = Github(auth=self.auth)
        else:
            logger.info("GitHub client initialized in demo mode")

    def create_pull_request(
        self, 
        repo_name: str, 
        branch_name: str, 
        title: str, 
        body: str, 
        base_branch: str = "main"
    ) -> str:
        """Creates a PR on GitHub."""
        logger.info("Creating GitHub PR", repo=repo_name, branch=branch_name, demo_mode=self.demo_mode)
        
        if self.demo_mode:
            # Return mock PR URL for demo
            pr_url = f"https://github.com/{repo_name}/pull/123"
            logger.info("Demo mode: Mock GitHub PR created", pr_url=pr_url)
            return pr_url
        
        # Real GitHub API call
        repo = self.github.get_repo(repo_name)
        pr = repo.create_pull(
            title=title,
            body=body,
            head=branch_name,
            base=base_branch
        )
        logger.info("GitHub PR created", pr_url=pr.html_url)
        return pr.html_url

    def get_pr_comments(self, pr_id: str) -> List[dict]:
        """Retrieves PR issue comments and review comments."""
        # pr_id here could be repo_name:pr_number
        repo_name, pr_number = pr_id.split(':')
        repo = self.github.get_repo(repo_name)
        pr = repo.get_pull(int(pr_number))
        
        comments = []
        for comment in pr.get_issue_comments():
            comments.append({
                "author": comment.user.login,
                "content": comment.body,
                "type": "issue"
            })
        for comment in pr.get_review_comments():
            comments.append({
                "author": comment.user.login,
                "content": comment.body,
                "type": "review"
            })
        return comments

    def add_pr_comment(self, pr_id: str, body: str) -> None:
        """Adds a comment to the PR."""
        repo_name, pr_number = pr_id.split(':')
        repo = self.github.get_repo(repo_name)
        pr = repo.get_pull(int(pr_number))
        pr.create_issue_comment(body)

    def check_build_status(self, pr_id: str) -> Optional[str]:
        """Checks GitHub Actions/Checks status."""
        repo_name, pr_number = pr_id.split(':')
        repo = self.github.get_repo(repo_name)
        pr = repo.get_pull(int(pr_number))
        last_commit = pr.get_commits().reversed[0]
        status = last_commit.get_combined_status()
        return status.state
