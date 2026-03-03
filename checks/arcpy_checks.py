import os
import subprocess
import tempfile
from pathlib import Path


def _python_from_env_var(env_var_name: str):
    val = os.environ.get(env_var_name)
    if not val:
        return None
    p = Path(val)
    # If env var points to python.exe
    if p.exists() and p.name.lower() == "python.exe":
        return str(p)
    # If env var points to env folder
    for cand in [p / "python.exe", p / "Scripts" / "python.exe"]:
        if cand.exists():
            return str(cand)
    return None


def _run_python(python_exe: str, code: str):
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
        tmp = f.name
    try:
        out = subprocess.check_output([python_exe, tmp], stderr=subprocess.STDOUT, text=True)
        return True, out.strip()
    except subprocess.CalledProcessError as e:
        return False, e.output.strip()
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass


def check_arcpy_license(cfg):
    lic = cfg.get("license_checks", {})
    arcpy3_var = lic.get("arcpy3_env_var", "GCC_ArcPy3")
    arcpy2_var = lic.get("arcpy2_env_var", "GCC_ArcPy2")

    py3 = _python_from_env_var(arcpy3_var)
    py2 = _python_from_env_var(arcpy2_var)

    code = r"""
import sys
try:
    import arcpy
    print("ARCPY_OK=True")
    try:
        print("PRODUCT_INFO=" + str(arcpy.ProductInfo()))
    except Exception as e:
        print("PRODUCT_INFO_ERROR=" + repr(e))
    print("PYTHON=" + sys.executable)
except Exception as e:
    print("ARCPY_OK=False")
    print("ERROR=" + repr(e))
    raise
"""

    details = {}
    ok_all = True

    if py3:
        ok, out = _run_python(py3, code)
        details["ArcPy3"] = {"python": py3, "success": ok, "output": out}
        ok_all = ok_all and ok
    else:
        ok_all = False
        details["ArcPy3"] = {"python": None, "success": False, "output": f"Could not resolve python from {arcpy3_var}"}

    if py2:
        ok, out = _run_python(py2, code)
        details["ArcPy2"] = {"python": py2, "success": ok, "output": out}
        ok_all = ok_all and ok
    else:
        # ArcPy2 might be optional in some environments
        details["ArcPy2"] = {"python": None, "success": False, "output": f"Could not resolve python from {arcpy2_var}"}
        ok_all = False

    return {"success": ok_all, "message": "ArcPy import/product info checks", "details": details}


def check_sde_read(cfg):
    sde = cfg.get("sde_read_test", {})
    env_var = sde.get("arcpy_python_env_var", "GCC_ArcPy3")
    python_exe = _python_from_env_var(env_var)

    if not python_exe:
        return {"success": False, "message": f"Could not resolve ArcPy python from env var {env_var}", "details": {}}

    sde_file = sde["sde_connection_file"]
    dataset = sde["dataset"]
    where = sde.get("where", "1=1")
    max_rows = int(sde.get("max_rows", 5))

    code = rf"""
import arcpy
arcpy.env.workspace = r"{sde_file}"
dataset = r"{dataset}"
where = r"{where}"
max_rows = {max_rows}

count = 0
fields = ["OID@"]

# Verify dataset exists
if not arcpy.Exists(dataset):
    raise RuntimeError("Dataset not found in SDE workspace: " + dataset)

with arcpy.da.SearchCursor(dataset, fields, where_clause=where) as cur:
    for row in cur:
        count += 1
        if count >= max_rows:
            break

print("SDE_READ_OK=True")
print("ROWS_READ=" + str(count))
"""

    ok, out = _run_python(python_exe, code)
    return {
        "success": ok,
        "message": "SDE read-only SearchCursor test",
        "details": {
            "python": python_exe,
            "sde_connection_file": sde_file,
            "dataset": dataset,
            "where": where,
            "max_rows": max_rows,
            "output": out
        }
    }