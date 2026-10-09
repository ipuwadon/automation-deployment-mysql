# Automation Deploy MySQL

## Overview

This project demonstrates a Proof of Concept (POC) for automating MySQL database deployment using:

- GitHub Repository
- GitHub Actions
- Self-hosted Runner
- MySQL Database
- Environment Configuration (.env)

The objective is to automate deployment of SQL scripts from source control to a MySQL development environment.

---

## Project Goals

Current scope:

✅ Source Control for SQL Scripts

✅ Automated Validation

✅ Automated Deployment to DEV Environment

✅ Deployment History Tracking

Future scope:

- Pull Request Approval Process
- UAT Deployment
- Production Deployment
- Rollback Automation
- Release Versioning

---

## Architecture

```text
Developer
    │
    ▼
Feature Branch
    │
    ▼
Git Push
    │
    ▼
GitHub Repository
    │
    ▼
GitHub Action
    │
    ▼
Self-hosted Runner
    │
    ▼
MySQL DEV Environment
```

---

## Project Structure

```text
automation-deploy-mysql
│
├── .github
│   └── workflows
│       └── autodeploy.yml
│
├── releases
│   └── projectA
│       ├── release
│       │   └── 001_create_customer.sql
│       │
│       ├── rollback
│       │   └── 001_drop_customer.sql
│       │
│       └── test
│           └── test_customer.sql
│
├── scripts
│   └── deploy-dev.sh
│
├── .env.dev
├── .gitignore
└── README.md
```

---

## Branch Strategy

Current branch model:

```text
main
│
├── dev
│
├── feature/projectA
├── feature/projectB
└── feature/projectC
```

### Purpose

| Branch | Description |
|----------|----------|
| main | Stable source code |
| dev | Integration branch for deployment to DEV |
| feature/* | Feature development branch |

---

## Deployment Flow

### 1. Development

Developer creates or modifies database objects manually.

Example:

```sql
CREATE TABLE customer (
    customer_id INT PRIMARY KEY,
    customer_name VARCHAR(100)
);
```

Objects are created within:

```text
dev_user
```

---

### 2. Prepare Release Package

Developer prepares:

```text
release script
rollback script
test script
```

Example:

```text
projectA
│
├── release
├── rollback
└── test
```

---

### 3. Commit Changes

```bash
git add .
git commit -m "Create customer table"
```

---

### 4. Push Feature Branch

```bash
git push origin feature/projectA
```

Future validation activities:

- SQL file verification
- Naming convention verification
- Rollback file verification
- Test script verification

---

### 5. Create Pull Request

```text
feature/projectA
        │
        ▼
       dev
```

Reviewer validates:

- Release script
- Rollback script
- Test script

---

### 6. Merge to DEV

Merge triggers:

```yaml
on:
  push:
    branches:
      - dev
```

---

### 7. Automatic Deployment

GitHub Action executes:

```text
deploy-dev.sh
```

which connects to:

```text
MySQL
```

using:

```text
dev_user
```

---

## Environment Configuration

File:

```text
.env.dev
```

Example:

```properties
DB_HOST=localhost
DB_NAME=mydb

DB_USER=dev_user
DB_PASSWORD=password123
```

### Important

Never commit environment files.

Add to:

```text
.gitignore
```

```text
.env*
```

---

## Deployment Script

File:

```text
scripts/deploy-dev.sh
```

Example:

```bash
#!/bin/bash

source .env.dev

mysql \
-h $DB_HOST \
-u $DB_USER \
-p$DB_PASSWORD \
$DB_NAME \
< releases/projectA/release/001_create_customer.sql
```

### Purpose

1. Load environment variables
2. Connect to MySQL
3. Execute release script

---

## Execution

Grant execution permission:

```bash
chmod +x scripts/deploy-dev.sh
```

Execute manually:

```bash
./scripts/deploy-dev.sh
```

---

## GitHub Workflow

File:

```text
.github/workflows/autodeploy.yml
```

Example:

```yaml
name: Deploy DEV

on:
  push:
    branches:
      - dev

jobs:
  deploy:
    runs-on: self-hosted

    steps:
      - uses: actions/checkout@v4

      - name: Deploy SQL Script
        run: |
          ./scripts/deploy-dev.sh
```

---

## Self-hosted Runner

Runner location:

```text
Developer Laptop
or
Linux VM
or
Windows Server
```

Purpose:

- Receive GitHub Action job
- Execute deployment script locally
- Connect to MySQL

Advantages:

- No GitHub Action minute consumption
- Full environment control
- Direct access to internal databases

---

## MySQL Users

Current environment setup:

```text
dev_user
```

Future environment setup:

```text
dev_user
uat_user
prod_user
```

---

## Future Enhancements

### Validation Workflow

Before deployment:

```text
Check release script exists

Check rollback script exists

Check test script exists

Verify naming convention
```

---

### Automated Testing

Execute:

```text
Release Script
        │
        ▼
Test Script
        │
        ▼
Result Validation
```

---

### Rollback

If deployment fails:

```text
Release Failure
       │
       ▼
Execute Rollback
```

---

### Deployment History

Table:

```sql
CREATE TABLE deployment_history (
    release_id VARCHAR(100),
    deployed_at DATETIME,
    status VARCHAR(20)
);
```

Purpose:

- Audit deployment history
- Prevent duplicate deployments
- Support troubleshooting

---

## Current Project Status

### Completed

- MySQL DEV User Created
- GitHub Repository Created
- Repository Cloned to Local Machine

### In Progress

- Repository Structure Setup
- Deployment Script Development
- Self-hosted Runner Configuration

### Next Milestone

- Deploy SQL Script Automatically After Merge to DEV Branch