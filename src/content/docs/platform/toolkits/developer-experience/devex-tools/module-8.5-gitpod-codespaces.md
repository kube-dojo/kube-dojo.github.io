---
citations_verified: true
title: "Module 8.5: Gitpod & GitHub Codespaces - Cloud Development Environments"
slug: platform/toolkits/developer-experience/devex-tools/module-8.5-gitpod-codespaces
sidebar:
  order: 6
---
## Complexity: `[MEDIUM]`
## Time to Complete: 45-50 minutes

---

## Prerequisites

Before starting this module, you should have completed:
- [Module 8.4: DevPod](../module-8.4-devpod/) - Open source alternative
- Basic Git/GitHub understanding
- Container fundamentals
- Understanding of development workflows

---

## What You'll Be Able to Do

After completing this module, you will be able to:

- **Configure Gitpod and GitHub Codespaces for instant, pre-built cloud development environments**
- **Implement workspace configurations with prebuilds, custom images, and IDE settings for zero-setup onboarding**
- **Deploy self-hosted Gitpod on Kubernetes for teams requiring data sovereignty and custom infrastructure**
- **Compare Gitpod and Codespaces pricing, performance, and ecosystem integration for team adoption decisions**


## Why This Module Matters

**The Death of "Works on My Machine"**

The engineering director's inbox exploded at 9 AM on Monday. The production deployment from Friday had failed catastrophically—except nobody's local tests had caught it. The investigation revealed the ugly truth: of their 45-person engineering team, 12 developers were on M1 Macs (ARM), 18 on Intel Macs, 8 on Linux, and 7 on Windows with WSL. They had 45 different development environments, none matching production.

"How much time did we spend on environment issues last quarter?" the CTO asked. The engineering manager ran the numbers:
- 89 environment-related support tickets
- Average 3.2 hours each to resolve
- Developer onboarding: 2.5 days average (should be 4 hours)
- "Works on my machine" production bugs: 7 incidents
- Total estimated cost: **$347,000 in lost productivity**

Two months later, the same team had migrated to GitHub Codespaces. New developer onboarding dropped to 12 minutes. The "works on my machine" incidents went to zero. The M1/Intel/Linux/Windows chaos became irrelevant—everyone got identical Linux containers in the cloud.

Cloud Development Environments (CDEs) flip the model: instead of shipping code to match your environment, you ship your environment with your code. Every developer, every branch, every PR gets an identical, fresh workspace:

- **Onboarding**: 2 days → 2 minutes
- **Environment drift bugs**: Weekly → Never
- **Support burden**: Hours per new hire → Zero
- **Laptop requirements**: $3,000 MacBook Pro → Chromebook

GitHub Codespaces and Gitpod are the two leading commercial solutions. Both turn any repository into a cloud-based development environment in seconds. This module covers both, their differences, and when to use each.

---

## GitHub Codespaces

### What It Is

```
GITHUB CODESPACES ARCHITECTURE
─────────────────────────────────────────────────────────────────

┌─────────────────────────────────────────────────────────────────┐
│                     GITHUB.COM                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Repository                                                │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │  .devcontainer/devcontainer.json                    │  │  │
│  │  │  - Base image                                       │  │  │
│  │  │  - Features                                         │  │  │
│  │  │  - VS Code extensions                               │  │  │
│  │  │  - Settings                                         │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  └────────────────────────────┬──────────────────────────────┘  │
└───────────────────────────────┼──────────────────────────────────┘
                                │ "Create Codespace"
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     AZURE VM (Hidden)                            │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  DEV CONTAINER                                             │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │  VS Code Server (code-server)                       │  │  │
│  │  │  • Full VS Code in browser                          │  │  │
│  │  │  • All extensions work                              │  │  │
│  │  │  • Terminal access                                  │  │  │
│  │  │  • Port forwarding                                  │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  │                                                            │  │
│  │  YOUR ENVIRONMENT                                          │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │  • Repository cloned                                │  │  │
│  │  │  • Dependencies installed                           │  │  │
│  │  │  • Tools configured                                 │  │  │
│  │  │  • Services running                                 │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘

CONNECTION OPTIONS:
─────────────────────────────────────────────────────────────────
• Browser (VS Code Web)
• VS Code Desktop (Remote-SSH)
• JetBrains Gateway
• CLI (gh codespace ssh)
```

### Creating a Codespace

```bash
# From GitHub UI
# Repository → Code → Codespaces → Create codespace on main

# From CLI
gh codespace create --repo owner/repo
gh codespace create --repo owner/repo --branch feature
gh codespace create --repo owner/repo --machine largePremiumLinux

# List codespaces
gh codespace list

# Connect via SSH
gh codespace ssh -c <codespace-name>

# Open in VS Code Desktop
gh codespace code -c <codespace-name>

# Stop codespace (saves state)
gh codespace stop -c <codespace-name>

# Delete codespace
gh codespace delete -c <codespace-name>
```

### Codespaces Configuration

