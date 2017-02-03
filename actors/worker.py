import os
import sys
import threading

import channelpy
from agave import Agave

from channels import ActorMsgChannel, ClientsChannel, CommandChannel,WorkerChannel
from codes import ERROR, READY, BUSY, COMPLETE
from docker_utils import DockerError, DockerStartContainerError, execute_actor, pull_image
from errors import WorkerException
from models import Actor, Execution, Worker
from stores import actors_store, workers_store


# keep_running will be updated by the thread listening on the worker channel when a graceful shutdown is
# required.
keep_running = True

def shutdown_worker(ch_name):
    """Gracefully shutdown a single worker."""
    ch = WorkerChannel(name=ch_name)
    ch.put("stop")

def shutdown_workers(actor_id):
    """Graceful shutdown of all workers for an actor. Pass db_id as the `actor_id` argument."""
    workers = Worker.get_workers(actor_id)
    for _, worker in workers.items():
        shutdown_worker(worker['ch_name'])

def process_worker_ch(tenant, worker_ch, actor_id, worker_id, actor_ch, ag_client):
    """ Target for a thread to listen on the worker channel for a message to stop processing.
    :param worker_ch:
    :return:
    """
    global keep_running
    print("Worker subscribing to worker channel...")
    while True:
        try:
            msg = worker_ch.get(timeout=2)
        except channelpy.ChannelTimeoutException:
            continue
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
            # first, delete an associated client
            # its possible this worker was not passed a client,
            # but if so, we need to delete it before shutting down.
            if ag_client:
                print("Requesting client {} be deleted.".format(ag_client.api_key))
                secret = os.environ.get('_abaco_secret')
                clients_ch = ClientsChannel()
                msg = clients_ch.request_delete_client(tenant=tenant,
                                                       actor_id=actor_id,
                                                       worker_id=worker_id,
                                                       client_id=ag_client.api_key,
                                                       secret=secret)

                if msg['status'] == 'ok':
                    print("Delete request completed successfully.")
                else:
                    print("Error deleting client. Message: {}".format(msg['message']))
            else:
                print("Did not receive client. Not issuing delete. Exiting.")
            try:
                Worker.delete_worker(actor_id, worker_id)
            except WorkerException:
                pass
            keep_running = False
            actor_ch.close()
            sys.exit()

def subscribe(tenant,
              actor_id,
              worker_id,
              api_server,
              client_id,
              client_secret,
              access_token,
              refresh_token,
              worker_ch):
    """
    Main loop for the Actor executor worker. Subscribes to the actor's inbox and executes actor
    containers when message arrive. Also subscribes to the worker channel for future communications.
    :return:
    """
    actor_ch = ActorMsgChannel(actor_id)
    ag = None
    if api_server and client_id and client_secret and access_token and refresh_token:
        ag = Agave(api_server=api_server,
                   token=access_token,
                   refresh_token=refresh_token,
                   api_key=client_id,
                   api_secret=client_secret)
    else:
        print("Not creating agave client.")
    t = threading.Thread(target=process_worker_ch, args=(tenant, worker_ch, actor_id, worker_id, actor_ch, ag))
    t.start()
    print("Worker subscribing to actor channel...")
    global keep_running
    while keep_running:
        Worker.update_worker_status(actor_id, worker_id, READY)
        try:
            msg = actor_ch.get(timeout=2)
        except channelpy.ChannelTimeoutException:
            continue
        except channelpy.ChannelClosedException:
            print("Channel closed, worker exiting...")
            keep_running = False
            sys.exit()
        print("Received message {}. Starting actor container...".format(str(msg)))
        # the msg object is a dictionary with an entry called message and an arbitrary
        # set of k:v pairs coming in from the query parameters.
        message = msg.pop('message', '')
        actor = Actor.from_db(actors_store[actor_id])
        execution_id = msg['_abaco_execution_id']
        privileged = False
        if actor['privileged'] == 'TRUE':
            privileged = True
        environment = actor['default_environment']
        print("Actor default environment: {}".format(environment))
        print("Actor privileged: {}".format(privileged))
        # overlay the default_environment registered for the actor with the msg
        # dictionary
        environment.update(msg)
        environment['_abaco_access_token'] = ''
        # if we have an agave client, get a fresh set of tokens:
        if ag:
            try:
                ag.token.refresh()
                token = ag.token.token_info['access_token']
                environment['_abaco_access_token'] = token
                print("Refreshed the tokens. Passed {} to the environment.".format(token))
            except Exception as e:
                print("Got an exception trying to get an access token: {}".format(e))
        else:
            print("Agave client `ag` is None -- not passing access token.")
        print("Passing update environment: {}".format(environment))
        try:
            stats, logs = execute_actor(actor_id, worker_id, worker_ch, image, message,
                                        environment, privileged)
        except DockerStartContainerError as e:
            print("Got DockerStartContainerError: {}".format(str(e)))
            Actor.set_status(actor_id, ERROR)
            continue
        # add the execution to the actor store
        print("Actor container finished successfully. Got stats object:{}".format(str(stats)))
        Execution.finalize_execution(actor_id, execution_id, COMPLETE, stats)
        print("Added execution: {}".format(execution_id))
        Execution.set_logs(execution_id, logs)
        Worker.update_worker_execution_time(actor_id, worker_id)

def main(worker_ch_name, worker_id, image):
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
    tenant = result.get('tenant')
    print("Worker received ok from spawner. Message: {}, actor_id:{}".format(result, actor_id))
    api_server = None
    client_id = None
    client_secret = None
    access_token = None
    refresh_token = None
    if result.get('client') == 'yes':
        api_server = result.get('api_server')
        client_id = result.get('client_id')
        client_secret = result.get('client_secret')
        access_token = result.get('access_token')
        refresh_token = result.get('refresh_token')
    else:
        print("Did not get client:yes, got client:{}".format(result.get('client')))
    Actor.set_status(actor_id, READY)
    subscribe(tenant,
              actor_id,
              worker_id,
              api_server,
              client_id,
              client_secret,
              access_token,
              refresh_token,
              worker_ch)


if __name__ == '__main__':
    # read channel and image from the environment
    print("Worker starting...")
    worker_ch_name = os.environ.get('ch_name')
    worker_id = os.environ.get('worker_id')
    image = os.environ.get('image')
    print("Channel name: {}  Image: {} ".format(worker_ch_name, image))
    main(worker_ch_name, worker_id, image)
