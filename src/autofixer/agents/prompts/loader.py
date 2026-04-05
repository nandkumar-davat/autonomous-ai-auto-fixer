"""Prompt loader for agent system prompts.

Reads Markdown-based system prompt files from the prompts directory
and returns their content as strings for use by the multi-agent system.
"""

from pathlib import Path
from functools import lru_cache
from structlog import get_logger

logger = get_logger()

# Directory containing the .md prompt files (same directory as this module)
_PROMPTS_DIR = Path(__file__).parent

# Valid agent names that have corresponding prompt files
_VALID_AGENTS = frozenset({"auditor", "team_lead", "fixer", "verifier"})

# Scanner-specific fixer prompt files
_SCANNER_FIXERS = frozenset({"mend_security_fixer", "trivy_security_fixer", "sonarqube_issue_fixer"})


def load_prompt(agent_name: str) -> str:
    """Load the system prompt for a given agent.

    Reads the corresponding `.md` file from the prompts directory and
    returns its content as a string.

    Args:
        agent_name: The name of the agent whose prompt to load.
            Must be one of: ``auditor``, ``team_lead``, ``fixer``, ``verifier``,
            or a scanner-specific fixer: ``mend_security_fixer``, ``trivy_security_fixer``, ``sonarqube_issue_fixer``.

    Returns:
        The full text of the agent's system prompt.

    Raises:
        ValueError: If ``agent_name`` is not a recognised agent.
        FileNotFoundError: If the prompt file does not exist on disk.
    """
    valid_names = _VALID_AGENTS | _SCANNER_FIXERS
    if agent_name not in valid_names:
        raise ValueError(
            f"Unknown agent name '{agent_name}'. "
            f"Valid agents are: {', '.join(sorted(valid_names))}"
        )

    return _load_prompt_cached(agent_name)


@lru_cache(maxsize=None)
def _load_prompt_cached(agent_name: str) -> str:
    """Cached internal loader — reads the file once and caches the result."""
    prompt_path = _PROMPTS_DIR / f"{agent_name}.md"

    if not prompt_path.exists():
        raise FileNotFoundError(
            f"Prompt file not found: {prompt_path}. "
            f"Ensure '{agent_name}.md' exists in {_PROMPTS_DIR}"
        )

    content = prompt_path.read_text(encoding="utf-8")
    logger.info("Loaded agent prompt", agent=agent_name, path=str(prompt_path), length=len(content))
    return content


def list_available_agents() -> list[str]:
    """Return a sorted list of agent names that have prompt files available.

    Returns:
        A list of agent name strings.
    """
    available = []
    all_valid_names = _VALID_AGENTS | _SCANNER_FIXERS
    for name in sorted(all_valid_names):
        prompt_path = _PROMPTS_DIR / f"{name}.md"
        if prompt_path.exists():
            available.append(name)
    return available
