# WAIO Spatial Projects — GitLab + Jenkins DevOps Implementation Guide

**Organisation:** BHP CloudFactory
**Team:** WAIO Spatial Projects
**Last Updated:** 2026-03-24
**Scope:** GitLab repository structure, branch strategy, Jenkins GUI job configuration, environment promotion, and enterprise governance.

---

## Table of Contents

1. [Architecture Decisions](#1-architecture-decisions)
2. [GitLab Hierarchy](#2-gitlab-hierarchy)
3. [Repository Structures](#3-repository-structures)
4. [Branch Strategy](#4-branch-strategy)
5. [GitLab Setup — Step by Step](#5-gitlab-setup--step-by-step)
6. [Protected Branches](#6-protected-branches)
7. [Merge Request Approvals](#7-merge-request-approvals)
8. [Jenkins — Credentials and Service Account](#8-jenkins--credentials-and-service-account)
9. [Jenkins — Freestyle Job Configuration](#9-jenkins--freestyle-job-configuration)
   - 9.1 Required Plugins
   - 9.2 Job Structure — Folders per Repo, Jobs per Branch
   - 9.3 Create the Folder
   - 9.4 Create Job: `waio-automations » npe`
   - 9.5 Create Job: `waio-automations » prod`
   - 9.6 Create Job: `waio-automations » main`
   - 9.7 Folder-Level Permissions
   - 9.8 GitLab Webhook Setup
10. [Environment Promotion Workflow](#10-environment-promotion-workflow)
11. [Conda Environment Management](#11-conda-environment-management)
12. [Risks, Anti-Patterns, and Governance](#12-risks-anti-patterns-and-governance)
13. [Naming Conventions Reference](#13-naming-conventions-reference)

---

## 1. Architecture Decisions

### 1.1 One Repo Per Concern — Not Per Environment

The single most important decision in this guide.

**Do NOT do this:**
```
WAIO-SPATIAL-PROJECTS
  └── automations (subgroup)
        ├── automations-main   ← separate repo
        ├── automations-npe    ← separate repo
        └── automations-prod   ← separate repo
```

**Do this:**
```
WAIO-SPATIAL-PROJECTS
  └── automations              ← ONE repo
        ├── branch: main
        ├── branch: npe
        └── branch: prod
```

**Why repo-per-environment is an anti-pattern:**

| Problem | Impact |
|---|---|
| No native GitLab diff between environments | Cannot prove what changed between NPE and prod |
| No MR-based promotion between repos | Loses approval gates, audit trail, and review history |
| Environment drift is invisible | Silent differences accumulate undetected |
| Jenkins credential and webhook complexity triples | 12 repos instead of 4 |
| Git history is fragmented | Cannot bisect bugs across environments |
| Tags and releases break | A version tag in one repo means nothing in another |

**The branch IS the environment separator.** Repos separate concerns (automations vs configs vs widgets). Branches separate environments (main vs npe vs prod).

### 1.2 Projects vs Subgroups for the Four Categories

Use **projects** (repositories), not subgroups, for `app-configs`, `automations`, `tool-automations`, and `widgets`.

Use subgroups only when you need:
- Different team membership and permissions per category
- Separate audit or reporting boundaries
- Truly independent ownership

For a single WAIO spatial team with shared access, four flat projects inside one subgroup is simpler, cleaner, and easier to govern.

---

## 2. GitLab Hierarchy

```
bhp-cloudfactory                              ← root group (existing)
└── waio-spatial-projects                     ← subgroup (create this)
    ├── app-configs                           ← project (repository)
    ├── automations                           ← project (repository)
    ├── tool-automations                      ← project (repository)
    └── widgets                               ← project (repository)
```

### 2.1 Role Assignment

Assign roles at the `waio-spatial-projects` subgroup level. Roles inherit down to all projects automatically.

| Role | Who | What they can do |
|---|---|---|
| Owner | Platform admin only | Delete groups, manage billing, transfer projects |
| Maintainer | Team leads, senior engineers | Merge to protected branches, manage settings, manage CI |
| Developer | Engineers | Push to feature branches, create MRs, cannot merge to protected branches |
| Reporter | Stakeholders, read-only consumers | View code, issues, pipelines. Cannot push. |

> Assign the Jenkins service account as **Reporter** (read-only clone) unless Jenkins needs to push tags, in which case use **Developer**.

---

## 3. Repository Structures

### 3.1 `app-configs` Repository

Stores all environment-specific configuration. Config values differ per environment — the folder structure makes that explicit.

```
app-configs/
├── npe/
│   ├── database.yaml
│   ├── sde-paths.yaml
│   ├── arcgis-connections.yaml
│   └── runtime.yaml
├── prod/
│   ├── database.yaml
│   ├── sde-paths.yaml
│   ├── arcgis-connections.yaml
│   └── runtime.yaml
├── shared/
│   └── logging.yaml
├── templates/
│   ├── database.yaml.template
│   └── README.md
├── CODEOWNERS
└── README.md
```

**Rules:**
- `npe/` contains config tuned for non-production. Jenkins NPE jobs read from here.
- `prod/` contains config tuned for production. Jenkins prod jobs read from here.
- `shared/` contains config that is identical across environments.
- `templates/` contains placeholder files used to onboard new environments or document expected fields.
- **Never store passwords, tokens, or secrets in this repo.** Use Jenkins credentials store or a secrets vault.

### 3.2 `automations` Repository

Stores Python/ArcPy automation scripts.

```
automations/
├── src/
│   ├── loaders/
│   │   ├── __init__.py
│   │   ├── raster_loader.py
│   │   └── surface_loader.py
│   ├── processors/
│   │   ├── __init__.py
│   │   └── data_processor.py
│   └── shared/
│       ├── __init__.py
│       ├── config_reader.py
│       └── logger.py
├── jobs/
│   ├── run_raster_load.py
│   └── run_surface_load.py
├── environments/
│   ├── environment-npe.yml      ← conda env spec for NPE
│   └── environment-prod.yml     ← conda env spec for prod
├── tests/
│   └── test_loaders.py
├── docs/
│   └── setup.md
├── requirements.txt
├── environment.yml              ← base conda spec
└── README.md
```

### 3.3 `tool-automations` Repository

Stores reusable ArcPy tools, FME jobs, and utility scripts.

```
tool-automations/
├── arcpy/
│   ├── __init__.py
│   ├── spatial_tools.py
│   └── raster_tools.py
├── fme/
│   ├── surface_transform.fmw
│   └── data_export.fmw
├── common/
│   ├── __init__.py
│   └── file_utils.py
├── utils/
│   └── validation.py
└── README.md
```

### 3.4 `widgets` Repository

Stores Experience Builder or other UI widgets.

```
widgets/
├── widgets/
│   ├── exb-surface-loader/
│   │   ├── src/
│   │   └── manifest.json
│   ├── exb-go-to-location/
│   │   ├── src/
│   │   └── manifest.json
│   └── shared-widget-lib/
│       └── src/
├── config/
│   ├── npe/
│   └── prod/
└── README.md
```

---

## 4. Branch Strategy

### 4.1 Branch Names and Purpose

| Branch | Purpose | Who can push directly |
|---|---|---|
| `main` | Integration branch — latest tested dev state | Nobody (MR only) |
| `npe` | Non-production tested state | Nobody (MR only) |
| `prod` | Production state | Nobody (MR only) |
| `feature/JIRA-XXX-description` | Developer work | Developer who owns it |
| `bugfix/JIRA-XXX-description` | Bug fix work | Developer who owns it |
| `hotfix/JIRA-XXX-description` | Emergency production fix | Developer, fast-tracked MR |

### 4.2 Promotion Flow

```
feature/JIRA-123-add-raster-loader
        │
        │  MR → review → 1 approval → merge
        ▼
      main          ← dev integration, CI validation runs
        │
        │  MR → review → 1 approval → merge
        ▼
       npe           ← Jenkins NPE job triggers automatically via webhook
        │
        │  MR → review → 2 approvals + change ticket → merge
        ▼
      prod           ← Jenkins PROD job triggered MANUALLY
```

**Hotfix flow (emergency only):**
```
hotfix/JIRA-XXX-urgent-prod-fix
        │
        │  MR → fast-track review → 2 approvals
        ▼
      prod
        │
        │  Back-merge MR → prod → npe → main
        ▼
    main/npe          ← keep branches in sync after hotfix
```

### 4.3 Branch Naming Examples

```
feature/JIRA-101-surface-loader-optimisation
feature/JIRA-102-add-config-validation
bugfix/JIRA-210-fix-sde-path-null-check
hotfix/JIRA-300-prod-raster-load-failure
release/2024-Q1
```

---

## 5. GitLab Setup — Step by Step

### Step 1: Confirm Governance with BHP GitLab Admin

Before creating anything, confirm with your GitLab administrator:

- [ ] Are you permitted to create a subgroup under `bhp-cloudfactory`?
- [ ] Who will be Owner and Maintainer?
- [ ] Does BHP have naming standards that must be followed?
- [ ] Is there an existing group access token policy?
- [ ] Is there a required visibility setting (Private/Internal)?

### Step 2: Create the Subgroup

```
GitLab → bhp-cloudfactory → New subgroup

Name:            WAIO-SPATIAL-PROJECTS
Path:            waio-spatial-projects
Description:     WAIO Spatial Projects — automations, configs, tools, and widgets
Visibility:      Private
```

### Step 3: Create the Four Projects

Inside `waio-spatial-projects`, create each project:

```
New project → Create blank project

Project 1
  Name:        app-configs
  Path:        app-configs
  Visibility:  Private
  Default:     ☑ Initialize repository with a README

Project 2
  Name:        automations
  Path:        automations
  Visibility:  Private
  Default:     ☑ Initialize repository with a README

Project 3
  Name:        tool-automations
  Path:        tool-automations
  Visibility:  Private
  Default:     ☑ Initialize repository with a README

Project 4
  Name:        widgets
  Path:        widgets
  Visibility:  Private
  Default:     ☑ Initialize repository with a README
```

### Step 4: Assign Roles at Subgroup Level

```
waio-spatial-projects → Manage → Members → Invite members

Platform lead:       Maintainer
Senior engineers:    Maintainer
Engineers:           Developer
Stakeholders:        Reporter
Jenkins svc account: Reporter
```

### Step 5: Create Environment Branches in Each Project

For **each** of the four projects, do the following:

```
Project → Code → Branches → New branch

Branch name:   npe
Create from:   main

Branch name:   prod
Create from:   main
```

Each project now has three long-lived branches: `main`, `npe`, `prod`.

---

## 6. Protected Branches

Configure protected branches in **each project** individually.

```
Project → Settings → Repository → Protected branches
```

### Configuration Table

| Branch | Allowed to merge | Allowed to push | Allow force push |
|---|---|---|---|
| `main` | Maintainers | No one | No |
| `npe` | Maintainers | No one | No |
| `prod` | Maintainers | No one | No |

**Steps for each branch:**

```
Protected branches → Expand → Add protected branch

Branch:               main
Allowed to merge:     Maintainers
Allowed to push:      No one
Allow force push:     ☐ (unchecked)

Repeat for npe and prod.
```

**For `feature/*` branches (optional wildcard protection):**

```
Branch:               feature/*
Allowed to merge:     Developers + Maintainers
Allowed to push:      Developers + Maintainers
Allow force push:     ☐ (unchecked)
```

This prevents developers from accidentally force-pushing over a colleague's feature branch.

---

## 7. Merge Request Approvals

### 7.1 Configure Approval Rules

```
Project → Settings → Merge requests
```

**Settings to enable:**

```
Merge method:                    Merge commit (or Squash — team preference)
Squash commits:                  Encourage (let MR author decide) or Require
☑ Pipelines must succeed         (if CI is configured)
☑ All discussions must be resolved before merge
☑ Show link to create/view a merge request when pushing from the command line

Approvals:
  Minimum approvals required:    1 (for main and npe)
                                 2 (for prod — configure in approval rule)
  ☑ Prevent approval by author
  ☑ Prevent committers from approving their own work
  ☑ Require new approval when new commits are added
```

### 7.2 Add Approval Rules for Prod

```
Project → Settings → Merge requests → Approval rules → Add approval rule

Rule name:       Production approval
Approvals:       2
Eligible users:  Add your Maintainers and senior engineers
Target branch:   prod
```

### 7.3 CODEOWNERS (Recommended for app-configs)

Create a file at the root of `app-configs` called `CODEOWNERS`:

```
# All production config changes require senior engineer approval
/prod/      @waio-platform-admin @waio-lead-engineer

# NPE config changes require any engineer
/npe/       @waio-spatial-team

# Shared config requires lead approval
/shared/    @waio-lead-engineer
```

Enable CODEOWNERS in the project:

```
Project → Settings → Merge requests
☑ Enable "Code Owner approval" for this project
```

---

## 8. Jenkins — Credentials and Service Account

### 8.1 Create GitLab Access Token for Jenkins

Use a **Project Access Token** or **Group Access Token** (preferred for enterprise) rather than a personal access token tied to a human account.

```
waio-spatial-projects → Settings → Access Tokens → Add new token

Token name:   jenkins-waio-svc
Expiry:       Set per BHP policy (e.g. 365 days — create a calendar reminder to rotate)
Role:         Reporter
Scopes:       ☑ read_repository
```

Copy the token value immediately. It is shown only once.

> **If Group Access Token is not available** (requires GitLab Premium or admin approval), create a dedicated GitLab user account named `jenkins-waio-svc` and assign it Reporter role on the subgroup. Generate a Personal Access Token from that account.

### 8.2 Add Token to Jenkins Credentials Store

```
Jenkins → Manage Jenkins → Credentials → System → Global credentials (unrestricted) → Add Credentials

Kind:         Username with password
Scope:        Global
Username:     jenkins-waio-svc
Password:     <paste token value>
ID:           gitlab-waio-token
Description:  GitLab WAIO Spatial Projects — read-only service token
```

### 8.3 Verify Git is Available on Jenkins Node

```
Jenkins → Manage Jenkins → Tools → Git installations

Name:         Default
Path to Git:  git   (or full path if not on PATH, e.g. C:\Program Files\Git\bin\git.exe)
```

### 8.4 Credential Rotation Process

When the token expires or needs rotation:

1. Generate a new token in GitLab (same steps as 8.1)
2. Go to Jenkins → Manage Jenkins → Credentials
3. Find `gitlab-waio-token` → Update → replace Password value
4. Save
5. Run a test job to confirm clone still works
6. Revoke the old token in GitLab

> Never delete the Jenkins credential before the new one is verified working.

---

## 9. Jenkins — Freestyle Job Configuration

### 9.1 Required Plugins

Verify these are installed before creating jobs:

```
Jenkins → Manage Jenkins → Plugins → Installed plugins

Required:
  Git plugin
  Credentials Binding plugin
  Workspace Cleanup plugin
  Timestamper plugin
  GitLab plugin (for webhook triggers)
  CloudBees Folders plugin (for folder-based job organisation)
```

### 9.2 Job Structure — Folders per Repo, Jobs per Branch

Instead of flat job names like `waio-automations-npe`, use **Jenkins Folders** to mirror the GitLab repo structure. Each repo becomes a folder. Each environment branch becomes a job inside that folder.

**Jenkins folder structure:**

```
Jenkins
├── waio-automations              ← Folder (one per GitLab repo)
│   ├── main                     ← Freestyle job (validation only)
│   ├── npe                      ← Freestyle job (auto-triggered)
│   └── prod                     ← Freestyle job (manual only)
├── waio-app-configs              ← Folder
│   ├── npe
│   └── prod
├── waio-tool-automations         ← Folder
│   ├── npe
│   └── prod
└── waio-widgets                  ← Folder
    ├── npe
    └── prod
```

**Why folders instead of flat names:**

| Flat naming (old) | Folder structure (new) |
|---|---|
| `waio-automations-npe` | `waio-automations / npe` |
| `waio-automations-prod` | `waio-automations / prod` |
| Hard to filter and find | Grouped by repo — easier to navigate |
| Permissions apply to each job individually | Folder-level permissions inherit to all jobs inside |
| No visual grouping in Jenkins UI | Clear hierarchy mirrors GitLab project structure |

**Jenkins webhook URL format with folders:**

```
http://<JENKINS_URL>/job/waio-automations/job/npe/build?token=<TOKEN>
```

### 9.3 Create the Folder

```
Jenkins → New Item

Name:   waio-automations
Type:   Folder
→ OK

Display Name:   waio-automations
Description:    Automation jobs for the automations GitLab repo.
                Contains one job per environment branch (main, npe, prod).
```

Repeat this step to create folders for each repo:

```
waio-app-configs
waio-tool-automations
waio-widgets
```

### 9.4 Create Job: `waio-automations » npe`

Navigate into the `waio-automations` folder, then:

```
New Item

Name:   npe
Type:   Freestyle project
→ OK
```

#### General Tab

```
Description:
  Clones automations repo (npe branch) and app-configs repo (npe branch),
  activates the waio-npe Conda environment, and runs the target Python script.
  Triggered automatically on push to npe branch via GitLab webhook.

☑ Discard old builds
  Strategy:       Log Rotation
  Keep builds:    30

☑ This project is parameterized
```

#### Parameters

```
Parameter 1
  Type:     Choice Parameter
  Name:     SCRIPT_NAME
  Choices:  run_raster_load.py
            run_surface_load.py
  Description: Name of the job script inside automations/jobs/

Parameter 2
  Type:     String Parameter
  Name:     EXTRA_ARGS
  Default:  (blank)
  Description: Optional additional arguments passed to the Python script
```

> Do not add `TARGET_ENV` as a parameter on this job. The `npe` job always runs NPE. Environment is defined by which job you run, not a free-text parameter. This prevents human error from deploying dev code to production.

#### Source Code Management Tab

```
☑ Git

Repository URL:   https://gitlab.bhp.com/bhp-cloudfactory/waio-spatial-projects/automations.git
Credentials:      gitlab-waio-token

Branch Specifier: */npe

Additional Behaviours → Add → Check out to a sub-directory
  Local subdirectory for repo: automations
```

This places the automations repo contents into `<WORKSPACE>\automations\`.

#### Build Triggers Tab

```
☑ Build when a change is pushed to GitLab
  GitLab webhook URL:  http://<JENKINS_URL>/job/waio-automations/job/npe/build?token=<TRIGGER_TOKEN>

  Trigger on:
    ☑ Push Events
    Filter branches by name:
      Include:  npe
```

#### Build Environment Tab

```
☑ Delete workspace before build starts
☑ Add timestamps to the Console Output
☑ Abort the build if it's stuck
  Timeout:   60 minutes
  Strategy:  Absolute

☑ Use secret text(s) or file(s)
  Bindings → Add → Secret text
    Variable:    GITLAB_TOKEN
    Credentials: gitlab-waio-token
```

> The `GITLAB_TOKEN` binding exposes the credential as an environment variable so it can be used in the clone step without hardcoding the token value in the job config.

#### Build Steps Tab

**Build Step 1 — Clone app-configs**

Add build step → Execute Windows Batch Command:

```batch
:: ============================================================
:: Step 1: Clone app-configs repo (npe branch)
:: ============================================================
if exist "%WORKSPACE%\app-configs" (
    echo Removing existing app-configs directory...
    rmdir /s /q "%WORKSPACE%\app-configs"
)

echo Cloning app-configs (npe branch)...
git clone --branch npe --single-branch --depth 1 ^
    https://jenkins-waio-svc:%GITLAB_TOKEN%@gitlab.bhp.com/bhp-cloudfactory/waio-spatial-projects/app-configs.git ^
    "%WORKSPACE%\app-configs"

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to clone app-configs
    exit /b 1
)

echo app-configs cloned successfully.
echo.
```

**Build Step 2 — Activate Conda and Run Python**

Add build step → Execute Windows Batch Command:

```batch
:: ============================================================
:: Step 2: Activate Conda environment and run Python script
:: ============================================================
echo Activating Conda environment: waio-npe
call C:\ProgramData\Miniconda3\condabin\conda.bat activate waio-npe

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to activate conda environment waio-npe
    echo Verify the environment exists: conda env list
    exit /b 1
)

echo Conda environment activated.
echo Python path:
where python

echo.
echo Running script: %SCRIPT_NAME%
echo Config:         %WORKSPACE%\app-configs\npe\runtime.yaml
echo Extra args:     %EXTRA_ARGS%
echo.

cd "%WORKSPACE%\automations"

python jobs\%SCRIPT_NAME% ^
    --config "%WORKSPACE%\app-configs\npe\runtime.yaml" ^
    %EXTRA_ARGS%

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python script exited with error code %ERRORLEVEL%
    exit /b %ERRORLEVEL%
)

echo Script completed successfully.
```

#### Post-build Actions Tab

```
Add post-build action → GitLab: Set build status on GitLab commit
  (updates the commit status icon in GitLab UI — requires GitLab plugin)
```

---

### 9.5 Create Job: `waio-automations » prod`

Navigate into the `waio-automations` folder, then create a new Freestyle job named `prod`.

Use the same configuration as `npe` (section 9.4) with the following differences:

| Setting | `npe` job | `prod` job |
|---|---|---|
| Job name | `npe` | `prod` |
| Description | NPE environment | Production environment |
| Branch specifier | `*/npe` | `*/prod` |
| app-configs branch in clone step | `npe` | `prod` |
| Conda environment | `waio-npe` | `waio-prod` |
| Config path | `app-configs\npe\runtime.yaml` | `app-configs\prod\runtime.yaml` |
| Build triggers | GitLab webhook on `npe` push | **No trigger — manual only** |
| Timeout | 60 minutes | 90 minutes |

**Additional settings for `prod` job only:**

```
General tab:
  ☑ Restrict where this project can be run
  Label Expression:   prod-node
  (use this only if you have a dedicated Jenkins agent for production)
```

```
Build Triggers tab:
  ☐ (leave all triggers unchecked)

  The prod job must only be triggered manually by a Maintainer.
  Never add a webhook or scheduled trigger to the prod job.
```

---

### 9.6 Create Job: `waio-automations » main` (Validation Job)

Navigate into the `waio-automations` folder, then create a new Freestyle job named `main`.

This job validates code on push to `main`. It does **not** deploy to any environment — it runs tests or a dry-run to catch failures before promotion to NPE.

Key differences from the `npe` job:

```
Branch specifier:     */main
Build trigger:        GitLab webhook on main push (auto-trigger is fine here)
App-configs branch:   main (or omit if no config is needed for tests)
Conda environment:    waio-npe (reuse NPE env for validation)
Build step:           Run tests or dry-run, not a full script execution
Timeout:              30 minutes
```

**Resulting folder view in Jenkins UI:**

```
waio-automations
  ├── main    Last build: ✓  #42  2 hours ago   (auto — push to main)
  ├── npe     Last build: ✓  #38  4 hours ago   (auto — push to npe)
  └── prod    Last build: ✓  #12  3 days ago    (manual — deployment)
```

---

### 9.7 Folder-Level Permissions

One of the key benefits of the folder structure is that permissions can be managed at the folder level and inherited by all jobs inside, or overridden at the individual job level when tighter control is needed.

#### Set Permissions on a Folder

```
Jenkins → waio-automations → Configure

☑ Enable project-based security

User / Group              Permission
─────────────────────────────────────────────────────────────
waio-platform-admins      ☑ Administer
waio-maintainers          ☑ Build  ☑ Cancel  ☑ Read  ☑ Workspace
waio-developers           ☑ Read
jenkins-waio-svc          ☑ Read  ☑ Build   (for webhook triggers)
```

> If `Enable project-based security` is not visible, ask your Jenkins admin to enable Matrix-based security or Project-based Matrix Authorization Strategy under Manage Jenkins → Security.

#### Override Permissions on the `prod` Job Only

Because production must be triggered only by senior staff, override permissions at the job level:

```
Jenkins → waio-automations → prod → Configure → ☑ Enable project-based security

User / Group              Permission
─────────────────────────────────────────────────────────────
waio-platform-admins      ☑ Administer
waio-maintainers          ☑ Build  ☑ Cancel  ☑ Read  ☑ Workspace
waio-developers           ☑ Read  (can view logs, cannot trigger)
jenkins-waio-svc          ☑ Read  (no Build — prod is never webhook-triggered)
```

This means:
- Developers can open `waio-automations` and see all three jobs.
- Developers can see build history and console output for `prod`.
- Only Maintainers can click **Build Now** on the `prod` job.
- The webhook service account cannot trigger `prod` even if a webhook were accidentally configured.

#### Permission Inheritance Summary

```
waio-automations  (folder)
│   Maintainers → Build + Read
│   Developers  → Read only
│
├── main          inherits folder permissions (developers can trigger)
├── npe           inherits folder permissions (developers can trigger)
└── prod          OVERRIDES — only Maintainers can trigger
```

---

### 9.8 GitLab Webhook Setup (Per Repo)

Configure one webhook per GitLab repo to point at the corresponding Jenkins folder jobs.

#### For `automations` repo — trigger `npe` job on push to npe branch

```
GitLab → automations project → Settings → Webhooks → Add new webhook

URL:      http://<JENKINS_URL>/job/waio-automations/job/npe/build?token=<TRIGGER_TOKEN>
Trigger:  ☑ Push events
          Branch filter:  npe
SSL:      match your BHP policy
```

#### For `automations` repo — trigger `main` job on push to main branch

```
URL:      http://<JENKINS_URL>/job/waio-automations/job/main/build?token=<TRIGGER_TOKEN>
Trigger:  ☑ Push events
          Branch filter:  main
```

> Do **not** add a webhook for `prod`. The prod job has no trigger — it is manual only.

#### Webhook Token Setup in Jenkins

Each Jenkins job that accepts a webhook trigger must have a trigger token set:

```
Jenkins → waio-automations → npe → Configure → Build Triggers
☑ Trigger builds remotely (e.g., from scripts)
  Authentication Token:   <TRIGGER_TOKEN>
```

Use a different token per job. Store the token values in a password manager or secrets vault — not in plain text documentation.

#### Full Webhook URL Reference

```
Repo: automations
  main job:  http://<JENKINS_URL>/job/waio-automations/job/main/build?token=<TOKEN>
  npe job:   http://<JENKINS_URL>/job/waio-automations/job/npe/build?token=<TOKEN>
  prod job:  (no webhook — manual only)

Repo: app-configs
  npe job:   http://<JENKINS_URL>/job/waio-app-configs/job/npe/build?token=<TOKEN>
  prod job:  (no webhook — manual only)

Repo: tool-automations
  npe job:   http://<JENKINS_URL>/job/waio-tool-automations/job/npe/build?token=<TOKEN>
  prod job:  (no webhook — manual only)

Repo: widgets
  npe job:   http://<JENKINS_URL>/job/waio-widgets/job/npe/build?token=<TOKEN>
  prod job:  (no webhook — manual only)
```

---

## 10. Environment Promotion Workflow

### 10.1 Feature to Main

```
1. Developer creates branch from main:
   git checkout main
   git pull
   git checkout -b feature/JIRA-123-add-raster-loader

2. Developer commits and pushes:
   git push origin feature/JIRA-123-add-raster-loader

3. Developer creates MR in GitLab:
   Source:  feature/JIRA-123-add-raster-loader
   Target:  main
   Title:   JIRA-123: Add raster loader optimisation
   Description: What changed, why, how to test

4. Peer assigns reviewer, reviewer approves (1 approval required)

5. Developer or reviewer clicks Merge

6. Jenkins waio-automations » main triggers (webhook on main push)
   → runs validation/tests
```

### 10.2 Main to NPE (Environment Promotion)

```
1. Platform lead (Maintainer) creates MR:
   Source:  main
   Target:  npe
   Title:   Promote main to NPE — JIRA-123, JIRA-124
   Description: List of changes being promoted, testing notes

2. 1 approval required from another Maintainer

3. Merge

4. GitLab webhook fires → Jenkins waio-automations » npe triggers automatically

5. Spatial team validates output in NPE environment

6. Results recorded (Jira ticket, comment on MR, or change ticket)
```

### 10.3 NPE to Prod (Change-Controlled Promotion)

```
1. Platform lead creates MR:
   Source:  npe
   Target:  prod
   Title:   PROD PROMOTION — Sprint 2024-W12 — JIRA-123, JIRA-124
   Description:
     - Change ticket reference: CHG-XXXXX
     - Testing evidence: link to NPE validation results
     - Rollback plan: revert this MR if issues found
     - Scheduled deployment window: YYYY-MM-DD HH:MM

2. 2 approvals required (CODEOWNERS rule applies for app-configs)

3. All discussions resolved

4. Merge (do NOT merge outside of deployment window)

5. Platform lead navigates to Jenkins → waio-automations » prod
   → Build with Parameters
   → Selects correct SCRIPT_NAME
   → Clicks Build

6. Monitor build output in Jenkins console

7. Validate production output

8. Update change ticket as completed
```

### 10.4 Hotfix Flow

```
1. Platform lead creates branch from prod:
   git checkout prod
   git pull
   git checkout -b hotfix/JIRA-300-prod-raster-load-failure

2. Fix applied, tested locally

3. MR: hotfix/JIRA-300 → prod
   2 approvals fast-tracked
   Change ticket raised

4. Merge to prod, deploy manually via Jenkins

5. Back-merge to prevent drift:
   MR: prod → npe  (merge the hotfix back)
   MR: npe → main  (keep main up to date)
```

---

## 11. Conda Environment Management

### 11.1 Environment Spec Files in Repo

Commit Conda environment spec files to the `automations` repo:

```
automations/environments/environment-npe.yml
automations/environments/environment-prod.yml
```

Example `environment-npe.yml`:

```yaml
name: waio-npe
channels:
  - esri
  - conda-forge
  - defaults
dependencies:
  - python=3.9
  - arcpy=3.1
  - pyyaml=6.0
  - requests=2.28
  - pandas=1.5
  - pip:
    - some-internal-package==1.2.3
```

### 11.2 Creating the Conda Environment on Jenkins Node

This is a one-time setup by the Jenkins admin or platform lead. Run on the Jenkins agent node:

```batch
:: Windows
conda env create -f automations\environments\environment-npe.yml
conda env create -f automations\environments\environment-prod.yml

:: Verify
conda env list
```

### 11.3 Updating the Environment

When `environment-npe.yml` changes in a PR:

```batch
conda env update --name waio-npe --file automations\environments\environment-npe.yml --prune
```

Add this as an optional build step in the Jenkins job, or run it manually after merging dependency changes.

### 11.4 Conda Activation in Non-Interactive Shell

Jenkins runs in a non-interactive shell. Standard `conda activate` fails without initialisation.

**Windows (Jenkins batch step):**

```batch
call C:\ProgramData\Miniconda3\condabin\conda.bat activate waio-npe
```

**Linux (Jenkins shell step):**

```bash
source /opt/miniconda3/etc/profile.d/conda.sh
conda activate waio-npe
```

> If the above paths differ on your Jenkins node, the Jenkins admin must confirm the Miniconda/Anaconda install path. The `conda.bat` or `conda.sh` path must match where the service account's Conda is installed.

---

## 12. Risks, Anti-Patterns, and Governance

### 12.1 Anti-Patterns — Avoid These

| Anti-pattern | Why it is harmful | Correct approach |
|---|---|---|
| Repo per environment | Loses diff, audit trail, MR promotion | One repo, branches per environment |
| Direct push to `main`, `npe`, or `prod` | Bypasses review, unreviewed code in production | Protected branches, MR only |
| Storing secrets in `app-configs` repo | Git history is permanent; secrets are compromised | Jenkins credentials store or secrets vault |
| Single Jenkins job for all environments via parameter | Human error sends dev code to prod | Separate jobs per environment |
| Conda env not pinned to a spec file | NPE and prod silently run different package versions | `environment.yml` committed and version-pinned |
| Jenkins service account with Maintainer role | Service account can approve MRs, merge to prod | Minimum Reporter role for read-only clone |
| Token without expiry | Enterprise audit finding | Set expiry, rotate on schedule |
| Author approving their own MR | Defeats review purpose | GitLab setting: prevent author approval |
| Prod job with webhook trigger | Prod deploys automatically without human gate | No trigger on prod job — manual only |
| Hotfix applied only to prod | Prod diverges from main/npe; hotfix regresses next release | Always back-merge hotfix to npe then main |

### 12.2 Security Checklist

```
□ Jenkins service account has read-only (Reporter) GitLab role
□ GitLab access token scoped to read_repository only
□ Token has expiry date set — calendar reminder created
□ Token rotation procedure documented and tested
□ No secrets, passwords, or connection strings in any Git repo
□ Jenkins credentials store used for all sensitive values
□ Jenkins nodes running prod jobs are access-controlled
□ Jenkins prod job has no automated trigger
□ GitLab protected branches prevent direct push to main/npe/prod
□ MR approvals require minimum 1 person (2 for prod)
□ Author cannot approve their own MR
□ CODEOWNERS defined for prod/ folder in app-configs
```

### 12.3 Governance Checklist

```
□ Subgroup creation approved by BHP CloudFactory GitLab admin
□ Naming conventions confirmed with BHP platform team
□ Role assignments documented and reviewed
□ Change management process defined for prod promotions
□ Change ticket reference required in prod MR descriptions
□ Jenkins job names follow agreed convention
□ Conda environment spec files committed to repo (reproducible)
□ Jenkins workspace cleanup enabled on all jobs
□ Jenkins build retention policy set (e.g. keep 30 builds)
□ Deployment window policy defined for prod jobs
□ Rollback procedure documented
□ On-call or support contact documented for prod incidents
```

### 12.4 Config and Code Version Coupling

Because config lives in a separate repo, maintain this discipline:

| Rule | Detail |
|---|---|
| Branch names must align | `automations:npe` pairs with `app-configs:npe` |
| Promote together | When promoting `main → npe`, promote both repos in the same deployment window |
| Tag releases together | Tag `v1.2.3` on both `automations:prod` and `app-configs:prod` after each prod deployment |
| Never edit prod config directly | All prod config changes via MR from npe branch |
| Templates document expected fields | `app-configs/templates/` prevents "what config does this script need?" confusion |

---

## 13. Naming Conventions Reference

### GitLab

| Item | Convention | Example |
|---|---|---|
| Subgroup | UPPER-KEBAB-CASE | `WAIO-SPATIAL-PROJECTS` |
| Subgroup path | lower-kebab-case | `waio-spatial-projects` |
| Project name | lower-kebab-case | `app-configs`, `automations` |
| Feature branch | `feature/JIRA-XXX-short-description` | `feature/JIRA-123-raster-loader` |
| Bugfix branch | `bugfix/JIRA-XXX-short-description` | `bugfix/JIRA-210-null-path-fix` |
| Hotfix branch | `hotfix/JIRA-XXX-short-description` | `hotfix/JIRA-300-prod-load-failure` |
| Release branch | `release/YYYY-QN` or `release/vX.X.X` | `release/2024-Q1` |
| MR title (feature) | `JIRA-XXX: Short description of change` | `JIRA-123: Add raster loader optimisation` |
| MR title (promotion) | `Promote {source} to {target} — {tickets}` | `Promote main to NPE — JIRA-123, JIRA-124` |

### Jenkins

| Item | Convention | Example |
|---|---|---|
| Folder name | `waio-{repo}` | `waio-automations` |
| Job name (inside folder) | environment branch name | `main`, `npe`, `prod` |
| Full job path | `waio-{repo} » {environment}` | `waio-automations » npe` |
| Webhook URL | `/job/waio-{repo}/job/{env}/build` | `/job/waio-automations/job/npe/build` |
| Credential ID | `gitlab-{org}-{purpose}` | `gitlab-waio-token` |
| Parameter names | `UPPER_SNAKE_CASE` | `SCRIPT_NAME`, `EXTRA_ARGS` |

### Config Files

| Item | Convention | Example |
|---|---|---|
| Config files | `lower-kebab-case.yaml` | `database.yaml`, `sde-paths.yaml` |
| Environment folders | lowercase | `npe/`, `prod/`, `shared/` |
| Conda env name | `waio-{environment}` | `waio-npe`, `waio-prod` |
| Conda spec file | `environment-{environment}.yml` | `environment-npe.yml` |

---

## Quick Reference: Repository URLs

Replace `<GITLAB_HOST>` with your BHP GitLab hostname.

```
Subgroup:        https://<GITLAB_HOST>/bhp-cloudfactory/waio-spatial-projects

app-configs:     https://<GITLAB_HOST>/bhp-cloudfactory/waio-spatial-projects/app-configs.git
automations:     https://<GITLAB_HOST>/bhp-cloudfactory/waio-spatial-projects/automations.git
tool-automations:https://<GITLAB_HOST>/bhp-cloudfactory/waio-spatial-projects/tool-automations.git
widgets:         https://<GITLAB_HOST>/bhp-cloudfactory/waio-spatial-projects/widgets.git
```

---

*This guide covers GitLab subgroup setup, protected branches, merge request approvals, Jenkins Freestyle job configuration via GUI, Conda environment management, and enterprise governance. It does not use Jenkinsfile or pipeline-as-code. All Jenkins configuration is GUI-based.*
