# example actor which interacts with agave
#
# Pass parameters in through a single env var MSG as a JSON dictionary
# or as individual env vars.
#
# Requires the following:
#    source_system - agave storage system id.
#    source_path - path on the storage system to a file.
#    dest_system - system id to transfer to.
#    dest_path - path on the destination system to transfer to.
#
# Optionally, override the following:
#    compress - (default False). Whether or not to compress the source
#    client_id
#    client_secret
#    username
#    password
#    base_url
#    verify
#
# Test this image from the command line with:
#     $ docker run -it -v $(pwd):/downloads -e MSG=<> -e client_id=pwSNUsxJAokxbb89JYRsMc82xtka -e client_secret=<> -e username=jstubbs -e password=<> jstubbs/abaco_agave_test
#
import json
import os
import zipfile

from agavepy.agave import Agave


class Error(Exception):
    def __init__(self, msg = None):
        self.msg = msg

def import_data(ag, source_url, dest_system, dest_path):
    ag.files.importData(systemId=dest_system,
                        filePath=dest_path,
                        urlToIngest=source_url)

def download_file(ag, local_path, remote_path, storage_system):
    """
    Download a file from a remote path on a storage_syestem to a local path.
    """
    print("Downloading file from {}:{} to: {}".format(storage_system,
                                                   remote_path,
                                                   local_path))
    with open(local_path, 'wb') as f:
        rsp = ag.files.download(systemId=storage_system, filePath=remote_path)
        if type(rsp) == dict:
            raise Error("Error downloading file at path: " + remote_path + ", filePath:"+ remote_path + ". Response: " + str(rsp))
        for block in rsp.iter_content(1024):
            if not block:
                break
            f.write(block)
    print("File downloaded.")

def compress_file(source, dest):
    print("Compressing file to: {}".format(dest))
    with zipfile.ZipFile(dest, 'w') as myzip:
        myzip.write(source)
    print("File compressed.")

def upload_file(ag, local_path, remote_path, storage_system):
    print("Uploading file from {} to:{}, path {}".format(local_path,
                                                         storage_system,
                                                         remote_path))
    ag.files.importData(systemId=storage_system,
                        filePath=remote_path,
                        fileToUpload=open(local_path))
    print("File uploaded.")

def get_context(msg):
    context = {}
    try:
        d = json.loads(msg)
        context.update(d)
    except ValueError as e:
        pass
    context.update(os.environ)
    compress = context.get('compress', 'false')
    if compress.lower == 'true':
        compress = True
    else:
        compress = False
    context['compress'] = compress
    return context

def compress_and_transfer(ag, context):
    # source and dest system and path
    source_system = context['source_system']
    source_path = context['source_path']
    dest_system = context['dest_system']
    dest_path = context['dest_path']
    # the file name we are transfering
    name = os.path.split(source_path)[1]
    # the local path on the host to download the file to
    local_path = os.path.join('/downloads', name)
    # the local path of the zip archive
    zip_path = local_path + '.zip'
    # download the file
    download_file(ag, local_path, source_path, source_system)
    # zip the file
    compress_file(local_path, zip_path)
    # upload the file
    upload_file(ag, zip_path, dest_path, dest_system)
    # upload_file(ag, local_path, dest_zip_path, storage_system)

def get_client(context):
    username = context.get('username', 'jdoe')
    password = context.get('password', 'abcde')
    client_key = context.get('client_key', 'iVlh5I4_I6I0b3_NJE2xTUfWAdYa')
    client_secret = context.get('client_secret', 'h4qMtPMGZH7DqsbFD2mA4Ssx9B0a')
    base_url = context.get('base_url', 'https://dev.tenants.staging.agaveapi.co')
    verify = context.get('verify', 'false')
    if verify.lower == 'true':
        verify = True
    else:
        verify = False
    ag = Agave(api_server=base_url,
               username=username,
               password=password,
               client_name='agave_abaco_test',
               api_key=client_key,
               api_secret=client_secret,
               verify=verify)
    return ag

def main():
    msg = os.environ.get('MSG')
    context = get_context(msg)
    ag = get_client(context)
    if not context['compress']:
        source_url = 'agave://{}/{}'.format(context['source_system'],
                                            context['source_path'])
        import_data(ag,
                    source_url=source_url,
                    dest_path=context['dest_path'],
                    dest_system=context['dest_system'])
    else:
        compress_and_transfer(ag, context)

if __name__ == '__main__':
    main()
