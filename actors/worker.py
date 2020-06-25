import copy
import os
import shutil
import sys
import threading
import _thread
import time

import channelpy
from aga import Agave

from auth import get_tenant_verify
from channels import ActorMsgChannel, ClientsChannel, CommandChannel, WorkerChannel, SpawnerWorkerChannel
from codes import SHUTDOWN_REQUESTED, SHUTTING_DOWN, ERROR, READY, BUSY, COMPLETE
from common.config import conf
from docker_utils import DockerError, DockerStartContainerError, DockerStopContainerError, execute_actor, pull_image
from errors import WorkerException
import globals
from models import Actor, Execution, Worker
from stores import actors_store, workers_store

from common.logs import get_logger
logger = get_logger(__name__)

# keep_running will be updated by the thread listening on the worker channel when a graceful shutdown is
# required.
keep_running = True

# maximum number of consecutive errors a worker can encounter before giving up and moving itself into an ERROR state.
MAX_WORKER_CONSECUTIVE_ERRORS = 5

def shutdown_worker(actor_id, worker_id, delete_actor_ch=True):
    """Gracefully shutdown a single worker."
    actor_id (str) - the dbid of the associated actor.
    """
    logger.debug("top of shutdown_worker for worker_id: {}".format(worker_id))
    # set the worker status to SHUTDOWN_REQUESTED:
    try:
        Worker.update_worker_status(actor_id, worker_id, SHUTDOWN_REQUESTED)
    except Exception as e:
        logger.error(f"worker got exception trying to update status to SHUTODWN_REQUESTED. actor_id: {actor_id};"
                     f"worker_id: {worker_id}; exception: {e}")
    ch = WorkerChannel(worker_id=worker_id)
    if not delete_actor_ch:
        ch.put("stop-no-delete")
    else:
        ch.put("stop")
    logger.info("A 'stop' message was sent to worker: {}".format(worker_id))
    ch.close()

def shutdown_workers(actor_id, delete_actor_ch=True):
    """
    Graceful shutdown of all workers for an actor. Arguments:
    * actor_id (str) - the db_id of the actor
    * delete_actor_ch (bool) - whether the worker shutdown process should also delete the actor_ch. This should be true
      whenever the actor is being removed. This will also force quit any currently running executions.
    """
    logger.debug("shutdown_workers() called for actor: {}".format(actor_id))
    try:
        workers = Worker.get_workers(actor_id)
    except Exception as e:
        logger.error("Got exception from get_workers: {}".format(e))
    if not workers:
        logger.info("shutdown_workers did not receive any workers from Worker.get_workers for actor: {}".format(actor_id))
    # @TODO - this code is not thread safe. we need to update the workers state in a transaction:
    for worker in workers:
        shutdown_worker(actor_id, worker['id'], delete_actor_ch)


