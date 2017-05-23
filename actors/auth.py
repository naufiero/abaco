# Utilities for authn/z
import base64
import json
import os
import re

from Crypto.Signature import PKCS1_v1_5
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA256
from flask import g, request, abort
from flask_restful import Resource
import jwt

from agaveflask.auth import authn_and_authz as agaveflask_az
from agaveflask.logs import get_logger
logger = get_logger(__name__)

from agaveflask.utils import ok, RequestParser

from config import Config
from errors import PermissionsException
from models import Actor, get_permissions

from stores import actors_store, permissions_store



jwt.verify_methods['SHA256WITHRSA'] = (
    lambda msg, key, sig: PKCS1_v1_5.new(key).verify(SHA256.new(msg), sig))
jwt.prepare_key_methods['SHA256WITHRSA'] = jwt.prepare_RS_key


def get_pub_key():
    pub_key = Config.get('web', 'apim_public_key')
    return RSA.importKey(base64.b64decode(pub_key))


PUB_KEY = get_pub_key()

TOKEN_RE = re.compile('Bearer (.+)')

WORLD_USER = 'world'

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
    # we use the agaveflask authn_and_authz function, passing in our authorization callback.
    agaveflask_az(authorization)

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
        return True

    # the 'ALL' role is a role set by agaveflask in case the access_control_type is none
    if 'ALL' in g.roles:
      return True

    # the 'abaco_admin' role is the admin role when JWT auth is configured:
    if 'Internal/abaco_admin' in g.roles:
      return True

    # all other checks are based on actor-id; if that is not present then let
    # request through to fail.
    actor_id = request.args.get('actor_id', None)
    if not actor_id:
        return

    if request.method == 'GET':
        has_pem = check_permissions(user=g.user, actor_id=actor_id, level='READ')
    else:
        logger.debug("URL rule in request: {}".format(request.url_rule.rule))
        # first, only admins can create/update actors to be privileged, so check that:
        if request.method == 'POST' or request.method == 'PUT':
            data = request.get_json()
            if not data:
                data = request.form
            if data.get('privileged'):
                # if we're here, user isn't an admin so this isn't allowed:
                raise PermissionsException("Not authorized")
        if request.method == 'POST':
            # creating a new actor requires no permissions
            if 'actors' == request.url_rule.rule or 'actors/' == request.url_rule.rule:
                has_pem = True
            # POST to the messages endpoint requires EXECUTE
            elif 'messages' in request.url_rule.rule:
                has_pem = check_permissions(user=g.user, actor_id=actor_id, level='EXECUTE')
            # otherwise, we require UPDATE
            else:
                has_pem = check_permissions(user=g.user, actor_id=actor_id, level='UPDATE')
    if not has_pem:
        raise PermissionsException("Not authorized")

def check_permissions(user, actor_id, level):
    """Check the permissions store for user and level"""
    # get all permissions for this actor
    permissions = get_permissions(actor_id)
    for pem in permissions:
        # if the actor has been shared with the WORLD_USER anyone can use it
        if user == WORLD_USER:
            return True
        # otherwise, check if the permission belongs to this user and has the necessary level
        if pem['user'] == user:
            if pem['level'] >= level:
                return True
    return False
