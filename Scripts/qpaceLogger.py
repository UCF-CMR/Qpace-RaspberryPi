#!/usr/bin/env python3
# qpaceLogger.py by Jonathan Kessluk
# 2-20-2018, Rev. 2
# Q-Pace project, Center for Microgravity Research
# University of Central Florida
#
# This program handles logging data to specific directories.

LOGGER_DEBUG = True

import os.path
import datetime
from time import strftime,gmtime

# Defined Paths.
LOG_PATH = "../logs/"
BOOTTIME_PATH = "../BOOTTIME"
# Default error if systemLog() doesn't work properly.
SYSTEMLOG_ERROR_DESCRIPTION = "Unable to write to the log."

LOG_ATTEMPTS = 0
MAX_LOG_ATTEMPTS = 5

class Errors():
    error_count = 0

    @staticmethod
    def get():
        return Errors.error_count

    @staticmethod
    def inc(n=1):
        Errors.error_count += n

    @staticmethod
    def set(n):
        Errors.error_count = n

def _logData(fileName,timestamp = 'Unknown', *strings):
    """
    This function handles logging the actual data. It should not be called by a user.

    Parameters
    ----------
    fileName - String - Name of the file to write to.
    timestamp - datetime.datetime timestamp
    *strings - Any number of strings to write. each string will be on a new line.
    Returns
    -------
    String - This will be the filename of the file it just wrote.
    system_BOOTTIME.log OR error_BOOTTIME.log - The log which just got written to.

    Raises
    ------
    All exceptions raised by this function are passed up to the caller.

    """
    global LOG_ATTEMPTS
    if LOG_ATTEMPTS >= MAX_LOG_ATTEMPTS:
        return None
    try:
        # Get a human readable datetime formated as %Y%m%d-%H%M%S from the BOOTTIME file.
        bootTime = datetime.datetime.utcfromtimestamp(os.path.getmtime(BOOTTIME_PATH)).strftime('%Y%m%d-%H%M%S')
        fileName = fileName + bootTime + ".log"
        with open(LOG_PATH + fileName,'a') as f:
            stringBuilder = []
            for string in strings:
                stringBuilder.append('[{}] {}'.format(timestamp,string))

            f.write('\n'.join(stringBuilder))
            if LOGGER_DEBUG:
                if fileName[:6] == 'error_':
                    prefix = 'Error: '
                else:
                    prefix = 'System:'
                for string in stringBuilder:
                    print(prefix, string)
        return fileName
    except Exception: raise # Pass all and any exceptions back to the caller.

def logError(description, exception = None):
    """
    This function takes a description and exception and logs the error to the error log.

    Parameters
    ----------
    String - description - User defined description of the error that happened.

    Exception - exception - Default: None - optional exception to be passed. the arguments of
        the exception will be written to the log too.

    Returns
    -------
    String - This will be the filename of the file it just wrote.

    Raises
    ------
    All exceptions raised by this function are ignored.

    """
    try:
        timestamp = strftime("%Y%m%d-%H%M%S",gmtime())
        errorData = [description]
        if exception is not None:
            errorData.append(str(exception.args))
        _logData('system_',timestamp,'An Error is being recorded to the error log.','Preview: {}'.format(description[0][:90]))
        Errors.inc()
        return _logData('error_',timestamp,*errorData) # Actually log the data.
    except Exception:
        global LOG_ATTEMPTS
        LOG_ATTEMPTS += 1
        pass

def logSystem(*data):
    """
    This function takes in a 2d array of data to log it to the system log.

    Parameters
    ----------
    *data - Strings - multiple strings to be written to the system log. Each string will be written on a new line.

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
        return _logData('system_',timestamp,*data)
    except Exception as e:
        global LOG_ATTEMPTS
        LOG_ATTEMPTS += 1
        pass