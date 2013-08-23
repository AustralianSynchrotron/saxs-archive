import paramiko
from changeover.common import syncutils, watchtree
from changeover.common.settings import Settings
from common import saxslog

class EventHandler(watchtree.WatchTreeFileHandler):
    """
    The handler class for processing the file notification events.
    """
    def __init__(self):
        """
        The constructor of the event handler.
        raven_client: (optional) The raven client for logging excpetions to
                      the Sentry server
        """
        self._logger, self._raven_client = saxslog.setup(__name__,
                                                         Settings()['debug'],
                                                         Settings()['sentry'])


    def process(self, path):
        """
        Run the rsync process after being notified of a change in the filesystem.
        path: The source path for the rsync process
        """
        conf = Settings()
        # check the length of the triggered path
        path_list = path.split('/')
        src_path_list = conf['src_folder_list']
        if len(path_list) < len(conf['src_folder_list']):
            self._logger.error("The triggered path is shorter than the source path!")
            return

        # build the source and target paths for rsync
        try:
            source, target = syncutils.build_sync_paths(path_list)
            self._logger.info("%s => %s"%(source, target))
        except Exception, e:
            if self._raven_client != None:
                self._raven_client.captureException()
            else:
                self._logger.error(e)
            return

        # Copy the files to the archive (mkdir + rsync)
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(conf['host'], username=conf['user'])

            # if the remote directory doesn't exist, create it
            try:
                _, _, stderr = client.exec_command("ls %s"%target)
                client_error = stderr.read()
                if client_error:
                    self._logger.info("Making remote directory: %s"%target)
                    syncutils.mkdir_remote(target, client)
            except Exception, e:
                if self._raven_client != None:
                    self._raven_client.captureException()
                else:
                    self._logger.error(e)
                client.close()
                return

            # set the rsync options
            options = "-a"
            options += "z" if conf['compress'] else ""
            options += "c" if conf['checksum'] else ""
            
            try:    
                # run the rsync process and get the stats dictionary
                rsync_stats = syncutils.run_rsync(source, target, client, options)

                # close ssh connection
                client.close()
            except Exception, e:
                if self._raven_client != None:
                    self._raven_client.captureException()
                else:
                    self._logger.error(e)
                client.close()

        except paramiko.SSHException, e:
            if self._raven_client != None:
                self._raven_client.captureException()
            else:
                self._logger.error("SSH connection threw an exception: %s"%e)
            client.close()
