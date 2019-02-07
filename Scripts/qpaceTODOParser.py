#! /usr/bin/env python3
# qpaceTODOParser.py by Jonathan Kessluk & Minh Pham
# 2-13-2018, Rev. 2
# Q-Pace project, Center for Microgravity Research
# University of Central Florida
#
# This program parses the todo file and then acts upon that information.

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

TODO_PATH = "/home/pi/data/text/"
TODO_FILE = "todo.txt"
TODO_FILE_PATH = TODO_PATH + TODO_FILE
TODO_TEMP = "todo.tmp"
GRAVEYARD_PATH = '/home/pi/graveyard/'
EXPERIMENT_DELTA = 600 # SECONDS

WTC_IRQ = 7

def getTodoList(logger):
	"""
		This function will gather the data from the todo list and parse it into a 2D array for manipulation and processing.

		Parameters
		----------
		None!

		Returns
		-------
		a List of Lists where the outer list is the "todo" task list and the inner lists are the individual commands. Each
		index of the inner lists are the individual arguments passed to the command.

		Note: if it cannot open the file for any reason the return will be empty.

		Raises
		------
		None!
	"""
	todo_list = []
	try:
		with open(TODO_FILE_PATH, 'r') as todofile:
			task_list = todofile.readlines()
			for task in task_list:
				task = task.replace('\n','')
				# Add every string to the todo_list
				todo_list.append(task.split(" "))
	except FileNotFoundError:
		logger.logSystem('TodoParser: There is not todo file found at {}'.format(TODO_FILE_PATH))
	except OSError as e:
		# Couldn't open the todo file. Send an error to the error log.
		logger.logError("TodoParser: Could not open todo file for reading.", e)

	return todo_list

def sortTodoList(todo_list,logger):
	"""
		This function will gather the data from the todo list and parse it into a 2D array for manipulation and processing.

		Parameters
		----------
		List - The unsorted todo list receceived from getTodoList().

		Returns
		-------
		List - The sorted todo list. Sorted by time to executed. If todo_list is input as empty, the function will return empty.

		Raises
		------
		None!
	"""
	if todo_list:
		# i = 0
		# #This loop pushes all the queue/now/or wait commands to the front of the list
		# #TODO deterime if we even want the queue/now/wait functionality
		# while i < len(todo_list):
		# 	offset = 0 # Start the offset at 0 because when wemove things the cmd was deleted so the position is really i-1
		# 	pattern_qnw = re.compile("QUEUE|NOW|WAIT:\d+")
		# 	pattern_nw = re.compile("QUEUE|WAIT:\d+")
		# 	# if the time argument is QUEUE,NOW, or WAIT
		# 	if pattern_qnw.match(todo_list[i][0]):
		# 		# if the time argument is NOW
		# 		if todo_list[i][0] == "NOW":
		# 			# Move that NOW command to the front of the list to do it ASAP
		# 			todo_list.insert(0,todo_list[i])
		# 			del todo_list[i]
		# 			# Grab anything after the current NOW that is a QUEUE or WAIT and move it ahead of everyone
		# 				# else but in the proper order following behind the current NOW.
		# 			while(pattern_nw.match(todo_list[i+offset][0])):
		# 				todo_list.insert(offset,todo_list[i+offset])
		# 				del todo_list[i+offset]
		# 				offset += 1
		# 	i += offset+1
		i = 0
		while i < len(todo_list):
			try:
				#Create a date time from the string
				todo_list[i][0] = datetime.strptime(todo_list[i][0],"%Y%m%d-%H%M%S")
			except (ValueError,TypeError) as e:
				logger.logSystem("TodoParser: Removed an item due to invalid time format. <{}>".format(todo_list[i]))
				del todo_list[i]
			else:
				i+=1
		todo_list.sort() # Python will sort a 2D list based off the first argument of each nested list in ascending order.
		#updateTodoFile(todo_list,logger)
	return todo_list

