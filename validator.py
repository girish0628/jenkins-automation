import json
import os
import sys
import time
import platform
import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from checks.common import TestResult, load_config, save_report, run_check_safely
from checks.envvars import check_env_vars
from checks.tools import check_tool_versions
from checks.arcpy_checks import check_arcpy_license, check_sde_read
from checks.network import check_network_shares
from checks.disk_software import check_disk_space, check_software_inventory
from checks.jenkins_api import (
    check_jenkins_agents_labels,
    trigger_jenkins_job,
    verify_jenkins_email_job,
    verify_job_chaining
)
from checks.gitlab_api import check_gitlab_pat


def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    cfg = load_config(config_path)

    report_dir = Path(cfg.get("report_dir", "reports"))
    report_dir.mkdir(parents=True, exist_ok=True)

    started = datetime.datetime.now().isoformat()
    host = platform.node()

    checks = []

    # Core checks
    checks.append(("Env Variables", lambda: check_env_vars(cfg)))
    checks.append(("Tool Versions", lambda: check_tool_versions(cfg)))
    checks.append(("Disk Space", lambda: check_disk_space(cfg)))

    if cfg.get("software_inventory", {}).get("enabled", False):
        checks.append(("Software Inventory", lambda: check_software_inventory(cfg)))

    # Network shares
    if cfg.get("network_shares"):
        checks.append(("Network Shares", lambda: check_network_shares(cfg)))

    # ArcPy license checks
    if cfg.get("license_checks", {}).get("enabled", False):
        checks.append(("ArcPy License Checks", lambda: check_arcpy_license(cfg)))

    # SDE read-only test (ArcPy)
    if cfg.get("sde_read_test", {}).get("enabled", False):
        checks.append(("SDE Read Test", lambda: check_sde_read(cfg)))

    # Jenkins checks
    if cfg.get("jenkins", {}).get("url"):
        checks.append(("Jenkins Agents/Labels", lambda: check_jenkins_agents_labels(cfg)))

        # Trigger test job
        checks.append(("Jenkins Trigger Test Job", lambda: trigger_jenkins_job(cfg, "trigger_test_job")))

        # Job chaining verification (trigger upstream and check downstream activity)
        checks.append(("Jenkins Job Chaining", lambda: verify_job_chaining(cfg)))

        # Email validation (trigger and verify)
        checks.append(("Jenkins Email Test", lambda: verify_jenkins_email_job(cfg)))

    # GitLab PAT validation
    if cfg.get("gitlab", {}).get("pat"):
        checks.append(("GitLab PAT", lambda: check_gitlab_pat(cfg)))

    results = []

    run_parallel = bool(cfg.get("run_parallel", True))
    max_workers = int(cfg.get("max_workers", 6))

    if run_parallel:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            future_map = {ex.submit(run_check_safely, name, fn): name for name, fn in checks}
            for fut in as_completed(future_map):
                results.append(fut.result())
    else:
        for name, fn in checks:
            results.append(run_check_safely(name, fn))

    # Summary
    failed = [r for r in results if not r["success"]]
    report = {
        "environment": cfg.get("environment", "DEV"),
        "node": host,
        "started": started,
        "finished": datetime.datetime.now().isoformat(),
        "total": len(results),
        "failed": len(failed),
        "results": results
    }

    out_path = report_dir / f"jenkins_env_report_{host}_{cfg.get('environment','DEV')}.json"
    save_report(report, out_path)

    print(f"\nReport saved: {out_path}")
    if failed:
        print("Failed checks:")
        for f in failed:
            print(f" - {f['name']}: {f.get('message','')}")
        sys.exit(2)
    else:
        print("All checks passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()