"""Set up the log handlers for the Abaco system."""

import logging


def get_file_handler(logfile):
    """Returns a log file handler that writes to the file logfile."""
    handler = logging.FileHandler(logfile)
    handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s '
        '[in %(pathname)s:%(lineno)d]'
    ))
    handler.setLevel(logging.DEBUG)
    return handler