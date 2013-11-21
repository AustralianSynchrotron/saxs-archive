import os
import json
import socket
import paramiko
from datetime import datetime, date
from string import Template
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
        """
        conf = Settings()
        self._logger, self._raven_client = saxslog.setup(__name__,
                                                         conf['logging']['debug'],
                                                         conf['logging']['sentry'])
        self._stats_file = None
        self._stats_file_datetime = datetime.now()
        self._flush_counter = 0


    def __del__(self):
        """
        The destructor.
        """
        if self._stats_file != None:
            self._stats_file.close()


    def process(self, path, file_list):
        """
        Run the rsync process after being notified of a change in the filesystem.
        path: The source path for the rsync process
        file_list: The list of files that should be rsynced
        """
        conf = Settings()
        
        # build the source and target paths for rsync
        try:
            source, target = syncutils.build_sync_paths(path)
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
            client.connect(conf['target']['host'],
                           username=conf['target']['user'])

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
            options += "z" if conf['rsync']['compress']==True else ""
            options += "c" if conf['rsync']['checksum']==True else ""

            try:    
                # run the rsync process and get the stats dictionary
                rsync_stats = syncutils.run_rsync(source, target, file_list,
                                                  client, options,
                                                  json.loads(conf['rsync']['exclude']))
                self._write_stats_file(rsync_stats)

                # close ssh connection
                client.close()
            except Exception, e:
                if self._raven_client != None:
                    self._raven_client.captureException()
                else:
                    self._logger.error(e)
                client.close()

        except (paramiko.SSHException, socket.error), e:
            if self._raven_client != None:
                self._raven_client.captureException()
            else:
                self._logger.error("SSH connection threw an exception: %s"%e)
            client.close()


    def _write_stats_file(self, statistics):
        """
        Write the rsync statistics to a file. The filename can contain a
        non-ambiguous combination of the template parameters ${day}, ${year}
        and ${month} or no template parameters at all.
        statistics: the dictionary as it is returned by syncutils.run_rsync()
        """
        conf = Settings()

        # check whether the stats file has been opened yet. If not open it.
        # Otherwise check if a new file has to be opened due to a date change
        if self._stats_file == None:
            self._open_stats_file()
        else:
            year_changed = self._stats_file_datetime.year != date.today().year
            month_changed = self._stats_file_datetime.month != date.today().month
            day_changed = self._stats_file_datetime.day != date.today().day
            if (conf['statistics']['has_year'] and year_changed) or \
               (conf['statistics']['has_month'] and month_changed) or \
               (conf['statistics']['has_day'] and day_changed):
               self._logger.info("Opening new statistics file")
               self._stats_file.close()
               self._open_stats_file()

        # write the statistics to the file
        self._stats_file.write("%s %s %s %s %s %s => %s\n"%\
                                (datetime.isoformat(datetime.now()),
                                statistics['files_total'],
                                statistics['files_transferred'],
                                statistics['size_total'],
                                statistics['size_transferred'],
                                statistics['source'],
                                statistics['target']))
        self._flush_counter += 1

        # flush buffer content to file
        if self._flush_counter >= int(conf['statistics']['frequency']):
            self._flush_counter = 0
            self._stats_file.flush()
            os.fsync(self._stats_file.fileno())


    def _open_stats_file(self):
        """
        Open a statistic file and store the datetime
        """
        self._stats_file_datetime = datetime.now()
        self._stats_file = open(Template(Settings()['statistics']['file'])\
                                .safe_substitute({'year': date.today().year,
                                                  'month': date.today().month,
                                                  'day': date.today().day}), 'a')
