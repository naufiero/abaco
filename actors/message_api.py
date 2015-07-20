
from flask import Flask
from request_utils import AbacoApi

from messages import MessagesResource

app = Flask(__name__)
api = AbacoApi(app)

# Resources
api.add_resource(MessagesResource, '/actors/<string:actor_id>/messages')

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
