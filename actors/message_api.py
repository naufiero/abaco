from flask import Flask
from flask_cors import CORS 

from request_utils import AgaveApi, handle_error
from auth import authn_and_authz
from controllers import MessagesResource

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
app.logger.addHandler(logs.get_file_handler('message_api_logs'))


# Resources
api.add_resource(MessagesResource, '/actors/<string:actor_id>/messages')

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
