
from flask import Flask
from flask_restful import Api

from actors import ActorResource, ActorStateResource, ActorsResource, \
    ActorSubscriptionResource, ActorExecutionsResource, ActorExecutionResource

app = Flask(__name__)
api = Api(app)

# Resources
api.add_resource(ActorsResource, '/actors')
api.add_resource(ActorResource, '/actors/<string:actor_id>')
api.add_resource(ActorStateResource, '/actors/<string:actor_id>/state')
api.add_resource(ActorSubscriptionResource, '/actors/<string:actor_id>/subscriptions')
api.add_resource(ActorExecutionsResource, '/actors/<string:actor_id>/executions')
api.add_resource(ActorExecutionResource, '/actors/<string:actor_id>/executions/<string:execution_id>')

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
