import os
import logging
import socket
import paramiko
from subprocess import Popen, PIPE
from changeover.common.settings import Settings

logger = logging.getLogger(__name__)


def rsync_running():
    conf = Settings()
    result = {'runs': False,
              'pid': "",
              'uptime': ""
             }
    
    # call the status action of supervisorctl
    cmd = conf['supervisor']['cmd'].split()
    cmd.append("status")
    proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    if stderr:
        logger.error("Error while calling supervisorctl: '%s'"%stderr)

    # parse the output
    for line in stdout.split("\n"):
        if conf['supervisor']['process'] in line:
            if "RUNNING" in line:
                result['runs'] = True
                pid_start = line.index("pid")+4
                result['pid'] = line[pid_start:line.index(",", pid_start)]
                result['uptime'] = line[line.index("uptime")+7:]
            return result

    logger.error("Couldn't find the supervisor process '%s'"\
                 %conf['supervisor']['process'])
    return result


def ssh_connected():
    conf = Settings()
    result = {'connected': False,
              'error_msg': ""
             }
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(conf['target']['host'],
                       username=conf['target']['user'], timeout=10)
        client.close()
        result['connected'] = True
    except (paramiko.SSHException, socket.error), e:
        logger.error("Can't connect to target host: %s"%e)
        result['error_msg'] = e
        client.close()
    return result
