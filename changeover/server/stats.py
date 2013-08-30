import glob
import logging
from dateutil import parser
from calendar import monthrange, month_abbr
from string import Template
from changeover.common.settings import Settings

import random

logger = logging.getLogger(__name__)


def aggregate(year=None, month=None, day=None):
    """
    Aggregates the rsync statistics and builds a histogram of transferred
    data and number of files. Returns a dictionary with the histogram data.
    year: if specified aggregates the data for each month of the year
    month: if specified aggregates the data for each day of a month
    day: if specified aggregates the data for each hour of the day
    """
    result = {'status': "success"}
    date_dict = {'year': "*", 'month': "*", 'day': "*"}

    # prepare the histograms
    bins = []
    if year != None:
        date_dict['year'] = year
        for i in range (1,13):
            bins.append(month_abbr[i])

    if month != None:
        date_dict['month'] = month
        bins = range(1, monthrange(int(year), int(month))[1]+1)

    if day != None:
        date_dict['day'] = day
        bins = range(24)

    if len(bins) > 0:
        hist_data = [0]*len(bins)
        hist_file = [0]*len(bins)
    else:
        hist_data = []
        hist_file = []

    # create list of input statistics files
    stats_files = glob.glob(Template(Settings()['statistics']['file'])\
                            .safe_substitute(date_dict))

    # loop over files and aggregate statistics    
    for stats_file in stats_files:
        try:
            curr_file = open(stats_file, 'r')

            while 1:
                line = curr_file.readline()
                if not line:
                    break

                tokens = line.split()
                line_date = parser.parse(tokens[0])
                data_transferred = int(tokens[4]) * 954e-9  # bytes -> MB
                files_transferred = int(tokens[2])

                idx = 0
                if day != None:
                    idx = line_date.hour
                elif month != None:
                    idx = line_date.day-1
                elif year != None:
                    idx = line_date.month-1
                else:
                    if line_date.year in bins:
                        idx = bins.index(line_date.year)
                    else:
                        idx = len(bins)
                        bins.append(line_date.year)
                        hist_data.append(0)
                        hist_file.append(0)

                hist_data[idx] += data_transferred
                hist_file[idx] += files_transferred

            curr_file.close()

        except IOError, e:
            logger.error("Couldn't open statistics file: %s"%e)

    # create output
    result['hist_data'] = []
    result['hist_file'] = []
    for i in range(len(bins)):
        result['hist_data'].append({'bin': bins[i], 'value': hist_data[i]})
        result['hist_file'].append({'bin': bins[i], 'value': hist_file[i]})
    return result
