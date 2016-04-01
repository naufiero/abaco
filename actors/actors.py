import json

from flask import g, request
from flask_restful import Resource, Api, inputs

from auth import add_permission
from channels import CommandChannel
from codes import SUBMITTED
from models import Actor, Execution
from request_utils import RequestParser, APIException, ok
from stores import actors_store, logs_store, permissions_store
from worker import shutdown_workers


class ActorsResource(Resource):

    def get(self):
        actors = []
        for k, v in actors_store.items():
            if k.startswith(g.tenant):
                actors.append(Actor.from_db(v).display())
        return ok(result=actors, msg="Actors retrieved successfully.")

    def validate_post(self):
        parser = Actor.request_parser()
        return parser.parse_args()

    def post(self):
        args = self.validate_post()
        args['tenant'] = g.tenant
        actor = Actor(**args)
        actors_store[actor.db_id] = actor.to_db()
        ch = CommandChannel()
        ch.put_cmd(actor_id=actor.db_id, image=actor.image)
        add_permission(g.user, actor.db_id, 'UPDATE')
        return ok(result=actor.display(), msg="Actor created successfully.")


class ActorResource(Resource):
    def get(self, actor_id):
        id = Actor.get_dbid(g.tenant, actor_id)
        try:
            actor = Actor.from_db(actors_store[id])
        except KeyError:
            raise APIException(
                "actor not found: {}'".format(actor_id), 404)
        return ok(result=actor.display(), msg="Actor retrieved successfully.")

    def delete(self, actor_id):
        id = Actor.get_dbid(g.tenant, actor_id)
        shutdown_workers(id)
        try:
            actor = Actor.from_db(actors_store[id])
            executions = actor.get('executions') or {}
            for ex_id, val in executions.items():
                del logs_store[ex_id]
        except KeyError:
            print("Did not find actor with id: {}".format(id))
        del actors_store[id]
        del permissions_store[id]
        return ok(result=None, msg='Actor deleted successfully.')

    def put(self, actor_id):
        id = Actor.get_dbid(g.tenant, actor_id)
        try:
            actor = Actor.from_db(actors_store[id])
        except KeyError:
            raise APIException(
                "actor not found: {}'".format(actor_id), 404)
        args = self.validate_put(actor)
        update_image = False
        if args['image'] == actor.image:
            args['status'] = actor.status
        else:
            update_image = True
            args['status'] = SUBMITTED
        # for k, v in actor.items():
        #     if not args.get(k):
        #         args[k] = v
        actor = Actor(**args)
        actors_store[actor.db_id] = actor.to_db()
        if update_image:
            ch = CommandChannel()
            ch.put_cmd(actor_id=actor.db_id, image=actor.image)
        return ok(result=actor.display(), msg="Actor updated successfully.")

    def validate_put(self, actor):
        # inherit derived attributes from the original actor, including id and db_id:
        args = actor
        args['tenant'] = actor.tenant
        parser = Actor.request_parser()
        parser.remove_argument('name')
        # this update overrides all required and optional attributes
        args.update(parser.parse_args())
        return args

    def delete_actor_message(self, actor_id):
        """Put a command message on the actor_messages queue that actor was deleted."""
        # TODO
        pass


class ActorStateResource(Resource):
    def get(self, actor_id):
        id = Actor.get_dbid(g.tenant, actor_id)
        try:
            actor = Actor.from_db(actors_store[id])
            state = actor.get('state')
        except KeyError:
            raise APIException(
                "actor not found: {}'".format(actor_id), 404)
        return ok(result={'state': state }, msg="Actor state retrieved successfully.")

    def post(self, actor_id):
        id = Actor.get_dbid(g.tenant, actor_id)
        args = self.validate_post()
        state = args['state']
        try:
            actor = Actor.from_db(actors_store[id])
        except KeyError:
            raise APIException(
                "actor not found: {}'".format(actor_id), 404)
        actor.state = state
        actors_store[id] = actor.to_db()
        return ok(result=actor.display(), msg="State updated successfully.")

    def validate_post(self):
        parser = RequestParser()
        parser.add_argument('state', type=str, required=True, help="Set the state for this actor.")
        args = parser.parse_args()
        return args


class ActorExecutionsResource(Resource):
    def get(self, actor_id):
        id = Actor.get_dbid(g.tenant, actor_id)
        try:
            actor = Actor.from_db(actors_store[id])
        except KeyError:
            raise APIException(
                "actor not found: {}'".format(actor_id), 404)
        tot = {'total_executions': 0, 'total_cpu': 0, 'total_io':0, 'total_runtime': 0, 'ids':[]}
        actor.display()
        executions = actor.get('executions') or {}
        for id, val in executions.items():
            tot['ids'].append(id)
            tot['total_executions'] += 1
            tot['total_cpu'] += int(val['cpu'])
            tot['total_io'] += int(val['io'])
            tot['total_runtime'] += int(val['runtime'])
        return ok(result=tot, msg="Actor executions retrieved successfully.")

    def post(self, actor_id):
        id = Actor.get_dbid(g.tenant, actor_id)
        try:
            actor = Actor.from_db(actors_store[id])
        except KeyError:
            raise APIException(
                "actor not found: {}'".format(actor_id), 404)
        args = self.validate_post()
        Execution.add_execution(id, args)
        return ok(result=actor.display(), msg="Actor execution added successfully.")

    def validate_post(self):
        parser = RequestParser()
        parser.add_argument('runtime', type=str, required=True, help="Runtime, in milliseconds, of the execution.")
        parser.add_argument('cpu', type=str, required=True, help="CPU usage, in user jiffies, of the execution.")
        parser.add_argument('io', type=str, required=True, help="Block I/O usage, in number of 512-byte sectors read from and written to, by the execution.")
        # Accounting for memory is quite hard -- probably easier to cap all containers at a fixed amount or perhaps have a graduated
        # list of cap sized (e.g. small, medium and large).
        # parser.add_argument('mem', type=str, required=True, help="Memory usage, , of the execution.")
        args = parser.parse_args()
        for k,v in args.items():
            try:
                int(v)
            except ValueError:
                raise APIException(message="Argument " + k + " must be an integer.")
        return args


class ActorExecutionResource(Resource):
    def get(self, actor_id, execution_id):
        id = Actor.get_dbid(g.tenant, actor_id)
        try:
            actor = Actor.from_db(actors_store[id])
        except KeyError:
            raise APIException(
                "actor not found: {}'".format(actor_id), 404)
        actor.display()
        try:
            excs = actor.executions
        except KeyError:
            raise APIException("No executions found for actor {}.".format(actor_id))
        # ex_id = Execution.get_dbid(g.tenant, execution_id)
        try:
            exc = excs[execution_id]
        except KeyError:
            raise APIException("Execution not found {}.".format(execution_id))
        return ok(result=exc, msg="Actor execution retrieved successfully.")


class ActorExecutionLogsResource(Resource):
    def get(self, actor_id, execution_id):
        id = Actor.get_dbid(g.tenant, actor_id)
        try:
            actor = Actor.from_db(actors_store[id])
        except KeyError:
            raise APIException(
                "actor not found: {}'".format(actor_id), 404)
        try:
            excs = actor.executions
        except KeyError:
            raise APIException("No executions found for actor {}.".format(actor_id))
        ex_id = Execution.get_dbid(g.tenant, execution_id)
        try:
            logs = logs_store[ex_id]
        except KeyError:
            logs = ""
        return ok(result=logs, msg="Logs retrieved successfully.")
