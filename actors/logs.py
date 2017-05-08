"""Set up the loggers for the Abaco system."""

import logging
import configparser

from config import Config

LEVELS = ('CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG',)
LOG_FILE = '/var/log/abaco.log'
LEVEL = 'INFO'
LOG_FILE_STRATEGIES = ('split', 'combined')
LOG_FILE_STRATEGY_DEFAULT = 'combined'

def get_log_file_strategy():
    """
    Returns the strategy for writing logs to files based on the config.
    The string "combined" means the logs should be written to a single file, abaco.log, while the string
    "split" means the logs should be split to different files, depending on the Abaco agent.
    """
    try:
        strategy = Config.get('logs', 'files')
    except (configparser.NoSectionError, configparser.NoOptionError):
        # default to collecting all logs to a single file
        strategy = LOG_FILE_STRATEGY_DEFAULT
    if strategy.lower() not in LOG_FILE_STRATEGIES:
        return LOG_FILE_STRATEGY_DEFAULT
    return strategy.lower()


def get_module_log_level(name):
    """Reads config file for a log level set for this module."""
    try:
        log_level = Config.get('logs', 'level.{}'.format(name))
    except configparser.NoSectionError:
        # if the logs section doesn't exist, use default
        return LEVEL
    except configparser.NoOptionError:
        # if the module doesn't have a specific level, see of there is a global config:
        try:
            log_level = Config.get('logs', 'level')
        except configparser.NoOptionError:
            return LEVEL
    if log_level.upper() in LEVELS:
        return log_level
    else:
        return LEVEL

def get_log_file(name):
    """
    Reads config file for a log file to record logs for this module.
    If a file isn't specified for the module, looks for a global config. Otherwise, returns the
    default.

    Note: These paths refer to container paths, and the files must already exist. Since separate host files can be
    mounted to the container, it it likely that this configuration is not needed.
    """
    try:
        log_file = Config.get('logs', 'file.{}'.format(name))
    except configparser.NoSectionError:
        # if the logs section doesn't exist, return the default
        return LOG_FILE
    except configparser.NoOptionError:
        # if the module doesn't have a specific file, check for a global config:
        try:
            log_file = Config.get('logs', 'file')
        except configparser.NoOptionError:
            return LOG_FILE
    return log_file


def get_logger(name):
    """
    Returns a properly configured logger.
         name (str) should be the module name.
    """
    logger = logging.getLogger(name)
    level = get_module_log_level(name)
    logger.setLevel(level)
    handler = logging.FileHandler(get_log_file(name))
    handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s '
        '[in %(pathname)s:%(lineno)d]'
    ))
    handler.setLevel(level)
    logger.addHandler(handler)
    logger.info("returning a logger set to level: {} for module: {}".format(level, name))
    return logger
