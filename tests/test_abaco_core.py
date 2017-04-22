# Functional test suite for abaco.
# This test suite now runs in its own docker container. To build the image, run
#     docker build -f Dockerfile-test -t jstubbs/abaco_testsuite .
# from within the tests directory.
#
# To run the tests execute, first start the development stack using:
#  1. export abaco_path=$(pwd)
#  2. docker-compose -f docker-compose-local-db.yml up -d (from within the root directory)
#  3. docker-compose -f docker-compose-local.yml up -d (from within the root directory)
# Then, also from the root directory, execute:
#     docker run -e base_url=http://172.17.0.1:8000 -e case=camel -v $(pwd)/local-dev.conf:/etc/abaco.conf -it --rm jstubbs/abaco_testsuite
# Change the -e case=camel to -e case=snake depending on the functionality you want to test.

#
# # --- Original notes for running natively ------
# Start the local development abaco stack (docker-compose-local.yml) and run these tests with py.test from the cwd.
#     $ py.test test_abaco_core.py
#
# Notes:
# 1. Running the tests against the docker-compose-local.yml instance (using local-dev.conf) will use an access_control
#    of none and the tenant configured in local-dev.conf (dev_staging) for all requests (essentially ignore headers).
#
# 2. With access control of type 'none'. abaco reads the tenant from a header "tenant" if present. If not present, it
#    uses the default tenant configured in the abaco.conf file.
#
# 3. most tests appear twice, e.g. "test_list_actors" and "test_tenant_list_actors": The first test uses the default
#    tenant by not setting the tenant header, while the second one sets tenant: abaco_test_suite_tenant; this enables
#    the suite to test tenancy bleed-over.
#
import ast
import os
import sys
sys.path.append(os.path.split(os.getcwd())[0])
sys.path.append('/actors')
import time

import pytest
import requests
import json

from actors import models

base_url = os.environ.get('base_url', 'http://localhost:8000')
case = os.environ.get('case', 'snake')

# #################
# registration API
# #################

@pytest.fixture(scope='session')
def headers():
    jwt = os.environ.get('jwt', open('/tests/jwt').read())
    if jwt:
        jwt_header = os.environ.get('jwt_header', 'X-Jwt-Assertion-AGAVE-PROD')
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

def basic_response_checks(rsp, check_tenant=True):
    assert rsp.status_code in [200, 201]
    assert 'application/json' in rsp.headers['content-type']
    data = json.loads(rsp.content.decode('utf-8'))
    assert 'message' in data.keys()
    assert 'status' in data.keys()
    assert 'result' in data.keys()
    assert 'version' in data.keys()
    result = data['result']
    if check_tenant:
        if result is not None:
            assert 'tenant' not in result
    return result


def test_dict_to_camel():
    dic = {"_links": {"messages": "http://localhost:8000/actors/v2/ca39fac2-60a7-11e6-af60-0242ac110009-059/messages",
                      "owner": "http://localhost:8000/profiles/v2/anonymous",
                      "self": "http://localhost:8000/actors/v2/ca39fac2-60a7-11e6-af60-0242ac110009-059/executions/458ab16c-60a8-11e6-8547-0242ac110008-053"
    },
           "execution_id": "458ab16c-60a8-11e6-8547-0242ac110008-053",
           "msg": "test"
    }
    dcamel = models.dict_to_camel(dic)
    assert 'executionId' in dcamel
    assert dcamel['executionId'] == "458ab16c-60a8-11e6-8547-0242ac110008-053"

def test_list_actors(headers):
    url = '{}/{}'.format(base_url, '/actors')
    rsp = requests.get(url, headers=headers)
    result = basic_response_checks(rsp)
    assert len(result) == 0

def test_list_nonexistent_actor(headers):
    url = '{}/{}'.format(base_url, '/actors/bad_actor_id')
    rsp = requests.get(url, headers=headers)
    assert rsp.status_code == 404
    data = json.loads(rsp.content.decode('utf-8'))
    assert data['status'] == 'error'

def test_cors_list_actors(headers):
    url = '{}/{}'.format(base_url, '/actors')
    headers['Origin'] = 'http://example.com'
    rsp = requests.get(url, headers=headers)
    basic_response_checks(rsp)
    assert 'Access-Control-Allow-Origin' in rsp.headers

def test_cors_options_list_actors(headers):
    url = '{}/{}'.format(base_url, '/actors')
    headers['Origin'] = 'http://example.com'
    headers['Access-Control-Request-Method'] = 'POST'
    headers['Access-Control-Request-Headers'] = 'X-Requested-With'
    rsp = requests.options(url, headers=headers)
    assert rsp.status_code == 200
    assert 'Access-Control-Allow-Origin' in rsp.headers
    assert 'Access-Control-Allow-Methods' in rsp.headers
    assert 'Access-Control-Allow-Headers' in rsp.headers

