import argparse
import subprocess

import codes
from .config import Config
from .models import Actor
from .stores import actors_store
from .tasks import SimpleProducer

class NoActorId(Exception):
    pass


class ImageNotFound(Exception):
    pass


class NewActorListener(object):
    """ Async worker that listens for the creation of new actors and staarts ActorExecutors in response.
    """
    def __init__(self):
        def start_actor_executor(msg, responder):
            """Start a new ActorExecutor"""
            actor_id = msg.get('actor_id')
            if not actor_id:
                raise NoActorId()
            cmd = 'python workers.py --type=actor_executor --actor_id=' + actor_id
            subprocess.Popen(cmd)

        uri = Config.get('rabbit', 'uri')
        port = Config.get('rabbit', 'port')
        self.con = SimpleProducer(host, port, queue_name='new_actor')
        self.con.consume_forever(start_actor_executor)


class ActorExecutor(object):
    """Asych worker object that can execute an actor container."""

    def __init___(self, actor_id):
        def execute_actor(msg, responder):
            """Execute an actor container with a given message."""
            # docker_run(self.image, msg)
            # inspect execution stats
            # post new actor execution
            # responder(message='ack') # acknowledge the queue
            pass
        self.actor_id = actor_id
        actor = Actor.from_db(actors_store[actor_id])
        self.image = actor.image
        try:
            self.get_image()
        except ImageNotFound as e:
            # if there is an exception here - for instance, if the image does not exist - we need to update the
            # database with an 'error' status to note that
            actor.status = codes.ERROR
            actor.status_msg = 'Image not found.'
            actors_store[actor.id] = actor.to_db()
            return
        # connect to actor_id queue:
        host = Config.get('rabbit', 'host')
        port = Config.get('rabbit', 'port')
        self.con = SimpleProducer(host, port, queue_name='actor_'+actor_id)
        actor.status = codes.READY
        actors_store[actor.id] = actor.to_db()
        self.con.consume_forever(execute_actor)


    def get_image(self):
        """Pull docker image to local registry."""
        pass

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create an actor executor for a given actor_id.')
    parser.add_argument('type', type=str,
                        help='Type of worker to start.')
    parser.add_argument('-a', '--actor_id', type=str,
                        help='The actor_id for type actor_executor.')
    args = parser.parse_args()
    if args.type == 'new_actor_listener':
        ne = NewActorListener()
    elif args.type == 'actor_exector':
        actor_id = args.actor_id
        if not actor_id:
            raise Exception("The actor_id parameter is required for type actor_executor.")
        ae = ActorExecutor(actor_id)
    else:
        raise Exception("Unrecognized worker type: {}".format(args.type))