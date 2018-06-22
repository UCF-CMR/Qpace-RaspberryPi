#!/usr/bin/env python3
# qpaceLogger.py by Jonathan Kessluk
# 2-20-2018, Rev. 1.3
# Q-Pace project, Center for Microgravity Research
# University of Central Florida
#
# This program handles logging data to specific directories.

import csv
import os.path
import datetime
from time import strftime,gmtime

# Defined Paths.
LOG_PATH = "/home/pi/logs/"
BOOTTIME_PATH = "/home/pi/BOOTTIME"
#Information for writing the CSV
DELIMITER = ","
# Default error if systemLog() doesn't work properly.
SYSTEMLOG_ERROR_DESCRIPTION = "Unable to write to a CSV to log data."

def _logData(data, csvName):
    print(data)
    """
    This function handles logging the actual data. It should not be called by a user.

    Parameters
    ----------
    2D array of values - data - the data to actually be logged. Each nested array is a row, each index is a cell.

    String - csvName - The actual name of the file. This should only be 'error_' or 'system_' depending on the file.

    Returns
    -------
    String - This will be the filename of the file it just wrote.
    system_BOOTTIME.csv OR error_BOOTTIME.csv - The log which just got written to.

    Raises
    ------
    All exceptions raised by this function are passed up to the caller.

    """
    try:
        # Get a human readable datetime formated as %Y%m%d-%H%M%S from the BOOTTIME file.
        bootTime = datetime.datetime.utcfromtimestamp(os.path.getmtime(BOOTTIME_PATH)).strftime('%Y%m%d-%H%M%S')
        filename = csvName + bootTime + ".csv"
        with open(LOG_PATH + filename,'a') as csvFile:
            fw = csv.writer(csvFile, delimiter = DELIMITER, quotechar = '|', quoting= csv.QUOTE_MINIMAL)
            fw.writerows(data) # Write all the rows from the 2d array.
            return filename
    except Exception: raise # Pass all and any exceptions back to the caller.

def logError(description, exception = None):
    """
    This function takes a description and exception and logs the error to the error log.

    Parameters
    ----------
    String - description - User defined description of the error that happened.

    Exception - exception - Default: None - optional exception to be passed. the arguments of
        the exception will be written to the CSV too.

    Returns
    -------
    String - This will be the filename of the file it just wrote.

    Raises
    ------
    All exceptions raised by this function are ignored.

    """
    try:
        timestamp = strftime("%Y%m%d-%H%M%S",gmtime())
        errorData = [timestamp, description]
        if exception is not None:
            errorData.append(str(exception.args))
        # logData exepcts a 2d array for each row, so make it a 2d array.
        errorData = [errorData]
        _logData([['An Error is being recorded to the error log.','Preview: ' + description[:30]]],'system_')
        return _logData(errorData, 'error_') # Actually log the data.
    except Exception: pass

def logSystem(data):
    """
    This function takes in a 2d array of data to log it to the system log.

    Parameters
    ----------
    2D array of values - data - the data to actually be logged. Each nested array is a row, each index is a cell.

    Returns
    -------
    String - This will be the filename of the file it just wrote.

    Raises
    ------
    All exceptions raised by this function are passed to the logError function to be handled and logged,
    and then ignored.

    """
    try:
        timestamp = strftime("%Y%m%d-%H%M%S",gmtime())
        for row in data:
            row.insert(0,timestamp)
        return _logData(data, 'system_')
    except Exception as e:
        # Guess we had a problem, so we'll log the error as an error.
        pass#logError(SYSTEMLOG_ERROR_DESCRIPTION,e) # Actually log the error.