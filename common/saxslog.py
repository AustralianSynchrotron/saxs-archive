import logging

# check if raven is available
try:
    from raven import Client
    from raven.conf import setup_logging
    from raven.handlers.logging import SentryHandler
    raven_available = True
except ImportError:
    raven_available = False


def setup(config, logger_name):
    """
    Setup the logging for the SAXS-WAXS archive tools.
    config: The configuration dictionary
    logger_name: The name of the logger
    Returns a reference to a logger instance and a raven client.
    If the raven module is not available, the raven client is None
    """
    logging.basicConfig()
    if config['debug']:
        logging.getLogger().setLevel(logging.INFO)
    else:
        logging.getLogger().setLevel(logging.ERROR)

    if raven_available and config['sentry']:
        return logging.getLogger(logger_name), Client(config['sentry'])
    else:
        return logging.getLogger(logger_name), None