def test_register_actor(headers):
    url = '{}/{}'.format(base_url, '/actors')
    data = {'image': 'jstubbs/abaco_test', 'name': 'abaco_test_suite'}
    rsp = requests.post(url, data=data, headers=headers)
    result = basic_response_checks(rsp)
    assert 'description' in result
    assert 'owner' in result
    # assert result['owner'] == 'jstubbs'
    assert result['image'] == 'jstubbs/abaco_test'
    assert result['name'] == 'abaco_test_suite'
    assert result['id'] is not None

def test_register_stateless_actor(headers):
    url = '{}/{}'.format(base_url, '/actors')
    data = {'image': 'jstubbs/abaco_test', 'name': 'abaco_test_suite_statelesss', 'stateless': True}
    rsp = requests.post(url, data=data, headers=headers)
    result = basic_response_checks(rsp)
    assert 'description' in result
    assert 'owner' in result
    # assert result['owner'] == 'jstubbs'
    assert result['image'] == 'jstubbs/abaco_test'
    assert result['name'] == 'abaco_test_suite_statelesss'
    assert result['id'] is not None

def get_actor_id(headers, name='abaco_test_suite'):
    url = '{}/{}'.format(base_url, '/actors')
    rsp = requests.get(url, headers=headers)
    result = basic_response_checks(rsp)
    for k in result:
        if k.get('name') == name:
            return k.get('id')
    # didn't find the test actor
    assert False

def test_list_actor(headers):
    actor_id = get_actor_id(headers)
    url = '{}/actors/{}'.format(base_url, actor_id)
    rsp = requests.get(url, headers=headers)
    result = basic_response_checks(rsp)
    assert 'description' in result
    assert 'owner' in result
    assert result['image'] == 'jstubbs/abaco_test'
    assert result['name'] == 'abaco_test_suite'
    assert result['id'] is not None

def test_list_actor_state(headers):
    actor_id = get_actor_id(headers)
    url = '{}/actors/{}/state'.format(base_url, actor_id)
    rsp = requests.get(url, headers=headers)
    result = basic_response_checks(rsp)
    assert 'state' in result

def test_update_actor_state_string(headers):
    actor_id = get_actor_id(headers)
    url = '{}/actors/{}/state'.format(base_url, actor_id)
    rsp = requests.post(url, headers=headers, data={'state': 'abc'})
    result = basic_response_checks(rsp)
    assert 'state' in result
    assert result['state'] == 'abc'

def test_update_actor_state_dict(headers):
    actor_id = get_actor_id(headers)
    url = '{}/actors/{}/state'.format(base_url, actor_id)
    # update the state
    rsp = requests.post(url, headers=headers, json={'state': {'foo': 'abc', 'bar': 1, 'baz': True}})
    result = basic_response_checks(rsp)
    # retrieve the actor's state:
    rsp = requests.get(url, headers=headers)
    result = basic_response_checks(rsp)
    assert 'state' in result
    assert ast.literal_eval(result['state']) == {'foo': 'abc', 'bar': 1, 'baz': True}

def test_cant_update_stateless_actor_state(headers):
    actor_id = get_actor_id(headers, name='abaco_test_suite_statelesss')
    url = '{}/actors/{}/state'.format(base_url, actor_id)
    rsp = requests.post(url, headers=headers, data={'state': 'abc'})
    assert rsp.status_code not in range(1-399)

def test_actor_is_ready(headers):
    count = 0
    actor_id = get_actor_id(headers)
    while count < 10:
        url = '{}/actors/{}'.format(base_url, actor_id)
        rsp = requests.get(url, headers=headers)
        result = basic_response_checks(rsp)
        if result['status'] == 'READY':
            return
        time.sleep(3)
        count += 1
    assert False

def test_executions_empty_list(headers):
    actor_id = get_actor_id(headers)
    url = '{}/actors/{}/executions'.format(base_url, actor_id)
    rsp = requests.get(url, headers=headers)
    result = basic_response_checks(rsp)
    assert 'ids' in result
    assert len(result['ids']) == 0

# ###################
# executions and logs
# ###################

def test_list_executions(headers):
    actor_id = get_actor_id(headers)
    url = '{}/actors/{}/executions'.format(base_url, actor_id)
    rsp = requests.get(url, headers=headers)
    result = basic_response_checks(rsp)
    assert len(result.get('ids')) == 0

