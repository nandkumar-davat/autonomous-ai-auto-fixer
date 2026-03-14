import json
from typing import List, Dict, Any
from pathlib import Path
from structlog import get_logger
from autofixer.models.finding import Finding
from autofixer.models.enums import ToolSource, IssueType, Severity

logger = get_logger()

class SonarQubeFileParser:
    """Parser for SonarQube JSON exports."""

    def __init__(self):
        pass

    def _map_severity(self, sq_severity: str) -> Severity:
        mapping = {
            "BLOCKER": Severity.BLOCKER,
            "CRITICAL": Severity.CRITICAL,
            "MAJOR": Severity.MAJOR,
            "MINOR": Severity.MINOR,
            "INFO": Severity.INFO
        }
        return mapping.get(str(sq_severity).upper(), Severity.INFO)

    def _map_type(self, sq_type: str) -> IssueType:
        mapping = {
            "BUG": IssueType.BUG,
            "VULNERABILITY": IssueType.VULNERABILITY,
            "CODE_SMELL": IssueType.CODE_SMELL,
            "SECURITY_HOTSPOT": IssueType.SECURITY_HOTSPOT
        }
        return mapping.get(str(sq_type).upper(), IssueType.CODE_SMELL)

    def parse_file(self, file_path: Path) -> List[Finding]:
        """Parses a SonarQube JSON output file and yields findings."""
        logger.info("Parsing SonarQube file", file_path=str(file_path))
        
        if not file_path.exists():
            logger.error("File does not exist", file_path=str(file_path))
            return []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            logger.error("Failed to decode JSON", file_path=str(file_path), error=str(e))
            return []
            
        return self.parse_json(data)

    def parse_json(self, data: Dict[str, Any]) -> List[Finding]:
        """Parses a loaded JSON object for SonarQube issues."""
        findings = []
        
        # Sonar API format
        issues = data.get("issues", [])
        
        # Sometimes GitLab SAST format is wrapped differently, we'll try to extract "vulnerabilities" or similar
        if not issues and "vulnerabilities" in data:
            # Fallback for GitLab SAST like structure 
            issues = data.get("vulnerabilities", [])
            
        for issue in issues:
            key = issue.get("key", issue.get("id", "unknown-key"))
            rule = issue.get("rule", issue.get("cve", "unknown-rule"))
            message = issue.get("message", issue.get("description", "No message provided"))
            
            component = issue.get("component")
            if component:
                file_path = component.split(":")[-1] if ":" in component else component
            else:
                location = issue.get("location", {})
                file_path = location.get("file", "unknown-file")
                
            line = issue.get("line") or issue.get("location", {}).get("start_line")

            severity_str = issue.get("severity", "INFO")
            type_str = issue.get("type", "CODE_SMELL")
            
            finding = Finding(
                id=key,
                source_tool=ToolSource.SONARQUBE,
                issue_type=self._map_type(type_str),
                severity=self._map_severity(severity_str),
                file_path=file_path,
                line=line,
                message=message,
                rule_id=rule,
                raw_data=issue
            )
            findings.append(finding)

        logger.info("Successfully parsed SonarQube file", total_findings=len(findings))
        return findings
