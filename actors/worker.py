import os
import sys
import threading

import channelpy

from channels import ActorMsgChannel, WorkerChannel
from codes import ERROR, READY
from docker_utils import DockerError, DockerStartContainerError, execute_actor, pull_image
from models import Actor, Execution

class WorkerException(Exception):
    def __init__(self, message):
        Exception.__init__(self, message)
        self.message = message

# keep_running will be updated by the thread listening on the worker channel when a graceful shutdown is
# required.
keep_running = True

def process_worker_ch(worker_ch, actor_ch):
    """ Target for a thread to listen on the worker channel for a message to stop processing.
    :param worker_ch:
    :return:
    """
    global keep_running
    print("Worker subscribing to worker channel...")
    msg = worker_ch.get()
    if msg == 'stop':
        print("Received stop message, stopping worker...")
        keep_running = False
        actor_ch.close()

def subscribe(actor_id, worker_ch):
    """
    Main loop for the Actor executor worker. Subscribes to the actor's inbox and executes actor
    containers when message arrive. Also subscribes to the worker channel for future communications.
    :return:
    """
    actor_ch = ActorMsgChannel(actor_id)
    t = threading.Thread(target=process_worker_ch, args=(worker_ch, actor_ch))
    t.start()
    print("Worker subscribing to actor channel...")
    while keep_running:
        try:
            msg = actor_ch.get(timeout=2)
        except channelpy.ChannelTimeoutException:
            continue
        print("Received message {}. Starting actor container...".format(str(msg)))
        try:
            stats = execute_actor(image, msg['msg'])
        except DockerStartContainerError as e:
            print("Got DockerStartContainerError: {}".format(str(e)))
            Actor.set_status(actor_id, ERROR)
            continue
        # add the execution to the actor store
        print("Actor container finished successfully. Got stats object:{}".format(str(stats)))
        Execution.add_execution(actor_id, stats)

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
