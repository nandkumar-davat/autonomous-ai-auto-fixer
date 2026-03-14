import pytest
from autofixer.models.enums import RiskLevel, Severity, IssueType, ApprovalStatus
from autofixer.models.finding import Finding
from autofixer.remediation.risk_assessor import RiskAssessor

def test_risk_assessor_code_smell():
    assessor = RiskAssessor()
    finding = Finding(
        id="test-1",
        source_tool="SONARQUBE",
        issue_type=IssueType.CODE_SMELL,
        severity=Severity.MINOR,
        file_path="main.py",
        message="Unused import",
        rule_id="python:S1128"
    )
    
    result = assessor.assess(finding)
    assert result.risk_level == RiskLevel.LOW
    assert result.approval_status == ApprovalStatus.PENDING_APPROVAL

def test_risk_assessor_vulnerability_auto_fix():
    assessor = RiskAssessor()
    finding = Finding(
        id="test-2",
        source_tool="MEND",
        issue_type=IssueType.VULNERABILITY,
        severity=Severity.CRITICAL,
        file_path="package.json",
        message="CVE in dependency",
        rule_id="CVE-2023-1000"
    )
    
    result = assessor.assess(finding)
    assert result.risk_level == RiskLevel.LOW
    assert result.approval_status == ApprovalStatus.AUTO_APPROVED

def test_risk_assessor_high_risk_bug():
    assessor = RiskAssessor()
    finding = Finding(
        id="test-3",
        source_tool="SONARQUBE",
        issue_type=IssueType.BUG,
        severity=Severity.MAJOR,
        file_path="logic.py",
        message="Complex state logic bug",
        rule_id="S1234"
    )
    
    result = assessor.assess(finding)
    # Bugs aren't guaranteed low risk in the current implementation default
    assert result.risk_level == RiskLevel.HIGH
    assert result.approval_status == ApprovalStatus.PENDING_APPROVAL
