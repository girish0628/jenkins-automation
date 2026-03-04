import os
import subprocess
import tempfile
from .base import BaseCheck


class ArcPyCheck(BaseCheck):

    def run_arcpy(self, python_path, code):

        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".py") as f:
            f.write(code)
            script = f.name

        try:
            output = subprocess.check_output([python_path, script])
            return True, output.decode()

        except Exception as e:
            return False, str(e)

    def run(self):

        env_var = self.config["sde_read_test"]["arcpy_python_env_var"]

        python_path = os.environ.get(env_var)

        if not python_path:
            return self.result(False, "ArcPy python environment not found")

        code = """
import arcpy
print(arcpy.ProductInfo())
"""

        ok, output = self.run_arcpy(python_path, code)

        return self.result(ok, "ArcPy license check", {"output": output})


class SDEReadCheck(BaseCheck):

    def run(self):

        sde = self.config["sde_read_test"]

        env_var = sde["arcpy_python_env_var"]

        python_path = os.environ.get(env_var)

        code = f"""
import arcpy
arcpy.env.workspace=r"{sde['sde_connection_file']}"

rows=0
with arcpy.da.SearchCursor("{sde['dataset']}",["OID@"]) as cursor:
    for r in cursor:
        rows+=1
        if rows>{sde['max_rows']}:
            break

print("ROWS:",rows)
"""

        try:
            output = subprocess.check_output([python_path, "-c", code])
            return self.result(True, "SDE Read Test", output.decode())

        except Exception as e:
            return self.result(False, "SDE Read failed", str(e))