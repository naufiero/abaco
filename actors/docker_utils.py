import timeit

import docker
from requests.exceptions import ReadTimeout

from config import Config


AE_IMAGE = 'ab_reg'

max_run_time = Config.get('workers', 'max_run_time')

dd = Config.get('docker', 'dd')

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

def run_worker(image, ch_name):
    """
    Run an actor executor worker with a given channel and image
    :return:
    """
    cli = docker.AutoVersionClient(base_url=dd)
    container = cli.create_container(image=AE_IMAGE,
                                     environment={'ch_name': ch_name,
                                                  'image': image},
                                     volumes=['/var/run/docker.sock'],
                                     command='python3 /actors/worker.py')
    binds = {'/var/run/docker.sock':{
        'bind': '/var/run/docker.sock',
        'ro': False }}

    cli.start(container=container.get('Id'), binds=binds)
    return { 'image': image,
             # @todo - location will need to change to support swarm or multi-node compute cluster.
             'location': 'unix://var/run/docker.sock',
             'cid': container.get('Id'),
             'ch_name': ch_name}

def execute_actor(image, msg):
    result = {'cpu': 0,
              'io': 0,
              'runtime': 0 }
    cli = docker.AutoVersionClient(base_url=dd)
    container = cli.create_container(image=image, environment={'message': msg})
    try:
        cli.start(container=container.get('Id'))
    except Exception as e:
        # if there was an error starting the container, user will need to debig
        raise DockerStartContainerError("Could not start container {}. Exception {}".format(container.get('Id'), str(e)))
    start = timeit.default_timer()
    stats_obj = cli.stats(container=container.get('Id'), decode=True)
    running = True
    while running:
        try:
            stats = next(stats_obj)
            result['cpu'] += stats['cpu_stats']['cpu_usage']['total_usage']
            result['io'] += stats['network']['rx_bytes']
            cli.wait(container=container.get('Id'), timeout=0.1)
            running = False
        except ReadTimeout:
            runtime = timeit.default_timer() - start
            if max_run_time > 0 and max_run_time < runtime:
                cli.stop(container.get('Id'))
                running = False
    stop = timeit.default_timer()
    result['runtime'] = int(stop - start)
    return result