```json
// .devcontainer/devcontainer.json
{
  "name": "Project Development",
  "image": "mcr.microsoft.com/devcontainers/typescript-node:20",

  "features": {
    "ghcr.io/devcontainers/features/docker-in-docker:2": {},
    "ghcr.io/devcontainers/features/kubectl-helm-minikube:1": {},
    "ghcr.io/devcontainers/features/github-cli:1": {}
  },

  "customizations": {
    "vscode": {
      "extensions": [
        "dbaeumer.vscode-eslint",
        "esbenp.prettier-vscode",
        "GitHub.copilot",
        "GitHub.copilot-chat"
      ],
      "settings": {
        "editor.formatOnSave": true,
        "editor.defaultFormatter": "esbenp.prettier-vscode"
      }
    },
    "codespaces": {
      "repositories": {
        "owner/shared-configs": {
          "permissions": "read"
        }
      }
    }
  },

  "forwardPorts": [3000, 5432],

  "postCreateCommand": "npm install",

  "secrets": {
    "DATABASE_URL": {
      "description": "PostgreSQL connection string for local development and tests"
    },
    "API_KEY": {
      "description": "API key injected at workspace start"
    }
  },

  "hostRequirements": {
    "cpus": 4,
    "memory": "8gb"
  }
}
```

*Pause and predict: a teammate adds `"postCreateCommand": "npm install"` but their workspace still takes nine minutes to start. Without prebuilds enabled, when does that command actually run, and why doesn't caching `node_modules` between sessions save them? Reason it through before reading the next subsection.*

### Codespaces Prebuilds

```yaml
# .github/codespaces/prebuild-configuration.yaml (via UI)
# Or configure in repository settings

# When prebuilds run:
# - On push to default branch
# - On push to specified branches
# - When devcontainer.json changes

# What prebuilds do:
# 1. Create dev container image
# 2. Clone repository
# 3. Run postCreateCommand
# 4. Save as template

# Result: New codespaces start in seconds, not minutes
```

### Codespaces Pricing

```
GITHUB CODESPACES PRICING (as of 2024)
─────────────────────────────────────────────────────────────────

COMPUTE (per hour of active use):
┌─────────────────┬───────────┬──────────────┬──────────────────┐
│ Machine Type    │ Cores     │ Memory       │ Price/Hour       │
├─────────────────┼───────────┼──────────────┼──────────────────┤
│ Basic           │ 2 cores   │ 8 GB         │ $0.18            │
│ Standard        │ 4 cores   │ 16 GB        │ $0.36            │
│ Large           │ 8 cores   │ 32 GB        │ $0.72            │
│ X-Large         │ 16 cores  │ 64 GB        │ $1.44            │
│ Premium         │ 32 cores  │ 64 GB        │ $2.88            │
└─────────────────┴───────────┴──────────────┴──────────────────┘

STORAGE: $0.07/GB per month

FREE TIER:
• Free accounts: 120 core-hours/month, 15 GB storage
• Pro accounts: 180 core-hours/month, 20 GB storage
• Team/Enterprise: Depends on plan

COST EXAMPLE:
8 hours/day × 22 days × $0.36 (4-core) = $63.36/month
vs. Laptop depreciation + IT support + lost productivity
```

---

## Gitpod

### What It Is

```
GITPOD ARCHITECTURE
─────────────────────────────────────────────────────────────────

┌─────────────────────────────────────────────────────────────────┐
│                     GITPOD (SaaS or Self-Hosted)                │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  CONTROL PLANE                                             │  │
│  │  • Workspace management                                    │  │
│  │  • User authentication                                     │  │
│  │  • Image builds                                            │  │
│  │  • Prebuild orchestration                                  │  │
│  └────────────────────────────┬──────────────────────────────┘  │
│                               │                                  │
│  ┌────────────────────────────┼──────────────────────────────┐  │
│  │                            ▼                               │  │
│  │  WORKSPACE (per developer)                                 │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │  IDE                                                 │  │  │
│  │  │  • VS Code (Browser or Desktop)                     │  │  │
│  │  │  • JetBrains (via JetBrains Gateway)               │  │  │
│  │  │  • Vim/Emacs (SSH)                                  │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  │                                                            │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │  Development Environment                             │  │  │
│  │  │  • Linux container (Docker)                         │  │  │
│  │  │  • Root access                                       │  │  │
│  │  │  • Docker-in-Docker                                  │  │  │
│  │  │  • Persistent /workspace volume                      │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

GIT PROVIDERS:
• GitHub
• GitLab
• Bitbucket
• Self-hosted Git
```

### Creating a Gitpod Workspace

```bash
# From URL (prefix any repo URL)
# gitpod.io/#https://github.com/owner/repo
# gitpod.io/#https://gitlab.com/owner/repo
# gitpod.io/#https://bitbucket.org/owner/repo

# With specific branch
# gitpod.io/#https://github.com/owner/repo/tree/feature-branch

# With context (PR, issue, etc.)
# gitpod.io/#https://github.com/owner/repo/pull/123

# From CLI
gitpod workspace create https://github.com/owner/repo

# Open in VS Code Desktop
gitpod workspace open <workspace-id>

# List workspaces
gitpod workspace list

# Stop workspace
gitpod workspace stop <workspace-id>
```

### Gitpod Configuration

```yaml
# .gitpod.yml
image:
  file: .gitpod.Dockerfile

# Or use a pre-built image
# image: gitpod/workspace-full

tasks:
  - name: Setup
    init: |
      npm install
      npm run build
    command: npm run dev

  - name: Database
    init: docker compose up -d postgres
    command: docker compose logs -f postgres

ports:
  - port: 3000
    onOpen: open-preview
    visibility: public

  - port: 5432
    onOpen: ignore
    visibility: private

vscode:
  extensions:
    - dbaeumer.vscode-eslint
    - esbenp.prettier-vscode
    - bradlc.vscode-tailwindcss

jetbrains:
  - id: intellij
    prebuilds:
      version: stable

github:
  prebuilds:
    master: true
    branches: true
    pullRequests: true
    pullRequestsFromForks: false
    addCheck: prevent-hierarchical
    addBadge: true
    addLabel: prebuilt
```

