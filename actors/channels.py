from channelpy import Channel, RabbitConnection

from config import Config


class WorkerChannel(Channel):
    """Channel for communication with a worker. Pass the name of the worker to communicate with an
    existing worker.
    """
    def __init__(self, name=None):
        self.uri = Config.get('rabbit', 'uri')
        super().__init__(name=name,
                         connection_type=RabbitConnection,
                         uri=self.uri)


class CommandChannel(Channel):
    """Work with commands on the command channel.
    """

    def __init__(self):
        self.uri = Config.get('rabbit', 'uri')
        super().__init__(name='command',
                         connection_type=RabbitConnection,
                         uri=self.uri)

    def put_cmd(self, actor_id, image, num=None, stop_existing=True):
        """Put a new command on the command channel."""
        msg = {'actor_id': actor_id, 'image': image, 'stop_existing': stop_existing}
        if num:
            msg['num'] = num
        self.put(msg)


class ActorMsgChannel(Channel):
    """Work with messages sent to a specific actor.
    """
    def __init__(self, actor_id):
        self.uri = Config.get('rabbit', 'uri')
        super().__init__(name='actor_msg_{}'.format(actor_id),
                         connection_type=RabbitConnection,
                         uri=self.uri)

    def put_msg(self, message, d={}, **kwargs):
        """Pass a message to an actor's inbox, thereby invoking it. `message` is the request
        body msg parameter; `d` is a dictionary built from the request query parameters;
        additional metadata (e.g. jwt, username) can be passed through kwargs.
        """
        d['message'] = message
        for k, v in kwargs:
            d[k] = v
        self.put(d)
