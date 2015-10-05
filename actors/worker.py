import json
import os
import threading
import time

from flask_restful import Resource
import channelpy

from channels import ActorMsgChannel, CommandChannel,WorkerChannel
from codes import ERROR, READY, BUSY
from docker_utils import DockerError, DockerStartContainerError, execute_actor, pull_image
from models import Actor, Execution, get_workers, get_worker, delete_worker, update_worker_status, WorkerException
from request_utils import APIException, ok, error, RequestParser
from stores import actors_store, workers_store


# keep_running will be updated by the thread listening on the worker channel when a graceful shutdown is
# required.
keep_running = True

class WorkersResource(Resource):
    def get(self, actor_id):
        try:
            Actor.from_db(actors_store[actor_id])
        except KeyError:
            raise APIException("actor not found: {}'".format(actor_id), 400)
        try:
            workers = get_workers(actor_id)
        except WorkerException as e:
            raise APIException(e.message, 404)
        return ok(result=workers, msg="Workers retrieved successfully.")

    def validate_post(self):
        parser = RequestParser()
        parser.add_argument('num', type=int, help="Number of workers to start (default is 1).")
        args = parser.parse_args()
        return args

    def post(self, actor_id):
        """Start new workers for an actor"""
        try:
            actor = Actor.from_db(actors_store[actor_id])
        except KeyError:
            raise APIException(
                "actor not found: {}'".format(actor_id), 404)
        args = self.validate_post()
        num = args.get('num')
        if not num or num == 0:
            num = 1
        ch = CommandChannel()
        ch.put_cmd(actor_id=actor.id, image=actor.image, num=num, stop_existing=False)
        return ok(result=None, msg="Scheduled {} new worker(s) to start.".format(str(num)))

class WorkerResource(Resource):
    def get(self, actor_id, ch_name):
        try:
            Actor.from_db(actors_store[actor_id])
        except KeyError:
            raise WorkerException("actor not found: {}'".format(actor_id))
        try:
            worker = get_worker(actor_id, ch_name)
        except WorkerException as e:
            raise APIException(e.message, 404)
        return ok(result=worker, msg="Worker retrieved successfully.")

    def delete(self, actor_id, ch_name):
        try:
            worker = get_worker(actor_id, ch_name)
        except WorkerException as e:
            raise APIException(e.message, 404)
        ch = WorkerChannel(name=ch_name)
        ch.put("stop")
        return ok(result=worker, msg="Worker scheduled to be stopped.")

def shutdown_workers(actor_id):
    """Graceful shutdown of all workers for an actor"""
    workers = get_workers(actor_id)
    for worker in workers:
        ch = WorkerChannel(name=worker['ch_name'])
        ch.put('stop')



def process_worker_ch(worker_ch, actor_id, actor_ch):
    """ Target for a thread to listen on the worker channel for a message to stop processing.
    :param worker_ch:
    :return:
    """
    global keep_running
    print("Worker subscribing to worker channel...")
    while True:
        msg = worker_ch.get()
        print("Received message in worker channel: {}".format(msg))
        print("Type(msg)={}".format(type(msg)))
        if type(msg) == dict:
            value = msg.get('value', '')
            if value == 'status':
                # this is a health check, return 'ok' to the reply_to channel.
                ch = msg['reply_to']
                ch.put('ok')
        elif msg == 'stop':
            print("Received stop message, stopping worker...")
            try:
                delete_worker(actor_id, worker_ch.name)
            except WorkerException:
                pass
            keep_running = False
            actor_ch.close()

def subscribe(actor_id, worker_ch):
    """
    Main loop for the Actor executor worker. Subscribes to the actor's inbox and executes actor
    containers when message arrive. Also subscribes to the worker channel for future communications.
    :return:
    """
    actor_ch = ActorMsgChannel(actor_id)
    t = threading.Thread(target=process_worker_ch, args=(worker_ch, actor_id, actor_ch))
    t.start()
    print("Worker subscribing to actor channel...")
    while keep_running:
        update_worker_status(actor_id, worker_ch.name, READY)
        try:
            msg = actor_ch.get(timeout=2)
        except channelpy.ChannelTimeoutException:
            continue
        print("Received message {}. Starting actor container...".format(str(msg)))
        # the msg object is a dictionary with an entry called message and an arbitrary
        # set of k:v pairs coming in from the query parameters.
        message = msg.pop('message', '')
        actor = Actor.from_db(actors_store[actor_id])
        privileged = False
        if actor['privileged'] == 'TRUE':
            privileged = True
        environment = actor['default_environment']
        print("Actor default environment: {}".format(environment))
        print("Actor privileged: {}".format(privileged))
        # overlay the default_environment registered for the actor with the msg
        # dictionary
        environment.update(msg)
        print("Passing update environment: {}".format(environment))
        try:
            stats, logs = execute_actor(actor_id, worker_ch, image, message,
                                        environment, privileged)
        except DockerStartContainerError as e:
            print("Got DockerStartContainerError: {}".format(str(e)))
            Actor.set_status(actor_id, ERROR)
            continue
        # add the execution to the actor store
        print("Actor container finished successfully. Got stats object:{}".format(str(stats)))
        exc_id = Execution.add_execution(actor_id, stats)
        Execution.set_logs(exc_id, logs)

def main(worker_ch_name, image):
    worker_ch = WorkerChannel(name=worker_ch_name)
    # first, attempt to pull image from docker hub:
    try:
        print("Worker pulling image {}...".format(image))
        pull_image(image)
    except DockerError as e:
        # return a message to the spawner that there was an error pulling image and abort
        worker_ch.put({'status': 'error', 'msg': str(e)})
        raise e
    # inform spawner that image pulled successfully
    print("Image pulled successfully")

    # wait to receive message from spawner that it is time to subscribe to the actor channel
    print("Worker waiting on message from spawner...")
    result = worker_ch.put_sync({'status': 'ok'})

    if result['status'] == 'error':
        print("Worker received error message from spawner: {}. Quiting...".format(str(result)))
        raise WorkerException(str(result))
    actor_id = result.get('actor_id')
    print("Worker received ok from spawner. Message: {}, actor_id:{}".format(result, actor_id))
    Actor.set_status(actor_id, READY)
    subscribe(actor_id, worker_ch)


if __name__ == '__main__':
    # read channel and image from the environment
    print("Worker starting...")
    worker_ch_name = os.environ.get('ch_name')
    image = os.environ.get('image')
    print("Channel name: {}  Image: {} ".format(worker_ch_name, image))
    main(worker_ch_name, image)
