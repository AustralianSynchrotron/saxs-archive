#!/usr/bin/env python
#
# Copyright (c) 2013, Synchrotron Light Source Australia Pty Ltd
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#   * Redistributions of source code must retain the above copyright
#     notice, this list of conditions and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright
#     notice, this list of conditions and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the Australian Synchrotron nor the names of its contributors
#     may be used to endorse or promote products derived from this software
#     without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import os
import logging
import argparse
import paramiko
import pyinotify
import settings
from string import Template
from subprocess import call

# check if raven is available
try:
    from raven import Client
    from raven.conf import setup_logging
    from raven.handlers.logging import SentryHandler
    raven_available = True
except ImportError:
    raven_available = False

#========================================
#             Event handler
#========================================
class EventHandler(pyinotify.ProcessEvent):

    def __init__(self, config):
        self._config = config

    def process_IN_CLOSE_WRITE(self, event):
        # check the length of the triggered path
        trg_path_list = event.path.split('/')
        src_path_list = self._config['src_folder_list']
        if len(trg_path_list) < len(src_path_list):
            logger.error("The triggered path is shorter than the source path!")
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
                    logger.error("Non matching path element '%s' \
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
                logger.error("Couldn't create target directory: %s"%stderr)
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
                logger.error("Couldn't change the permission: %s"%stderr)

            # change the ownership of the files
            _, stdout, stderr = \
                client.exec_command("%schown -R %s:%s %s"%(sudo_str,
                                                           self._config['owner'],
                                                           self._config['group'],
                                                           target))
            if stderr.read() != "":
                logger.error("Couldn't change the ownership: %s"%stderr)

            client.close()
        except paramiko.SSHException, e:
            if raven_available:
                raven_client.captureException()
            else:
                logger.error("SSH connection threw an exception: %s"%e)
            client.close()
        return


#========================================
#              Main script
#========================================
# parse the command line arguments
parser = argparse.ArgumentParser(prog='saxs-archive',
                                 description='realtime data archiver')
parser.add_argument('<config_file>', action='store',
                     help='Path to configuration file')
args = vars(parser.parse_args())

# read the configuration file
config = settings.read(args['<config_file>'])


#----------------------------------
#             Logging
#----------------------------------
logging.basicConfig()
if config['debug']:
    logging.getLogger().setLevel(logging.INFO)
else:
    logging.getLogger().setLevel(logging.ERROR)

logger = logging.getLogger("saxs-archive")
if raven_available and config['sentry']:
    raven_client = Client(config['sentry'])
    setup_logging(SentryHandler(raven_client))
    logger.info("Raven is available. Logging will be sent to Sentry")


#----------------------------------
#  Settings and validation checks
#----------------------------------
# check if the watchfolder exists
if not os.path.isdir(config['watch']):
    logger.error("The watch folder '%s' doesn't exist!"%config['watch'])
    exit()
logger.info("Watchfolder exists and is valid")

# build the folder list
config['src_folder_list'] = config['src_folder'].split('/')

# check if all keys in the target folder string have been declared in the
# source folder string
try:
    check_dict = {}
    for token in config['src_folder_list']:
        if token.startswith('${') and token.endswith('}'):
            check_dict[token[2:len(token)-1]] = ""
    Template(config['tar_folder']).substitute(check_dict)
    logger.info("Source and target folder keys match")
except KeyError, e:
    if raven_available:
        raven_client.captureException()
    else:
        logger.error("Key %s doesn't exist in the source folder settings!"%e)
    exit()

# check if the target host is reachable (uses key pair authentication)
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    client.connect(config['host'], username=config['user'])
    client.close()
    logger.info("Connection to the target host was successfully established")
except paramiko.SSHException, e:
    if raven_available:
        raven_client.captureException()
    else:
        logger.error("Can't connect to target host: %s"%e)
    client.close()
    exit()


#--------------------------------
#      Notification system
#--------------------------------
# create the watch manager, event handler and notifier
watch_manager = pyinotify.WatchManager()
handler = EventHandler(config)
notifier = pyinotify.Notifier(watch_manager, handler)

# add the watch directory to the watch manager
watch_manager.add_watch(config['watch'], pyinotify.IN_CLOSE_WRITE, rec=True)
logger.info("Created the notification system and added the watchfolder")

# start watching
logger.info("Waiting for notifications...")
notifier.loop()