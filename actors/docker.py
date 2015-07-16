import timeit

import docker
from requests.exceptions import ReadTimeout

from .config import Config

max_run_time = Config.get('workers', 'max_run_time')

class DockerError(Exception):
    def __init__(self, message):
        Exception.__init__(self, message)
        self.message = message



def pull_image(image):
    """
    Update the local registry with an actor's image.
    :param actor_id:
    :return:
    """
    cli = docker.AutoVersionClient(base_url='unix://var/run/docker.sock')
    try:
        rsp = cli.pull(repository=image)
    except Exception as e:
        raise DockerError("Error pulling image {} - exception: {} ".format(image, str(e)))
    return rsp

def execute_actor(image, msg):
    result = {'cpu': 0,
              'io': 0,
              'runtime': 0 }
    cli = docker.AutoVersionClient(base_url='unix://var/run/docker.sock')
    container = cli.create_container(image=image, environment={'message': msg})
    cli.start(container=container.get('Id'))
    start = timeit.default_timer()
    stats_obj = cli.stats(container=container.get('Id'), decode=True)
    while True:
        try:
            cli.wait(container=container.get('Id'), timeout=0.5)
            stats = next(stats_obj)
            result['cpu'] += stats['cpu_stats']['cpu_usage']['total_usage']
            result['io'] += stats['network']['rx_bytes']
        except ReadTimeout:
            if max_run_time
            
    stop = timeit.default_timer()
    result['runtime'] = stop - start
    return result