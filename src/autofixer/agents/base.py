"""Base agent class for the autofixer multi-agent system.

All specialised agents (Auditor, TeamLead, Fixer, Verifier) inherit from
``BaseAgent`` which provides shared LLM interaction helpers, structured
JSON extraction, and consistent logging via *structlog*.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from structlog import get_logger

from autofixer.agents.prompts.loader import load_prompt
from autofixer.llm.base import BaseLLMProvider, LLMMessage, LLMResponse


class BaseAgent:
    """Foundation for every agent in the pipeline.

    Parameters
    ----------
    name:
        Human-readable agent identifier used in logs and metrics.
    llm_provider:
        An ``BaseLLMProvider`` instance (or ``FallbackLLMProvider``)
        used for all LLM interactions within the agent.
    config:
        Arbitrary configuration object/dict passed from the
        orchestrator.  Each sub-class interprets its own keys.
    """

    def __init__(
        self,
        name: str,
        llm_provider: BaseLLMProvider,
        config: Any = None,
    ) -> None:
        self.name = name
        self.llm_provider = llm_provider
        self.config = config or {}
        self.logger = get_logger().bind(agent=name)

    # ------------------------------------------------------------------
    # LLM helpers
    # ------------------------------------------------------------------

    def _load_system_prompt(self, agent_key: str) -> str:
        """Load the Markdown system prompt for *agent_key*.

        Delegates to ``agents.prompts.loader.load_prompt`` and logs
        on failure so calling code can decide how to proceed.
        """
        try:
            return load_prompt(agent_key)
        except (ValueError, FileNotFoundError) as exc:
            self.logger.warning(
                "Failed to load system prompt – falling back to empty",
                agent_key=agent_key,
                error=str(exc),
            )
            return ""

    def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> Optional[str]:
        """Send a system + user message pair to the LLM provider.

        Returns the assistant's text content on success, or ``None``
        when the provider returns no response.
        """
        messages: List[LLMMessage] = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt),
        ]
        try:
            response: Optional[LLMResponse] = self.llm_provider.generate(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if response is None:
                self.logger.warning("LLM returned no response")
                return None
            return response.content
        except Exception as exc:
            self.logger.error(
                "LLM call failed",
                error=str(exc),
                exc_info=True,
            )
            return None

    # ------------------------------------------------------------------
    # JSON extraction
    # ------------------------------------------------------------------

    def _parse_json_response(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract a JSON object from an LLM response string.

        The method tries, in order:

        1. Content between ``````json … `````` fences.
        2. Content between bare ````` … ````` fences.
        3. Direct ``json.loads`` on the entire *text*.

        Returns ``None`` if no valid JSON object can be found.
        """
        if not text:
            return None

        # 1. Try ```json ... ``` fences
        fenced = re.search(
            r"```json\s*\n?(.*?)```",
            text,
            re.DOTALL,
        )
        if fenced:
            try:
                return json.loads(fenced.group(1).strip())
            except json.JSONDecodeError:
                pass

        # 2. Try bare ``` ... ``` fences
        bare = re.search(r"```\s*\n?(.*?)```", text, re.DOTALL)
        if bare:
            try:
                return json.loads(bare.group(1).strip())
            except json.JSONDecodeError:
                pass

        # 3. Try the whole text directly
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        # 4. Last resort: find the first { … } block
        brace = re.search(r"\{.*\}", text, re.DOTALL)
        if brace:
            try:
                return json.loads(brace.group(0))
            except json.JSONDecodeError:
                pass

        self.logger.warning(
            "Could not parse JSON from LLM response",
            text_preview=text[:200],
        )
        return None

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{self.__class__.__name__} name={self.name!r}>"
