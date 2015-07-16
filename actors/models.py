import json
from stores import actors_store

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
