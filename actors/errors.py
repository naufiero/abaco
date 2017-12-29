"""All exceptions thrown by the Abaco system"""
import os
from agaveflask.errors import BaseAgaveflaskError

from config import Config

TAG = os.environ.get('service_TAG') or Config.get('general', 'TAG')

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

errors = {
    'MethodNotAllowed': {
        'message': "Invalid HTTP method on requested resource.",
        'status': "error",
        'version': TAG
    },
}