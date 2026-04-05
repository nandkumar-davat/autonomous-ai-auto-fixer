import os
from typing import List, Optional

from structlog import get_logger

from autofixer.llm.base import BaseLLMProvider, LLMMessage, LLMResponse

logger = get_logger()


class GeminiProvider(BaseLLMProvider):
    """LLM provider using the Google Gemini (Generative AI) API."""

    provider_name: str = "gemini"

    def __init__(
        self,
        model: str = "gemini-2.0-flash",
        api_key: Optional[str] = None,
    ) -> None:
        self.model = model
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")

        if not self.api_key:
            logger.warning(
                "GEMINI_API_KEY not set – Gemini provider will fail"
            )

        try:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            self._genai = genai
        except Exception as exc:
            logger.error(
                "Failed to initialise Gemini client",
                error=str(exc),
            )
            self._genai = None  # type: ignore[assignment]

    def generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> Optional[LLMResponse]:
        """Generate a response using the Google Gemini API."""
        if self._genai is None:
            logger.error("Gemini client is not initialised")
            return None

        logger.info(
            "Calling Gemini",
            model=self.model,
            message_count=len(messages),
        )

        try:
            model = self._genai.GenerativeModel(
                model_name=self.model,
                generation_config=self._genai.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
            )

            # Build Gemini-compatible message history.
            # Gemini expects a flat list where system messages are
            # prepended to the first user message.
            system_parts: list[str] = []
            history: list[dict[str, str]] = []
            for msg in messages:
                if msg.role == "system":
                    system_parts.append(msg.content)
                elif msg.role == "user":
                    content = msg.content
                    if system_parts:
                        content = (
                            "\n\n".join(system_parts) + "\n\n" + content
                        )
                        system_parts = []
                    history.append({"role": "user", "parts": [content]})
                elif msg.role == "assistant":
                    history.append(
                        {"role": "model", "parts": [msg.content]}
                    )

            # If only system messages remain with no user message, wrap them
            if system_parts and not history:
                history.append(
                    {
                        "role": "user",
                        "parts": ["\n\n".join(system_parts)],
                    }
                )

            response = model.generate_content(
                history if len(history) > 1 else history[0]["parts"][0]
            )

            usage = {}
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                meta = response.usage_metadata
                usage = {
                    "prompt_tokens": getattr(
                        meta, "prompt_token_count", 0
                    ),
                    "completion_tokens": getattr(
                        meta, "candidates_token_count", 0
                    ),
                    "total_tokens": getattr(
                        meta, "total_token_count", 0
                    ),
                }

            return LLMResponse(
                content=response.text,
                model=self.model,
                provider=self.provider_name,
                usage=usage,
            )
        except Exception as exc:
            logger.error(
                "Gemini generation failed",
                error=str(exc),
                model=self.model,
            )
            return None