def _processTask(chip,task,shutdownEvent,experimentEvent,runEvent,nextQueue,logger):
	"""
		This function handles processing a specific command given. This is what does the real "parsing"

		Parameters
		----------
		chip - an SC16IS750 object
		task - List - List that is the arguments to a command.
			   task[0] is when the command should execute.
			   task[1] is the name of the command.
			   task[2:] is args for that command.
		experimentEvent - threading.Event - if set() then there is an experiment going on.
											if clear() there is no experiment running.

		Returns
		-------
		True for successful completion of the task.
		False for failure to complete a task.

		Raises
		------
		Nothing!

		Revisions
		---------
		Rev. 1.1 - 4/10/2018 Minh Pham (Added code execution to tasks.)
	"""
	logger.logSystem("TodoParser: Beginning execution of a task. {}".format(str(task[1:])))
	currentTask = task[1].upper()
	try:
		if currentTask == "EXPERIMENT":

			try:
				# If experimentEvent exists and is not set, then let's run an experiment.
				if experimentEvent is None or experimentEvent.is_set():
					raise StopIteration('experimentEvent is None or experimentEvent is set.') # If experimentEvent does not exist or is set, return False to know there is a failure.

				# Run an experiment file from the experiment directory
				logger.logSystem("TodoParser: Running an experiment.", task[2]) # Placeholder
				parserThread = threading.Thread(name='experimentParser',target=exp.run, args=(task[2],experimentEvent,runEvent,logger,nextQueue))
				parserThread.start()
			except Exception as e:
				logger.logError('TodoParser: Task failed',e)
				return False

		elif currentTask == "COPY":  #Back up a file
			logger.logSystem("Attempting to create a backup.", ROOTPATH + task[2], ROOTPATH + task[3]) # Placeholder
			try:
				copy(ROOTPATH + task[2], ROOTPATH + task[3]) #Copy the file from task[2] to task[3]
			except Exception as e:
				logger.logError('TodoParser: Task failed',e)
				return False # The task failed
		elif currentTask == "REPORT":  #Get the status
			logger.logSystem("TodoParser: Saving status to file.")
			try:
				cmd.Command().saveStatus(logger)
			except:
				logger.logError('TodoParser: Task failed',e)
				return False # The task failed
		elif currentTask == 'SPLIT':
			logger.logSystem('TodoParser: Splitting a video...')
			cmd.Command().splitVideo(logger," ".join(task[2:]).encode('ascii'),silent=True)
		elif currentTask == 'CONVERT':
			logger.logSystem('TodoParser: Converting a video...')
			cmd.Command().convertVideo(logger," ".join(task[2:]).encode('ascii'),silent=True)
		elif currentTask == 'SHUTDOWN':
			logger.logSystem('TodoParser: Shutdown!')
			os.system('sleep 5 && sudo halt &')
			self.shutdownEvent.set()
		elif currentTask == 'HANDBRAKE':
			logger.logSystem('TodoParser: Running handbrake on a video...')
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
				logger.logSystem('TodoParser: The task could not be completed due to an import error.')
			except Exception as e:
				logger.logError('TodoParser: The task encountered an error.',e)
				return False # It failed.
		elif currentTask == 'LOG':
			logger.logSystem('TodoParserLog: {}'.format(' '.join(task[2:])))
		else:
			logger.logSystem("TodoParser: Unknown task!", str(task[1:]))
	except ValueError as err:
		logger.logSystem('TodoParser(ValueError): The task could not be completed. <{}>'.format(task))
	except StopIteration as err:
		logger.logSystem('TodoParser: Task aborted. {}'.format(str(err)))

	return True # If we reach here, assume everything was a success.

