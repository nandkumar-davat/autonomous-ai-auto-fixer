import csv
from typing import List
from pathlib import Path
from structlog import get_logger
from autofixer.models.finding import Finding
from autofixer.models.enums import ToolSource, IssueType, Severity

logger = get_logger()

class MendCSVParser:
    """Parser for Mend CSV reports."""

    def __init__(self):
        pass

    def _map_severity(self, mend_severity: str) -> Severity:
        mapping = {
            "HIGH": Severity.HIGH,
            "MEDIUM": Severity.MAJOR,
            "LOW": Severity.MINOR,
            "CRITICAL": Severity.CRITICAL,
        }
        return mapping.get(str(mend_severity).upper().strip(), Severity.INFO)

    def parse_file(self, file_path: Path) -> List[Finding]:
        """Parses a Mend CSV file and returns findings."""
        logger.info("Parsing Mend CSV file", file_path=str(file_path))
        findings = []

        if not file_path.exists():
            logger.error("File does not exist", file_path=str(file_path))
            return []

        try:
            with open(file_path, mode='r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader):
                    # Mend CSV column names can vary based on report type.
                    # Commonly: Library, CVE, Severity, Vulnerability Score, Top Fix
                    library = row.get("Library", "Unknown Library")
                    cve = row.get("CVE", "Unknown CVE")
                    severity_str = row.get("Severity", "LOW")
                    description = row.get("Description", "No description")
                    top_fix = row.get("Top Fix", "No fix available")
                    
                    message = f"{library} has vulnerability {cve} ({severity_str}). {description}. Fix: {top_fix}"
                    
                    finding = Finding(
                        id=f"{cve}-{i}", # Generate a unique ID if one isn't provided
                        source_tool=ToolSource.MEND,
                        issue_type=IssueType.VULNERABILITY,
                        severity=self._map_severity(severity_str),
                        file_path="package.json", # Usually dependency findings apply to manifest files
                        line=None,
                        message=message,
                        rule_id=cve,
                        raw_data=row
                    )
                    findings.append(finding)
        except Exception as e:
            logger.error("Error reading Mend CSV file", file_path=str(file_path), error=str(e))

        logger.info("Finished parsing Mend CSV", total_findings=len(findings))
        return findings
