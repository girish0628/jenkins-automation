import shutil
from .base import BaseCheck


class DiskCheck(BaseCheck):

    def run(self):

        min_space = self.config["disk"]["min_free_gb"]

        total, used, free = shutil.disk_usage("C:\\")

        free_gb = free / (1024**3)

        success = free_gb >= min_space

        return self.result(
            success,
            "Disk space validation",
            {"free_gb": free_gb}
        )