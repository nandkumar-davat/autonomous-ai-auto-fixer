"""Batch-mode CLI for the autofixer pipeline.

Usage::

    autofixer run --repo /path/to/repo --mend-report mend.json --mode dry-run
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict

import click
import structlog
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from autofixer.agents.orchestrator import AgentOrchestrator
from autofixer.config import Config, load_config

logger = structlog.get_logger(__name__)
console = Console()


def _print_summary(results: Dict[str, Any]) -> None:
    """Render a human-friendly summary of pipeline results."""
    status = results.get("status", "unknown")
    style = "bold green" if status == "pass" else "bold yellow"
    if status == "fail":
        style = "bold red"

    console.print()
    console.print(
        Panel(
            f"Pipeline Status: [bold]{status.upper()}[/bold]",
            style=style,
            title="Autonomous AI Auto-Fixer – Results",
        )
    )

    # Audit summary table
    audit_plans = results.get("audit_plans", [])
    if audit_plans:
        table = Table(title="Audit Plans")
        table.add_column("Scanner", style="cyan")
        table.add_column("Findings", justify="right")
        table.add_column("Proposed Fixes", justify="right")
        for plan in audit_plans:
            table.add_row(
                plan.get("scanner_type", "?"),
                str(plan.get("total_findings", 0)),
                str(len(plan.get("proposed_fixes", []))),
            )
        console.print(table)

    # Consolidated plan
    consolidated = results.get("consolidated_plan")
    if consolidated:
        console.print(
            f"\n[bold]Consolidated:[/bold] "
            f"{consolidated.get('total_fixes', 0)} fixes across "
            f"{consolidated.get('files_affected', 0)} files"
        )

    # Fix result
    fix_result = results.get("fix_result")
    if fix_result:
        applied = fix_result.get("total_fixes_applied", 0)
        attempted = fix_result.get("total_fixes_attempted", 0)
        console.print(
            f"[bold]Fixes:[/bold] {applied}/{attempted} applied"
        )
        if fix_result.get("pr_url"):
            console.print(
                f"[bold]PR:[/bold] {fix_result['pr_url']}"
            )

    # Verification
    verification = results.get("verification")
    if verification:
        passed = verification.get("passed_checks", 0)
        total = verification.get("total_checks", 0)
        v_status = verification.get("overall_status", "?")
        console.print(
            f"[bold]Verification:[/bold] {passed}/{total} checks "
            f"passed ({v_status})"
        )
        regressions = verification.get("regressions_found", [])
        if regressions:
            console.print(
                f"[bold red]Regressions:[/bold red] "
                f"{', '.join(regressions)}"
            )

    console.print()


@click.command("run")
@click.option(
    "--mend-report",
    type=click.Path(exists=False),
    default=None,
    help="Path to Mend scan JSON report.",
)
@click.option(
    "--trivy-report",
    type=click.Path(exists=False),
    default=None,
    help="Path to Trivy scan JSON report.",
)
@click.option(
    "--sonar-report",
    type=click.Path(exists=False),
    default=None,
    help="Path to SonarQube scan JSON report.",
)
@click.option(
    "--repo",
    required=True,
    type=click.Path(exists=True, file_okay=False),
    help="Path to target repository.",
)
@click.option(
    "--base-branch",
    default="main",
    show_default=True,
    help="Base branch to create fix branch from.",
)
@click.option(
    "--mode",
    type=click.Choice(["dry-run", "fix"], case_sensitive=False),
    default="dry-run",
    show_default=True,
    help="Execution mode.",
)
@click.option(
    "--config",
    "config_path",
    default="config/default.yaml",
    show_default=True,
    type=click.Path(),
    help="Path to YAML configuration file.",
)
@click.option(
    "--output-json",
    type=click.Path(),
    default=None,
    help="Write full results to a JSON file.",
)
def run(
    mend_report: str | None,
    trivy_report: str | None,
    sonar_report: str | None,
    repo: str,
    base_branch: str,
    mode: str,
    config_path: str,
    output_json: str | None,
) -> None:
    """Run the autonomous auto-fixer pipeline in batch mode."""
    console.print(
        Panel(
            "[bold]Autonomous AI Auto-Fixer – Batch Mode[/bold]",
            style="bold blue",
        )
    )

    # Load configuration and apply CLI overrides
    cfg: Config = load_config(config_path)
    cfg.agent.mode = mode
    cfg.agent.base_branch = base_branch

    logger.info(
        "Starting batch pipeline",
        mode=mode,
        repo=repo,
        base_branch=base_branch,
        mend_report=mend_report,
        trivy_report=trivy_report,
        sonar_report=sonar_report,
    )

    # At least one report must be provided
    if not any([mend_report, trivy_report, sonar_report]):
        console.print(
            "[bold red]Error:[/bold red] At least one scan report "
            "must be provided (--mend-report, --trivy-report, "
            "or --sonar-report)."
        )
        sys.exit(1)

    try:
        orchestrator = AgentOrchestrator(config=cfg)
        results = orchestrator.run_pipeline(
            mend_report=mend_report,
            trivy_report=trivy_report,
            sonar_report=sonar_report,
            repo_path=repo,
            base_branch=base_branch,
        )
    except Exception:
        logger.exception("Pipeline failed with an unexpected error")
        console.print(
            "[bold red]Pipeline failed.[/bold red] "
            "Check logs for details."
        )
        sys.exit(2)

    _print_summary(results)

    if output_json:
        with open(output_json, "w") as fh:
            json.dump(results, fh, indent=2, default=str)
        console.print(f"[dim]Results written to {output_json}[/dim]")

    # Exit with non-zero on failure
    if results.get("status") == "fail":
        sys.exit(1)
