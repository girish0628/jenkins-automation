import os
import time

def check_network_shares(cfg):
    shares = cfg.get("network_shares", [])
    details = []
    all_ok = True

    for s in shares:
        path = s.get("path")
        rw_test = bool(s.get("rw_test", True))

        item = {"path": path, "exists": False, "rw_ok": None, "message": ""}
        try:
            item["exists"] = os.path.exists(path)
            if not item["exists"]:
                item["message"] = "Path not reachable"
                all_ok = False
            else:
                if rw_test:
                    fn = os.path.join(path, f"rw_test_{int(time.time())}.txt")
                    with open(fn, "w", encoding="utf-8") as f:
                        f.write("test")
                    with open(fn, "r", encoding="utf-8") as f:
                        _ = f.read()
                    os.remove(fn)
                    item["rw_ok"] = True
                else:
                    item["rw_ok"] = "skipped"
        except Exception as e:
            item["rw_ok"] = False
            item["message"] = str(e)
            all_ok = False

        details.append(item)

    return {"success": all_ok, "message": "Network share connectivity test", "details": details}