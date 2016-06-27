from copy import deepcopy
import json
import time
import uuid

from codes import SUBMITTED
from config import Config
import errors
from request_utils import RequestParser
from stores import actors_store, executions_store, logs_store, permissions_store, workers_store


class DbDict(dict):
    """Class for persisting a Python dictionary."""

    def __getattr__(self, key):
        # returning an AttributeError is important for making deepcopy work. cf.,
        # http://stackoverflow.com/questions/25977996/supporting-the-deep-copy-operation-on-a-custom-class
        try:
            return self[key]
        except KeyError as e:
            raise AttributeError(e)

    def __setattr__(self, key, value):
        self[key] = value

    def to_db(self):
        # json serialization now happening in the store class. @todo - should remove all uses of .to_db
        return self
        # return json.dumps(self)


class AbacoDAO(DbDict):
    """Base Data Access Object class for Abaco models."""

    # the parameters for the DAO
    # tuples of the form (param name, required/optional/provided/derived, attr_name, type, help, default)
    # should be defined in the subclass.
    #
    #
    # required: these fields are required in the post/put methods of the web app.
    # optional: these fields are optional in the post/put methods of the web app and have a default value.
    # provided: these fields are required to construct the DAO but are provided by the abaco client code, not the user
    #           and not the DAO class code.
    # derived: these fields are derived by the DAO class code and do not need to be passed.
    PARAMS = []

    def __init__(self, **kwargs):
        """Construct a DAO from **kwargs. Client can also create from a dictionary, d, using AbacoDAO(**d)"""
        for name, source, attr, typ, help, default in self.PARAMS:
            if source == 'required':
                try:
                    value = kwargs[name]
                except KeyError:
                    raise errors.DAOError("Required field {} missing".format(name))
            elif source == 'optional':
                value = kwargs.get(name, default)
            elif source == 'provided':
                try:
                    value = kwargs[name]
                except KeyError:
                    raise errors.DAOError("Required field {} missing.".format(name))
            else:
                # derived value - check to see if already computed
                if hasattr(self, name):
                    value = getattr(self, name)
                else:
                    value = self.get_derived_value(name, kwargs)
            setattr(self, attr, value)

    def get_uuid(self):
        """Generate a random uuid."""
        return str(uuid.uuid4())

    @classmethod
    def request_parser(cls):
        """Return a flask RequestParser object that can be used in post/put processing."""
        parser = RequestParser()
        for name, source, attr, typ, help, default in cls.PARAMS:
            if source == 'derived':
                continue
            required = source == 'required'
            parser.add_argument(name, type=typ, required=required, help=help, default=default)
        return parser

    @classmethod
    def from_db(cls, db_json):
        """Construct a DAO from a db serialization."""
        return cls(**db_json)

    def get_derived_value(self, name, d):
        """Compute a derived value for the attribute `name` from the dictionary d of attributes provided."""
        raise NotImplementedError


