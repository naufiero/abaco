# Functional test suite for abaco.
# Start the local development abaco stack and run these tests with py.test from the cwd.

import os
import time

import pytest
import requests
import json

base_url = os.environ.get('base_url', 'http://localhost:8000')

# #################
# registration API
# #################

def test_remove_initial_actors():
    url = '{}/{}'.format(base_url, '/actors')
    rsp = requests.get(url)
    result = basic_response_checks(rsp)
    for act in result:
        url = '{}/{}/{}'.format(base_url, '/actors', act.get('id'))
        rsp = requests.delete(url)
        result = basic_response_checks(rsp)

def basic_response_checks(rsp):
    assert rsp.status_code in [200, 201]
    assert  'application/json' in rsp.headers['content-type']
    data = json.loads(rsp.content)
    assert 'msg' in data.keys()
    assert 'status' in data.keys()
    assert 'result' in data.keys()
    assert 'version' in data.keys()
    return data['result']

def test_list_actors():
    url = '{}/{}'.format(base_url, '/actors')
    rsp = requests.get(url)
    result = basic_response_checks(rsp)
    assert len(result) == 0

def test_register_actor():
    url = '{}/{}'.format(base_url, '/actors')
    data = {'image': 'jstubbs/abaco_test', 'name': 'test'}
    rsp = requests.post(url, data=data)
    result = basic_response_checks(rsp)
    assert 'description' in result
    assert 'executions' in result
    assert result['image'] == 'jstubbs/abaco_test'
    assert result['name'] == 'test'
    assert result['id'] == 'test_0'

def test_list_actor():
    url = '{}/actors/test_0'.format(base_url)
    rsp = requests.get(url)
    result = basic_response_checks(rsp)
    assert 'description' in result
    assert 'executions' in result
    assert result['image'] == 'jstubbs/abaco_test'
    assert result['name'] == 'test'
    assert result['id'] == 'test_0'

def test_actor_is_ready():
    count = 0
    while count < 10:
        url = '{}/actors/test_0'.format(base_url)
        rsp = requests.get(url)
        result = basic_response_checks(rsp)
        if result['status'] == 'READY':
            return
        time.sleep(3)
        count += 1
    assert False

def test_execute_actor():
    url = '{}/actors/test_0/messages'.format(base_url)
    data = {'message': 'testing execution'}
    rsp = requests.post(url, data=data)
    result = basic_response_checks(rsp)
    assert result.get('msg')  == 'testing execution'
    # check for the execution to complete
    count = 0
    while count < 3:
        time.sleep(2)
        url = '{}/actors/test_0/executions'.format(base_url)
        rsp = requests.get(url)
        result = basic_response_checks(rsp)
        ids = result.get('ids')
        if ids:
            assert len(ids) == 1
            assert ids[0] ==  'test_0_exc_0'
            assert result.get('total_executions') == 1
            assert result.get('total_cpu')
            assert result.get('total_io')
            assert result.get('total_runtime')
            return
        count += 1
    assert False

def test_list_execution_logs():
    url = '{}/actors/test_0/executions/test_0_exc_0/logs'.format(base_url)
    rsp = requests.get(url)
    result = basic_response_checks(rsp)
    assert 'Contents of MSG: testing execution' in result
    assert 'PATH' in result


# ################
# admin API
# ################

def test_list_workers():
    url = '{}/actors/test_0/workers'.format(base_url)
    rsp = requests.get(url)
    result = basic_response_checks(rsp)
    assert len(result) > 0
    worker = result[0]
    assert worker.get('image') == 'jstubbs/abaco_test'
    assert worker.get('status') == 'READY'
    assert worker.get('location')
    assert worker.get('cid')
    assert worker.get('last_update')
    assert worker.get('ch_name')

def test_add_worker():
    url = '{}/actors/test_0/workers'.format(base_url)
    rsp = requests.post(url)
    result = basic_response_checks(rsp)
    time.sleep(8)
    rsp = requests.get(url)
    result = basic_response_checks(rsp)
    assert len(result) == 2

def test_delete_worker():
    # get the list of workers
    url = '{}/actors/test_0/workers'.format(base_url)
    rsp = requests.get(url)
    result = basic_response_checks(rsp)

    # delete the last one
    id = result[1].get('ch_name')
    url = '{}/actors/test_0/workers/{}'.format(base_url, id)
    rsp = requests.delete(url)
    result = basic_response_checks(rsp)
    time.sleep(2)

    # get the update list of workers
    url = '{}/actors/test_0/workers'.format(base_url)
    rsp = requests.get(url)
    result = basic_response_checks(rsp)
    assert len(result) == 1

def test_list_permissions():
    url = '{}/actors/test_0/permissions'.format(base_url)
    rsp = requests.get(url)
    result = basic_response_checks(rsp)
    assert len(result) == 1


# ##############
# Clean up
# ##############

def test_update_actor():
    url = '{}/actors/test_0'.format(base_url)
    data = {'image': 'jstubbs/abaco_test2'}
    rsp = requests.put(url, data=data)
    result = basic_response_checks(rsp)
    assert 'description' in result
    assert 'executions' in result
    assert result['image'] == 'jstubbs/abaco_test2'
    assert result['name'] == 'test'
    assert result['id'] == 'test_0'

def test_remove_final_actors():
    url = '{}/{}'.format(base_url, '/actors')
    rsp = requests.get(url)
    result = basic_response_checks(rsp)
    for act in result:
        url = '{}/{}/{}'.format(base_url, '/actors', act.get('id'))
        rsp = requests.delete(url)
        result = basic_response_checks(rsp)