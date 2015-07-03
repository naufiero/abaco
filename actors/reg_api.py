import json

from flask import Flask, request
from flask_restful import Resource, Api
import flask.ext.restful.reqparse as reqparse
from werkzeug.exceptions import ClientDisconnected

from stores import actors_store

app = Flask(__name__)
api = Api(app)


class APIException(Exception):

    def __init__(self, message, code=400):
        Exception.__init__(self, message)
        self.message = message
        self.code = code

class RequestParser(reqparse.RequestParser):
    """Wrap reqparse to raise APIException."""

    def parse_args(self, *args, **kwargs):
        try:
            return super(RequestParser, self).parse_args(*args, **kwargs)
        except ClientDisconnected as exc:
            raise APIException(exc.data['message'], 400)

class ActorsResource(Resource):

    def get(self):
        return [actor for actor in actors_store.items()]

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
        name = args['name']
        image = args['image']
        subscriptions = args.get('subscriptions', None)
        description = args.get('description', None)
        state = args.get('state', None)
        actor = Actor(name, image, subscriptions, description, state)
        actors_store[actor.id] = json.dumps(actor.to_json())
        self.new_actor_message()
        return actor.to_json()

    def new_actor_message(self):
        """Put a message on the new_actors queue that actor was created to create a new ActorExecutor for an actor."""
        # TODO
        pass

class Actor(object):

    def __init__(self, name, image, subscriptions=None, description=None, state=None):
        self.name = name
        self.id = self.get_id()
        self.image = image
        self.subscriptions = subscriptions
        self.description = description
        self.state = state

    def get_id(self):
        idx = 0
        while True:
            id = self.name + "_" + str(idx)
            if id not in actors_store:
                return id
            idx = idx + 1

    def to_json(self):
        obj = {'id': self.id,
               'name': self.name,
               'image': self.image,
               'subscriptions': self.subscriptions,
               'description': self.description,
               'state': self.state
        }
        return obj


class ActorResource(Resource):
    def get(self, actor_id):
        try:
            return actors_store[actor_id]
        except KeyError:
            raise APIException(
                "actor not found: {}'".format(actor_id), 404)

    def delete(self, actor_id):
        del actors_store[actor_id]
        self.delete_actor_message(actor_id)
        return {'msg': 'Delete successful.'}

    def delete_actor_message(self, actor_id):
        """Put a command message on the actor_messages queue that actor was deleted."""
        pass
        
api.add_resource(ActorsResource, '/actors')
api.add_resource(ActorResource, '/actors/<string:actor_id>')


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
