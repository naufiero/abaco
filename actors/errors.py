"""All exceptions thrown by the Abaco system"""

import logging

class BaseAbacoError(Exception):
    def __init__(self, msg=None):
        self.msg = msg


class DAOError(BaseAbacoError):
    pass


class WorkerException(BaseAbacoError):
    pass


class ExecutionException(BaseAbacoError):
    pass


class PermissionsException(BaseAbacoError):
    pass


class ClientException(BaseAbacoError):
    pass