class Actor(AbacoDAO):
    """Basic data access object for working with Actors."""

    PARAMS = [
        # param_name, required/optional/provided/derived, attr_name, type, help, default
        ('name', 'required', 'name', str, 'User defined name for this actor.', None),
        ('image', 'required', 'image', str, 'Reference to image on docker hub for this actor.', None),

        ('stateless', 'optional', 'stateless', bool, 'Whether the actor stores private state.', False),
        ('description', 'optional', 'description', str,  'Description of this actor', ''),
        ('privileged', 'optional', 'privileged', bool, 'Whether this actor runs in privileged mode.', False),
        ('default_environment', 'optional', 'default_environment', dict, 'Default environmental variables and values.', {}),
        ('status', 'optional', 'status', str, 'Current status of the actor.', SUBMITTED),
        ('executions', 'optional', 'executions', dict, 'Executions for this actor.', {}),

        ('tenant', 'provided', 'tenant', str, 'The tenant that this actor belongs to.', None),

        ('db_id', 'derived', 'db_id', str, 'Primary key in the database for this actor.', None),
        ('id', 'derived', 'id', str, 'Human readable id for this actor.', None),
        ]

    def get_derived_value(self, name, d):
        """Compute a derived value for the attribute `name` from the dictionary d of attributes provided."""
        # first, see if the attribute is already in the object:
        if hasattr(self, 'id'):
            return
        # next, see if it was passed:
        try:
            return d[name]
        except KeyError:
            pass
        # if not, generate an id
        try:
            actor_id, db_id = self.generate_id(d['name'], d['tenant'])
        except KeyError:
            raise errors.DAOError("Required field name or tenant missing")
        self.id = actor_id
        self.db_id = db_id
        if name == 'id':
            return actor_id
        else:
            return db_id

    def display(self):
        """Return a representation fit for display."""
        self.pop('db_id')
        self.pop('executions')
        return self

    def generate_id(self, name, tenant):
        """Generate an id for a new actor."""
        id = self.get_uuid()
        return id, Actor.get_dbid(tenant, id)

    @classmethod
    def get_dbid(cls, tenant, id):
        """Return the key used in redis from the "display_id" and tenant. """
        return str('{}_{}'.format(tenant, id))

    @classmethod
    def get_display_id(cls, tenant, dbid):
        """Return the display id from the dbid."""
        return dbid.strip('{}_'.format(tenant))

    @classmethod
    def set_status(cls, actor_id, status):
        """Update the status of an actor"""
        actors_store.update(actor_id, 'status', status)


class Execution(AbacoDAO):
    """Basic data access object for working with actor executions."""

    PARAMS = [
        # param_name, required/optional/provided/derived, attr_name, type, help, default
        ('tenant', 'required', 'tenant', str, 'The tenant that this execution belongs to.', None),
        ('actor_id', 'required', 'actor_id', str, 'The human readable id for the actor associated with this execution.', None),
        ('runtime', 'required', 'runtime', str, 'Runtime, in milliseconds, of the execution.', None),
        ('cpu', 'required', 'cpu', str, 'CPU usage, in user jiffies, of the execution.', None),
        ('io', 'required', 'io', str,
         'Block I/O usage, in number of 512-byte sectors read from and written to, by the execution.', None),
        ('id', 'derived', 'id', str, 'Human readable id for this execution.', None),
        ('status', 'required', 'status', str, 'Status of the execution.', None)
    ]

    def get_derived_value(self, name, d):
        """Compute a derived value for the attribute `name` from the dictionary d of attributes provided."""
        # first, see if the attribute is already in the object:
        try:
            if d[name]:
                return d[name]
        except KeyError:
            pass
        return self.get_uuid()

    @classmethod
    def add_execution(cls, actor_id, ex):
        """
        Add an execution to an actor.
        :param actor_id: str; the dbid of the actor
        :param ex: dict describing the execution.
        :return:
        """
        actor = Actor.from_db(actors_store[actor_id])
        ex.update({'actor_id': actor_id,
                   'tenant': actor.tenant,
                   })
        execution = Execution(**ex)

        try:
            executions_store.update(actor_id, execution.id, execution)
        except KeyError:
            # if actor has no executions, a KeyError will be thrown
            executions_store[actor_id] = {execution.id: execution}
        return execution.id

    @classmethod
    def finalize_execution(cls, actor_id, execution_id, status, stats):
        """Update an execution status and stats after the execution is complete or killed.
         `actor_id` should be the dbid of the actor.
         `execution_id` should be the id of the execution returned from a prior call to add_execution.
         `status` should be the final status of the execution.
         `stats` parameter should be a dictionary with io, cpu, and runtime."""
        if not 'io' in stats:
            raise errors.ExecutionException("'io' parameter required to finalize execution.")
        if not 'cpu' in stats:
            raise errors.ExecutionException("'cpu' parameter required to finalize execution.")
        if not 'runtime' in stats:
            raise errors.ExecutionException("'runtime' parameter required to finalize execution.")
        try:
            executions_store.update_subfield(actor_id, execution_id, 'status', status)
            executions_store.update_subfield(actor_id, execution_id, 'io', stats['io'])
            executions_store.update_subfield(actor_id, execution_id, 'cpu', stats['cpu'])
            executions_store.update_subfield(actor_id, execution_id, 'runtime', stats['runtime'])
        except KeyError:
            raise errors.ExecutionException("Execution {} not found.".format(execution_id))


    @classmethod
    def set_logs(cls, exc_id, logs):
        """
        Set the logs for an execution.
        :param exc_id: the id of the execution (str)
        :param logs: dict describing the logs
        :return:
        """
        log_ex = Config.get('web', 'log_ex')
        try:
            log_ex = int(log_ex)
        except ValueError:
            log_ex = -1
        if log_ex > 0:
            logs_store.set_with_expiry(exc_id, logs, log_ex)
        else:
            logs_store[exc_id] = logs

    def display(self):
        """Return a display version of the execution."""
        tenant = self.pop('tenant')
        self.actor_id = Actor.get_display_id(tenant, self.actor_id)
        return self

