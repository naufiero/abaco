import os
import threading

from channels import ActorMsgChannel, WorkerChannel
from codes import ERROR
from docker_utils import DockerError, DockerStartContainerError, execute_actor, pull_image
from models import Actor, Execution

class WorkerException(Exception):
    def __init__(self, message):
        Exception.__init__(self, message)
        self.message = message

# keep_running will be updated by the thread listening on the worker channel when a graceful shutdown is
# required.
keep_running = True
lock = threading.Lock()

def process_worker_ch(worker_ch):
    """ Target for a thread to listen on the worker channel for a message to stop processing.
    :param worker_ch:
    :return:
    """
    global keep_running
    msg = worker_ch.get()
    if msg == 'stop':
        # gracefully stop entire process...
        lock.acquire()
        keep_running = False
        lock.release()

def subscribe(actor_id, worker_ch):
    """
    Main loop for the Actor executor worker. Subscribes to the actor's inbox and executes actor
    containers when message arrive. Also subscribes to the worker channel for future communications.
    :return:
    """
    actor_ch = ActorMsgChannel(actor_id)
    t = threading.Thread(target=process_worker_ch, args=(worker_ch,))
    t.start()
    while keep_running:
        msg = actor_ch.get()
        try:
            stats = execute_actor(image, msg['msg'])
        except DockerStartContainerError as e:
            Actor.set_status(actor_id, ERROR)
            continue
        # add the execution to the actor store
        Execution.add_execution(actor_id, stats)

def main(worker_ch_name, image):
    worker_ch = WorkerChannel(name=worker_ch_name)
    # first, attempt to pull image from docker hub:
    try:
        pull_image(image)
    except DockerError as e:
        # return a message to the spawner that there was an error pulling image and abort
        worker_ch.put({'status': 'error', 'msg': str(e)})
        raise e
    # inform spawner that image pulled successfully
    worker_ch.put({'status': 'ok'})
    # wait to receive message from spawner that it is time to subscribe to the actor channel
    result = worker_ch.get()  # <- message should contain the actor's id
    if result['status'] == 'error':
        raise WorkerException(str(result))
    actor_id = result.get('actor_id')
    subscribe(actor_id, worker_ch)


if __name__ == '__main__':
    # read channel and image from the environment
    worker_ch_name = os.environ.get('ch_name')
    image = os.environ.get('image')
    main(worker_ch_name, image)