def process_worker_ch(tenant, worker_ch, actor_id, worker_id, actor_ch, ag_client):
    """ Target for a thread to listen on the worker channel for a message to stop processing.
    :param worker_ch:
    :return:
    """
    global keep_running
    logger.info("Worker subscribing to worker channel...{}_{}".format(actor_id, worker_id))
    while keep_running:
        msg, msg_obj = worker_ch.get_one()
        # receiving the message is enough to ack it - resiliency is currently handled in the calling code.
        msg_obj.ack()
        logger.debug("Received message in worker channel; msg: {}; {}_{}".format(msg, actor_id, worker_id))
        logger.debug("Type(msg)={}".format(type(msg)))
        if type(msg) == dict:
            value = msg.get('value', '')
            if value == 'status':
                # this is a health check, return 'ok' to the reply_to channel.
                logger.debug("received health check. returning 'ok'.")
                ch = msg['reply_to']
                ch.put('ok')
                # @TODO -
                # delete the anonymous channel from this thread but sleep first to avoid the race condition.
                time.sleep(1.5)
                ch.delete()
                # NOT doing this for now -- deleting entire anon channel instead (see above)
                # clean up the event queue on this anonymous channel. this should be fixed in channelpy.
                # ch._queue._event_queue
        elif msg == 'force_quit':
            logger.info("Worker with worker_id: {} (actor_id: {}) received a force_quit message, "
                        "forcing the execution to halt...".format(worker_id, actor_id))
            globals.force_quit = True
            globals.keep_running = False

        elif msg == 'stop' or msg == 'stop-no-delete':
            logger.info("Worker with worker_id: {} (actor_id: {}) received stop message, "
                        "stopping worker...".format(worker_id, actor_id))
            globals.keep_running = False
            # set the worker status to SHUTTING_DOWN:
            try:
                Worker.update_worker_status(actor_id, worker_id, SHUTTING_DOWN)
            except Exception as e:
                logger.error(
                    f"worker got exception trying to update status to SHUTTING_DOWN. actor_id: {actor_id};"
                    f"worker_id: {worker_id}; exception: {e}")

            # when an actor's image is updated, old workers are deleted while new workers are
            # created. Deleting the actor msg channel in this case leads to race conditions
            delete_actor_ch = True
            if msg == 'stop-no-delete':
                logger.info("Got stop-no-delete; will not delete actor_ch. {}_{}".format(actor_id, worker_id))
                delete_actor_ch = False
            # if a `stop` was sent, the actor is being deleted, and so we want to immediately shutdown processing.
            else:
                globals.force_quit = True
            # first, delete an associated client
            # its possible this worker was not passed a client,
            # but if so, we need to delete it before shutting down.
            if ag_client:
                logger.info("worker {}_{} Requesting client {} be deleted.".format(actor_id, worker_id, ag_client.api_key))
                secret = os.environ.get('_abaco_secret')
                clients_ch = ClientsChannel()
                msg = clients_ch.request_delete_client(tenant=tenant,
                                                       actor_id=actor_id,
                                                       worker_id=worker_id,
                                                       client_id=ag_client.api_key,
                                                       secret=secret)

                if msg['status'] == 'ok':
                    logger.info("Client delete request completed successfully for "
                                "worker_id: {}, client_id: {}.".format(worker_id, ag_client.api_key))
                else:
                    logger.error("Error deleting client for "
                                 "worker_id: {}, client_id: {}. Message: {}".format(worker_id, msg['message'],
                                                                                    ag_client.api_key))
                clients_ch.close()
            else:
                logger.info("Did not receive client. Not issuing delete. Exiting. {}_{}".format(actor_id, worker_id))
            try:
                Worker.delete_worker(actor_id, worker_id)
            except WorkerException as e:
                logger.info("Got WorkerException from delete_worker(). "
                            "worker_id: {}"
                            "Exception: {}".format(worker_id, e))
            # delete associated channels:
            # it is possible the actor channel was already deleted, in which case we just keep processing
            if delete_actor_ch:
                try:
                    actor_ch.delete()
                    logger.info("ActorChannel deleted for actor: {} worker_id: {}".format(actor_id, worker_id))
                except Exception as e:
                    logger.info("Got exception deleting ActorChannel for actor: {} "
                                "worker_id: {}; exception: {}".format(actor_id, worker_id, e))
            try:
                worker_ch.delete()
                logger.info("WorkerChannel deleted for actor: {} worker_id: {}".format(actor_id, worker_id))
            except Exception as e:
                logger.info("Got exception deleting WorkerChannel for actor: {} "
                            "worker_id: {}; exception: {}".format(actor_id, worker_id, e))

            logger.info("Worker with worker_id: {} is now exiting.".format(worker_id))
            _thread.interrupt_main()
            logger.info("main thread interrupted, worker {}_{} issuing os._exit()...".format(actor_id, worker_id))
            os._exit(0)

