"""Module to determine file system mounts for an actor."""

import configparser
from config import Config

from agaveflask.logs import get_logger
logger = get_logger(__name__)


def replace_tokens(s, actor):
    """Replaces the following tokens in a string based on a dictionary representing an actor:
         tenant_id: the tenant id associated with the actor.
         username: the username of the owner of the actor.
         tas_homeDirectory: the homeDirectory attribute returned from tas. This attribute requires the
                            use_tas_uid config must be set to true.
    """
    logger.debug("top of replace_tokens for string: {}".format(s))
    s = s.replace('{username}', actor['owner'])
    s = s.replace('{tenant_id}', actor['tenant'])
    if '{tas_homeDirectory}' in s:
        if 'tas_homeDirectory' in actor:
                s = s.replace('{tas_homeDirectory}', actor['tas_homeDirectory'])
        else:
            logger.error("actor did not have a tas_homeDirectory though "
                         "there is one in the mounts string. s: {}. actor: {}".format(s, actor))
            # better to return an empty string in this case:
            return ''
    return s


def process_mount_strs(mount_strs, actor):
    """Process the mount_strs list including token replacement for recognized attributes."""
    result = []
    if not mount_strs:
        return result
    mounts = mount_strs.split(",")
    for m in mounts:
        parts = m.split(":")
        if not len(parts) == 3:
            # we will "swallow" invalid global_mounts config since this is not something the user can fix;
            # however, we log an error:
            logger.error("Invalid global_mounts config. "
                         "Each config must be two paths and a format separated by a colon: {}".format(m))
        else:
            host_path = replace_tokens(parts[0], actor)
            container_path = replace_tokens(parts[1], actor)
            mode = parts[2]
            if host_path == '' or container_path == '':
                logger.info("skipping mount due to empty string. "
                            "host_path: {}. container_path: {}".format(host_path, container_path))
            else:
                result.append({'host_path': host_path,
                               'container_path': container_path,
                               'mode': mode})
    logger.info("Returning global mounts: {}".format(result))
    return result


def get_global_mounts(actor):
    """
    Read and parse the global_mounts config.
    Returns a list of dictionaries containing host_path, container_path and mode.
    """
    try:
        mount_strs = Config.get("workers", "global_mounts")
    except configparser.NoOptionError:
        logger.info("No workers.global_mounts config. Skipping.")
        mount_strs = None
    return process_mount_strs(mount_strs, actor)


def get_privileged_mounts(actor):
    """
    Read and parse the global_mounts config.
    Returns a list of dictionaries containing host_path, container_path and mode.
    """
    try:
        mount_strs = Config.get("workers", "privileged_mounts")
    except configparser.NoOptionError:
        logger.info("No workers.privileged_mounts config. Skipping.")
        mount_strs = None
    return process_mount_strs(mount_strs, actor)


def get_all_mounts(actor):
    """Get all mounts for a given actor description, actor. This function is called at registration
    time to set the mounts parameter for the actor.
    """
    # get the global mounts first and then get the privileged mounts so that privileged mounts overlay.
    logger.debug("top of get_all_mounts for actor: {}".format(actor))
    result = get_global_mounts(actor)
    logger.debug("just got the global mounts: {}".format(result))
    if actor.get('privileged'):
        logger.debug("getting the privileged mounts for actor: {}".format(actor))
        result.extend(get_privileged_mounts(actor))
    logger.debug("final mounts: {}".format(result))
    return result
