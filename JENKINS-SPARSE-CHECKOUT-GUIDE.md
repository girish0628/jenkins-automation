# Jenkins Sparse Checkout Guide — app-automation + app-configs

## Overview

This guide covers a production-ready Jenkins Freestyle job on a **Windows agent** that:

- Manages two GitLab repositories (`app-automation`, `app-configs`)
- Selects branch and config folder based on `ENV_NAME` parameter (`npe` / `prod`)
- Clones only once, then fetches and compares commits on subsequent runs
- Pulls only when there is a newer remote commit
- Uses Git sparse checkout on `app-configs` to pull only the relevant folder

---

## Repository Structure

```
app-configs (main branch)
├── npe/
└── prod/

app-automation
├── branch: npe
└── branch: prod
```

---

## Jenkins Workspace Layout

```
workspace/
├── app-automation/     ← full clone, branch = ENV_NAME
└── app-configs/
    ├── npe/            ← sparse, only present when ENV_NAME=npe
    └── prod/           ← sparse, only present when ENV_NAME=prod
```

---

## Required Jenkins Plugins

| Plugin | Purpose |
|---|---|
| **Git Plugin** | Git operations on agent |
| **Credentials Binding Plugin** | Inject GitLab credentials safely into scripts |
| **Workspace Cleanup Plugin** | Optional — manual workspace cleanup when needed |
| **Parameterized Trigger Plugin** | Optional — trigger downstream jobs |
| **GitLab Plugin** | Optional — webhook-based triggering from GitLab |

Install via: `Manage Jenkins → Plugins → Available`

---

## Step-by-Step Jenkins GUI Setup

### Step 1 — Create Freestyle Job

1. Open Jenkins
2. Click **New Item**
3. Enter name: `app-automation-runner`
4. Select **Freestyle project**
5. Click **OK**

---

### Step 2 — Add Environment Parameter

1. Tick **This project is parameterized**
2. Click **Add Parameter → Choice Parameter**
3. Set:

```
Name    : ENV_NAME
Choices : npe
          prod
Description: Target environment to run automation
```

---

### Step 3 — General Settings

| Setting | Value |
|---|---|
| Discard old builds | Optional — keep last 10 builds |
| Do NOT clean workspace before build | Critical — needed for clone-once logic |
| Restrict where this project can be run | Set to your Windows agent label |

---

### Step 4 — Source Code Management

Set to **None**.

> All Git operations are handled in the batch script for full control over
> sparse checkout, branch selection, and commit comparison logic.

---

### Step 5 — Add GitLab Credentials

1. Go to `Manage Jenkins → Credentials → (global) → Add Credentials`
2. Select kind: **Username with password**
3. Fill:

```
Username : your-gitlab-username  (or deploy token username)
Password : your-gitlab-PAT-or-token
ID       : gitlab-credentials
```

> **Recommended:** Use a **GitLab Deploy Token** with `read_repository` scope
> instead of a personal access token. It is scoped to the repo and does not
> expire with your personal account.

---

### Step 6 — Add Build Step

1. Under **Build**, click **Add build step**
2. Select **Execute Windows batch command**
3. Paste the script below

---

## Production Batch Script

> Replace `<GITLAB_URL>` with your actual GitLab server hostname.