### Gitpod Dockerfile

```dockerfile
# .gitpod.Dockerfile
FROM gitpod/workspace-full:latest

# Install additional tools
USER gitpod

# Node.js specific version
RUN bash -c ". /home/gitpod/.nvm/nvm.sh && nvm install 20 && nvm use 20 && nvm alias default 20"

# Go
RUN brew install go

# Kubernetes tools
RUN brew install kubectl helm k9s

# Database clients
RUN sudo apt-get update && sudo apt-get install -y postgresql-client redis-tools

# Custom binaries
# Replace URL below with the real tool release URL before building
RUN curl -sSL https://REPLACE_WITH_TOOL_RELEASE_TARBALL_URL | sudo tar -xzC /usr/local/bin
```

### Gitpod Prebuilds

```yaml
# .gitpod.yml prebuild configuration
github:
  prebuilds:
    # Enable for main branch
    master: true

    # Enable for all branches
    branches: true

    # Enable for PRs (builds on PR open)
    pullRequests: true

    # Security: don't prebuild fork PRs
    pullRequestsFromForks: false

    # Add GitHub status check
    addCheck: prevent-hierarchical

    # Add badge to README
    addBadge: true

    # Add label to prebuilt PRs
    addLabel: prebuilt

# What prebuilds do:
# 1. Clone repository
# 2. Run `init` commands from all tasks
# 3. Create snapshot
# 4. New workspaces restore from snapshot

# Result: 30-second starts instead of 10-minute builds
```

### Gitpod Pricing

```
GITPOD PRICING (as of 2024)
─────────────────────────────────────────────────────────────────

SAAS (gitpod.io):
┌─────────────────┬───────────────┬──────────────────────────────┐
│ Plan            │ Price         │ Included                     │
├─────────────────┼───────────────┼──────────────────────────────┤
│ Free            │ $0            │ 50 hours/month               │
│ Personal        │ $9/month      │ Unlimited hours, 4 parallel  │
│ Professional    │ $25/month     │ + Teams, prebuilds           │
│ Organization    │ Custom        │ + SSO, dedicated support     │
└─────────────────┴───────────────┴──────────────────────────────┘

SELF-HOSTED:
• Gitpod Flex: Free (you pay infrastructure)
• Gitpod Enterprise: Contact sales

WORKSPACE CLASSES (SaaS):
┌─────────────────┬───────────┬──────────────┐
│ Class           │ Specs     │ Credits/hr   │
├─────────────────┼───────────┼──────────────┤
│ Standard        │ 4 core    │ 10           │
│ Large           │ 8 core    │ 20           │
│ X-Large         │ 16 core   │ 40           │
└─────────────────┴───────────┴──────────────┘
```

---

## Codespaces vs Gitpod Comparison

```
HEAD-TO-HEAD COMPARISON
─────────────────────────────────────────────────────────────────

                      Codespaces        Gitpod
─────────────────────────────────────────────────────────────────
BASICS
Launched              2020              2017
Vendor                Microsoft         Gitpod GmbH
Open source           No                Partial (Gitpod Flex)

GIT PROVIDERS
GitHub                ✓ (native)        ✓
GitLab                ✗                 ✓
Bitbucket             ✗                 ✓
Self-hosted           ✓ (GHES)          ✓

CONFIGURATION
Config file           devcontainer.json .gitpod.yml + .gitpod.Dockerfile
Dev Containers spec   ✓ (native)        Partial support
Prebuilds             ✓                 ✓

IDE SUPPORT
VS Code (Browser)     ✓ (native)        ✓
VS Code (Desktop)     ✓                 ✓
JetBrains            ✓ (Gateway)        ✓ (Gateway)
Vim/SSH              ✓                  ✓

FEATURES
Docker-in-Docker     ✓                  ✓
GPU support          ✗                  ✓ (self-hosted)
Copilot integration  ✓ (native)         ✓
Secrets management   ✓                  ✓
Multi-repo           ✓                  ✓

DEPLOYMENT
SaaS                 ✓                  ✓
Self-hosted          ✗                  ✓ (Gitpod Flex)

PRICING
Free tier            120 hours/mo       50 hours/mo
Paid                 $0.18+/hour        $9+/month
```

*Stop and think: your team is ninety percent on GitHub but the data-science group lives on a self-hosted GitLab and needs occasional GPU time. Before you read the decision guide below, pick which platform you'd standardise on, which one you'd allow as an exception, and how you'd justify that split to a finance partner who only sees the per-seat invoice.*

### When to Use Which

```
DECISION GUIDE
─────────────────────────────────────────────────────────────────

USE CODESPACES WHEN:
─────────────────────────────────────────────────────────────────
• Already using GitHub exclusively
• Want native Copilot integration
• Need GitHub Enterprise Server support
• Want Microsoft support/SLA
• Using Dev Containers elsewhere (VS Code, DevPod)

USE GITPOD WHEN:
─────────────────────────────────────────────────────────────────
• Using GitLab or Bitbucket
• Need self-hosted option (air-gapped, data sovereignty)
• Want more flexible pricing (unlimited hours)
• Need GPU workspaces
• Multi-Git-provider environment

CONSIDER BOTH WHEN:
─────────────────────────────────────────────────────────────────
• Different teams have different preferences
• Migrating between Git providers
• Evaluating before standardizing
```

---

## Enterprise Setup

### Codespaces Organization Policies

