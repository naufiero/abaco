# Ensures that:
# 1. all worker containers in the database are still responsive; workers that have stopped
#    responding are shutdown and removed from the database.
# 2. Enforce ttl for idle workers.
#
# In the future, this module will also implement:
# 3. all actors with stateless=true have a number of workers proportional to the messages in the queue.

# Execute from a container on a schedule as follows:
# docker run -it --rm -v /var/run/docker.sock:/var/run/docker.sock abaco/core python3 -u /actors/health.py

import os
import shutil
import time
import datetime

from agaveflask.auth import get_api_server
import channelpy

from aga import Agave
from auth import get_tenants, get_tenant_verify
import codes
from common.config import conf
from docker_utils import rm_container, DockerError, container_running, run_container_with_docker
from models import Actor, Worker, is_hashid
from channels import ClientsChannel, CommandChannel, WorkerChannel
from stores import actors_store, clients_store, executions_store, workers_store
from worker import shutdown_worker

TAG = os.environ.get('TAG') or conf.version or ""
if not TAG[0] == ":":
    TAG = f":{TAG}"
AE_IMAGE = f"{os.environ.get('AE_IMAGE', 'abaco/core')}{TAG}"

from common.logs import get_logger
logger = get_logger(__name__)

# max executions allowed in a mongo document; if the total executions for a given actor exceeds this number,
# the health process will place
MAX_EXECUTIONS_PER_MONGO_DOC = 25000

def get_actor_ids():
    """Returns the list of actor ids currently registered."""
    return [aid for aid in actors_store]

def check_workers_store(ttl):
    logger.debug("Top of check_workers_store.")
    """Run through all workers in workers_store and ensure there is no data integrity issue."""
    for worker in workers_store.items():
        aid = worker['actor_id']
        check_worker_health(aid, worker, ttl)

def get_worker(wid):
    """
    Check to see if a string `wid` is the id of a worker in the worker store.
    If so, return it; if not, return None.
    """
    worker = workers_store.items({'id': wid})
    if worker:
        return worker
    return None

def clean_up_socket_dirs():
    logger.debug("top of clean_up_socket_dirs")
    socket_dir = os.path.join('/', conf.worker_socket_host_path_dir.strip('/'))
    logger.debug("processing socket_dir: {}".format(socket_dir))
    for p in os.listdir(socket_dir):
        # check to see if p is a worker
        worker = get_worker(p)
        if not worker:
            path = os.path.join(socket_dir, p)
            logger.debug("Determined that {} was not a worker; deleting directory: {}.".format(p, path))
            shutil.rmtree(path)

def clean_up_fifo_dirs():
    logger.debug("top of clean_up_fifo_dirs")
    fifo_dir = os.path.join('/', conf.worker_fifo_host_path_dir.strip('/'))
    logger.debug("processing fifo_dir: {}".format(fifo_dir))
    for p in os.listdir(fifo_dir):
        # check to see if p is a worker
        worker = get_worker(p)
        if not worker:
            path = os.path.join(fifo_dir, p)
            logger.debug("Determined that {} was not a worker; deleting directory: {}.".format(p, path))
            shutil.rmtree(path)

def clean_up_ipc_dirs():
    """Remove all directories created for worker sockets and fifos"""
    clean_up_socket_dirs()
    clean_up_fifo_dirs()

def delete_client(ag, client_name):
    """Remove a client from the APIM."""
    try:
        ag.clients.delete(clientName=client_name)
    except Exception as e:
        m = 'Not able to delete client from APIM. Got an exception: {}'.format(e)
        logger.error(m)
    return None

