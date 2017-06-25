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
import codes
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
    g.admin = False
    if request.method == 'OPTIONS':
        # allow all users to make OPTIONS requests
        logger.info("Allowing request because of OPTIONS method.")
        return True

    # the 'ALL' role is a role set by agaveflask in case the access_control_type is none
    if codes.ALL_ROLE in g.roles:
        g.admin = True
        logger.info("Allowing request because of ALL role.")
        return True

    # the admin role when JWT auth is configured:
    if codes.ADMIN_ROLE in g.roles:
        g.admin = True
        logger.info("Allowing request because of ADMIN_ROLE.")
        return True

    # all other requests require some kind of abaco role:
    if set(g.roles).isdisjoint(codes.roles):
        logger.info("NOT allowing request - user has no abaco role.")
        raise PermissionsException("Not authorized -- missing required role.")
    else:
        logger.debug("User has an abaco role.")
    logger.debug("URL rule: {}".format(request.url_rule.rule or 'actors/'))
    logger.debug("request.path: {}".format(request.path))
    # there are special rules on the root collection:
    if '/actors' == request.url_rule.rule or '/actors/' == request.url_rule.rule:
        logger.debug("Checking permissions on root collection.")
        # first, only admins can create/update actors to be privileged, so check that:
        if request.method == 'POST':
            check_privileged()
        # if we are here, it is either a GET or a new actor, so the request is allowed:
        logger.debug("new actor or GET on root connection. allowing request.")
        return True

    # all other checks are based on actor-id:
    db_id = get_db_id()
    logger.debug("db_id: {}".format(db_id))
    if request.method == 'GET':
        # GET requests require READ access
        has_pem = check_permissions(user=g.user, actor_id=db_id, level=codes.READ)
    elif request.method == 'DELETE':
        has_pem = check_permissions(user=g.user, actor_id=db_id, level=codes.UPDATE)
    else:
        logger.debug("URL rule in request: {}".format(request.url_rule.rule))
        # first, only admins can create/update actors to be privileged, so check that:
        if request.method == 'POST' or request.method == 'PUT':
            check_privileged()
            # only admins have access to the workers endpoint, and if we are here, the user is not an admin:
            if 'workers' in request.url_rule.rule:
                raise PermissionsException("Not authorized -- only admins are authorized to update workers.")
        if request.method == 'POST':
            # POST to the messages endpoint requires EXECUTE
            if 'messages' in request.url_rule.rule:
                has_pem = check_permissions(user=g.user, actor_id=db_id, level=codes.EXECUTE)
            # otherwise, we require UPDATE
            else:
                has_pem = check_permissions(user=g.user, actor_id=db_id, level=codes.UPDATE)
    if not has_pem:
        logger.info("NOT allowing request.")
        raise PermissionsException("Not authorized -- you do not have access to this actor.")

def check_privileged():
    """Check if request is trying to make an actor privileged."""
    logger.debug("top of check_privileged")
    # admins have access to all actors:
    if g.admin:
        return True
    data = request.get_json()
    if not data:
        data = request.form
    if data.get('privileged'):
        logger.debug("User is trying to set privileged")
        # if we're here, user isn't an admin so must have privileged role:
        if not codes.PRIVILEGED_ROLE in g.roles:
            logger.info("User does not have privileged role.")
            raise PermissionsException("Not authorized -- only admins and privileged users can make privileged actors.")
        else:
            logger.debug("user allowed to set privileged.")
            return True
    else:
        logger.debug("not trying to set privileged.")
        return True

def check_permissions(user, actor_id, level):
    """Check the permissions store for user and level"""
    logger.debug("Checking user: {} permissions for actor id: {}".format(user, actor_id))
    # get all permissions for this actor
    permissions = get_permissions(actor_id)
    for pem in permissions:
        # if the actor has been shared with the WORLD_USER anyone can use it
        if user == WORLD_USER:
            logger.info("Allowing request - actor has been shared with the WORLD_USER.")
            return True
        # otherwise, check if the permission belongs to this user and has the necessary level
        if pem['user'] == user:
            if pem['level'] >= level:
                logger.info("Allowing request - user has appropriate permission with the actor.")
                return True
    return False

def get_db_id():
    """Get the db_id from the request path."""
    path_split = request.path.split("/")
    if len(path_split) < 3:
        logger.error("Unrecognized request -- could not find the actor id. path_split: {}".format(path_split))
        raise PermissionsException("Not authorized.")
    actor_id = path_split[2]
    logger.debug("actor_id: {}".format(actor_id))
    return Actor.get_dbid(g.tenant, actor_id)
