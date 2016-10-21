import configparser
import json
import os
import time
import timeit

import docker
from requests.packages.urllib3.exceptions import ReadTimeoutError
from requests.exceptions import ReadTimeout

from config import Config
from codes import BUSY
from models import Worker

AE_IMAGE = os.environ.get('AE_IMAGE', 'jstubbs/abaco_core')

max_run_time = int(Config.get('workers', 'max_run_time'))

dd = Config.get('docker', 'dd')
host_id = Config.get('spawner', 'host_id')
host_ip = Config.get('spawner', 'host_ip')


class DockerError(Exception):
    def __init__(self, message):
        Exception.__init__(self, message)
        self.message = message

class DockerStartContainerError(DockerError):
    pass

def rm_container(cid):
    """
    Remove a container.
    :param cid:
    :return:
    """
    cli = docker.AutoVersionClient(base_url=dd)
    try:
        cli.remove_container(cid, force=True)
    except Exception as e:
        raise DockerError("Error removing container {}, exception: {}".format(cid, str(e)))

def pull_image(image):
    """
    Update the local registry with an actor's image.
    :param actor_id:
    :return:
    """
    cli = docker.AutoVersionClient(base_url=dd)
    try:
        rsp = cli.pull(repository=image)
    except Exception as e:
        raise DockerError("Error pulling image {} - exception: {} ".format(image, str(e)))
    return rsp

def container_running(image=None, name=None):
    """Check if there is a running container for an image.
    image should be fully qualified; e.g. image='jstubbs/abaco_core'
    Can pass wildcards in name using * character; e.g. name='abaco_spawner*'
    """
    filters = {}
    if name:
        filters['name'] = name
    if image:
        filters['image'] = image
    cli = docker.AutoVersionClient(base_url=dd)
    containers = cli.containers(filters=filters)
    return len(containers) > 0

def run_container_with_docker(image, command, name=None, environment={}):
    """Run a container with docker mounted in it."""
    cli = docker.AutoVersionClient(base_url=dd)
    volumes = ['/var/run/docker.sock']
    binds = {'/var/run/docker.sock': {'bind': '/var/run/docker.sock', 'ro': False}}
    try:
        abaco_conf_host_path = os.environ.get('abaco_conf_host_path')
        if not abaco_conf_host_path:
            abaco_conf_host_path = Config.get('spawner', 'abaco_conf_host_path')
        print("docker_utils using abaco_conf_host_path={}".format(abaco_conf_host_path))
        # if an abaco_conf_host_path was configured, mount that into the running container
        volumes.append('/abaco.conf')
        binds[abaco_conf_host_path] = {'bind': '/abaco.conf', 'ro': True}
    except configparser.NoOptionError:
        pass
    host_config = cli.create_host_config(binds=binds)
    container = cli.create_container(image=image,
                                     environment=environment,
                                     volumes=volumes,
                                     host_config=host_config,
                                     command=command)
    cli.start(container=container.get('Id'))
    return container

def run_worker(image, ch_name):
    """
    Run an actor executor worker with a given channel and image
    :return:
    """
    command = 'python3 -u /actors/worker.py'
    print("docker_utils running worker. image:{}, command:{}, chan:{}".format(
        image, command, ch_name
    ))
    container = run_container_with_docker(image=AE_IMAGE,
                                          command=command,
                                          environment={'ch_name': ch_name, 'image': image})
    # TODO - determines worker structure; should be placed in a proper DAO class.
    return { 'image': image,
             # @todo - location will need to change to support swarm or cluster
             'location': dd,
             'cid': container.get('Id'),
             'ch_name': ch_name,
             'status': BUSY,
             'host_id': host_id,
             'host_ip': host_ip,
             'last_execution': 0}

def execute_actor(actor_id, worker_ch, image, msg, d={}, privileged=False):
    result = {'cpu': 0,
              'io': 0,
              'runtime': 0 }
    cli = docker.AutoVersionClient(base_url=dd)
    d['MSG'] = msg
    binds = {}
    volumes = []
    # if container is privileged, mount the docker daemon so that additional
    # containers can be started.
    if privileged:
        binds = {'/var/run/docker.sock':{
                    'bind': '/var/run/docker.sock',
                    'ro': False }}
        volumes = ['/var/run/docker.sock']
    host_config = cli.create_host_config(binds=binds, privileged=privileged)
    container = cli.create_container(image=image, environment=d, volumes=volumes, host_config=host_config)
    try:
        cli.start(container=container.get('Id'))
    except Exception as e:
        # if there was an error starting the container, user will need to debig
        raise DockerStartContainerError("Could not start container {}. Exception {}".format(container.get('Id'), str(e)))
    start = timeit.default_timer()
    Worker.update_worker_status(actor_id, worker_ch.name, BUSY)
    running = True
    # create a separate cli for checkin stats objects since these should be fast and we don't want to wait
    stats_cli = docker.AutoVersionClient(base_url=dd, timeout=1)
    try:
        stats_obj = stats_cli.stats(container=container.get('Id'), decode=True)
    except ReadTimeout:
        # if the container execution is so fast that the inital stats object cannot be created,
        # we skip the running loop and return a minimal stats object
        result['cpu'] = 1
        result['runtime'] = 1
        return result
    while running:
        try:
            print("waiting on a stats obj: {}".format(timeit.default_timer()))
            stats = next(stats_obj)
        except ReadTimeoutError:
            print("next(stats) just timed out: {}".format(timeit.default_timer()))
            # container stopped before another stats record could be read, just ignore and move on
            running = False
            break
        try:
            result['cpu'] += stats['cpu_stats']['cpu_usage']['total_usage']
            result['io'] += stats['network']['rx_bytes']
        except KeyError:
            # as of docker 1.9, the stats object returns bytes that must be decoded
            # and the network key is now 'networks' with multiple subkeys.
            print("got a stats obj: {}".format(timeit.default_timer()))
            if type(stats) == bytes:
                stats = json.loads(stats.decode("utf-8"))
            result['cpu'] += stats['cpu_stats']['cpu_usage']['total_usage']
            # even running docker 1.9, there seems to be a race condition where the 'networks' key doesn't
            # always get populated.
            try:
                result['io'] += stats['networks']['eth0']['rx_bytes']
            except KeyError:
                pass
            print("Recorded a stats obj:".format(timeit.default_timer()))
        if running:
            try:
                print("waiting on cli.wait: {}".format(timeit.default_timer()))
                cli.wait(container=container.get('Id'), timeout=1)
                print("container finished: {}".format(timeit.default_timer()))
                running = False
            except ReadTimeout:
                print("cli.wait just timed out: {}".format(timeit.default_timer()))
                # the wait timed out so check if we are beyond the max_run_time
                runtime = timeit.default_timer() - start
                if max_run_time > 0 and max_run_time < runtime:
                    print("hit runtime limit: {}".format(timeit.default_timer()))
                    cli.stop(container.get('Id'))
                    running = False
    print("container stopped:{}".format(timeit.default_timer()))
    stop = timeit.default_timer()
    # get logs from container
    logs = cli.logs(container.get('Id'))
    # remove container, ignore errors
    try:
        cli.remove_container(container=container)
        print("Container removed.")
    except Exception as e:
        print("Exception trying to remove actor: {}".format(e))
    result['runtime'] = int(stop - start)
    return result, logs