def test_list_messages(headers):
    actor_id = get_actor_id(headers)
    url = '{}/actors/{}/messages'.format(base_url, actor_id)
    rsp = requests.get(url, headers=headers)
    result = basic_response_checks(rsp)
    assert result.get('messages') == 0

def test_cors_list_messages(headers):
    actor_id = get_actor_id(headers)
    url = '{}/actors/{}/messages'.format(base_url, actor_id)
    headers['Origin'] = 'http://example.com'
    rsp = requests.get(url, headers=headers)
    basic_response_checks(rsp)
    assert 'Access-Control-Allow-Origin' in rsp.headers

def test_cors_options_list_messages(headers):
    actor_id = get_actor_id(headers)
    url = '{}/actors/{}/messages'.format(base_url, actor_id)
    headers['Origin'] = 'http://example.com'
    headers['Access-Control-Request-Method'] = 'POST'
    headers['Access-Control-Request-Headers'] = 'X-Requested-With'
    rsp = requests.options(url, headers=headers)
    assert rsp.status_code == 200
    assert 'Access-Control-Allow-Origin' in rsp.headers
    assert 'Access-Control-Allow-Methods' in rsp.headers
    assert 'Access-Control-Allow-Headers' in rsp.headers

def check_execution_details(result, actor_id, exc_id):
    if case == 'snake':
        assert result.get('actor_id') == actor_id
        assert 'worker_id' in result
        assert 'exit_code' in result
        assert 'final_state' in result
    else:
        assert result.get('actorId') == actor_id
        assert 'workerId' in result
        assert 'exitCode' in result
        assert 'finalState' in result

    assert result.get('id') == exc_id
    # note: it is possible for io to be 0 in which case an `assert result['io']` will fail.
    assert 'io' in result
    assert 'runtime' in result


def test_execute_actor(headers):
    actor_id = get_actor_id(headers)
    url = '{}/actors/{}/messages'.format(base_url, actor_id)
    data = {'message': 'testing execution'}
    rsp = requests.post(url, data=data, headers=headers)
    result = basic_response_checks(rsp)
    assert result.get('msg')  == 'testing execution'
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
            return
        count += 1
    assert False

def test_list_execution_details(headers):
    actor_id = get_actor_id(headers)
    # get execution id
    url = '{}/actors/{}/executions'.format(base_url, actor_id)
    rsp = requests.get(url, headers=headers)
    result = basic_response_checks(rsp)
    exec_id = result.get('ids')[0]
    url = '{}/actors/{}/executions/{}'.format(base_url, actor_id, exec_id)
    rsp = requests.get(url, headers=headers)
    result = basic_response_checks(rsp)
    if case == 'snake':
        assert 'actor_id' in result
        assert result['actor_id'] == actor_id
    else:
        assert 'actorId' in result
        assert result['actorId'] == actor_id
    assert 'cpu' in result
    assert 'executor' in result
    assert 'id' in result
    assert 'io' in result
    assert 'runtime' in result
    assert 'status' in result
    assert result['status'] == 'COMPLETE'
    assert result['id'] == exec_id

def test_list_execution_logs(headers):
    actor_id = get_actor_id(headers)
    # get execution id
    url = '{}/actors/{}/executions'.format(base_url, actor_id)
    rsp = requests.get(url, headers=headers)
    # we don't check tenant because it could (and often does) appear in the logs
    result = basic_response_checks(rsp, check_tenant=False)
    exec_id = result.get('ids')[0]
    url = '{}/actors/{}/executions/{}/logs'.format(base_url, actor_id, exec_id)
    rsp = requests.get(url, headers=headers)
    result = basic_response_checks(rsp, check_tenant=False)
    assert 'Contents of MSG: testing execution' in result['logs']
    assert 'PATH' in result['logs']
    assert '_abaco_actor_id' in result['logs']
    assert '_abaco_api_server' in result['logs']
    assert '_abaco_actor_state' in result['logs']
    assert '_abaco_username' in result['logs']
    assert '_abaco_execution_id' in result['logs']
    assert '_abaco_Content-Type' in result['logs']


def test_execute_actor_json(headers):
    actor_id = get_actor_id(headers)
    url = '{}/actors/{}/messages'.format(base_url, actor_id)
    data = {'key1': 'value1', 'key2': 'value2'}
    # pass raw JSON to the messages endpoint.
    rsp = requests.post(url, json=data, headers=headers)
    result = basic_response_checks(rsp)
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
            if case == 'snake':
                assert result.get('actor_id') == actor_id
            else:
                assert result.get('actorId') == actor_id
            assert result.get('id') == exc_id
            # note: it is possible for io to be 0 in which case an `assert result['io']` will fail.
            assert 'io' in result
            assert 'runtime' in result
            return
        count += 1
    assert False

