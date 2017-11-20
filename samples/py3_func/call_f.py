import os
import cloudpickle

def main():
    fifo = open('/_abaco_binary_data', 'rb')
    raw_message = fifo.read()
    fifo.close()
    try:
        m = cloudpickle.loads(raw_message)
    except Exception as e:
        print("Got exception: {} trying to loads raw_message: {}. raw_message: {}".format(e, raw_message))
        raise e
    print("Was able to execute cloudpickle.loads: {}".format(m))
    f = m.get('func')
    if not f:
        print("Error - function attribute required. Got: {}".format(m))
        raise Exception
    args = m.get('args')
    kwargs = m.get('kwargs')
    try:
        result = f(*args, **kwargs)
    except Exception as e:
        print("Got exception trying to call f: {}. Exception: {}".format(f, e))

    print("result: {}".format(result))

if __name__ == '__main__':
    main()
