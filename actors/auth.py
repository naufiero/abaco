# Utilities for authn/z
import base64
import json
import re

from Crypto.Signature import PKCS1_v1_5
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA256
from flask import g, request, abort
from flask_restful import Resource
import jwt

from config import Config
from models import Actor
from request_utils import APIException, ok, RequestParser
from stores import actors_store, permissions_store


jwt.verify_methods['SHA256WITHRSA'] = (
    lambda msg, key, sig: PKCS1_v1_5.new(key).verify(SHA256.new(msg), sig))
jwt.prepare_key_methods['SHA256WITHRSA'] = jwt.prepare_RS_key


def get_pub_key():
    pub_key = Config.get('web', 'apim_public_key')
    return RSA.importKey(base64.b64decode(pub_key))


PUB_KEY = get_pub_key()

TOKEN_RE = re.compile('Bearer (.+)')

PERMISSION_LEVELS = ('READ', 'UPDATE')

class PermissionsException(Exception):
    def __init__(self, message):
        Exception.__init__(self, message)
        self.message = message


def get_pub_key():
    pub_key = Config.get('web', 'apim_public_key')
    return RSA.importKey(base64.b64decode(pub_key))


def authn_and_authz():
    """All-in-one convenience function for implementing the basic abaco authentication
    and authorization on a flask app. Use as follows:

    import auth

    my_app = Flask(__name__)
    @my_app.before_request
    def authnz_for_my_app():
        auth.authn_and_authz()

    """
    authentication()
    authorization()


def authentication():
    """Entry point for authentication. Use as follows:

    import auth

    my_app = Flask(__name__)
    @my_app.before_request
    def authn_for_my_app():
        auth.authentication()

    """
    # don't control access to OPTIONS verb
    if request.method == 'OPTIONS':
        return
    access_control_type = Config.get('web', 'access_control')
    if access_control_type == 'none':
        g.user = 'anonymous'
        g.token = 'N/A'
        return
    if access_control_type == 'jwt':
        return check_jwt(request)
    abort(400, {'message': 'Invalid access_control'})


def check_jwt(req):
    tenant_name = Config.get('web', 'tenant_name')
    try:
        jwt_header = req.headers['X-JWT-Assertion-{0}'.format(tenant_name)]
    except KeyError:
        try:
            jwt_header = req.headers['Assertion']
        except KeyError:
             msg = ''
             for k,v in req.headers.items():
                msg = msg + ' ' + str(k) + ': ' + str(v)
             abort(400, {'message': 'JWT header missing. Headers: '+msg})
             # abort(400, {'message': 'JWT header missing.'})
    try:
        decoded = jwt.decode(jwt_header, PUB_KEY)
        g.jwt = jwt_header
        g.user = decoded['http://wso2.org/claims/enduser']
        g.token = get_token(req.headers)
    except (jwt.DecodeError, KeyError):
        abort(400, {'message': 'Invalid JWT.'})

def get_token(headers):
    """
    :type headers: dict
    :rtype: str|None
    """
    auth = headers.get('Authorization', '')
    match = TOKEN_RE.match(auth)
    if not match:
        return None
    else:
        return match.group(1)

def authorization():
    """Entry point for authorization. Use as follows:

    import auth

    my_app = Flask(__name__)
    @my_app.before_request
    def authz_for_my_app():
        auth.authorization()

    """
    if request.method == 'OPTIONS':
        # allow all users to make OPTIONS requests
        return

    # all other checks are based on actor-id; if that is not present then let
    # request through to fail.
    actor_id = request.args.get('actor_id', None)
    if not actor_id:
        return

    if request.method == 'GET':
        has_pem = check_permissions(user=g.user, actor_id=actor_id, level='READ')
    else:
        # creating a new actor requires no permissions
        print(request.url_rule.rule)
        if request.method == 'POST' \
                and ('actors' == request.url_rule.rule or 'actors/' == request.url_rule.rule):
            has_pem = True
        else:
            has_pem = check_permissions(user=g.user, actor_id=actor_id, level='UPDATE')
    if not has_pem:
        raise APIException("Not authorized")

def get_permissions(actor_id):
    """ Return all permissions for an actor
    :param actor_id:
    :return:
    """
    try:
        permissions = json.loads(permissions_store[actor_id])
        return permissions
    except KeyError:
        raise PermissionsException("Actor {} does not exist".format(actor_id))

def check_permissions(user, actor_id, level):
    """Check the permissions store for user and level"""
    permissions = get_permissions(actor_id)
    for pem in permissions:
        if pem['user'] == user:
            if pem['level'] >= level:
                return True
    return False

def add_permission(user, actor_id, level):
    """Add a permission for a user and level to an actor."""
    try:
        permissions = get_permissions(actor_id)
    except PermissionsException:
        permissions = []
    for pem in permissions:
        if pem.get('user') == 'user' and pem.get('level') == level:
            return
    permissions.append({'user': user,
                        'level': level})
    permissions_store[actor_id] = json.dumps(permissions)


class PermissionsResource(Resource):
    def get(self, actor_id):
        try:
            Actor.from_db(actors_store[actor_id])
        except KeyError:
            raise APIException(
                "actor not found: {}'".format(actor_id), 404)
        try:
            permissions = get_permissions(actor_id)
        except PermissionsException as e:
            raise APIException(e.message, 404)
        return ok(result=permissions, msg="Permissions retrieved successfully.")

    def validate_post(self):
        parser = RequestParser()
        parser.add_argument('user', type=str, required=True, help="User owning the permission.")
        parser.add_argument('level', type=str, required=True,
                            help="Level of the permission: {}".format(PERMISSION_LEVELS))
        args = parser.parse_args()
        if not args['level'] in PERMISSION_LEVELS:
            raise APIException("Invalid permission level: {}. \
            The valid values are {}".format(args['level'], PERMISSION_LEVELS))
        return args

    def post(self, actor_id):
        """Add new permissions for an actor"""
        try:
            Actor.from_db(actors_store[actor_id])
        except KeyError:
            raise APIException(
                "actor not found: {}'".format(actor_id), 404)
        args = self.validate_post()
        add_permission(args['user'], actor_id, args['level'])
        permissions = get_permissions(actor_id)
        return ok(result=permissions, msg="Permission added successfully.")
