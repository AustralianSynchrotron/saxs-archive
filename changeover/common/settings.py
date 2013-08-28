import os
import paramiko
import ConfigParser
from string import Template
from common import saxslog

class ChangeoverParser(ConfigParser.ConfigParser):
    """
    Extends the ConfigParser by a method that returns a dictionary of the
    settings file and converts "true" and "false" strings to Boolean values.
    """
    def to_dict(self):
        """
        Returns a dictionary of the settings file
        """
        conf_dict = dict(self._sections)
        for key in conf_dict:
            conf_dict[key] = dict(self._defaults, **conf_dict[key])
            for k, v in conf_dict[key].iteritems():
                if v.lower() in ["true", "false"]:
                    conf_dict[key][k] = bool(v)
            conf_dict[key].pop('__name__', None)
        return conf_dict


class __SettingsSingleton(object):
    d = {}


def Settings():
    return __SettingsSingleton().d


def read(conf_path):
    """
    Read the settings from the specified configuration file and builds a
    dictionary.
    conf_path: The path to the settings file
    """
    conf_parser = ChangeoverParser()
    conf_parser.read(conf_path)
    Settings().clear()
    Settings().update(conf_parser.to_dict())

    # build the source folder list
    conf = Settings()
    conf['source']['folder_list'] = conf['source']['folder'].split('/')

    # set the statistics file configuration
    conf['statistics']['has_year'] = (conf['statistics']['file'].find("${year}") > -1)
    conf['statistics']['has_month'] = (conf['statistics']['file'].find("${month}") > -1)
    conf['statistics']['has_day'] = (conf['statistics']['file'].find("${day}") > -1)


def validate():
    """
    Performs a validation of the settings.
    Returns True if the settings are valid, otherwise False is returned.
    """
    conf = Settings()
    logger, raven_client = saxslog.setup(__name__,
                                        conf['logging']['debug'],
                                        conf['logging']['sentry'])

    # check if the watchfolder exists
    if not os.path.isdir(conf['source']['watch']):
        logger.error("The watch folder '%s' doesn't exist!"%conf['source']['watch'])
        return False
    logger.info("Watchfolder exists and is valid")

    # check if all keys in the target folder string have been declared in the
    # source folder string
    try:
        check_dict = {}
        for token in conf['source']['folder_list']:
            if token.startswith('${') and token.endswith('}'):
                check_dict[token[2:len(token)-1]] = ""
        Template(conf['target']['folder']).substitute(check_dict)
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
        client.connect(conf['target']['host'], username=conf['target']['user'])
        client.close()
        logger.info("Connection to the target host was successfully established")
    except paramiko.SSHException, e:
        if raven_client != None:
            raven_client.captureException()
        else:
            logger.error("Can't connect to target host: %s"%e)
        client.close()
        return False

    # check if the statistics filename has either no or a valid list of
    # template parameters.
    has_year = conf['statistics']['has_year']
    has_month = conf['statistics']['has_month']
    has_day = conf['statistics']['has_day']
    if (has_day and not (has_month and has_year)) or \
       (has_month and not has_year):
        logger.error("The statistics filename has to contain either no "+
                     "template parameters or a non-ambiguous combination "+
                     "of '${day}' '${year}' and '${month}'")
        return False

    return True
