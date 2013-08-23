import os
import paramiko
import ConfigParser
from string import Template
from common import saxslog

class __SettingsSingleton(object):
    d = {}

def Settings():
    return __SettingsSingleton().d


def read(conf_path):
    """
    Read the settings from the specified configuration file.
    conf_path: The path to the settings file
    Returns a dictionary with the settings.
    """
    #default_values = {}
    conf = ConfigParser.ConfigParser()
    conf.read(conf_path)
    config = {}

    # [logging]
    config['debug'] = conf.getboolean('logging', 'debug')
    config['sentry'] = conf.get('logging', 'sentry')

    # [rsync]
    config['compress'] = conf.getboolean('rsync', 'compress')
    config['checksum'] = conf.getboolean('rsync', 'checksum')

    # [source]
    config['watch'] = conf.get('source', 'watch')
    config['src_folder'] = conf.get('source', 'folder')

    # [target]
    config['host'] = conf.get('target', 'host')
    config['user'] = conf.get('target', 'user')
    config['sudo'] = conf.getboolean('target', 'sudo')
    config['tar_folder'] = conf.get('target', 'folder')
    config['chmod'] = conf.get('target', 'permission')
    config['owner'] = conf.get('target', 'owner')
    config['group'] = conf.get('target', 'group')

    # [server]
    #config['server_name'] = conf.get('server', 'name', 'Detector')
    #config['server_host'] = conf.get('server', 'host')
    #config['server_port'] = conf.getint('server', 'port')

    # build the source folder list
    config['src_folder_list'] = config['src_folder'].split('/')

    # update singleton
    Settings().clear()
    Settings().update(config)


def validate():
    """
    Performs a validation of the settings.
    Returns True if the settings are valid, otherwise False is returned.
    """
    conf = Settings()
    logger, raven_client = saxslog.setup(__name__, conf['debug'], conf['sentry'])

    # check if the watchfolder exists
    if not os.path.isdir(conf['watch']):
        logger.error("The watch folder '%s' doesn't exist!"%conf['watch'])
        return False
    logger.info("Watchfolder exists and is valid")

    # check if all keys in the target folder string have been declared in the
    # source folder string
    try:
        check_dict = {}
        for token in conf['src_folder_list']:
            if token.startswith('${') and token.endswith('}'):
                check_dict[token[2:len(token)-1]] = ""
        Template(conf['tar_folder']).substitute(check_dict)
        logger.info("Source and target folder keys match")
    except KeyError, e:
        if raven_client != None:
            raven_client.captureException()
        else:
            logger.error("Key %s doesn't exist in the source folder settings!"%e)
        return False

    # check if the target host is reachable (uses key pair authentication)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(conf['host'], username=conf['user'])
        client.close()
        logger.info("Connection to the target host was successfully established")
    except paramiko.SSHException, e:
        if raven_client != None:
            raven_client.captureException()
        else:
            logger.error("Can't connect to target host: %s"%e)
        client.close()
        return False

    return True