```batch
@echo off
setlocal enabledelayedexpansion

echo ==========================================
echo  Jenkins App Automation Runner
echo  ENV_NAME = %ENV_NAME%
echo  Date     = %DATE%  Time = %TIME%
echo ==========================================

REM ---------------------------------------------------------------
REM CONFIGURATION — update these values for your environment
REM ---------------------------------------------------------------
set AUTOMATION_REPO_URL=https://%GIT_USER%:%GIT_PASS%@<GITLAB_URL>/your-group/app-automation.git
set CONFIG_REPO_URL=https://%GIT_USER%:%GIT_PASS%@<GITLAB_URL>/your-group/app-configs.git

set AUTOMATION_DIR=%WORKSPACE%\app-automation
set CONFIG_DIR=%WORKSPACE%\app-configs

set AUTOMATION_BRANCH=%ENV_NAME%
set CONFIG_FOLDER=%ENV_NAME%
set CONFIG_BRANCH=main

set LOG_FILE=%WORKSPACE%\sync_%ENV_NAME%.log

REM ---------------------------------------------------------------
REM LOGGING SETUP
REM ---------------------------------------------------------------
if not exist "%WORKSPACE%\logs" mkdir "%WORKSPACE%\logs"
set LOG_FILE=%WORKSPACE%\logs\sync_%ENV_NAME%_%DATE:~-4%%DATE:~3,2%%DATE:~0,2%.log

call :log "=========================================="
call :log "START  %DATE% %TIME%"
call :log "ENV    %ENV_NAME%"
call :log "=========================================="

REM ==================================================================
REM SECTION 1 — app-automation repository
REM ==================================================================
call :log "[SECTION 1] app-automation"

IF NOT EXIST "%AUTOMATION_DIR%\.git" (
    call :log "[INFO] app-automation not found. First-time clone..."
    git clone --branch %AUTOMATION_BRANCH% "%AUTOMATION_REPO_URL%" "%AUTOMATION_DIR%"
    IF ERRORLEVEL 1 (
        call :log "[ERROR] Clone failed for app-automation"
        exit /b 1
    )
    call :log "[INFO] Clone completed."
) ELSE (
    call :log "[INFO] app-automation repo exists. Skipping clone."
)

cd /d "%AUTOMATION_DIR%"
IF ERRORLEVEL 1 (
    call :log "[ERROR] Cannot access automation dir: %AUTOMATION_DIR%"
    exit /b 1
)

REM Ensure we are on the correct branch
call :log "[INFO] Switching to branch: %AUTOMATION_BRANCH%"
git checkout %AUTOMATION_BRANCH%
IF ERRORLEVEL 1 (
    call :log "[ERROR] Failed to checkout branch %AUTOMATION_BRANCH%"
    exit /b 1
)

REM Fetch latest without touching working tree
call :log "[INFO] Fetching remote information for app-automation..."
git fetch origin %AUTOMATION_BRANCH%
IF ERRORLEVEL 1 (
    call :log "[ERROR] Fetch failed for app-automation"
    exit /b 1
)

REM Compare local vs remote commit
FOR /F %%i IN ('git rev-parse HEAD') DO SET LOCAL_AUTO_COMMIT=%%i
FOR /F %%i IN ('git rev-parse origin/%AUTOMATION_BRANCH%') DO SET REMOTE_AUTO_COMMIT=%%i

call :log "[INFO] app-automation local  : !LOCAL_AUTO_COMMIT!"
call :log "[INFO] app-automation remote : !REMOTE_AUTO_COMMIT!"

IF /I "!LOCAL_AUTO_COMMIT!"=="!REMOTE_AUTO_COMMIT!" (
    call :log "[INFO] app-automation is up to date. Skipping pull."
) ELSE (
    call :log "[INFO] New commits found. Pulling app-automation..."
    git pull origin %AUTOMATION_BRANCH% --rebase
    IF ERRORLEVEL 1 (
        call :log "[ERROR] Pull failed for app-automation"
        exit /b 1
    )
    FOR /F %%i IN ('git rev-parse HEAD') DO SET UPDATED_AUTO_COMMIT=%%i
    call :log "[INFO] app-automation updated to: !UPDATED_AUTO_COMMIT!"
)

cd /d "%WORKSPACE%"

REM ==================================================================
REM SECTION 2 — app-configs repository (sparse checkout)
REM ==================================================================
call :log "[SECTION 2] app-configs (sparse: %CONFIG_FOLDER%)"

IF NOT EXIST "%CONFIG_DIR%\.git" (
    call :log "[INFO] app-configs not found. First-time sparse clone..."

    git clone --no-checkout --filter=blob:none "%CONFIG_REPO_URL%" "%CONFIG_DIR%"
    IF ERRORLEVEL 1 (
        call :log "[ERROR] Clone failed for app-configs"
        exit /b 1
    )

    cd /d "%CONFIG_DIR%"

    git sparse-checkout init --cone
    IF ERRORLEVEL 1 (
        call :log "[ERROR] sparse-checkout init failed"
        exit /b 1
    )

    git sparse-checkout set %CONFIG_FOLDER%
    IF ERRORLEVEL 1 (
        call :log "[ERROR] sparse-checkout set failed for folder: %CONFIG_FOLDER%"
        exit /b 1
    )

    git checkout %CONFIG_BRANCH%
    IF ERRORLEVEL 1 (
        call :log "[ERROR] Checkout failed for branch: %CONFIG_BRANCH%"
        exit /b 1
    )

    call :log "[INFO] Sparse clone completed. Folder: %CONFIG_FOLDER%"

) ELSE (
    call :log "[INFO] app-configs repo exists. Skipping clone."
    cd /d "%CONFIG_DIR%"

    REM Safety: re-apply sparse folder in case it changed
    call :log "[INFO] Ensuring sparse folder is set to: %CONFIG_FOLDER%"
    git sparse-checkout set %CONFIG_FOLDER%
    IF ERRORLEVEL 1 (
        call :log "[ERROR] Failed to switch sparse folder to %CONFIG_FOLDER%"
        exit /b 1
    )
)

REM Ensure we are on the config branch
git checkout %CONFIG_BRANCH%
IF ERRORLEVEL 1 (
    call :log "[ERROR] Failed to checkout branch %CONFIG_BRANCH% in app-configs"
    exit /b 1
)

REM Fetch latest without touching working tree
call :log "[INFO] Fetching remote information for app-configs..."
git fetch origin %CONFIG_BRANCH%
IF ERRORLEVEL 1 (
    call :log "[ERROR] Fetch failed for app-configs"
    exit /b 1
)

REM Compare local vs remote commit
FOR /F %%i IN ('git rev-parse HEAD') DO SET LOCAL_CONFIG_COMMIT=%%i
FOR /F %%i IN ('git rev-parse origin/%CONFIG_BRANCH%') DO SET REMOTE_CONFIG_COMMIT=%%i

call :log "[INFO] app-configs local  : !LOCAL_CONFIG_COMMIT!"
call :log "[INFO] app-configs remote : !REMOTE_CONFIG_COMMIT!"

IF /I "!LOCAL_CONFIG_COMMIT!"=="!REMOTE_CONFIG_COMMIT!" (
    call :log "[INFO] app-configs is up to date. Skipping pull."
) ELSE (
    call :log "[INFO] New commits found. Pulling app-configs..."
    git pull origin %CONFIG_BRANCH% --rebase
    IF ERRORLEVEL 1 (
        call :log "[ERROR] Pull failed for app-configs"
        exit /b 1
    )
    FOR /F %%i IN ('git rev-parse HEAD') DO SET UPDATED_CONFIG_COMMIT=%%i
    call :log "[INFO] app-configs updated to: !UPDATED_CONFIG_COMMIT!"
)

cd /d "%WORKSPACE%"

REM ==================================================================
REM SECTION 3 — Run Python automation script
REM ==================================================================
call :log "[SECTION 3] Running automation"
call :log "[INFO] Automation dir : %AUTOMATION_DIR%"
call :log "[INFO] Config dir     : %CONFIG_DIR%\%CONFIG_FOLDER%"

cd /d "%AUTOMATION_DIR%"

python your_script.py --env %ENV_NAME% --config "%CONFIG_DIR%\%CONFIG_FOLDER%"
IF ERRORLEVEL 1 (
    call :log "[ERROR] Python script failed. Exit code: %ERRORLEVEL%"
    exit /b 1
)

call :log "[SUCCESS] Automation completed. %DATE% %TIME%"
call :log "=========================================="
endlocal
exit /b 0

REM ==================================================================
REM LOGGING FUNCTION
REM ==================================================================
:log
echo [%TIME%] %~1
echo [%DATE% %TIME%] %~1 >> "%LOG_FILE%"
goto :eof
```

