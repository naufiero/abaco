# An example abaco actor that reads a

import os
import requests

# agave client information
username = os.environ.get('username', 'jdoe')
password = os.environ.get('password', 'abcde')
client_key = os.environ.get('client_key', 'iVlh5I4_I6I0b3_NJE2xTUfWAdYa')
client_secret = os.environ.get('client_secret', 'h4qMtPMGZH7DqsbFD2mA4Ssx9B0a')
base_url = os.environ.get('base_url', 'https://public.tenants.prod.agaveapi.co')


def get_token():
    url = '{}/token'.format(base_url)
    data={'username': username,
          'password': password,
          'scope': 'PRODUCTION',
          'grant_type': 'password'}
    rsp = requests.post(url, data=data)
    try:
        token = rsp.json.get('access_token')
    except Exception as e:
        print("Got an exception trying to retrieve an access token: {}".format(e))
    return token

def transfer_file(token):
    source_system = ''
    dest_system = ''
    print("Transfering file from {} to {}...".format(source_system, dest_system))

def main():
    msg = os.environ.get('MSG')
    print('transfer container running for MSG: {}'.format(msg))
    token = get_token()
    transfer_file(token)

if __name__ == '__main__':
    main()