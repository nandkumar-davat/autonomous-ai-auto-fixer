import json
from typing import List
from pathlib import Path
from structlog import get_logger
from autofixer.models.finding import Finding
from autofixer.models.enums import ToolSource, IssueType, Severity

logger = get_logger()

class MendJSONParser:
    """Parser for Mend JSON API response files."""

    def __init__(self):
        pass

    def parse_file(self, file_path: Path) -> List[Finding]:
        """Parses a Mend JSON report file."""
        logger.info("Parsing Mend JSON file", file_path=str(file_path))
        findings = []

        if not file_path.exists():
            logger.error("File does not exist", file_path=str(file_path))
            return []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            alerts = data.get('alerts', [])
            logger.debug("Processing Mend alerts", alert_count=len(alerts))

            for alert in alerts:
                try:
                    finding = self._parse_alert(alert)
                    findings.append(finding)
                    logger.debug("Parsed vulnerability", 
                               vuln_id=finding.id, 
                               severity=finding.severity,
                               library=alert.get('libraryName'))
                except Exception as e:
                    logger.warning("Failed to parse alert", 
                                 alert_id=alert.get('vulnerabilityId'), 
                                 error=str(e))

        except json.JSONDecodeError as e:
            logger.error("Invalid JSON format", file_path=str(file_path), error=str(e))
        except Exception as e:
            logger.error("Error parsing Mend JSON file", file_path=str(file_path), error=str(e))

        logger.info("Finished parsing Mend JSON", total_findings=len(findings))
        return findings

    def _parse_alert(self, alert: dict) -> Finding:
        """Converts a Mend alert to a Finding object."""
        vulnerability_id = alert.get('vulnerabilityId', 'unknown')
        library_name = alert.get('libraryName', 'unknown')
        severity_str = alert.get('severity', 'MEDIUM').upper()
        cvss_score = alert.get('cvssScore', '0.0')
        project = alert.get('project', 'unknown')
        
        # Map Mend severity to our enum
        severity = self._map_severity(severity_str)
        
        # Extract fix information
        top_fix = alert.get('topFix', {})
        fix_resolution = top_fix.get('fixResolution', 'No fix available')
        fix_url = top_fix.get('url', '')
        
        # Create descriptive message
        message = f"Vulnerability {vulnerability_id} in {library_name} (CVSS: {cvss_score})"
        if fix_resolution:
            message += f". Fix: {fix_resolution}"
        
        # Determine file path based on library type
        library_type = alert.get('libraryType', '').lower()
        file_path = self._determine_file_path(library_type, library_name, project)
        
        return Finding(
            id=vulnerability_id,
            source_tool=ToolSource.MEND,
            issue_type=IssueType.VULNERABILITY,
            severity=severity,
            file_path=file_path,
            line=None,  # JSON reports don't have line numbers
            message=message,
            rule_id=vulnerability_id,
            raw_data={
                'alert': alert,
                'library_name': library_name,
                'cvss_score': cvss_score,
                'fix_resolution': fix_resolution,
                'fix_url': fix_url,
                'project': project,
                'library_type': alert.get('libraryType'),
                'confidence_score': alert.get('confidenceScore'),
                'exploit_available': alert.get('exploitAvailable')
            }
        )

    def _map_severity(self, mend_severity: str) -> Severity:
        """Maps Mend severity levels to our Severity enum."""
        severity_mapping = {
            'CRITICAL': Severity.CRITICAL,
            'HIGH': Severity.HIGH,
            'MEDIUM': Severity.MAJOR,
            'LOW': Severity.MINOR,
            'INFO': Severity.INFO
        }
        return severity_mapping.get(mend_severity.upper(), Severity.MAJOR)

    def _determine_file_path(self, library_type: str, library_name: str, project: str) -> str:
        """Determines the likely file path based on library type and name."""
        if library_type == 'nuget':
            # .NET NuGet packages
            if 'packages.config' in project.lower():
                return 'packages.config'
            else:
                return f"{project}.csproj"
        elif library_type == 'npm':
            return 'package.json'
        elif library_type == 'maven':
            return 'pom.xml'
        elif library_type == 'pip':
            return 'requirements.txt'
        elif library_type == 'gradle':
            return 'build.gradle'
        else:
            # Generic fallback based on library name
            if 'csproj' in library_name.lower() or '.nupkg' in library_name.lower():
                return f"{project}.csproj"
            else:
                return f"dependencies-{library_type}"