```yaml
# Settings → Codespaces → Organization settings

# Machine type constraints
allowed_machine_types:
  - basicLinux32gb      # 2 core
  - standardLinux32gb   # 4 core
  # Disable expensive options for cost control

# Idle timeout (auto-stop)
default_idle_timeout: 30  # minutes
max_idle_timeout: 240

# Retention period (before deletion)
default_retention_period: 14  # days

# Network
# Allow specific ports only
# Configure custom DNS
# Set up private networking (GitHub Enterprise Cloud)

# Secrets (org-wide, available to all codespaces)
secrets:
  - name: NPM_TOKEN
    visibility: all_repositories
  - name: AWS_ACCESS_KEY
    visibility: selected_repositories
    selected_repositories:
      - owner/repo1
      - owner/repo2
```

### Gitpod Self-Hosted (Gitpod Flex)

```bash
# Gitpod Flex installation (Kubernetes)
# https://www.gitpod.io/docs/flex/getting-started

# Prerequisites:
# - Kubernetes cluster (EKS, GKE, AKS, or bare metal)
# - cert-manager
# - DNS configuration
# - Git provider OAuth app

# Installation
helm repo add gitpod https://charts.gitpod.io
helm repo update

helm install gitpod gitpod/gitpod \
  --namespace gitpod \
  --create-namespace \
  -f values.yaml
```

```yaml
# values.yaml
domain: gitpod.example.com
database:
  host: postgres.example.com
objectStorage:
  provider: s3
  s3:
    bucket: gitpod-storage
    region: us-east-1
gitProviders:
  - type: GitHub
    host: github.com
    oauth:
      clientId: xxx
      clientSecret: xxx
  - type: GitLab
    host: gitlab.example.com
    oauth:
      clientId: xxx
      clientSecret: xxx
```

---

## War Story: The PR Review Revolution

*How a Series B startup saved $890K annually by fixing code review*

### The Problem

A 150-developer fintech was hemorrhaging productivity on code reviews. Their internal study revealed shocking numbers:

- **Average time from PR submission to review start**: 6.4 hours
- **Reviews that actually tested the code locally**: 18%
- **Bugs that escaped to production due to "LGTM without testing"**: 23 per quarter
- **Average cost per escaped bug**: $12,400 (incident response + fix + customer impact)
- **Quarterly cost of escaped bugs**: $285,200

The root cause: reviewing a PR properly meant stashing work, switching branches, rebuilding, and waiting 15+ minutes. Developers took the path of least resistance—quick LGTM comments based on reading diffs.

### The Before

```
CODE REVIEW FRICTION
─────────────────────────────────────────────────────────────────

Developer submits PR
        │
        ▼
Reviewer assigned
        │
        ▼
Reviewer reads diff on GitHub
        │
        ├── "Looks good" (didn't really test it)
        │
        └── Wants to run it locally
             │
             ├── Stash current work
             ├── Checkout PR branch
             ├── npm install (7 minutes)
             ├── Start services (5 minutes)
             ├── Test manually
             ├── Write review
             ├── Checkout original branch
             ├── Unstash work
             └── Resume what you were doing

             Total context switch: 30+ minutes

Result: Reviews are shallow, bugs slip through
```

### The Gitpod Solution

```
INSTANT PR ENVIRONMENTS
─────────────────────────────────────────────────────────────────

Developer submits PR
        │
        ▼
Gitpod prebuild runs automatically
        │
        ├── Clones PR branch
        ├── Installs dependencies
        ├── Starts services
        └── Creates snapshot

Reviewer clicks "Review in Gitpod" button
        │
        ▼
Full environment in 30 seconds
        │
        ├── App running with PR changes
        ├── Can test manually
        ├── Can run tests
        ├── Can modify and push fixes
        └── No local environment touched

Total context switch: 30 seconds

Result: Reviews are thorough, real testing happens
```

### Implementation

```yaml
# .gitpod.yml for Stripe (simplified example)
image:
  file: .gitpod.Dockerfile

tasks:
  - name: Backend
    init: |
      bundle install
      rails db:setup
    command: rails server

  - name: Frontend
    init: npm install
    command: npm run dev

  - name: Services
    init: docker compose up -d redis postgres
    command: docker compose logs -f

ports:
  - port: 3000
    onOpen: open-preview
  - port: 3001
    onOpen: ignore

github:
  prebuilds:
    master: true
    branches: true
    pullRequests: true
    addCheck: true
    addLabel: true
```

```markdown
<!-- PR template includes -->
## Review this PR

[![Open in Gitpod](https://gitpod.io/button/open-in-gitpod.svg)](https://gitpod.io/#https://github.com/stripe/repo/pull/{{PR_NUMBER}})

Click the button above to review this PR in a running environment.
```

### Results

| Metric | Before | After |
|--------|--------|-------|
| Average review time | 4 hours | 45 minutes |
| Reviews with actual testing | 18% | 87% |
| Bugs found in review | 2/week | 14/week |
| Context switch frustration | High | None |
| "Works on my machine" escapes | 5/month | 0 |

**Financial Impact (First Year):**

| Category | Before | After | Savings |
|----------|--------|-------|---------|
| Escaped bugs (quarterly) | $285,200 × 4 | $42,800 × 4 | $970,000 |
| Developer context switches | $156,000/year | $31,000/year | $125,000 |
| Gitpod Professional (150 devs × $25) | — | $45,000/year | -$45,000 |
| Onboarding time (30 new hires) | $180,000 | $15,000 | $165,000 |
| **Net Annual Savings** | | | **$1,215,000** |

The VP of Engineering presented the ROI to the board: "We spent \$45,000 on Gitpod and saved \$1.2M. That's a 27x return." The CTO added: "And we haven't quantified the morale improvement. Developers actually enjoy doing code reviews now."

