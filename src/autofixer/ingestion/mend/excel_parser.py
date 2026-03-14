import pandas as pd
from typing import List
from pathlib import Path
from structlog import get_logger
from autofixer.models.finding import Finding
from autofixer.models.enums import ToolSource, IssueType, Severity

logger = get_logger()

class MendExcelParser:
    """Parser for Mend Excel (.xlsx) reports."""

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
        """Parses a Mend Excel file and returns findings."""
        logger.info("Parsing Mend Excel file", file_path=str(file_path))
        findings = []

        if not file_path.exists():
            logger.error("File does not exist", file_path=str(file_path))
            return []

        try:
            # Requires openpyxl and pandas
            df = pd.read_excel(file_path, engine="openpyxl")
            
            # Mend Excel reports usually have specific sheets or column names
            # Adjust mapping based on actual typical report format
            columns = df.columns
            
            for i, row in df.iterrows():
                # Try to find standard columns, fallback to defaults
                library = row.get("Library", row.get("File", "Unknown Library"))
                cve = row.get("CVE", "Unknown CVE")
                severity_str = row.get("Severity", "LOW")
                description = row.get("Description", "No description")
                top_fix = row.get("Top Fix", "No fix available")
                
                message = f"{library} has vulnerability {cve} ({severity_str}). {description}. Fix: {top_fix}"
                
                finding = Finding(
                    id=f"{cve}-{i}", 
                    source_tool=ToolSource.MEND,
                    issue_type=IssueType.VULNERABILITY,
                    severity=self._map_severity(severity_str),
                    file_path="package.json", # Usually manifest files
                    line=None,
                    message=message,
                    rule_id=cve,
                    raw_data=row.to_dict()
                )
                findings.append(finding)
        except Exception as e:
            logger.error("Error reading Mend Excel file", file_path=str(file_path), error=str(e))

        logger.info("Finished parsing Mend Excel", total_findings=len(findings))
        return findings
