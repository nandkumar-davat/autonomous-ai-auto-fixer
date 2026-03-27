# GitHub App Authentication Setup Guide

## Why GitHub Apps?
- More secure than Personal Access Tokens
- Fine-grained repository permissions
- Better audit logging
- Can be installed organization-wide

## Setup Steps:

### 1. Create GitHub App
- Go to GitHub Organization Settings → Developer settings → GitHub Apps
- Create a new app with these permissions:
  - Repository permissions:
    - Contents: Write
    - Pull requests: Write
    - Metadata: Read
  - Subscribe to Push events

### 2. Generate Private Key
- Download the private key file (.pem)
- Store it securely in Azure Key Vault

### 3. Update Configuration
```yaml
vcs:
  primary: github
  github:
    app_id: 123456  # Your App ID
    installation_id: 789012  # Installation ID

secrets:
  github_app_private_key_secret_name: "github-app-private-key"
```

### 4. Install App
- Install the GitHub App on your target repositories
- Note the Installation ID from the URL

## Benefits:
- Repository-scoped access
- Automatic token refresh
- Better security audit trail
- No user dependency