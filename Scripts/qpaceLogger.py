#!/usr/bin/env python3
# qpaceLogger.Logger.py by Jonathan Kessluk
# 2-20-2018, Rev. 3
# Q-Pace project, Center for Microgravity Research
# University of Central Florida
#
# This program handles logging data to specific directories.



import os
import datetime
from time import strftime,gmtime,time

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

class Logger():

    # Defined Paths.
    LOG_PATH = "../logs/"
    # Default error if systemLog() doesn't work properly.
    SYSTEMLOG_ERROR_DESCRIPTION = "Unable to write to the log."

    LOG_ATTEMPTS = 0
    MAX_LOG_ATTEMPTS = 5
    DEBUG = True

    def __init__(self):
        self._boot = False
        # Create the filename. Count up from that number. The highest number is the latest log.
        fileList = [int(x.replace('.log','')) for x in os.listdir('../logs/') if x.endswith('.log')]
        if fileList:
            self.counter = max(fileList) + 1
        else:
            self.counter = 0

    def setBoot(self):
        self._boot = True

    def clearBoot(self):
        self._boot = False

    def logData(self,type,timestamp = 'Unknown',*strings):
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
        system_###.log OR error_###.log - The log which just got written to.

        Raises
        ------
        All exceptions raised by this function are passed up to the caller.

        """
        if Logger.LOG_ATTEMPTS >= Logger.MAX_LOG_ATTEMPTS:
            return None
        try:
            stringBuilder = []
            for string in strings:
                stringBuilder.append('{} > [{}] {}'.format(type,timestamp,string))


            with open('{}{}.log'.format(Logger.LOG_PATH,self.counter),'a') as f:
                f.write('\n'.join(stringBuilder))

            if Logger.DEBUG:
                for string in stringBuilder:
                    if string.startswith('Err'):
                        color = '\033[1;31m' # Red. Make errors pop out in terminal, because that's fun.
                    else:
                        color = '\033[0;1m' # Bold
                    print(self.counter,'|{}'.format(color),string,'\033[0;0m')
        except Exception as e:
            print(e)
            raise # Pass all and any exceptions back to the caller.

    def logError(self,description, exception = None):
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
            timestamp = strftime("%Y%m%d-%H%M%S",gmtime()) if self._boot else str(round(time()))
            if exception is not None:
                description += ' {}'.format(str(exception.args))
            Errors.inc()
            return self.logData('Err',timestamp,description) # Actually log the data.
        except Exception:
            Logger.LOG_ATTEMPTS += 1

    def logSystem(self,*data):
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
            timestamp = strftime("%Y%m%d-%H%M%S",gmtime()) if self._boot else str(round(time()))
            return self.logData('Sys',timestamp,*data)
        except Exception as e:
            Logger.LOG_ATTEMPTS += 1