import json
import os
import threading

from flask_restful import Resource
import channelpy

from channels import ActorMsgChannel, CommandChannel,WorkerChannel
from codes import ERROR, READY
from docker_utils import DockerError, DockerStartContainerError, execute_actor, pull_image
from models import Actor, Execution
from request_utils import APIException, ok, error, RequestParser
from stores import actors_store, workers_store


class WorkerException(Exception):
    def __init__(self, message):
        Exception.__init__(self, message)
        self.message = message

# keep_running will be updated by the thread listening on the worker channel when a graceful shutdown is
# required.
keep_running = True

class WorkersResource(Resource):
    def get(self, actor_id):
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

def get_workers(actor_id):
    """Retrieve all workers for an actor."""
    try:
        Actor.from_db(actors_store[actor_id])
    except KeyError:
        raise WorkerException("actor not found: {}'".format(actor_id))
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
    workers = get_workers(actor_id)
    i = -1
    for idx, worker in enumerate(workers):
        if worker['ch_name'] == ch_name:
            i = idx
            break
    if i > -1:
        workers.pop(i)
        workers_store[actor_id] = json.dumps(workers)


def process_worker_ch(worker_ch, actor_id, actor_ch):
    """ Target for a thread to listen on the worker channel for a message to stop processing.
    :param worker_ch:
    :return:
    """
    global keep_running
    print("Worker subscribing to worker channel...")
    msg = worker_ch.get()
    if msg == 'stop':
        print("Received stop message, stopping worker...")
        try:
            delete_worker(actor_id, worker_ch._name)
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
        try:
            msg = actor_ch.get(timeout=2)
        except channelpy.ChannelTimeoutException:
            continue
        print("Received message {}. Starting actor container...".format(str(msg)))
        message = msg.pop('msg', '')
        try:
            stats, logs = execute_actor(image, message, msg)
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
    result = worker_ch.put_sync({'status': 'ok'})
    # wait to receive message from spawner that it is time to subscribe to the actor channel
    print("Worker waiting on message from spawner...")
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
