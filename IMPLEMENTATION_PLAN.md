# Autonomous AI Auto-Fixer — Implementation Plan

## Overview

Build a Python-based autonomous AI agent that integrates with **SonarQube**, **Mend**, and **Trivy** to automatically remediate low-risk code issues (code smells, dependency vulnerabilities, security patches) and submit validated Pull Requests for human review. This is a **greenfield project** — no existing code exists yet.

> [!IMPORTANT]
> **Timeline:** The requirements documents specify a 23-week project (2026-03-16 → 2026-08-21) across 7 phases. Development proceeds **sequentially**, phase-by-phase with review gates.

> [!NOTE]
> **Development workflow:** Code is written using **Gemini 3 Flash**. The agent itself uses **GitHub Copilot** in VS Code (Auto mode or Claude Sonnet 4) as its runtime LLM for code reasoning and fix generation.

---

## Current Project Status

| Phase | Status | Key Components |
|-------|--------|----------------|
| **Phase 0** | ✅ | Scaffolding, `pyproject.toml`, Config schemas |
| **Phase 1** | ✅ | VCS Clients (Azure/GitHub), Git Ops, PR Monitor |
| **Phase 2** | ✅ | SonarQube API/File Ingester, Code Smell Strategies |
| **Phase 3** | ✅ | Mend API/File Ingester (CSV/Excel/PDF), Dependency Bumps |
| **Phase 4** | ⏳ | Trivy Ingester (SARIF/JSON) |
| **Phase 5** | 🔄 | Core Engine, Risk Assessor (Implemented), Validation Loop |
| **Phase 6** | ⏳ | Testing, Dockerization, Final Docs |

---

## Proposed Project Structure

```
autonomous-ai-auto-fixer/
├── pyproject.toml                    # Project metadata, dependencies
├── .python-version                   # Pins Python version (e.g. 3.11)
├── Dockerfile                        # Container deployment
├── docker-compose.yml                # Local development stack
├── .env.example                      # Environment variable template
├── .gitignore                        # Ignores .venv/, __pycache__/, etc.
├── README.md
├── config/
│   ├── default.yaml                  # Default configuration
│   └── logging.yaml                  # Logging configuration
├── src/
│   └── autofixer/
│       ├── __init__.py
│       ├── main.py                   # CLI entrypoint
│       ├── config.py                 # Config loader (YAML + env vars)
│       ├── models/
│       │   ├── __init__.py
│       │   ├── finding.py            # Unified Finding dataclass
│       │   ├── remediation.py        # Remediation result models
│       │   └── enums.py              # RiskLevel, Severity, ToolSource enums
│       ├── ingestion/
│       │   ├── __init__.py
│       │   ├── base.py               # Abstract BaseIngester
│       │   ├── sonarqube/
│       │   │   ├── __init__.py
│       │   │   ├── api_client.py     # SonarQube REST API client
│       │   │   └── file_parser.py    # JSON file parser
│       │   ├── mend/
│       │   │   ├── __init__.py
│       │   │   ├── api_client.py     # Mend Platform API 3.0 client
│       │   │   ├── pdf_parser.py     # PDF report parser (PyMuPDF)
│       │   │   ├── excel_parser.py   # Excel report parser (pandas)
│       │   │   └── csv_parser.py     # CSV report parser
│       │   └── trivy/
│       │       ├── __init__.py
│       │       ├── api_client.py     # Trivy Server/Operator client
│       │       └── file_parser.py    # JSON/SARIF parser
│       ├── remediation/
│       │   ├── __init__.py
│       │   ├── engine.py             # Core remediation orchestrator
│       │   ├── risk_assessor.py      # Risk classification (Low/High)
│       │   ├── context_retriever.py  # Source code context fetching
│       │   ├── llm_client.py         # GitHub Copilot / Claude Sonnet 4 LLM client
│       │   ├── self_corrector.py     # Retry loop with validation feedback
│       │   └── strategies/
│       │       ├── __init__.py
│       │       ├── code_smell.py     # Code smell fix strategies
│       │       ├── dependency.py     # Dependency version bump strategies
│       │       └── security.py       # Security patch strategies
│       ├── validation/
│       │   ├── __init__.py
│       │   ├── linter.py             # Language-specific linter runner
│       │   └── build_verifier.py     # Optional CI build trigger
│       ├── vcs/
│       │   ├── __init__.py
│       │   ├── base_vcs.py           # Abstract VCS client interface
│       │   ├── git_ops.py            # Clone, branch, commit, push
│       │   ├── azure_devops_client.py # Azure Repos API (PR CRUD) — primary
│       │   ├── github_client.py      # GitHub App API (PR CRUD) — secondary
│       │   └── pr_monitor.py         # PR comment monitoring & response
│       ├── secrets/
│       │   ├── __init__.py
│       │   └── keyvault.py            # Azure Key Vault integration
│       └── audit/
│           ├── __init__.py
│           └── logger.py             # Tamper-proof audit logging
└── tests/
    ├── __init__.py
    ├── conftest.py                   # Shared fixtures
    ├── unit/
    │   ├── test_sonarqube_parser.py
    │   ├── test_mend_parsers.py
    │   ├── test_trivy_parser.py
    │   ├── test_risk_assessor.py
    │   ├── test_remediation_engine.py
    │   └── test_git_ops.py
    ├── integration/
    │   ├── test_sonarqube_integration.py
    │   ├── test_mend_integration.py
    │   ├── test_trivy_integration.py
    │   ├── test_azure_devops_integration.py
    │   └── test_github_integration.py
    └── e2e/
        └── test_full_workflow.py
```

