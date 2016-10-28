import json
import os
import time

import rabbitpy

from codes import ERROR
from config import Config
from docker_utils import DockerError, run_worker
from models import Actor, Worker
from stores import workers_store
from channels import ActorMsgChannel, ClientsChannel, CommandChannel, WorkerChannel


class SpawnerException(Exception):
    def __init__(self, message):
        Exception.__init__(self, message)
        self.message = message


class Spawner(object):

    def __init__(self):
        self.num_workers = int(Config.get('workers', 'init_count'))
        self.secret = os.environ.get('_abaco_secret')
        self.cmd_ch = CommandChannel()

    def run(self):
        while True:
            cmd = self.cmd_ch.get()
            self.process(cmd)

    def stop_workers(self, actor_id):
        """Stop existing workers; used when updating an actor's image."""

        try:
            workers_dict = workers_store[actor_id]
        except KeyError:
            workers_dict = {}

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
        tenant = cmd['tenant']
        stop_existing = cmd.get('stop_existing', True)
        num_workers = cmd.get('num', self.num_workers)
        print("Actor id:{}".format(actor_id))
        try:
            new_channels, anon_channels, new_workers = self.start_workers(actor_id, image, tenant, num_workers)
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
            for _, worker in new_workers.items():
                Worker.add_worker(actor_id, worker)
        else:
            workers_store[actor_id] = new_workers
        # send new workers their clients and tell them to subscribe to the actor channel.
        for idx, channel in enumerate(anon_channels):
            print("Getting client for worker {}".format(idx))
            client_ch = ClientsChannel()
            client_msg = client_ch.request_client(tenant=tenant,
                                                  actor_id=actor_id,
                                                  # new_workers is a dictionary of dictionaries; list(d) creates a
                                                  # list of keys for a dictionary d. hence, the idx^th entry
                                                  # of list(ner_workers) should be the key.
                                                  worker_id=new_workers[list(new_workers)[idx]]['ch_name'],
                                                  secret=self.secret)
            # we need to ignore errors when generating clients because it's possible it is not set up for a specific
            # tenant. we log it instead.
            if client_msg.get('status') == 'error':
                print("Error generating client: {}".format(client_msg.get('message')))
                channel.put({'status': 'ok',
                             'actor_id': actor_id,
                             'tenant': tenant,
                             'client': 'no'})
            # else, client was generated successfully:
            else:
                print("Got a client: {}, {}, {}".format(client_msg['client_id'],
                                                        client_msg['access_token'],
                                                        client_msg['refresh_token']))
                channel.put({'status': 'ok',
                             'actor_id': actor_id,
                             'tenant': tenant,
                             'client': 'yes',
                             'client_id': client_msg['client_id'],
                             'client_secret': client_msg['client_secret'],
                             'access_token': client_msg['access_token'],
                             'refresh_token': client_msg['refresh_token'],
                             'api_server': client_msg['api_server'],
                             })
        print("Done processing command.")


    def start_workers(self, actor_id, image, tenant, num_workers):
        print("starting {} workers. actor_id: {} image: {}".format(str(self.num_workers), actor_id, image))
        channels = []
        anon_channels = []
        workers = {}
        try:
            for i in range(num_workers):
                print("starting worker {}".format(str(i)))
                ch, anon_ch, worker = self.start_worker(image, tenant)
                print("channel for worker {} is: {}".format(str(i), ch.name))
                channels.append(ch)
                anon_channels.append(anon_ch)
                workers[worker['ch_name']] = worker
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

    def start_worker(self, image, tenant):
        ch = WorkerChannel()
        # start an actor executor container and wait for a confirmation that image was pulled.
        worker_dict = run_worker(image, ch.name)
        worker = Worker(tenant=tenant, **worker_dict)
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
            print("spawner using abaco_conf_host_path={}".format(os.environ.get('abaco_conf_host_path')))
            sp.run()
        except rabbitpy.exceptions.ConnectionException:
            # rabbit seems to take a few seconds to come up
            time.sleep(5)
            idx += 1


if __name__ == '__main__':
    main()
