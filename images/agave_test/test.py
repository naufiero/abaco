# example actor which interacts with agave
#
# Requires the following in the MSG dictionary:
#    system - agave storage system id
#    path - path on the storage system to a file
#
# Also requires the following environmental vars:
#    client_id
#    client_secret
#    username
#    password
#
# Test this image from the command line with:
#     $ docker run -it -e MSG=<> -e client_id=pwSNUsxJAokxbb89JYRsMc82xtka -e client_secret=<> -e username=jstubbs -e password=<> jstubbs/abaco_agave_test
#
import json
import os
import zipfile

from agavepy.agave import Agave


class Error(Exception):
    def __init__(self, msg = None):
        self.msg = msg


def download_file(ag, local_path, remote_path, storage_system):
    """
    Download a file from a remote path on a storage_syestem to a local path
    :param ag:
    :param path:
    :param storage_system:
    :return:
    """
    with open(local_path, 'wb') as f:
        rsp = ag.files.download(systemId=storage_system, filePath=remote_path)
        if type(rsp) == dict:
            raise Error("Error downloading file at path: " + remote_path + ", filePath:"+ remote_path + ". Response: " + str(rsp))
        for block in rsp.iter_content(1024):
            if not block:
                break
            f.write(block)

def compress_file(source, dest):
    with zipfile.ZipFile(dest, 'w') as myzip:
        myzip.write(source)



def upload_file(ag, local_path, remote_path, storage_system):
    ag.files.importData(systemId=storage_system,
                        filePath=remote_path,
                        fileToUpload=open(local_path,'rb'))

def do_work(ag, msg):
    try:
        d = json.loads(msg)
    except ValueError as e:
        print("Unable to parse msg. msg: {}, exception:{}".format(msg, e))
        return
    # the storage system to retrieve the file from
    storage_system = d.get('system')
    # the remote path on the storage system to download
    remote_path = d.get('path')
    # the file name we are downloading
    name = os.path.split(remote_path)[1]
    # the local path on the host to download the file to
    local_path = os.path.join(os.getcwd(), name)
    # the local path of the zip archive
    zip_path = local_path + '.zip'
    # the full path on the remote system to the new zip file
    dest_zip_path = os.path.split(remote_path)[0] + name + '.zip'

    # download the file
    download_file(ag, local_path, remote_path, storage_system)

    # zip the file
    compress_file(local_path, zip_path)

    # upload the file
    upload_file(ag, zip_path, dest_zip_path, storage_system)

def main():
    client_key = os.environ.get('client_key')
    client_secret = os.environ.get('client_secret')
    username = os.environ.get('username')
    password = os.environ.get('password')

    ag = Agave(api_server='https://api.tacc.utexas.edu',
               username=username,
               password=password,
               client_name='my_client',
               api_key=client_key,
               api_secret=client_secret)

    msg = os.environ.get('MSG')

    do_work(ag, msg)

if __name__ == '__main__':
    main()
