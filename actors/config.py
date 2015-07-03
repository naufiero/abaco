"""Read config files from:
- Deployed abaco.conf inside package
- /etc/abaco.conf
"""

from configparser import ConfigParser
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def read_config():
    parser = ConfigParser()
    places = [os.path.abspath(os.path.join(HERE, '../abaco.conf')),
              os.path.expanduser('/etc/abaco.conf')]
    if not parser.read(places):
        raise RuntimeError("couldn't read config file from {0}"
                           .format(', '.join(places)))
    return parser

Config = read_config()