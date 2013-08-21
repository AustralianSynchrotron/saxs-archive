import paramiko
import pyinotify
from changeover import syncutils
from common import saxslog

class EventHandler(pyinotify.ProcessEvent):
    """
    The handler class for processing pyinotify events.
    """

    def __init__(self, config):
        """
        The constructor of the event handler.
        config: The configuration dictionary
        raven_client: (optional) The raven client for logging excpetions to
                      the Sentry server
        """
        self._config = config
        self._logger, self._raven_client = saxslog.setup(config, __name__)


    def process_IN_CLOSE_WRITE(self, event):
        """
        Process events that were triggered by closing a file after having
        written into it.
        event: The event that triggered this method
        """
        # check the length of the triggered path
        trg_path_list = event.path.split('/')
        src_path_list = self._config['src_folder_list']
        if len(trg_path_list) < len(self._config['src_folder_list']):
            self._logger.error("The triggered path is shorter than the source path!")
            return

        # build the source and target paths for rsync
        try:
            source, target = syncutils.build_sync_paths(trg_path_list,
                                                        self._config)
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
            client.connect(self._config['host'], username=self._config['user'])

            # if the remote directory doesn't exist, create it
            try:
                _, _, stderr = client.exec_command("ls %s"%target)
                client_error = stderr.read()
                if client_error:
                    self._logger.info("Making remote directory: %s"%target)
                    syncutils.mkdir_remote(target, client, self._config)
            except Exception, e:
                if self._raven_client != None:
                    self._raven_client.captureException()
                else:
                    self._logger.error(e)
                client.close()
                return

            # set the rsync options
            options = "-a"
            options += "z" if self._config['compress'] else ""
            options += "c" if self._config['checksum'] else ""
            
            try:    
                # run the rsync process
                syncutils.run_rsync(source, target, client, self._config,
                                    options)

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
