import shutil
import winreg

def check_disk_space(cfg):
    disk_cfg = cfg.get("disk", {})
    drives = disk_cfg.get("drives", ["C:\\"])
    min_free_gb = float(disk_cfg.get("min_free_gb", 10))

    details = []
    ok_all = True

    for d in drives:
        total, used, free = shutil.disk_usage(d)
        free_gb = free / (1024**3)
        ok = free_gb >= min_free_gb
        ok_all = ok_all and ok
        details.append({
            "drive": d,
            "free_gb": round(free_gb, 2),
            "min_free_gb": min_free_gb,
            "ok": ok
        })

    return {"success": ok_all, "message": "Disk free-space check", "details": details}


def _read_uninstall_key(root, path):
    apps = []
    try:
        with winreg.OpenKey(root, path) as k:
            i = 0
            while True:
                try:
                    sub = winreg.EnumKey(k, i)
                    i += 1
                    with winreg.OpenKey(k, sub) as sk:
                        name = _get_str(sk, "DisplayName")
                        if not name:
                            continue
                        apps.append({
                            "name": name,
                            "version": _get_str(sk, "DisplayVersion"),
                            "publisher": _get_str(sk, "Publisher"),
                            "install_date": _get_str(sk, "InstallDate")
                        })
                except OSError:
                    break
    except OSError:
        pass
    return apps

def _get_str(k, name):
    try:
        v, _ = winreg.QueryValueEx(k, name)
        return str(v)
    except OSError:
        return None

def check_software_inventory(cfg):
    lim = int(cfg.get("software_inventory", {}).get("limit", 300))

    apps = []
    apps += _read_uninstall_key(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")
    apps += _read_uninstall_key(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall")

    # dedupe by name+version
    seen = set()
    uniq = []
    for a in sorted(apps, key=lambda x: (x["name"] or "").lower()):
        key = (a.get("name"), a.get("version"))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(a)

    return {
        "success": True,
        "message": "Installed software inventory (registry uninstall keys)",
        "details": {"count": len(uniq), "items": uniq[:lim], "truncated_to": lim}
    }