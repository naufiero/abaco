import json

from flask import g, request
from flask_restful import Resource, Api, inputs

from channels import ActorMsgChannel, CommandChannel
from codes import SUBMITTED, PERMISSION_LEVELS
from config import Config
from errors import DAOError, ResourceError, PermissionsException, WorkerException
from models import dict_to_camel, Actor, Execution, ExecutionsSummary, Worker, get_permissions, \
    add_permission
from request_utils import RequestParser, ok
from stores import actors_store, executions_store, logs_store, permissions_store
from worker import shutdown_workers, shutdown_worker


class ActorsResource(Resource):

    def get(self):
        actors = []
        for k, v in actors_store.items():
            if v['tenant'] == g.tenant:
                actors.append(Actor.from_db(v).display())
        return ok(result=actors, msg="Actors retrieved successfully.")

    def validate_post(self):
        parser = Actor.request_parser()
        return parser.parse_args()

    def post(self):
        args = self.validate_post()
        args['tenant'] = g.tenant
        args['api_server'] = g.api_server
        args['owner'] = g.user
        actor = Actor(**args)
        actors_store[actor.db_id] = actor.to_db()
        actor.ensure_one_worker()
        # worker_id = Worker.request_worker(actor_id=actor.db_id)
        # ch = CommandChannel()
        # ch.put_cmd(actor_id=actor.db_id,
        #            worker_ids=[worker_id],
        #            image=actor.image,
        #            tenant=args['tenant'],
        #            stop_existing=False)
        add_permission(g.user, actor.db_id, 'UPDATE')
        return ok(result=actor.display(), msg="Actor created successfully.", request=request)


class ActorResource(Resource):
    def get(self, actor_id):
        dbid = Actor.get_dbid(g.tenant, actor_id)
        try:
            actor = Actor.from_db(actors_store[dbid])
        except KeyError:
            raise ResourceError(
                "actor not found: {}. db_id:{}'".format(actor_id, dbid), 404)
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
        dbid = Actor.get_dbid(g.tenant, actor_id)
        try:
            actor = Actor.from_db(actors_store[dbid])
        except KeyError:
            raise ResourceError(
                "actor not found: {}'".format(actor_id), 404)
        previous_image = actor.image
        args = self.validate_put(actor)
        args['tenant'] = g.tenant
        update_image = False
        if args['image'] == previous_image:
            args['status'] = actor.status
        else:
            update_image = True
            args['status'] = SUBMITTED
        args['api_server'] = g.api_server
        args['owner'] = g.user
        actor = Actor(**args)
        actors_store[actor.db_id] = actor.to_db()
        worker_ids = Worker.request_worker(actor.db_id)
        if update_image:
            ch = CommandChannel()
            ch.put_cmd(actor_id=actor.db_id, worker_ids=worker_ids, image=actor.image, tenant=args['tenant'])
        # return ok(result={'update_image': str(update_image)},
        #           msg="Actor updated successfully.")
        return ok(result=actor.display(),
                  msg="Actor updated successfully.")

    def validate_put(self, actor):
        # inherit derived attributes from the original actor, including id and db_id:
        parser = Actor.request_parser()
        # remove since name is only required for POST, not PUT
        parser.remove_argument('name')
        # this update overrides all required and optional attributes
        actor.update(parser.parse_args())
        return actor

    def delete_actor_message(self, actor_id):
        """Put a command message on the actor_messages queue that actor was deleted."""
        # TODO
        pass


