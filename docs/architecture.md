# Architecture & Technology Stack

## System Architecture

The Autonomous AI Auto-Fixer uses a **multi-agent pipeline** with four specialized agents:

```
Scan Reports (Mend/Trivy/SonarQube)
        ||
   [Auditor x3]  <-- parallel execution (one per scanner)
        ||
   [Team Lead]   <-- consolidate findings, deduplicate, resolve conflicts
        ||
   [Fixer]       <-- apply fixes, lint loop with retries, commit, PR
        ||
   [Verifier]    <-- re-check, validate no regressions
```

### Agent Descriptions

| Agent | Responsibility |
|-------|----------------|
| **Auditor** | Parses scan reports, filters by severity, proposes fix strategies |
| **Team Lead** | Merges audit plans, deduplicates findings, resolves version/line conflicts |
| **Fixer** | Applies fixes, runs lint/build verification, commits changes, creates PR |
| **Verifier** | Re-runs lint/build checks, detects regressions via LLM |

### Legacy Components (still used)

1.  **Ingestion Layer**: Fetches data from SonarQube, Mend, and Trivy.
2.  **Strategy Layer**: CodeSmell, Dependency, Security strategies.
3.  **LLM Layer**: Multi-provider support (GitHub Copilot, Gemini, OpenRouter, Ollama).
4.  **VCS Layer**: Git operations and Pull Requests on Azure DevOps/GitHub.

## Tech Stack Details

- **Core**: Python 3.11
- **Models**: Pydantic v2
- **APIs**: httpx (async), azure-devops, PyGithub
- **Parsing**: PyMuPDF (PDF), pandas (Excel/CSV)
- **Git**: GitPython
- **LLM**: Claude 3.5 Sonnet / GPT-4o
- **Security**: Azure Key Vault
- **Logging**: structlog with tamper-proof hashing
