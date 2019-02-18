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
    """ Helper class that counts how many errors are logged"""
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
    """ Handles logging information to file and outputting to terminal during debug sessions"""
    # Defined Paths.
    LOG_PATH = "/home/pi/logs/"
    # Default error if systemLog() doesn't work properly.
    SYSTEMLOG_ERROR_DESCRIPTION = "Unable to write to the log."

    LOG_ATTEMPTS = 0
    MAX_LOG_ATTEMPTS = 5
    DEBUG = True

    def __init__(self):
        """
        Constructor for the Logger. Opens up a log called unknownBootTime_# where # is the
        next number in the serialization of logs in the log directory.

        Parameters: None

        Returns: None

        Raises: None

        """
        self._boot = False
        # Create the filename. Count up from that number. The highest number is the latest log.
        # take everything after 15 characters. Log names are in the format YYYYmmdd-HHMMSS_C.log where C is the counter.
        try:

            fileList = [int(x.replace('.log','')[16:]) for x in os.listdir('../logs/') if x.endswith('.log') and not x.endswith('null.log')]
            if fileList:
                self.counter = max(fileList) + 1
            else:
                self.counter = 0
        except:
            self.counter='null'

        self.filename = 'unknownBootTime' # Must be 15 characters for the serialization.

    def bootWasSet(self):
        """
        Check the _boot flag

        Parameters: None

        Returns: self._boot

        Raises: None

        """
        return self._boot

    def setBoot(self,newTimestamp=None):
        """
        Sets the _boot flag to True. Also renames the current log to the current timestamp.

        Parameters:
        newTimestamp - optional - if given it will rename the current log to the newTimestamp.

        Returns: None

        Raises: None

        """
        self._boot = True
        #newTimestamp is an integer that represents the 4 byte timestamp
        if newTimestamp:
            try:
                newTimestamp = datetime.datetime.fromtimestamp(newTimestamp).strftime('%Y%m%d-%H%M%S')
                os.rename('{}{}_{}.log'.format(Logger.LOG_PATH,self.filename,self.counter),'{}{}_{}.log'.format(Logger.LOG_PATH,newTimestamp,self.counter))
                self.filename = newTimestamp
            except:pass
    def clearBoot(self):
        """
        Sets the _boot flag to false

        Parameters: None

        Returns: None

        Raises: None

        """
        self._boot = False

    def logData(self,type,*strings):
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
                stringBuilder.append('{} > [{}] {}'.format(type,self.filename if self._boot else str(round(time())),string))

            with open('{}{}_{}.log'.format(Logger.LOG_PATH,self.filename,self.counter),'a') as f:
                f.write('\n'.join(stringBuilder))
                f.write('\n')

            if Logger.DEBUG:
                for string in stringBuilder:
                    if string.startswith('Err'):
                        color = '\033[1;31m' # Red. Make errors pop out in terminal, because that's fun.
                    else:
                        color = '\033[0;1m' # Bold
                    print(self.counter,'|{}'.format(color),string,'\033[0;0m')
        except Exception as e:
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
            if exception is not None:
                description += ' {}'.format(str(exception.args))
            Errors.inc()
            self.logData('Sys','An error is being recorded to the error log. Please check the error log at this timestamp.')
            return self.logData('Err',description) # Actually log the data.
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
            return self.logData('Sys',*data)
        except Exception as e:
            Logger.LOG_ATTEMPTS += 1