class ActorStateResource(Resource):
    def get(self, actor_id):
        dbid = Actor.get_dbid(g.tenant, actor_id)
        try:
            actor = Actor.from_db(actors_store[dbid])
        except KeyError:
            raise ResourceError(
                "actor not found: {}'".format(actor_id), 404)
        return ok(result={'state': actor.get('state') }, msg="Actor state retrieved successfully.")

    def post(self, actor_id):
        dbid = Actor.get_dbid(g.tenant, actor_id)
        try:
            actor = Actor.from_db(actors_store[dbid])
        except KeyError:
            raise ResourceError(
                "actor not found: {}'".format(actor_id), 404)
        if actor.stateless:
            raise ResourceError("actor is stateless.", 404)
        args = self.validate_post()
        state = args['state']
        actors_store.update(dbid, 'state', state)
        actor = Actor.from_db(actors_store[dbid])
        return ok(result=actor.display(), msg="State updated successfully.")

    def validate_post(self):
        parser = RequestParser()
        parser.add_argument('state', type=str, required=True, help="Set the state for this actor.")
        args = parser.parse_args()
        return args


class ActorExecutionsResource(Resource):
    def get(self, actor_id):
        dbid = Actor.get_dbid(g.tenant, actor_id)
        try:
            summary = ExecutionsSummary(db_id=dbid)
        except DAOError as e:
            raise ResourceError("actor not found: {}. DAOError: {}'".format(actor_id, e), 404)
        return ok(result=summary.display(), msg="Actor executions retrieved successfully.")

    def post(self, actor_id):
        id = Actor.get_dbid(g.tenant, actor_id)
        try:
            actor = Actor.from_db(actors_store[id])
        except KeyError:
            raise ResourceError(
                "actor not found: {}'".format(actor_id), 404)
        args = self.validate_post()
        Execution.add_execution(id, args)
        return ok(result=actor.display(), msg="Actor execution added successfully.")

    def validate_post(self):
        parser = RequestParser()
        parser.add_argument('runtime', type=str, required=True, help="Runtime, in milliseconds, of the execution.")
        parser.add_argument('cpu', type=str, required=True, help="CPU usage, in user jiffies, of the execution.")
        parser.add_argument('io', type=str, required=True, help="Block I/O usage, in number of 512-byte sectors read from and written to, by the execution.")
        # Accounting for memory is quite hard -- probably easier to cap all containers at a fixed amount or perhaps have
        # a graduated list of cap sized (e.g. small, medium and large).
        # parser.add_argument('mem', type=str, required=True, help="Memory usage, , of the execution.")
        args = parser.parse_args()
        for k,v in args.items():
            try:
                int(v)
            except ValueError:
                raise ResourceError(message="Argument " + k + " must be an integer.")
        return args


class ActorExecutionResource(Resource):
    def get(self, actor_id, execution_id):
        dbid = Actor.get_dbid(g.tenant, actor_id)
        try:
            actors_store[dbid]
        except KeyError:
            raise ResourceError(
                "actor not found: {}'".format(actor_id), 404)
        try:
            excs = executions_store[dbid]
        except KeyError:
            raise ResourceError("No executions found for actor {}.".format(actor_id))
        try:
            exc = Execution.from_db(excs[execution_id])
        except KeyError:
            raise ResourceError("Execution not found {}.".format(execution_id))
        return ok(result=exc.display(), msg="Actor execution retrieved successfully.")


class ActorExecutionLogsResource(Resource):
    def get(self, actor_id, execution_id):
        def get_hypermedia(actor, exc):
            return {'_links': {'self': '{}/actors/v2/{}/executions/{}/logs'.format(actor.api_server, actor.id, exc.id),
                               'owner': '{}/profiles/v2/{}'.format(actor.api_server, actor.owner),
                               'execution': '{}/actors/v2/{}/executions/{}'.format(actor.api_server, actor.id, exc.id)},
                    }
        dbid = Actor.get_dbid(g.tenant, actor_id)
        try:
            actor = Actor.from_db(actors_store[dbid])
        except KeyError:
            raise ResourceError(
                "actor not found: {}'".format(actor_id), 404)
        try:
            excs = executions_store[dbid]
        except KeyError:
            raise ResourceError("No executions found for actor {}.".format(actor_id))
        try:
            exc = Execution.from_db(excs[execution_id])
        except KeyError:
            raise ResourceError("Execution not found {}.".format(execution_id))
        try:
            logs = logs_store[execution_id]
        except KeyError:
            logs = ""
        result={'logs': logs}
        result.update(get_hypermedia(actor, exc))
        return ok(result, msg="Logs retrieved successfully.")


