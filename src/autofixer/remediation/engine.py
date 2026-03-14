from typing import List, Optional
from autofixer.models.finding import Finding, RemediationResult
from autofixer.models.enums import AgentMode, ApprovalStatus, RiskLevel
from autofixer.remediation.risk_assessor import RiskAssessor
from structlog import get_logger

logger = get_logger()

class RemediationEngine:
    """Core orchestrator for scanning, classifying, and fixing issues."""

    def __init__(self, config):
        self.config = config
        self.risk_assessor = RiskAssessor(policy=config.agent.risk_policy)
        self.findings: List[Finding] = []

    def run(self, repo_name: Optional[str] = None):
        """Main execution loop."""
        logger.info("Starting remediation engine", mode=self.config.agent.mode)
        
        # 1. Ingestion (Mocked for now)
        raw_findings = self.ingest_findings(repo_name)
        
        # 2. Risk Assessment & Priority Sorting
        processed_findings = []
        for raw in raw_findings:
            finding = self.risk_assessor.assess(raw)
            processed_findings.append(finding)
            
        # Sort by priority rank (assigned during ingestion based on type/severity)
        self.findings = sorted(processed_findings, key=lambda x: x.priority_rank)
        
        # 3. Process Findings
        results = []
        for finding in self.findings:
            if finding.approval_status == ApprovalStatus.AUTO_APPROVED:
                result = self.process_finding(finding)
                results.append(result)
            else:
                logger.info("Finding skipped (approval required or rejected)", id=finding.id, status=finding.approval_status)
        
        # 4. Reporting
        self.generate_report(results)

    def ingest_findings(self, repo_name: Optional[str]) -> List[Finding]:
        """Placeholder for tool-specific ingestion (SonarQube, Mend, Trivy)."""
        logger.info("Ingesting findings")
        return [] # Implement in Phase 2-4

    def process_finding(self, finding: Finding) -> RemediationResult:
        """Fixes a single finding."""
        logger.info("Processing finding", id=finding.id)
        
        # In Dry-Run mode, we just simulate
        if self.config.agent.mode == "dry-run":
            logger.info("Dry-run: simulating fix", id=finding.id)
            return RemediationResult(finding=finding, applied=False, validation_passed=True)
            
        # In Fix mode, we'd call the LLM and VCS
        # 1. Retrieve Context
        # 2. Call LLM
        # 3. Validate Fix
        # 4. Create PR
        return RemediationResult(finding=finding, applied=True, validation_passed=True)

    def generate_report(self, results: List[RemediationResult]):
        """Generates a summary of actions taken."""
        logger.info("Generating execution report", total_results=len(results))
        # TODO: Implement structured reporting