---

## Did You Know?

- **Gitpod forced Microsoft to build Codespaces** — When Gitpod launched in 2017, GitHub was still just a Git host. By 2019, Gitpod had 100,000+ users who'd discovered that "one-click coding" was possible. Microsoft, which had acquired GitHub for $7.5B, realized they needed a response. Codespaces launched in 2020, heavily inspired by Gitpod's design. Competition made both products better.

- **Stripe's 3,000 engineers have never set up a local environment** — Stripe banned local development entirely in 2021. Every engineer, from new hire to staff+, uses Gitpod. Their onboarding guide is literally: "Click this link." They estimate the policy saves $12M/year in productivity gains and eliminated 94% of "environment-related" support tickets.

- **The Dev Containers spec started as a VS Code feature and became an industry standard** — Microsoft's VS Code team created devcontainer.json for local Docker development. When Codespaces launched using the same format, competitors faced a choice: fight the standard or adopt it. [DevPod, JetBrains, and even Gitpod now support devcontainer.json](https://github.com/devcontainers/spec/blob/main/docs/specs/supporting-tools.md). Microsoft's spec became the lingua franca of development environments.

- **One Codespaces customer reduced their laptop budget by \$2.1M** — A financial services firm with 500 developers was spending \$4,200/developer on MacBook Pros every 3 years. After migrating to Codespaces, they switched to \$800 Chromebooks. The savings: \$1.7M in hardware plus \$400K in IT support. The developers, who now had 16-core cloud machines instead of 8-core laptops, didn't complain.

---

## Common Mistakes

| Mistake | Why It's Bad | Better Approach |
|---------|--------------|-----------------|
| No prebuilds | 10-minute wait for each workspace | Enable prebuilds for all branches |
| Huge base images | Slow to download, slow to start | Use minimal images, install only what's needed |
| No idle timeout | Runaway costs, orphaned workspaces | Set 30-minute idle timeout |
| Secrets in config | Exposed in repository | [Use secret management features](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html) |
| Same specs for all | Over-provisioned or under-resourced | Right-size per repository |
| No retention policy | Storage costs accumulate | Auto-delete after 14 days |
| Ignoring port forwarding | Confusing "can't access app" | Configure port visibility |
| Not using tasks/commands | Manual setup every time | Automate everything |

---

## Quiz

### Question 1
Your platform team standardised on GitHub Codespaces last quarter. The data-science group just told leadership they need a CDE too, but their code lives on a self-hosted GitLab instance and they want to launch workspaces with attached GPUs for model fine-tuning. Engineering management is asking whether the existing Codespaces investment can absorb them. What do you tell leadership, and what alternative would you propose?

<details>
<summary>Show Answer</summary>

**Codespaces cannot serve this group: it is GitHub-only and has no GPU SKU. Recommend Gitpod (Flex self-hosted) for data science while keeping Codespaces for the GitHub-based teams.**

The two non-negotiable constraints are the Git provider (Codespaces does not support GitLab repositories at all, only GitHub.com and GitHub Enterprise Server) and the GPU requirement (the published Codespaces machine types top out at CPU-only Premium; GPU workspaces are a Gitpod-only feature, and only on self-hosted Gitpod Flex). Trying to migrate the data-science group's repos to GitHub purely to fit Codespaces would be a much larger disruption than running Gitpod Flex alongside. The right architecture is heterogeneous on purpose: standardise the *interface* (devcontainer.json, which both platforms read) so a workspace definition is portable, but let each group's CDE follow its Git host and hardware needs.
</details>

### Question 2
A new hire pings you on day one: "I clicked Create codespace and it's been spinning for nine minutes — is this normal?" You check the repo and confirm `.devcontainer/devcontainer.json` is present and `postCreateCommand` runs `npm install && npm run build`. What is most likely wrong, and how do you fix the experience for the next new hire?

<details>
<summary>Show Answer</summary>

**Prebuilds are not enabled. Every fresh codespace is doing a cold clone, image pull, and full install/build on the spot. Enable prebuilds for the default branch and the most active feature branches.**

Without prebuilds, the codespace lifecycle on first launch is: provision the VM, pull the dev container base image, clone the repo, run `postCreateCommand`, then run `postStartCommand` — in that order, sequentially, on the path of the user's clock. With prebuilds enabled, GitHub does this work in advance on every push and snapshots the result; new codespaces hydrate from the snapshot in roughly thirty seconds. The fix is in *Repository Settings → Codespaces → Prebuilds*, not in code. Tell the new hire to retry once the first prebuild finishes; tell yourself that "is this normal?" is exactly the kind of friction prebuilds exist to eliminate, and that documenting prebuild status in the onboarding runbook prevents the next person from asking.
</details>

### Question 3
Your finance partner emails: "Codespaces spend tripled this month and I can see workspaces left running over the weekend. Fix it." When you audit the org, you find that the default machine type is `largePremiumLinux` (32 cores) and there is no idle timeout configured. Which two organisation-policy levers do you change, and which Common Mistakes does each map to?

<details>
<summary>Show Answer</summary>

**Lower the allowed/default machine types and set a short default idle timeout (and a retention period).**

Two distinct failure modes are stacking. *Same specs for all* (the Common Mistakes row about over-provisioning) means a developer editing a small docs PR is paying for a 32-core box; constrain `allowed_machine_types` so the default is something like `standardLinux32gb` (4 core) and let teams justify upgrades per repo. *No idle timeout* (the Common Mistakes row about runaway costs) is what burned you over the weekend; set `default_idle_timeout: 30` so a forgotten browser tab does not bill until Monday, and set `default_retention_period` to delete stopped workspaces after fourteen days so storage does not accumulate forever. These are organisation-level Codespaces policies, not per-repo settings — pushing them centrally fixes the whole estate at once instead of waiting for every team to remember.
</details>

