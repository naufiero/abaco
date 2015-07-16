import sys

from channelpy import Channel

from .config import Config
from .docker import pull_image

class Worker(object):

    pass


def main(ch, image):
    err = pull_image(image)
    if err:
        ch.put({'status': err})
    else:
        ch.put({'status': 'ok'})
    ch.get()  # <- start
    subscribe()
    main(ch, image)

    pass


if __name__ == '__main__':
    ch_name = sys.argv[1]
    image = sys.argv[2]
    uri = Config.get('rabbit', 'uri')
    ch = Channel(name=ch_name, uri=uri)
    main(ch, image)
