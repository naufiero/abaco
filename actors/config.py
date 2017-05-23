"""Read config files from:
- /abaco.conf (added by user)
- /etc/abaco.conf (an example is placed here by the Dockerfile)

"""

from configparser import ConfigParser
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def read_config():
    parser = ConfigParser()
    places = ['/service.conf',
              '/etc/service.conf']
    place = places[0]
    for p in places:
        if os.path.exists(p):
            place = p
            break
    if not parser.read(place):
        raise RuntimeError("couldn't read config file; tried these places: {0}"
                           .format(', '.join(places)))
    return parser

Config = read_config()