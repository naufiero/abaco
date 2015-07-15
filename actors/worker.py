

class Worker(object):

    pass


def main():
    pass


if __name__ == '__main__':
    ch_name = sys.argv[1]
    image = sys.argv[2]
    ch = Channel(name=ch_name)
    err = docker_pull(image)
    if err:
        ch.put({'status': err})
    else:
        ch.put({'status': 'ok'})
    ch.get()  # <- start
    subscribe()
    main(ch, image)
