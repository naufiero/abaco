
from flask_restful import Resource, Api

from models import Actor
from request_utils import RequestParser, APIException
from stores import actors_store

class MessagesResource(Resource):

    def get(self, actor_id):
        # check that actor exists
        try:
            actor = Actor.from_db(actors_store[actor_id])
        except KeyError:
            raise APIException(
                "actor not found: {}'".format(actor_id), 404)
        # TODO
        # retrieve pending messages from the queue
        return {'messages': []}

    def validate_post(self):
        parser = RequestParser()
        parser.add_argument('message', type=str, required=True, help="The message to send to the actor.")
        args = parser.parse_args()
        return args

    def post(self, actor_id):
        args = self.validate_post()
        self.new_message(args['message'])
        return {'msg': 'Success'}

    def new_message(self, message):
        """Put a message on the new_actors queue that actor was created to create a new ActorExecutor for an actor."""
        # TODO
        pass
