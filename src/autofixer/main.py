"""Autonomous AI Auto-Fixer – CLI entry-point.

Provides two sub-commands:

* ``autofixer run``  – batch pipeline mode
* ``autofixer chat`` – interactive REPL mode

The legacy ``main()`` function is retained for backward compatibility
with existing ``[project.scripts]`` entries and direct invocation.
"""

from __future__ import annotations

import click
import structlog

from autofixer.cli.batch import run
from autofixer.cli.chat import chat
from autofixer.config import load_config
from autofixer.models.enums import AgentMode
from autofixer.remediation.engine import RemediationEngine

logger = structlog.get_logger(__name__)


# ── Click group ──────────────────────────────────────────────────────
@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Autonomous AI Auto-Fixer Agent."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


cli.add_command(run)
cli.add_command(chat)


# ── Legacy entry-point (backward compatibility) ─────────────────────
@cli.command("legacy")
@click.option(
    "--mode",
    type=click.Choice(["dry-run", "fix"]),
    default="dry-run",
    help="Execution mode",
)
@click.option(
    "--config",
    "config_path",
    default="config/default.yaml",
    help="Path to config file",
)
@click.option(
    "--input-file",
    "input_file",
    default=None,
    help="Path to input file (PDF, CSV, Excel, etc.)",
)
@click.option(
    "--repo",
    "repo_name",
    default=None,
    help="Specify a single repository to scan",
)
@click.option(
    "--branch",
    "base_branch",
    default=None,
    help="The base branch to scan and branch off from",
)
def legacy(
    mode: str,
    config_path: str,
    input_file: str | None,
    repo_name: str | None,
    base_branch: str | None,
) -> None:
    """Run the legacy remediation engine (pre-agent pipeline)."""
    cfg = load_config(config_path)
    cfg.agent.mode = mode
    if base_branch:
        cfg.agent.base_branch = base_branch

    logger.info(
        "Initializing Autonomous AI Auto-Fixer (legacy mode)",
        mode=cfg.agent.mode,
        branch=cfg.agent.base_branch,
        input_file=input_file,
        repo=repo_name,
    )

    if input_file:
        logger.info("Processing input file", file_path=input_file)

    if cfg.agent.mode == "dry-run":
        logger.info(
            "Running in DRY-RUN mode. No changes will be applied."
        )
    else:
        logger.warning(
            "Running in FIX mode. Changes will be committed and "
            "PRs created."
        )

    engine = RemediationEngine(cfg, input_file=input_file)
    engine.run(repo_name=repo_name)


def main() -> None:
    """Backward-compatible entry-point for ``autofixer`` console script."""
    cli()


if __name__ == "__main__":
    main()
