from channelpy import Channel


class Spawner(object):

    def __init__(self):
        self.ch = Channel(name='command')

    def run(self):
        while True:
            cmd = self.ch.get()
            self.process(cmd)

    def process(self, cmd):
        actor_id = cmd['actor_id']
        image = cmd['image']
        new_channels, new_workers = self.start_workers(actor_id, image)
        workers = workers_store[actor_id]
        # { w_1: { image: .., location: .., channel: .. }, w_2: ... }
        channels = []

        for worker in workers.values():
            ch = Channel(name=worker['channel'])
            ch.put('stop')
            channels.append(ch)

        for channel in channels:
            channel.get(timeout=10)

        for channel in new_channels:
            channel.put('start')

        workers_store[actor_id] = new_workers

    def start_workers(self, actor_id, image):
        channels = []
        workers = []
        try:
            for i in range(self.num_workers):
                ch, worker = self.start_worker(actor_id, image)
                channels.append(ch)
                workers.append(worker)
        except Exception:
            for worker in workers:
                kill(worker)
            return
        return channels, workers

    def start_worker(self, actor_id, image):
        ch = Channel()
        worker = self.schedule_to_run(image, ch._name)
        result = ch.get()
        if result['status'] == 'ok':
            return ch, worker
        else:
            raise Exception()


def main():
    pass


if __name__ == '__main__':
    main()
