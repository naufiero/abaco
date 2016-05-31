from functools import partial

from store import Store
from config import Config


config_store = partial(
    Store, Config.get('store', 'host'), Config.getint('store', 'port'))

actors_store = config_store(db=1)
workers_store = config_store(db=2)
logs_store = config_store(db=3)
permissions_store = config_store(db=4)
executions_store = config_store(db=5)