import os
import time
from .base import BaseCheck


class NetworkShareCheck(BaseCheck):

    def run(self):

        shares = self.config["network_shares"]

        results = []
        success = True

        for share in shares:

            path = share["path"]

            try:

                testfile = os.path.join(path, f"jenkins_test_{int(time.time())}.txt")

                with open(testfile, "w") as f:
                    f.write("test")

                with open(testfile) as f:
                    f.read()

                os.remove(testfile)

                results.append({"path": path, "status": "OK"})

            except Exception as e:

                success = False
                results.append({"path": path, "error": str(e)})

        return self.result(success, "Network share test", results)