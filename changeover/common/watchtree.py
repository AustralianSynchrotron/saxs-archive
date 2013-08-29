import os
import re
import logging
import pyinotify
import threading

logger = logging.getLogger(__name__)


class AggregationThread(threading.Thread):
    """
    Thread class that waits the delay time and then calls the file handler process
    """
    def __init__(self, delay, file_handler, path):
        """
        Constructor of the aggregation thread class
        delay: time in seconds the thread should wait
        file_handler: reference to a file handler object
        path: The path of the node the thread was started from
        """
        super(AggregationThread, self).__init__()
        self._delay = delay
        self._file_handler = file_handler
        self._stop = threading.Event()
        self._path = path

    def run(self):
        """
        The main run method of the thread. Waits for the delay time and, if not
        stopped, calls the file handler method.
        """
        self._stop.wait(self._delay)
        if not self.stopped():
            self._file_handler.process(self._path)
        else:
            logger.info("Aggregation thread was stopped")

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
        self._nodes = {}
        self._watch_manager = watch_manager
        self._file_handler = file_handler
        self._regex = regex
        self._delay = delay
        self._agg_thread = AggregationThread(delay, file_handler, "")

    def create(self, path):
        """
        Create a watch for this node and the child nodes for the sub-directories
        of the specified path
        path: the path of this node and the parent path for this nodes children
        """
        # add a watch on this node
        mask = pyinotify.IN_CLOSE_WRITE | pyinotify.IN_CREATE | \
               pyinotify.IN_DELETE | pyinotify.IN_MOVED_TO | \
               pyinotify.IN_MOVED_FROM
        try:
            wd = self._watch_manager.add_watch(path, mask,
                                               proc_fun=self.handle_event,
                                               quiet=False).items()[0]
            self._wd = wd[1]
            logger.info("Added watch '%i' for '%s'"%(self._wd,path))
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
                self._nodes[curr_dir] = new_node
                new_node.create(abs_dir)

    def delete(self):
        """
        Deletes the watch of this node and all children nodes
        """
        if self._wd > -1:
            try:
                # stop a running aggregation thread
                if self._agg_thread.is_alive():
                    self._agg_thread.stop()

                # remove watch
                self._watch_manager.rm_watch(self._wd, quiet=False)
                logger.info("Removed watch '%i' successfully"%self._wd)
                self._wd = -1
            except pyinotify.WatchManagerError, e:
                logger.error("Couldn't remove watch: %s, %s"%(e, e.wmd))
        for key, node in self._nodes.iteritems():
            node.delete()
        self._nodes.clear()

    def handle_event(self, event):
        """
        The callback method for notification events
        If the delay time is larger than 0, a thread is started in order to wait
        for for the delay time to pass and then calls the rsync process. In the
        meantime calls to this method are simply not handled.
        event: the pyinotify event object
        """
        # if it is a directory remove it and its sub-nodes then rebuild the sub-tree.
        if event.dir:
            if (event.name != None) and (event.name in self._nodes):
                self._nodes[event.name].delete()
                del self._nodes[event.name]
                logger.info("Deleted node '%s' and its sub-tree '%s'"%\
                            (event.name, event.pathname))
            if os.path.exists(event.pathname):
                new_node = Node(self._watch_manager,
                                self._file_handler,
                                self._regex,
                                self._delay)
                self._nodes[event.name] = new_node
                logger.info("Adding node '%s' and its sub-tree '%s'"%\
                            (event.name, event.pathname))
                new_node.create(event.pathname)
        else:
            if event.mask == pyinotify.IN_CLOSE_WRITE:
                if (os.path.exists(event.path)) and (not self._agg_thread.is_alive()):
                    if self._regex != None and \
                        self._regex.search(event.name) != None:
                        return

                    if self._delay > 0:
                        self._agg_thread = AggregationThread(self._delay,
                                                             self._file_handler,
                                                             event.path)
                        self._agg_thread.start()
                        logger.info("Started event aggregation thread")
                    else:
                        self._file_handler.process(event.path)


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
