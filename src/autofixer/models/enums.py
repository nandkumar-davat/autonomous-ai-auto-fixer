from enum import Enum

class IssueType(str, Enum):
    BUG = "BUG"
    VULNERABILITY = "VULNERABILITY"
    CODE_SMELL = "CODE_SMELL"
    SECURITY_HOTSPOT = "SECURITY_HOTSPOT"

class Severity(str, Enum):
    BLOCKER = "BLOCKER"
    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    HIGH = "HIGH"
    MINOR = "MINOR"
    INFO = "INFO"

class RiskLevel(str, Enum):
    LOW = "LOW"
    HIGH = "HIGH"

class ToolSource(str, Enum):
    SONARQUBE = "SONARQUBE"
    MEND = "MEND"
    TRIVY = "TRIVY"

class AgentMode(str, Enum):
    DRY_RUN = "DRY_RUN"
    FIX = "FIX"

class ApprovalStatus(str, Enum):
    AUTO_APPROVED = "AUTO_APPROVED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    USER_APPROVED = "USER_APPROVED"
    USER_REJECTED = "USER_REJECTED"
