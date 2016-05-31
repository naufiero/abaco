import json
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

    def stop_workers(self, actor_id):
        """Stop existing workers; used when updating an actor's image."""

        try:
            workers_dict = json.loads(workers_store[actor_id])
        except KeyError:
            workers = {}

        # if there are existing workers, we need to close the actor message channel and
        # gracefully shutdown the existing worker processes.
        if len(workers_dict.items()) > 0:
            # first, close the actor msg channel to prevent any new messages from being pulled
            # by the old workers.
            actor_ch = ActorMsgChannel(actor_id)
            actor_ch.close()
            # now, send messages to workers for a graceful shutdown:
            for _, worker in workers_dict.items():
                ch = WorkerChannel(name=worker['ch_name'])
                ch.put('stop')


    def process(self, cmd):
        print("Processing cmd:{}".format(str(cmd)))
        actor_id = cmd['actor_id']
        image = cmd['image']
        stop_existing = cmd.get('stop_existing', True)
        num_workers = cmd.get('num', self.num_workers)
        print("Actor id:{}".format(actor_id))
        try:
            new_channels, anon_channels, new_workers = self.start_workers(actor_id, image, num_workers)
        except SpawnerException as e:
            # for now, start_workers will do clean up for a SpawnerException, so we just need
            # to return back to the run loop.
            return
        print("Created new workers: {}".format(str(new_workers)))

        # stop any existing workers:
        if stop_existing:
            self.stop_workers(actor_id)

        # add workers to store first so that the records will be there when the workers go
        # to update their status
        if not stop_existing:
            # @todo - NOT thread safe
            workers = json.loads(workers_store[actor_id])
            workers.extend(new_workers)
            workers_store[actor_id] = json.dumps(workers)
        else:
            workers_store[actor_id] = json.dumps(new_workers)


        # tell new workers to subscribe to the actor channel.
        for channel in anon_channels:
            channel.put({'status': 'ok', 'actor_id': actor_id})
        print("Done processing command.")


    def start_workers(self, actor_id, image, num_workers):
        print("starting {} workers. actor_id: {} image: {}".format(str(self.num_workers), actor_id, image))
        channels = []
        anon_channels = []
        workers = []
        try:
            for i in range(num_workers):
                print("starting worker {}".format(str(i)))
                ch, anon_ch, worker = self.start_worker(image)
                print("channel for worker {} is: {}".format(str(i), ch.name))
                channels.append(ch)
                anon_channels.append(anon_ch)
                workers.append(worker)
        except SpawnerException as e:
            print("Caught SpawnerException:{}".format(str(e)))
            # in case of an error, put the actor in error state and kill all workers
            Actor.set_status(actor_id, ERROR)
            for worker in workers:
                try:
                    self.kill_worker(worker)
                except DockerError as e:
                    print("Received DockerError trying to kill worker: {}".format(str(e)))
            raise SpawnerException()
        return channels, anon_channels, workers

    def start_worker(self, image):
        ch = WorkerChannel()
        # start an actor executor container and wait for a confirmation that image was pulled.
        worker = run_worker(image, ch.name)
        print("worker started successfully, waiting on ack that image was pulled...")
        result = ch.get()
        if result['value']['status'] == 'ok':
            print("received ack from worker.")
            return ch, result['reply_to'], worker
        else:
            print("Got an error status from worker: {}. Raising an exception.".format(str(result)))
            raise SpawnerException()

    def kill_worker(self, worker):
        pass

def main():
    # todo - find something more elegant
    idx = 0
    while idx < 3:
        try:
            sp = Spawner()
            print("spawner made connection to rabbit, entering main loop")
            sp.run()
        except rabbitpy.exceptions.ConnectionException:
            # rabbit seems to take a few seconds to come up
            time.sleep(5)
            idx += 1


if __name__ == '__main__':
    main()
