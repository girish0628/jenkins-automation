import requests

def check_gitlab_pat(cfg):
    g = cfg["gitlab"]
    headers = {"PRIVATE-TOKEN": g["pat"]}
    url = f"{g['api_base'].rstrip('/')}/projects/{g['project']}"
    try:
        r = requests.get(url, headers=headers, timeout=20)
        ok = (r.status_code == 200)
        details = r.json() if ok else {"status": r.status_code, "body": r.text}
        return {"success": ok, "message": "GitLab PAT access check", "details": details}
    except Exception as e:
        return {"success": False, "message": "GitLab PAT check failed", "details": str(e)}