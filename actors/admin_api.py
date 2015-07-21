from flask import Flask
from request_utils import AbacoApi

from auth import authn_and_authz, PermissionsResource
from worker import WorkersResource, WorkerResource

app = Flask(__name__)
api = AbacoApi(app)

# Authn/z
@app.before_request
def auth():
    authn_and_authz()


# Resources
api.add_resource(WorkersResource, '/actors/<string:actor_id>/workers')
api.add_resource(PermissionsResource, '/actors/<string:actor_id>/permissions')
api.add_resource(WorkerResource, '/actors/<string:actor_id>/workers/<string:ch_name>')

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