---

## Proposed Changes

### Phase 0 — Project Setup & Scaffolding

#### Python Virtual Environment Setup

All development and execution uses a **Python `venv`** virtual environment. This is the first step before any dependency installation.

```bash
# Create the virtual environment (one-time)
python -m venv .venv

# Activate (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Activate (Linux / macOS / Git Bash)
source .venv/bin/activate

# Install project in editable mode with all dependencies
pip install -e ".[dev]"
```

> [!NOTE]
> The `.venv/` directory is added to `.gitignore`. All CI/CD pipelines and Docker builds will create their own isolated environments. The `pyproject.toml` pins `requires-python = ">=3.11"`.

#### [DONE] `pyproject.toml`

Python 3.11+ project with key dependencies:
- **HTTP**: `httpx` (async-first HTTP client with retry/backoff)
- **LLM**: `anthropic` / `openai` (GitHub Copilot / Claude Sonnet 4 for runtime reasoning)
- **Parsing**: `PyMuPDF` (PDF), `pandas` + `openpyxl` (Excel/CSV)
- **Git**: `GitPython` for local git operations
- **VCS APIs**: `azure-devops` (Azure DevOps Python SDK) — primary; `PyGithub` — secondary
- **Secrets**: `azure-identity`, `azure-keyvault-secrets` (Azure Key Vault)
- **Config**: `pyyaml`, `pydantic` (settings validation)
- **CLI**: `click` for command-line interface
- **Audit**: `structlog` for structured, tamper-aware logging

#### [NEW] `config/default.yaml`

Configuration schema covering:
- Tool connection settings (SonarQube URL, Mend org, Trivy endpoint)
- VCS settings (Azure DevOps org/project — primary; GitHub App ID — secondary)
- Azure Key Vault settings (vault URL, tenant ID — credentials via `DefaultAzureCredential`)
- LLM settings (GitHub Copilot / Claude Sonnet 4, temperature, max retries)
- Risk assessment thresholds
- **Issue fix priority order** (configurable, default below)
- Linter paths per language
- **Dry-run mode** enabled by default (`mode: dry-run`); set to `mode: fix` after user approval

#### [NEW] `src/autofixer/models/`

Pydantic-based data models:
- `Finding`: Unified representation with fields for `source_tool`, `rule_id`, `severity`, `file_path`, `line`, `message`, `risk_level`, `priority_rank`, `raw_data`
- `RemediationResult`: `finding`, `original_code`, `fixed_code`, `validation_status`, `llm_prompt_used`
- Enums:
  - `IssueType(BUG, VULNERABILITY, CODE_SMELL, SECURITY_HOTSPOT)`
  - `Severity(BLOCKER, CRITICAL, MAJOR, HIGH, MINOR, INFO)`
  - `RiskLevel(LOW, HIGH)`
  - `ToolSource(SONARQUBE, MEND, TRIVY)`
  - `AgentMode(DRY_RUN, FIX)`
  - `ApprovalStatus(AUTO_APPROVED, PENDING_APPROVAL, USER_APPROVED, USER_REJECTED)`

#### [NEW] `src/autofixer/secrets/keyvault.py`

Azure Key Vault integration:
- Uses `DefaultAzureCredential` for authentication (works with managed identity, Azure CLI, env vars)
- Retrieves all API tokens at startup: SonarQube, Mend, Trivy, Azure DevOps PAT, GitHub App key, Gemini API key
- Secrets are never logged or written to disk

---

### Phase 1 — Core Agent, VCS Integration & Dry-Run Mode [COMPLETED]

