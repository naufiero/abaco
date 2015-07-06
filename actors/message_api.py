
from flask import Flask
from flask_restful import Api

from messages import MessagesResource

app = Flask(__name__)
api = Api(app)

# Resources
api.add_resource(MessagesResource, '/actors/<string:actor_id>/messages')

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
