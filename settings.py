import ConfigParser

def read(conf_path):
    conf = ConfigParser.ConfigParser()
    conf.read(conf_path)

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

    return settings
