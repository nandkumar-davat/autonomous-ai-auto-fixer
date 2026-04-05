from typing import Any, Dict, List, Optional, Type

from structlog import get_logger

from autofixer.llm.base import BaseLLMProvider, LLMMessage, LLMResponse

logger = get_logger()


class FallbackLLMProvider(BaseLLMProvider):
    """Meta-provider that tries a chain of providers in order.

    On each call to ``generate()``, providers are attempted sequentially.
    The first successful (non-None) response is returned.  If every
    provider fails, ``None`` is returned.
    """

    provider_name: str = "fallback"

    def __init__(self, providers: List[BaseLLMProvider]) -> None:
        if not providers:
            raise ValueError(
                "FallbackLLMProvider requires at least one provider"
            )
        self.providers = providers
        names = [p.provider_name for p in providers]
        logger.info("Fallback chain initialised", providers=names)

    def generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> Optional[LLMResponse]:
        """Try each provider in order until one succeeds."""
        for provider in self.providers:
            logger.debug(
                "Attempting provider in fallback chain",
                provider=provider.provider_name,
            )
            response = provider.generate(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if response is not None:
                logger.info(
                    "Fallback chain succeeded",
                    provider=provider.provider_name,
                )
                return response
            logger.warning(
                "Provider failed, trying next in chain",
                failed_provider=provider.provider_name,
            )

        logger.error("All providers in fallback chain failed")
        return None


class LLMProviderFactory:
    """Factory for creating LLM provider instances by name."""

    _registry: Dict[str, Type[BaseLLMProvider]] = {}

    @classmethod
    def _ensure_registry(cls) -> None:
        """Lazily populate the provider registry on first access."""
        if cls._registry:
            return

        from autofixer.llm.gemini import GeminiProvider
        from autofixer.llm.github_copilot import GitHubCopilotProvider
        from autofixer.llm.ollama import OllamaProvider
        from autofixer.llm.openrouter import OpenRouterProvider

        cls._registry = {
            "github_copilot": GitHubCopilotProvider,
            "gemini": GeminiProvider,
            "openrouter": OpenRouterProvider,
            "ollama": OllamaProvider,
        }

    @classmethod
    def register(
        cls, name: str, provider_class: Type[BaseLLMProvider]
    ) -> None:
        """Register a custom provider class under *name*."""
        cls._ensure_registry()
        cls._registry[name] = provider_class
        logger.info("Registered LLM provider", name=name)

    @classmethod
    def available_providers(cls) -> List[str]:
        """Return the names of all registered providers."""
        cls._ensure_registry()
        return list(cls._registry.keys())

    @classmethod
    def create_provider(
        cls, provider_name: str, **kwargs: Any
    ) -> BaseLLMProvider:
        """Instantiate a provider by its registered name.

        Args:
            provider_name: Key used when the provider was registered
                (e.g. ``"gemini"``, ``"ollama"``).
            **kwargs: Forwarded to the provider constructor.

        Returns:
            A ready-to-use ``BaseLLMProvider`` instance.

        Raises:
            ValueError: If *provider_name* is not in the registry.
        """
        cls._ensure_registry()

        provider_class = cls._registry.get(provider_name)
        if provider_class is None:
            available = ", ".join(sorted(cls._registry.keys()))
            raise ValueError(
                f"Unknown LLM provider '{provider_name}'. "
                f"Available providers: {available}"
            )

        logger.info(
            "Creating LLM provider",
            provider=provider_name,
            kwargs=list(kwargs.keys()),
        )
        return provider_class(**kwargs)

    @classmethod
    def create_fallback_chain(
        cls, provider_names: List[str], **kwargs: Any
    ) -> FallbackLLMProvider:
        """Create a ``FallbackLLMProvider`` from an ordered list of names.

        Each provider is instantiated via ``create_provider()``; any
        *kwargs* are forwarded to every constructor.

        Args:
            provider_names: Ordered list of provider names to try.
            **kwargs: Forwarded to each provider constructor.

        Returns:
            A ``FallbackLLMProvider`` wrapping the requested chain.
        """
        providers: List[BaseLLMProvider] = []
        for name in provider_names:
            try:
                provider = cls.create_provider(name, **kwargs)
                providers.append(provider)
            except Exception as exc:
                logger.warning(
                    "Skipping provider in fallback chain",
                    provider=name,
                    error=str(exc),
                )

        if not providers:
            raise ValueError(
                "No providers could be initialised for the fallback chain"
            )

        return FallbackLLMProvider(providers=providers)
