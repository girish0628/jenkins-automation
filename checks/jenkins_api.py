import time
import requests
from urllib.parse import quote

def _jenkins_auth(cfg):
    j = cfg["jenkins"]
    return (j["user"], j["api_token"])

def _base(cfg):
    return cfg["jenkins"]["url"].rstrip("/")

def _get(cfg, path, params=None):
    r = requests.get(_base(cfg) + path, auth=_jenkins_auth(cfg), params=params, timeout=20)
    r.raise_for_status()
    return r

def _post(cfg, path, params=None, data=None, headers=None):
    r = requests.post(_base(cfg) + path, auth=_jenkins_auth(cfg), params=params, data=data, headers=headers or {}, timeout=20)
    # Jenkins may return 201/302/200/202 depending config
    if r.status_code not in (200, 201, 202, 302):
        r.raise_for_status()
    return r

def check_jenkins_agents_labels(cfg):
    expected = cfg.get("expected_nodes", [])
    try:
        data = _get(cfg, "/computer/api/json", params={"depth": 1}).json()
    except Exception as e:
        return {"success": False, "message": "Failed to query Jenkins agents", "details": str(e)}

    nodes = {}
    for c in data.get("computer", []):
        labels = []
        for l in c.get("assignedLabels", []) or []:
            n = l.get("name")
            if n:
                labels.append(n)
        nodes[c.get("displayName")] = {"offline": c.get("offline"), "labels": labels}

    details = []
    ok_all = True

    for exp in expected:
        name = exp["name"]
        exp_labels = set(exp.get("labels", []))
        if name not in nodes:
            ok_all = False
            details.append({"node": name, "ok": False, "message": "Node not found in Jenkins"})
            continue

        n = nodes[name]
        if n["offline"]:
            ok_all = False
            details.append({"node": name, "ok": False, "message": "Node is offline", "labels": n["labels"]})
            continue

        actual = set(n["labels"])
        missing = sorted(list(exp_labels - actual))
        ok = len(missing) == 0
        ok_all = ok_all and ok
        details.append({"node": name, "ok": ok, "missing_labels": missing, "labels": n["labels"]})

    return {"success": ok_all, "message": "Agent online + label validation", "details": details}

def _job_path(job_name: str) -> str:
    # basic job path; if folder jobs exist, you can pass "folder/jobname" and split by "/"
    parts = [p for p in job_name.split("/") if p]
    path = ""
    for p in parts:
        path += "/job/" + quote(p)
    return path

def trigger_jenkins_job(cfg, job_key: str, parameters=None):
    job = cfg["jenkins"]["jobs"].get(job_key)
    if not job:
        return {"success": False, "message": f"Job key not configured: {job_key}", "details": {}}

    try:
        if parameters:
            _post(cfg, _job_path(job) + "/buildWithParameters", data=parameters)
        else:
            _post(cfg, _job_path(job) + "/build")
        return {"success": True, "message": f"Triggered job: {job}", "details": {"job": job}}
    except Exception as e:
        return {"success": False, "message": f"Failed to trigger job: {job}", "details": str(e)}

def _get_last_build_number(cfg, job_name: str):
    j = _get(cfg, _job_path(job_name) + "/api/json").json()
    lb = j.get("lastBuild")
    return lb.get("number") if lb else None

def _get_build_info(cfg, job_name: str, build_number: int):
    return _get(cfg, _job_path(job_name) + f"/{build_number}/api/json").json()

def _get_console_text(cfg, job_name: str, build_number: int):
    r = _get(cfg, _job_path(job_name) + f"/{build_number}/consoleText")
    return r.text or ""

def _wait_for_build_complete(cfg, job_name: str, build_number: int, wait_seconds: int, poll_interval: int):
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        info = _get_build_info(cfg, job_name, build_number)
        if not info.get("building", False):
            return True, info
        time.sleep(poll_interval)
    return False, _get_build_info(cfg, job_name, build_number)

def verify_jenkins_email_job(cfg):
    job = cfg["jenkins"]["jobs"].get("email_test_job")
    if not job:
        return {"success": False, "message": "email_test_job not configured", "details": {}}

    verify_cfg = cfg["jenkins"].get("verify", {})
    wait_seconds = int(verify_cfg.get("wait_seconds", 45))
    poll_interval = int(verify_cfg.get("poll_interval_seconds", 3))
    contains = verify_cfg.get("console_contains_for_email_success", [])

    # trigger
    trig = trigger_jenkins_job(cfg, "email_test_job", parameters={"mode": "success"})
    if not trig["success"]:
        return trig

    # find last build and verify
    try:
        b = _get_last_build_number(cfg, job)
        if b is None:
            return {"success": False, "message": "No builds found for email test job", "details": {"job": job}}

        done, info = _wait_for_build_complete(cfg, job, b, wait_seconds, poll_interval)
        console = _get_console_text(cfg, job, b)

        # Heuristic: check build result + console keywords
        result_ok = (info.get("result") == "SUCCESS")
        keyword_ok = any(k.lower() in console.lower() for k in contains) if contains else True

        ok = result_ok and keyword_ok
        return {
            "success": ok,
            "message": "Email test job triggered and verified (heuristic)",
            "details": {
                "job": job,
                "build": b,
                "completed": done,
                "result": info.get("result"),
                "keyword_match": keyword_ok
            }
        }
    except Exception as e:
        return {"success": False, "message": "Failed verifying email job", "details": str(e)}

def verify_job_chaining(cfg):
    up = cfg["jenkins"]["jobs"].get("chain_upstream_job")
    down = cfg["jenkins"]["jobs"].get("chain_downstream_job")
    if not up or not down:
        return {"success": False, "message": "chain_upstream_job/chain_downstream_job not configured", "details": {}}

    verify_cfg = cfg["jenkins"].get("verify", {})
    wait_seconds = int(verify_cfg.get("wait_seconds", 45))
    poll_interval = int(verify_cfg.get("poll_interval_seconds", 3))
    lookback = int(verify_cfg.get("downstream_max_lookback_builds", 10))

    # record downstream last build BEFORE
    try:
        down_before = _get_last_build_number(cfg, down)
    except Exception:
        down_before = None

    trig = trigger_jenkins_job(cfg, "chain_upstream_job", parameters={"mode": "chain"})
    if not trig["success"]:
        return trig

    # wait a bit then see if downstream build increments
    deadline = time.time() + wait_seconds
    down_after = down_before

    try:
        while time.time() < deadline:
            down_after = _get_last_build_number(cfg, down)
            if down_before is None and down_after is not None:
                break
            if down_before is not None and down_after is not None and down_after > down_before:
                break
            time.sleep(poll_interval)

        ok = (down_before is None and down_after is not None) or (down_before is not None and down_after is not None and down_after > down_before)

        return {
            "success": ok,
            "message": "Job chaining verified by downstream build number change",
            "details": {
                "upstream": up,
                "downstream": down,
                "downstream_before": down_before,
                "downstream_after": down_after
            }
        }
    except Exception as e:
        return {"success": False, "message": "Failed verifying job chaining", "details": str(e)}