def test_update_actor(headers):
    actor_id = get_actor_id(headers)
    url = '{}/actors/{}'.format(base_url, actor_id)
    data = {'image': 'jstubbs/abaco_test2'}
    rsp = requests.put(url, data=data, headers=headers)
    result = basic_response_checks(rsp)
    assert 'description' in result
    assert result['image'] == 'jstubbs/abaco_test2'
    assert result['name'] == 'abaco_test_suite'
    assert result['id'] is not None



# ################
# admin API
# ################

def test_list_workers(headers):
    actor_id = get_actor_id(headers)
    url = '{}/actors/{}/workers'.format(base_url, actor_id)
    rsp = requests.get(url, headers=headers)
    # workers collection returns the tenant_id since it is an admin api
    result = basic_response_checks(rsp, check_tenant=False)
    assert len(result) > 0
    # get the first worker
    worker = result[0]
    assert worker.get('image') == 'jstubbs/abaco_test'
    assert worker.get('status') == 'READY'
    assert worker.get('location')
    assert worker.get('cid')
    assert worker.get('last_execution')
    assert worker.get('ch_name')
    assert worker.get('tenant')

def test_cors_list_workers(headers):
    actor_id = get_actor_id(headers)
    url = '{}/actors/{}/workers'.format(base_url, actor_id)
    headers['Origin'] = 'http://example.com'
    rsp = requests.get(url, headers=headers)
    basic_response_checks(rsp)
    assert 'Access-Control-Allow-Origin' in rsp.headers

def test_cors_options_list_workers(headers):
    actor_id = get_actor_id(headers)
    url = '{}/actors/{}/workers'.format(base_url, actor_id)
    headers['Origin'] = 'http://example.com'
    headers['Access-Control-Request-Method'] = 'POST'
    headers['Access-Control-Request-Headers'] = 'X-Requested-With'
    rsp = requests.options(url, headers=headers)
    assert rsp.status_code == 200
    assert 'Access-Control-Allow-Origin' in rsp.headers
    assert 'Access-Control-Allow-Methods' in rsp.headers
    assert 'Access-Control-Allow-Headers' in rsp.headers


def test_ensure_one_worker(headers):
    actor_id = get_actor_id(headers)
    url = '{}/actors/{}/workers'.format(base_url, actor_id)
    rsp = requests.post(url, headers=headers)
    # workers collection returns the tenant_id since it is an admin api
    assert rsp.status_code in [200, 201]
    time.sleep(8)
    rsp = requests.get(url, headers=headers)
    result = basic_response_checks(rsp, check_tenant=False)
    assert len(result) == 1

def test_ensure_two_worker(headers):
    actor_id = get_actor_id(headers)
    url = '{}/actors/{}/workers'.format(base_url, actor_id)
    data = {'num': '2'}
    rsp = requests.post(url, data=data, headers=headers)
    # workers collection returns the tenant_id since it is an admin api
    assert rsp.status_code in [200, 201]
    time.sleep(8)
    rsp = requests.get(url, headers=headers)
    result = basic_response_checks(rsp, check_tenant=False)
    assert len(result) == 2



def test_delete_worker(headers):
    # get the list of workers
    actor_id = get_actor_id(headers)
    url = '{}/actors/{}/workers'.format(base_url, actor_id)
    rsp = requests.get(url, headers=headers)
    # workers collection returns the tenant_id since it is an admin api
    result = basic_response_checks(rsp, check_tenant=False)

    # delete the first one
    id = result[0].get('id')
    url = '{}/actors/{}/workers/{}'.format(base_url, actor_id, id)
    rsp = requests.delete(url, headers=headers)
    result = basic_response_checks(rsp, check_tenant=False)
    time.sleep(4)

    # get the update list of workers
    url = '{}/actors/{}/workers'.format(base_url, actor_id)
    rsp = requests.get(url, headers=headers)
    result = basic_response_checks(rsp, check_tenant=False)
    assert len(result) == 1

def test_list_permissions(headers):
    actor_id = get_actor_id(headers)
    url = '{}/actors/{}/permissions'.format(base_url, actor_id)
    rsp = requests.get(url, headers=headers)
    result = basic_response_checks(rsp)
    assert len(result) == 1

def test_add_permissions(headers):
    actor_id = get_actor_id(headers)
    url = '{}/actors/{}/permissions'.format(base_url, actor_id)
    data = {'user': 'tester', 'level': 'UPDATE'}
    rsp = requests.post(url, data=data, headers=headers)
    result = basic_response_checks(rsp)
    rsp = requests.get(url, headers=headers)
    result = basic_response_checks(rsp)
    assert len(result) == 2


