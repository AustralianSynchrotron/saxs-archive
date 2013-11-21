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


def folders():
    """
    Return a list of the source and their associated target folders together
    with a flag that indicates if the target folder exists.
    """
    result = {}
    conf = Settings()

    # get the list of source folders
    src_folders = syncutils.get_source_folders()

    # connect to the remote server
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        client.connect(conf['target']['host'],
                       username=conf['target']['user'], timeout=10)

        # iterate over the source folders
        for src_folder in src_folders:
            source, target = syncutils.build_sync_paths(src_folder)

            # check if the target folder exists
            target_exists = False
            cmd = "[ -d \"%s\" ] && echo \"True\" || echo \"False\""%target
            _, stdout, stderr = client.exec_command(cmd)
            err = stderr.read()
            if err:
                logger.error("Couldn't check target folder: %s"%err.rstrip())
            else:
                if stdout.read().rstrip() == "True":
                    target_exists = True

            result[source] = {'target': target,
                              'exists': target_exists}
    
    except (paramiko.SSHException, socket.error), e:
        logger.error("Can't connect to target host: %s"%e)
    
    finally:
        client.close()
        return result


def files(source, target):
    """
    Returns a file list comparing the specified source and target folders.
    Assumes the target folder exists!
    """
    result = {'files': {}}
    if (not source) or (not target):
        return result

    conf = Settings()
    regex = re.compile(conf['source']['exclude'])
    datetime_epoch = datetime.datetime(1970, 1, 1)

    # create source file list
    src_files = {}
    file_list = [f for f in os.listdir(source) \
                 if os.path.isfile(os.path.join(source, f))]
    for f in file_list:
        if regex.search(f) == None:
            filename = os.path.join(source, f)
            src_files[f] = (os.path.getsize(filename),
                            int(os.path.getmtime(filename)))

    # create target file list
    trg_files = {}
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(conf['target']['host'],
                       username=conf['target']['user'], timeout=10)

        # get the list of files
        cmd = "TZ=\"UTC\" ls -l --time-style=full-iso %s"%target
        _, stdout, stderr = client.exec_command(cmd)
        err = stderr.read()
        if err:
            logger.error("Couldn't return remote file list: %s"%err.rstrip())
        else:
            file_list = stdout.read().split("\n")
            for f in file_list:
                ft = f.split()
                if len(ft) > 8:
                    trg_files[ft[8]] = (int(ft[4]),
                     int((dateutil.parser.parse(ft[5]+"T"+ft[6])-datetime_epoch).total_seconds()))

    except (paramiko.SSHException, socket.error), e:
        logger.error("Can't connect to target host: %s"%e)

    finally:
        client.close()

    # build result by comparing the source with the target list
    for key, value in src_files.iteritems():
        result['files'][key] = {'exists'   : key in trg_files,
                                'same_size': (key in trg_files) and \
                                             (trg_files[key][0] == value[0]),
                                'same_date': (key in trg_files) and \
                                             (trg_files[key][1] == value[1])}
    return result
