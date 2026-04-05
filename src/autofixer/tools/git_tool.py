"""Git tool wrapping common repository operations via GitPython."""

from pathlib import Path
from typing import Any, Dict, List, Optional

import git
from structlog import get_logger

from autofixer.tools.base import BaseTool

logger = get_logger()


class GitTool(BaseTool):
    """Wraps common git operations for a local repository.

    Parameters
    ----------
    repo_path:
        Path to the root of the git repository.  The repository is opened
        lazily on first use; pass a path to an existing clone or use
        :meth:`init_repo` / :meth:`clone` to create one.
    """

    name: str = "git"
    description: str = (
        "Perform common git operations: init, clone, branch, checkout, "
        "add, commit, push, diff, status."
    )

    def __init__(self, repo_path: str) -> None:
        self.repo_path = Path(repo_path)
        self._repo: Optional[git.Repo] = None

    # ------------------------------------------------------------------
    # Lazy repo accessor
    # ------------------------------------------------------------------

    @property
    def repo(self) -> git.Repo:
        """Return the ``git.Repo`` instance, opening it if necessary."""
        if self._repo is None:
            if not (self.repo_path / ".git").exists():
                raise RuntimeError(
                    f"No git repository at {self.repo_path}. "
                    "Call init_repo() or clone() first."
                )
            self._repo = git.Repo(self.repo_path)
        return self._repo

    # ------------------------------------------------------------------
    # BaseTool interface
    # ------------------------------------------------------------------

    def execute(self, *, action: str, **kwargs: Any) -> Dict[str, Any]:
        """Dispatch to the requested git *action*.

        Supported actions: ``init``, ``create_branch``, ``checkout``, ``add``,
        ``commit``, ``push``, ``diff``, ``status``.
        """
        dispatch = {
            "init": self._action_init,
            "create_branch": self._action_create_branch,
            "checkout": self._action_checkout,
            "add": self._action_add,
            "commit": self._action_commit,
            "push": self._action_push,
            "diff": self._action_diff,
            "status": self._action_status,
        }
        handler = dispatch.get(action)
        if handler is None:
            return {
                "success": False,
                "result": None,
                "error": f"Unknown git action: {action!r}. "
                f"Supported: {list(dispatch.keys())}",
            }
        try:
            return handler(**kwargs)
        except Exception as exc:
            logger.error("git.action_failed", action=action, error=str(exc))
            return {"success": False, "result": None, "error": str(exc)}

    # ------------------------------------------------------------------
    # Public convenience methods (also usable directly)
    # ------------------------------------------------------------------

    def init_repo(self, bare: bool = False) -> git.Repo:
        """Initialise a new git repository at :attr:`repo_path`."""
        logger.info("git.init", path=str(self.repo_path), bare=bare)
        self.repo_path.mkdir(parents=True, exist_ok=True)
        self._repo = git.Repo.init(self.repo_path, bare=bare)
        return self._repo

    def create_branch(self, branch_name: str) -> None:
        """Create a new branch from the current HEAD and check it out."""
        logger.info("git.create_branch", branch=branch_name)
        new_branch = self.repo.create_head(branch_name)
        new_branch.checkout()

    def checkout(self, branch_name: str) -> None:
        """Check out an existing branch."""
        logger.info("git.checkout", branch=branch_name)
        self.repo.git.checkout(branch_name)

    def add(self, paths: Optional[List[str]] = None) -> None:
        """Stage files.  Stages everything when *paths* is ``None``."""
        if paths:
            logger.info("git.add", paths=paths)
            self.repo.index.add(paths)
        else:
            logger.info("git.add_all")
            self.repo.git.add(A=True)

    def commit(self, message: str) -> str:
        """Create a commit and return its SHA."""
        logger.info("git.commit", message=message)
        commit = self.repo.index.commit(message)
        return commit.hexsha

    def push(self, branch_name: Optional[str] = None, remote: str = "origin") -> None:
        """Push to the remote."""
        branch = branch_name or self.repo.active_branch.name
        logger.info("git.push", branch=branch, remote=remote)
        self.repo.remote(name=remote).push(branch)

    def diff(self, staged: bool = False) -> str:
        """Return the diff as a string."""
        if staged:
            return self.repo.git.diff("--cached")
        return self.repo.git.diff()

    def status(self) -> str:
        """Return ``git status --short``."""
        return self.repo.git.status("--short")

    # ------------------------------------------------------------------
    # Private action handlers (called by execute)
    # ------------------------------------------------------------------

    def _action_init(self, **kwargs: Any) -> Dict[str, Any]:
        bare = kwargs.get("bare", False)
        self.init_repo(bare=bare)
        return {"success": True, "result": f"Initialised repo at {self.repo_path}"}

    def _action_create_branch(self, **kwargs: Any) -> Dict[str, Any]:
        branch_name: str = kwargs["branch_name"]
        self.create_branch(branch_name)
        return {"success": True, "result": f"Created and checked out branch {branch_name}"}

    def _action_checkout(self, **kwargs: Any) -> Dict[str, Any]:
        branch_name: str = kwargs["branch_name"]
        self.checkout(branch_name)
        return {"success": True, "result": f"Checked out branch {branch_name}"}

    def _action_add(self, **kwargs: Any) -> Dict[str, Any]:
        paths: Optional[List[str]] = kwargs.get("paths")
        self.add(paths)
        desc = ", ".join(paths) if paths else "all files"
        return {"success": True, "result": f"Staged {desc}"}

    def _action_commit(self, **kwargs: Any) -> Dict[str, Any]:
        message: str = kwargs["message"]
        sha = self.commit(message)
        return {"success": True, "result": sha}

    def _action_push(self, **kwargs: Any) -> Dict[str, Any]:
        branch_name: Optional[str] = kwargs.get("branch_name")
        remote: str = kwargs.get("remote", "origin")
        self.push(branch_name, remote)
        return {"success": True, "result": f"Pushed to {remote}/{branch_name or 'HEAD'}"}

    def _action_diff(self, **kwargs: Any) -> Dict[str, Any]:
        staged: bool = kwargs.get("staged", False)
        diff_text = self.diff(staged=staged)
        return {"success": True, "result": diff_text}

    def _action_status(self, **kwargs: Any) -> Dict[str, Any]:
        status_text = self.status()
        return {"success": True, "result": status_text}
