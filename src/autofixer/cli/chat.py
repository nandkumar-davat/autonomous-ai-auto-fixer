"""Interactive chat-mode CLI for the autofixer pipeline.

Provides a simple REPL with slash-commands to drive the pipeline
step-by-step::

    autofixer chat --repo /path/to/repo
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import click
import structlog
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from autofixer.agents.messages import (
    AuditPlan,
    ConsolidatedPlan,
    FixResult,
    VerificationReport,
)
from autofixer.agents.orchestrator import AgentOrchestrator
from autofixer.config import Config, load_config

logger = structlog.get_logger(__name__)
console = Console()

_HELP_TEXT = """\
**Available Commands**

| Command | Description |
|---|---|
| `/scan <file>` | Audit a single report file (auto-detects scanner type) |
| `/plan` | Consolidate all audit plans into a fix plan |
| `/fix` | Apply fixes from the consolidated plan |
| `/verify` | Verify the applied fixes |
| `/run` | Run the full pipeline (scan → plan → fix → verify) |
| `/status` | Show current session state |
| `/reset` | Clear session state |
| `/help` | Show this help message |
| `/quit` | Exit the chat |
"""


class ChatSession:
    """Holds mutable state across the interactive session."""

    def __init__(
        self,
        orchestrator: AgentOrchestrator,
        repo_path: str,
        base_branch: str,
    ) -> None:
        self.orchestrator = orchestrator
        self.repo_path = repo_path
        self.base_branch = base_branch

        # Accumulated state
        self.audit_plans: List[AuditPlan] = []
        self.consolidated_plan: Optional[ConsolidatedPlan] = None
        self.fix_result: Optional[FixResult] = None
        self.verification: Optional[VerificationReport] = None

    def reset(self) -> None:
        self.audit_plans = []
        self.consolidated_plan = None
        self.fix_result = None
        self.verification = None


def _detect_scanner(path: str) -> str:
    """Best-effort scanner type detection from the file name."""
    name = os.path.basename(path).lower()
    if "mend" in name or "whitesource" in name:
        return "mend"
    if "trivy" in name:
        return "trivy"
    if "sonar" in name:
        return "sonarqube"
    # Default to sonarqube as a safe fallback
    console.print(
        "[yellow]Could not auto-detect scanner type from filename. "
        "Defaulting to 'sonarqube'.[/yellow]"
    )
    return "sonarqube"


def _handle_scan(session: ChatSession, args: str) -> None:
    """Handle the /scan command."""
    path = args.strip()
    if not path:
        console.print("[red]Usage: /scan <path-to-report-file>[/red]")
        return

    if not os.path.isfile(path):
        console.print(f"[red]File not found: {path}[/red]")
        return

    scanner = _detect_scanner(path)
    console.print(
        f"[cyan]Auditing {scanner} report:[/cyan] {path}"
    )

    try:
        plan = session.orchestrator._run_single_auditor(scanner, path)
        if plan is None:
            console.print("[yellow]Auditor returned no plan.[/yellow]")
            return
        session.audit_plans.append(plan)
        console.print(
            f"[green]✓ Audit complete:[/green] "
            f"{plan.total_findings} findings, "
            f"{len(plan.proposed_fixes)} proposed fixes"
        )
    except Exception as exc:
        logger.exception("Scan failed", scanner=scanner)
        console.print(f"[red]Scan failed: {exc}[/red]")


def _handle_plan(session: ChatSession) -> None:
    """Handle the /plan command."""
    if not session.audit_plans:
        console.print(
            "[yellow]No audit plans yet. Run /scan first.[/yellow]"
        )
        return

    console.print("[cyan]Consolidating audit plans…[/cyan]")
    try:
        session.consolidated_plan = (
            session.orchestrator._phase_consolidate(session.audit_plans)
        )
        cp = session.consolidated_plan
        console.print(
            f"[green]✓ Plan ready:[/green] "
            f"{cp.total_fixes} fixes across {cp.files_affected} files"
        )
        if cp.deduplication_notes:
            for note in cp.deduplication_notes:
                console.print(f"  [dim]• {note}[/dim]")
    except Exception as exc:
        logger.exception("Consolidation failed")
        console.print(f"[red]Plan failed: {exc}[/red]")


def _handle_fix(session: ChatSession) -> None:
    """Handle the /fix command."""
    if session.consolidated_plan is None:
        console.print(
            "[yellow]No consolidated plan. Run /plan first.[/yellow]"
        )
        return

    mode = session.orchestrator.config.agent.mode
    console.print(f"[cyan]Applying fixes (mode={mode})…[/cyan]")
    try:
        session.fix_result = session.orchestrator._phase_fix(
            session.consolidated_plan,
            repo_path=session.repo_path,
            base_branch=session.base_branch,
        )
        fr = session.fix_result
        console.print(
            f"[green]✓ Fixes applied:[/green] "
            f"{fr.total_fixes_applied}/{fr.total_fixes_attempted}"
        )
        if fr.pr_url:
            console.print(f"[bold]PR:[/bold] {fr.pr_url}")
    except Exception as exc:
        logger.exception("Fix phase failed")
        console.print(f"[red]Fix failed: {exc}[/red]")


def _handle_verify(session: ChatSession) -> None:
    """Handle the /verify command."""
    if session.fix_result is None:
        console.print(
            "[yellow]No fix result. Run /fix first.[/yellow]"
        )
        return

    console.print("[cyan]Running verification checks…[/cyan]")
    try:
        session.verification = session.orchestrator._phase_verify(
            session.fix_result,
            repo_path=session.repo_path,
        )
        vr = session.verification
        style = "green" if vr.overall_status == "PASS" else "red"
        console.print(
            f"[{style}]✓ Verification: {vr.overall_status}[/{style}] "
            f"({vr.passed_checks}/{vr.total_checks} checks passed)"
        )
        if vr.regressions_found:
            console.print("[red]Regressions:[/red]")
            for r in vr.regressions_found:
                console.print(f"  • {r}")
    except Exception as exc:
        logger.exception("Verification failed")
        console.print(f"[red]Verify failed: {exc}[/red]")


def _handle_run(session: ChatSession) -> None:
    """Handle the /run command – full pipeline."""
    if not session.audit_plans:
        console.print(
            "[yellow]No audit plans loaded. "
            "Use /scan <file> first, then /run.[/yellow]"
        )
        return

    console.print("[cyan]Running full pipeline…[/cyan]")
    _handle_plan(session)
    if session.consolidated_plan and session.consolidated_plan.total_fixes:
        _handle_fix(session)
        if session.fix_result:
            _handle_verify(session)


def _handle_status(session: ChatSession) -> None:
    """Handle the /status command."""
    table = Table(title="Session State")
    table.add_column("Phase", style="cyan")
    table.add_column("Status")

    # Audit
    n_plans = len(session.audit_plans)
    table.add_row(
        "Audit Plans",
        f"[green]{n_plans} loaded[/green]" if n_plans else "[dim]none[/dim]",
    )

    # Consolidated
    if session.consolidated_plan:
        cp = session.consolidated_plan
        table.add_row(
            "Consolidated Plan",
            f"[green]{cp.total_fixes} fixes / "
            f"{cp.files_affected} files[/green]",
        )
    else:
        table.add_row("Consolidated Plan", "[dim]not yet[/dim]")

    # Fix
    if session.fix_result:
        fr = session.fix_result
        table.add_row(
            "Fix Result",
            f"[green]{fr.total_fixes_applied}/"
            f"{fr.total_fixes_attempted} applied[/green]",
        )
    else:
        table.add_row("Fix Result", "[dim]not yet[/dim]")

    # Verify
    if session.verification:
        vr = session.verification
        style = "green" if vr.overall_status == "PASS" else "red"
        table.add_row(
            "Verification",
            f"[{style}]{vr.overall_status}[/{style}]",
        )
    else:
        table.add_row("Verification", "[dim]not yet[/dim]")

    console.print(table)


def _run_repl(session: ChatSession) -> None:
    """Main REPL loop."""
    console.print(Markdown(_HELP_TEXT))
    console.print()

    while True:
        try:
            raw = console.input("[bold green]autofixer>[/bold green] ")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye![/dim]")
            break

        line = raw.strip()
        if not line:
            continue

        if not line.startswith("/"):
            console.print(
                "[yellow]Unknown input. "
                "Type /help for available commands.[/yellow]"
            )
            continue

        parts = line.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd == "/quit" or cmd == "/exit":
            console.print("[dim]Goodbye![/dim]")
            break
        elif cmd == "/help":
            console.print(Markdown(_HELP_TEXT))
        elif cmd == "/scan":
            _handle_scan(session, args)
        elif cmd == "/plan":
            _handle_plan(session)
        elif cmd == "/fix":
            _handle_fix(session)
        elif cmd == "/verify":
            _handle_verify(session)
        elif cmd == "/run":
            _handle_run(session)
        elif cmd == "/status":
            _handle_status(session)
        elif cmd == "/reset":
            session.reset()
            console.print("[green]Session state cleared.[/green]")
        else:
            console.print(
                f"[yellow]Unknown command: {cmd}. "
                f"Type /help for available commands.[/yellow]"
            )


@click.command("chat")
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
    help="Base branch for fix branches.",
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
def chat(
    repo: str,
    base_branch: str,
    mode: str,
    config_path: str,
) -> None:
    """Start an interactive chat session with the auto-fixer."""
    console.print(
        Panel(
            "[bold]Autonomous AI Auto-Fixer – Interactive Mode[/bold]\n"
            f"Repository: {repo}  |  Branch: {base_branch}  |  "
            f"Mode: {mode}",
            style="bold green",
        )
    )

    cfg: Config = load_config(config_path)
    cfg.agent.mode = mode
    cfg.agent.base_branch = base_branch

    logger.info(
        "Starting interactive session",
        repo=repo,
        mode=mode,
        base_branch=base_branch,
    )

    orchestrator = AgentOrchestrator(config=cfg)
    session = ChatSession(
        orchestrator=orchestrator,
        repo_path=repo,
        base_branch=base_branch,
    )
    _run_repl(session)
