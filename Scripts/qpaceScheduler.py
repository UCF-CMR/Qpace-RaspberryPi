#! /usr/bin/env python3
# qpaceScheduler.py by Jonathan Kessluk & Minh Pham
# 2-13-2018, Rev. 2
# Q-Pace project, Center for Microgravity Research
# University of Central Florida
#
# This program parses the Schedule file and then acts upon that information.

import re
import os
import signal
import time
from datetime import datetime, date, timedelta
from math import ceil
from shutil import copy
import threading
import qpaceLogger as qpLog
import qpaceExperimentParser as exp
import qpacePiCommands as cmd
from qpaceControl import QPCONTROL

Schedule_PATH = "/home/pi/data/text/"
Schedule_FILE = "todo.txt"
Schedule_TEMP = "Schedule.tmp"
GRAVEYARD_PATH = '/home/pi/graveyard/'
ABORT_DELTA = 450 # SECONDS
Schedule_FILE_PATH = Schedule_PATH + Schedule_FILE

WTC_IRQ = 7

def getScheduleList(logger):
	"""
	Get the schedule from the file we placed it in.

	Parameters: logger - just the Logger() to log data

	Returns: the list of items to schedule.

	Raises: None

	"""
	schedule_list = []
	try:
		with open(Schedule_FILE_PATH, 'r') as Schedulefile:
			task_list = Schedulefile.readlines()
			for task in task_list:
				task = task.replace('\n','')
				# Add every string to the schedule_list
				schedule_list.append(task.split(" "))
	except FileNotFoundError:
		logger.logSystem('Scheduler: There is not a Schedule file found at {}'.format(Schedule_FILE_PATH))
	except OSError as e:
		# Couldn't open the Schedule file. Send an error to the error log.
		logger.logError("Scheduler: Could not open Schedule file for reading.", e)

	return schedule_list

def sortScheduleList(schedule_list,logger):
	"""
	Take the items in the list and sort them. If one fails to be converted to a sortable type, then remove it.

	Parameters:
	schedule_list - the list of items to be scheduled
	logger - the logger object to log data

	Returns: the sorted schedule_list

	Raises: None

	"""
	if schedule_list:
		i = 0
		while i < len(schedule_list):
			try:
				#Create a date time from the string
				schedule_list[i][0] = datetime.strptime(schedule_list[i][0],"%Y%m%d-%H%M%S")
			except (ValueError,TypeError) as e:
				logger.logSystem("Scheduler: Removed an item due to invalid time format. <{}>".format(schedule_list[i]))
				del schedule_list[i]
			else:
				i+=1
		schedule_list.sort() # Python will sort a 2D list based off the first argument of each nested list in ascending order.
		#updateScheduleFile(schedule_list,logger)
	return schedule_list

