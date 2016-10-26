"""
Process to generate Agave clients for workers.
"""

import os
import time
import rabbitpy

from agavepy.agave import Agave

from auth import get_api_server, get_tenants
from channels import ClientsChannel
from models import Actor, Client, Worker
from errors import ClientException, WorkerException
from stores import actors_store, clients_store

class ClientGenerator(object):

    def __init__(self):
        self.secret = os.environ.get('_abaco_secret')
        self.ch = ClientsChannel()
        self.credentials = {}
        for tenant in get_tenants():
            self.credentials[tenant]['username'] = os.environ.get('_abaco_{}_username'.format(tenant), '')
            self.credentials[tenant]['password'] = os.environ.get('_abaco_{}_password'.format(tenant), '')


    def get_agave(self, tenant, actor_owner):
        """
        Generate an agavepy client representing a specific user owning an actor.
        The `actor_owner` should be the username associated with the owner of the actor.
        """
        username = self.credentials[tenant.upper()]['username']
        password = self.credentials[tenant.upper()]['password']
        if username == '' or password == '':
            raise ClientException('Client service credentials not defined for tenant {}'.format(tenant))
        api_server = get_api_server(tenant)
        return Agave(api_server=api_server, username=username, password=password, token_username=actor_owner)


    def run(self):
        """
        Listen to the clients channel for new client requests. Requests use the put_sync method to send
        an anonymous channel together with the actual client request command.
        """
        while True:
            message = self.ch.get()
            anon_ch = message['reply_to']
            cmd = message['value']
            if cmd.get('command') == 'new':
                self.new_client(cmd, anon_ch)
            elif cmd.get('command') == 'delete':
                self.delete_client(cmd, anon_ch)
            else:
                ch = ClientsChannel(name=anon_ch)
                ch.put({'status': 'error',
                        'message': 'Received invalid command: {}'.format(cmd.get('command'))})

    def new_client(self, cmd, anon_ch):
        valid, msg, owner = self.check_new_params(cmd)
        if valid:
            try:
                key, secret, access_token, refresh_token = self.generate_client(cmd, owner)
            except ClientException as e:
                ch = ClientsChannel(name=anon_ch)
                ch.put({'status': 'error',
                        'message': e.msg})
                return None
            cl = Client({'tenant': cmd['tenant'],
                         'actor_id': cmd['actor_id'],
                         'worker_id': cmd['worker_id'],
                         'client_key': key,
                         'client_name': cmd['worker_id'],
                         })
            clients_store[cl.id] = cl
            self.send_client(key, secret, access_token, refresh_token, anon_ch)
        else:
            ch = ClientsChannel(name=anon_ch)
            ch.put({'status': 'error',
                    'message': 'Invalid command parameters: {}'.format(msg)})

    def generate_client(self, cmd, owner):
        ag = self.get_agave(cmd['tenant'], actor_owner=owner)
        client = ag.clients.create(body={'clientName': cmd['worker_id']})
        # note - the client generates tokens representing the user who registered the actor
        return client['consumerKey'], \
               client['consumerSecret'], \
               client.token.token_info['access_token'], \
               client.token.token_info['refresh_token']


    def send_client(self, client_id, client_secret, access_token, refresh_token, anon_ch):
        """Send client credentials to a worker on an anonymous channel."""
        msg = {'status': 'ok',
               'client_id': client_id,
               'client_secret': client_secret,
               'access_token': access_token,
               'refresh_token': refresh_token}
        ch = ClientsChannel(name=anon_ch)
        ch.put(msg)

    def check_common(self, cmd):
        # validate the secret
        if not cmd.get('secret') == self.secret:
            return False, 'Invalid secret.', None
        # validate tenant
        if not cmd.get('tenant') in get_tenants():
            return False, 'Invalid client passed: {}'.format(cmd.get('tenant')), None
        # validate the actor_id
        try:
            actor = Actor.from_db(actors_store[cmd.get('actor_id')])
        except KeyError:
            return False, "Unable to look up actor with id: {}".format(cmd.get('actor_id')), None
        # validate the worker id
        try:
            Worker.get_worker(actor_id=cmd.get('actor_id'), ch_name=cmd.get('worker_id'))
        except WorkerException as e:
            return False, "Unable to look up worker: {}".format(e.msg), None
        return True, '', actor.owner

    def check_new_params(self, cmd):
        valid, msg, owner = self.check_common(cmd)
        return valid, msg, owner

    def check_del_params(self, cmd):
        valid, msg, owner = self.check_common(cmd)
        if not cmd.get('client_key'):
            return False, 'client_key parameter required.', None
        return valid, msg, owner

    def delete_client(self, cmd, anon_ch):
        valid, msg, owner = self.check_del_params(cmd)
        if not valid:
            return valid, msg
        ag = self.get_agave(cmd, owner)
        # remove the client from APIM
        ag.clients.delete(clientName=cmd['worker_id'])
        # remove the client from the abaco db
        Client.delete_client(tenant=cmd['tenant'], client_key=cmd['client_key'])




def main():
    # todo - find something more elegant
    idx = 0
    while idx < 3:
        try:
            sp = ClientGenerator()
            print("client generator made connection to rabbit, entering main loop")
            sp.run()
        except rabbitpy.exceptions.ConnectionException:
            # rabbit seems to take a few seconds to come up
            time.sleep(5)
            idx += 1


if __name__ == '__main__':
    main()