---

## Credentials Binding in Jenkins

Wrap your batch step with the **Credentials Binding** plugin so tokens never appear in plain text:

In the job configuration, before the batch step, add a **Binding**:

```
Kind     : Username and password (separated)
Username : GIT_USER
Password : GIT_PASS
Credentials: gitlab-credentials   ← the ID you set in Step 5
```

The variables `%GIT_USER%` and `%GIT_PASS%` are then available inside the batch script, which is how the `REPO_URL` is constructed securely.

---

## Jenkins Workspace Persistence — Best Practices

| Setting | Recommendation |
|---|---|
| **Delete workspace before build** | NEVER enable — defeats clone-once logic |
| **Agent assignment** | Lock job to a specific agent label so workspace path stays consistent |
| **Workspace path** | Keep default `%WORKSPACE%` — Jenkins manages it per job per agent |
| **Discard old builds** | Keep last 10–20 builds to limit disk usage |
| **Clean after failure** | Only clean if you suspect workspace corruption, not by default |

---

## GitLab Webhook Setup (Recommended over Polling)

### GitLab side

```
Project → Settings → Integrations → Jenkins
  or
Project → Settings → Webhooks → Add webhook
  URL     : http://<jenkins-host>/project/app-automation-runner
  Token   : (generated in Jenkins job — see below)
  Trigger : Push events
  Branch  : npe, prod (filter by branch)
```

