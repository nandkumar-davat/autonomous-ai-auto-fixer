import httpx
from typing import List, Optional
from structlog import get_logger
from autofixer.models.finding import Finding
from autofixer.models.enums import ToolSource, IssueType, Severity
import asyncio

logger = get_logger()

class SonarQubeClient:
    """Client for SonarQube REST API."""

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def _map_severity(self, sq_severity: str) -> Severity:
        mapping = {
            "BLOCKER": Severity.BLOCKER,
            "CRITICAL": Severity.CRITICAL,
            "MAJOR": Severity.MAJOR,
            "MINOR": Severity.MINOR,
            "INFO": Severity.INFO
        }
        return mapping.get(sq_severity.upper(), Severity.INFO)

    def _map_type(self, sq_type: str) -> IssueType:
        mapping = {
            "BUG": IssueType.BUG,
            "VULNERABILITY": IssueType.VULNERABILITY,
            "CODE_SMELL": IssueType.CODE_SMELL,
            "SECURITY_HOTSPOT": IssueType.SECURITY_HOTSPOT
        }
        return mapping.get(sq_type.upper(), IssueType.CODE_SMELL)

    async def fetch_issues(self, project_key: str, status: str = "OPEN") -> List[Finding]:
        """Fetches issues from SonarQube using pagination."""
        url = f"{self.base_url}/api/issues/search"
        findings = []
        page = 1
        page_size = 100

        logger.info("Fetching issues from SonarQube", project=project_key)

        async with httpx.AsyncClient(headers=self.headers) as client:
            while True:
                params = {
                    "componentKeys": project_key,
                    "statuses": status,
                    "ps": page_size,
                    "p": page
                }
                
                try:
                    response = await client.get(url, params=params)
                    response.raise_for_status()
                    data = response.json()
                    issues = data.get("issues", [])
                    
                    if not issues:
                        break

                    for issue in issues:
                        # Extract basic info
                        key = issue["key"]
                        rule = issue["rule"]
                        message = issue["message"]
                        component = issue.get("component", "")
                        file_path = component.split(":")[-1] if ":" in component else component
                        line = issue.get("line")
                        
                        severity = self._map_severity(issue.get("severity", "INFO"))
                        issue_type = self._map_type(issue.get("type", "CODE_SMELL"))

                        finding = Finding(
                            id=key,
                            source_tool=ToolSource.SONARQUBE,
                            issue_type=issue_type,
                            severity=severity,
                            file_path=file_path,
                            line=line,
                            message=message,
                            rule_id=rule,
                            raw_data=issue
                        )
                        findings.append(finding)

                    total = data.get("total", 0)
                    if len(findings) >= total or len(issues) < page_size:
                        break

                    page += 1
                    
                except httpx.HTTPError as e:
                    logger.error("Failed to fetch SonarQube issues", error=str(e), url=response.url)
                    break

        logger.info("Finished fetching issues", total_fetched=len(findings))
        return findings
