import os
import json
import re
import logging
import paramiko
import socket
import datetime
import dateutil
from subprocess import Popen, PIPE
from changeover.common import syncutils
from changeover.common.settings import Settings

logger = logging.getLogger(__name__)


def diff():
    result = {}
    conf = Settings()
    regex = re.compile(conf['source']['exclude'])
    datetime_epoch = datetime.datetime(1970,1,1)

    # get the list of source folders
    src_folders = syncutils.get_source_folders()

    # iterate over the source folders
    for src_folder in src_folders:
        source, target = syncutils.build_sync_paths(src_folder.split("/"))

        # create source file list
        src_files = {}
        file_list = [f for f in os.listdir(source) \
                     if os.path.isfile(os.path.join(source, f))]
        for f in file_list:
            if regex.search(f) == None:
                filename = os.path.join(source, f)
                src_files[f] = (os.path.getsize(filename), int(os.path.getmtime(filename)))

        # create target file list
        trg_files = {}
        trg_folder_exists = False
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(conf['target']['host'],
                           username=conf['target']['user'], timeout=10)

            # check if the target folder exists
            _, stdout, stderr = client.exec_command("[ -d \"%s\" ] && echo \"True\" || echo \"False\""%target)
            err = stderr.read()
            if err:
                logger.error("Couldn't check existence of target folder: %s"%err.rstrip())
            else:
                if stdout.read().rstrip() == "True":
                    trg_folder_exists = True

            if trg_folder_exists:
                # get the list of files
                _, stdout, stderr = client.exec_command("TZ=\"UTC\" ls -l --time-style=full-iso %s"%target)
                err = stderr.read()
                if err:
                    logger.error("Couldn't return remote file list: %s"%err.rstrip())
                else:
                    file_list = stdout.read().split("\n")
                    for f in file_list:
                        ft = f.split()
                        if len(ft) > 8:
                            trg_files[ft[8]] = (int(ft[4]),
                                int((dateutil.parser.parse(ft[5]+"T"+ft[6])-datetime_epoch).total_seconds())
                                                )

            client.close()
        except (paramiko.SSHException, socket.error), e:
            logger.error("Can't connect to target host: %s"%e)
            client.close()

        # build result
        if trg_folder_exists:
            result[source] = {'trg_folder_exists': True,
                              'files': {}}

            # compare source with target list
            for key, value in src_files.iteritems():
                result[source]['files'][key] = {'trg_file_exists': key in trg_files,
                                                'same_size': (key in trg_files) and \
                                                             (trg_files[key][0] == value[0]),
                                                'same_date': (key in trg_files) and \
                                                             (trg_files[key][1] == value[1])}
                if key in trg_files:
                    print trg_files[key][1], value[1]

        else:
            result[source] = {'trg_folder_exists': False,
                              'files': {}}
        
    return result
