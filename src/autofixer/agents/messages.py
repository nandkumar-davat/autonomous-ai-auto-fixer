"""Agent message models for the autofixer pipeline.

These Pydantic models define the structured messages passed between
pipeline stages: audit planning, fix consolidation, fix application,
and verification.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class FixStrategy(str, Enum):
    VERSION_BUMP = "version_bump"
    CODE_PATCH = "code_patch"
    CONFIG_CHANGE = "config_change"
    DOCKERFILE_UPDATE = "dockerfile_update"
    LLM_ASSISTED = "llm_assisted"


class ProposedFix(BaseModel):
    finding_id: str
    file_path: str
    strategy: FixStrategy
    description: str
    confidence: float = 0.0  # 0.0-1.0
    suggested_change: Optional[str] = None
    metadata: Dict[str, Any] = {}


class AuditPlan(BaseModel):
    scanner_type: str  # 'mend', 'trivy', 'sonarqube'
    total_findings: int
    filtered_findings: int
    proposed_fixes: List[ProposedFix]
    skipped_findings: List[Dict[str, Any]] = []
    summary: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ConsolidatedFix(BaseModel):
    file_path: str
    fixes: List[ProposedFix]  # All fixes targeting this file
    priority: int  # Lower = higher priority
    has_conflicts: bool = False
    resolution_notes: Optional[str] = None


class ConsolidatedPlan(BaseModel):
    total_fixes: int
    files_affected: int
    consolidated_fixes: List[ConsolidatedFix]
    deduplication_notes: List[str] = []
    conflict_resolutions: List[str] = []
    summary: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class FileFixResult(BaseModel):
    file_path: str
    success: bool
    finding_ids: List[str]
    diff: Optional[str] = None
    error: Optional[str] = None
    lint_passed: bool = False
    retries: int = 0


class FixResult(BaseModel):
    branch_name: str
    total_fixes_attempted: int
    total_fixes_applied: int
    file_results: List[FileFixResult]
    pr_url: Optional[str] = None
    commit_sha: Optional[str] = None
    summary: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class VerificationCheck(BaseModel):
    check_name: str
    passed: bool
    details: str


class VerificationReport(BaseModel):
    total_checks: int
    passed_checks: int
    failed_checks: int
    checks: List[VerificationCheck]
    regressions_found: List[str] = []
    overall_status: str  # 'PASS', 'FAIL', 'PARTIAL'
    summary: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
