import httpx
import pytest
from autofixer.ingestion.sonarqube.api_client import SonarQubeClient
from autofixer.models.enums import ToolSource, IssueType

class MockResponse:
    def __init__(self, json_data, status_code=200):
        self.json_data = json_data
        self.status_code = status_code
        self.url = "http://mock-sonarqube/api/issues/search"

    def json(self):
        return self.json_data
        
    def raise_for_status(self):
        pass

@pytest.fixture
def mock_httpx_client(mocker):
    # This assumes using pytest-mock
    pass # To complete later if needed, but here we can just do a class monkeypatch

@pytest.mark.asyncio
async def test_sonarqube_api_client(monkeypatch):
    
    async def mock_get(*args, **kwargs):
        # Only return items on the first page, empty on 2nd
        if kwargs.get('params', {}).get('p') == 1:
            return MockResponse({
                "total": 1,
                "issues": [
                    {
                        "key": "AWE123",
                        "rule": "python:S1128",
                        "severity": "MINOR",
                        "component": "my_project:src/main.py",
                        "line": 15,
                        "message": "Remove this unused import",
                        "type": "CODE_SMELL"
                    }
                ]
            })
        else:
            return MockResponse({"total": 1, "issues": []})

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
    
    client = SonarQubeClient("http://mock-sonarqube", "fake-token")
    findings = await client.fetch_issues("my_project")
    
    assert len(findings) == 1
    assert findings[0].id == "AWE123"
    assert findings[0].source_tool == ToolSource.SONARQUBE
    assert findings[0].issue_type == IssueType.CODE_SMELL
