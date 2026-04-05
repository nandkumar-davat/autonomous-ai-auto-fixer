"""Fixer agent for the autofixer multi-agent system.

The ``FixerAgent`` is the "hands" of the pipeline.  It:

1. Creates a feature branch from *base_branch*.
2. Iterates over every ``ConsolidatedFix`` in priority order.
3. Reads the target file, applies the fix (deterministic or LLM-assisted).
4. Runs the linter; on failure retries with LLM feedback up to *max_retries*.
5. Records each outcome as a ``FileFixResult``.
6. Commits, pushes, and (optionally) opens a pull request.
7. Returns a ``FixResult`` summary.
"""

from __future__ import annotations

import difflib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from structlog import get_logger

from autofixer.agents.base import BaseAgent
from autofixer.agents.messages import (
    ConsolidatedFix,
    ConsolidatedPlan,
    FileFixResult,
    FixResult,
    FixStrategy,
    ProposedFix,
)
from autofixer.agents.prompts.loader import load_prompt
from autofixer.llm.base import BaseLLMProvider
from autofixer.models.enums import ToolSource
from autofixer.remediation.context_retriever import ContextRetriever
from autofixer.validation.linter import LinterValidator
from autofixer.vcs.git_ops import GitOperations


class FixerAgent(BaseAgent):
    """Applies fixes to source files and manages the git workflow.

    Parameters
    ----------
    llm_provider:
        Provider used for LLM-assisted fix generation.
    config:
        Orchestrator configuration.  Recognised keys:

        * ``max_retries`` (int) – lint-retry budget per file (default 3).
        * ``dry_run`` (bool) – skip git operations when ``True``.
        * ``github_token`` (str) – forwarded to ``GitOperations``.
    repo_path:
        Absolute or workspace-relative path to the cloned repository.
    base_branch:
        Branch to create the autofix branch from (default ``main``).
    """

    def __init__(
        self,
        llm_provider: BaseLLMProvider,
        config: Any = None,
        *,
        repo_path: str = "workspace/repo",
        base_branch: str = "main",
    ) -> None:
        super().__init__(
            name="fixer",
            llm_provider=llm_provider,
            config=config,
        )
        self.repo_path = Path(repo_path)
        self.base_branch = base_branch
        self.max_retries: int = int(
            (self.config or {}).get("max_retries", 3)
            if isinstance(self.config, dict)
            else 3
        )
        self.dry_run: bool = bool(
            (self.config or {}).get("dry_run", False)
            if isinstance(self.config, dict)
            else False
        )

        # Workspace dir is the parent of the repo checkout
        workspace_dir = str(self.repo_path.parent)
        self.repo_name = self.repo_path.name
        self.linter = LinterValidator(workspace_dir=workspace_dir)
        self.context_retriever = ContextRetriever(
            workspace_dir=workspace_dir
        )

        github_token: Optional[str] = (
            (self.config or {}).get("github_token")
            if isinstance(self.config, dict)
            else None
        )
        self.git_ops = GitOperations(
            workspace_dir=workspace_dir,
            github_token=github_token,
        )

        self.system_prompt = self._load_system_prompt("fixer")
        
        # Load scanner-specific prompts
        self.scanner_prompts = {
            ToolSource.MEND: load_prompt("mend_security_fixer"),
            ToolSource.TRIVY: load_prompt("trivy_security_fixer"), 
            ToolSource.SONARQUBE: load_prompt("sonarqube_issue_fixer"),
        }

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    def apply_fixes(self, plan: ConsolidatedPlan) -> FixResult:
        """Execute every fix in *plan* and return a ``FixResult``.

        Parameters
        ----------
        plan:
            The ``ConsolidatedPlan`` produced by the Team-Lead agent.

        Returns
        -------
        FixResult
            Detailed per-file outcomes plus the overall summary.
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        branch_name = f"autofix/{timestamp}"

        self.logger.info(
            "Starting fix application",
            branch=branch_name,
            total_files=plan.files_affected,
            total_fixes=plan.total_fixes,
            dry_run=self.dry_run,
        )

        # 1. Branch setup --------------------------------------------------
        repo = None
        if not self.dry_run:
            try:
                repo = self.git_ops.clone_repository(
                    repo_url="",  # already cloned – pull latest
                    repo_name=self.repo_name,
                )
            except Exception:
                # Repo already exists locally – open it
                import git as gitmodule

                repo = gitmodule.Repo(str(self.repo_path))

            try:
                self.git_ops.create_branch(repo, branch_name)
            except Exception as exc:
                self.logger.warning(
                    "Branch creation issue (may already exist)",
                    error=str(exc),
                )

        # 2. Apply each ConsolidatedFix ------------------------------------
        file_results: List[FileFixResult] = []

        for consolidated_fix in plan.consolidated_fixes:
            result = self._apply_file_fixes(consolidated_fix)
            file_results.append(result)

        # 3. Commit & push -------------------------------------------------
        applied = [r for r in file_results if r.success]
        commit_sha: Optional[str] = None

        if applied and repo and not self.dry_run:
            try:
                commit_msg = (
                    f"autofix: apply {len(applied)} fix(es) across "
                    f"{len(applied)} file(s)\n\n"
                    "Generated by autonomous-ai-auto-fixer."
                )
                self.git_ops.commit_and_push(
                    repo, branch_name, commit_msg
                )
                commit_sha = str(repo.head.commit)
            except Exception as exc:
                self.logger.error(
                    "Failed to commit/push",
                    error=str(exc),
                    exc_info=True,
                )

        summary = (
            f"Fixer: attempted {plan.total_fixes} fixes, "
            f"applied {len(applied)}/{len(file_results)} file-level "
            f"results successfully on branch {branch_name}."
        )
        self.logger.info("Fix application complete", summary=summary)

        return FixResult(
            branch_name=branch_name,
            total_fixes_attempted=plan.total_fixes,
            total_fixes_applied=sum(
                len(r.finding_ids) for r in applied
            ),
            file_results=file_results,
            pr_url=None,  # PR creation delegated to CI / orchestrator
            commit_sha=commit_sha,
            summary=summary,
        )

    # -----------------------------------------------------------------
    # Per-file fix application
    # -----------------------------------------------------------------

    def _apply_file_fixes(
        self, consolidated: ConsolidatedFix
    ) -> FileFixResult:
        """Apply all fixes targeting a single file.

        Returns a ``FileFixResult`` capturing success/failure,
        the unified diff, and lint status.
        """
        file_path = consolidated.file_path
        finding_ids = [f.finding_id for f in consolidated.fixes]

        self.logger.info(
            "Applying fixes to file",
            file=file_path,
            fix_count=len(consolidated.fixes),
        )

        # Read current content
        full_path = self.repo_path / file_path
        try:
            original_content = full_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            msg = f"File not found: {file_path}"
            self.logger.error(msg)
            return FileFixResult(
                file_path=file_path,
                success=False,
                finding_ids=finding_ids,
                error=msg,
            )
        except Exception as exc:
            msg = f"Error reading {file_path}: {exc}"
            self.logger.error(msg)
            return FileFixResult(
                file_path=file_path,
                success=False,
                finding_ids=finding_ids,
                error=msg,
            )

        # Apply fixes sequentially (priority-sorted by Team-Lead)
        current_content = original_content
        for fix in consolidated.fixes:
            try:
                patched = self._apply_single_fix(
                    fix, file_path, current_content
                )
                if patched is not None:
                    current_content = patched
            except Exception as exc:
                self.logger.warning(
                    "Fix application error – skipping",
                    finding=fix.finding_id,
                    error=str(exc),
                )

        # Nothing changed?
        if current_content == original_content:
            return FileFixResult(
                file_path=file_path,
                success=False,
                finding_ids=finding_ids,
                error="No changes produced by any fix",
            )

        # Lint loop with retries
        lint_passed, retries = self._lint_loop(
            file_path, original_content, current_content
        )

        # Compute diff
        diff = self._unified_diff(
            original_content, current_content, file_path
        )

        # Persist the final content
        if not self.dry_run:
            try:
                full_path.write_text(current_content, encoding="utf-8")
            except Exception as exc:
                return FileFixResult(
                    file_path=file_path,
                    success=False,
                    finding_ids=finding_ids,
                    error=f"Failed to write file: {exc}",
                )

        return FileFixResult(
            file_path=file_path,
            success=True,
            finding_ids=finding_ids,
            diff=diff,
            lint_passed=lint_passed,
            retries=retries,
        )

    # -----------------------------------------------------------------
    # Single fix dispatch
    # -----------------------------------------------------------------

    def _apply_single_fix(
        self,
        fix: ProposedFix,
        file_path: str,
        content: str,
    ) -> Optional[str]:
        """Dispatch a single ``ProposedFix`` to the right handler."""
        strategy = fix.strategy

        if strategy == FixStrategy.VERSION_BUMP:
            return self._apply_version_bump(fix, content)
        if strategy == FixStrategy.DOCKERFILE_UPDATE:
            return self._apply_dockerfile_update(fix, content)
        if strategy == FixStrategy.CONFIG_CHANGE:
            return self._apply_config_change(fix, content)
        if strategy == FixStrategy.CODE_PATCH:
            return self._apply_code_patch(fix, file_path, content)
        if strategy == FixStrategy.LLM_ASSISTED:
            return self._apply_llm_assisted(fix, file_path, content)

        self.logger.warning(
            "Unknown strategy – skipping",
            strategy=strategy,
            finding=fix.finding_id,
        )
        return None

    # -----------------------------------------------------------------
    # Strategy-specific handlers
    # -----------------------------------------------------------------

    def _apply_version_bump(
        self, fix: ProposedFix, content: str
    ) -> Optional[str]:
        """Apply a dependency version bump using ``suggested_change``."""
        if not fix.suggested_change:
            return self._apply_llm_assisted_raw(
                fix, content, "version bump"
            )

        # Try to extract target version from suggested_change
        import re

        match = re.search(
            r"(\d+\.\d+\.\d+(-[\w.]+)?)", fix.suggested_change
        )
        if not match:
            return self._apply_llm_assisted_raw(
                fix, content, "version bump"
            )

        target_ver = match.group(1)

        # Heuristic: look for the old version near the finding
        # and replace with target – JSON-safe
        try:
            import json

            pkg = json.loads(content)
            raw = fix.metadata or {}
            pkg_name = raw.get("rule_id", "")
            # Walk dependency sections
            updated = False
            for section in (
                "dependencies",
                "devDependencies",
                "peerDependencies",
            ):
                if section in pkg and isinstance(pkg[section], dict):
                    for name in pkg[section]:
                        if pkg_name and pkg_name.lower() in name.lower():
                            old = pkg[section][name]
                            prefix = ""
                            if old and old[0] in ("^", "~"):
                                prefix = old[0]
                            pkg[section][name] = f"{prefix}{target_ver}"
                            updated = True
            if updated:
                return json.dumps(pkg, indent=2) + "\n"
        except (json.JSONDecodeError, Exception):
            pass

        # Fallback: simple string replacement
        if target_ver in content:
            return content  # already at target
        return self._apply_llm_assisted_raw(
            fix, content, "version bump"
        )

    def _apply_dockerfile_update(
        self, fix: ProposedFix, content: str
    ) -> Optional[str]:
        """Apply a Dockerfile base-image or instruction update."""
        if fix.suggested_change:
            import re

            match = re.search(
                r"([\w./-]+:\S+)", fix.suggested_change
            )
            if match:
                new_image = match.group(1)
                lines = content.splitlines(keepends=True)
                updated_lines: List[str] = []
                changed = False
                for line in lines:
                    if line.strip().startswith("FROM ") and not changed:
                        updated_lines.append(f"FROM {new_image}\n")
                        changed = True
                    else:
                        updated_lines.append(line)
                if changed:
                    return "".join(updated_lines)

        return self._apply_llm_assisted_raw(
            fix, content, "Dockerfile update"
        )

    def _apply_config_change(
        self, fix: ProposedFix, content: str
    ) -> Optional[str]:
        """Apply a configuration file change via LLM."""
        return self._apply_llm_assisted_raw(
            fix, content, "config change"
        )

    def _apply_code_patch(
        self,
        fix: ProposedFix,
        file_path: str,
        content: str,
    ) -> Optional[str]:
        """Apply a direct code patch (e.g. remove unused import)."""
        if fix.suggested_change:
            # If the auditor already has the replacement, use it
            return fix.suggested_change

        return self._apply_llm_assisted_raw(
            fix, content, "code patch"
        )

    def _apply_llm_assisted(
        self,
        fix: ProposedFix,
        file_path: str,
        content: str,
    ) -> Optional[str]:
        """Use the LLM to generate a fix from scratch using scanner-specific prompts."""
        # Build focused context around the affected line
        line = fix.metadata.get("line")
        if line is not None:
            context = self.context_retriever.get_context(
                self.repo_name, file_path, int(line), context_lines=30
            )
        else:
            # Use first 120 lines as context
            context = "\n".join(content.splitlines()[:120])

        # Use scanner-specific prompt if available
        source_tool = fix.metadata.get("source_tool")
        system_prompt = self._get_scanner_prompt(source_tool)
        
        # Build scanner-aware user prompt
        user_prompt = self._build_scanner_aware_prompt(
            fix, file_path, context, source_tool
        )

        raw = self._call_llm(
            system_prompt,
            user_prompt,
            temperature=0.0,
            max_tokens=4096,
        )
        if raw is None:
            return None

        fixed = self._strip_code_fences(raw)
        if not fixed.strip():
            return None

        # Replace the context region in the full content
        if context in content:
            return content.replace(context, fixed, 1)

        # If context doesn't match exactly, return full LLM output
        # as the new file content (best-effort)
        return fixed

    def _apply_llm_assisted_raw(
        self,
        fix: ProposedFix,
        content: str,
        fix_type: str,
    ) -> Optional[str]:
        """LLM fallback that operates on the entire file content with scanner-specific prompts."""
        source_tool = fix.metadata.get("source_tool")
        system_prompt = self._get_scanner_prompt(source_tool)
        
        user_prompt = (
            f"Apply a {fix_type} to the following file following the systematic approach.\n\n"
            f"FINDING: {fix.description}\n"
            f"SCANNER: {source_tool or 'Unknown'}\n"
            f"SUGGESTED CHANGE: {fix.suggested_change or 'N/A'}\n\n"
            f"FULL FILE:\n```\n{content[:6000]}\n```\n\n"
            "Return ONLY the complete corrected file content. Follow the scanner-specific methodology."
        )

        raw = self._call_llm(
            system_prompt,
            user_prompt,
            temperature=0.0,
            max_tokens=8192,
        )
        if raw is None:
            return None

        fixed = self._strip_code_fences(raw)
        return fixed if fixed.strip() else None

    # -----------------------------------------------------------------
    # Lint loop
    # -----------------------------------------------------------------

    def _lint_loop(
        self,
        file_path: str,
        original_content: str,
        current_content: str,
    ) -> tuple[bool, int]:
        """Write content, lint, and retry with LLM feedback.

        Returns ``(lint_passed, retries_used)``.
        """
        full_path = self.repo_path / file_path

        for attempt in range(self.max_retries + 1):
            # Temporarily write so the linter can inspect the file
            try:
                full_path.write_text(current_content, encoding="utf-8")
            except Exception as exc:
                self.logger.error(
                    "Cannot write file for lint check",
                    error=str(exc),
                )
                return False, attempt

            passed, error_msg = self.linter.validate_file(
                self.repo_name, file_path
            )

            if passed:
                return True, attempt

            if attempt < self.max_retries:
                self.logger.info(
                    "Lint failed – asking LLM to correct",
                    file=file_path,
                    attempt=attempt + 1,
                    errors=error_msg[:300],
                )
                retry_prompt = (
                    f"The following code in `{file_path}` has lint "
                    f"errors:\n{error_msg}\n\n"
                    f"Current code:\n```\n{current_content[:6000]}\n"
                    "```\n\nReturn ONLY the corrected file content."
                )
                raw = self._call_llm(
                    self.system_prompt,
                    retry_prompt,
                    temperature=0.0,
                    max_tokens=8192,
                )
                if raw:
                    fixed = self._strip_code_fences(raw)
                    if fixed.strip():
                        current_content = fixed

        # Restore original on total failure
        try:
            full_path.write_text(original_content, encoding="utf-8")
        except Exception:
            pass
        return False, self.max_retries

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------

    @staticmethod
    def _unified_diff(
        old: str, new: str, file_path: str
    ) -> str:
        """Generate a unified diff string."""
        return "".join(
            difflib.unified_diff(
                old.splitlines(keepends=True),
                new.splitlines(keepends=True),
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
            )
        )

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        """Remove markdown code fences from LLM output."""
        if "```" not in text:
            return text.strip()

        parts = text.split("```")
        if len(parts) < 3:
            return parts[-1].strip()

        inner = parts[1]
        lines = inner.split("\n")
        # Drop optional language tag on first line
        first = lines[0].strip().lower()
        lang_tags = {
            "python", "javascript", "typescript", "java", "go",
            "json", "yaml", "dockerfile", "xml", "html", "css",
            "sh", "bash", "toml", "ini", "py", "js", "ts",
        }
        if first in lang_tags:
            lines = lines[1:]
        return "\n".join(lines).strip()
    
    # -----------------------------------------------------------------
    # Scanner-specific prompt handling
    # -----------------------------------------------------------------
    
    def _get_scanner_prompt(self, source_tool: Optional[str]) -> str:
        """Get the appropriate system prompt based on the scanner source."""
        if source_tool and hasattr(ToolSource, source_tool.upper()):
            tool_enum = getattr(ToolSource, source_tool.upper())
            scanner_prompt = self.scanner_prompts.get(tool_enum)
            if scanner_prompt:
                return scanner_prompt
        
        # Fallback to default fixer prompt
        return self.system_prompt
        
    def _build_scanner_aware_prompt(
        self, 
        fix: ProposedFix, 
        file_path: str, 
        context: str,
        source_tool: Optional[str]
    ) -> str:
        """Build a user prompt that's aware of the scanner type."""
        base_prompt = (
            f"Fix the following issue in `{file_path}` using the systematic approach "
            f"outlined in the system prompt.\\n\\n"
            f"FINDING: {fix.description}\\n"
            f"SCANNER: {source_tool or 'Unknown'}\\n"
            f"STRATEGY: {fix.strategy.value}\\n"
        )
        
        # Add scanner-specific context
        if source_tool:
            if source_tool.upper() == "MEND":
                base_prompt += f"CVE/VULNERABILITY ID: {fix.finding_id}\\n"
                if fix.suggested_change:
                    base_prompt += f"RECOMMENDED FIX: {fix.suggested_change}\\n"
            elif source_tool.upper() == "SONARQUBE":
                base_prompt += f"SONARQUBE KEY: {fix.finding_id}\\n"
                if fix.metadata.get("rule_id"):
                    base_prompt += f"RULE ID: {fix.metadata.get('rule_id')}\\n"
            elif source_tool.upper() == "TRIVY": 
                base_prompt += f"CVE ID: {fix.finding_id}\\n"
                if fix.suggested_change:
                    base_prompt += f"FIXED VERSION: {fix.suggested_change}\\n"
        
        base_prompt += (
            f"\\nCODE CONTEXT:\\n```\\n{context}\\n```\\n\\n"
            "Apply the fix following the systematic methodology. "
            "Return ONLY the corrected code for the snippet above. "
            "Do not include explanations or markdown."
        )
        
        return base_prompt