def clean_up_apim_clients(tenant):
    """Check the list of clients registered in APIM and remove any that are associated with retired workers."""
    username = os.environ.get('_abaco_{}_username'.format(tenant), '')
    password = os.environ.get('_abaco_{}_password'.format(tenant), '')
    if not username:
        msg = "Health process did not get a username for tenant {}; " \
              "returning from clean_up_apim_clients".format(tenant)
        if tenant in ['SD2E', 'TACC-PROD']:
            logger.error(msg)
        else:
            logger.info(msg)
        return None
    if not password:
        msg = "Health process did not get a password for tenant {}; " \
              "returning from clean_up_apim_clients".format(tenant)
        if tenant in ['SD2E', 'TACC-PROD']:
            logger.error(msg)
        else:
            logger.info(msg)
        return None
    api_server = get_api_server(tenant)
    verify = get_tenant_verify(tenant)
    ag = Agave(api_server=api_server,
               username=username,
               password=password,
               verify=verify)
    logger.debug("health process created an ag for tenant: {}".format(tenant))
    try:
        cs = ag.clients.list()
        clients = cs.json()['result']
    except Exception as e:
        msg = "Health process got an exception trying to retrieve clients; exception: {}".format(e)
        logger.error(msg)
        return None
    for client in clients:
        # check if the name of the client is an abaco hash (i.e., a worker id). if not, we ignore it from the beginning
        name = client.get('name')
        if not is_hashid(name):
            logger.debug("client {} is not an abaco hash id; skipping.".format(name))
            continue
        # we know this client came from a worker, so we need to check to see if the worker is still active;
        # first check if the worker even exists; if it does, the id will be the client name:
        worker = get_worker(name)
        if not worker:
            logger.info("no worker associated with id: {}; deleting client.".format(name))
            delete_client(ag, name)
            logger.info("client {} deleted by health process.".format(name))
            continue
        # if the worker exists, we should check the status:
        status = worker.get('status')
        if status == codes.ERROR:
            logger.info("worker {} was in ERROR status so deleting client; worker: {}.".format(name, worker))
            delete_client(ag, name)
            logger.info("client {} deleted by health process.".format(name))
        else:
            logger.debug("worker {} still active; not deleting client.".format(worker))

def clean_up_clients_store():
    logger.debug("top of clean_up_clients_store")
    secret = os.environ.get('_abaco_secret')
    if not secret:
        logger.error("health.py not configured with _abaco_secret. exiting clean_up_clients_store.")
        return None
    for client in clients_store.items():
        wid = client.get('worker_id')
        if not wid:
            logger.error("client object in clients_store without worker_id. client: {}".format(client))
            continue
        tenant = client.get('tenant')
        if not tenant:
            logger.error("client object in clients_store without tenant. client: {}".format(client))
            continue
        actor_id = client.get('actor_id')
        if not actor_id:
            logger.error("client object in clients_store without actor_id. client: {}".format(client))
            continue
        client_key = client.get('client_key')
        if not client_key:
            logger.error("client object in clients_store without client_key. client: {}".format(client))
            continue
        # check to see if the wid is the id of an actual worker:
        worker = get_worker(wid)
        if not worker:
            logger.info(f"worker {wid} is gone. deleting client {client}.")
            clients_ch = ClientsChannel()
            msg = clients_ch.request_delete_client(tenant=tenant,
                                                   actor_id=actor_id,
                                                   worker_id=wid,
                                                   client_id=client_key,
                                                   secret=secret)
            if msg['status'] == 'ok':
                logger.info(f"Client delete request completed successfully for "
                            "worker_id: {wid}, client_id: {client_key}.".format(wid, client_key))
            else:
                logger.error(f"Error deleting client for "
                             "worker_id: {wid}, client_id: {client_key}. Message: {msg}")

        else:
            logger.info(f"worker {wid} still here. ignoring client {client}.")

def check_worker_health(actor_id, worker, ttl):
    """Check the specific health of a worker object."""
    logger.debug("top of check_worker_health")
    worker_id = worker.get('id')
    logger.info("Checking status of worker from db with worker_id: {}".format(worker_id))
    if not worker_id:
        logger.error("Corrupt data in the workers_store. Worker object without an id attribute. {}".format(worker))
        try:
            workers_store.pop_field([actor_id])
        except KeyError:
            # it's possible another health agent already removed the worker record.
            pass
        return None
    # make sure the actor id still exists:
    try:
        actors_store[actor_id]
    except KeyError:
        logger.error("Corrupt data in the workers_store. Worker object found but no corresponding actor. {}".format(worker))
        try:
            # todo - removing worker objects from db can be problematic if other aspects of the worker are not cleaned
            # up properly. this code should be reviewed.
            workers_store.pop_field([actor_id])
        except KeyError:
            # it's possible another health agent already removed the worker record.
            pass
        return None

def zero_out_workers_db():
    """
    Set all workers collections in the db to empty. Run this as part of a maintenance; steps:
      1) remove all docker containers
      2) run this function
      3) run clean_up_apim_clients().
      4) run zero_out_clients_db()
    :return:
    """
    for worker in workers_store.items(proj_inp=None):
        del workers_store[worker['_id']]

