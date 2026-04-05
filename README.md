# Autonomous AI Auto-Fixer

An enterprise-grade AI-powered agent for automated remediation of security vulnerabilities and code quality findings.

## Key Features

- **Multi-Agent Architecture**: Four specialized agents work in sequence:
  - **Auditor** (3 parallel) - Analyzes Mend, Trivy, and SonarQube scan reports
  - **Team Lead** - Consolidates findings, deduplicates, resolves conflicts
  - **Fixer** - Applies fixes, runs lint/build verification, commits & creates PR
  - **Verifier** - Re-checks fixes, validates no regressions

- **Multi-LLM Support**: Configurable providers with automatic fallback:
  - GitHub Copilot (default: "auto" mode)
  - Google Gemini Flash
  - OpenRouter (free tier)
  - Ollama (local models)

- **Scanner Integration**: SonarQube, Mend (WhiteSource), Trivy
- **VCS Integration**: Azure DevOps and GitHub
- **Risk Assessment**: Low/High classification for safe automation
- **Dry-Run Mode**: Preview changes before applying

## Quick Start

```bash
cd autonomous-ai-auto-fixer
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Batch mode
autofixer run --repo /path/to/repo --sonar-report scan.json --mode dry-run

# Interactive mode
autofixer chat --repo /path/to/repo --base-branch main
```

## Architecture

```
Pipeline Flow:
Scan Reports (Mend/Trivy/SonarQube)
        ||
   [Auditor x3]  <-- parallel execution
        ||
   [Team Lead]   <-- consolidate & deduplicate
        ||
   [Fixer]       <-- apply fixes, lint, commit, PR
        ||
   [Verifier]    <-- re-check, validate no regressions
```

## Documentation

- [Implementation Plan](IMPLEMENTATION_PLAN.md)
- [Task List](TASKS.md)
- [Configuration & Ingestion Guide](docs/configuration.md)
- [Architecture & Tech Stack](docs/architecture.md)
- [Deployment & Execution Guide](docs/deployment.md)
- [Testing & Verification Guide](docs/testing_guide.md)

## Configuration

Edit `config/default.yaml`:

```yaml
llm:
  provider: github-copilot
  providers: [github_copilot, gemini, openrouter, ollama]
  model: auto

agent:
  mode: dry-run
  max_retries: 3
  base_branch: main

severity_filters:
  mend:
    min_severity: HIGH
    include_types: [VULNERABILITY]
  trivy:
    min_severity: HIGH
    include_types: [VULNERABILITY, MISCONFIGURATION]
  sonarqube:
    min_severity: MAJOR
    include_types: [BUG, VULNERABILITY, CODE_SMELL]
```

## Current Progress

- [x] Phase 1: Core Framework & VCS Integration
- [x] Phase 2: SonarQube Integration
- [x] Phase 3: Mend Integration
- [x] Phase 4: Trivy Integration
- [x] Phase 5: Remediation Engine & Validation
- [x] Phase 6: Multi-Agent Orchestration
- [x] Phase 7: Testing & Documentation