"""Multi-agent orchestrator for the autofixer pipeline.

Coordinates four sequential phases:
  1. **Audit**   – parallel scanner-specific auditors
  2. **Consolidate** – team-lead deduplication & prioritisation
  3. **Fix**     – apply code changes from the consolidated plan
  4. **Verify**  – run lint / build / test checks on the result
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

import structlog

from autofixer.agents.messages import (
    AuditPlan,
    ConsolidatedPlan,
    FixResult,
    VerificationReport,
)
from autofixer.config import Config
from autofixer.llm.base import BaseLLMProvider
from autofixer.llm.factory import LLMProviderFactory

logger = structlog.get_logger(__name__)

# Scanner type → report key mapping
_SCANNER_MAP: Dict[str, str] = {
    "mend": "mend_report",
    "trivy": "trivy_report",
    "sonarqube": "sonar_report",
}


class AgentOrchestrator:
    """Top-level orchestrator that drives all pipeline agents."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.llm_provider: BaseLLMProvider = self._init_llm_provider()
        logger.info(
            "Orchestrator initialised",
            mode=config.agent.mode,
            providers=config.llm.providers,
        )

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    def _init_llm_provider(self) -> BaseLLMProvider:
        """Create an LLM provider (or fallback chain) from config."""
        provider_names: List[str] = self.config.llm.providers
        if len(provider_names) == 1:
            return LLMProviderFactory.create_provider(provider_names[0])
        return LLMProviderFactory.create_fallback_chain(provider_names)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_pipeline(
        self,
        *,
        mend_report: Optional[str] = None,
        trivy_report: Optional[str] = None,
        sonar_report: Optional[str] = None,
        repo_path: str = ".",
        base_branch: str = "main",
    ) -> Dict[str, Any]:
        """Execute the full audit → consolidate → fix → verify pipeline.

        Parameters
        ----------
        mend_report:
            Path to a Mend (WhiteSource) JSON scan report.
        trivy_report:
            Path to a Trivy JSON scan report.
        sonar_report:
            Path to a SonarQube JSON scan report.
        repo_path:
            Local checkout of the target repository.
        base_branch:
            Git branch to create the fix branch from.

        Returns
        -------
        dict
            Combined results with keys ``audit_plans``,
            ``consolidated_plan``, ``fix_result``, ``verification``,
            and ``status``.
        """
        results: Dict[str, Any] = {
            "audit_plans": [],
            "consolidated_plan": None,
            "fix_result": None,
            "verification": None,
            "status": "success",
        }

        # ----- Phase 1: Audit (parallel) -----
        report_map: Dict[str, str] = self._resolve_reports(
            mend_report=mend_report,
            trivy_report=trivy_report,
            sonar_report=sonar_report,
        )

        if not report_map:
            logger.warning("No valid reports provided – nothing to audit")
            results["status"] = "no_reports"
            return results

        audit_plans = self._phase_audit(report_map)
        results["audit_plans"] = [p.model_dump() for p in audit_plans]

        if not audit_plans:
            logger.warning("All auditors returned empty plans")
            results["status"] = "no_findings"
            return results

        # ----- Phase 2: Consolidate -----
        consolidated = self._phase_consolidate(audit_plans)
        results["consolidated_plan"] = consolidated.model_dump()

        if consolidated.total_fixes == 0:
            logger.info("Consolidated plan contains zero fixes")
            results["status"] = "no_fixes"
            return results

        # ----- Phase 3: Fix -----
        fix_result = self._phase_fix(
            consolidated,
            repo_path=repo_path,
            base_branch=base_branch,
        )
        results["fix_result"] = fix_result.model_dump()

        # ----- Phase 4: Verify -----
        verification = self._phase_verify(fix_result, repo_path=repo_path)
        results["verification"] = verification.model_dump()

        results["status"] = verification.overall_status.lower()
        logger.info(
            "Pipeline complete",
            status=results["status"],
            fixes_applied=fix_result.total_fixes_applied,
            verification=verification.overall_status,
        )
        return results

    # ------------------------------------------------------------------
    # Phase implementations
    # ------------------------------------------------------------------

    def _phase_audit(
        self, report_map: Dict[str, str]
    ) -> List[AuditPlan]:
        """Run auditors in parallel, one per scanner report."""
        from autofixer.agents.auditor import AuditorAgent

        logger.info(
            "Phase 1: Audit",
            scanners=list(report_map.keys()),
        )

        plans: List[AuditPlan] = []
        max_workers = min(len(report_map), 3)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    self._run_single_auditor,
                    scanner_type,
                    report_path,
                ): scanner_type
                for scanner_type, report_path in report_map.items()
            }

            for future in as_completed(futures):
                scanner = futures[future]
                try:
                    plan = future.result()
                    if plan is not None:
                        plans.append(plan)
                        logger.info(
                            "Auditor complete",
                            scanner=scanner,
                            findings=plan.total_findings,
                            proposed=len(plan.proposed_fixes),
                        )
                except Exception:
                    logger.exception(
                        "Auditor failed",
                        scanner=scanner,
                    )

        return plans

    def _run_single_auditor(
        self, scanner_type: str, report_path: str
    ) -> Optional[AuditPlan]:
        """Instantiate and run a single AuditorAgent."""
        from autofixer.agents.auditor import AuditorAgent

        agent = AuditorAgent(
            scanner_type=scanner_type,
            llm_provider=self.llm_provider,
            config=self.config,
        )
        return agent.audit(report_path)

    def _phase_consolidate(
        self, audit_plans: List[AuditPlan]
    ) -> ConsolidatedPlan:
        """Consolidate and deduplicate findings across scanners."""
        from autofixer.agents.team_lead import TeamLeadAgent

        logger.info(
            "Phase 2: Consolidate",
            plan_count=len(audit_plans),
        )
        agent = TeamLeadAgent(
            llm_provider=self.llm_provider,
            config=self.config,
        )
        return agent.consolidate(audit_plans)

    def _phase_fix(
        self,
        plan: ConsolidatedPlan,
        *,
        repo_path: str,
        base_branch: str,
    ) -> FixResult:
        """Apply code fixes from the consolidated plan."""
        from autofixer.agents.fixer import FixerAgent

        logger.info(
            "Phase 3: Fix",
            total_fixes=plan.total_fixes,
            mode=self.config.agent.mode,
        )
        agent = FixerAgent(
            llm_provider=self.llm_provider,
            config=self.config,
            repo_path=repo_path,
            base_branch=base_branch,
        )
        return agent.apply_fixes(plan)

    def _phase_verify(
        self,
        fix_result: FixResult,
        *,
        repo_path: str,
    ) -> VerificationReport:
        """Verify the applied fixes pass lint / build / test checks."""
        from autofixer.agents.verifier import VerifierAgent

        logger.info(
            "Phase 4: Verify",
            fixes_applied=fix_result.total_fixes_applied,
        )
        agent = VerifierAgent(
            llm_provider=self.llm_provider,
            config=self.config,
        )
        return agent.verify(fix_result, repo_path)

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_reports(
        *,
        mend_report: Optional[str] = None,
        trivy_report: Optional[str] = None,
        sonar_report: Optional[str] = None,
    ) -> Dict[str, str]:
        """Return only the reports that actually exist on disk."""
        candidates: List[Tuple[str, Optional[str]]] = [
            ("mend", mend_report),
            ("trivy", trivy_report),
            ("sonarqube", sonar_report),
        ]
        resolved: Dict[str, str] = {}
        for scanner, path in candidates:
            if path is None:
                continue
            if not os.path.isfile(path):
                logger.warning(
                    "Report file not found – skipping scanner",
                    scanner=scanner,
                    path=path,
                )
                continue
            resolved[scanner] = path
        return resolved
