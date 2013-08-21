import logging
import argparse
import pyinotify
from changeover import settings, eventhandler
from common import saxslog

def main():
    """
    The main method of the event based rsync tool for the SAXS-WAXS beamline
    """
    #--------------------------------
    #       Settings & Logging
    #--------------------------------
    # parse the command line arguments
    parser = argparse.ArgumentParser(prog='changeover-rsync',
                                     description='event based rsync tool')
    parser.add_argument('<config_file>', action='store',
                         help='Path to configuration file')
    args = vars(parser.parse_args())

    # read the configuration file
    config = settings.read(args['<config_file>'])

    # setup the global logging
    logger, raven_client = saxslog.setup(config, "changeover-rsync")
    if raven_client != None:
        saxslog.setup_logging(saxslog.SentryHandler(raven_client))
        logger.info("Raven is available. Logging will be sent to Sentry")

    # settings and validation checks
    if not settings.validate(config):
        exit()


    #--------------------------------
    #      Notification system
    #--------------------------------
    # create the watch manager, event handler and notifier
    watch_manager = pyinotify.WatchManager()
    handler = eventhandler.EventHandler(config)
    notifier = pyinotify.Notifier(watch_manager, handler)

    # add the watch directory to the watch manager
    watch_manager.add_watch(config['watch'], pyinotify.IN_CLOSE_WRITE,
                            rec=True, auto_add=True)
    logger.info("Created the notification system and added the watchfolder")

    # start watching
    logger.info("Waiting for notifications...")
    notifier.loop()
