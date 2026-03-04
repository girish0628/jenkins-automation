import requests
from .base import BaseCheck


class JenkinsAgentCheck(BaseCheck):

    def run(self):

        j = self.config["jenkins"]

        url = f"{j['url']}/computer/api/json"

        try:

            r = requests.get(url, auth=(j["user"], j["api_token"]))
            data = r.json()

            agents = []

            for node in data["computer"]:
                agents.append({
                    "name": node["displayName"],
                    "offline": node["offline"]
                })

            return self.result(True, "Jenkins agents checked", agents)

        except Exception as e:

            return self.result(False, "Jenkins API error", str(e))