### Jenkins side

1. Install **GitLab Plugin**
2. In job config → **Build Triggers**
3. Tick **Build when a change is pushed to GitLab**
4. Copy the **GitLab webhook URL** and **Secret token** into GitLab

> This eliminates polling entirely. Jenkins reacts instantly to pushes.

---

## Behavior Summary

### First Run (workspace empty)

```
app-automation  → full clone  (branch = ENV_NAME)
app-configs     → sparse clone (folder = ENV_NAME, branch = main)
Python script   → executed
```

### Subsequent Runs — no changes in GitLab

```
app-automation  → fetch → commits match → skip pull
app-configs     → fetch → commits match → skip pull
Python script   → executed
```

### Subsequent Runs — new commit pushed to GitLab

```
app-automation  → fetch → commits differ → pull --rebase
app-configs     → fetch → commits differ → pull --rebase
Python script   → executed
```

---

## ENV_NAME Mapping Table

| ENV_NAME | app-automation branch | app-configs folder | app-configs branch |
|---|---|---|---|
| `npe` | `npe` | `npe/` | `main` |
| `prod` | `prod` | `prod/` | `main` |

---

## Common Issues and Fixes

### 1. Sparse checkout not working

Verify Git version on agent supports cone mode:

```batch
git --version
```

Minimum required: **Git 2.25+**. Upgrade via `https://git-scm.com/download/win`.

---

### 2. Wrong folder from previous run persists

Running `git sparse-checkout set npe` or `git sparse-checkout set prod` switches
the working tree cleanly. The script re-applies this on every run as a safety measure.

---

### 3. Authentication failure

Test manually on the Jenkins agent first:

```batch
git clone https://YOUR_USER:YOUR_TOKEN@<GITLAB_URL>/group/repo.git test-clone
```

If this fails, the token is wrong or lacks `read_repository` scope.

---

### 4. Detached HEAD after previous failed run

The script runs `git checkout <branch>` explicitly before every fetch/pull to
prevent this.

---

### 5. ENV_NAME not passed correctly

When triggering from GitLab webhook, pass ENV_NAME via a trigger parameter or
use a separate job per environment that hardcodes the value.

---

## Optional Enhancements

| Enhancement | Benefit |
|---|---|
| `--filter=blob:none` on initial clone | Faster clone — skips blobs until checkout |
| `--depth=1` on app-automation clone | Shallow clone — only latest snapshot |
| Add `git gc` step weekly | Keeps workspace lean over time |
| Send build status back to GitLab | Visible pipeline status on MR/commit |
| Archive log file as build artifact | `%WORKSPACE%\logs\sync_*.log` |
| Email/Slack notification on failure | Alert team without checking Jenkins |
