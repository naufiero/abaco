
from flask import request, g
from flask_restful import Resource

from channels import ActorMsgChannel, CommandChannel
from models import Actor, get_workers
from request_utils import RequestParser, APIException, ok
from stores import actors_store

class MessagesResource(Resource):

    def get(self, actor_id):
        # check that actor exists
        id = Actor.get_dbid(g.tenant, actor_id)
        try:
            actor = Actor.from_db(actors_store[id])
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
        # build a dictionary of k:v pairs from the query parameters, and pass a single
        # additional object 'message' from within the post payload. Note that 'message'
        # need not be JSON data.
        for k, v in request.args.items():
            if k == 'message':
                continue
            d[k] = v
        if hasattr(g, 'user'):
            d['_abaco_username'] = g.user
        if hasattr(g, 'jwt'):
            d['_abaco_jwt'] = g.jwt
        if hasattr(g, 'api_server'):
            d['_abaco_api_server'] = g.api_server
        id = Actor.get_dbid(g.tenant, actor_id)
        ch = ActorMsgChannel(actor_id=id)
        ch.put_msg(message=args['message'], d=d)
        # make sure at least one worker is available
        workers = get_workers(id)
        if len(workers) < 1:
            ch = CommandChannel()
            actor = Actor.from_db(actors_store[id])
            ch.put_cmd(actor_id=id, image=actor.image, num=1, stop_existing=False)

        return ok(result={'msg': args['message']})