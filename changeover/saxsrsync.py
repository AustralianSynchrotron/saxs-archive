import os
import logging
import argparse
import paramiko
import pyinotify
from changeover import settings
from common import saxslog
from string import Template
from subprocess import call

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
        if len(trg_path_list) < len(src_path_list):
            self._logger.error("The triggered path is shorter than the source path!")
            return

        # match the path elements between the triggered and the source path
        # and extract the template values from the triggered path
        tmp_dict = {}
        for i in range(len(src_path_list)):
            trg_element = trg_path_list[i]
            path_element = src_path_list[i]
            if path_element.startswith('${') and path_element.endswith('}'):
                tmp_dict[path_element[2:len(path_element)-1]] = trg_element
            else:
                if path_element != trg_element:
                    self._logger.error("Non matching path element '%s' \
                                        found in triggered path!"%trg_element)
                    return

        # substitute the template parameters in the source and target path
        source = Template(self._config['src_folder']).substitute(tmp_dict)
        target = Template(self._config['tar_folder']).substitute(tmp_dict)

        # make sure the paths end with a trailing slash
        if not source.endswith("/"):
            source += "/."

        if not target.endswith("/"):
            target += "/"

        # Copy the files to the archive
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(self._config['host'], username=self._config['user'])

            # check if the remote directory already exists. If not, create it
            _, stdout, stderr = \
                client.exec_command("[ -d %s ] || mkdir -p %s"%(target, target))
            if stderr.read() != "":
                self._logger.error("Couldn't create target directory: %s"%stderr)
                client.close()
                return

            # set the rsync options
            options = "-aq"
            options += "z" if self._config['compress'] else ""
            options += "c" if self._config['checksum'] else ""
                
            # run the rsync process
            call(["rsync", options, "-e ssh",
                  source, "%s@%s:%s"%(self._config['user'],
                                      self._config['host'],
                                      target)])

            # change the permission of the files
            sudo_str = "sudo " if self._config['sudo'] else ""

            _, stdout, stderr = \
                client.exec_command("%schmod -R %s %s"%(sudo_str,
                                                        self._config['chmod'],
                                                        target))
            if stderr.read() != "":
                self._logger.error("Couldn't change the permission: %s"%stderr)

            # change the ownership of the files
            _, stdout, stderr = \
                client.exec_command("%schown -R %s:%s %s"%(sudo_str,
                                                           self._config['owner'],
                                                           self._config['group'],
                                                           target))
            if stderr.read() != "":
                self._logger.error("Couldn't change the ownership: %s"%stderr)

            client.close()
        except paramiko.SSHException, e:
            if raven_available:
                self._raven_client.captureException()
            else:
                self._logger.error("SSH connection threw an exception: %s"%e)
            client.close()
        return


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

    # Settings and validation checks
    if not settings.validate(config, raven_client):
        exit()

    # create the watch manager, event handler and notifier
    watch_manager = pyinotify.WatchManager()
    handler = EventHandler(config, logger, raven_client)
    notifier = pyinotify.Notifier(watch_manager, handler)

    # add the watch directory to the watch manager
    watch_manager.add_watch(config['watch'], pyinotify.IN_CLOSE_WRITE, rec=True)
    logger.info("Created the notification system and added the watchfolder")

    # start watching
    logger.info("Waiting for notifications...")
    notifier.loop()
