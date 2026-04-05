import os
from typing import List, Optional

from structlog import get_logger

from autofixer.llm.base import BaseLLMProvider, LLMMessage, LLMResponse

logger = get_logger()


class GitHubCopilotProvider(BaseLLMProvider):
    """LLM provider using GitHub Copilot's OpenAI-compatible API."""

    provider_name: str = "github_copilot"

    def __init__(
        self,
        model: str = "auto",
        api_key: Optional[str] = None,
        base_url: str = "https://models.inference.ai.azure.com",
    ) -> None:
        # "auto" lets the backend select the best available model
        self.model = model if model != "auto" else "gpt-4o"
        self.api_key = api_key or os.environ.get("GITHUB_TOKEN", "")
        self.base_url = base_url

        if not self.api_key:
            logger.warning(
                "GITHUB_TOKEN not set – GitHub Copilot provider will fail"
            )

        try:
            from openai import OpenAI

            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        except Exception as exc:
            logger.error(
                "Failed to initialise GitHub Copilot client",
                error=str(exc),
            )
            self.client = None  # type: ignore[assignment]

    def generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> Optional[LLMResponse]:
        """Generate a response using the GitHub Copilot API."""
        if self.client is None:
            logger.error("GitHub Copilot client is not initialised")
            return None

        logger.info(
            "Calling GitHub Copilot",
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
                "GitHub Copilot generation failed",
                error=str(exc),
                model=self.model,
            )
            return None
