import argparse
from flask import Flask
from common import saxslog
from changeover.common import settings

# parse the command line arguments
parser = argparse.ArgumentParser(prog='changeover-server',
                                 description='server to manage the changeover')
parser.add_argument('<config_file>', action='store',
                    help='Path to configuration file')
args = vars(parser.parse_args())

# read the configuration file
settings.read(args['<config_file>'])

# setup the global logging
logger, raven_client = saxslog.setup("changeover-server",
                                     settings.Settings()['logging']['debug'],
                                     settings.Settings()['logging']['sentry'])
if raven_client != None:
    saxslog.setup_logging(saxslog.SentryHandler(raven_client))
    logger.info("Raven is available. Logging will be sent to Sentry")

app = Flask(__name__)

from changeover.server import views
