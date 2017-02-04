from functools import partial

from store import RedisStore, MongoStore
from config import Config


# redis is used for actor and worker run time state for its speed and transactional semantics.
redis_config_store = partial(
    RedisStore, Config.get('store', 'redis_host'), Config.getint('store', 'redis_port'))

actors_store = redis_config_store(db='1')
workers_store = redis_config_store(db='2')


# Mongo is used for accounting, permissions and logging data for its scalability.
mongo_config_store = partial(
    MongoStore, Config.get('store', 'mongo_host'), Config.getint('store', 'mongo_port'))

logs_store = mongo_config_store(db='1')
permissions_store = mongo_config_store(db='2')
executions_store = mongo_config_store(db='3')
clients_store = mongo_config_store(db='4')
