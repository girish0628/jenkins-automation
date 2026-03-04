import json
import platform
import datetime
from concurrent.futures import ThreadPoolExecutor

from checks.env_check import EnvVariableCheck
from checks.tool_check import ToolCheck
from checks.arcpy_check import ArcPyCheck, SDEReadCheck
from checks.network_check import NetworkShareCheck
from checks.jenkins_check import JenkinsAgentCheck
from checks.gitlab_check import GitLabCheck
from checks.disk_check import DiskCheck

from report_generator import generate_html


class JenkinsEnvironmentValidator:

    def __init__(self, config_file):

        with open(config_file) as f:
            self.config = json.load(f)

        self.tests = [
            EnvVariableCheck(self.config),
            ToolCheck(self.config),
            ArcPyCheck(self.config),
            SDEReadCheck(self.config),
            NetworkShareCheck(self.config),
            JenkinsAgentCheck(self.config),
            GitLabCheck(self.config),
            DiskCheck(self.config)
        ]

        self.results = []

    def run_test(self, test):

        try:
            res = test.run()
            print(f"{test.name} -> {res['success']}")
            return res

        except Exception as e:

            return {
                "name": test.name,
                "success": False,
                "message": str(e)
            }

    def run(self):

        with ThreadPoolExecutor(max_workers=5) as executor:

            futures = [executor.submit(self.run_test, t) for t in self.tests]

            for f in futures:
                self.results.append(f.result())

    def save_report(self):

        report = {

            "node": platform.node(),
            "environment": self.config["environment"],
            "timestamp": datetime.datetime.now().isoformat(),
            "results": self.results
        }

        with open("reports/report.json", "w") as f:
            json.dump(report, f, indent=4)

        generate_html(report)

        print("Reports generated")


if __name__ == "__main__":

    validator = JenkinsEnvironmentValidator("config.json")

    validator.run()

    validator.save_report()