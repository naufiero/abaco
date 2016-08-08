
import collections
import json

import redis
from pymongo import MongoClient

def _do_get(getter, key):
    obj = getter(key)
    if obj is None:
        raise KeyError('"{}" not found'.format(key))
    try:
        return json.loads(obj.decode('utf-8'))
    # handle non-JSON data
    except ValueError:
        return obj.decode('utf-8')


def _do_set(setter, key, value):
    obj = json.dumps(value)
    setter(key, obj.encode('utf-8'))

class StoreMutexException(Exception):
    pass


class AbstractStore(collections.MutableMapping):
    """A persitent dictionary."""

    def __getitem__(self, key):
        pass

    def __setitem__(self, key, value):
        pass

    def __delitem__(self, key):
        pass

    def __iter__(self):
        """Iterator for the keys."""
        pass

    def __len__(self):
        """Size of db."""
        pass

    def set_with_expiry(self, key, obj, ex):
        """Set `key` to `obj` with automatic expiration of `ex` seconds."""
        pass

    def update(self, key, field, value):
        "Atomic ``self[key][field] = value``."""
        pass

    def pop_field(self, key, field):
        "Atomic pop ``self[key][field]``."""
        pass

    def update_subfield(self, key, field1, field2, value):
        "Atomic ``self[key][field1][field2] = value``."""
        pass

    def getset(self, key, value):
        "Atomically: ``self[key] = value`` and return previous ``self[key]``."
        pass

    def mutex_acquire(self, key):
        """Try to use key as a mutex.
        Raise StoreMutexException if not available.
        """

        busy = self.getset(key, True)
        if busy:
            raise StoreMutexException('{} is busy'.format(key))

    def mutex_release(self, key):
        self[key] = False


class Store(AbstractStore):

    def __init__(self, host, port, db=0):
        self._db = redis.StrictRedis(host=host, port=port, db=db)

    def __getitem__(self, key):
        return _do_get(self._db.get, key)

    def __setitem__(self, key, value):
        _do_set(self._db.set, key, value)

    def __delitem__(self, key):
        self._db.delete(key)

    def __iter__(self):
        return self._db.scan_iter()

    def __len__(self):
        return self._db.dbsize()

    def set_with_expiry(self, key, obj, ex):
        """Set `key` to `obj` with automatic expiration of `ex` seconds."""
        self._db.set(key, obj, ex=ex)

    def update(self, key, field, value):
        "Atomic ``self[key][field] = value``."""

        def _update(pipe):
            cur = _do_get(pipe.get, key)
            cur[field] = value
            pipe.multi()
            _do_set(pipe.set, key, cur)

        self._db.transaction(_update, key)

    def pop_field(self, key, field):
        "Atomic pop ``self[key][field]``."""
        def _pop(pipe):
            cur = _do_get(pipe.get, key)
            value = cur.pop(field)
            pipe.multi()
            _do_set(pipe.set, key, cur)
            return value

        return self._db.transaction(_pop, key)


    def update_subfield(self, key, field1, field2, value):
        "Atomic ``self[key][field1][field2] = value``."""

        def _update(pipe):
            cur = _do_get(pipe.get, key)
            cur[field1][field2] = value
            pipe.multi()
            _do_set(pipe.set, key, cur)

        self._db.transaction(_update, key)

    def getset(self, key, value):
        "Atomically: ``self[key] = value`` and return previous ``self[key]``."

        value = self._db.getset(key, json.dumps(value).encode('utf-8'))
        if value is not None:
            return json.loads(value.decode('utf-8'))


class MongoStore(AbstractStore):

    def __init__(self, host, port, database='abaco', db='0'):
        """
        Creates an abaco `store` which maps to a single mongo
        collection within some database.
        :param host: the IP address of the mongo server.
        :param port: port of the mongo server.
        :param database: the mongo database to use for abaco.
        :param db: an integer mapping to a mongo collection within the
        mongo database.

        :return:
        """
        mongo_uri = 'mongodb://{}:{}'.format(host, port)
        self._mongo_client = MongoClient(mongo_uri)
        self._mongo_database = self._mongo_client[database]
        self._db = self._mongo_database[db]

    def __getitem__(self, key):
        result = self._db.find_one({'_id': key})
        if not result:
            raise KeyError()
        # return self._decode(result[key])
        return result[key]

    def __setitem__(self, key, value):
        # self._db.save({'_id': key, key: self._encode(value)})
        self._db.save({'_id': key, key: value})

    def __delitem__(self, key):
        self._db.delete_one({'_id': key})

    def __iter__(self):
        for cursor in self._db.find():
            yield cursor['_id']
        # return self._db.scan_iter()

    def __len__(self):
        return self._db.count()

    def _prepset(self, value):
        if type(value) is bytes:
            return value.decode('utf-8')
        return value

    def set_with_expiry(self, key, obj, ex):
        """Set `key` to `obj` with automatic expiration of `ex` seconds."""
        self._db.save({'_id': key, 'exp': ex, key: self._prepset(obj)})

    def update(self, key, field, value):
        "Atomic ``self[key][field] = value``."""
        # result = self._db.find_and_modify(query={'_id': key},
        #                          update={'$set': {'{}.{}'.format(key,field): self._encode(value)}})
        result = self._db.find_and_modify(query={'_id': key},
                                 update={'$set': {'{}.{}'.format(key,field): value}})
        if not result:
            raise KeyError()

    def pop_field(self, key, field):
        "Atomic pop ``self[key][field]``."""
        # result = self._db.find_and_modify(query={'_id': key},
        #                                   update={'$unset': {'{}.{}'.format(key, self._encode(field)): ''}})
        result = self._db.find_and_modify(query={'_id': key},
                                          update={'$unset': {'{}.{}'.format(key, field): ''}})
        result = result.get(key)
        # return self._decode(result[key])
        return result[key]

    def update_subfield(self, key, field1, field2, value):
        "Atomic ``self[key][field1][field2] = value``."""
        # self._db.update_one({'_id': key}, {'$set': {'{}.{}.{}'.format(key, field1, field2): self._encode(value)}})
        self._db.update_one({'_id': key}, {'$set': {'{}.{}.{}'.format(key, field1, field2): value}})

    def getset(self, key, value):
        "Atomically: ``self[key] = value`` and return previous ``self[key]``."
        # value = self._db.find_and_modify(query={'_id': key},
        #                                  update={key: self._encode(value)})
        value = self._db.find_and_modify(query={'_id': key},
                                         update={key: value})
        # return self._decode(value[key])
        return value[key]