import httpx
from typing import List, Optional
from structlog import get_logger
from autofixer.models.finding import Finding
from autofixer.models.enums import ToolSource, IssueType, Severity
import asyncio

logger = get_logger()

class MendAPIClient:
    """Client for Mend Platform API 3.0."""

    def __init__(self, base_url: str, user_key: str, org_token: str):
        self.base_url = base_url.rstrip('/')
        self.user_key = user_key
        self.org_token = org_token
        # Mend commonly uses a specific login endpoint to get a JWT, or headers depending on the exact API version.
        # Assuming token-based auth for API 3.0
        self.headers = {
            "Authorization": f"Bearer {self.user_key}",
            "Content-Type": "application/json"
        }

    def _map_severity(self, mend_severity: str) -> Severity:
        mapping = {
            "HIGH": Severity.HIGH,
            "MEDIUM": Severity.MAJOR,
            "LOW": Severity.MINOR,
            "CRITICAL": Severity.CRITICAL,
        }
        return mapping.get(mend_severity.upper(), Severity.INFO)

    async def fetch_vulnerabilities(self, project_uuid: str) -> List[Finding]:
        """Fetches vulnerabilities for a Mend project."""
        url = f"{self.base_url}/api/v3/projects/{project_uuid}/alerts/vulnerabilities"
        findings = []

        logger.info("Fetching Mend vulnerabilities", project=project_uuid)

        async with httpx.AsyncClient(headers=self.headers) as client:
            try:
                # Assuming Mend returns a paginated list or list of alerts
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                
                alerts = data.get("alerts", [])
                
                for alert in alerts:
                    # Mend API 3.0 Alert JSON structure (simplified)
                    uuid = alert.get("uuid")
                    vulnerability = alert.get("vulnerability", {})
                    name = vulnerability.get("name", "Unknown CVE")
                    description = vulnerability.get("description", "")
                    severity = self._map_severity(vulnerability.get("severity", "LOW"))
                    
                    library = alert.get("library", {})
                    lib_name = library.get("name", "Unknown Library")
                    lib_version = library.get("version", "Unknown")
                    file_path = library.get("filename", "")
                    
                    message = f"Vulnerability {name} in {lib_name} (v{lib_version}). {description}"
                    
                    finding = Finding(
                        id=uuid,
                        source_tool=ToolSource.MEND,
                        issue_type=IssueType.VULNERABILITY, # Mend primarily reports SCA vulnerabilities
                        severity=severity,
                        file_path=file_path,
                        line=None, # SCA findings often don't have a specific line number
                        message=message,
                        rule_id=name,
                        raw_data=alert
                    )
                    findings.append(finding)
                    
            except httpx.HTTPError as e:
                logger.error("Failed to fetch Mend issues", error=str(e), url=url)

        logger.info("Finished fetching Mend issues", total_fetched=len(findings))
        return findings
