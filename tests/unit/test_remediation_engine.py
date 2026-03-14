import pytest
from unittest.mock import MagicMock, patch
from autofixer.remediation.engine import RemediationEngine
from autofixer.models.finding import Finding
from autofixer.models.enums import ToolSource, IssueType, Severity, ApprovalStatus

@pytest.fixture
def mock_config():
    config = MagicMock()
    config.agent.mode = "dry-run"
    config.agent.risk_policy = {}
    return config

def test_engine_priority_sorting(mock_config):
    engine = RemediationEngine(mock_config)
    
    # Create findings with different priorities
    f1 = Finding(
        id="low-p", source_tool=ToolSource.SONARQUBE, issue_type=IssueType.CODE_SMELL,
        severity=Severity.MINOR, file_path="a.py", message="m1", rule_id="S1",
        priority_rank=10
    )
    f2 = Finding(
        id="high-p", source_tool=ToolSource.MEND, issue_type=IssueType.VULNERABILITY,
        severity=Severity.CRITICAL, file_path="b.py", message="m2", rule_id="S2",
        priority_rank=1
    )
    
    with patch.object(engine, 'ingest_findings', return_value=[f1, f2]):
        engine.run()
        
        assert engine.findings[0].id == "high-p"
        assert engine.findings[1].id == "low-p"

def test_engine_dry_run_logic(mock_config):
    mock_config.agent.mode = "dry-run"
    engine = RemediationEngine(mock_config)
    
    f1 = Finding(
        id="f1", source_tool=ToolSource.SONARQUBE, issue_type=IssueType.CODE_SMELL,
        severity=Severity.MINOR, file_path="a.py", message="m1", rule_id="S1",
        approval_status=ApprovalStatus.AUTO_APPROVED
    )
    
    with patch.object(engine, 'ingest_findings', return_value=[f1]):
        with patch.object(engine, 'generate_report') as mock_report:
            engine.run()
            
            # Check if process_finding was called and result reflected dry-run
            mock_report.assert_called_once()
            results = mock_report.call_args[0][0]
            assert results[0].applied is False
