import os
import logging
import argparse
import paramiko
import pyinotify
import ConfigParser
from string import Template
from subprocess import call

logging.basicConfig()
logger = logging.getLogger("saxs-archive")

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
            if self._config['compress']:
                options += "z"
            if self._config['checksum']:
                options += "c"
            
            # run the rsync process
            # --append ?
            # --exclude ? pattern?
            call(["rsync", options, "-e ssh",
                  source, "%s@%s:%s"%(self._config['user'],
                                      self._config['host'],
                                      target)])

            # change the permission of the files
            _, stdout, stderr = \
                client.exec_command("chmod -R %s %s"%(self._config['chmod'],
                                                      target))
            if stderr.read() != "":
                logger.error("Couldn't change the permission: %s"%stderr)

            # change the ownership of the files
            _, stdout, stderr = \
                client.exec_command("chown -R %s:%s %s"%(self._config['owner'],
                                                         self._config['group'],
                                                         target))
            if stderr.read() != "":
                logger.error("Couldn't change the ownership: %s"%stderr)

            client.close()
        except paramiko.SSHException, e:
            logger.error("SSH connection threw an exception: %s"%e)
            client.close()
        return


#========================================
#              Main script
#========================================
settings = {}

# parse the command line arguments
parser = argparse.ArgumentParser(prog='saxs-archive',
                                 description='realtime data archiver')
parser.add_argument('<config_file>', action='store',
                     help='Path to configuration file')
args = vars(parser.parse_args())

# read the configuration file
conf = ConfigParser.ConfigParser()
conf.read(args['<config_file>'])

# read the configuration values
settings['compress'] = conf.getboolean('rsync', 'compress')
settings['checksum'] = conf.getboolean('rsync', 'checksum')
settings['watch'] = conf.get('source', 'watch')
settings['src_folder'] = conf.get('source', 'folder')
settings['host'] = conf.get('target', 'host')
settings['user'] = conf.get('target', 'user')
settings['tar_folder'] = conf.get('target', 'folder')
settings['chmod'] = conf.get('target', 'permission')
settings['owner'] = conf.get('target', 'owner')
settings['group'] = conf.get('target', 'group')


#----------------------------------
#  Settings and validation checks
#----------------------------------
# check if the watchfolder exists
if not os.path.isdir(settings['watch']):
    logger.error("The watch folder '%s' doesn't exist!"%settings['watch'])
    exit()

# build the folder list
settings['src_folder_list'] = settings['src_folder'].split('/')

# check if all keys in the target folder string have been declared in the
# source folder string
try:
    check_dict = {}
    for token in settings['src_folder_list']:
        if token.startswith('${') and token.endswith('}'):
            check_dict[token[2:len(token)-1]] = ""
    Template(settings['tar_folder']).substitute(check_dict)
except KeyError, e:
    logger.error("Key %s doesn't exist in the source folder settings!"%e)
    exit()

# check if the target host is reachable (uses key pair authentication)
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    client.connect(settings['host'], username=settings['user'])
    client.close()
except paramiko.SSHException, e:
    logger.error("Can't connect to target host: %s"%e)
    client.close()
    exit()


#--------------------------------
#      Notification system
#--------------------------------
# create the watch manager, event handler and notifier
watch_manager = pyinotify.WatchManager()
handler = EventHandler(settings)
notifier = pyinotify.Notifier(watch_manager, handler)

# add the watch directory to the watch manager
watch_manager.add_watch(settings['watch'], pyinotify.IN_CLOSE_WRITE, rec=True)

# start watching
notifier.loop()
