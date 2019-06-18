# To run tests: docker-compose -f docker-compose-dashboard.yml run django python3 manage.py test tests
# to build dashboard image: docker build -t abaco/dashboard -f Dockerfile-dashboard .

import unittest
from django.test import TestCase, Client
from dashboard_util import base_url, basic_response_checks, headers


import requests
import inspect
import os
import tempfile
import json


class DashboardClassCase(TestCase):
    def setup(self):
        self.client = Client()


    def login(self, username, password):
        login = self.client.post('/login', data=dict(
            username=username,
            password=password,
            Content_Type='application/json',
        ), follow_redirects=True)

        return login



    def logout(self, client):
        return self.client.get('/logout', follow_redirects=True)

    def test_login(self):
        # from pudb.remote import set_trace; set_trace(term_size=(160, 40), host='0.0.0.0', port=6900)
        rsp = self.login(username='testshareuser', password='testshareuser')
        rsp_content = rsp.content.decode("utf-8")
        self.assertNotIn("Invalid username or password", rsp_content)
        self.assertNotIn("You do not have Admin privileges.", rsp_content)
        self.logout(client=Client)

    def test_no_login_if_not_admin(self):
        rsp = self.login(username='testuser', password='testuser')
        rsp_content = rsp.content.decode("utf-8")
        self.assertIn("You do not have Admin privileges.", rsp_content)
        self.logout(client=Client)

    def test_no_login_if_invalid(self):
        rsp = self.login(username='hshs', password='jsjsjs')
        rsp_content = rsp.content.decode("utf-8")
        self.assertIn("Invalid username or password", rsp_content)
        self.logout(client=Client)

    def test_actors_tab_no_session(self):
        rsp = self.client.get('/actors')
        rsp_content = rsp.content.decode("utf-8")
        self.assertEquals(rsp.status_code, 302)
        self. assertIn(rsp_content, "there was an error")

    def test_workers_tab_no_session(self):
        rsp = self.client.get('/workers')
        rsp_content = rsp.content.decode("utf-8")
        self.assertEquals(rsp.status_code, 302)
        self.assertIn(rsp_content, "there was an error")

    def test_executions_tab_no_session(self):
        rsp = self.client.get('/executions')
        rsp_content = rsp.content.decode("utf-8")
        self.assertEquals(rsp.status_code, 302)
        self.assertIn(rsp_content, "there was an error")

    def test_logout(self):
        rsp = self.login(username='testshareuser', password='testshareuser')
        self.assertEquals(rsp.status_code, 302)
        self.logout(client=Client)
        rsp = self.client.get('/workers')
        rsp_content = rsp.content.decode("utf-8")
        self.assertEquals(rsp.status_code, 302)
        self.assertIn(rsp_content, "there was an error")
        rspa = self.client.get('/actors')
        self.assertEquals(rspa.status_code, 302)
        rspa_decoded = rspa.content.decode("utf-8")
        self.assertIn(rspa_decoded, "there was an error")
        rspe = self.client.get('/executions')
        rspe_decoded = rspe.content.decode("utf-8")
        self.assertEquals(rspe.status_code, 302)
        self.assertIn(rspe_decoded, "there was an error")


    def test_api_deletes_actors_from_dashboard(self):
        url = '{}/{}/v2'.format(base_url, 'actors')

        data = {
            'image': 'jstubbs/abaco_test',
            'name': 'abaco_test_default',
            'stateless': False,
        }
        tokendata = {'grant_type': 'password',
                'username': 'testshareuser',
                'password': 'testshareuser',
                'scope': 'PRODUCTION'}
        token_url = '{}/{}'.format(base_url, 'token')
        auth = requests.auth.HTTPBasicAuth('PrvjJibzGlducHasXUWeTX1wOg8a', '34pvSqDNSTe0eQdhc1VQcaahLDUa')
        resp = requests.post(token_url, data=tokendata, auth=auth)
        tokeninfo = resp.json()
        token = tokeninfo['access_token']

        headers = {'Authorization': 'Bearer {}'.format(token)}

        rsp = requests.post(url, data=data, headers=headers)
        data = json.loads(rsp.content.decode('utf-8'))
        all_data = data['result']
        actor_id = all_data['id'].encode()

        url_del = '{}/{}/v2/{}'.format(base_url, 'actors', actor_id)
        self.assertIn(actor_id, rsp.content)
        del_rsp = requests.delete(url_del, headers=headers)
        fin_rsp = self.client.get('/actors')
        self.assertNotIn(actor_id, fin_rsp.content)


    def test_delete_button_deletes_workers_from_api(self):
        pass
    # pass until caching has been implemented
    ###########
    #     url = '{}/{}'.format(base_url, '/actors')
    #     data = {
    #         'image': 'jstubbs/abaco_test',
    #         'name': 'abaco_test_default',
    #         'stateless': False,
    #     }
    #     rsp = requests.post(url, data=data, headers=headers)
    #     actor_id = rsp['id']
    #     print(actor_id)
    #     drsp = requests.delete(self.url, headers=headers, actorId=self.actor_id)
    #     # frsp = self.client.get('/actors') this one needs to go to API
    #     self.assertNotIn(frsp.conent, actor_id)


