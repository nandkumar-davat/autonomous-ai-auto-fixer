"""Code-aware search tool using ripgrep with language-aware patterns."""

import subprocess
from typing import Any, Dict, List, Optional

from structlog import get_logger

from autofixer.tools.base import BaseTool

logger = get_logger()

# Language-aware regex patterns for common constructs.
# Each pattern uses a named group ``<name>`` for the identifier.
_FUNCTION_PATTERNS: Dict[str, str] = {
    "python": r"^\s*(?:async\s+)?def\s+{name}\s*\(",
    "javascript": r"(?:function\s+{name}\s*\(|(?:const|let|var)\s+{name}\s*=\s*(?:async\s*)?\()",
    "typescript": r"(?:function\s+{name}\s*[\(<]|(?:const|let|var)\s+{name}\s*=\s*(?:async\s*)?\()",
    "java": r"(?:public|private|protected|static|\s)+\S+\s+{name}\s*\(",
    "go": r"func\s+(?:\(.*?\)\s+)?{name}\s*\(",
}

_CLASS_PATTERNS: Dict[str, str] = {
    "python": r"^\s*class\s+{name}\s*[\(:]",
    "javascript": r"class\s+{name}\s*[\{{]",
    "typescript": r"(?:export\s+)?(?:abstract\s+)?class\s+{name}\s*[\{<]",
    "java": r"(?:public|private|protected|abstract|final|\s)+class\s+{name}\s*[\{<]",
    "go": r"type\s+{name}\s+struct\s*\{{",
}

_IMPORT_PATTERNS: Dict[str, str] = {
    "python": r"(?:from\s+{module}\s+import|import\s+{module})",
    "javascript": r"(?:import\s+.*from\s+['\"].*{module}|require\s*\(\s*['\"].*{module})",
    "typescript": r"import\s+.*from\s+['\"].*{module}",
    "java": r"import\s+.*{module}",
    "go": r"\".*{module}\"",
}

# File-glob per language for ripgrep ``--glob``
_LANG_GLOBS: Dict[str, str] = {
    "python": "*.py",
    "javascript": "*.{js,jsx,mjs,cjs}",
    "typescript": "*.{ts,tsx}",
    "java": "*.java",
    "go": "*.go",
}