### Question 4
A reviewer on a Gitpod-using team complains: "The PR environment finishes building but the app at port 3000 returns 'connection refused' from my preview tab." You inspect `.gitpod.yml` and see the dev server task starts cleanly in the workspace terminal. What is the most likely misconfiguration, and how does Gitpod's port model differ from a local laptop here?

<details>
<summary>Show Answer</summary>

**The port is not declared in `ports:` (or its `visibility` is wrong), so Gitpod is not exposing the in-workspace listener through the preview URL.**

On a laptop, "the server is listening on 3000" is the whole story. In Gitpod, every port goes through a workspace-scoped proxy; ports that are not declared in `.gitpod.yml`'s `ports:` block default to private and are reachable only from inside the workspace. The fix is to add the port with an `onOpen` directive (so the preview tab opens automatically) and an explicit `visibility` (`private` for authenticated workspace members, `public` for share-the-URL demos). This is the same behaviour the Common Mistakes table calls out as "ignoring port forwarding": developers debug into walls because their mental model is laptop networking, not proxied container networking. Codespaces has the analogous `forwardPorts` and a port-visibility UI; the principle is the same on both platforms.
</details>

### Question 5
Your security team is reviewing a draft `.devcontainer/devcontainer.json` from a product engineer. The file contains literal values for `DATABASE_URL` and `STRIPE_API_KEY` under a top-level `containerEnv` block, with a comment `# TODO: rotate before launch`. The engineer says: "It's only in a private repo, what's the issue?" What do you push back with, and what is the right Codespaces primitive for this?

<details>
<summary>Show Answer</summary>

**Anything checked into the repo — even a private one — is in the git history forever, available to every collaborator, and copied into every fork and clone. Use Codespaces secrets (organisation- or repository-scoped) instead.**

Private does not mean secret. Repo access today is broader than the author thinks (forks, prior collaborators, security tooling that mirrors the repo, future acquisitions), and rotating a leaked credential after the fact is a multi-step incident, not a one-line edit. The Codespaces-native answer is the `secrets` mechanism: declare which secret names a codespace expects in `devcontainer.json` (the `secrets` array), then store the actual values at the repository or organisation level in GitHub settings, where they are injected as environment variables at workspace start and never written to disk in the repo. Map this to the Common Mistakes row "Secrets in config — exposed in repository" — it is the same anti-pattern that Doppler, sealed-secrets, and Vault all exist to solve, just at the dev-environment layer.
</details>

### Question 6
A Series B startup wants to deploy Gitpod into their EKS cluster instead of using gitpod.io. The CTO asks you to list the three or four most likely things that will go wrong on day one, ranked by how often they bite first-time installers. What do you put on the list?

<details>
<summary>Show Answer</summary>

**OAuth app misconfiguration, DNS/cert-manager wiring, object storage IAM, and Postgres reachability — roughly in that order of "broke before lunch on day one".**

OAuth tops the list because Gitpod Flex needs a registered OAuth application on every Git provider it federates with (GitHub, GitLab, etc.) and the redirect URI must match the cluster's domain exactly; a typo here means users can land on the login page but never finish the handshake. DNS and cert-manager are next: Flex assumes a wildcard hostname for workspaces (each workspace gets its own subdomain) and a working ACME issuer; if cert-manager is not already producing certs in the namespace, every workspace URL throws a TLS error. Object storage is third — the Helm values point Gitpod at S3 (or GCS/MinIO) for workspace snapshots and prebuilds, and the IAM role needs read+write on the bucket; permissions failures here surface as workspaces that build but cannot be restored. Postgres reachability rounds out the top four: the database lives outside the chart in real deployments and the cluster network policy must allow the namespace to reach it. None of these are Gitpod bugs; all of them are environment assumptions that a first-time installer has not validated yet.
</details>

### Question 7
Two engineers on the same team disagree. Engineer A wants to keep the workspace image small (`node:20-slim`, install tools per-workspace via `postCreateCommand`). Engineer B wants a fat custom image baked weekly with every tool the team uses. Each says the other is making the developer experience worse. Whose argument is stronger, and under what condition would you flip your answer?

<details>
<summary>Show Answer</summary>

**Engineer A is right by default — start small and let prebuilds amortise the install cost — but flip to Engineer B if the team's setup commands are slow, flaky, or pull from rate-limited registries.**

The Common Mistakes row "Huge base images — slow to download, slow to start" is the case for Engineer A: a slim base pulls fast on every cache miss and the difference between "cold start" and "warm start" stays small. Prebuilds make `postCreateCommand` essentially free on the user's clock — the install runs once, on the prebuild runner, and every new workspace hydrates from a snapshot. The case for Engineer B emerges when the install path is unreliable: corporate proxy that throttles npm, an internal artifact registry with quotas, a build step that compiles native modules and randomly fails on certain CPU types, or a tool whose installer hits a public endpoint that occasionally rate-limits. In those environments, baking the tools into the image trades disk size for determinism, and a weekly rebuild keeps it fresh without exposing every developer to install flakiness. The decision is not aesthetic; it is "which failure mode hurts us more — slow pulls or flaky installs?"
</details>

