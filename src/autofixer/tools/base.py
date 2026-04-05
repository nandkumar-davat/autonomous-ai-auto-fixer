"""Base tool abstractions and registry for the autofixer tool system."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from structlog import get_logger

logger = get_logger()


class BaseTool(ABC):
    """Abstract base class for all autofixer tools.

    Every tool must define a ``name``, ``description``, and implement
    the ``execute`` method which returns a dict containing at minimum
    ``success`` (bool) and ``result`` keys.
    """

    name: str
    description: str

    @abstractmethod
    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        """Execute the tool with the given keyword arguments.

        Returns:
            A dict with at least ``success`` (bool) and ``result`` keys.
        """
        ...


class ToolRegistry:
    """Registry that holds named tool instances for easy look-up."""

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}

    def register_tool(self, tool: BaseTool) -> None:
        """Register a tool instance.  Overwrites if the name already exists."""
        logger.info("tool.registered", tool_name=tool.name)
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> BaseTool:
        """Retrieve a tool by name.

        Raises:
            KeyError: If no tool with the given name is registered.
        """
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' is not registered")
        return self._tools[name]

    def list_tools(self) -> List[Dict[str, str]]:
        """Return a list of dicts describing each registered tool."""
        return [
            {"name": t.name, "description": t.description}
            for t in self._tools.values()
        ]
