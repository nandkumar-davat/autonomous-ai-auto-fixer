# Autonomous AI Auto-Fixer

The **Autonomous AI Auto-Fixer** is an enterprise-grade agent designed to automate the remediation of technical debt and security vulnerabilities. It integrates with **SonarQube**, **Mend**, and **Trivy** to ingest findings, generate validated code fixes using AI, and submit Pull Requests to **Azure Repos** and **GitHub**.

- [Implementation Plan](IMPLEMENTATION_PLAN.md)
- [Task List](TASKS.md)


## Current Progress
- [x] **Phase 1**: Core Framework & VCS Integration (Azure DevOps, GitHub)
- [x] **Phase 2**: SonarQube Integration (API & File Ingestion)
- [x] **Phase 3**: Mend Integration (SCA, PDF/Excel/CSV)
- [x] **Phase 4**: Trivy Integration (Container & OS Scanning)
- [x] **Phase 5**: Remediation Engine (Linter validation, CI hooks, LLM Retries)
- [ ] **Phase 6**: Testing, Deployment & Documentation

## Key Features
- **Autonomous Remediation**: Automatically fixes code smells, bugs, and dependency vulnerabilities using CodeSmell and Dependency strategies.
- **VCS Clients**: Robust integration with Azure DevOps and GitHub for PR management.
- **Risk Assessment**: Classifies findings into Low/High risk to ensure only safe changes are automated.
- **Multi-Tool Ingestion**: Unified ingestion from SonarQube and Mend (vulnerability and technical debt).
- **PR Monitoring**: Human-in-the-loop support via comment polling.
- **Dry-Run Mode**: Supports a "Report Only" mode for human approval before applying any fixes.
- **Enterprise-Grade Security**: Integrated with Azure Key Vault for secure credential management.

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
