import os

def check_env_vars(cfg):
    env_map = cfg.get("env_variables", {})
    details = {}
    ok = True
    for logical, var in env_map.items():
        val = os.environ.get(var)
        details[logical] = {"var": var, "value": val}
        if not val:
            ok = False
    return {
        "success": ok,
        "message": "Checked environment variables",
        "details": details
    }