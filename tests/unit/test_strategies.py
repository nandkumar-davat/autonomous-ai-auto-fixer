import pytest
from unittest.mock import MagicMock
from autofixer.remediation.strategies.code_smell import CodeSmellStrategy
from autofixer.remediation.strategies.dependency import DependencyStrategy
from autofixer.remediation.strategies.security import SecurityStrategy
from autofixer.models.finding import Finding
from autofixer.models.enums import ToolSource, IssueType, Severity

@pytest.fixture
def mock_llm_client():
    client = MagicMock()
    client.generate_fix.return_value = "fixed code"
    return client

def test_code_smell_strategy_heuristic(mock_llm_client):
    strategy = CodeSmellStrategy(mock_llm_client)
    finding = Finding(
        id="f1", source_tool=ToolSource.SONARQUBE, issue_type=IssueType.CODE_SMELL,
        severity=Severity.MINOR, file_path="main.py", message="unused import 'os'", rule_id="S1"
    )
    context = "import os\nimport sys\nprint('hi')"
    
    # Heuristic for unused imports
    result = strategy.fix(finding, context)
    assert "import os" not in result
    assert "import sys" in result

def test_dependency_strategy_fast_path(mock_llm_client):
    strategy = DependencyStrategy(mock_llm_client)
    finding = Finding(
        id="f2", source_tool=ToolSource.MEND, issue_type=IssueType.VULNERABILITY,
        severity=Severity.HIGH, file_path="package.json", 
        message="Upgrade to 1.2.3", rule_id="CVE-2",
        raw_data={"name": "lodash"}
    )
    context = '{"dependencies": {"lodash": "1.0.0"}}'
    
    result = strategy.fix(finding, context)
    assert '"lodash": "1.2.3"' in result

def test_security_strategy_dockerfile(mock_llm_client):
    strategy = SecurityStrategy(mock_llm_client)
    finding = Finding(
        id="f3", source_tool=ToolSource.TRIVY, issue_type=IssueType.VULNERABILITY,
        severity=Severity.CRITICAL, file_path="Dockerfile", 
        message="fixed in 3.10-slim", rule_id="CVE-3"
    )
    context = "FROM python:3.9-slim\nRUN echo hi"
    
    result = strategy.fix(finding, context)
    assert "FROM python:3.10-slim" in result

def test_strategy_llm_fallback(mock_llm_client):
    strategy = SecurityStrategy(mock_llm_client)
    finding = Finding(
        id="f4", source_tool=ToolSource.SONARQUBE, issue_type=IssueType.BUG,
        severity=Severity.MAJOR, file_path="app.py", message="complex stuff", rule_id="S4"
    )
    context = "def foo(): pass"
    
    result = strategy.fix(finding, context)
    assert result == "fixed code"
    mock_llm_client.generate_fix.assert_called_once()
