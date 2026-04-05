"""File operation tools: read, write, and search files."""

import glob
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from structlog import get_logger

from autofixer.tools.base import BaseTool

logger = get_logger()


class FileReadTool(BaseTool):
    """Reads the contents of a file and returns it as a string."""

    name: str = "file_read"
    description: str = "Read the full contents of a file at a given path."

    def execute(self, *, file_path: str, **kwargs: Any) -> Dict[str, Any]:
        logger.info("file_read.execute", file_path=file_path)
        try:
            path = Path(file_path)
            if not path.exists():
                return {"success": False, "result": None, "error": f"File not found: {file_path}"}
            if not path.is_file():
                return {"success": False, "result": None, "error": f"Not a file: {file_path}"}
            content = path.read_text(encoding="utf-8")
            return {"success": True, "result": content}
        except Exception as exc:
            logger.error("file_read.failed", file_path=file_path, error=str(exc))
            return {"success": False, "result": None, "error": str(exc)}


class FileWriteTool(BaseTool):
    """Writes content to a file, creating parent directories if needed."""

    name: str = "file_write"
    description: str = "Write content to a file. Creates the file and parent dirs if they do not exist."

    def execute(
        self, *, file_path: str, content: str, create_dirs: bool = True, **kwargs: Any
    ) -> Dict[str, Any]:
        logger.info("file_write.execute", file_path=file_path, content_length=len(content))
        try:
            path = Path(file_path)
            if create_dirs:
                path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return {"success": True, "result": f"Written {len(content)} bytes to {file_path}"}
        except Exception as exc:
            logger.error("file_write.failed", file_path=file_path, error=str(exc))
            return {"success": False, "result": None, "error": str(exc)}


class FileSearchTool(BaseTool):
    """Searches for a pattern in files using ripgrep with fallback to Python glob+regex."""

    name: str = "file_search"
    description: str = (
        "Search for a regex pattern across files. Uses ripgrep (rg) when available, "
        "falls back to Python glob + regex."
    )

    def execute(
        self,
        *,
        pattern: str,
        directory: str = ".",
        file_glob: Optional[str] = None,
        max_results: int = 50,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        logger.info(
            "file_search.execute",
            pattern=pattern,
            directory=directory,
            file_glob=file_glob,
        )
        try:
            results = self._search_ripgrep(pattern, directory, file_glob, max_results)
            if results is not None:
                return {"success": True, "result": results, "backend": "ripgrep"}
        except FileNotFoundError:
            logger.debug("file_search.ripgrep_not_found, falling back to python")

        # Fallback to Python-based search
        try:
            results = self._search_python(pattern, directory, file_glob, max_results)
            return {"success": True, "result": results, "backend": "python"}
        except Exception as exc:
            logger.error("file_search.failed", error=str(exc))
            return {"success": False, "result": None, "error": str(exc)}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _search_ripgrep(
        pattern: str,
        directory: str,
        file_glob: Optional[str],
        max_results: int,
    ) -> Optional[List[Dict[str, Any]]]:
        """Run ``rg`` and parse its JSON output.  Returns *None* if rg is not installed."""
        cmd: List[str] = [
            "rg",
            "--json",
            "--max-count",
            str(max_results),
            pattern,
            directory,
        ]
        if file_glob:
            cmd.extend(["--glob", file_glob])

        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if proc.returncode not in (0, 1):
            # returncode 1 means no matches – still valid
            if proc.returncode == 2:
                raise FileNotFoundError("ripgrep not found")
            return None

        matches: List[Dict[str, Any]] = []
        for line in proc.stdout.splitlines():
            if not line.strip():
                continue
            import json

            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("type") == "match":
                data = entry["data"]
                matches.append(
                    {
                        "file": data["path"]["text"],
                        "line_number": data["line_number"],
                        "line": data["lines"]["text"].rstrip("\n"),
                    }
                )
        return matches

    @staticmethod
    def _search_python(
        pattern: str,
        directory: str,
        file_glob: Optional[str],
        max_results: int,
    ) -> List[Dict[str, Any]]:
        """Pure-Python fallback using glob + regex."""
        regex = re.compile(pattern)
        search_glob = file_glob or "**/*"
        matches: List[Dict[str, Any]] = []

        for filepath in glob.iglob(os.path.join(directory, search_glob), recursive=True):
            if not os.path.isfile(filepath):
                continue
            try:
                with open(filepath, encoding="utf-8", errors="ignore") as fh:
                    for lineno, line in enumerate(fh, start=1):
                        if regex.search(line):
                            matches.append(
                                {
                                    "file": filepath,
                                    "line_number": lineno,
                                    "line": line.rstrip("\n"),
                                }
                            )
                            if len(matches) >= max_results:
                                return matches
            except (OSError, UnicodeDecodeError):
                continue
        return matches
