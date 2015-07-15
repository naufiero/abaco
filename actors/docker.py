import docker
from models import Actor
from stores import actors_store

class ActorError(Exception):
    def __init__(self, message):
        Exception.__init__(self, message)
        self.message = message



def pull_image(actor_id):
    """
    Update the local registry with an actor's image.
    :param actor_id:
    :return:
    """
    try:
        actor = Actor.from_db(actors_store[actor_id])
    except KeyError:
        raise ActorError("Unable to pull image -- actor {} not found.".format(actor_id))
    image = actor.image
    cli = docker.AutoVersionClient(base_url='unix://var/run/docker.sock')
    try:
        rsp = cli.pull(repository=image)
    except Exception as e:
        raise ActorError("Error pulling image for actor {} - exception: {} ".format(actor_id, str(e)))
    return rsp

def execute_actor(image, msg):
    cli = docker.AutoVersionClient(base_url='unix://var/run/docker.sock')
    container = cli.create_container(image=image, environment={'message': msg})
    cli.start(container=container.get('Id'))
    cli.wait(container=container.get('Id'))
    

if __name__ == "__main__":
    rsp = pull_image("foo_1")
    print("Image pulled. Response: {}".format(str(rsp)))

