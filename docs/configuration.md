# Configuration & Ingestion Guide

This guide explains how to provide source details (APIs) and local report files (JSON, Excel, PDF) to the Autonomous AI Auto-Fixer.

---

## 1. API-Based Ingestion (Automated)

For continuous monitoring, details are provided in `config/default.yaml` or through **Environment Variables**.

### API Details Configuration
In your `config/default.yaml`, update the `ingestion` section:

```yaml
ingestion:
  sonarqube:
    url: "https://sonarqube.yourcompany.com"
    project_key: "your_project"
  mend:
    org_token: "your-org-token"
    user_key: "your-user-key"
  trivy:
    server_url: "http://trivy-server:8080"
```

### Branch Configuration
By default, the agent works on the `main` branch. You can change this globally in `config/default.yaml` or per execution via the CLI.

```yaml
agent:
  base_branch: "main"  # The source branch to scan and branch off from
```

### Credentials & Secrets
**Do not hardcode tokens in YAML.** The system retrieves them automatically via:
1.  **Azure Key Vault**: Recommended for production. The agent looks for secrets named `sonarqube-token`, `mend-user-key`, etc.
2.  **Environment Variables**: The agent checks for:
    - `SONARQUBE_TOKEN`
    - `MEND_USER_KEY`
    - `TRIVY_TOKEN`

---

## 2. File-Based Ingestion (Manual/Report Mode)

If you have exported reports (PDF, CSV, Excel, JSON) and want the agent to fix them without calling an API, use the CLI or the local `reports/` directory.

### Combined CLI Usage (Recommended for Local Reports)
You can pass the path to a report file and specify the target repository simultaneously. This ensures the agent precisely maps external findings to your local source code.
```bash
# Ingest a Mend PDF report and apply fixes to a specific repository
autofixer --mode fix --input-file "./manual_reports/mend_vulnerabilities.pdf" --repo "my-org/web-app"

# Ingest a SonarQube JSON export and dry-run fixes for a project
autofixer --mode dry-run --input-file "./exports/sonar_issues.json" --repo "enterprise/backend-service"

# Ingest a Trivy SARIF report for a container and generate PRs
autofixer --mode fix --input-file "./scans/trivy_output.sarif" --repo "infrastructure/docker-images"
```

### Local Scanning Directory
By default, the agent is configured to look into a `data/inputs/` directory. Any supported file placed here will be processed during a scan:
- **SonarQube**: `.json`
- **Mend**: `.csv`, `.xlsx`, `.pdf`
- **Trivy**: `.sarif`, `.json`

---

## 3. Mapping Sources to Repositories
The agent needs to know which finding belongs to which repository.
- **For APIs**: The `project_key` or `repo_name` in the metadata must match the `--repo` flag you pass in the CLI.
- **For Files**: The agent attempts to extract the file path from the report. If the report says `src/main.py` is vulnerable, the agent will look for that file in the workspace of the repository you specified.

---

## Summary of Input Locations

| Source | API Location | File Location |
| :--- | :--- | :--- |
| **SonarQube** | `config/default.yaml` (URL + Token) | `--input-file report.json` |
| **Mend** | `config/default.yaml` (Org Token) | `--input-file report.pdf/xlsx/csv` |
| **Trivy** | `config/default.yaml` (Server URL) | `--input-file report.sarif` |
