import os
import logging
import argparse
import paramiko
import pyinotify
from changeover import settings, syncutils
from common import saxslog
from string import Template
from subprocess import call


def main():
    """
    """
    # parse the command line arguments
    parser = argparse.ArgumentParser(prog='saxs-changeover',
                                     description='validate copied files and create\
                                                  a new EPN folder structure')
    parser.add_argument('<config_file>', action='store',
                         help='Path to configuration file')
    parser.add_argument('<cycle>', action='store',
                         help='The cycle that should be setup')
    parser.add_argument('<epn>', action='store',
                         help='The EPN that should be setup')
    args = vars(parser.parse_args())

    # read the configuration file
    config = settings.read(args['<config_file>'])

    # setup the logging
    logger, raven_client = saxslog.setup(config, "changeover-switch")

    # settings and validation checks
    if not settings.validate(config, raven_client):
        exit()

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(config['host'], username=config['user'])

        # loop over all folders with a 'deepness' given by the
        # [source]/folder setting and rsync the files in those folders using the
        # checksum method.
        for root, dirs, files in os.walk(config['watch']):
            root_list = root.split('/')
            if len(root_list) == len(config['src_folder_list']):
                # build the source and target paths for rsync
                source, target = syncutils.build_sync_paths(root_list, config)
                logger.info("Synchronising content from '%s' to '%s'"%(source, target))

                # if the remote directory doesn't exist, create it
                if not syncutils.mkdir_remote(client, target):
                    logger.error("Couldn't create target directory: %s"\
                                       %stderr)
                    continue

                try:
                    # run the rsync process
                    syncutils.run_rsync(source, target, "-acz", config)

                    #TODO: collect the rsync output and print the stats as JSON

                    # change the permission of the files
                    syncutils.change_permissions(client, target, config)
                except Exception, e:
                    logger.error(e)
                    continue

        client.close()
    except paramiko.SSHException, e:
        if raven_available:
            raven_client.captureException()
        else:
            logger.error("SSH connection threw an exception: %s"%e)
        client.close()
