import subprocess
from pathlib import Path
from typing import Tuple, Optional
from structlog import get_logger

logger = get_logger()

class LinterValidator:
    """Validates the syntax and style of code using language-specific linters."""

    def __init__(self, workspace_dir: str = "workspace"):
        self.workspace_dir = Path(workspace_dir)

    def _determine_language(self, file_path: str) -> Optional[str]:
        if file_path.endswith('.py'):
            return "python"
        elif file_path.endswith('.js') or file_path.endswith('.ts'):
            return "javascript"
        elif file_path.endswith('.java'):
            return "java"
        # Add more extensions as needed
        return None

    def validate_file(self, repo_name: str, file_path: str) -> Tuple[bool, str]:
        """Runs the appropriate linter on a given file.
        Returns a tuple: (Success_Boolean, Error_Message_If_Any)
        """
        full_path = self.workspace_dir / repo_name / file_path
        if not full_path.exists():
            msg = f"File not found for validation: {file_path}"
            logger.error(msg)
            return False, msg

        lang = self._determine_language(file_path)
        if not lang:
            logger.info("No configured linter for file extension, assuming valid", file=file_path)
            return True, ""

        logger.info("Running syntax validation", file=file_path, language=lang)
        
        try:
            if lang == "python":
                # Assuming flake8 is installed in the environment
                result = subprocess.run(
                    ["flake8", str(full_path)],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
            elif lang == "javascript":
                # Assuming eslint is configured in the repo
                result = subprocess.run(
                    ["npx", "eslint", str(full_path)],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=str(self.workspace_dir / repo_name)
                )
            else:
                return True, ""

            if result.returncode == 0:
                logger.info("Validation passed", file=file_path)
                return True, ""
            else:
                # Capture standard output/error, returning the first few lines as context
                error_msg = result.stdout.strip() or result.stderr.strip()
                logger.warning("Validation failed", file=file_path, errors=error_msg[:200])
                return False, error_msg

        except subprocess.TimeoutExpired:
            msg = "Linter timed out"
            logger.error(msg, file=file_path)
            return False, msg
        except Exception as e:
            msg = f"Linter execution failed: {str(e)}"
            logger.error(msg, file=file_path)
            return False, msg
