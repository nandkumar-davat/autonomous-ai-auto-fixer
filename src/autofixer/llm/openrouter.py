import os
from typing import List, Optional

from structlog import get_logger

from autofixer.llm.base import BaseLLMProvider, LLMMessage, LLMResponse

logger = get_logger()


class OpenRouterProvider(BaseLLMProvider):
    """LLM provider using the OpenRouter API (OpenAI-compatible)."""

    provider_name: str = "openrouter"

    def __init__(
        self,
        model: str = "meta-llama/llama-3.1-8b-instruct:free",
        api_key: Optional[str] = None,
        base_url: str = "https://openrouter.ai/api/v1",
    ) -> None:
        self.model = model
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self.base_url = base_url

        if not self.api_key:
            logger.warning(
                "OPENROUTER_API_KEY not set – OpenRouter provider will fail"
            )

        try:
            from openai import OpenAI

            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        except Exception as exc:
            logger.error(
                "Failed to initialise OpenRouter client",
                error=str(exc),
            )
            self.client = None  # type: ignore[assignment]

    def generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> Optional[LLMResponse]:
        """Generate a response using the OpenRouter API."""
        if self.client is None:
            logger.error("OpenRouter client is not initialised")
            return None

        logger.info(
            "Calling OpenRouter",
            model=self.model,
            message_count=len(messages),
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": m.role, "content": m.content} for m in messages
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )

            choice = response.choices[0]
            usage = {}
            if response.usage:
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }

            return LLMResponse(
                content=choice.message.content or "",
                model=response.model or self.model,
                provider=self.provider_name,
                usage=usage,
            )
        except Exception as exc:
            logger.error(
                "OpenRouter generation failed",
                error=str(exc),
                model=self.model,
            )
            return None