# ##############################
# tenancy - tests for bleed over
# ##############################

def test_tenant_list_actors():
    # passing another tenant should result in 0 actors.
    headers = {'tenant': 'abaco_test_suite_tenant'}
    url = '{}/{}'.format(base_url, '/actors')
    rsp = requests.get(url, headers=headers)
    result = basic_response_checks(rsp)
    assert len(result) == 0

def test_tenant_register_actor():
    headers = {'tenant': 'abaco_test_suite_tenant'}
    url = '{}/{}'.format(base_url, '/actors')
    data = {'image': 'jstubbs/abaco_test', 'name': 'abaco_test_suite_other_tenant'}
    rsp = requests.post(url, data=data, headers=headers)
    result = basic_response_checks(rsp)
    assert 'description' in result
    assert result['image'] == 'jstubbs/abaco_test'
    assert result['name'] == 'abaco_test_suite_other_tenant'
    assert result['id'] is not None

def test_tenant_actor_is_ready():
    headers = {'tenant': 'abaco_test_suite_tenant'}
    count = 0
    actor_id = get_actor_id(headers, name='abaco_test_suite_other_tenant')
    while count < 10:
        url = '{}/actors/{}'.format(base_url, actor_id)
        rsp = requests.get(url, headers=headers)
        result = basic_response_checks(rsp)
        if result['status'] == 'READY':
            return
        time.sleep(3)
        count += 1
    assert False

def test_tenant_list_registered_actors():
    # passing another tenant should result in 1 actor.
    headers = {'tenant': 'abaco_test_suite_tenant'}
    url = '{}/{}'.format(base_url, '/actors')
    rsp = requests.get(url, headers=headers)
    result = basic_response_checks(rsp)
    assert len(result) == 1

def test_tenant_list_actor():
    headers = {'tenant': 'abaco_test_suite_tenant'}
    actor_id = get_actor_id(headers, name='abaco_test_suite_other_tenant')
    url = '{}/actors/{}'.format(base_url, actor_id)
    rsp = requests.get(url, headers=headers)
    result = basic_response_checks(rsp)
    assert 'description' in result
    assert result['image'] == 'jstubbs/abaco_test'
    assert result['name'] == 'abaco_test_suite_other_tenant'
    assert result['id'] is not None

def test_tenant_list_executions():
    headers = {'tenant': 'abaco_test_suite_tenant'}
    actor_id = get_actor_id(headers, name='abaco_test_suite_other_tenant')
    url = '{}/actors/{}/executions'.format(base_url, actor_id)
    rsp = requests.get(url, headers=headers)
    result = basic_response_checks(rsp)
    assert len(result.get('ids')) == 0

def test_tenant_list_messages():
    headers = {'tenant': 'abaco_test_suite_tenant'}
    actor_id = get_actor_id(headers, name='abaco_test_suite_other_tenant')
    url = '{}/actors/{}/messages'.format(base_url, actor_id)
    rsp = requests.get(url, headers=headers)
    result = basic_response_checks(rsp)
    assert result.get('messages') == 0

def test_tenant_list_workers():
    headers = {'tenant': 'abaco_test_suite_tenant'}
    actor_id = get_actor_id(headers, name='abaco_test_suite_other_tenant')
    url = '{}/actors/{}/workers'.format(base_url, actor_id)
    rsp = requests.get(url, headers=headers)
    # workers collection returns the tenant_id since it is an admin api
    result = basic_response_checks(rsp, check_tenant=False)
    assert len(result) > 0
    # get the first worker
    worker = result[0]
    assert worker.get('image') == 'jstubbs/abaco_test'
    assert worker.get('status') == 'READY'
    assert worker.get('location')
    assert worker.get('cid')
    assert worker.get('ch_name')


# ##############
# Clean up
# ##############

def test_remove_final_actors(headers):
    url = '{}/actors'.format(base_url)
    rsp = requests.get(url, headers=headers)
    result = basic_response_checks(rsp)
    for act in result:
        url = '{}/actors/{}'.format(base_url, act.get('id'))
        rsp = requests.delete(url, headers=headers)
        result = basic_response_checks(rsp)

def test_tenant_remove_final_actors():
    headers = {'tenant': 'abaco_test_suite_tenant'}
    url = '{}/actors'.format(base_url)
    rsp = requests.get(url, headers=headers)
    result = basic_response_checks(rsp)
    for act in result:
        url = '{}/actors/{}'.format(base_url, act.get('id'))
        rsp = requests.delete(url, headers=headers)
        result = basic_response_checks(rsp)