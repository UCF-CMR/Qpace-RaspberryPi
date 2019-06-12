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
import sys
import pigpio
import SC16IS750

class Colors():
    # Foreground:
    HEADER  = '\033[95m'
    OKBLUE  = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL    = '\033[91m'
    # Formatting
    BOLD      = '\033[1m'
    UNDERLINE = '\033[4m'    
    # End colored text
    END = '\033[0m'
    NC  ='\x1b[0m' # No Color
    
    #other foreground colors
    RED        = "\x1b[31m"
    LIGHT_CYAN = "\x1b[96m"
    BLACK      = "\x1b[30m"
    DEFAULT    = "\x1b[39m"
    #other background colors
    BACKGROUND_WHITE   = "\x1b[107m"
    BACKGROUND_DEFAULT = "\x1b[49m"

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
    #MODE should contain all sys arguments from the user when running qpaceMain.py independantly from startQPACE.sh
    #debug purposes only!
    MODE = sys.argv[1:]

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

        self.Errors = Errors()
        self.Colors = Colors()
        self.filename = 'unknownBootTime' # Must be 15 characters for the serialization.

        # A pigpio object is required if we are using the TX/RX method so we can quiet the logger
        self.pi = pigpio.pi()
        self.pi.set_mode(SC16IS750.FLIGHT_MODE_ON_PIN, pigpio.INPUT)
        self.pi.set_pull_up_down(SC16IS750.FLIGHT_MODE_ON_PIN, pigpio.PUD_DOWN)

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
        
    def logPrint(self, typeStr, log):

        '''
        sysargv logging modes:
        no arguments - prints sys
        e - prints errors
        w - prints warnings
        i - prints info
        d - prints debugging
        r - prints results
        s - prints successes
        f - prints failures
        v - prints verbosely (everything)    

        You can combine modes to see different logging information
        '''    
        # If flight mode is on, print nothing
        if (self.pi.read(SC16IS750.FLIGHT_MODE_ON_PIN) == 1):
            return
        #if its a sys log, always print it
        elif 'typeStr' == 'systm':
            print(log)
        #if the mode is v (verbose) print everything
        elif 'v' in Logger.MODE:
            print(log)
        #if the log message one of the modes selected by the user print it
        elif typeStr[0] in Logger.MODE:
            print(log)   
      
    
    def logData(self,typeStr,*strings):
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

            #add time string
            if self._boot:
                timeStr = self.filename
            else:
                timeStr = str(time())
            # concat string: " 'log type' > ['time'] + 'log data'
            log = typeStr + ' > [' + timeStr + '] ' + ''.join(strings)
            
            #write to log file.
            with open('{}{}_{}.log'.format(Logger.LOG_PATH,self.filename,self.counter),'a') as f:
                f.write('\n' + log + '\n')

            #Used for Debugging only!
            return self.logPrint(typeStr, log)

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
            self.Errors.inc()
            log = Colors.RED + description + Colors.DEFAULT 
            return self.logData('error', log) # Actually log the data.
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
        #Add Color to Text
        log = Colors.HEADER + ''.join(data) + Colors.END
        try:
            return self.logData('systm', log)
        except Exception as e:
            Logger.LOG_ATTEMPTS += 1

    def logInfo(self,*data):
        """
        This function should be called when:
            - wanting to log normal information about the current state / operation.

        This function accepts:
            - a string ready to be formatted
        This function returns:
            - the string the user passed a pretix of 'Info'

        Suggested Color: white
        """
        #Add Color to Text
        log = Colors.NC + ''.join(data) + Colors.END
    
        try:
            return self.logData('info ', log)
        except Exception as e:
            Logger.LOG_ATTEMPTS += 1

    def logWarning(self,*data):
        """
        This function should be called when:
            - wanting to log normal information about the current state / operation.

        This function accepts:
            - a string ready to be formatted
        This function returns:
            - the string the user passed a pretix of 'Warn'

        Suggested Color: yellow or orange
        """
        #Add Color to Text
        log = Colors.WARNING + ''.join(data) + Colors.END
        try:
            return self.logData('warn ', log)
        except Exception as e:
            Logger.LOG_ATTEMPTS += 1

    def logResults(self,*data):
        """
        This function should be called when:
            - wanting to log data/values/results about the current state / operation.

        This function accepts:
            - a string ready to be formatted
        This function returns:
            - the string the user passed a pretix of 'Data'

        Suggested Color: yellow or orange
        """
        #Add Color to Text
        log = Colors.LIGHT_CYAN + ''.join(data) + Colors.DEFAULT
        try:
            return self.logData('result', log)
        except Exception as e:
            Logger.LOG_ATTEMPTS += 1

    def logSuccess(self,*data):
        """
        This function should be called when:
            - wanting to log function/operation/validation success information about the current state / operation.

        This function accepts:
            - a string ready to be formatted
        This function returns:
            - the string the user passed a pretix of 'Pass'
        
        Suggested Color: green
        """
        #Add Color to Text
        log = Colors.OKGREEN + ''.join(data) + Colors.END
        try:
            return self.logData('succ ', log)
        except Exception as e:
            Logger.LOG_ATTEMPTS += 1

    def logFailure(self,*data):
        """
        This function should be called when:
            - wanting to log function/operation/validation failure information about the current state / operation.
            - this is not an exception but a process failure.

        This function accepts:
            - a string ready to be formatted
        This function returns:
            - the string the user passed a pretix of 'Fail'

        Suggested Color: red or orange
        """
        #Add Color to Text
        log = Colors.FAIL + ''.join(data) + Colors.END
        try:
            return self.logData('fail ', log)
        except Exception as e:
            Logger.LOG_ATTEMPTS += 1

    def logDebug(self,*data):
        """
        This function should be called when:
            - wanting to log any debug information about the current state / operation.

        This function accepts:
            - a string ready to be formatted
        This function returns:
            - the string the user passed a pretix of 'Debug'
        
        Suggested Color: blue
        """
        #Add Color to Text
        log = Colors.OKBLUE + ''.join(data) + Colors.END
        try:
            return self.logData('debug', log)
        except Exception as e:
            Logger.LOG_ATTEMPTS += 1