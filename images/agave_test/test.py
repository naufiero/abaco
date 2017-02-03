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
import sys
import zipfile

from agavepy.actors import get_client, get_context


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

def main():
    ag = get_client()
    context = get_context()
    m = context.message_dict
    file_m = m.get('file')
    if not file_m:
        print "Not a file event."
        sys.exit()
    status = file_m['status']
    path = file_m['path']
    system_id = file_m['systemId']
    native_format = file_m['nativeFormat']
    print "Status: {} path:{} system_id:{} format:{} ".format(status, path, system_id, native_format)
    try:
        rsp = ag.files.list(systemId=system_id, filePath=path)
    except Exception as e:
        print "Got an exception trying to list files: {}".format(e)
        print "URL on the request: {}".format(e.request.url)
        print "Request headers: {}".format(e.request.headers)
        print "Request body: {}".format(e.request.body)

    print "Agave files response: {}".format(rsp)
    if status == 'STAGING_COMPLETED' or status == 'TRANSFORMING_COMPLETED':
        if native_format == 'dir':
            # new project directory, let's add our project skeleton
            ag.files.manage(systemId=system_id, filePath=path, body={'action':'mkdir', 'path': 'data'})
            ag.files.manage(systemId=system_id, filePath=path, body={'action':'mkdir', 'path': 'analysis'})
            ag.files.manage(systemId=system_id, filePath=path, body={'action':'mkdir', 'path': 'logs'})
        else:
            print "Skipping since native_format was {}, not 'dir'".format(native_format)
    else:
        print "Skipping since status was {}".format(status)

    # just try to list apps:
    # apps = ag.apps.list()
    # systems = ag.systems.list()
#    print "Context: {}".format(context)
#    print "Apps: {}".format(apps)
#    print "Systems: {}".format(systems)
#     print "message_dict: {}".format(context.message_dict)



def main_prev():
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
