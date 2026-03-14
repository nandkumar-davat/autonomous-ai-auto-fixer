import pytest
import json
from pathlib import Path
from autofixer.ingestion.trivy.file_parser import TrivyFileParser
from autofixer.models.enums import ToolSource, Severity

def test_trivy_json_parser(tmp_path):
    trivy_data = {
        "Results": [
            {
                "Target": "alpine:3.15",
                "Vulnerabilities": [
                    {
                        "VulnerabilityID": "CVE-2022-0001",
                        "PkgName": "ssl",
                        "InstalledVersion": "1.0",
                        "FixedVersion": "1.1",
                        "Severity": "CRITICAL"
                    }
                ]
            }
        ]
    }
    json_file = tmp_path / "trivy.json"
    json_file.write_text(json_encode := json.dumps(trivy_data))
    
    parser = TrivyFileParser()
    findings = parser.parse_file(json_file)
    
    assert len(findings) == 1
    assert findings[0].id == "CVE-2022-0001-ssl"
    assert findings[0].severity == Severity.CRITICAL
    assert findings[0].source_tool == ToolSource.TRIVY

def test_trivy_sarif_parser(tmp_path):
    sarif_data = {
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "Trivy",
                        "rules": [{"id": "CVE-X"}]
                    }
                },
                "results": [
                    {
                        "ruleId": "CVE-X",
                        "message": {"text": "Bug description"},
                        "level": "error",
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": "Dockerfile"},
                                    "region": {"startLine": 1}
                                }
                            }
                        ]
                    }
                ]
            }
        ]
    }
    sarif_file = tmp_path / "trivy.sarif"
    sarif_file.write_text(json.dumps(sarif_data))
    
    parser = TrivyFileParser()
    findings = parser.parse_file(sarif_file)
    
    assert len(findings) == 1
    assert findings[0].id == "CVE-X-Dockerfile"
    assert findings[0].severity == Severity.CRITICAL
    assert findings[0].file_path == "Dockerfile"
