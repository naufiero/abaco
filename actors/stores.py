from functools import partial

from store import Store
from config import Config


config_store = partial(
    Store, Config.get('store', 'host'), Config.getint('store', 'port'))

actors_store = config_store(db=1)
