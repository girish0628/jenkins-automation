import requests
from .base import BaseCheck


class GitLabCheck(BaseCheck):

    def run(self):

        g = self.config["gitlab"]

        headers = {"PRIVATE-TOKEN": g["pat"]}

        url = f"{g['api_base']}/projects/{g['project']}"

        r = requests.get(url, headers=headers)

        if r.status_code == 200:

            return self.result(True, "GitLab PAT valid")

        return self.result(False, "GitLab PAT invalid", r.text)