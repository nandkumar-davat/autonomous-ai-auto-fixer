"""Web search tool placeholder that delegates research queries to an LLM."""

from typing import Any, Dict, Optional, Protocol

from structlog import get_logger

from autofixer.tools.base import BaseTool

logger = get_logger()


class LLMProvider(Protocol):
    """Minimal protocol that any LLM client must satisfy."""

    def generate_fix(self, context: str, message: str, issue_type: str) -> Optional[str]:
        ...


class WebSearchTool(BaseTool):
    """Answers research questions about libraries, APIs, and best practices.

    This is a *placeholder* implementation that sends the query to the
    configured LLM provider rather than performing a real web search.
    It is useful for looking up upgrade guides, API changes, and
    migration notes during automated remediation.

    Parameters
    ----------
    llm_provider:
        An object that exposes a ``generate_fix`` method (e.g.
        :class:`autofixer.remediation.llm_client.LLMClient`).
    """

    name: str = "web_search"
    description: str = (
        "Answer research questions about libraries, frameworks, and APIs "
        "by querying the LLM. Useful for upgrade guides and migration notes."
    )

    def __init__(self, llm_provider: LLMProvider) -> None:
        self.llm_provider = llm_provider

    # ------------------------------------------------------------------
    # BaseTool interface
    # ------------------------------------------------------------------

    def execute(
        self,
        *,
        query: str,
        context: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Send a research *query* to the LLM and return the answer.

        Parameters
        ----------
        query:
            The research question (e.g. "How to upgrade lodash from 4.17.15
            to 4.17.21?").
        context:
            Optional additional context to include in the prompt.
        """
        logger.info("web_search.execute", query=query)

        prompt_context = context or "No additional context provided."
        research_prompt = (
            f"Research the following question and provide a detailed, accurate answer.\n\n"
            f"QUESTION:\n{query}\n\n"
            f"CONTEXT:\n{prompt_context}\n\n"
            f"Provide specific version numbers, code examples, and migration steps "
            f"where applicable."
        )

        try:
            answer = self.llm_provider.generate_fix(
                context=research_prompt,
                message=query,
                issue_type="research",
            )
            if answer is None:
                return {
                    "success": False,
                    "result": None,
                    "error": "LLM returned no answer for the query.",
                }
            return {"success": True, "result": answer}
        except Exception as exc:
            logger.error("web_search.failed", query=query, error=str(exc))
            return {"success": False, "result": None, "error": str(exc)}
