import httpx
from typing import List, Optional
from structlog import get_logger
from autofixer.models.finding import Finding
from autofixer.models.enums import ToolSource, IssueType, Severity

logger = get_logger()

class TrivyAPIClient:
    """Client for Trivy Server or Operator API."""

    def __init__(self, base_url: str, token: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.headers = {}
        if token:
            self.headers["Trivy-Token"] = token

    def _map_severity(self, trivy_severity: str) -> Severity:
        mapping = {
            "CRITICAL": Severity.CRITICAL,
            "HIGH": Severity.HIGH,
            "MEDIUM": Severity.MAJOR,
            "LOW": Severity.MINOR,
            "UNKNOWN": Severity.INFO
        }
        return mapping.get(trivy_severity.upper(), Severity.INFO)

    async def scan_image(self, image_name: str) -> List[Finding]:
        """Requests Trivy server to scan a container image."""
        # Note: Trivy server API usually involves POSTing a scan request or using the trivy client CLI pointed at a server.
        # This implementation assumes a standard REST interface for a Trivy server/operator.
        url = f"{self.base_url}/twirp/trivy.scanner.v1.Scanner/Scan"
        findings = []

        logger.info("Requesting Trivy scan", image=image_name)

        async with httpx.AsyncClient(headers=self.headers, timeout=60.0) as client:
            try:
                # Mocking the TWIRP/GRPC-web like request format Trivy server uses
                payload = {
                    "target": image_name,
                    "artifact_type": "CONTAINER_IMAGE"
                }
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                
                results = data.get("Results", [])
                for result in results:
                    target = result.get("Target", "unknown")
                    vulnerabilities = result.get("Vulnerabilities", [])
                    
                    for vuln in vulnerabilities:
                        vuln_id = vuln.get("VulnerabilityID", "UNKNOWN")
                        pkg_name = vuln.get("PkgName", "unknown")
                        installed_version = vuln.get("InstalledVersion", "")
                        fixed_version = vuln.get("FixedVersion", "")
                        severity = self._map_severity(vuln.get("Severity", "LOW"))
                        
                        message = f"Vulnerability {vuln_id} found in {pkg_name} ({installed_version})."
                        if fixed_version:
                            message += f" Fixed in version {fixed_version}."
                        
                        finding = Finding(
                            id=f"{vuln_id}-{pkg_name}",
                            source_tool=ToolSource.TRIVY,
                            issue_type=IssueType.VULNERABILITY,
                            severity=severity,
                            file_path=target,
                            line=None,
                            message=message,
                            rule_id=vuln_id,
                            raw_data=vuln
                        )
                        findings.append(finding)
                        
            except httpx.HTTPError as e:
                logger.error("Failed to fetch Trivy scan results", error=str(e), url=url)

        logger.info("Finished fetching Trivy issues", total_fetched=len(findings))
        return findings
