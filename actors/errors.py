"""All exceptions thrown by the Abaco system"""

from agaveflask.errors import BaseAgaveflaskError

class DAOError(BaseAgaveflaskError):
    pass


class ResourceError(BaseAgaveflaskError):
    pass


class WorkerException(BaseAgaveflaskError):
    pass


class ExecutionException(BaseAgaveflaskError):
    pass


class PermissionsException(BaseAgaveflaskError):
    pass


class ClientException(BaseAgaveflaskError):
    pass
