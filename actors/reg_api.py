
from flask import Flask
from request_utils import AbacoApi

from actors import ActorResource, ActorStateResource, ActorsResource, \
    ActorSubscriptionResource, ActorExecutionsResource, ActorExecutionResource, \
    ActorExecutionLogsResource
from auth import authn_and_authz


app = Flask(__name__)
api = AbacoApi(app)

# Authn/z
@app.before_request
def auth():
    authn_and_authz()


# Resources
api.add_resource(ActorsResource, '/actors')
api.add_resource(ActorResource, '/actors/<string:actor_id>')
api.add_resource(ActorStateResource, '/actors/<string:actor_id>/state')
api.add_resource(ActorSubscriptionResource, '/actors/<string:actor_id>/subscriptions')
api.add_resource(ActorExecutionsResource, '/actors/<string:actor_id>/executions')
api.add_resource(ActorExecutionResource, '/actors/<string:actor_id>/executions/<string:execution_id>')
api.add_resource(ActorExecutionLogsResource, '/actors/<string:actor_id>/executions/<string:execution_id>/logs')

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
