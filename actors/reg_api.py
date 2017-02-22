
from flask import Flask
from flask_cors import CORS

from request_utils import AgaveApi, handle_error
from controllers import ActorResource, ActorStateResource, ActorsResource, \
    ActorExecutionsResource, ActorExecutionResource, \
    ActorExecutionLogsResource
from auth import authn_and_authz


app = Flask(__name__)
CORS(app)
api = AgaveApi(app)

# Authn/z
@app.before_request
def auth():
    authn_and_authz()

# Set up error handling
@app.errorhandler(Exception)
def handle_all_errors(e):
    return handle_error(e)

import logs
app.logger.addHandler(logs.get_file_handler('reg_api_logs'))


# Resources
api.add_resource(ActorsResource, '/actors')
api.add_resource(ActorResource, '/actors/<string:actor_id>')
api.add_resource(ActorStateResource, '/actors/<string:actor_id>/state')
api.add_resource(ActorExecutionsResource, '/actors/<string:actor_id>/executions')
api.add_resource(ActorExecutionResource, '/actors/<string:actor_id>/executions/<string:execution_id>')
api.add_resource(ActorExecutionLogsResource, '/actors/<string:actor_id>/executions/<string:execution_id>/logs')

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
