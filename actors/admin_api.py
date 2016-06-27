from flask import Flask
from flask_cors import CORS

from request_utils import AbacoApi
from auth import authn_and_authz
from controllers import PermissionsResource, WorkersResource, WorkerResource

app = Flask(__name__)
CORS(app)
api = AbacoApi(app)

import logs
app.logger.addHandler(logs.get_file_handler('admin_api_logs'))

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
