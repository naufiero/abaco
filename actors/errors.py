"""All exceptions thrown by the Abaco system"""

import logging

class BaseAbacoError(Exception):
    def __init__(self, msg=None, code=400):
        self.msg = msg
        self.code = code

class DAOError(BaseAbacoError):
    pass


class ResourceError(BaseAbacoError):
    pass


class WorkerException(BaseAbacoError):
    pass


class ExecutionException(BaseAbacoError):
    pass


class PermissionsException(BaseAbacoError):
    pass


class ClientException(BaseAbacoError):
    pass
