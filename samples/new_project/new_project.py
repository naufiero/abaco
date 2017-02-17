import sys
from agavepy.actors import get_client, get_context


def add_project(ag, path, system_id):
    ag.files.manage(systemId=system_id, filePath=path, body={'action':'mkdir', 'path': 'data'})
    ag.files.manage(systemId=system_id, filePath=path, body={'action':'mkdir', 'path': 'analysis'})
    ag.files.manage(systemId=system_id, filePath=path, body={'action':'mkdir', 'path': 'images'})


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
    if status == 'STAGING_COMPLETED' or status == 'TRANSFORMING_COMPLETED':
        native_format = file_m['nativeFormat']
        if native_format == 'dir':
            # new project directory, let's add our project skeleton
            path = file_m['path']
            system_id = file_m['systemId']
            add_project(ag, path, system_id)
        else:
            print "Skipping since native_format was {}, not 'dir'".format(native_format)
    else:
        print "Skipping since status was {}".format(status)


if __name__ == '__main__':
    main()