def executeTodoList(chip,nextQueue,todo_list, shutdownEvent, experimentEvent, runEvent,logger):
	"""
		This function will execute the todoList in order. If it is interrupted, it will return the todolist

		Parameters
		----------
		chip - an SC16IS750 object.
		todo_list - List - Sorted todo_list. (Sorted by the timestamp to execute.)
		shutdownEvent - threading.Event - if set() then we need to back out and shutdown.
		experimentEvent - threading.Event - pass through an event object to determine whether or not an experiment
										 is running.

		Returns
		-------
		List - A sorted todo_list that is a subset of the original todolist. Only returns a list
		if it was interrupted prematurly. Otherwise, if it completes properly, it will return
		an empty list

		Raises
		------
		None!
	"""
	#signal.signal(STOP_SIGNAL, stop_handler)
	completedTask = True
	timeDelta = EXPERIMENT_DELTA

	# We ideally want to use the global threading.Event, but worst case is it doesn't exist.
	# If it doesn't, lets create one locally so we have something to use regardless.
	if experimentEvent is None:
		experimentEvent = threading.Event()
	while todo_list and not shutdownEvent.is_set():
		todo_list = list(todo_list)
		# How many seconds until our next task?
		try:
			runEvent.wait() # If we should be holding, do the hold.
			wait_time = ceil((todo_list[0][0] - datetime.now()).total_seconds()) # Determine how long to wait.
			if wait_time < 0 and wait_time > -timeDelta: # If the wait_time ends up being negative, but we're within' the delta, just start the task.
				wait_time = 1
			elif wait_time < -timeDelta: # If the wait_time is negative, but also less than then the time delta then we need to trash that task.
				raise TimeoutError()
		except TimeoutError:
			logger.logSystem('TodoParser: The timeDelta for {} is passed so it will not be run <{}>.'.format(todo_list[0][1],todo_list[0]))
			todo_list.pop(0) # If we can't run it, then remove it from the list.
		except Exception as e:
			logger.logSystem('TodoParser: There is a problem executing {}. It will be removed from the list. Exception: {}'.format(str(todo_list[0][1]),str(e)))
			todo_list.pop(0) # If there is a problem determining when to execute, remove it from the list
		else:
			# Wait until it's time to run our next task. If the time has already passed wait a second and then do it.
			logger.logSystem("TodoParser: Waiting {} seconds for task: {}.".format(str(wait_time),str(todo_list[0][1])))
			# Wait for wait_time seconds but also check the shutdownEvent every second.
			sleep_time = 0.35 #seconds to sleep.
			for i in range(ceil(wait_time//sleep_time)): # Get the proper number if iterations to sleep.
				if shutdownEvent.is_set():
					return todo_list
				time.sleep(sleep_time)
			runEvent.wait() # Pause if we need to wait for something.
			# run the next item on the todolist.
			taskCompleted = _processTask(chip,todo_list[0],shutdownEvent,experimentEvent,runEvent,nextQueue,logger)
			if taskCompleted:
				logger.logSystem("TodoParser: Task completed.")
				todo_list.pop(0) # pop the first item off the list.

	return todo_list

def updateTodoFile(todo_list,logger):
	"""
		This function will rewrite the todo list to contain the current tasks that haven't yet
		been completed. This would only happen if we are interrupted.

		Parameters
		----------
		List - Sorted todo_list.

		Returns
		-------
		Bool - True if wrote to file successfuly. This will overwrite the old todo file.
			   False if there was some kind of failure.

		Raises
		------
		None!
	"""
	try:
		todo_copy = list(todo_list)
		with open(TODO_PATH + TODO_TEMP,"w") as tempTodo:
			for line in todo_copy:
				# Convert the datetime object back to a string for writing
				line[0] = line[0].strftime("%Y%m%d-%H%M%S")
				tempTodo.write(" ".join(line)+"\n")
		# Try to change the name of the temp file. Delete the old file.
		os.rename(TODO_FILE_PATH,GRAVEYARD_PATH+TODO_FILE+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
		time.sleep(1)
		os.rename(TODO_PATH+TODO_TEMP, TODO_FILE_PATH)
	except (OSError, PermissionError) as e:
		logger.logError("TodoParser: Could not record new todo list.", e)
		return False
	except FileNotFoundError as e:
		logger.logError("TodoParser: The todo file does not exist right now!", e)
		return False
	return True

def run(chip,nextQueue,packetQueue,experimentEvent, runEvent, shutdownEvent,parserEmpty,logger):
	"""
	Method to handle the todo parser when running it. This allows the parser to be used when calling
	it from another module.

	Paramters
	---------
	chip - an SC16IS750 object
	experimentEvent - threading.Event - pass through an event object to determine whether or not an experiment
									 is running.
	runEvent - threading.Event - acts as a wait-until-set object. If not set(), wait until set().
	shutdownEvent - threading.Event - used to flag that we need to shutdown the Pi.

	Raises
	-------
	None

	Returns
	-------
	None
	"""
	logger.logSystem("TodoParser: Starting <{}>".format(TODO_FILE_PATH))
	try:
		todo_list = getTodoList(logger)
		if todo_list:
			# We will assume the todo-list is NOT sorted, and sort it.
			sortTodoList(todo_list,logger)
			if chip is not None:
				todo_list = executeTodoList(chip,nextQueue,todo_list,shutdownEvent,experimentEvent,runEvent,logger)

			if todo_list:
				logger.logSystem("TodoParser: The TodoParser has terminated early. Updating the todo file.")
				if updateTodoFile(todo_list,logger): # If we terminated early, re-write the todo file before leaving.
					logger.logSystem("TodoParser: Successfuly updated the todo file.<{}>".format(TODO_FILE_PATH),"TodoParser: Finished.")
				else:
					logger.logError("TodoParser: Encountered a problem when trying to update the todo file!")
			else:
				logger.logSystem("TodoParser: Finished execution.")
				parserEmpty.set()
		else:
			logger.logSystem("TodoParser: Todo list is not populated.")
			parserEmpty.set()
	except InterruptedError as interrupt:
		logger.logSystem("TodoParser: Interrupted.")

	logger.logSystem("TodoParser: Shutting down...")
	return