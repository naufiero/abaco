# Ensures that:
# 1. all worker containers in the database are still responsive
# 2. all actors have at least one responsive worker
# 3. all actors with autoscale=true have a number of workers proportional to the messages in the queue.

# Execute from a container on a schedule as follows:
# docker run -it --rm -v /var/run/docker.sock:/var/run/docker.sock jstubbs/abaco_core python3 -u /actors/health.py

import channelpy

from docker_utils import rm_container, DockerError
from models import Actor, delete_worker, get_workers
from channels import CommandChannel, WorkerChannel
from stores import actors_store

def get_actor_ids():
    """Returns the list of actor ids currently registered."""
    return [id for id, _ in actors_store.items()]

def check_workers(actor_id):
    """Check health of all workers for an actor."""
    print("Checking health for actors: {}".format(actor_id))
    workers = get_workers(actor_id)
    print("workers: {}".format(workers))
    for worker in workers:
        print("Checking health for worker: {}".format(worker))
        ch = WorkerChannel(name=worker['ch_name'])
        try:
            print("Issuing status check to channel: {}".format(worker['ch_name']))
            result = ch.put_sync('status', timeout=5)
        except channelpy.exceptions.ChannelTimeoutException:
            print("Worker did not respond, removing container and deleting worker.")
            try:
                rm_container(worker['cid'])
            except DockerError:
                pass
            delete_worker(actor_id, worker['ch_name'])
            continue
        if not result == 'ok':
            print("Worker responded unexpectedly: {}, deleting worker.".format(result))
            rm_container(worker['cid'])
            delete_worker(actor_id, worker['ch_name'])
        else:
            print("Worker ok.")

def add_workers(actor_id):
    """Add workers for an actor if necessary."""
    print("Entering add_workers for {}".format(actor_id))
    try:
        actor = Actor.from_db(actors_store[actor_id])
    except KeyError:
        print("Did not find actor; returning.")
        return
    workers = get_workers(actor_id)
    if len(workers) < 1:
        print("Found zero workers, starting another worker.")
        ch = CommandChannel()
        ch.put_cmd(actor_id=actor.id, image=actor.image, num=1, stop_existing=False)
    else:
        print("Found at least one worker.")

def main():
    print("Running abaco health checks...")
    ids = get_actor_ids()
    print("Found {} actor(s). Now checking status.".format(len(ids)))
    for id in ids:
        check_workers(id)
        add_workers(id)


if __name__ == '__main__':
    main()