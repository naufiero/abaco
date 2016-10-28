"""
Process to generate Agave clients for workers.
"""

import os
import time
import rabbitpy

from agave import Agave
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
            self.credentials[tenant] = {'username': os.environ.get('_abaco_{}_username'.format(tenant), ''),
                                        'password': os.environ.get('_abaco_{}_password'.format(tenant), '')}

    def get_agave(self, tenant, actor_owner):
        """
        Generate an agavepy client representing a specific user owning an actor.
        The `actor_owner` should be the username associated with the owner of the actor.
        """
        # these are the credentials of the abaco service account. this account should have the abaco and
        # impersonator roles.
        username = self.credentials[tenant.upper()]['username']
        password = self.credentials[tenant.upper()]['password']
        if username == '' or password == '':
            raise ClientException('Client service credentials not defined for tenant {}'.format(tenant))
        api_server = get_api_server(tenant)
        # generate an Agave client set up for admin_password representing the actor owner:
        return api_server,\
               Agave(api_server=api_server, username=username, password=password, token_username=actor_owner)


    def run(self):
        """
        Listen to the clients channel for new client and deletion requests. Requests use the put_sync method
        to send an anonymous channel together with the actual client request command.
        """
        while True:
            message = self.ch.get()
            print("cleintg processing message: {}".format(message))
            anon_ch = message['reply_to']
            cmd = message['value']
            print("cleintg processing cmd: {}".format(cmd))
            if cmd.get('command') == 'new':
                self.new_client(cmd, anon_ch)
            elif cmd.get('command') == 'delete':
                self.delete_client(cmd, anon_ch)
            else:
                anon_ch.put({'status': 'error',
                             'message': 'Received invalid command: {}'.format(cmd.get('command'))})

    def new_client(self, cmd, anon_ch):
        valid, msg, owner = self.check_new_params(cmd)
        if valid:
            try:
                api_server, key, secret, access_token, refresh_token = self.generate_client(cmd, owner)
            except ClientException as e:
                ch = ClientsChannel(name=anon_ch)
                ch.put({'status': 'error',
                        'message': e.msg})
                return None
            cl = Client(**{'tenant': cmd['tenant'],
                           'actor_id': cmd['actor_id'],
                           'worker_id': cmd['worker_id'],
                           'client_key': key,
                           'client_name': cmd['worker_id'],
                         })
            clients_store[cl.id] = cl
            self.send_client(api_server, key, secret, access_token, refresh_token, anon_ch)
        else:
            anon_ch.put({'status': 'error',
                         'message': 'Invalid command parameters: {}'.format(msg)})

    def generate_client(self, cmd, owner):
        api_server, ag = self.get_agave(cmd['tenant'], actor_owner=owner)
        ag.clients.create(body={'clientName': cmd['worker_id']})
        # note - the client generates tokens representing the user who registered the actor
        return api_server,\
               ag.api_key, \
               ag.api_secret, \
               ag.token.token_info['access_token'], \
               ag.token.token_info['refresh_token']


    def send_client(self, api_server, client_id, client_secret, access_token, refresh_token, anon_ch):
        """Send client credentials to a worker on an anonymous channel."""
        msg = {'status': 'ok',
               'api_server': api_server,
               'client_id': client_id,
               'client_secret': client_secret,
               'access_token': access_token,
               'refresh_token': refresh_token}
        anon_ch.put(msg)

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
        return True, '', actor.owner

    def check_new_params(self, cmd):
        valid, msg, owner = self.check_common(cmd)
        # validate the worker id
        try:
            Worker.get_worker(actor_id=cmd.get('actor_id'), ch_name=cmd.get('worker_id'))
        except WorkerException as e:
            return False, "Unable to look up worker: {}".format(e.msg), None
        return valid, msg, owner

    def check_del_params(self, cmd):
        valid, msg, owner = self.check_common(cmd)
        if not cmd.get('client_id'):
            return False, 'client_id parameter required.', None
        return valid, msg, owner

    def delete_client(self, cmd, anon_ch):
        valid, msg, owner = self.check_del_params(cmd)
        if not valid:
            anon_ch.put({'status': 'error',
                         'message': 'Invalid parameters sent: {}'.format(msg)})
            return None
        try:
            _, ag = self.get_agave(cmd['tenant'], owner)
        except ClientException as e:
            anon_ch.put({'status': 'error',
                         'message': 'Could not generate an Agave clientt: {}'.format(e)})
            return None
        # remove the client from APIM
        try:
            ag.clients.delete(clientName=cmd['worker_id'])
        except Exception as e:
            anon_ch.put({'status': 'error',
                        'message': 'Not able to delete client from APIM. Exception: {}'.format(e)})
            return None
        # remove the client from the abaco db
        try:
            Client.delete_client(tenant=cmd['tenant'], client_key=cmd['client_key'])
        except Exception as e:
            anon_ch.put({'status': 'error',
                        'message': 'Not able to delete client from abaco db. Exception: {}'.format(e)})
            return None
        anon_ch.put({'status': 'ok',
                     'message': 'Client deleted.'})


def main():
    # todo - find something more elegant
    idx = 0
    while idx < 3:
        try:
            client_gen = ClientGenerator()
            print("client generator made connection to rabbit, entering main loop")
            client_gen.run()
        except rabbitpy.exceptions.ConnectionException:
            # rabbit seems to take a few seconds to come up
            time.sleep(5)
            idx += 1


if __name__ == '__main__':
    main()
