from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from structlog import get_logger
from typing import Optional

logger = get_logger()

class KeyVaultManager:
    """Manages retrieval of secrets from Azure Key Vault."""

    def __init__(self, vault_url: str):
        self.vault_url = vault_url
        self.credential = DefaultAzureCredential()
        self.client = SecretClient(vault_url=vault_url, credential=self.credential)

    def get_secret(self, secret_name: str) -> Optional[str]:
        """Retrieves a secret from the vault."""
        try:
            logger.info("Retrieving secret from Key Vault", name=secret_name)
            secret = self.client.get_secret(secret_name)
            return secret.value
        except Exception as e:
            logger.error("Failed to retrieve secret", name=secret_name, error=str(e))
            return None

    def get_all_required_secrets(self, secret_names: list[str]) -> dict[str, str]:
        """Retrieves multiple secrets at once."""
        secrets = {}
        for name in secret_names:
            value = self.get_secret(name)
            if value:
                secrets[name] = value
        return secrets