class MessagesResource(Resource):

    def get(self, actor_id):
        def get_hypermedia(actor):
            return {'_links': {'self': '{}/actors/v2/{}/messages'.format(actor.api_server, actor.id),
                               'owner': '{}/profiles/v2/{}'.format(actor.api_server, actor.owner),
                               },
                       }
        # check that actor exists
        id = Actor.get_dbid(g.tenant, actor_id)
        try:
            actor = Actor.from_db(actors_store[id])
        except KeyError:
            raise ResourceError(
                "actor not found: {}'".format(actor_id), 404)
        result={'messages': len(ActorMsgChannel(actor_id=id)._queue._queue)}
        result.update(get_hypermedia(actor))
        return ok(result)

    def validate_post(self):
        parser = RequestParser()
        parser.add_argument('message', type=str, required=False, help="The message to send to the actor.")
        args = parser.parse_args()
        # if a special 'message' object isn't passed, use entire POST payload as message
        if not args.get('message'):
            json_data = request.get_json()
            if json_data:
                args['message'] = json_data
                args['_abaco_Content-Type'] = 'application/json'
            else:
                # try to get data for mime types not recognized by flask. flask creates a python string for these
                try:
                    args['message'] = json.loads(request.data)
                except TypeError:
                    raise DAOError('message POST body could not be serialized. Pass JSON data or use the message attribute.')
                args['_abaco_Content-Type'] = 'str'
        else:
            # the special message object is a string
            args['_abaco_Content-Type'] = 'str'
        return args

    def post(self, actor_id):
        def get_hypermedia(actor, exc):
            return {'_links': {'self': '{}/actors/v2/{}/executions/{}'.format(actor.api_server, actor.id, exc),
                               'owner': '{}/profiles/v2/{}'.format(actor.api_server, actor.owner),
                               'messages': '{}/actors/v2/{}/messages'.format(actor.api_server, actor.id)},}

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
        if hasattr(g, 'api_server'):
            d['_abaco_api_server'] = g.api_server
        # if hasattr(g, 'jwt'):
        #     d['_abaco_jwt'] = g.jwt
        # if hasattr(g, 'jwt_server'):
        #     d['_abaco_jwt_server'] = g.jwt_server
        if hasattr(g, 'jwt_header_name'):
            d['_abaco_jwt_header_name'] = g.jwt_header_name
        dbid = Actor.get_dbid(g.tenant, actor_id)
        # create an execution
        exc = Execution.add_execution(dbid, {'cpu': 0,
                                             'io': 0,
                                             'runtime': 0,
                                             'status': SUBMITTED,
                                             'executor': g.user})
        d['_abaco_execution_id'] = exc
        d['_abaco_Content-Type'] = args.get('_abaco_Content-Type', '')
        ch = ActorMsgChannel(actor_id=dbid)
        ch.put_msg(message=args['message'], d=d)
        # make sure at least one worker is available
        actor = Actor.from_db(actors_store[dbid])
        actor.ensure_one_worker()
        result={'execution_id': exc, 'msg': args['message']}
        result.update(get_hypermedia(actor, exc))
        case = Config.get('web', 'case')
        if not case == 'camel':
            return ok(result)
        else:
            return ok(dict_to_camel(result))



