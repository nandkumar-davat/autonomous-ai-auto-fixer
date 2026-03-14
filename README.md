# Autonomous AI Auto-Fixer

The **Autonomous AI Auto-Fixer** is an enterprise-grade agent designed to automate the remediation of technical debt and security vulnerabilities. It integrates with **SonarQube**, **Mend**, and **Trivy** to ingest findings, generate validated code fixes using AI, and submit Pull Requests to **Azure Repos** and **GitHub**.

- [Implementation Plan](IMPLEMENTATION_PLAN.md)
- [Task List](TASKS.md)


## Key Features

- **Autonomous Remediation**: Automatically fixes code smells, bugs, and dependency vulnerabilities.
- **Risk Assessment**: Classifies findings into Low/High risk to ensure only safe changes are automated.
- **Priority-Based Fixing**: Processes issues in priority order (Bugs → Vulnerabilities → Blocker → Critical → Major → High).
- **Dry-Run Mode**: Supports a "Report Only" mode for human approval before applying any fixes.
- **Multi-VCS Support**: Primary integration with Azure Repos, secondary with GitHub.
- **Enterprise-Grade Security**: Integrated with Azure Key Vault for secure credential management.
- **Validation Loop**: Every fix is validated via linters and (optionally) CI builds with AI self-correction.

## Tech Stack

- **Language**: Python 3.11+
- **Agent Orchestration**: Custom AI reasoning loops
- **Runtime LLM**: GitHub Copilot / Claude Sonnet 4
- **VCS**: Azure DevOps Python SDK, PyGithub
- **Secrets**: Azure Key Vault
- **Infrastructure**: Containerized deployment (Docker/Kubernetes)

## Setup

### Prerequisites

- Python 3.11 or higher
- Access to Azure Key Vault (with appropriate secrets configured)
- VCS Credentials (PAT for Azure DevOps, GitHub App credentials)

### Installation

1. Create a virtual environment:
   ```bash
   python -m venv .venv
   ```

2. Activate the virtual environment:
   - **Windows**: `.venv\Scripts\Activate.ps1`
   - **Linux/macOS**: `source .venv/bin/activate`

3. Install the package in editable mode:
   ```bash
   pip install -e ".[dev]"
   ```

## Usage

Run the autofixer in dry-run mode:
```bash
autofixer --mode dry-run
```

Review the report and approve fixes:
```bash
autofixer --mode fix --approve-all
```

## Audit & Logging

The system maintains a tamper-proof audit log of all actions, including:
- Ingested findings
- Generated prompts and LLM responses
- Validation results
- PR creation details
