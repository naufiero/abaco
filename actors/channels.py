from channelpy import Channel

from config import Config


class WorkerChannel(Channel):
    """Channel for communication with a worker. Pass the name of the worker to communicate with an
    existing worker.
    """
    def __init__(self, name=None):
        self.uri = Config.get('rabbit', 'uri')
        super().__init__(name, uri=self.uri)


class CommandChannel(Channel):
    """Work with commands on the command channel.
    """

    def __init__(self):
        self.uri = Config.get('rabbit', 'uri')
        super().__init__(name='command', uri=self.uri)

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
        super().__init__(name='actor_msg_{}'.format(actor_id), uri=self.uri)

    def put_msg(self, msg):
        self.put({'msg': msg})