> [!IMPORTANT]
> **Dry-Run is a first-class feature from Phase 1.** The agent starts in `dry-run` mode by default — it scans, classifies, and generates a remediation report but **does not modify code or create PRs**. Only when the user explicitly approves (switches to `fix` mode) does the agent apply changes.

#### Dry-Run Workflow

```
1. Ingest findings → 2. Classify risk → 3. Generate proposed fixes (in memory)
   ↓
4. Output dry-run report (JSON + human-readable summary)
   ↓
5. User reviews report → approves → agent switches to fix mode
   ↓
6. Apply fixes → validate → create PR
```

#### [NEW] `src/autofixer/vcs/base_vcs.py`

Abstract VCS client interface (`BaseVCSClient`) defining the contract for PR operations. Enables swapping between Azure DevOps and GitHub via config.

#### [NEW] `src/autofixer/vcs/git_ops.py`

Git operations using `GitPython`:
- `clone_repo(url, branch) → Path`
- `create_branch(repo, name) → Branch`
- `apply_changes(repo, file_path, new_content)` — skipped in dry-run mode
- `commit_and_push(repo, message)` — skipped in dry-run mode

#### [NEW] `src/autofixer/vcs/azure_devops_client.py` ⭐ Primary

Azure Repos integration (implemented first):
- PAT retrieved from Azure Key Vault at startup
- Create PR with structured description (summary, source finding, risk level, validation results)
- List/respond to PR review comments (thread-based API)
- Support Azure Pipelines build status checks

#### [NEW] `src/autofixer/vcs/github_client.py` — Secondary

GitHub App integration (implemented after Azure Repos):
- JWT authentication for GitHub Apps (key from Azure Key Vault)
- Create PR with structured description
- List/respond to PR review comments

#### [NEW] `src/autofixer/vcs/pr_monitor.py`

Human-in-the-loop (VCS-agnostic via `BaseVCSClient`):
- Poll PR comments on a configurable interval
- Parse reviewer feedback and route back to remediation engine
- Push updated commits in response

---

### Phase 2 — SonarQube Integration [COMPLETED]

#### [NEW] `src/autofixer/ingestion/sonarqube/api_client.py`

- Token-based authentication
- Query `api/issues/search` with filters: `types=CODE_SMELL,BUG`, `severities=INFO,MINOR,MAJOR`
- Automatic pagination handling
- Exponential backoff with jitter for rate limits
- Returns list of `Finding` objects

#### [NEW] `src/autofixer/ingestion/sonarqube/file_parser.py`

- Parse SonarQube JSON exports and GitLab SAST format
- Extract: `key`, `rule`, `severity`, `component` (file path), `line`, `message`
- Normalize to unified `Finding` model

---

### Phase 3 — Mend Integration [COMPLETED]

#### [NEW] `src/autofixer/ingestion/mend/api_client.py`

- Mend Platform API 3.0 with User Keys + Organization Tokens
- Fetch "Code Application Findings"
- Map to unified `Finding` model

#### [NEW] `src/autofixer/ingestion/mend/pdf_parser.py`, `excel_parser.py`, `csv_parser.py`

- **PDF**: `PyMuPDF` for structured text extraction; extract `Vulnerability ID`, `Library Name`, `Current/Fixed Version`
- **Excel**: `pandas` + `openpyxl` for `.xlsx` reports
- **CSV**: Column mapping for `Library`, `CVE`, `Remediation Recommendation`

---

### Phase 4 — Trivy Integration

#### [NEW] `src/autofixer/ingestion/trivy/api_client.py`

- Trivy client-server or Operator API integration
- Real-time vulnerability report retrieval

#### [NEW] `src/autofixer/ingestion/trivy/file_parser.py`

- Parse JSON output: `Results[].Vulnerabilities[]` → extract `PkgName`, `InstalledVersion`, `FixedVersion`, `PrimaryURL`
- Support SARIF and CycloneDX formats

---

### Phase 5 — Remediation Engine & Validation

#### Issue Fix Priority Order

The remediation engine processes findings in a strict priority queue. Issues at higher priority are fixed first. Lower-priority categories require explicit user approval:

| Priority | Type / Severity | Auto-Fix? |
|----------|----------------|----------|
| 1 (highest) | **Bugs** | ✅ Auto |
| 2 | **Vulnerabilities** | ✅ Auto |
| 3 | **Blocker** | ✅ Auto |
| 4 | **Critical** | ✅ Auto |
| 5 | **Major** | ⚠️ Optional — requires user approval |
| 6 | **High** | ⚠️ Optional — requires user approval |

> [!WARNING]
> **Major** and **High** severity issues are queued but **not fixed** until the user explicitly approves them (per-issue or batch). The dry-run report flags these separately under an "Awaiting Approval" section.

