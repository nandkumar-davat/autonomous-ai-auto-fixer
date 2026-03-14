from autofixer.models.enums import RiskLevel, Severity, IssueType, ApprovalStatus
from autofixer.models.finding import Finding
from structlog import get_logger

logger = get_logger()

class RiskAssessor:
    """Classifies findings into Low/High risk and determines if auto-fix is allowed."""

    def __init__(self, policy: str = "low-risk-only"):
        self.policy = policy

    def assess(self, finding: Finding) -> Finding:
        """Evaluates the finding and updates risk_level and approval_status."""
        logger.info("Assessing risk for finding", id=finding.id, type=finding.issue_type, severity=finding.severity)

        # 1. Base classification based on issue type and severity
        # High predictability issues are generally Low Risk
        if finding.issue_type == IssueType.CODE_SMELL:
            # Code smells like unused imports or naming conventions are Low Risk
            finding.risk_level = RiskLevel.LOW
        elif finding.issue_type == IssueType.VULNERABILITY:
            # Dependency bumps with direct upgrade paths are usually Low Risk
            # (In a real system, we'd check if it's a major version bump)
            finding.risk_level = RiskLevel.LOW
        else:
            finding.risk_level = RiskLevel.HIGH

        # 2. Determine approval status based on Priority/Severity
        # Bugs, Vulnerabilities, Blocker, Critical are Auto-Approved if Low Risk
        auto_fix_severities = [Severity.BLOCKER, Severity.CRITICAL]
        auto_fix_types = [IssueType.BUG, IssueType.VULNERABILITY]

        if finding.risk_level == RiskLevel.LOW:
            if finding.severity in auto_fix_severities or finding.issue_type in auto_fix_types:
                finding.approval_status = ApprovalStatus.AUTO_APPROVED
            else:
                # Major, High require user approval
                finding.approval_status = ApprovalStatus.PENDING_APPROVAL
        else:
            # High risk always requires approval
            finding.approval_status = ApprovalStatus.PENDING_APPROVAL

        logger.info("Risk assessment complete", id=finding.id, risk=finding.risk_level, status=finding.approval_status)
        return finding
