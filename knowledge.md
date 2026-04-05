# Project knowledge

This file gives Codebuff context about your project: goals, commands, conventions, and gotchas.

## What is this project?

An enterprise-grade autonomous AI agent that remediates technical debt and security vulnerabilities. It ingests findings from **SonarQube**, **Mend**, and **Trivy**, generates validated code fixes via LLM (GitHub Copilot / Claude Sonnet 4), and submits Pull Requests to **Azure DevOps** (primary) and **GitHub** (secondary).

## Quickstart

- Setup:
  ```bash
  python -m venv .venv
  source .venv/bin/activate
  pip install -e ".[dev]"
  ```
- Run (dry-run): `autofixer --mode dry-run`
- Run (fix): `autofixer --mode fix --approve-all`
- Test (unit): `pytest tests/unit/ -v --cov=src/autofixer --cov-report=term-missing`
- Test (integration): `pytest tests/integration/ -v`
- Lint: `flake8 src/ tests/`
- Format: `black src/ tests/` and `isort src/ tests/`
- Type check: `mypy src/`

## Architecture

- Key directories:
  - `src/autofixer/` — all application code
  - `src/autofixer/ingestion/` — tool-specific parsers (sonarqube, mend, trivy)
  - `src/autofixer/remediation/` — engine, strategies, LLM client, risk assessor, self-corrector
  - `src/autofixer/validation/` — linter runner, CI build verifier
  - `src/autofixer/vcs/` — git ops, Azure DevOps client, GitHub client, PR monitor
  - `src/autofixer/secrets/` — Azure Key Vault integration
  - `src/autofixer/audit/` — structured audit logging
  - `src/autofixer/models/` — Pydantic models, enums, Finding dataclass
  - `config/default.yaml` — default configuration
  - `tests/unit/` and `tests/integration/` — test suites
- Data flow: Ingestion → Risk Assessment → Remediation Engine → Strategy Selection → LLM Fix Generation → Validation (linter) → Self-correction loop (max 3 retries) → VCS/PR creation
- Entry point: `src/autofixer/main.py` (CLI via Click, registered as `autofixer` script)

## Conventions

- **Python version**: 3.11+
- **Formatting**: Black (line-length 88), isort (profile "black")
- **Linting**: flake8
- **Type checking**: mypy
- **Testing**: pytest with pytest-asyncio, pytest-cov
- **Models**: Pydantic v2 for data validation and settings
- **HTTP**: httpx (async-first)
- **Logging**: structlog for structured audit logs
- **Config**: YAML (`config/default.yaml`) + env vars; secrets via Azure Key Vault
- **Package layout**: src-layout (`src/autofixer/`), packages discovered via `[tool.setuptools.packages.find] where = ["src"]`
- **VCS priority**: Azure DevOps first, GitHub second
- **Dry-run mode**: Default mode; agent reports only until user approves fixes

## Things to avoid

- Never log or write secrets to disk
- Don't auto-fix Major/High severity issues without explicit user approval
- Don't modify code in dry-run mode
- Complex multi-file refactors and core business logic changes are never auto-fixed