### Question 8
Your VP of Engineering wants to ban local development entirely and put all 200 engineers on a single CDE, like the Stripe story in the war story section. Before you green-light it, you have an architectural-review meeting tomorrow. What three concrete questions do you bring to that meeting that would change the recommendation if the answers came back wrong?

<details>
<summary>Show Answer</summary>

**(1) Which Git providers do we actually have? (2) What is our network shape for build/test traffic? (3) What is our acceptable failure mode when the CDE is down?**

The Git-provider question decides the platform itself — a single GitHub-only org points at Codespaces, a multi-provider environment forces Gitpod or a mixed deployment, and the wrong assumption here invalidates the whole rollout. The network question decides cost and latency: if developers' tests pull large datasets or push to private artifact registries inside a specific cloud region, picking a CDE region that is far from those services adds seconds to every round-trip and dollars to every egress, and that compounds across two hundred engineers. The failure-mode question is the one VPs forget: a CDE outage means *nobody can code*, not just "some people are inconvenienced," and the answer determines whether you need a self-hosted footprint, a documented laptop fallback, or an SLA-backed plan with the vendor. If any of these three answers comes back wrong — multi-provider repos with a Codespaces choice, distant region with no plan to relocate, no tolerance for any downtime — you do not say no, but you say "not this quarter, here is what we fix first."
</details>

---

## Hands-On Exercise

**Objective**: Stand up the same Node.js project for both Codespaces and Gitpod, get a one-click "Open in Gitpod" PR review experience working, and compare the two platforms on real metrics — not vendor marketing.

**Prerequisites**: a GitHub account with Codespaces enabled (free tier is sufficient), a Gitpod account linked to that GitHub account, and `git` plus `gh` installed locally for the bootstrap.

You will work through five progressive tasks. Each task ends with a `- [ ]` checkbox list — do not move on until every box is ticked.

### Task 1: Bootstrap a minimal Node.js app locally

Before the cloud platforms can build anything, they need something to build. Create the smallest possible Express app and commit it.

```bash
mkdir cde-lab && cd cde-lab
git init
git branch -M main

cat > package.json << 'EOF'
{
  "name": "cde-lab",
  "scripts": {
    "dev": "node server.js"
  },
  "dependencies": {
    "express": "^4.18.0"
  }
}
EOF

cat > server.js << 'EOF'
const express = require('express');
const app = express();
app.get('/', (req, res) => res.send('Hello from CDE!'));
app.listen(3000, () => console.log('Running on :3000'));
EOF
```

Success criteria:
- [ ] `cde-lab/package.json` and `cde-lab/server.js` both exist
- [ ] `git status` shows the two files as untracked, ready to commit
- [ ] You can predict (without running it) that `npm install && npm run dev` would print `Running on :3000`

<details>
<summary>Why so minimal?</summary>

The point of this lab is to compare *platform behaviour*, not application complexity. A two-file Express app keeps the install fast on free-tier machines, makes prebuild timings easy to read, and lets you finish the lab in one session. You can swap in a real repo later — the configuration files transfer unchanged.
</details>

### Task 2: Configure GitHub Codespaces with a dev container

Create a `.devcontainer/devcontainer.json` that pins the base image, declares the port, runs `npm install` once on container creation, and starts the dev server every time the workspace boots.

```bash
mkdir -p .devcontainer
cat > .devcontainer/devcontainer.json << 'EOF'
{
  "name": "CDE Lab",
  "image": "mcr.microsoft.com/devcontainers/javascript-node:20",
  "customizations": {
    "vscode": {
      "extensions": ["dbaeumer.vscode-eslint"]
    }
  },
  "forwardPorts": [3000],
  "postCreateCommand": "npm install",
  "postStartCommand": "npm run dev"
}
EOF
```

Success criteria:
- [ ] `.devcontainer/devcontainer.json` parses as valid JSON (try `python -m json.tool < .devcontainer/devcontainer.json`)
- [ ] You can explain out loud why `postCreateCommand` runs `npm install` but `postStartCommand` runs `npm run dev` — and not the other way around
- [ ] The `forwardPorts` value matches the port `server.js` listens on

<details>
<summary>Hint: postCreate vs postStart lifecycle</summary>

`postCreateCommand` runs *once*, when the container is first built (or when a prebuild bakes the image). `postStartCommand` runs *every time* the workspace starts, including resumes from stop. Putting `npm install` in `postCreate` means dependencies hydrate from cache on resumes; putting `npm run dev` in `postStart` means the server is listening as soon as you connect, even after the workspace was stopped overnight.
</details>

### Task 3: Configure Gitpod with `.gitpod.yml`

Mirror the Codespaces setup using Gitpod's configuration format. Note how the same intent (install once, run server, expose port 3000) maps onto a different file structure.

```bash
cat > .gitpod.yml << 'EOF'
image: gitpod/workspace-node

tasks:
  - name: Dev Server
    init: npm install
    command: npm run dev

ports:
  - port: 3000
    onOpen: open-preview
    visibility: public

vscode:
  extensions:
    - dbaeumer.vscode-eslint

github:
  prebuilds:
    master: true
    pullRequests: true
    addBadge: true
EOF
```

Success criteria:
- [ ] `.gitpod.yml` is valid YAML (try `python -c "import yaml,sys; yaml.safe_load(open('.gitpod.yml'))"`)
- [ ] You can identify which Gitpod field plays the role of `postCreateCommand` and which plays the role of `postStartCommand`
- [ ] You set `pullRequests: true` so reviewers will get a prebuilt environment on every PR

<details>
<summary>Mapping between the two formats</summary>

Same primitives, different spelling:

