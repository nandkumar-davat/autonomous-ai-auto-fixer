"""Auditor agent for the autofixer multi-agent system.

The ``AuditorAgent`` is responsible for:

1. Parsing a scanner report (Mend, Trivy, or SonarQube).
2. Filtering findings by severity and issue-type thresholds.
3. Determining the appropriate ``FixStrategy`` for each finding.
4. Optionally consulting the LLM to assess fix confidence.
5. Producing an ``AuditPlan`` consumed by the Team-Lead agent.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from structlog import get_logger

from autofixer.agents.base import BaseAgent
from autofixer.agents.messages import (
    AuditPlan,
    FixStrategy,
    ProposedFix,
)
from autofixer.ingestion.mend.json_parser import MendJSONParser
from autofixer.ingestion.sonarqube.file_parser import SonarQubeFileParser
from autofixer.ingestion.trivy.file_parser import TrivyFileParser
from autofixer.llm.base import BaseLLMProvider
from autofixer.models.enums import IssueType, Severity, ToolSource
from autofixer.models.finding import Finding


class AuditorAgent(BaseAgent):
    """Analyses scanner reports and produces an ``AuditPlan``.

    Each scanner type (``mend``, ``trivy``, ``sonarqube``) has its own
    severity / issue-type filter gates so that only actionable findings
    are forwarded to subsequent pipeline stages.
    """

    # Severity values that pass the filter for each scanner.
    SEVERITY_FILTERS: Dict[str, List[str]] = {
        "mend": ["CRITICAL", "HIGH", "MAJOR"],
        "trivy": ["CRITICAL", "HIGH"],
        "sonarqube": ["BLOCKER", "CRITICAL", "MAJOR", "HIGH"],
    }

    # Extra issue-type gate (only applied when the key is present).
    ISSUE_TYPE_FILTERS: Dict[str, List[str]] = {
        "sonarqube": ["BUG", "VULNERABILITY", "SECURITY_HOTSPOT"],
    }

    # -----------------------------------------------------------------
    # Construction
    # -----------------------------------------------------------------

    def __init__(
        self,
        scanner_type: str,
        llm_provider: BaseLLMProvider,
        config: Any = None,
    ) -> None:
        super().__init__(
            name=f"auditor_{scanner_type}",
            llm_provider=llm_provider,
            config=config,
        )
        self.scanner_type = scanner_type.lower()
        self.parser = self._get_parser()
        self.system_prompt = self._load_system_prompt("auditor")

    # -----------------------------------------------------------------
    # Parser selection
    # -----------------------------------------------------------------

    def _get_parser(
        self,
    ) -> MendJSONParser | TrivyFileParser | SonarQubeFileParser:
        """Return the parser instance matching ``self.scanner_type``."""
        if self.scanner_type == "mend":
            return MendJSONParser()
        if self.scanner_type == "trivy":
            return TrivyFileParser()
        if self.scanner_type == "sonarqube":
            return SonarQubeFileParser()
        raise ValueError(
            f"Unsupported scanner type: {self.scanner_type!r}. "
            "Expected one of: mend, trivy, sonarqube."
        )

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    def audit(self, report_path: str) -> AuditPlan:
        """Parse *report_path*, filter, strategise and return an ``AuditPlan``.

        Parameters
        ----------
        report_path:
            Filesystem path to the scanner's JSON/SARIF report.

        Returns
        -------
        AuditPlan
            A plan containing all ``ProposedFix`` items ready for
            consolidation.
        """
        self.logger.info("Starting audit", report_path=report_path)

        # 1. Parse -------------------------------------------------------
        path = Path(report_path)
        all_findings: List[Finding] = self.parser.parse_file(path)
        total_count = len(all_findings)
        self.logger.info(
            "Parsed findings from report",
            total=total_count,
            scanner=self.scanner_type,
        )

        # 2. Filter -------------------------------------------------------
        filtered = self._filter_findings(all_findings)
        skipped = [
            {
                "id": f.id,
                "severity": f.severity,
                "issue_type": f.issue_type,
                "reason": "below_threshold",
            }
            for f in all_findings
            if f not in filtered
        ]
        self.logger.info(
            "Filtering complete",
            kept=len(filtered),
            skipped=len(skipped),
        )

        # 3. Strategise & assess -----------------------------------------
        proposed_fixes: List[ProposedFix] = []
        for finding in filtered:
            strategy = self._determine_strategy(finding)
            confidence = self._base_confidence(finding, strategy)
            suggested_change = self._get_suggested_change(finding)

            # Optional LLM assessment for complex cases
            if strategy == FixStrategy.LLM_ASSISTED:
                llm_assessment = self._llm_assess(finding)
                if llm_assessment:
                    confidence = llm_assessment.get(
                        "confidence", confidence
                    )
                    suggested_change = llm_assessment.get(
                        "suggested_change", suggested_change
                    )

            proposed_fixes.append(
                ProposedFix(
                    finding_id=finding.id,
                    file_path=finding.file_path,
                    strategy=strategy,
                    description=finding.message,
                    confidence=min(max(confidence, 0.0), 1.0),
                    suggested_change=suggested_change,
                    metadata={
                        "severity": finding.severity
                        if isinstance(finding.severity, str)
                        else finding.severity,
                        "rule_id": finding.rule_id,
                        "source_tool": self.scanner_type,
                        "line": finding.line,
                        "issue_type": finding.issue_type
                        if isinstance(finding.issue_type, str)
                        else finding.issue_type,
                    },
                )
            )

        summary = (
            f"Auditor ({self.scanner_type}): "
            f"{total_count} total findings, "
            f"{len(filtered)} passed filters, "
            f"{len(proposed_fixes)} proposed fixes."
        )
        self.logger.info("Audit complete", summary=summary)

        return AuditPlan(
            scanner_type=self.scanner_type,
            total_findings=total_count,
            filtered_findings=len(filtered),
            proposed_fixes=proposed_fixes,
            skipped_findings=skipped,
            summary=summary,
        )

    # -----------------------------------------------------------------
    # Filtering
    # -----------------------------------------------------------------

    def _filter_findings(
        self, findings: List[Finding]
    ) -> List[Finding]:
        """Apply severity (and optionally issue-type) filters."""
        allowed_severities = {
            s.upper()
            for s in self.SEVERITY_FILTERS.get(
                self.scanner_type, []
            )
        }
        allowed_types: set[str] | None = None
        if self.scanner_type in self.ISSUE_TYPE_FILTERS:
            allowed_types = {
                t.upper()
                for t in self.ISSUE_TYPE_FILTERS[self.scanner_type]
            }

        result: List[Finding] = []
        for f in findings:
            sev = (
                f.severity.upper()
                if isinstance(f.severity, str)
                else f.severity
            )
            if sev not in allowed_severities:
                continue

            if allowed_types is not None:
                itype = (
                    f.issue_type.upper()
                    if isinstance(f.issue_type, str)
                    else f.issue_type
                )
                if itype not in allowed_types:
                    continue

            result.append(f)
        return result

    # -----------------------------------------------------------------
    # Strategy determination
    # -----------------------------------------------------------------

    def _determine_strategy(self, finding: Finding) -> FixStrategy:
        """Pick a ``FixStrategy`` for *finding* based on heuristics."""
        issue = (
            finding.issue_type.upper()
            if isinstance(finding.issue_type, str)
            else finding.issue_type
        )
        fp_lower = finding.file_path.lower()

        # Dependency vulnerabilities → version bump
        if issue == "VULNERABILITY" and self.scanner_type in (
            "mend",
            "trivy",
        ):
            if fp_lower.endswith(("package.json", "requirements.txt",
                                  "pom.xml", "build.gradle",
                                  ".csproj", "packages.config",
                                  "pyproject.toml")):
                return FixStrategy.VERSION_BUMP

        # Dockerfile issues → dedicated strategy
        if fp_lower.endswith("dockerfile") or "dockerfile" in fp_lower:
            return FixStrategy.DOCKERFILE_UPDATE

        # Config file changes
        if fp_lower.endswith((".yml", ".yaml", ".toml", ".cfg", ".ini")):
            return FixStrategy.CONFIG_CHANGE

        # SonarQube code smells → direct code patch
        if issue == "CODE_SMELL":
            return FixStrategy.CODE_PATCH

        # Everything else (security hotspots, complex vulns) → LLM
        return FixStrategy.LLM_ASSISTED

    # -----------------------------------------------------------------
    # Confidence heuristics
    # -----------------------------------------------------------------

    @staticmethod
    def _base_confidence(
        finding: Finding, strategy: FixStrategy
    ) -> float:
        """Return a baseline confidence score (0-1)."""
        # Deterministic strategies get higher base confidence
        score_map: Dict[FixStrategy, float] = {
            FixStrategy.VERSION_BUMP: 0.85,
            FixStrategy.DOCKERFILE_UPDATE: 0.70,
            FixStrategy.CONFIG_CHANGE: 0.65,
            FixStrategy.CODE_PATCH: 0.60,
            FixStrategy.LLM_ASSISTED: 0.50,
        }
        base = score_map.get(strategy, 0.50)

        # Boost if the finding includes a concrete fix suggestion
        raw = finding.raw_data or {}
        if raw.get("fix_resolution") or raw.get("FixedVersion"):
            base = min(base + 0.10, 1.0)

        return round(base, 2)

    # -----------------------------------------------------------------
    # Suggested-change extraction
    # -----------------------------------------------------------------

    @staticmethod
    def _get_suggested_change(finding: Finding) -> Optional[str]:
        """Extract an actionable suggestion from the finding metadata."""
        raw = finding.raw_data or {}

        # Mend
        top_fix = raw.get("alert", {}).get("topFix", {})
        if top_fix:
            resolution = top_fix.get("fixResolution")
            if resolution:
                return f"Upgrade to {resolution}"

        # Trivy
        fixed_ver = raw.get("FixedVersion")
        if fixed_ver:
            pkg = raw.get("PkgName", "package")
            return f"Upgrade {pkg} to {fixed_ver}"

        # Generic message extraction
        fix_res = raw.get("fix_resolution")
        if fix_res and fix_res != "No fix available":
            return fix_res

        return None

    # -----------------------------------------------------------------
    # LLM assessment for complex findings
    # -----------------------------------------------------------------

    def _llm_assess(
        self, finding: Finding
    ) -> Optional[Dict[str, Any]]:
        """Ask the LLM to assess fix difficulty and suggest a change.

        Returns a dict with ``confidence`` (float) and optionally
        ``suggested_change`` (str), or ``None`` on failure.
        """
        user_prompt = (
            "Assess the following security finding and provide a JSON "
            "response with keys 'confidence' (float 0-1) and "
            "'suggested_change' (string).\n\n"
            f"Finding ID: {finding.id}\n"
            f"File: {finding.file_path}\n"
            f"Line: {finding.line}\n"
            f"Severity: {finding.severity}\n"
            f"Message: {finding.message}\n"
            f"Rule: {finding.rule_id}\n"
        )

        raw = self._call_llm(
            self.system_prompt,
            user_prompt,
            temperature=0.0,
            max_tokens=1024,
        )
        if raw is None:
            return None

        parsed = self._parse_json_response(raw)
        if parsed and "confidence" in parsed:
            return {
                "confidence": float(parsed["confidence"]),
                "suggested_change": parsed.get("suggested_change"),
            }
        return None
