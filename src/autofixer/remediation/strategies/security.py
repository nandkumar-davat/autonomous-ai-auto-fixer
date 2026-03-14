import re
from typing import Optional
from structlog import get_logger
from autofixer.models.finding import Finding
from autofixer.remediation.llm_client import LLMClient

logger = get_logger()

class SecurityStrategy:
    """Strategy for fixing security vulnerabilities and hotspots."""

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def fix(self, finding: Finding, context: str) -> Optional[str]:
        """Applies a security patch or fix based on finding details."""
        logger.info("Applying SecurityStrategy", finding_id=finding.id, rule_id=finding.rule_id)
        
        # 1. Dockerfile / Container Fixes (Common in Trivy)
        if finding.file_path.lower().endswith("dockerfile"):
            new_context = self._attempt_dockerfile_fix(finding, context)
            if new_context:
                return new_context

        # 2. Fallback to LLM for most security patches
        # Security fixes require high precision and context awareness
        logger.info("Delegating security fix to LLM", risk="HIGH")
        return self.llm_client.generate_fix(context, finding.message, "VULNERABILITY")

    def _attempt_dockerfile_fix(self, finding: Finding, context: str) -> Optional[str]:
        """Tries to apply common Dockerfile security fixes (e.g., base image update)."""
        # If Trivy reports a vulnerability in a base image, we might look for 'FROM'
        if "base image" in finding.message.lower() or "installed version" in finding.message.lower():
            # Extract fixed version if suggested
            match = re.search(r"fixed in ([\w\.-]+)", finding.message, re.IGNORECASE)
            if match:
                fixed_ver = match.group(1)
                lines = context.split("\n")
                fixed_lines = []
                updated = False
                
                for line in lines:
                    if line.strip().startswith("FROM "):
                        # Try to replace the tag
                        # Example: FROM python:3.9-slim -> FROM python:3.10-slim
                        if ":" in line:
                            new_line = re.sub(r":[\w\.-]+", f":{fixed_ver}", line)
                            if new_line != line:
                                logger.info("Updated Dockerfile base image tag", old=line, new=new_line)
                                fixed_lines.append(new_line)
                                updated = True
                                continue
                    fixed_lines.append(line)
                
                if updated:
                    return "\n".join(fixed_lines)
                    
        return None
