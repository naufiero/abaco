"""
Module to test implementation of cleanup code in Abaco attempting to clean up RabbitMQ channel and connection
objects.

Usage:
1. Start a testsuite container in interactive mode:
$ docker run -it -e case=camel -e base_url=http://172.17.0.1:8000 -v $(pwd)/local-dev.conf:/etc/service.conf --rm --entrypoint=bash abaco/testsuite:dev

2. Start the test program
bash-4.3# python3 /tests/rabbit_abaco_tests.py

3. Watch the http://localhost:15672/#/queues and http://localhost:15672/#/connections
"""
import os
import sys
import time

import requests

from util import base_url, case, headers, basic_response_checks


# whether to first delete the workers before deleting the actor.
FIRST_DELETE_WORKERS = os.environ.get('FIRST_DELETE_WORKERS', "True")

print("rabbit_abaco_tests running with: {}. {}. {}".format(base_url, case, FIRST_DELETE_WORKERS))


def basic_test():
    # create an actor
    url = '{}/actors'.format(base_url)
    data = {'image': 'abacosamples/test'}
    rsp = requests.post(url, data=data, headers=headers())
    result = basic_response_checks(rsp)
    aid = result['id']
    print("created actor {}".format(aid))

    # send a message
    url = '{}/actors/{}/messages'.format(base_url, aid)
    data = {'message': 'test'}
    rsp = requests.post(url, data=data, headers=headers())
    result = basic_response_checks(rsp)
    if case == 'snake':
        eid = result.get('execution_id')
    else:
        eid = result.get('executionId')
    print("got execution: {}".format(eid))

    # wait for execution to complete:
    count = 0
    while count < 10:
        time.sleep(1)
        url = '{}/actors/{}/executions/{}'.format(base_url, aid, eid)
        rsp = requests.get(url, headers=headers())
        result = basic_response_checks(rsp)
        status = result.get('status')
        if status == 'COMPLETE':
            print("execution complete")
            break
    else:
        print("execution didn't complete. exiting")
        sys.exit()

    # delete workers first, if configured:
    if FIRST_DELETE_WORKERS == 'True':
        print("deleting worker.")
        url = '{}/actors/{}/workers'.format(base_url, aid)
        rsp = requests.get(url, headers=headers())
        result = basic_response_checks(rsp)
        wid = result[0]['id']
        url = '{}/actors/{}/workers/{}'.format(base_url, aid, wid)
        rsp = requests.delete(url, headers=headers())
        basic_response_checks(rsp)
        print("worker {} deleted.".format(wid))
        time.sleep(1.5)
    else:
        print("not deleting worker first.")
    # delete actor
    print("deleting actor {}.".format(aid))
    url = '{}/actors/{}'.format(base_url, aid)
    rsp = requests.delete(url, headers=headers())
    basic_response_checks(rsp)
    print("deleted actor: {}.".format(aid))


if __name__ == '__main__':
    tot = 1
    while True:
        print("launching actor: {}".format(tot))
        basic_test()
        time.sleep(1)
        tot += 1