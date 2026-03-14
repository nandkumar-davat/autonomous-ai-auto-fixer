import re
import json
from typing import Optional
from structlog import get_logger
from autofixer.models.finding import Finding
from autofixer.remediation.llm_client import LLMClient

logger = get_logger()

class DependencyStrategy:
    """Strategy for fixing dependency vulnerabilities (version bumps)."""

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def fix(self, finding: Finding, context: str) -> Optional[str]:
        """Applies a fix for a vulnerable dependency."""
        logger.info("Applying DependencyStrategy", finding_id=finding.id, rule_id=finding.rule_id)
        
        # 1. Very basic Node.js generic fix heuristic
        if finding.file_path.endswith("package.json"):
            new_context = self._attempt_package_json_bump(finding, context)
            if new_context:
                return new_context
                
        # 2. Python generic fix heuristic
        elif finding.file_path.endswith("requirements.txt") or finding.file_path.endswith("pyproject.toml"):
            pass 
            # Implement Python-specific logic here
            
        # 3. Fallback to LLM if manual parsing heuristics fail
        logger.info("Falling back to LLM for dependency bump", file=finding.file_path)
        prompt_msg = f"{finding.message}. Upgrade the affected package safely without breaking other dependencies."
        return self.llm_client.generate_fix(context, prompt_msg, "VULNERABILITY")

    def _attempt_package_json_bump(self, finding: Finding, context: str) -> Optional[str]:
        """Tries to update a package.json dependency to a fixed version."""
        logger.debug("Attempting fast-path package.json bump")
        # Extract potential library and target version from finding message
        # Many Mend / Trivy findings say "Requires version >= 1.2.3" or "Fixed in: 1.2.3"
        try:
            # Look for the library name from raw_data if we have it
            library_name = finding.raw_data.get("name") or finding.raw_data.get("Library")
            
            if not library_name:
                return None
                
            match = re.search(r"(?:Fixed in|Upgrade to|>=)[\s:]*([0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?)*", finding.message, re.IGNORECASE)
            if match:
                target_version = match.group(1)
                
                # We could try loading the package.json and writing it out
                pkg = json.loads(context)
                
                updated = False
                for dep_key in ["dependencies", "devDependencies", "peerDependencies"]:
                    if dep_key in pkg and library_name in pkg[dep_key]:
                        old_ver = pkg[dep_key][library_name]
                        
                        # Preserve prefixes like ^ or ~
                        prefix = ""
                        if old_ver.startswith("^") or old_ver.startswith("~"):
                            prefix = old_ver[0]
                            
                        pkg[dep_key][library_name] = f"{prefix}{target_version}"
                        logger.info("Fast package.json bump applied", package=library_name, old=old_ver, new=f"{prefix}{target_version}")
                        updated = True
                
                if updated:
                    # Write it back formatting nicely
                    return json.dumps(pkg, indent=2) + "\n"
                    
        except json.JSONDecodeError:
            logger.warning("Failed to parse package.json for fast path")
        except Exception as e:
            logger.warning("Fast path dependency bump failed", error=str(e))
            
        return None