#### [NEW] `src/autofixer/remediation/engine.py`

Core orchestrator:
1. Receive all `Finding` objects → sort by priority order (Bugs → Vulnerabilities → Blocker → Critical → Major → High)
2. For each finding: classify risk
3. If auto-approved priority (1–4) and Low Risk → retrieve source context (50+ surrounding lines)
4. If optional priority (5–6) → queue for user approval; skip until approved
5. Select strategy (code smell / dependency / security)
6. Generate fix via **GitHub Copilot** (Auto mode / Claude Sonnet 4)
7. Validate via linter
8. If validation fails → self-correct (max 3 retries)
9. Return `RemediationResult`
10. If `dry-run` mode → output report only; if `fix` mode → apply changes + create PR

#### [NEW] `src/autofixer/remediation/risk_assessor.py`

Policy-driven classification combining **type/severity priority** and **risk level**:
- **Auto-fix eligible**: Bugs, Vulnerabilities, Blocker, Critical — AND classified as Low Risk
- **Approval required**: Major, High severity — queued with `ApprovalStatus.PENDING_APPROVAL`
- **Never auto-fix**: complex architectural changes, multi-file refactors, changes to core business logic (regardless of severity)

#### [NEW] `src/autofixer/validation/linter.py`

- Detect file language from extension
- Run appropriate linter (`flake8` for Python, `eslint` for JS/TS, `checkstyle` for Java)
- Parse linter output for pass/fail determination

#### [NEW] `src/autofixer/remediation/self_corrector.py`

- Feed validation errors back to GitHub Copilot / Claude Sonnet 4 with original context
- Maximum 3 retry attempts
- Log each attempt for auditability

---

### Phase 6 — Testing & Deployment

#### [NEW] `tests/`

- **Unit tests**: Parser correctness with sample data fixtures, risk assessor classification, git operations
- **Integration tests**: Mock API responses for SonarQube/Mend/Trivy/Azure DevOps/GitHub
- **E2E tests**: Full ingestion → dry-run report → approval → fix → PR workflow with a test repository

#### [NEW] `Dockerfile`

Multi-stage Docker build for containerized deployment.

---

## Resolved Decisions

| # | Decision | Resolution |
|---|----------|------------|
| 1 | **VCS Priority** | ✅ Azure Repos first, GitHub second |
| 2 | **LLM Provider** | ✅ **GitHub Copilot** (Auto / Claude Sonnet 4) as agent runtime LLM; development via Gemini 3 Flash |
| 3 | **Secret Management** | ✅ **Azure Key Vault** (`azure-keyvault-secrets` + `DefaultAzureCredential`) |
| 4 | **Dry-Run Mode** | ✅ First-class from **Phase 1**; agent reports only until user approves fixes |
| 5 | **Implementation Scope** | ✅ **All phases sequentially** (Phase 0 → 1 → 2 → 3 → 4 → 5 → 6) |

---

## Verification Plan

### Automated Tests

All test commands assume the virtual environment is activated:

```bash
# Activate venv first
.venv\Scripts\Activate.ps1   # Windows
source .venv/bin/activate     # Linux/macOS

# Run all unit tests
pytest tests/unit/ -v --cov=src/autofixer --cov-report=term-missing

# Run integration tests (requires mock fixtures)
pytest tests/integration/ -v

# Run E2E tests (requires test repository setup)
pytest tests/e2e/ -v
```

**Per-phase verification:**
- **Phase 1**: Unit tests for git operations; integration test creating a PR on a test repo
- **Phase 2**: Unit tests for SonarQube JSON parsing with sample fixture files; integration test with SonarQube API mock
- **Phase 3**: Unit tests for PDF/Excel/CSV parsers with sample Mend reports
- **Phase 4**: Unit tests for Trivy JSON/SARIF parsing
- **Phase 5**: Unit tests for risk assessor; integration test for full remediation pipeline with mocked LLM
- **Phase 6**: Full E2E test and deployment smoke test via Docker

### Manual Verification

- **PR Quality Check**: After Phase 1, manually review a test PR created by the agent against a sample repository for correct formatting, branch naming, and description structure.
- **Parser Accuracy**: After Phases 2-4, provide sample report files (SonarQube JSON, Mend PDF/CSV, Trivy JSON) and manually verify the parsed `Finding` objects match expected values.
- **Dry-Run Mode**: Run the agent in report-only mode and verify it produces an actionable report without modifying any code.
- **Approval Gate**: Verify that switching from `dry-run` to `fix` mode correctly triggers code changes and PR creation only after explicit user approval.
