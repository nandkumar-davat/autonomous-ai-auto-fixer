import pytest
from pydantic import ValidationError
from autofixer.models.finding import Finding, RemediationResult
from autofixer.models.enums import ToolSource, Severity, IssueType, RiskLevel, ApprovalStatus

def test_finding_creation():
    finding = Finding(
        id="test-key",
        source_tool=ToolSource.SONARQUBE,
        issue_type=IssueType.BUG,
        severity=Severity.CRITICAL,
        file_path="src/main.py",
        line=10,
        message="A bug found",
        rule_id="S101",
        risk_level=RiskLevel.LOW,
        priority_rank=1
    )
    assert finding.id == "test-key"
    assert finding.source_tool == ToolSource.SONARQUBE
    assert finding.risk_level == RiskLevel.LOW

def test_finding_defaults():
    finding = Finding(
        id="test-key",
        source_tool=ToolSource.SONARQUBE,
        issue_type=IssueType.BUG,
        severity=Severity.CRITICAL,
        file_path="src/main.py",
        message="A bug found",
        rule_id="S101"
    )
    assert finding.risk_level == RiskLevel.HIGH
    assert finding.priority_rank == 99
    assert finding.approval_status == ApprovalStatus.PENDING_APPROVAL

def test_remediation_result_creation():
    finding = Finding(
        id="test-key",
        source_tool=ToolSource.SONARQUBE,
        issue_type=IssueType.BUG,
        severity=Severity.CRITICAL,
        file_path="src/main.py",
        message="A bug found",
        rule_id="S101"
    )
    result = RemediationResult(
        finding=finding,
        original_code="old",
        fixed_code="new",
        applied=True,
        validation_passed=True
    )
    assert result.finding.id == "test-key"
    assert result.applied is True
    assert result.validation_passed is True
