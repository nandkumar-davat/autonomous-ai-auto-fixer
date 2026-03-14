# Deployment & Execution Guide

This guide explains how to deploy the Autonomous AI Auto-Fixer, how to trigger scans for specific repositories, and where to find the results.

---

## 1. Where to Deploy

The application is containerized and designed for enterprise deployment in the following environments:

*   **Azure Container Apps / Kubernetes (AKS)**: Recommended for production. Use the provided `Dockerfile`. Ensure the hosting environment has a **Managed Identity** with access to your Azure Key Vault.
*   **GitHub Actions / Azure Pipelines**: Can be run as a scheduled job or a "ChatOps" trigger.
*   **Local / Private VM**: For testing, use `docker-compose.yml`.

---

## 2. How to Run

The agent is controlled via a CLI entrypoint named `autofixer` (or `python -m autofixer.main`).

### Local Execution (Venv)
Once installed via `pip install -e .`, you can run the agent. You can specify the target repository and the base branch to work on.

```bash
# Dry-run against 'develop' branch of a specific repo
autofixer --mode dry-run --repo "my-org/my-repo" --branch "develop"

# Apply fixes using a local Mend report against the default 'main' branch
autofixer --mode fix --repo "my-org/my-target-repo" --input-file "./reports/mend_scan.pdf"
```

**Note on Branches:**
- **Default**: If `--branch` is not specified, the agent defaults to `main`.
- **Behavior**: The agent clones/pulls the specified branch and creates new feature branches (e.g., `fix/sonarqube-S1128`) off of it.

### Docker Execution
```bash
docker build -t autofixer .
docker run --env-file .env autofixer --mode fix --repo "my-org/my-target-repo"
```

---

## 3. Passing Repositories to Scan

You have two ways to define the target:

1.  **CLI Flag**: Use the `--repo` parameter as shown above. This tells the agent to filter ingestion results (SonarQube/Mend/Trivy) for that specific project key or repository name.
2.  **Configuration**: You can define a list of "monitored repositories" in your `config/default.yaml` under the `monitored_repos` section.

---

## 4. Where to Check Generated PRs

The agent submits fixes directly to your Version Control System.

### For Azure DevOps (Primary)
1.  Navigate to your Project in **Azure DevOps**.
2.  Go to **Repos** > **Pull Requests**.
3.  Look for PRs titled: `[Auto-Fix] <Issue Type>: <Short Description>`.
4.  The PR description will contain:
    - The original finding (SonarQube/Mend/Trivy link).
    - The reasoning behind the fix.
    - Linter/Build validation status.

### For GitHub (Secondary)
1.  Navigate to the **Pull Requests** tab of your repository.
2.  Look for PRs created by your **GitHub App** (or the account associated with your PAT).
3.  Review the automated description and code diff.

### Human-in-the-Loop Feedback
You can comment directly on the PR. If you ask for changes (e.g., "Change this to a list comprehension"), the `PRMonitor` (running in the background) will detect your comment and attempt to refine the fix automatically.
