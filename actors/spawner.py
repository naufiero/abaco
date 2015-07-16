import time

import rabbitpy

from codes import ERROR
from config import Config
from docker_utils import DockerError, run_worker
from models import Actor
from stores import workers_store
from channels import ActorMsgChannel, CommandChannel, WorkerChannel


class SpawnerException(Exception):
    def __init__(self, message):
        Exception.__init__(self, message)
        self.message = message


class Spawner(object):

    def __init__(self):
        self.num_workers = int(Config.get('workers', 'init_count'))
        self.cmd_ch = CommandChannel()

    def run(self):
        while True:
            cmd = self.cmd_ch.get()
            self.process(cmd)

    def process(self, cmd):
        print("Processing cmd:{}".format(str(cmd)))
        actor_id = cmd['actor_id']
        image = cmd['image']
        try:
            new_channels, new_workers = self.start_workers(actor_id, image)
        except SpawnerException as e:
            # for now, start_workers will do clean up for a SpawnerException, so we just need
            # to return back to the run loop.
            return

        # get any existing workers:
        try:
            workers = workers_store[actor_id]
        except KeyError:
            workers = {}

        # if there are existing workers, we need to close the actor message channel and
        # gracefully shutdown the existing worker processes.
        if len(workers.values()) > 0 :
            # first, close the actor msg channel to prevent any new messages from being pulled
            # by the old workers.
            actor_ch = ActorMsgChannel(actor_id)
            actor_ch.close()

            # now, send messages to workers for a graceful shutdown:
            for worker in workers.values():
                ch = WorkerChannel(name=worker['ch_name'])
                ch.put('stop')

        # finally, tell new workers to subscribe to the actor channel.
        for channel in new_channels:
            channel.put({'status': 'ok', 'actor_id': actor_id})

        workers_store[actor_id] = new_workers

    def start_workers(self, actor_id, image):
        print("starting workers. actor_id: {} image: {}".format(actor_id, image))
        channels = []
        workers = []
        try:
            for i in range(self.num_workers):
                ch, worker = self.start_worker(image)
                channels.append(ch)
                workers.append(worker)
        except SpawnerException as e:
            print("Caught SpawnerException:{}".format(str(e)))
            # in case of an error, put the actor in error state and kill all workers
            Actor.set_status(actor_id, ERROR)
            for worker in workers:
                try:
                    self.kill_worker(worker)
                except DockerError as e:
                    # todo -- should log these but want to continue on.
                    pass
            raise SpawnerException()
        return channels, workers

    def start_worker(self, image):
        ch = WorkerChannel()
        # start an actor executor container and wait for a confirmation that image was pulled.
        worker = run_worker(image, ch._name)
        result = ch.get()
        if result['status'] == 'ok':
            return ch, worker
        else:
            raise SpawnerException()

    def kill_worker(self, worker):
        pass

def main():
    # todo - find something more elegant
    idx = 0
    while idx < 3:
        try:
            sp = Spawner()
            print("Made connection to rabbit, entering main loop")
            sp.run()
        except rabbitpy.exceptions.ConnectionException:
            # rabbit seems to take a few seconds to come up
            time.sleep(5)
            idx += 1


if __name__ == '__main__':
    main()