def zero_out_clients_db():
    """
    Set all clients collections in the db to empty. Run this as part of a maintenance; steps:
      1) remove all docker containers
      2) run zero_out_workers_db()
      3) run clean_up_apim_clients().
      4) run this function
    :return:
    """
    for client in clients_store.items():
        clients_store[client['_id']] = {}


def check_workers(actor_id, ttl):
    """Check health of all workers for an actor."""
    logger.info("Checking health for actor: {}".format(actor_id))
    try:
        workers = Worker.get_workers(actor_id)
    except Exception as e:
        logger.error("Got exception trying to retrieve workers: {}".format(e))
        return None
    logger.debug(f"workers: {workers}")
    host_id = os.environ.get('SPAWNER_HOST_ID', conf.spawner_host_id)
    logger.debug(f"host_id: {host_id}")
    for worker in workers:
        # if the worker has only been requested, it will not have a host_id.
        if 'host_id' not in worker:
            # @todo- we will skip for now, but we need something more robust in case the worker is never claimed.
            continue
        # ignore workers on different hosts
        if not host_id == worker['host_id']:
            continue
        # first check if worker is responsive; if not, will need to manually kill
        logger.info("Checking health for worker: {}".format(worker))
        ch = WorkerChannel(worker_id=worker['id'])
        worker_id = worker.get('id')
        result = None
        try:
            logger.debug("Issuing status check to channel: {}".format(worker['ch_name']))
            result = ch.put_sync('status', timeout=5)
        except channelpy.exceptions.ChannelTimeoutException:
            logger.info("Worker did not respond, removing container and deleting worker.")
            try:
                rm_container(worker['cid'])
            except DockerError:
                pass
            try:
                Worker.delete_worker(actor_id, worker_id)
                logger.info("worker {} deleted from store".format(worker_id))
            except Exception as e:
                logger.error("Got exception trying to delete worker: {}".format(e))
            # if the put_sync timed out and we removed the worker, we also need to delete the channel
            # otherwise the un-acked message will remain.
            try:
                ch.delete()
            except Exception as e:
                logger.error("Got exception: {} while trying to delete worker channel for worker: {}".format(e, worker_id))
        finally:
            try:
                ch.close()
            except Exception as e:
                logger.error("Got an error trying to close the worker channel for dead worker. Exception: {}".format(e))
        if result and not result == 'ok':
            logger.error("Worker responded unexpectedly: {}, deleting worker.".format(result))
            try:
                rm_container(worker['cid'])
                Worker.delete_worker(actor_id, worker_id)
            except Exception as e:
                logger.error("Got error removing/deleting worker: {}".format(e))
        else:
            # worker is healthy so update last health check:
            Worker.update_worker_health_time(actor_id, worker_id)
            logger.info("Worker ok.")

        # now check if the worker has been idle beyond the ttl:
        if ttl < 0:
            # ttl < 0 means infinite life
            logger.info("Infinite ttl configured; leaving worker")
            return
        # we don't shut down workers that are currently running:
        if not worker['status'] == codes.BUSY:
            last_execution = worker.get('last_execution_time', 0)
            # if worker has made zero executions, use the create_time
            if last_execution == 0:
                last_execution = worker.get('create_time', datetime.datetime.min)
            logger.debug("using last_execution: {}".format(last_execution))
            try:
                assert type(last_execution) == datetime.datetime
            except:
                logger.error("Time received for TTL measurements is not of type datetime.")
                last_execution = datetime.datetime.min
            if last_execution + datetime.timedelta(seconds=ttl) < datetime.datetime.utcnow():
                # shutdown worker
                logger.info("Shutting down worker beyond ttl.")
                shutdown_worker(actor_id, worker['id'])
            else:
                logger.info("Still time left for this worker.")

        if worker['status'] == codes.ERROR:
            # shutdown worker
            logger.info("Shutting down worker in error status.")
            shutdown_worker(actor_id, worker['id'])
        # else:
        #     logger.debug("Worker not in READY status, will postpone.")

def get_host_queues():
    """
    Read host_queues string from config and parse to return a Python list.
    :return: list[str]
    """
    try:
        host_queues = conf.spawner_host_queues
        return host_queues
    except Exception as e:
        msg = "Got unexpected exception attempting to parse the host_queues config. Exception: {}".format(e)
        logger.error(e)
        raise e

