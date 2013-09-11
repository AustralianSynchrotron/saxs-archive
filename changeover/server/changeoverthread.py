import threading
from changeover.common import syncutils
from changeover.common.settings import Settings
from common import saxslog


class ChangeoverThread(threading.Thread):
    """
    Thread class that performs the changeover
    """
    def __init__(self, folder_create=False, folder_folders={},
                       rsync_enabled=False, rsync_checksum=True,
                       rsync_compress=True, rsync_exclude=[],
                       post_checksum=True, post_delete=False):
        """
        Constructor of the changeover thread class
        """
        super(ChangeoverThread, self).__init__()
        conf = Settings()
        self._logger, self._raven_client = saxslog.setup(__name__,
                                                         conf['logging']['debug'],
                                                         conf['logging']['sentry'])
        self._stop = threading.Event()

    def run(self):
        """
        The main run method of the thread.
        """
        #self._stop.wait(10)
        if self.stopped():
            return
        #logger.info("Aggregation thread was stopped")

    def stop(self):
        """
        Stops the thread.
        """
        self._stop.set()

    def stopped(self):
        """
        Returns the stop flag of the thread
        """
        return self._stop.is_set()
