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
import time

import channelpy

import codes
from config import Config
from docker_utils import rm_container, DockerError, container_running, run_container_with_docker
from models import Actor, Worker
from channels import CommandChannel, WorkerChannel
from stores import actors_store
from worker import shutdown_worker

AE_IMAGE = os.environ.get('AE_IMAGE', 'abaco/core')

from logs import get_logger, get_log_file_strategy
logger = get_logger(__name__)


def get_actor_ids():
    """Returns the list of actor ids currently registered."""
    return [db_id for db_id, _ in actors_store.items()]

def check_workers(actor_id, ttl):
    """Check health of all workers for an actor."""
    logger.info("Checking health for actor: {}".format(actor_id))
    try:
        workers = Worker.get_workers(actor_id)
    except Exception as e:
        logger.error("Got exception trying to retrieve workers: {}".format(e))
        return None
    logger.debug("workers: {}".format(workers))
    for _, worker in workers.items():
        # if the worker has only been requested, it will not have a host_id.
        if 'host_id' not in worker:
            # @todo- we will skip for now, but we need something more robust in case the worker is never claimed.
            continue
        # ignore workers on different hosts
        if not Config.get('spawner', 'host_id') == worker['host_id']:
            continue
        # first check if worker is responsive; if not, will need to manually kill
        logger.info("Checking health for worker: {}".format(worker))
        ch = WorkerChannel(name=worker['ch_name'])
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
                Worker.delete_worker(actor_id, worker['ch_name'])
            except Exception as e:
                logger.error("Got exception trying to delete worker: {}".format(e))
            continue
        if not result == 'ok':
            logger.error("Worker responded unexpectedly: {}, deleting worker.".format(result))
            try:
                rm_container(worker['cid'])
                Worker.delete_worker(actor_id, worker['ch_name'])
            except Exception as e:
                logger.error("Got error removing/deleting worker: {}".format(e))
        else:
            logger.info("Worker ok.")
        # now check if the worker has been idle beyond the ttl:
        if ttl < 0:
            # ttl < 0 means infinite life
            logger.info("Infinite ttl configured; leaving worker")
            return
        if worker['status'] == codes.READY and \
            worker['last_execution'] + ttl < time.time():
            # shutdown worker
            logger.info("Shutting down worker beyond ttl.")
            shutdown_worker(worker['ch_name'])
        else:
            logger.debug("Worker still has life.")

def manage_workers(actor_id):
    """Scale workers for an actor if based on message queue size and policy."""
    logger.info("Entering manage_workers for {}".format(actor_id))
    try:
        actor = Actor.from_db(actors_store[actor_id])
    except KeyError:
        logger.info("Did not find actor; returning.")
        return
    workers = Worker.get_workers(actor_id)
    #TODO - implement policy

def main():
    logger.info("Running abaco health checks. Now: {}".format(time.time()))
    try:
        ttl = Config.get('workers', 'worker_ttl')
    except Exception as e:
        logger.error("Could not get worker_ttl config. Exception: {}".format(e))
    if not container_running(name='spawner*'):
        logger.critical("No spawners running! Launching new spawner..")
        command = 'python3 -u /actors/spawner.py'
        # check logging strategy to determine log file name:
        if get_log_file_strategy() == 'split':
            log_file = 'spawner.log'
        else:
            log_file = 'abaco.log'
        try:
            run_container_with_docker(AE_IMAGE,
                                      command,
                                      name='abaco_spawner_0',
                                      environment={'AE_IMAGE': AE_IMAGE},
                                      log_file=log_file)
        except Exception as e:
            logger.critical("Could not restart spanwer. Exception: {}".format(e))
    try:
        ttl = int(ttl)
    except Exception as e:
        logger.error("Invalid ttl config: {}. Setting to -1.".format(e))
        ttl = -1
    ids = get_actor_ids()
    logger.info("Found {} actor(s). Now checking status.".format(len(ids)))
    for id in ids:
        check_workers(id, ttl)
        # manage_workers(id)


if __name__ == '__main__':
    main()