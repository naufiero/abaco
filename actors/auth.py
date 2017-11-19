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
import requests

from agaveflask.auth import authn_and_authz as agaveflask_az
from agaveflask.logs import get_logger
logger = get_logger(__name__)

from agaveflask.utils import ok, RequestParser

from config import Config
import codes
from errors import PermissionsException
from models import Actor, get_permissions

from errors import ResourceError
from stores import actors_store, permissions_store



jwt.verify_methods['SHA256WITHRSA'] = (
    lambda msg, key, sig: PKCS1_v1_5.new(key).verify(SHA256.new(msg), sig))
jwt.prepare_key_methods['SHA256WITHRSA'] = jwt.prepare_RS_key


def get_pub_key():
    pub_key = Config.get('web', 'apim_public_key')
    return RSA.importKey(base64.b64decode(pub_key))


PUB_KEY = get_pub_key()

TOKEN_RE = re.compile('Bearer (.+)')

WORLD_USER = 'ABACO_WORLD'

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
        if hasattr(request, 'url_rule'):
            logger.debug("request.url_rule: {}".format(request.url_rule))
            if hasattr(request.url_rule, 'rule'):
                logger.debug("url_rule.rule: {}".format(request.url_rule.rule))
            else:
                logger.info("url_rule has no rule.")
                raise ResourceError("Invalid request: the API endpoint does not exist or the provided HTTP method is not allowed.", 405)
        else:
            logger.info("Request has no url_rule")
            raise ResourceError(
                "Invalid request: the API endpoint does not exist or the provided HTTP method is not allowed.", 405)
    logger.debug("request.path: {}".format(request.path))
    # the admin API requires the admin role:
    if 'admin' in request.path or '/actors/admin' in request.url_rule.rule or '/actors/admin/' in request.url_rule.rule:
        if g.admin:
            return True
        else:
            raise PermissionError("Abaco Admin role required.")

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

    # when using the UID associated with the user in TAS, admins can still register actors
    # to use the UID built in the container using the use_container_uid flag:
    if Config.get('workers', 'use_tas_uid'):
        if data.get('use_container_uid') or data.get('useContainerUid'):
            logger.debug("User is trying to use_container_uid")
            # if we're here, user isn't an admin so must have privileged role:
            if not codes.PRIVILEGED_ROLE in g.roles:
                logger.info("User does not have privileged role.")
                raise PermissionsException("Not authorized -- only admins and privileged users can use container uid.")
            else:
                logger.debug("user allowed to use container uid.")
    else:
        logger.debug("not trying to use privileged options.")
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

def get_tenant_verify(tenant):
    """Return whether to turn on SSL verification."""
    # sandboxes and the develop instance have a self-signed certs
    if 'SANDBOX' in tenant.upper():
        return False
    if tenant.upper() == 'DEV-DEVELOP':
        return False
    return True

def get_tenants():
    """Return a list of tenants"""
    return ['AGAVE-PROD',
            'ARAPORT-ORG',
            'DESIGNSAFE',
            'DEV-DEVELOP',
            'DEV-STAGING',
            'IPLANTC-ORG',
            'IREC',
            'SD2E',
            'SGCI',
            'TACC-PROD',
            'VDJSERVER-ORG']


# TAS configuration:
# base URL for TAS API.
TAS_URL_BASE = os.environ.get('TAS_URL_BASE', 'https://tas.tacc.utexas.edu/api/v1')
TAS_ROLE_ACCT = os.environ.get('TAS_ROLE_ACCT', 'tas-jetstream')
TAS_ROLE_PASS = os.environ.get('TAS_ROLE_PASS')


def get_tas_data(username):
    """Get the TACC uid, gid and homedir for this user from the TAS API."""
    logger.debug("Top of get_tas_data for username: {}".format(username))
    if not TAS_ROLE_ACCT:
        logger.error("No TAS_ROLE_ACCT configured. Aborting.")
        return
    if not TAS_ROLE_PASS:
        logger.error("No TAS_ROLE_PASS configured. Aborting.")
        return
    url = '{}/users/username/{}'.format(TAS_URL_BASE, username)
    headers = {'Content-type': 'application/json',
               'Accept': 'application/json'
               }
    try:
        rsp = requests.get(url,
                           headers=headers,
                           auth=requests.auth.HTTPBasicAuth(TAS_ROLE_ACCT, TAS_ROLE_PASS))
    except Exception as e:
        logger.error("Got an exception from TAS API. "
                       "Exception: {}. url: {}. TAS_ROLE_ACCT: {}".format(e, url, TAS_ROLE_ACCT))
        return
    try:
        data = rsp.json()
    except Exception as e:
        logger.error("Did not get JSON from TAS API. rsp: {}"
                       "Exception: {}. url: {}. TAS_ROLE_ACCT: {}".format(rsp, e, url, TAS_ROLE_ACCT))
        return
    try:
        tas_uid = data['result']['uid']
        tas_homedir = data['result']['homeDirectory']
    except Exception as e:
        logger.error("Did not get attributes from TAS API. rsp: {}"
                       "Exception: {}. url: {}. TAS_ROLE_ACCT: {}".format(rsp, e, url, TAS_ROLE_ACCT))
        return
    # if the instance has a configured TAS_GID to use we will use that; otherwise,
    # we fall back on using the user's uid as the gid, which is (almost) always safe)
    tas_gid = os.environ.get('TAS_GID', tas_uid)
    logger.info("Setting the following TAS data: uid:{} gid:{} homedir:{}".format(tas_uid,
                                                                                  tas_gid,
                                                                                  tas_homedir))
    return tas_uid, tas_gid, tas_homedir