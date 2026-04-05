from typing import List, Optional

from structlog import get_logger

from autofixer.llm.base import BaseLLMProvider, LLMMessage, LLMResponse

logger = get_logger()


class OllamaProvider(BaseLLMProvider):
    """LLM provider using a local Ollama instance (OpenAI-compatible)."""

    provider_name: str = "ollama"

    def __init__(
        self,
        model: str = "llama3.1",
        base_url: str = "http://localhost:11434/v1",
    ) -> None:
        self.model = model
        self.base_url = base_url

        try:
            from openai import OpenAI

            self.client = OpenAI(
                api_key="ollama",  # dummy key; Ollama ignores it
                base_url=self.base_url,
            )
        except Exception as exc:
            logger.error(
                "Failed to initialise Ollama client",
                error=str(exc),
            )
            self.client = None  # type: ignore[assignment]

    def generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> Optional[LLMResponse]:
        """Generate a response using a local Ollama instance."""
        if self.client is None:
            logger.error("Ollama client is not initialised")
            return None

        logger.info(
            "Calling Ollama",
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
                "Ollama generation failed",
                error=str(exc),
                model=self.model,
            )
            return None
