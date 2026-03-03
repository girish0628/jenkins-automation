import subprocess

def _run(cmd_list):
    try:
        out = subprocess.check_output(cmd_list, stderr=subprocess.STDOUT, text=True, shell=False)
        return True, out.strip()
    except Exception as e:
        return False, str(e)

def check_tool_versions(cfg):
    tools = cfg.get("tools", {})
    node_cmd = tools.get("node_cmd", "node")
    fme_cmd = tools.get("fme_cmd", "fme")
    fme_args = tools.get("fme_version_args", ["--version"])

    ok_node, out_node = _run([node_cmd, "-v"])
    ok_fme, out_fme = _run([fme_cmd] + list(fme_args))

    return {
        "success": ok_node and ok_fme,
        "message": "Checked Node and FME versions",
        "details": {
            "node": {"success": ok_node, "output": out_node},
            "fme": {"success": ok_fme, "output": out_fme}
        }
    }