def subscribe(tenant,
              actor_id,
              image,
              worker_id,
              api_server,
              client_id,
              client_secret,
              access_token,
              refresh_token,
              worker_ch):
    """
    Main loop for the Actor executor worker. Subscribes to the actor's inbox and executes actor
    containers when message arrive. Also launches a separate thread which ultimately subscribes to the worker channel
    for future communications.
    :return:
    """
    logger.debug("Top of subscribe(). worker_id: {}".format(worker_id))
    actor_ch = ActorMsgChannel(actor_id)
    # establish configs for this worker -------
    leave_containers = conf.worker_leave_containers
    logger.debug(f"leave_containers: {leave_containers}")

    mem_limit = str(conf.worker_mem_limit)
    logger.debug(f"mem_limit: {mem_limit}")

    max_cpus = conf.worker_max_cpus
    logger.debug(f"max_cpus: {max_cpus}")

    # instantiate an OAuth client python object if credentials were passed -----
    ag = None
    if api_server and client_id and client_secret and access_token and refresh_token:
        logger.info("Creating agave client.")
        verify = get_tenant_verify(tenant)
        ag = Agave(api_server=api_server,
                   token=access_token,
                   refresh_token=refresh_token,
                   api_key=client_id,
                   api_secret=client_secret,
                   verify=verify)
    else:
        logger.info("Not creating agave client.")

    # start a separate thread for handling messages sent to the worker channel ----
    logger.info("Starting the process worker channel thread.")
    t = threading.Thread(target=process_worker_ch, args=(tenant, worker_ch, actor_id, worker_id, actor_ch, ag))
    t.start()

    # subscribe to the actor message queue -----
    logger.info("Worker subscribing to actor channel. worker_id: {}".format(worker_id))
    # keep track of whether we need to update the worker's status back to READY; otherwise, we
    # will hit redis with an UPDATE every time the subscription loop times out (i.e., every 2s)
    update_worker_status = True

    # global tracks whether this worker should keep running.
    globals.keep_running = True

    # consecutive_errors tracks the number of consecutive times a worker has gotten an error trying to process a
    # message. Even though the message will be requeued, we do not want the worker to continue processing
    # indefinitely when a compute node is unhealthy.
    consecutive_errors = 0

    # main subscription loop -- processing messages from actor's mailbox
    while globals.keep_running:
        logger.debug("top of keep_running; worker id: {}".format(worker_id))
        if update_worker_status:
            Worker.update_worker_status(actor_id, worker_id, READY)
            logger.debug("updated worker status to READY in SUBSCRIBE; worker id: {}".format(worker_id))
            update_worker_status = False

        # note: the following get_one() call blocks until a message is returned. this means it could be a long time
        # (i.e., many seconds, or even minutes) between the check above to globals.keep_running (line 252) and the
        # get_one() function returning. In this time, the worker channel thread could have received a stop. We need to
        # check this.
        try:
            msg, msg_obj = actor_ch.get_one()
        except channelpy.ChannelClosedException:
            logger.info("Channel closed, worker exiting. worker id: {}".format(worker_id))
            globals.keep_running = False
            sys.exit()
        logger.info("worker {} processing new msg.".format(worker_id))

        # worker ch thread has received a stop and is already shutting us down (see note above); we need to nack this
        # message and exit
        if not globals.keep_running:
            logger.info("got msg from get_one() but globals.keep_running was False! "
                        "Requeing message and worker will exit. {}+{}".format(actor_id, worker_id))
            msg_obj.nack(requeue=True)
            logger.info("message requeued; worker exiting:{}_{}".format(actor_id, worker_id))
            time.sleep(5)
            raise Exception()
        try:
            Worker.update_worker_status(actor_id, worker_id, BUSY)
        except Exception as e:
            logger.error("unexpected exception from call to update_worker_status. Nacking message."
                         "actor_id: {}; worker_id: {}; status: {}; exception: {}".format(actor_id,
                                                                                         worker_id,
                                                                                         BUSY,
                                                                                         e))
            logger.info("worker exiting. {}_{}".format(actor_id, worker_id))
            msg_obj.nack(requeue=True)
            raise e
        update_worker_status = True
        logger.info("Received message {}. Starting actor container. worker id: {}".format(msg, worker_id))
        # the msg object is a dictionary with an entry called message and an arbitrary
        # set of k:v pairs coming in from the query parameters.
        message = msg.pop('message', '')
        try:
            actor = Actor.from_db(actors_store[actor_id])
            execution_id = msg['_abaco_execution_id']
            content_type = msg['_abaco_Content_Type']
            mounts = actor.mounts
            logger.debug("actor mounts: {}".format(mounts))
        except Exception as e:
            logger.error("unexpected exception retrieving actor, execution, content-type, mounts. Nacking message."
                         "actor_id: {}; worker_id: {}; status: {}; exception: {}".format(actor_id,
                                                                                         worker_id,
                                                                                         BUSY,
                                                                                         e))
            msg_obj.nack(requeue=True)
            logger.info("worker exiting. worker_id: {}".format(worker_id))
            raise e

        # for results, create a socket in the configured directory.

        socket_host_path_dir = conf.worker_socket_host_path_dir
        socket_host_path = '{}.sock'.format(os.path.join(socket_host_path_dir, worker_id, execution_id))
        logger.info("Create socket at path: {}".format(socket_host_path))
        # add the socket as a mount:
        mounts.append({'host_path': socket_host_path,
                       'container_path': '/_abaco_results.sock',
                       'format': 'ro'})
        # for binary data, create a fifo in the configured directory. The configured
        # fifo_host_path_dir is equal to the fifo path in the worker container:
        fifo_host_path = None
        if content_type == 'application/octet-stream':
            fifo_host_path_dir = conf.worker_fifo_host_path_dir
            fifo_host_path = os.path.join(fifo_host_path_dir, worker_id, execution_id)
            try:
                os.mkfifo(fifo_host_path)
                logger.info("Created fifo at path: {}".format(fifo_host_path))
            except Exception as e:
                logger.error("Could not create fifo_path. Nacking message. Exception: {}".format(e))
                msg_obj.nack(requeue=True)
                logger.info("worker exiting. worker_id: {}".format(worker_id))
                raise e
            # add the fifo as a mount:
            mounts.append({'host_path': fifo_host_path,
                           'container_path': '/_abaco_binary_data',
                           'format': 'ro'})

        # the execution object was created by the controller, but we need to add the worker id to it now that we
        # know which worker will be working on the execution.
        logger.debug(f"Adding worker_id to execution. worker_id: {worker_id}")
        try:
            Execution.add_worker_id(actor_id, execution_id, worker_id)
        except Exception as e:
            logger.error("Unexpected exception adding working_id to the Execution. Nacking message. Exception: {}".format(e))
            msg_obj.nack(requeue=True)
            logger.info("worker exiting. worker_id: {}".format(worker_id))
            raise e

        # privileged dictates whether the actor container runs in privileged mode and if docker daemon is mounted.
        privileged = False
        if type(actor['privileged']) == bool and actor['privileged']:
            privileged = True
        logger.debug("privileged: {}; worker_id: {}".format(privileged, worker_id))

        # overlay resource limits if set on actor:
        if actor.mem_limit:
            mem_limit = actor.mem_limit
        if actor.max_cpus:
            max_cpus = actor.max_cpus

        # retrieve the default environment registered with the actor.
        environment = actor['default_environment']
        logger.debug("Actor default environment: {}".format(environment))

        # construct the user field from the actor's uid and gid:
        user = get_container_user(actor)
        logger.debug("Final user valiue: {}".format(user))
        # overlay the default_environment registered for the actor with the msg
        # dictionary
        environment.update(msg)
        environment['_abaco_access_token'] = ''
        environment['_abaco_actor_dbid'] = actor_id
        environment['_abaco_actor_id'] = actor.id
        environment['_abaco_worker_id'] = worker_id
        environment['_abaco_container_repo'] = actor.image
        environment['_abaco_actor_state'] = actor.state
        environment['_abaco_actor_name'] = actor.name or 'None'
        logger.debug("Overlayed environment: {}; worker_id: {}".format(environment, worker_id))

        # if we have an agave client, get a fresh set of tokens:
        if ag:
            need_to_refresh = True
            refresh_attempts = 0
            while need_to_refresh and refresh_attempts < 10:
                refresh_attempts = refresh_attempts + 1
                logger.debug("About to try and refreh the token; "
                             "attempt number: {}; {}_{}".format(refresh_attempts, actor_id, worker_id))
                try:
                    ag.token.refresh()
                    token = ag.token.token_info['access_token']
                    environment['_abaco_access_token'] = token
                    logger.info("Refreshed the tokens. Passed {} to the environment.".format(token))
                    need_to_refresh = False
                except Exception as e:
                    logger.error("Got an exception trying to get an access token. Attempt number {} "
                                 "Exception: {}; actor_id: {}; worker_id: {}; execution_id: {}; client_id: {}; "
                                 "client_secret: {}".format(refresh_attempts, e, actor_id, worker_id, execution_id, client_id, client_secret))
                    # try to log the raw response; it is possible the exception object, e, will not have a response object
                    # on it, for instance if one of the other lines above caused the exception.
                    try:
                        logger.error("content from response: {}".format(e.response.content))
                    except Exception as e2:
                        logger.error("got exception trying to log response content: {}".format(e2))
                    # we hit the limit; give up, nack the message and raise an exception (which will put the actor in
                    # ERROR state).
                    if refresh_attempts == 10:
                        msg_obj.nack(requeue=True)
                        logger.info("worker exiting. worker_id: {}".format(worker_id))
                        raise e
                    else:
                        # otherwise, wait 2 seconds and then try again:
                        time.sleep(2)
        else:
            logger.info("Agave client `ag` is None -- not passing access token; worker_id: {}".format(worker_id))
        logger.info("Passing update environment: {}".format(environment))
        logger.info("About to execute actor; worker_id: {}".format(worker_id))
        try:
            stats, logs, final_state, exit_code, start_time = execute_actor(actor_id,
                                                                            worker_id,
                                                                            execution_id,
                                                                            image,
                                                                            message,
                                                                            user,
                                                                            environment,
                                                                            privileged,
                                                                            mounts,
                                                                            leave_containers,
                                                                            fifo_host_path,
                                                                            socket_host_path,
                                                                            mem_limit,
                                                                            max_cpus,
                                                                            tenant)
        except DockerStartContainerError as e:
            logger.error("Worker {} got DockerStartContainerError: {} trying to start actor for execution {}."
                         "Placing message back on queue.".format(worker_id, e, execution_id))
            # if we failed to start the actor container, we leave the worker up and re-queue the original message
            msg_obj.nack(requeue=True)
            logger.debug('message requeued.')
            consecutive_errors += 1
            if consecutive_errors > MAX_WORKER_CONSECUTIVE_ERRORS:
                logger.error("Worker {} failed to successfully start actor for execution {} {} consecutive times; "
                             "Exception: {}. Putting the actor in error status and shutting "
                             "down workers.".format(worker_id, execution_id, MAX_WORKER_CONSECUTIVE_ERRORS, e))
                Actor.set_status(actor_id, ERROR, "Error executing container: {}; w".format(e))
                shutdown_workers(actor_id, delete_actor_ch=False)
                # wait for worker to be shutdown..
                time.sleep(60)
                break
            else:
                # sleep five seconds before getting a message again to give time for the compute
                # node and/or docker health to recover
                time.sleep(5)
                continue
        except DockerStopContainerError as e:
            logger.error("Worker {} was not able to stop actor for execution: {}; Exception: {}. "
                         "Putting the actor in error status and shutting down workers.".format(worker_id, execution_id, e))
            Actor.set_status(actor_id, ERROR, "Error executing container: {}".format(e))
            # since the error was with stopping the actor, we will consider this message "processed"; this choice
            # could be reconsidered/changed
            msg_obj.ack()
            shutdown_workers(actor_id, delete_actor_ch=False)
            # wait for worker to be shutdown..
            time.sleep(60)
            break
        except Exception as e:
            logger.error("Worker {} got an unexpected exception trying to run actor for execution: {}."
                         "Putting the actor in error status and shutting down workers. "
                         "Exception: {}; type: {}".format(worker_id, execution_id, e, type(e)))
            Actor.set_status(actor_id, ERROR, "Error executing container: {}".format(e))
            # the execute_actor function raises a DockerStartContainerError if it met an exception before starting the
            # actor container; if the container was started, then another exception should be raised. Therefore,
            # we can assume here that the container was at least started and we can ack the message.
            msg_obj.ack()
            shutdown_workers(actor_id, delete_actor_ch=False)
            # wait for worker to be shutdown..
            time.sleep(60)
            break
        # ack the message
        msg_obj.ack()
        logger.debug("container finished successfully; worker_id: {}".format(worker_id))
        # Add the completed stats to the execution
        logger.info("Actor container finished successfully. Got stats object:{}".format(str(stats)))
        Execution.finalize_execution(actor_id, execution_id, COMPLETE, stats, final_state, exit_code, start_time)
        logger.info("Added execution: {}; worker_id: {}".format(execution_id, worker_id))

        # Add the logs to the execution
        try:
            Execution.set_logs(execution_id, logs, actor_id, tenant, worker_id)
            logger.debug("Successfully added execution logs.")
        except Exception as e:
            msg = "Got exception trying to set logs for exception {}; " \
                  "Exception: {}; worker_id: {}".format(execution_id, e, worker_id)
            logger.error(msg)

        # Update the worker's last updated and last execution fields:
        try:
            Worker.update_worker_execution_time(actor_id, worker_id)
            logger.debug("worker execution time updated. worker_id: {}".format(worker_id))
        except KeyError:
            # it is possible that this worker was sent a gracful shutdown command in the other thread
            # and that spawner has already removed this worker from the store.
            logger.info("worker {} got unexpected key error trying to update its execution time. "
                        "Worker better be shutting down! keep_running: {}".format(worker_id, globals.keep_running))
            if globals.keep_running:
                logger.error("worker couldn't update's its execution time but keep_running is still true!")

        # we completed an execution successfully; reset the consecutive_errors counter
        consecutive_errors = 0
        logger.info("worker time stamps updated; worker_id: {}".format(worker_id))
    logger.info("global.keep_running no longer true. worker is now exited. worker id: {}".format(worker_id))

