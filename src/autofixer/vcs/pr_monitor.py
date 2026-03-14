from typing import List, Callable, Optional
import time
from structlog import get_logger
from autofixer.vcs.base_vcs import BaseVCSClient

logger = get_logger()

class PRMonitor:
    """Human-in-the-loop monitor for PR comments."""

    def __init__(self, vcs_client: BaseVCSClient, polling_interval_sec: int = 60):
        self.vcs_client = vcs_client
        self.polling_interval_sec = polling_interval_sec
        self._processed_comment_ids = set()

    def get_new_comments(self, pr_id: str) -> List[dict]:
        """Fetches newly added comments for a given PR."""
        logger.info("Polling PR comments", pr_id=pr_id)
        all_comments = self.vcs_client.get_pr_comments(pr_id)
        
        new_comments = []
        for c in all_comments:
            # We construct a mock unique ID using author + content for now.
            # In a real scenario, the VCS client should return the comment ID.
            c_id = f"{c.get('author')}_{c.get('content')}"
            if c_id not in self._processed_comment_ids:
                new_comments.append(c)
                self._processed_comment_ids.add(c_id)

        if new_comments:
            logger.info("Found new comments", count=len(new_comments), pr_id=pr_id)
            
        return new_comments

    def poll_continuously(self, pr_id: str, callback: Callable[[dict], None]) -> None:
        """Polls for comments continuously and calls the callback on new ones."""
        logger.info("Starting continuous PR monitoring", pr_id=pr_id)
        try:
            while True:
                new_comments = self.get_new_comments(pr_id)
                for comment in new_comments:
                    callback(comment)
                time.sleep(self.polling_interval_sec)
        except KeyboardInterrupt:
            logger.info("Stopping PR monitor (KeyboardInterrupt)")
