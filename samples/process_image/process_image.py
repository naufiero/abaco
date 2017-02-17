import sys
from agavepy.actors import get_client, get_context

def download_input(ag, path, system_id):
    """Download rhw remote file locally to a file `data` in cwd."""
    with open('data', 'wb') as f:
        rsp = ag.files.download(systemId=system_id, filePath=path)
        if type(rsp) == dict:
            print "Error downloading file, got dict response: {}".format(rsp)
            return None
        for block in rsp.iter_content(1024):
            if not block:
                break
            f.write(block)
    return 'data'

def process():
    """Process the downloaded file."""

def upload_result(ag, path, system_id, output):
    """Upload the output to remote storage."""
    ag.files.importData(systemId=system_id,
                        filePath=path,
                        fileToUpload=open(output))

def process_image(ag, path, system_id):
    result = download_input(ag, path, system_id)
    if not result:
        return
    output = process()
    if output:
        upload_result(ag, path, system_id, output)

def main():
    ag = get_client()
    context = get_context()
    m = context.message_dict
    print "new_project actor running for message: {}".format(m)
    file_m = m.get('file')
    if not file_m:
        print "Not a file event."
        sys.exit()
    status = file_m.get('status')
    if status == 'STAGING_COMPLETED':
        native_format = file_m['nativeFormat']
        if native_format == 'raw':
            path = file_m['path']
            system_id = file_m['systemId']
            process_image(ag, path, system_id)
        else:
            print "Skipping since native_format was {}, not 'raw'".format(native_format)
    else:
        print "Skipping since status was {}".format(status)


if __name__ == '__main__':
    main()
