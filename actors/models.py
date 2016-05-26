from copy import deepcopy
import json
import time

from codes import SUBMITTED
from config import Config
import errors
from request_utils import RequestParser
from stores import actors_store, logs_store, workers_store

class DbDict(dict):
    """Class for persisting a Python dictonary."""

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
        return json.dumps(self)


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
                value = self.get_derived_value(name, kwargs)
            setattr(self, attr, value)

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
        return cls(**json.loads(db_json))

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
        try:
            if d[name]:
                return d[name]
        except KeyError:
            pass
        # if not, generate an id
        try:
            actor_id, db_id = Actor.generate_id(d['name'], d['tenant'])
        except KeyError:
            raise errors.DAOError("Required field name or tenant missing")
        if name == 'id':
            return actor_id
        elif name == 'db_id':
            return db_id

    def display(self):
        """Return a representation fit for display."""
        # make a deep copy to prevent destructive behavior in the db.
        result = deepcopy(self)
        db_id = result.pop('db_id')
        if not result.executions:
            return result
        # strip tenant from execution id's
        for k,v in result.executions.items():
            if not '{}_'.format(result.tenant) in k:
            # if len(k.split('{}_'.format(result.tenant))) < 2:
                print("Data issue in subscription key: {}, value: {}, for actor with db_id: {} and tenant: {}".format(k, v, db_id, self.tenant))
                ex_display_id = k
            else:
                ex_display_id = k.split('{}_'.format(result.tenant))[1]
                # change the id in the value as well
                v['id'] = ex_display_id
            v.pop('tenant', None)
            result.executions[ex_display_id] = result.executions.pop(k)

        return result

    @classmethod
    def generate_id(cls, name, tenant):
        """Generate an id for a new actor."""
        idx = 0
        while True:
            db_id = '{}_{}_{}'.format(tenant, name, idx)
            id = '{}_{}'.format(name, idx)
            if db_id not in actors_store:
                return id, db_id
            idx = idx + 1

    @classmethod
    def get_dbid(cls, tenant, id):
        """Return the key used in redis from the "display_id" and tenant. """
        return '{}_{}'.format(tenant, id)

    # @classmethod
    # def from_db(cls, s):
    #     a = Actor(**json.loads(s))
    #     return a

    @classmethod
    def set_status(cls, actor_id, status):
        """Update the status of an actor"""
        actor = Actor.from_db(actors_store[actor_id])
        actor.status = status
        actors_store[actor_id] = actor.to_db()


class Execution(DbDict):
    """Basic data access object representing an Actor execution."""

    def __init__(self, actor, d):
        super(Execution, self).__init__(d)
        self.tenant = actor.tenant
        if not self.get('id'):
            self['id'] = Execution.get_id(actor)

    @classmethod
    def get_id(cls, actor):
        idx = 0
        actor_id = actor.db_id
        try:
            excs = actor.executions
        except KeyError:
            return actor_id + "_exc_0"
        if not excs:
            return actor_id + "_exc_0"
        while True:
            id = actor_id + "_exc_" + str(idx)
            if id not in excs:
                return id
            idx = idx + 1

    @classmethod
    def get_dbid(cls, tenant, id):
        """Return the key used in redis from the "display_id" and tenant. """
        return '{}_{}'.format(tenant, id)

    @classmethod
    def add_execution(cls, actor_id, ex):
        """
        Add an execution to an actor.
        :param actor_id: str
        :param ex: dict
        :return:
        """
        actor = Actor.from_db(actors_store[actor_id])
        execution = Execution(actor, ex)
        actor.executions[execution.id] = execution
        actors_store[actor_id] = actor.to_db()
        return execution.id

    @classmethod
    def set_logs(cls, exc_id, logs):
        """
        Set the logs for an execution.
        :param actor_id: str
        :param ex: dict
        :return:
        """
        log_ex = Config.get('web', 'log_ex')
        try:
            log_ex = int(log_ex)
        except Exception:
            log_ex = -1
        if log_ex > 0:
            logs_store.set_with_expiry(exc_id, logs, log_ex)
        else:
            logs_store[id] = logs


class WorkerException(Exception):
    def __init__(self, message):
        Exception.__init__(self, message)
        self.message = message


def get_workers(actor_id):
    """Retrieve all workers for an actor. Pass db_id as `actor_id` parameter."""
    try:
        workers = json.loads(workers_store[actor_id])
    except KeyError:
        return []
    return workers

def get_worker(actor_id, ch_name):
    """Retrieve a worker from the workers store. Pass db_id as `actor_id` parameter."""
    workers = get_workers(actor_id)
    for worker in workers:
        if worker['ch_name'] == ch_name:
            return worker
    raise WorkerException("Worker not found.")

def delete_worker(actor_id, ch_name):
    """Deletes a worker from the worker store. Uses Redis optimistic locking to provide thread-safety since multiple
    clients could be attempting to delete workers at the same time. Pass db_id as `actor_id`
    parameter.
    """
    def safe_delete(pipe):
        """Removes a worker from the worker store in a thread-safe way; this is the callable function to be used
        with the redis-py transaction method. See the Pipelines section of the docs:
        https://github.com/andymccurdy/redis-py
        """
        workers = pipe.get(actor_id)
        workers = json.loads(workers)
        i = -1
        for idx, worker in enumerate(workers):
            if worker.get('ch_name') == ch_name:
                i = idx
                break
        if i > -1:
            print("safe_delete found worker, removing.")
            workers.pop(i)
        else:
            print("safe_delete did not find worker: {}. workers:{}".format(ch_name, workers))
        pipe.multi()
        pipe.set(actor_id, json.dumps(workers))

    workers_store.transaction(safe_delete, actor_id)

def update_worker_execution_time(actor_id, worker_ch):
    """Pass db_id as `actor_id` parameter."""
    workers = get_workers(actor_id)
    now = time.time()
    for worker in workers:
        if worker['ch_name'] == worker_ch:
            worker['last_execution'] = now
            worker['last_update'] = now
    workers_store[actor_id] = json.dumps(workers)

def update_worker_status(actor_id, worker_ch, status):
    """Pass db_id as `actor_id` parameter."""
    workers = get_workers(actor_id)
    for worker in workers:
        if worker['ch_name'] == worker_ch:
            worker['status'] = status
            worker['last_update'] = time.time()
    workers_store[actor_id] = json.dumps(workers)