class WorkersResource(Resource):
    def get(self, actor_id):
        dbid = Actor.get_dbid(g.tenant, actor_id)
        try:
            Actor.from_db(actors_store[dbid])
        except KeyError:
            raise ResourceError("actor not found: {}'".format(actor_id), 400)
        try:
            workers = Worker.get_workers(dbid)
        except WorkerException as e:
            raise ResourceError(e.msg, 404)
        result = []
        for id, worker in workers.items():
            worker.update({'id': id})
            result.append(worker)
        return ok(result=result, msg="Workers retrieved successfully.")

    def validate_post(self):
        parser = RequestParser()
        parser.add_argument('num', type=int, help="Number of workers to start (default is 1).")
        args = parser.parse_args()
        return args

    def post(self, actor_id):
        """Ensure a certain number of workers are running for an actor"""
        id = Actor.get_dbid(g.tenant, actor_id)
        try:
            actor = Actor.from_db(actors_store[id])
        except KeyError:
            raise ResourceError(
                "actor not found: {}'".format(actor_id), 404)
        args = self.validate_post()
        num = args.get('num')
        if not num or num == 0:
            num = 1
        dbid = Actor.get_dbid(g.tenant, actor_id)
        workers = Worker.get_workers(dbid)
        if len(workers.items()) < num:
            worker_ids = []
            num_to_add = int(num) - len(workers.items())
            for idx in range(num_to_add):
                worker_ids.append(Worker.request_worker(actor_id))
            ch = CommandChannel()
            ch.put_cmd(actor_id=actor.db_id,
                       worker_ids=worker_ids,
                       image=actor.image,
                       tenant=g.tenant,
                       num=num_to_add,
                       stop_existing=False)
            return ok(result=None, msg="Scheduled {} new worker(s) to start. There were only".format(num_to_add))
        else:
            return ok(result=None, msg="Actor {} already had {} worker(s).".format(actor_id, num))


class WorkerResource(Resource):
    def get(self, actor_id, worker_id):
        id = Actor.get_dbid(g.tenant, actor_id)
        try:
            Actor.from_db(actors_store[id])
        except KeyError:
            raise WorkerException("actor not found: {}'".format(actor_id))
        try:
            worker = Worker.get_worker(id, worker_id)
        except WorkerException as e:
            raise ResourceError(e.msg, 404)
        return ok(result=worker, msg="Worker retrieved successfully.")

    def delete(self, actor_id, worker_id):
        id = Actor.get_dbid(g.tenant, actor_id)
        try:
            worker = Worker.get_worker(id, worker_id)
        except WorkerException as e:
            raise ResourceError(e.msg, 404)
        shutdown_worker(worker['ch_name'])
        return ok(result=None, msg="Worker scheduled to be stopped.")


class PermissionsResource(Resource):
    def get(self, actor_id):
        id = Actor.get_dbid(g.tenant, actor_id)
        try:
            Actor.from_db(actors_store[id])
        except KeyError:
            raise ResourceError(
                "actor not found: {}'".format(actor_id), 404)
        try:
            permissions = get_permissions(id)
        except PermissionsException as e:
            raise ResourceError(e.msg, 404)
        return ok(result=permissions, msg="Permissions retrieved successfully.")

    def validate_post(self):
        parser = RequestParser()
        parser.add_argument('user', type=str, required=True, help="User owning the permission.")
        parser.add_argument('level', type=str, required=True,
                            help="Level of the permission: {}".format(PERMISSION_LEVELS))
        args = parser.parse_args()
        if not args['level'] in PERMISSION_LEVELS:
            raise ResourceError("Invalid permission level: {}. \
            The valid values are {}".format(args['level'], PERMISSION_LEVELS))
        return args

    def post(self, actor_id):
        """Add new permissions for an actor"""
        id = Actor.get_dbid(g.tenant, actor_id)
        try:
            Actor.from_db(actors_store[id])
        except KeyError:
            raise ResourceError(
                "actor not found: {}'".format(actor_id), 404)
        args = self.validate_post()
        add_permission(args['user'], id, args['level'])
        permissions = get_permissions(id)
        return ok(result=permissions, msg="Permission added successfully.")
