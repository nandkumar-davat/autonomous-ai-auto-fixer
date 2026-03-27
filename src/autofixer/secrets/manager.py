import os
from typing import Optional
from autofixer.secrets.keyvault import KeyVaultManager
from structlog import get_logger

logger = get_logger()

class SecretsManager:
    """Unified secrets manager supporting multiple sources."""

    def __init__(self, config):
        self.config = config
        self.source = config.secrets.source
        
        if self.source == "azure-keyvault":
            if not config.secrets.vault_url:
                raise ValueError("vault_url is required for azure-keyvault source")
            self.keyvault = KeyVaultManager(config.secrets.vault_url)
        else:
            self.keyvault = None

    def get_github_token(self) -> Optional[str]:
        """Get GitHub token from configured source."""
        if self.source == "environment":
            token = os.getenv("GITHUB_TOKEN")
            if token:
                logger.info("GitHub token loaded from environment variable")
                return token
            else:
                logger.warning("GITHUB_TOKEN environment variable not found")
                return None
        
        elif self.source == "azure-keyvault":
            if not self.keyvault:
                logger.error("KeyVault not initialized")
                return None
            
            token = self.keyvault.get_secret(self.config.secrets.github_token_secret_name)
            if token:
                logger.info("GitHub token loaded from Azure Key Vault")
                return token
            else:
                logger.warning("GitHub token not found in Key Vault", 
                             secret_name=self.config.secrets.github_token_secret_name)
                return None
        
        else:
            logger.error("Unknown secrets source", source=self.source)
            return None

    def get_azure_devops_token(self) -> Optional[str]:
        """Get Azure DevOps PAT from configured source."""
        if self.source == "environment":
            return os.getenv("AZURE_DEVOPS_TOKEN")
        elif self.source == "azure-keyvault" and self.keyvault:
            return self.keyvault.get_secret("azure-devops-token")
        return None