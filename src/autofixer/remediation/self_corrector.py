from typing import Optional, Tuple
from structlog import get_logger
from autofixer.models.finding import Finding
from autofixer.models.enums import AgentMode, RiskLevel
from autofixer.remediation.llm_client import LLMClient
from autofixer.remediation.context_retriever import ContextRetriever
from autofixer.validation.linter import LinterValidator
from autofixer.remediation.strategies.code_smell import CodeSmellStrategy
from autofixer.remediation.strategies.dependency import DependencyStrategy
from autofixer.remediation.strategies.security import SecurityStrategy

logger = get_logger()

class SelfCorrector:
    """Manages the retry loop for fixes that fail validation."""

    def __init__(self, llm_client: LLMClient, workspace_dir: str = "workspace", max_retries: int = 3):
        self.llm_client = llm_client
        self.max_retries = max_retries
        self.linter = LinterValidator(workspace_dir=workspace_dir)
        self.context_retriever = ContextRetriever(workspace_dir=workspace_dir)

    def generate_and_validate(
            self, finding: Finding, initial_context: str, repo_name: str
    ) -> Tuple[Optional[str], bool, int]:
        """
        Attempts to generate a fix using the appropriate strategy.
        If it fails the linter, it retries up to 'max_retries' times by feeding the error back to the LLM.
        Returns: (best_fix_content, is_valid_boolean, number_of_retries_used)
        """
        logger.info("Starting self-correction loop", finding_id=finding.id, max_retries=self.max_retries)
        
        # 1. Select the initial strategy based on finding type
        strategy = self._select_strategy(finding)
        
        # 2. Generate the initial fix
        current_context = initial_context
        proposed_fix = strategy.fix(finding, initial_context)
        
        if not proposed_fix:
            logger.warning("Strategy failed to generate an initial fix", finding=finding.id)
            return None, False, 0
            
        retries = 0
        valid = False
        error_msg = ""
        
        # We need to temporarily write the fix to the workspace to run the Linter
        import tempfile, os
        from pathlib import Path
            
        repo_dir = Path(self.linter.workspace_dir) / repo_name
        full_path = repo_dir / finding.file_path
        
        # Backup the original content
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                original_file_content = f.read()
        except FileNotFoundError:
            logger.error("Original file missing from workspace", path=str(full_path))
            return None, False, 0

        while retries <= self.max_retries:
            
            # Apply the proposed fix to the actual file
            self._write_to_file(full_path, proposed_fix, initial_context, original_file_content)
            
            # 3. Validate the syntax
            valid, error_msg = self.linter.validate_file(repo_name, finding.file_path)
            
            if valid:
                logger.info("Validation passed!", finding=finding.id, retries=retries)
                break
                
            retries += 1
            if retries <= self.max_retries:
                logger.info("Validation failed, retrying with error context", finding=finding.id, retry=retries)
                # 4. Generate a new prompt feeding back the error
                retry_prompt = (
                    f"Your previous fix caused the following syntax/validation error:\n"
                    f"{error_msg}\n\n"
                    f"Please correct the code and provide a valid replacement."
                )
                
                # The LLM Client handles the retry context
                proposed_fix = self.llm_client.generate_fix(initial_context, retry_prompt, finding.issue_type)
                
                if not proposed_fix:
                    logger.warning("LLM failed to generate a retry fix", finding=finding.id)
                    break
            else:
                logger.error("Max retries reached. Fix is invalid.", finding=finding.id)

        # Restore original file state for safety since GitOps will handle the real commit
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(original_file_content)

        return proposed_fix if valid else None, valid, retries

    def _select_strategy(self, finding: Finding):
        """Returns the appropriate strategy instance."""
        from autofixer.models.enums import IssueType
        
        if finding.issue_type == IssueType.CODE_SMELL:
            return CodeSmellStrategy(self.llm_client)
        elif finding.issue_type == IssueType.VULNERABILITY and finding.file_path.endswith('.json'):
            return DependencyStrategy(self.llm_client)
        else:
            return SecurityStrategy(self.llm_client)
            
    def _write_to_file(self, file_path: Path, proposed_code: str, old_context: str, full_original: str):
        """Replaces the old context with the proposed code in the file."""
        # Simple string replacement for the demo. Real implementations use AST or diff applying.
        new_content = full_original.replace(old_context, proposed_code)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
