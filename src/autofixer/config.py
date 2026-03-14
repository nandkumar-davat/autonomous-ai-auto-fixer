import os
import yaml
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

class AgentConfig(BaseModel):
    mode: str = "dry-run"
    max_retries: int = 3
    risk_policy: str = "low-risk-only"
    base_branch: str = "main"

class AzureDevOpsConfig(BaseModel):
    org_url: Optional[str] = None
    project: Optional[str] = None

class GitHubConfig(BaseModel):
    app_id: Optional[int] = None
    installation_id: Optional[int] = None

class VCSConfig(BaseModel):
    primary: str = "azure-devops"
    azure_devops: AzureDevOpsConfig = Field(default_factory=AzureDevOpsConfig)
    github: GitHubConfig = Field(default_factory=GitHubConfig)

class LLMConfig(BaseModel):
    provider: str = "github-copilot"
    model: str = "auto"
    temperature: float = 0.0
    max_tokens: int = 4096

class SecretConfig(BaseModel):
    source: str = "azure-keyvault"
    vault_url: Optional[str] = None
    tenant_id: Optional[str] = None

class Config(BaseModel):
    agent: AgentConfig = Field(default_factory=AgentConfig)
    vcs: VCSConfig = Field(default_factory=VCSConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    secrets: SecretConfig = Field(default_factory=SecretConfig)
    remediation: Dict[str, Any] = Field(default_factory=dict)
    ingestion: Dict[str, Any] = Field(default_factory=dict)
    validation: Dict[str, Any] = Field(default_factory=dict)

def load_config(config_path: str = "config/default.yaml") -> Config:
    """Loads configuration from YAML and environment variables."""
    # Load defaults from YAML if it exists
    data = {}
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            data = yaml.safe_load(f) or {}

    # Override with environment variables (simplified for now)
    # Prefix: AUTOFIXER_
    # Example: AUTOFIXER_AGENT_MODE -> data['agent']['mode']
    for key, value in os.environ.items():
        if key.startswith("AUTOFIXER_"):
            parts = key.replace("AUTOFIXER_", "").lower().split("_")
            current = data
            for part in parts[:-1]:
                current = current.setdefault(part, {})
            current[parts[-1]] = value

    return Config(**data)

# Singleton instance
config = load_config()
