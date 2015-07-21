
from flask import request
from flask_restful import Resource

from channels import ActorMsgChannel
from models import Actor
from request_utils import RequestParser, APIException, ok
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
        return ok(result={'messages': []})

    def validate_post(self):
        parser = RequestParser()
        parser.add_argument('message', type=str, required=True, help="The message to send to the actor.")
        args = parser.parse_args()
        return args

    def post(self, actor_id):
        args = self.validate_post()
        d = {}
        for k, v in request.args.items():
            if k == 'message':
                continue
            d[k] = v
        ch = ActorMsgChannel(actor_id=actor_id)
        ch.put_msg(msg=args['message'], d=d)
        return ok(result={'msg': args['message']})