- Base image: `image` in both
- One-time setup: `postCreateCommand` in Codespaces, `tasks[].init` in Gitpod
- Per-start command: `postStartCommand` in Codespaces, `tasks[].command` in Gitpod
- Port exposure: `forwardPorts` in Codespaces, `ports[]` (with `visibility`) in Gitpod
- VS Code extensions: `customizations.vscode.extensions` in Codespaces, `vscode.extensions` in Gitpod
- Prebuilds: repo settings UI in Codespaces, `github.prebuilds` block in Gitpod

A team that maintains both can keep these two files in sync with a short script.
</details>

### Task 4: Add the "Open in Gitpod" badge and push to GitHub

The PR-review story from earlier in the module hinges on reviewers being one click away from a running environment. Wire that up now.

```bash
cat > README.md << 'EOF'
# CDE Lab

[![Open in Gitpod](https://gitpod.io/button/open-in-gitpod.svg)](https://gitpod.io/#https://github.com/YOUR_USER/cde-lab)

## Development

Or use GitHub Codespaces from the repository Code button.
EOF

git add .
git commit -m "Configure cloud development environments"
gh repo create cde-lab --public --source=. --remote=origin --push
```

Success criteria:
- [ ] `README.md` shows the Gitpod badge in GitHub's rendered preview
- [ ] You replaced `YOUR_USER` with your actual GitHub username before committing
- [ ] `gh repo view --web` opens the repo and the badge is clickable

<details>
<summary>If `gh repo create` fails</summary>

You can do the equivalent in the browser: create a new public repo named `cde-lab` on GitHub, then in the local clone run `git remote add origin git@github.com:YOUR_USER/cde-lab.git && git push -u origin main`. The CLI is faster but not load-bearing for the lab.
</details>

### Task 5: Launch on both platforms and compare

Now exercise both platforms end-to-end and record what you see. This is where the lab moves from "can I configure it?" to "do I understand the differences?"

```bash
# Codespaces
# Browse to https://github.com/YOUR_USER/cde-lab
# Click Code -> Codespaces -> Create codespace on main
# Wait for the workspace to open, then verify the preview tab shows "Hello from CDE!"

# Gitpod
# Browse to https://gitpod.io/#https://github.com/YOUR_USER/cde-lab
# Authorize on first launch, then wait for the Dev Server task to settle
# The preview tab should show "Hello from CDE!"
```

Success criteria:
- [ ] Codespaces workspace boots and the forwarded port 3000 returns `Hello from CDE!`
- [ ] Gitpod workspace boots and the public port 3000 returns `Hello from CDE!`
- [ ] You wrote down the cold-start time for each platform (in seconds, from click to "ready")
- [ ] You can name one thing each platform did *better* than the other in your hands — not from the comparison table, from your own measurement
- [ ] You stopped both workspaces afterwards (do not let them idle on free-tier hours)

<details>
<summary>Stretch: enable a prebuild and re-measure</summary>

Codespaces: in the repository's *Settings → Codespaces → Prebuilds*, configure a prebuild for the `main` branch. Push a trivial commit and wait for the prebuild to complete (check the *Codespaces* tab).

Gitpod: the `github.prebuilds` block you wrote in Task 3 already enables this — push a commit and watch the prebuild status under your Gitpod dashboard.

Then create a *fresh* workspace on each platform and time the cold start again. The delta between "first time" and "after prebuild" is the single most important number for selling CDEs to a skeptical team — capture it.
</details>

---

## Key Takeaways

1. **CDEs eliminate environment drift** - Everyone gets identical setups
2. **Prebuilds are essential** - Without them, cloud is slower than local
3. **Codespaces = GitHub native** - Best integration for GitHub users
4. **Gitpod = Provider agnostic** - Works with GitHub, GitLab, Bitbucket
5. **Both use VS Code** - Familiar experience for most developers
6. **Self-hosted needs Gitpod** - Codespaces is SaaS only
7. **Cost management matters** - Set idle timeouts, right-size machines
8. **PR reviews transformed** - One-click testing environments
9. **Onboarding accelerated** - 2 days → 2 minutes
10. **Security improved** - No code on laptops, centralized audit

---

## Next Steps

- **Related**: [Module 8.4: DevPod](../module-8.4-devpod/) - Open source alternative
- **Related**: [Platform Engineering](/platform/disciplines/core-platform/platform-engineering/) - Building developer platforms
- **Related**: [Module 8.3: Local Kubernetes](../module-8.3-local-kubernetes/) - When you need local

---

## Further Reading

- [GitHub Codespaces Documentation](https://docs.github.com/en/codespaces)
- [Gitpod Documentation](https://www.gitpod.io/docs)
- [Dev Containers Specification](https://containers.dev/)
- [Gitpod Flex (Self-Hosted)](https://www.gitpod.io/docs/flex)
- [Codespaces Pricing Calculator](https://github.com/pricing/calculator)

---

*"The laptop is becoming what the thin client was supposed to be—a window into compute that happens elsewhere. CDEs make this vision actually work for developers."*

## Sources

- [GitHub Codespaces](https://github.com/features/codespaces) — Official GitHub product page for repeatable cloud development environments and free included usage.
- [GitHub Pricing Calculator](https://github.com/pricing/calculator) — Live source for Codespaces machine and storage cost estimates.
- [Development Containers Specification](https://github.com/devcontainers/spec) — Canonical source for devcontainer.json and the Dev Containers ecosystem.
- [Gitpod Project Repository](https://github.com/gitpod-io/gitpod) — Public Gitpod project repository for product background and links into Gitpod's documentation ecosystem.
