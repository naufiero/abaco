from flask import Flask, render_template
from flask_cors import CORS

from agaveflask.utils import AgaveApi
from common.utils import handle_error

from auth import authn_and_authz
from controllers import AdminActorsResource, AdminWorkersResource, AdminExecutionsResource, \
    ActorPermissionsResource, AliasPermissionsResource, WorkersResource, WorkerResource
from dashboard import dashboard

app = Flask(__name__)
CORS(app)
api = AgaveApi(app)

# Authn/z
@app.before_request
def auth():
    authn_and_authz()

# Set up error handling
api.handle_error = handle_error
api.handle_exception = handle_error
api.handle_user_exception = handle_error

# Resources
api.add_resource(WorkersResource, '/actors/<string:actor_id>/workers')
api.add_resource(AliasPermissionsResource, '/actors/aliases/<string:identifier>/permissions')
api.add_resource(ActorPermissionsResource, '/actors/<string:identifier>/permissions')
api.add_resource(WorkerResource, '/actors/<string:actor_id>/workers/<string:worker_id>')
api.add_resource(AdminActorsResource, '/actors/admin')
api.add_resource(AdminWorkersResource, '/actors/admin/workers')
api.add_resource(AdminExecutionsResource, '/actors/admin/executions')

# web app
@app.route('/admin/dashboard', methods=['POST', 'GET'])
def admin_dashboard():
    return dashboard()


if __name__ == '__main__':
    # must be threaded to support the dashboard which can in some cases, make requests to the admin API.
    app.run(host='0.0.0.0', debug=True, threaded=True)
