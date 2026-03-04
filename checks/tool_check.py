import subprocess
from .base import BaseCheck


class ToolCheck(BaseCheck):

    def run_cmd(self, cmd):

        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
            return True, output.decode().strip()

        except subprocess.CalledProcessError as e:
            return False, e.output.decode()

    def run(self):

        tools = self.config["tools"]

        node_ok, node_out = self.run_cmd(f"{tools['node_cmd']} -v")
        fme_ok, fme_out = self.run_cmd(f"{tools['fme_cmd']} --version")

        return self.result(
            node_ok and fme_ok,
            "Tool version check",
            {
                "node": node_out,
                "fme": fme_out
            }
        )