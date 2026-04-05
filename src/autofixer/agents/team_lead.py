"""Team-Lead agent for the autofixer multi-agent system.

The ``TeamLeadAgent`` sits between auditors and the fixer.  It:

1. Collects ``ProposedFix`` items from every ``AuditPlan``.
2. Groups fixes by target file.
3. Deduplicates (same CVE reported by multiple scanners).
4. Resolves conflicts (e.g. different version suggestions for the same
   package – picks the higher version).
5. Assigns priority based on severity.
6. Falls back to the LLM to resolve ambiguous conflicts.
7. Emits a single ``ConsolidatedPlan`` for the Fixer agent.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from structlog import get_logger

from autofixer.agents.base import BaseAgent
from autofixer.agents.messages import (
    AuditPlan,
    ConsolidatedFix,
    ConsolidatedPlan,
    ProposedFix,
)
from autofixer.llm.base import BaseLLMProvider


class TeamLeadAgent(BaseAgent):
    """Merges audit plans into a single prioritised work-list.

    Severity → priority mapping (lower number = higher priority):

    ======== ========
    Severity Priority
    ======== ========
    CRITICAL 1
    BLOCKER  2
    HIGH     3
    MAJOR    4
    MINOR    5
    INFO     6
    ======== ========
    """

    PRIORITY_MAP: Dict[str, int] = {
        "CRITICAL": 1,
        "BLOCKER": 2,
        "HIGH": 3,
        "MAJOR": 4,
        "MINOR": 5,
        "INFO": 6,
    }

    DEFAULT_PRIORITY: int = 99

    # -----------------------------------------------------------------
    # Construction
    # -----------------------------------------------------------------

    def __init__(
        self,
        llm_provider: BaseLLMProvider,
        config: Any = None,
    ) -> None:
        super().__init__(
            name="team_lead",
            llm_provider=llm_provider,
            config=config,
        )
        self.system_prompt = self._load_system_prompt("team_lead")

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    def consolidate(
        self, audit_plans: List[AuditPlan]
    ) -> ConsolidatedPlan:
        """Merge *audit_plans* into a ``ConsolidatedPlan``.

        Parameters
        ----------
        audit_plans:
            One ``AuditPlan`` per scanner that ran during auditing.

        Returns
        -------
        ConsolidatedPlan
            A deduplicated, conflict-resolved, priority-sorted plan.
        """
        self.logger.info(
            "Consolidating audit plans",
            plan_count=len(audit_plans),
        )

        # 1. Collect all proposed fixes ------------------------------------
        all_fixes: List[ProposedFix] = []
        for plan in audit_plans:
            all_fixes.extend(plan.proposed_fixes)
        self.logger.info("Total proposed fixes collected", count=len(all_fixes))

        # 2. Deduplicate ---------------------------------------------------
        dedup_fixes, dedup_notes = self._deduplicate(all_fixes)
        self.logger.info(
            "After deduplication",
            remaining=len(dedup_fixes),
            removed=len(all_fixes) - len(dedup_fixes),
        )

        # 3. Group by file -------------------------------------------------
        by_file: Dict[str, List[ProposedFix]] = defaultdict(list)
        for fix in dedup_fixes:
            by_file[fix.file_path].append(fix)

        # 4. Detect & resolve conflicts per file ---------------------------
        consolidated: List[ConsolidatedFix] = []
        conflict_notes: List[str] = []

        for file_path, fixes in by_file.items():
            has_conflicts, resolution, notes = self._resolve_conflicts(
                file_path, fixes
            )
            if notes:
                conflict_notes.extend(notes)

            # Determine file-level priority (best among its fixes)
            priority = self._best_priority(fixes)

            consolidated.append(
                ConsolidatedFix(
                    file_path=file_path,
                    fixes=resolution,
                    priority=priority,
                    has_conflicts=has_conflicts,
                    resolution_notes=(
                        "; ".join(notes) if notes else None
                    ),
                )
            )

        # 5. Sort by priority (ascending = most urgent first) --------------
        consolidated.sort(key=lambda c: c.priority)

        total_fixes = sum(len(c.fixes) for c in consolidated)
        summary = (
            f"Team-Lead: consolidated {len(all_fixes)} proposed fixes "
            f"into {total_fixes} across {len(consolidated)} files. "
            f"Dedup removed {len(all_fixes) - len(dedup_fixes)}. "
            f"Conflicts resolved: {len(conflict_notes)}."
        )
        self.logger.info("Consolidation complete", summary=summary)

        return ConsolidatedPlan(
            total_fixes=total_fixes,
            files_affected=len(consolidated),
            consolidated_fixes=consolidated,
            deduplication_notes=dedup_notes,
            conflict_resolutions=conflict_notes,
            summary=summary,
        )

    # -----------------------------------------------------------------
    # Deduplication
    # -----------------------------------------------------------------

    def _deduplicate(
        self, fixes: List[ProposedFix]
    ) -> Tuple[List[ProposedFix], List[str]]:
        """Remove duplicate findings (same CVE / finding_id across scanners).

        When a duplicate is detected the fix with the highest
        ``confidence`` is kept.

        Returns
        -------
        tuple
            (deduplicated list, list of human-readable notes)
        """
        notes: List[str] = []
        best: Dict[str, ProposedFix] = {}

        for fix in fixes:
            key = self._dedup_key(fix)
            existing = best.get(key)
            if existing is None:
                best[key] = fix
            else:
                # Keep the one with higher confidence
                kept, dropped = (
                    (fix, existing)
                    if fix.confidence > existing.confidence
                    else (existing, fix)
                )
                best[key] = kept
                src_kept = kept.metadata.get("source_tool", "?")
                src_drop = dropped.metadata.get("source_tool", "?")
                note = (
                    f"Dedup: {fix.finding_id} reported by both "
                    f"{src_kept} and {src_drop} – kept {src_kept} "
                    f"(confidence {kept.confidence:.2f} vs "
                    f"{dropped.confidence:.2f})."
                )
                notes.append(note)
                self.logger.debug("Deduplicated finding", note=note)

        return list(best.values()), notes

    @staticmethod
    def _dedup_key(fix: ProposedFix) -> str:
        """Build a key for dedup: normalised CVE / finding_id + file."""
        fid = fix.finding_id.upper().strip()
        # Strip scanner-specific suffixes like "-pkgname"
        # e.g. "CVE-2023-1234-lodash" → "CVE-2023-1234"
        if fid.startswith("CVE-"):
            parts = fid.split("-")
            if len(parts) > 3:
                fid = "-".join(parts[:3])
        return f"{fid}::{fix.file_path}"

    # -----------------------------------------------------------------
    # Conflict resolution
    # -----------------------------------------------------------------

    def _resolve_conflicts(
        self,
        file_path: str,
        fixes: List[ProposedFix],
    ) -> Tuple[bool, List[ProposedFix], List[str]]:
        """Detect and resolve conflicting fixes for a single file.

        Conflict types handled:

        * **Version conflict** – two VERSION_BUMP fixes suggest
          different target versions for the same package.  The higher
          semver wins.
        * **Strategy conflict** – multiple strategies target the same
          line.  The LLM is consulted to pick a winner.

        Returns
        -------
        tuple
            (has_conflicts, resolved_fixes, resolution_notes)
        """
        notes: List[str] = []
        has_conflict = False

        # --- Version conflicts -------------------------------------------
        version_bumps = [
            f for f in fixes if f.strategy.value == "version_bump"
        ]
        non_version = [
            f for f in fixes if f.strategy.value != "version_bump"
        ]

        resolved_bumps, bump_notes = self._resolve_version_conflicts(
            version_bumps
        )
        if bump_notes:
            has_conflict = True
            notes.extend(bump_notes)

        # --- Line-level strategy conflicts --------------------------------
        resolved_others, line_notes = self._resolve_line_conflicts(
            file_path, non_version
        )
        if line_notes:
            has_conflict = True
            notes.extend(line_notes)

        resolved = resolved_bumps + resolved_others
        return has_conflict, resolved, notes

    def _resolve_version_conflicts(
        self, bumps: List[ProposedFix]
    ) -> Tuple[List[ProposedFix], List[str]]:
        """For version-bump fixes, keep the highest suggested version."""
        if len(bumps) <= 1:
            return bumps, []

        notes: List[str] = []
        # Group by package heuristic (finding_id often contains pkg name)
        by_pkg: Dict[str, List[ProposedFix]] = defaultdict(list)
        for b in bumps:
            pkg_key = b.file_path  # same file = likely same manifest
            by_pkg[pkg_key].append(b)

        result: List[ProposedFix] = []
        for _pkg, group in by_pkg.items():
            if len(group) == 1:
                result.append(group[0])
                continue

            # Try to extract semver from suggested_change
            best = group[0]
            best_ver = self._extract_version(best.suggested_change)
            for fix in group[1:]:
                ver = self._extract_version(fix.suggested_change)
                if ver and best_ver and self._semver_gt(ver, best_ver):
                    note = (
                        f"Version conflict in {fix.file_path}: "
                        f"chose {ver} over {best_ver}."
                    )
                    notes.append(note)
                    best = fix
                    best_ver = ver
                elif fix.confidence > best.confidence:
                    best = fix
                    best_ver = ver

            result.append(best)

        return result, notes

    def _resolve_line_conflicts(
        self,
        file_path: str,
        fixes: List[ProposedFix],
    ) -> Tuple[List[ProposedFix], List[str]]:
        """Detect fixes targeting the same line and resolve via LLM."""
        if len(fixes) <= 1:
            return fixes, []

        notes: List[str] = []
        by_line: Dict[Optional[int], List[ProposedFix]] = defaultdict(
            list
        )
        for f in fixes:
            line = f.metadata.get("line")
            by_line[line].append(f)

        result: List[ProposedFix] = []
        for line, group in by_line.items():
            if len(group) == 1 or line is None:
                result.extend(group)
                continue

            # Multiple fixes on the same line → ask LLM
            winner = self._llm_pick_best(file_path, line, group)
            if winner:
                note = (
                    f"Line conflict at {file_path}:{line} – "
                    f"LLM chose finding {winner.finding_id}."
                )
                notes.append(note)
                result.append(winner)
            else:
                # Fallback: keep highest confidence
                group.sort(key=lambda f: f.confidence, reverse=True)
                result.append(group[0])
                note = (
                    f"Line conflict at {file_path}:{line} – "
                    f"kept highest-confidence fix "
                    f"{group[0].finding_id}."
                )
                notes.append(note)

        return result, notes

    # -----------------------------------------------------------------
    # LLM conflict resolution
    # -----------------------------------------------------------------

    def _llm_pick_best(
        self,
        file_path: str,
        line: Optional[int],
        candidates: List[ProposedFix],
    ) -> Optional[ProposedFix]:
        """Ask the LLM which fix to prefer when multiple target the same line."""
        descriptions = "\n".join(
            f"  [{i}] {c.finding_id} ({c.strategy.value}): "
            f"{c.description}  [confidence={c.confidence:.2f}]"
            for i, c in enumerate(candidates)
        )
        user_prompt = (
            f"Multiple fixes target {file_path} line {line}.  "
            "Pick the single best fix index and explain briefly.  "
            "Respond with JSON: {\"chosen_index\": <int>, "
            "\"reason\": \"...\"}.\n\n"
            f"Candidates:\n{descriptions}"
        )

        raw = self._call_llm(
            self.system_prompt,
            user_prompt,
            temperature=0.0,
            max_tokens=512,
        )
        if raw is None:
            return None

        parsed = self._parse_json_response(raw)
        if parsed and "chosen_index" in parsed:
            idx = int(parsed["chosen_index"])
            if 0 <= idx < len(candidates):
                return candidates[idx]
        return None

    # -----------------------------------------------------------------
    # Priority helpers
    # -----------------------------------------------------------------

    def _best_priority(self, fixes: List[ProposedFix]) -> int:
        """Return the highest (lowest number) priority among *fixes*."""
        best = self.DEFAULT_PRIORITY
        for fix in fixes:
            sev = str(
                fix.metadata.get("severity", "INFO")
            ).upper()
            best = min(best, self.PRIORITY_MAP.get(sev, self.DEFAULT_PRIORITY))
        return best

    # -----------------------------------------------------------------
    # Version utilities
    # -----------------------------------------------------------------

    _SEMVER_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")

    @classmethod
    def _extract_version(cls, text: Optional[str]) -> Optional[str]:
        """Pull the first semver-like string from *text*."""
        if not text:
            return None
        m = cls._SEMVER_RE.search(text)
        return m.group(0) if m else None

    @classmethod
    def _semver_gt(cls, a: str, b: str) -> bool:
        """Return ``True`` when semver *a* > *b*."""
        try:
            a_parts = tuple(int(x) for x in a.split("."))
            b_parts = tuple(int(x) for x in b.split("."))
            return a_parts > b_parts
        except (ValueError, AttributeError):
            return False
