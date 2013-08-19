import os
import logging
import argparse
import paramiko
import pyinotify
from changeover import settings, syncutils
from common import saxslog

class EventHandler(pyinotify.ProcessEvent):
    """
    The handler for processing the pyinotify event.
    """

    def __init__(self, config, logger, raven_client):
        """
        Store the configuration.
        config: The configuration dictionary
        """
        self._config = config
        self._logger = logger
        self._raven_client = raven_client

    def process_IN_CLOSE_WRITE(self, event):
        """
        Process events that were triggered by closing a file after having
        written into it.
        event: The event that triggered this method
        """
        # check the length of the triggered path
        trg_path_list = event.path.split('/')
        src_path_list = self._config['src_folder_list']
        if len(trg_path_list) < len(self._config['src_folder_list']):
            self._logger.error("The triggered path is shorter than the source path!")
            return

        # build the source and target paths for rsync
        try:
            source, target = syncutils.build_sync_paths(trg_path_list,
                                                        self._config)
        except Exception, e:
            self._logger.error(e)

        # Copy the files to the archive
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(self._config['host'], username=self._config['user'])

            # if the remote directory doesn't exist, create it
            if not syncutils.mkdir_remote(client, target, self._config):
                self._logger.error("Couldn't create target directory: %s"%target)
                client.close()
                return

            # set the rsync options
            options = "-a"
            options += "z" if self._config['compress'] else ""
            options += "c" if self._config['checksum'] else ""
            
            try:    
                # run the rsync process
                syncutils.run_rsync(source, target, options, self._config)

                # change the permission of the files
                #syncutils.change_permissions(client, target, self._config)
            except Exception, e:
                self._logger.error(e)

            client.close()
        except paramiko.SSHException, e:
            if raven_available:
                self._raven_client.captureException()
            else:
                self._logger.error("SSH connection threw an exception: %s"%e)
            client.close()


def main():
    """
    The main method of the event based rsync tool for the SAXS-WAXS beamline
    """
    # parse the command line arguments
    parser = argparse.ArgumentParser(prog='changeover-rsync',
                                     description='event based rsync tool')
    parser.add_argument('<config_file>', action='store',
                         help='Path to configuration file')
    args = vars(parser.parse_args())

    # read the configuration file
    config = settings.read(args['<config_file>'])

    # setup the logging
    logger, raven_client = saxslog.setup(config, "changeover-rsync")

    # settings and validation checks
    if not settings.validate(config, raven_client):
        exit()

    # create the watch manager, event handler and notifier
    watch_manager = pyinotify.WatchManager()
    handler = EventHandler(config, logger, raven_client)
    notifier = pyinotify.Notifier(watch_manager, handler)

    # add the watch directory to the watch manager
    watch_manager.add_watch(config['watch'], pyinotify.IN_CLOSE_WRITE, rec=True, auto_add=True)
    logger.info("Created the notification system and added the watchfolder")

    # start watching
    logger.info("Waiting for notifications...")
    notifier.loop()