def _processTask(chip,task,shutdownEvent,experimentEvent,runEvent,nextQueue,disableCallback,logger):
	"""
		This function handles processing a specific command given. This is what does the real "parsing"

		Parameters
		----------
		chip - an SC16IS750 object
		task - List - List that is the arguments to a command.
			   task[0] is when the command should execute.
			   task[1] is the name of the command.
			   task[2:] is args for that command.
		shutdownEvent - threading.Event - if set() then abort and shutdown gracefully
		experimentEvent - threading.Event - if set() then there is an experiment going on.
											if clear() there is no experiment running.
		runEvent - threading.Event - if clear() then pause the threadd
		nextQueue - queue to put control characters for the WTC
		disableCallback - threading.Event - if set() disable the callback in the interpreter. If clear() start it
		logger - the logging object for logging data

		Returns
		-------
		True for successful completion of the task.
		False for failure to complete a task.

		Raises
		------
		Nothing!
	"""
	logger.logSystem("Scheduler: Beginning execution of a task. {}".format(str(task[1:])))
	currentTask = task[1].upper()
	try:
		if currentTask == "EXPERIMENT":

			try:
				# If experimentEvent exists and is not set, then let's run an experiment.
				if experimentEvent is None or experimentEvent.is_set():
					raise StopIteration('experimentEvent is None or experimentEvent is set.') # If experimentEvent does not exist or is set, return False to know there is a failure.

				# Run an experiment file from the experiment directory
				logger.logSystem("Scheduler: Running an experiment.", task[2]) # Placeholder
				parserThread = threading.Thread(name='experimentParser',target=exp.run, args=(task[2],experimentEvent,runEvent,logger,nextQueue,disableCallback))
				parserThread.start()
			except Exception as e:
				logger.logError('Scheduler: Task failed',e)
				return False

		elif currentTask == "COPY":  #Back up a file
			logger.logSystem("Attempting to create a copy.", ROOTPATH + task[2], ROOTPATH + task[3]) # Placeholder
			try:
				copy(ROOTPATH + task[2], ROOTPATH + task[3]) #Copy the file from task[2] to task[3]
			except Exception as e:
				logger.logError('Scheduler: Task failed',e)
				return False # The task failed
		elif currentTask == "REPORT":  #Get the status
			logger.logSystem("Scheduler: Saving status to file.")
			try:
				cmd.Command().saveStatus(logger)
			except:
				logger.logError('Scheduler: Task failed',e)
				return False # The task failed
		elif currentTask == 'SPLIT':
			logger.logSystem('Scheduler: Splitting a video...',str(task))
			cmd.Command().splitVideo(logger," ".join(task[2:]).encode('ascii'),silent=True)
		elif currentTask == 'CONVERT':
			logger.logSystem('Scheduler: Converting a video...',str(task))
			cmd.Command().convertVideo(logger," ".join(task[2:]).encode('ascii'),silent=True)
		elif currentTask == 'SHUTDOWN':
			logger.logSystem('Scheduler: Shutdown!')
			os.system('sleep 5 && sudo halt &')
			self.shutdownEvent.set()
		elif currentTask == 'HANDBRAKE':
			logger.logSystem('Scheduler: Running handbrake on a video...',str(task))
			cmd.Command().runHandbrake(logger," ".join(task[2:]).encode('ascii'),silent=True)
		elif currentTask == 'BACKUP': # Compress a file
			try:
				import tarfile
				# The name of the new file will be whatever was input, but since the path could be long
				# create the {}.tar.gz at the filename. Since it could be a directory with a /
				# look for the 2nd to last / and then slice it. Then remove and trailing /'s
				if task[2].endswith('/'):
					task[2] = task[2][:-1]
				newFile = ROOTPATH + task[2][task[2].rfind('/')+1:]
				tarDir = ROOTPATH + 'data/backup/{}.tar.gz'.format(newFile)
				with tarfile.open(tarDir, "w:gz") as tar:
					tar.add(ROOTPATH+task[2])
			except ImportError as e:
				logger.logSystem('Scheduler: The task could not be completed due to an import error.')
			except Exception as e:
				logger.logError('Scheduler: The task encountered an error.',e)
				return False # It failed.
		elif currentTask == 'LOG':
			logger.logSystem('SchedulerLog: {}'.format(' '.join(task[2:])))
		else:
			logger.logSystem("Scheduler: Unknown task!", str(task[1:]))
	except ValueError as err:
		logger.logSystem('Scheduler(ValueError): The task could not be completed. <{}>'.format(task))
	except StopIteration as err:
		logger.logSystem('Scheduler: Task aborted. {}'.format(str(err)))

	return True # If we reach here, assume everything was a success.

