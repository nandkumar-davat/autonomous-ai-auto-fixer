"""Terminal tool for executing shell commands with safety controls."""

import shlex
import subprocess
from typing import Any, Dict, List, Optional

from structlog import get_logger

from autofixer.tools.base import BaseTool

logger = get_logger()

DEFAULT_ALLOWED_COMMANDS: List[str] = [
    "ls",
    "cat",
    "head",
    "tail",
    "grep",
    "find",
    "wc",
    "diff",
    "echo",
    "pwd",
    "python",
    "pip",
    "npm",
    "node",
    "git",
    "rg",
    "make",
    "docker",
    "go",
    "cargo",
    "mvn",
    "gradle",
]


class TerminalTool(BaseTool):
    """Executes shell commands with timeout, output capture, and optional sandboxing.

    Parameters
    ----------
    allowed_commands:
        Whitelist of command base-names that may be executed.  When *None* the
        ``DEFAULT_ALLOWED_COMMANDS`` list is used.
    sandbox_mode:
        When ``True`` every command is wrapped in a disposable Docker
        container for isolation.
    sandbox_image:
        Docker image used for sandboxed execution.
    default_timeout:
        Default timeout in seconds for each command invocation.
    """

    name: str = "terminal"
    description: str = (
        "Run a shell command and return stdout/stderr. "
        "Supports an allowed-commands whitelist and Docker sandbox mode."
    )

    def __init__(
        self,
        *,
        allowed_commands: Optional[List[str]] = None,
        sandbox_mode: bool = False,
        sandbox_image: str = "python:3.11-slim",
        default_timeout: int = 60,
    ) -> None:
        self.allowed_commands: List[str] = (
            allowed_commands if allowed_commands is not None else list(DEFAULT_ALLOWED_COMMANDS)
        )
        self.sandbox_mode: bool = sandbox_mode
        self.sandbox_image: str = sandbox_image
        self.default_timeout: int = default_timeout

    # ------------------------------------------------------------------
    # BaseTool interface
    # ------------------------------------------------------------------

    def execute(
        self,
        *,
        command: str,
        timeout: Optional[int] = None,
        cwd: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Execute *command* and return its output.

        Parameters
        ----------
        command:
            The shell command string to execute.
        timeout:
            Override the default timeout (seconds).
        cwd:
            Working directory for the command.
        """
        effective_timeout = timeout if timeout is not None else self.default_timeout
        logger.info(
            "terminal.execute",
            command=command,
            timeout=effective_timeout,
            sandbox=self.sandbox_mode,
        )

        # --- safety check ---
        if not self._is_allowed(command):
            msg = f"Command not in allowed list: {command.split()[0]!r}"
            logger.warning("terminal.blocked", reason=msg)
            return {"success": False, "result": None, "error": msg}

        # --- optionally wrap in Docker ---
        if self.sandbox_mode:
            command = self._wrap_in_docker(command, cwd)
            cwd = None  # cwd is handled inside the container

        try:
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=effective_timeout,
                cwd=cwd,
            )
            return {
                "success": proc.returncode == 0,
                "result": proc.stdout,
                "stderr": proc.stderr,
                "returncode": proc.returncode,
            }
        except subprocess.TimeoutExpired:
            logger.error("terminal.timeout", command=command, timeout=effective_timeout)
            return {
                "success": False,
                "result": None,
                "error": f"Command timed out after {effective_timeout}s",
            }
        except Exception as exc:
            logger.error("terminal.failed", command=command, error=str(exc))
            return {"success": False, "result": None, "error": str(exc)}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _is_allowed(self, command: str) -> bool:
        """Check that the base command name appears in the whitelist."""
        try:
            parts = shlex.split(command)
        except ValueError:
            parts = command.split()
        if not parts:
            return False
        base_cmd = parts[0].rsplit("/", maxsplit=1)[-1]  # handle absolute paths
        return base_cmd in self.allowed_commands

    def _wrap_in_docker(self, command: str, cwd: Optional[str]) -> str:
        """Wrap *command* inside a ``docker run --rm`` invocation."""
        volume_flag = f"-v {shlex.quote(cwd)}:/work -w /work" if cwd else ""
        escaped = shlex.quote(command)
        return (
            f"docker run --rm --network none {volume_flag} "
            f"{self.sandbox_image} sh -c {escaped}"
        )