def start_spawner(queue, idx='0'):
    """
    Start a spawner on this host listening to a queue, `queue`.
    :param queue: (str) - the queue the spawner should listen to.
    :param idx: (str) - the index to use as a suffix to the spawner container name.
    :return:
    """
    command = 'python3 -u /actors/spawner.py'
    name = 'healthg_{}_spawner_{}'.format(queue, idx)

    try:
        environment = dict(os.environ)
    except Exception as e:
        environment = {}
        logger.error("Unable to convert environment to dict; exception: {}".format(e))

    environment.update({'AE_IMAGE': AE_IMAGE.split(':')[0],
                        'queue': queue,
    })
    if not '_abaco_secret' in environment:
        msg = 'Error in health process trying to start spawner. Did not find an _abaco_secret. Aborting'
        logger.critical(msg)
        raise

    # check logging strategy to determine log file name:
    log_file = 'abaco.log'
    if conf.log_filing_strategy == 'split':
        log_file = 'spawner.log'
    try:
        run_container_with_docker(AE_IMAGE,
                                  command,
                                  name=name,
                                  environment=environment,
                                  mounts=[],
                                  log_file=log_file)
    except Exception as e:
        logger.critical("Could not restart spawner for queue {}. Exception: {}".format(queue, e))

def check_spawner(queue):
    """
    Check the health and existence of a spawner on this host for a particular queue.
    :param queue: (str) - the queue to check on.
    :return:
    """
    logger.debug("top of check_spawner for queue: {}".format(queue))
    # spawner container names by convention should have the format <project>_<queue>_spawner_<count>; for example
    #   abaco_default_spawner_2.
    # so, we look for container names containing a string with that format:
    spawner_name_segment = '{}_spawner'.format(queue)
    if not container_running(name=spawner_name_segment):
        logger.critical("No spawners running for queue {}! Launching new spawner..".format(queue))
        start_spawner(queue)
    else:
        logger.debug("spawner for queue {} already running.".format(queue))

def check_spawners():
    """
    Check health of spawners running on a given host.
    :return:
    """
    logger.debug("top of check_spawners")
    host_queues = get_host_queues()
    logger.debug("checking spawners for queues: {}".format(host_queues))
    for queue in host_queues:
        check_spawner(queue)


def manage_workers(actor_id):
    """Scale workers for an actor if based on message queue size and policy."""
    logger.info("Entering manage_workers for {}".format(actor_id))
    try:
        actor = Actor.from_db(actors_store[actor_id])
    except KeyError:
        logger.info("Did not find actor; returning.")
        return
    workers = Worker.get_workers(actor_id)
    for worker in workers:
        time_difference = time.time() - worker['create_time']
        if worker['status'] == 'PROCESSING' and time_difference > 1:
            logger.info("LOOK HERE - worker creation time {}".format(worker['create_time']))
    #TODO - implement policy

def shutdown_all_workers():
    """
    Utility function for properly shutting down all existing workers.
    This function is useful when deploying a new version of the worker code.
    """
    # iterate over the workers_store directly, not the actors_store, since there could be data integrity issue.
    logger.debug("Top of shutdown_all_workers.")
    actors_with_workers = set()
    for worker in workers_store.items():
        actors_with_workers.add(worker['actor_id'])

    for actor_id in actors_with_workers:
        check_workers(actor_id, 0)

def main():
    logger.info("Running abaco health checks. Now: {}".format(time.time()))
    # TODO - turning off the check_spawners call in the health process for now as there seem to be some issues.
    # the way the check works currently is to look for a spawner with a specific name. However, that check does not
    # appear to be working currently.
    # check_spawners()
    try:
        clean_up_ipc_dirs()
    except Exception as e:
        logger.error("Got exception from clean_up_ipc_dirs: {}".format(e))
    ttl = conf.worker_worker_ttl
    ids = get_actor_ids()
    logger.info("Found {} actor(s). Now checking status.".format(len(ids)))
    for id in ids:
        # manage_workers(id)
        check_workers(id, ttl)
    tenants = get_tenants()
    for t in tenants:
        logger.debug("health process cleaning up apim_clients for tenant: {}".format(t))
        clean_up_apim_clients(t)

    # TODO - turning off the check_workers_store for now. unclear that removing worker objects
    # check_workers_store(ttl)

if __name__ == '__main__':
    main()