def executeScheduleList(chip,nextQueue,schedule_list, shutdownEvent, experimentEvent, runEvent,disableCallback,logger):
	"""
		This function will execute the ScheduleList in order. If it is interrupted, it will return the Schedulelist

		Parameters
		----------
		chip - an SC16IS750 object.
		nextQueue - queue to put control characters for the WTC
		schedule_list - List - Sorted schedule_list. (Sorted by the timestamp to execute.)
		shutdownEvent - threading.Event - if set() then we need to back out and shutdown.
		experimentEvent - threading.Event - pass through an event object to determine whether or not an experiment
										 is running.
		runEvent - threading.Event - if clear() then pause the threadd
		disableCallback - threading.Event - if set() disable the callback in the interpreter. If clear() start it
		logger - the logging object for logging data

		Returns
		-------
		List - A sorted schedule_list that is a subset of the original Schedulelist. Only returns a list
		if it was interrupted prematurly. Otherwise, if it completes properly, it will return
		an empty list

		Raises
		------
		None!
	"""
	completedTask = True
	timeDelta = ABORT_DELTA

	# We ideally want to use the global threading.Event, but worst case is it doesn't exist.
	# If it doesn't, lets create one locally so we have something to use regardless.
	if experimentEvent is None:
		experimentEvent = threading.Event()
	while schedule_list and not shutdownEvent.is_set():
		schedule_list = list(schedule_list)
		# How many seconds until our next task?
		try:
			if len(schedule_list[0]) < 3:
				raise SyntaxError()
			runEvent.wait() # If we should be holding, do the hold.
			wait_time = ceil((schedule_list[0][0] - datetime.now()).total_seconds()) # Determine how long to wait.
			if wait_time < 0 and wait_time > -timeDelta: # If the wait_time ends up being negative, but we're within' the delta, just start the task.
				wait_time = 1
			elif wait_time < -timeDelta: # If the wait_time is negative, but also less than then the time delta then we need to trash that task.
				raise TimeoutError()
		except TimeoutError:
			logger.logSystem('Scheduler: The timeDelta for {} is passed so it will not be run <{}>.'.format(schedule_list[0][1],schedule_list[0]))
			schedule_list.pop(0) # If we can't run it, then remove it from the list.
		except SyntaxError:
			logger.logSystem('Scheduler: The task is formatted incorrectly. Removing the task. {}'.format(str(schedule_list[0])))
			schedule_list.pop(0)
		except Exception as e:
			logger.logSystem('Scheduler: There is a problem executing {}. It will be removed from the list. Exception: {}'.format(str(schedule_list[0][1]),str(e)))
			schedule_list.pop(0) # If there is a problem determining when to execute, remove it from the list
		else:
			# Wait until it's time to run our next task. If the time has already passed wait a second and then do it.
			logger.logSystem("Scheduler: Waiting {} seconds for task: {}.".format(str(wait_time),str(schedule_list[0][1])))
			# Wait for wait_time seconds but also check the shutdownEvent every second.
			sleep_time = 0.35 #seconds to sleep.
			for i in range(ceil(wait_time//sleep_time)): # Get the proper number if iterations to sleep.
				if shutdownEvent.is_set():
					return schedule_list
				time.sleep(sleep_time)
			runEvent.wait() # Pause if we need to wait for something.
			# run the next item on the Schedulelist.
			taskCompleted = _processTask(chip,schedule_list[0],shutdownEvent,experimentEvent,runEvent,nextQueue,disableCallback,logger)
			if taskCompleted:
				logger.logSystem("Scheduler: Task completed.")
				schedule_list.pop(0) # pop the first item off the list.

	return schedule_list

def updateScheduleFile(schedule_list,logger):
	"""
		This function will rewrite the Schedule list to contain the current tasks that haven't yet
		been completed. This would only happen if we are interrupted.

		Parameters
		----------
		List - Sorted schedule_list.

		Returns
		-------
		Bool - True if wrote to file successfuly. This will overwrite the old Schedule file.
			   False if there was some kind of failure.

		Raises
		------
		None!
	"""
	try:
		Schedule_copy = list(schedule_list)
		with open(Schedule_PATH + Schedule_TEMP,"w") as tempSchedule:
			for line in Schedule_copy:
				# Convert the datetime object back to a string for writing
				line[0] = line[0].strftime("%Y%m%d-%H%M%S")
				tempSchedule.write(" ".join(line)+"\n")
		# Try to change the name of the temp file. Delete the old file.
		os.rename(Schedule_FILE_PATH,GRAVEYARD_PATH+Schedule_FILE+datetime.now().strftime('%Y%m%d-%H%M%S'))
		os.rename(Schedule_PATH+Schedule_TEMP, Schedule_FILE_PATH)
	except (OSError, PermissionError) as e:
		logger.logError("Scheduler: Could not record new Schedule list.", e)
		return False
	except FileNotFoundError as e:
		logger.logError("Scheduler: The Schedule file does not exist right now!", e)
		return False
	return True

def run(chip,nextQueue,packetQueue,experimentEvent, runEvent, shutdownEvent,parserEmpty,disableCallback,logger):
	"""
	Method to handle the Schedule parser when running it. This allows the parser to be used when calling
	it from another module.

	Paramters
	---------
		chip - an SC16IS750 object.
		nextQueue - queue to put control characters for the WTC
		experimentEvent - threading.Event - pass through an event object to determine whether or not an experiment
		is running.
		runEvent - threading.Event - if clear() then pause the threadd
		shutdownEvent - threading.Event - if set() then we need to back out and shutdown.
		parserEmpty - threading.Event - if set() then the schedule is empty. This lets main know that it's okay to exit.
		disableCallback - threading.Event - if set() disable the callback in the interpreter. If clear() start it
		logger - the logging object for logging data

	Raises
	-------
	None

	Returns
	-------
	None
	"""
	logger.logSystem("Scheduler: Starting <{}>".format(Schedule_FILE_PATH))
	try:
		schedule_list = getScheduleList(logger)
		if schedule_list:
			# We will assume the Schedule-list is NOT sorted, and sort it.
			sortScheduleList(schedule_list,logger)
			if chip is not None:
				if not logger.bootWasSet():
					logger.logSystem('Scheduler: Waiting until the time is set...')
				while not logger.bootWasSet():
					if shutdownEvent.is_set():
						break
					else:
						time.sleep(.25)
				if not shutdownEvent.is_set():
					logger.logSystem('Scheduler: Beginning execution of tasks.')
					schedule_list = executeScheduleList(chip,nextQueue,schedule_list,shutdownEvent,experimentEvent,runEvent,disableCallback,logger)

			if schedule_list:
				logger.logSystem("Scheduler: The ScheduleParser has terminated early. Updating the Schedule file.")
				if updateScheduleFile(schedule_list,logger): # If we terminated early, re-write the Schedule file before leaving.
					logger.logSystem("Scheduler: Successfuly updated the Schedule file.<{}>".format(Schedule_FILE_PATH),"Scheduler: Finished.")
				else:
					logger.logError("Scheduler: Encountered a problem when trying to update the Schedule file!")
			else:
				logger.logSystem("Scheduler: Finished execution.")
				parserEmpty.set()
		else:
			logger.logSystem("Scheduler: Schedule list is not populated.")
			parserEmpty.set()
	except InterruptedError as interrupt:
		logger.logSystem("Scheduler: Interrupted.")

	logger.logSystem("Scheduler: Shutting down...")
	return