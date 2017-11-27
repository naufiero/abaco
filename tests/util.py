# Utilities shared across testing modules.
import json
import os
import pytest
import requests
import time

base_url = os.environ.get('base_url', 'http://localhost:8000')
case = os.environ.get('case', 'snake')


@pytest.fixture(scope='session')
def headers():
    with open('/tests/jwt-abaco_admin', 'r') as f:
        jwt_default = f.read()
    jwt = os.environ.get('jwt', jwt_default)
    if jwt:
        jwt_header = os.environ.get('jwt_header', 'X-Jwt-Assertion-DEV-DEVELOP')
        headers = {jwt_header: jwt}
    else:
        token = os.environ.get('token', '')
        headers = {'Authorization': 'Bearer {}'.format(token)}
    return headers

def test_remove_initial_actors(headers):
    url = '{}/actors'.format(base_url)
    rsp = requests.get(url, headers=headers)
    result = basic_response_checks(rsp)
    for act in result:
        url = '{}/actors/{}'.format(base_url, act.get('id'))
        rsp = requests.delete(url, headers=headers)
        basic_response_checks(rsp)

def get_actor_id(headers, name='abaco_test_suite'):
    url = '{}/{}'.format(base_url, '/actors')
    rsp = requests.get(url, headers=headers)
    result = basic_response_checks(rsp)
    for k in result:
        if k.get('name') == name:
            return k.get('id')
    # didn't find the test actor
    assert False

def response_format(rsp):
    assert 'application/json' in rsp.headers['content-type']
    data = json.loads(rsp.content.decode('utf-8'))
    assert 'message' in data.keys()
    assert 'status' in data.keys()
    assert 'version' in data.keys()

def basic_response_checks(rsp, check_tenant=True):
    assert rsp.status_code in [200, 201]
    response_format(rsp)
    data = json.loads(rsp.content.decode('utf-8'))
    assert 'result' in data.keys()
    result = data['result']
    if check_tenant:
        if result is not None:
            assert 'tenant' not in result
    return result


def check_execution_details(result, actor_id, exc_id):
    if case == 'snake':
        assert result.get('actor_id') == actor_id
        assert 'worker_id' in result
        assert 'exit_code' in result
        assert 'final_state' in result
        assert 'message_received_time' in result
        assert 'start_time' in result
    else:
        assert result.get('actorId') == actor_id
        assert 'workerId' in result
        assert 'exitCode' in result
        assert 'finalState' in result
        assert 'messageReceivedTime' in result
        assert 'startTime' in result

    assert result.get('id') == exc_id
    # note: it is possible for io to be 0 in which case an `assert result['io']` will fail.
    assert 'io' in result
    assert 'runtime' in result


def execute_actor(headers, actor_id, data=None, json_data=None, binary=None):
    url = '{}/actors/{}/messages'.format(base_url, actor_id)
    #
    # actor_id = get_actor_id(headers)
    # data = {'message': 'testing execution'}
    if data:
        rsp = requests.post(url, data=data, headers=headers)
    elif json:
        rsp = requests.post(url, json=json_data, headers=headers)
    elif binary:
        rsp = requests.post(url, data=binary, headers=headers)
    else:
        raise Exception # invalid
    result = basic_response_checks(rsp)
    if data:
        assert data.get('message') in result.get('msg')
    if case == 'snake':
        assert result.get('execution_id')
        exc_id = result.get('execution_id')
    else:
        assert result.get('executionId')
        exc_id = result.get('executionId')
    # check for the execution to complete
    count = 0
    while count < 10:
        time.sleep(3)
        url = '{}/actors/{}/executions'.format(base_url, actor_id)
        rsp = requests.get(url, headers=headers)
        result = basic_response_checks(rsp)
        ids = result.get('ids')
        if ids:
            assert exc_id in ids
        url = '{}/actors/{}/executions/{}'.format(base_url, actor_id, exc_id)
        rsp = requests.get(url, headers=headers)
        result = basic_response_checks(rsp)
        status = result.get('status')
        assert status
        if status == 'COMPLETE':
            check_execution_details(result, actor_id, exc_id)
            return result
        count += 1
    assert False

