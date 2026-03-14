# Human Verification & Testing Guide

This guide outlines how a human reviewer can verify the agent's functionality across different scenarios.

## 1. Setup for Testing

1.  **Virtual Environment**: Ensure `.venv` is active.
2.  **Mock Data**: Place sample reports (JSON/CSV) in a `reports/` directory if testing file-based ingestion.
3.  **Config**: Ensure `config/default.yaml` points to your test repository.

## 2. Test Scenarios

### Scenario A: Dry-Run Safety
- **Action**: `autofixer --mode dry-run`
- **Verification**: Check logs for "Findings detected" and "No changes applied". Verify local code is untouched.

### Scenario B: Automatic Code Smell Fix
- **Action**: Create a Python file with unused imports, then run `autofixer --mode fix`.
- **Verification**: Verify the agent creates a branch, removes the import, and submits a PR.

### Scenario C: Security Patching (Dockerfile)
- **Action**: Use a Dockerfile with a vulnerable base image (reported in a Trivy JSON).
- **Verification**: Verify the agent updates the `FROM` tag to the recommended version.

### Scenario D: Self-Correction Loop
- **Action**: Provide a finding where a simple fix would cause a linting error (break syntax).
- **Verification**: Monitor logs for "Validation failed" followed by a successful retry.

### Scenario E: PR Comment Interaction
- **Action**: Comment on an agent-created PR and wait for the monitor interval.
- **Verification**: Verify the agent pushes a follow-up commit addressing your comment.
