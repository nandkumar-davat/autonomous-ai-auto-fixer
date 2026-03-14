from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from autofixer.models.enums import ToolSource, Severity, IssueType, RiskLevel, ApprovalStatus

class Finding(BaseModel):
    id: str = Field(..., description="Unique identifier for the finding (e.g., SonarQube key)")
    source_tool: ToolSource
    issue_type: IssueType
    severity: Severity
    file_path: str
    line: Optional[int] = None
    message: str
    rule_id: str
    risk_level: RiskLevel = RiskLevel.HIGH  # Default to high for safety
    priority_rank: int = 99  # Lower is higher priority
    approval_status: ApprovalStatus = ApprovalStatus.PENDING_APPROVAL
    raw_data: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True

class RemediationResult(BaseModel):
    finding: Finding
    original_code: str
    fixed_code: Optional[str] = None
    applied: bool = False
    validation_passed: bool = False
    llm_prompt_used: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
