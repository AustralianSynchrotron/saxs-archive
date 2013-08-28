import logging
import argparse
from changeover.common import settings, watchtree
from changeover.rsync import eventhandler
from common import saxslog

# parse the command line arguments
parser = argparse.ArgumentParser(prog='changeover-rsync',
                                 description='event based rsync tool')
parser.add_argument('<config_file>', action='store',
                    help='Path to configuration file')
args = vars(parser.parse_args())

# read the configuration file
settings.read(args['<config_file>'])

# setup the global logging
logger, raven_client = saxslog.setup("changeover-rsync",
                                     settings.Settings()['logging']['debug'],
                                     settings.Settings()['logging']['sentry'])
if raven_client != None:
    saxslog.setup_logging(saxslog.SentryHandler(raven_client))
    logger.info("Raven is available. Logging will be sent to Sentry")

# create the watch tree
wt = watchtree.WatchTree(eventhandler.EventHandler(),
                         settings.Settings()['source']['exclude'],
                         int(settings.Settings()['rsync']['delay']))
wt.create(settings.Settings()['source']['watch'])
logger.info("Created the watch tree notification system")