class CodeSearchTool(BaseTool):
    """Searches for code constructs (functions, classes, imports) using ripgrep.

    Falls back to a simple ``grep -rn`` when ripgrep is unavailable.
    """

    name: str = "code_search"
    description: str = (
        "Search for functions, classes, imports, or arbitrary patterns "
        "across a codebase using language-aware regex via ripgrep."
    )

    def __init__(self, *, default_directory: str = ".") -> None:
        self.default_directory = default_directory

    # ------------------------------------------------------------------
    # BaseTool interface
    # ------------------------------------------------------------------

    def execute(
        self,
        *,
        action: str = "pattern",
        name: Optional[str] = None,
        module: Optional[str] = None,
        pattern: Optional[str] = None,
        file_glob: Optional[str] = None,
        language: Optional[str] = None,
        directory: Optional[str] = None,
        max_results: int = 50,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Dispatch to the appropriate search method.

        ``action`` may be one of ``function``, ``class``, ``import``, ``pattern``.
        """
        target_dir = directory or self.default_directory

        try:
            if action == "function":
                if not name:
                    return {"success": False, "result": None, "error": "'name' is required for function search"}
                results = self.search_function(name, target_dir, language, max_results)
            elif action == "class":
                if not name:
                    return {"success": False, "result": None, "error": "'name' is required for class search"}
                results = self.search_class(name, target_dir, language, max_results)
            elif action == "import":
                if not module:
                    return {"success": False, "result": None, "error": "'module' is required for import search"}
                results = self.search_imports(module, target_dir, language, max_results)
            else:
                if not pattern:
                    return {"success": False, "result": None, "error": "'pattern' is required for pattern search"}
                results = self.search_pattern(pattern, target_dir, file_glob, max_results)
            return {"success": True, "result": results}
        except Exception as exc:
            logger.error("code_search.failed", action=action, error=str(exc))
            return {"success": False, "result": None, "error": str(exc)}

    # ------------------------------------------------------------------
    # Public convenience methods
    # ------------------------------------------------------------------

    def search_function(
        self,
        name: str,
        directory: Optional[str] = None,
        language: Optional[str] = None,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """Search for a function definition by *name*."""
        logger.info("code_search.search_function", name=name, language=language)
        return self._search_construct(
            _FUNCTION_PATTERNS, "name", name, directory, language, max_results
        )

    def search_class(
        self,
        name: str,
        directory: Optional[str] = None,
        language: Optional[str] = None,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """Search for a class definition by *name*."""
        logger.info("code_search.search_class", name=name, language=language)
        return self._search_construct(
            _CLASS_PATTERNS, "name", name, directory, language, max_results
        )

    def search_imports(
        self,
        module: str,
        directory: Optional[str] = None,
        language: Optional[str] = None,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """Search for import statements referencing *module*."""
        logger.info("code_search.search_imports", module=module, language=language)
        return self._search_construct(
            _IMPORT_PATTERNS, "module", module, directory, language, max_results
        )

    def search_pattern(
        self,
        pattern: str,
        directory: Optional[str] = None,
        file_glob: Optional[str] = None,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """Search for an arbitrary regex *pattern*."""
        logger.info("code_search.search_pattern", pattern=pattern, file_glob=file_glob)
        target_dir = directory or self.default_directory
        return self._run_rg(pattern, target_dir, file_glob, max_results)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _search_construct(
        self,
        pattern_map: Dict[str, str],
        placeholder: str,
        value: str,
        directory: Optional[str],
        language: Optional[str],
        max_results: int,
    ) -> List[Dict[str, Any]]:
        target_dir = directory or self.default_directory
        all_results: List[Dict[str, Any]] = []

        languages = [language] if language else list(pattern_map.keys())
        for lang in languages:
            tmpl = pattern_map.get(lang)
            if tmpl is None:
                continue
            regex = tmpl.replace(f"{{{placeholder}}}", value)
            glob_pat = _LANG_GLOBS.get(lang)
            results = self._run_rg(regex, target_dir, glob_pat, max_results - len(all_results))
            all_results.extend(results)
            if len(all_results) >= max_results:
                break
        return all_results[:max_results]

    @staticmethod
    def _run_rg(
        pattern: str,
        directory: str,
        file_glob: Optional[str],
        max_results: int,
    ) -> List[Dict[str, Any]]:
        """Execute ripgrep and return parsed match dicts."""
        cmd: List[str] = [
            "rg",
            "--line-number",
            "--no-heading",
            "--max-count",
            str(max_results),
            pattern,
            directory,
        ]
        if file_glob:
            cmd.extend(["--glob", file_glob])

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except FileNotFoundError:
            logger.warning("code_search.ripgrep_not_found, falling back to grep")
            return CodeSearchTool._run_grep_fallback(pattern, directory, file_glob, max_results)

        matches: List[Dict[str, Any]] = []
        for line in proc.stdout.splitlines():
            # rg output format: file:lineno:text
            parts = line.split(":", maxsplit=2)
            if len(parts) >= 3:
                matches.append(
                    {
                        "file": parts[0],
                        "line_number": int(parts[1]),
                        "line": parts[2],
                    }
                )
            if len(matches) >= max_results:
                break
        return matches

    @staticmethod
    def _run_grep_fallback(
        pattern: str,
        directory: str,
        file_glob: Optional[str],
        max_results: int,
    ) -> List[Dict[str, Any]]:
        """Fallback to ``grep -rn`` when ripgrep is not installed."""
        cmd: List[str] = ["grep", "-rn", "-E", pattern, directory]
        if file_glob:
            cmd.extend(["--include", file_glob])

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except Exception as exc:
            logger.error("code_search.grep_fallback_failed", error=str(exc))
            return []

        matches: List[Dict[str, Any]] = []
        for line in proc.stdout.splitlines():
            parts = line.split(":", maxsplit=2)
            if len(parts) >= 3:
                matches.append(
                    {
                        "file": parts[0],
                        "line_number": int(parts[1]),
                        "line": parts[2],
                    }
                )
            if len(matches) >= max_results:
                break
        return matches
