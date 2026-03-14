import re
from typing import Optional
from structlog import get_logger
from autofixer.models.finding import Finding
from autofixer.remediation.llm_client import LLMClient

logger = get_logger()

class CodeSmellStrategy:
    """Strategy for fixing code smells like unused imports and naming conventions."""

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def fix(self, finding: Finding, context: str) -> Optional[str]:
        """Applies a fix for a code smell based on its context."""
        logger.info("Applying CodeSmellStrategy", finding_id=finding.id, rule_id=finding.rule_id)
        
        # Fast paths for simple, highly predictable Python code smells
        if "unused import" in finding.message.lower():
            return self._remove_unused_import(context, finding.message)
            
        # Fallback to LLM for more complex refactorings (e.g., naming conventions)
        logger.info("Falling back to LLM for code smell fix")
        return self.llm_client.generate_fix(context, finding.message, "CODE_SMELL")

    def _remove_unused_import(self, context: str, message: str) -> Optional[str]:
        """Heurustic approach to remove unused imports."""
        # This is a very simplistic heuristic for demo purposes.
        # A real implementation would parse the AST or rely on the LLM.
        
        # Try to extract the module/name from the message
        # e.g., "Unused import 'sys'."
        match = re.search(r"['\"](.+?)['\"]", message)
        if match:
            target_import = match.group(1)
            lines = context.split("\n")
            fixed_lines = []
            for line in lines:
                if target_import in line and ("import " in line or "from " in line):
                    # Skip this line (remove the import)
                    logger.debug("Removed unused import line", line=line)
                    continue
                fixed_lines.append(line)
            return "\n".join(fixed_lines)
            
        return None
