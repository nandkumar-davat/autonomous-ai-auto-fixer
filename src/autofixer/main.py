import click
from autofixer.config import load_config
from autofixer.models.enums import AgentMode
from structlog import get_logger

logger = get_logger()

@click.command()
@click.option("--mode", type=click.Choice(["dry-run", "fix"]), default="dry-run", help="Execution mode")
@click.option("--config", "config_path", default="config/default.yaml", help="Path to config file")
@click.option("--repo", "repo_name", help="Specify a single repository to scan")
@click.option("--branch", "base_branch", help="The base branch to scan and branch off from (e.g., 'main', 'develop')")
def main(mode, config_path, repo_name, base_branch):
    """Autonomous AI Auto-Fixer Entrypoint."""
    
    # Load configuration
    cfg = load_config(config_path)
    
    # Override mode from CLI
    cfg.agent.mode = mode
    if base_branch:
        cfg.agent.base_branch = base_branch
    
    logger.info("Initializing Autonomous AI Auto-Fixer", mode=cfg.agent.mode, branch=cfg.agent.base_branch)
    
    if cfg.agent.mode == "dry-run":
        logger.info("Running in DRY-RUN mode. No changes will be applied.")
    else:
        logger.warning("Running in FIX mode. Changes will be committed and PRs created.")

    # TODO: Initialize Core Engine and start ingestion
    # engine = RemediationEngine(cfg)
    # engine.run(repo_name=repo_name)

if __name__ == "__main__":
    main()
