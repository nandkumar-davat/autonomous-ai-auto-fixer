import json
from typing import List, Dict, Any
from pathlib import Path
from structlog import get_logger
from autofixer.models.finding import Finding
from autofixer.models.enums import ToolSource, IssueType, Severity

logger = get_logger()

class TrivyFileParser:
    """Parser for Trivy JSON and SARIF reports."""

    def __init__(self):
        pass

    def _map_severity(self, trivy_severity: str) -> Severity:
        mapping = {
            "CRITICAL": Severity.CRITICAL,
            "HIGH": Severity.HIGH,
            "MEDIUM": Severity.MAJOR,
            "LOW": Severity.MINOR,
            "UNKNOWN": Severity.INFO
        }
        return mapping.get(str(trivy_severity).upper(), Severity.INFO)

    def parse_file(self, file_path: Path) -> List[Finding]:
        """Parses a Trivy report file and returns findings."""
        logger.info("Parsing Trivy file", file_path=str(file_path))
        findings = []

        if not file_path.exists():
            logger.error("File does not exist", file_path=str(file_path))
            return []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            logger.error("Failed to decode JSON", file_path=str(file_path), error=str(e))
            return []

        # Detect format: SARIF or Trivy JSON
        if data.get("$schema", "").endswith("sarif-2.1.0.json") or "runs" in data:
            return self.parse_sarif(data)
        else:
            return self.parse_json(data)

    def parse_json(self, data: Dict[str, Any]) -> List[Finding]:
        """Parses a standard Trivy JSON report."""
        findings = []
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
                
                message = f"Vulnerability {vuln_id} in {pkg_name} ({installed_version})."
                if fixed_version:
                    message += f" Fixed in: {fixed_version}."
                
                findings.append(Finding(
                    id=f"{vuln_id}-{pkg_name}",
                    source_tool=ToolSource.TRIVY,
                    issue_type=IssueType.VULNERABILITY,
                    severity=severity,
                    file_path=target,
                    line=None,
                    message=message,
                    rule_id=vuln_id,
                    raw_data=vuln
                ))
        
        return findings

    def parse_sarif(self, data: Dict[str, Any]) -> List[Finding]:
        """Parses a SARIF report (Trivy supports SARIF export)."""
        findings = []
        runs = data.get("runs", [])
        
        for run in runs:
            results = run.get("results", [])
            rules = {r["id"]: r for r in run.get("tool", {}).get("driver", {}).get("rules", [])}
            
            for result in results:
                rule_id = result.get("ruleId")
                message = result.get("message", {}).get("text", "No message")
                
                # In SARIF, location info is nested
                locations = result.get("locations", [])
                file_path = "unknown"
                line = None
                if locations:
                    uri = locations[0].get("physicalLocation", {}).get("artifactLocation", {}).get("uri")
                    if uri:
                        file_path = uri
                    line = locations[0].get("physicalLocation", {}).get("region", {}).get("startLine")

                # Map SARIF level to our Severity
                level = result.get("level", "warning")
                severity = Severity.MAJOR
                if level == "error": severity = Severity.CRITICAL
                elif level == "note": severity = Severity.MINOR

                findings.append(Finding(
                    id=f"{rule_id}-{file_path}",
                    source_tool=ToolSource.TRIVY,
                    issue_type=IssueType.VULNERABILITY,
                    severity=severity,
                    file_path=file_path,
                    line=line,
                    message=message,
                    rule_id=rule_id,
                    raw_data=result
                ))
        
        return findings
