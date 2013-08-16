import os
import logging
import paramiko
import ConfigParser
from string import Template

logger = logging.getLogger("saxs-archive:settings")

def read(conf_path):
    """
    Read the settings from the specified file.
    conf_path: The path to the settings file
    Returns a dictionary with the settings.
    """
    conf = ConfigParser.ConfigParser()
    conf.read(conf_path)

    # read the settings
    settings = {}
    settings['debug'] = conf.getboolean('logging', 'debug')
    settings['sentry'] = conf.get('logging', 'sentry')
    settings['compress'] = conf.getboolean('rsync', 'compress')
    settings['checksum'] = conf.getboolean('rsync', 'checksum')
    settings['watch'] = conf.get('source', 'watch')
    settings['src_folder'] = conf.get('source', 'folder')
    settings['host'] = conf.get('target', 'host')
    settings['user'] = conf.get('target', 'user')
    settings['sudo'] = conf.getboolean('target', 'sudo')
    settings['tar_folder'] = conf.get('target', 'folder')
    settings['chmod'] = conf.get('target', 'permission')
    settings['owner'] = conf.get('target', 'owner')
    settings['group'] = conf.get('target', 'group')

    # build the source folder list
    settings['src_folder_list'] = settings['src_folder'].split('/')

    return settings


def validate(settings, raven_client=None):
    """
    Performs a validation of the settings.
    settings: Reference to the settings dictionary that should be validated.
    raven_client: Optional reference to a raven client to log exceptions.
    Returns True if the settings are valid, otherwise False is returned.
    """
    # check if the watchfolder exists
    if not os.path.isdir(settings['watch']):
        logger.error("The watch folder '%s' doesn't exist!"%settings['watch'])
        return False
    logger.info("Watchfolder exists and is valid")

    # check if all keys in the target folder string have been declared in the
    # source folder string
    try:
        check_dict = {}
        for token in settings['src_folder_list']:
            if token.startswith('${') and token.endswith('}'):
                check_dict[token[2:len(token)-1]] = ""
        Template(settings['tar_folder']).substitute(check_dict)
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
        client.connect(settings['host'], username=settings['user'])
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
