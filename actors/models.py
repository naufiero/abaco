import json
import time

from stores import actors_store, logs_store, workers_store

class DbDict(dict):

    def __getattr__(self, key):
        return self[key]

    def __setattr__(self, key, value):
        self[key] = value

    def to_db(self):
        return json.dumps(self)

class Actor(DbDict):
    """Basic data access object for working with Actors."""

    def __init__(self, d):
        super(Actor, self).__init__(d)
        if not self.get('id'):
            self['id'] = Actor.get_id(self.name)

    @classmethod
    def get_id(cls, name):
        idx = 0
        while True:
            id = name + "_" + str(idx)
            if id not in actors_store:
                return id
            idx = idx + 1

    @classmethod
    def from_db(cls, s):
        a = Actor(json.loads(s))
        return a

    @classmethod
    def set_status(cls, actor_id, status):
        """Update the status of an actor"""
        actor = Actor.from_db(actors_store[actor_id])
        actor.status = status
        actors_store[actor.id] = actor.to_db()


class Subscription(DbDict):
    """Basic data access object for an Actor's subscription to an event."""

    def __init__(self, actor, d):
        super(Subscription, self).__init__(d)
        if not self.get('id'):
            self['id'] = Subscription.get_id(actor)

    @classmethod
    def get_id(cls, actor):
        idx = 0
        actor_id = actor.id
        try:
            subs = actor.subscriptions
        except AttributeError:
            return actor_id + "_sub_0"
        if not subs:
            return actor_id + "_sub_0"
        while True:
            id = actor_id + "_sub_" + str(idx)
            if id not in subs:
                return id
            idx = idx + 1

class Execution(DbDict):
    """Basic data access object representing an Actor execution."""

    def __init__(self, actor, d):
        super(Execution, self).__init__(d)
        if not self.get('id'):
            self['id'] = Execution.get_id(actor)

    @classmethod
    def get_id(cls, actor):
        idx = 0
        actor_id = actor.id
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
        logs_store[exc_id] = logs

class WorkerException(Exception):
    def __init__(self, message):
        Exception.__init__(self, message)
        self.message = message


def get_workers(actor_id):
    """Retrieve all workers for an actor."""
    try:
        workers = json.loads(workers_store[actor_id])
    except KeyError:
        return []
    return workers

def get_worker(actor_id, ch_name):
    """Retrieve a worker from the workers store."""
    workers = get_workers(actor_id)
    for worker in workers:
        if worker['ch_name'] == ch_name:
            return worker
    raise WorkerException("Worker not found.")

def delete_worker(actor_id, ch_name):
    """Deletes a worker from the worker store. Uses Redis optimistic locking to provide thread-safety since multiple
    clients could be attempting to delete workers at the same time.
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


def update_worker_status(actor_id, worker_ch, status):
    workers = get_workers(actor_id)
    for worker in workers:
        if worker['ch_name'] == worker_ch:
            worker['status'] = status
            worker['last_update'] = time.time()
    workers_store[actor_id] = json.dumps(workers)
