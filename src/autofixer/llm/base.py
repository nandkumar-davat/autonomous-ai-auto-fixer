from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from pydantic import BaseModel
from structlog import get_logger

logger = get_logger()


class LLMMessage(BaseModel):
    """A single message in an LLM conversation."""

    role: str  # 'system', 'user', 'assistant'
    content: str


class LLMResponse(BaseModel):
    """Structured response from an LLM provider."""

    content: str
    model: str
    provider: str
    usage: Dict[str, int] = {}


class BaseLLMProvider(ABC):
    """Abstract base class for all LLM providers."""

    provider_name: str

    @abstractmethod
    def generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> Optional[LLMResponse]:
        """Generate a response from the LLM.

        Args:
            messages: List of conversation messages.
            temperature: Sampling temperature (0.0 = deterministic).
            max_tokens: Maximum tokens in the response.

        Returns:
            An LLMResponse on success, or None on failure.
        """
        ...

    def generate_fix(
        self, context: str, message: str, issue_type: str
    ) -> Optional[str]:
        """Generate a code fix using the standard fix prompt.

        Builds a prompt identical to the legacy LLMClient pattern,
        calls self.generate(), and returns only the cleaned-up code.

        Args:
            context: The code snippet that needs fixing.
            message: The finding / issue description.
            issue_type: Category of the issue (e.g. 'security', 'bug').

        Returns:
            The fixed code as a string, or None on failure.
        """
        logger.info(
            "Generating fix via LLM",
            provider=self.provider_name,
            type=issue_type,
        )

        prompt = f"""
You are an expert software engineer specializing in security and code quality.
You are tasked with fixing a {issue_type} in the following code snippet.

FINDING MESSAGE:
{message}

CODE CONTEXT:
```
{context}
```

INSTRUCTIONS:
1. Analyze the finding and the code.
2. Provide ONLY the corrected code for the snippet provided.
3. Do not include any explanations or markdown formatting other than the code itself.
4. Ensure the fix follows best practices and doesn't introduce new issues.

FIXED CODE:
"""

        messages = [LLMMessage(role="user", content=prompt)]
        response = self.generate(messages, temperature=0.0, max_tokens=2048)

        if response is None:
            logger.warning(
                "LLM returned no response for fix",
                provider=self.provider_name,
                type=issue_type,
            )
            return None

        fixed_code = response.content.strip()
        fixed_code = self._strip_markdown_fences(fixed_code)
        return fixed_code

    @staticmethod
    def _strip_markdown_fences(code: str) -> str:
        """Remove markdown code fences from LLM output."""
        if "```" not in code:
            return code

        parts = code.split("```")
        if len(parts) < 3:
            # Only one fence marker – take everything after it
            inner = parts[1].strip()
        else:
            # Take the content between the first pair of fences
            inner = parts[1].strip()

        # Strip optional language identifier on the first line
        lines = inner.split("\n")
        first_line = lines[0].strip().lower()
        language_ids = {
            "python",
            "javascript",
            "typescript",
            "java",
            "go",
            "ruby",
            "rust",
            "c",
            "cpp",
            "csharp",
            "cs",
            "sh",
            "bash",
            "yaml",
            "json",
            "xml",
            "html",
            "css",
            "sql",
            "py",
            "js",
            "ts",
        }
        if first_line in language_ids:
            lines = lines[1:]

        return "\n".join(lines).strip()
