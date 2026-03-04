import os
from .base import BaseCheck


class EnvVariableCheck(BaseCheck):

    def run(self):

        env_vars = self.config["env_variables"]

        details = {}
        success = True

        for name, var in env_vars.items():

            value = os.environ.get(var)

            if not value:
                success = False

            details[name] = {
                "variable": var,
                "value": value
            }

        return self.result(success, "Environment variables validation", details)