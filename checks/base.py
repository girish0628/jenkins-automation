import datetime

class BaseCheck:

    def __init__(self, config):
        self.config = config
        self.name = self.__class__.__name__

    def run(self):
        raise NotImplementedError("Subclasses must implement run()")

    def result(self, success, message="", details=None):
        return {
            "name": self.name,
            "success": success,
            "message": message,
            "details": details or {},
            "timestamp": datetime.datetime.now().isoformat()
        }