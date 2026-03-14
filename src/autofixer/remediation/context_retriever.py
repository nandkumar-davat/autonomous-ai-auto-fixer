from pathlib import Path
from typing import Optional
from structlog import get_logger

logger = get_logger()

class ContextRetriever:
    """Retrieves source code context for a given finding."""

    def __init__(self, workspace_dir: str = "workspace"):
        self.workspace_dir = Path(workspace_dir)

    def get_context(self, repo_name: str, file_path: str, line: Optional[int], context_lines: int = 50) -> str:
        """Retrieves text from a file, centered around the given line."""
        full_path = self.workspace_dir / repo_name / file_path
        
        if not full_path.exists():
            logger.error("File not found for context retrieval", path=full_path)
            return ""

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            if not lines:
                return ""

            if line is None or line < 1:
                # Return first 100 lines if no line number specified
                return "".join(lines[:100])

            # Line numbers are usually 1-indexed
            idx = line - 1
            start = max(0, idx - context_lines)
            end = min(len(lines), idx + context_lines + 1)
            
            return "".join(lines[start:end])
        except Exception as e:
            logger.error("Error reading file context", path=full_path, error=str(e))
            return ""