class Worker(AbacoDAO):
    """Basic data access object for working with Workers."""

    PARAMS = [
        # param_name, required/optional/provided/derived, attr_name, type, help, default
        ('tenant', 'required', 'tenant', str, 'The tenant that this worker belongs to.', None),
        ('ch_name', 'required', 'ch_name', str, 'The worker id and the name of the associated worker chanel.', None),
        ('image', 'required', 'image', list, 'The list of images associated with this worker', None),
        ('location', 'required', 'location', str, 'The location of the docker daemon used by this worker.', None),
        ('cid', 'required', 'cid', str, 'The container ID of this worker.', None),
        ('status', 'required', 'status', str, 'Status of the worker.', None),
        ('host_id', 'required', 'host_id', str, 'id of the host where worker is running.', None),
        ('host_ip', 'required', 'host_ip', str, 'ip of the host where worker is running.', None),
        ('last_execution', 'required', 'last_execution', str, 'Last time the worker executed an actor container.', None),
        ]

    @classmethod
    def get_workers(cls, actor_id):
        """Retrieve all workers for an actor. Pass db_id as `actor_id` parameter."""
        try:
            return workers_store[actor_id]
        except KeyError:
            return {}

    @classmethod
    def get_worker(cls, actor_id, ch_name):
        """Retrieve a worker from the workers store. Pass db_id as `actor_id` parameter."""
        try:
            return workers_store[actor_id][ch_name]
        except KeyError:
            raise errors.WorkerException("Worker not found.")

    @classmethod
    def delete_worker(cls, actor_id, ch_name):
        """Deletes a worker from the worker store. Uses Redis optimistic locking to provide thread-safety since multiple
        clients could be attempting to delete workers at the same time. Pass db_id as `actor_id`
        parameter.
        """
        try:
            workers_store.pop_field(actor_id, ch_name)
        except KeyError:
            raise errors.WorkerException("Worker not found.")

    @classmethod
    def add_worker(cls, actor_id, worker):
        """Add a worker to an actor's collection of workers."""
        workers_store.update(actor_id, worker['ch_name'], worker)

    @classmethod
    def update_worker_execution_time(cls, actor_id, ch_name):
        """Pass db_id as `actor_id` parameter."""
        now = time.time()
        workers_store.update_subfield(actor_id, ch_name, 'last_execution', now)
        workers_store.update_subfield(actor_id, ch_name, 'last_update', now)

    @classmethod
    def update_worker_status(cls, actor_id, ch_name, status):
        """Pass db_id as `actor_id` parameter."""
        workers_store.update_subfield(actor_id, ch_name, 'status', status)


def get_permissions(actor_id):
    """ Return all permissions for an actor
    :param actor_id:
    :return:
    """
    try:
        permissions = json.loads(permissions_store[actor_id])
        return permissions
    except KeyError:
        raise errors.PermissionsException("Actor {} does not exist".format(actor_id))

def add_permission(user, actor_id, level):
    """Add a permission for a user and level to an actor."""
    try:
        permissions = get_permissions(actor_id)
    except errors.PermissionsException:
        permissions = []
    for pem in permissions:
        if pem.get('user') == 'user' and pem.get('level') == level:
            return
    permissions.append({'user': user,
                        'level': level})
    permissions_store[actor_id] = json.dumps(permissions)