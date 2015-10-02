import collections

import redis


class Store(collections.MutableMapping):

    def __init__(self, host, port, db=0):
        self._db = redis.StrictRedis(host=host, port=port, db=db, decode_responses=True)

    def __getitem__(self, key):
        obj = self._db.get(key)
        if obj is None:
            raise KeyError('"{}" not found'.format(key))
        return obj

    def __setitem__(self, key, value):
        obj = value
        self._db.set(key, obj)

    def __delitem__(self, key):
        self._db.delete(key)

    def __iter__(self):
        return self._db.scan_iter()

    def __len__(self):
        return self._db.dbsize()

    def transaction(self, callable, *args):
        """ Convenience wrapper around redis-py transaction. See the Pipelines section of the docs:
        https://github.com/andymccurdy/redis-py
        """
        self._db.transaction(callable, args)