def get_container_user(actor):
    logger.debug("top of get_container_user")
    if actor.get('use_container_uid'):
        logger.info("actor set to use_container_uid. Returning None for user")
        return None
    uid = actor.get('uid')
    gid = actor.get('gid')
    logger.debug(f"The uid: {uid} and gid: {gid} from the actor.")
    if not uid:
        if conf.global_auth_object.get("use_tas_uid") and not actor.get('use_container_uid'):
            logger.warn('Warning - legacy actor running as image UID without use_container_uid!')
        user = None
    elif not gid:
        user = uid
    else:
        user = '{}:{}'.format(uid, gid)
    return user

def main():
    """
    Main function for the worker process.

    This function
    """
    worker_id = os.environ.get('worker_id')
    image = os.environ.get('image')
    actor_id = os.environ.get('actor_id')

    client_id = os.environ.get('client_id', None)
    client_access_token = os.environ.get('client_access_token', None)
    client_refresh_token = os.environ.get('client_refresh_token', None)
    tenant = os.environ.get('tenant', None)
    api_server = os.environ.get('api_server', None)
    client_secret = os.environ.get('client_secret', None)

    logger.info(f"Top of main() for worker: {worker_id}, image: {image}; "
                f"actor_id: {actor_id}; client_id:{client_id}; tenant: {tenant}; api_server: {api_server}")
    spawner_worker_ch = SpawnerWorkerChannel(worker_id=worker_id)

    logger.debug("Worker waiting on message from spawner...")
    result = spawner_worker_ch.get()
    logger.debug("Worker received reply from spawner. result: {}.".format(result))

    # should be OK to close the spawner_worker_ch on the worker side since spawner was first client
    # to open it.
    spawner_worker_ch.close()
    logger.debug('spawner_worker_ch closed.')
    if not client_id:
        logger.info("Did not get client id.")
    else:
        logger.info(f"Got a client; client_id: {client_id}")

    logger.info(f"Actor {actor_id} status set to READY. subscribing to inbox.")
    worker_ch = WorkerChannel(worker_id=worker_id)
    subscribe(tenant,
              actor_id,
              image,
              worker_id,
              api_server,
              client_id,
              client_secret,
              client_access_token,
              client_refresh_token,
              worker_ch)


if __name__ == '__main__':
    # This is the entry point for the worker container.
    # Worker containers are launched by spawners and spawners pass the initial configuration
    # data for the worker through environment variables.
    logger.info("Initial log for new worker.")

    # call the main() function:
    try:
        os.system(f'sudo /home/tapis/actors/folder_permissions.sh /home/tapis/runtime_files/_abaco_fifos')
        os.system(f'sudo /home/tapis/actors/folder_permissions.sh /home/tapis/runtime_files/_abaco_results_sockets')
        main()
    except Exception as e:
        try:
            worker_id = os.environ.get('worker_id')
        except:
            worker_id = ''
        msg = "worker caught exception from main loop. worker exiting. e" \
              "Exception: {} worker_id: {}".format(e, worker_id)
        logger.info(msg)
    sys.exit()

