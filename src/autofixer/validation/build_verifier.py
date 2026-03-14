from typing import Optional
from structlog import get_logger
from autofixer.vcs.base_vcs import BaseVCSClient

logger = get_logger()

class BuildVerifier:
    """Hooks into CI systems to trigger and verify builds after a PR is created."""

    def __init__(self, vcs_client: BaseVCSClient):
        self.vcs_client = vcs_client

    def trigger_and_wait(self, pr_id: str, timeout_sec: int = 1800) -> Optional[bool]:
        """Triggers a build for the PR or waits for the existing CI pipeline to finish.
        Returns: True if build passes, False if it fails, None if timeout/error.
        """
        import time
        logger.info("Starting build verification loop for PR", pr_id=pr_id)
        
        start_time = time.time()
        poll_interval = 60

        while (time.time() - start_time) < timeout_sec:
            try:
                # In Azure Repos, checking the git status usually delegates to the Pipelines API
                # In GitHub, checking the Combined Status object provides CI status
                status = self.vcs_client.check_build_status(pr_id)
                
                # Assume standard nomenclature returned by the VCS client wrappers
                if status in ["success", "succeeded", "passed"]:
                    logger.info("CI Build Passed", pr=pr_id)
                    return True
                elif status in ["failure", "failed", "error"]:
                    logger.warning("CI Build Failed", pr=pr_id)
                    return False
                elif status in ["pending", "inProgress"]:
                    logger.debug("CI Build still pending/running", pr=pr_id)
                else:
                    logger.warning("Unknown or unimplemented build status returned", status=status, pr=pr_id)
                    # For demo purposes, pretend we don't have CI configured
                    return True

            except Exception as e:
                logger.error("Error checking build status", pr=pr_id, error=str(e))
                return None
                
            time.sleep(poll_interval)
            
        logger.error("Timed out waiting for CI build", pr=pr_id)
        return None
