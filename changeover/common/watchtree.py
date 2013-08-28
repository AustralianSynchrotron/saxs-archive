import os
import re
import time
import logging
import pyinotify
import threading

logger = logging.getLogger(__name__)

class Node(object):
    """
    A single node in the directory tree.
    """

    def __init__(self, watch_manager, file_handler, regex=None, delay=0):
        """
        Constructor of the tree node.
        watch_manager: reference to the watch manager that maintains the watches.
        file_handler: reference to a file handler object
        regex: a regex for excluding files from the watch
        delay: time in seconds to aggregate together several events
        """
        self._wd = -1
        self._nodes = []
        self._watch_manager = watch_manager
        self._file_handler = file_handler
        self._regex = regex
        self._delay = delay
        self._thread_active = False

    def create(self, path):
        """
        Create a watch for this node and the child nodes for the sub-directories
        of the specified path
        path: the path of this node and the parent path for this nodes children
        """
        # add a watch on this node
        mask = pyinotify.IN_CLOSE_WRITE | pyinotify.IN_CREATE | \
               pyinotify.IN_DELETE | pyinotify.IN_MOVED_TO
        try:
            wd = self._watch_manager.add_watch(path, mask,
                                               proc_fun=self.handle_event,
                                               quiet=False).items()[0]
            self._wd = wd[1]
        except pyinotify.WatchManagerError, e:
            logger.error("Couldn't add watch: %s, %s"%(e, e.wmd))

        # add the nodes for the sub-directories recursively
        for curr_dir in os.listdir(path):
            abs_dir = os.path.join(path, curr_dir)
            if os.path.isdir(abs_dir):
                new_node = Node(self._watch_manager,
                                self._file_handler,
                                self._regex,
                                self._delay)
                self._nodes.append(new_node)
                new_node.create(abs_dir)

    def delete(self):
        """
        Deletes the watch of this node and all children nodes
        """
        if self._wd > -1:
            try:
                self._watch_manager.rm_watch(self._wd, quiet=False)
            except pyinotify.WatchManagerError, e:
                logger.error("Couldn't remove watch: %s, %s"%(e, e.wmd))
        for node in self._nodes:
            node.delete()
        del self._nodes[:]

    def handle_event(self, event):
        """
        The callback method for notification events
        If the delay time is larger than 0, a thread is started in order to wait
        for for the delay time to pass and then calls the rsync process. In the
        meantime calls to this method are simply not handled.
        event: the pyinotify event object
        """
        # if it is a directory remove all sub-nodes then rebuild the sub-tree.
        if event.dir:
            self.delete()
            self.create(event.path)
            logger.info("Recreated the sub-tree '%s'"%event.path)
        else:
            if event.mask == pyinotify.IN_CLOSE_WRITE:
                if not self._thread_active:
                    if self._regex != None and \
                        self._regex.search(event.name) != None:
                        return

                    if self._delay > 0:
                        threading.Thread(target=self._thread_handle_event,
                                         args=(self._delay, event.path)).start()
                        logger.info("Started event aggregation thread")
                        self._thread_active = True
                    else:
                        self._file_handler.process(event.path)

    def _thread_handle_event(self, delay, path):
        """
        Thread method that waits the delay time and then calls the rsync process
        """
        time.sleep(delay)
        self._file_handler.process(path)
        self._thread_active = False


class WatchTree(object):
    """
    The tree of folders that are being watched for changes. Implements the full
    hierarchical structure of the target directories. If a folder is created,
    renamed or deleted, the part of the tree that is affected by this change
    is automatically rebuild. The associated pyinotify watches are also updated.
    """
    def __init__(self, file_handler, exclude="", delay=0):
        """
        Constructor of the watch tree class
        file_handler: reference to a file handler object
        exclude: a regex for excluding files from the watch
        delay: time in seconds to aggregate together several events
        """
        self._watch_manager = pyinotify.WatchManager()
        self._notifier = pyinotify.Notifier(self._watch_manager)
        self._root = Node(self._watch_manager, file_handler,
                          re.compile(exclude) if exclude else None,
                          delay)

    def create(self, root):
        """
        Create the initial tree. Starts with the root directory and builds the
        tree structure recursively.
        root: the root directory from which the tree creation is started with.
        """
        self._root.create(root)

    def watch(self):
        """
        Start watching.
        """
        self._notifier.loop()


class WatchTreeFileHandler(object):
    """
    Abstract base class for handling file change notifications.
    Inherit this class to create your own handler.
    """
    def process(self, path):
        """
        This method is called every time a file was finished writing.
        path: the path to the file.
        """
        pass
