import json

from flask_restful import Resource, Api

from model import DbDict
from request_utils import RequestParser, APIException
from stores import actors_store


class Actor(DbDict):
    """Basic data access oject for working with Actors."""

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


class ActorsResource(Resource):

    def get(self):
        return [json.loads(actor[1]) for actor in actors_store.items()]

    def validate_post(self):
        parser = RequestParser()
        parser.add_argument('name', type=str, required=True, help="User defined name for this actor.")
        parser.add_argument('image', type=str, required=True,
                            help='Reference to image on docker hub for this actor.')
        parser.add_argument('subscriptions', type=[str], help='List of event ids to subscribe this actor to.')
        parser.add_argument('description', type=str)
        args = parser.parse_args()
        return args

    def post(self):
        args = self.validate_post()
        actor = Actor(args)
        actors_store[actor.id] = actor.to_db()

        self.new_actor_message()
        return actor.to_json()

    def new_actor_message(self):
        """Put a message on the new_actors queue that actor was created to create a new ActorExecutor for an actor."""
        # TODO
        pass


class ActorResource(Resource):
    def get(self, actor_id):
        try:
            actor = Actor.from_db(actors_store[actor_id])
        except KeyError:
            raise APIException(
                "actor not found: {}'".format(actor_id), 404)
        return actor

    def delete(self, actor_id):
        del actors_store[actor_id]
        self.delete_actor_message(actor_id)
        return {'msg': 'Delete successful.'}

    def delete_actor_message(self, actor_id):
        """Put a command message on the actor_messages queue that actor was deleted."""
        # TODO
        pass

class ActorStateResource(Resource):
    def get(self, actor_id):
        try:
            actor = Actor.from_db(actors_store[actor_id])
        except KeyError:
            raise APIException(
                "actor not found: {}'".format(actor_id), 404)
        return {'state': actor.state } or { 'state': None }

    def post(self, actor_id):
        args = self.validate_post()
        state = args['state']
        try:
            actor = Actor.from_db(actors_store[actor_id])
        except KeyError:
            raise APIException(
                "actor not found: {}'".format(actor_id), 404)
        actor.state = state
        actors_store[actor_id] = actor.to_db()
        return actor

    def validate_post(self):
        parser = RequestParser()
        parser.add_argument('state', type=str, required=True, help="Set the state for this actor.")
        args = parser.parse_args()
        return args
