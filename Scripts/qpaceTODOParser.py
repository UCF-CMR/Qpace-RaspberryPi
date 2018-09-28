#! /usr/bin/env python3
# qpaceTODOParser.py by Jonathan Kessluk & Minh Pham
# 2-13-2018, Rev. 1.1
# Q-Pace project, Center for Microgravity Research
# University of Central Florida
#
# This program parses the todo file and then acts upon that information.

import csv
import re
import os
import signal
import time
from datetime import datetime, date, timedelta
from math import ceil
from shutil import copy
import threading
import qpaceLogger as logger
import qpaceExperimentParser as exp
import qpacePiCommands as cmd
import qpaceWTCHandler as qph
from qpaceStates import QPCOMMAND

TODO_PATH = "/home/pi/data/text/"
TODO_FILE = "todo.txt"
TODO_FILE_PATH = TODO_PATH + TODO_FILE
TODO_TEMP = "todo_temp.tmp"

WTC_IRQ = 7

def getTodoList():
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
				# Convert every string to uppercase and then add it to the todo_list
				todo_list.append(task.split(" "))

	except OSError as e:
		# Couldn't open the todo file. Send an error to the error log.
		logger.logError("TodoParser: Could not open todo file for reading.", e)

	return todo_list

def sortTodoList(todo_list):
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
				logger.logSystem([
					["TodoParser: an item has an invalid time format and will be removed from the queue."] + todo_list[i]
				])
				del todo_list[i]
			else:
				i+=1
		todo_list.sort() # Python will sort a 2D list based off the first argument of each nested list in ascending order.
	return todo_list

def _processTask(chip,task,experimentEvent = None):
	"""
		This function handles processing a specific command given. This is what does the real "parsing"

		Parameters
		----------
		List - List that is the arguments to a command.
			   task[0] is when the command should execute.
			   task[1] is the name of the command.
			   task[2:] is args for that command.

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
	logger.logSystem([["TodoParser: Beginning execution of a task.", str(task[1:])]])
	currentTask = task[1].upper()
	if currentTask == "EXPERIMENT":
		# If experimentEvent exists and is not set, then let's run an experiment.
		if experimentEvent is not None and not experimentEvent.is_set():
			#Run an experiment file from the experiment directory
			logger.logSystem([["TodoParser: Running an experiment.", task[2]]]) # Placeholder
			parserThread = threading.Thread(name='experimentParser',target=exp.experimentparser, args=(task[2],experimentEvent))


			qph.NextQueue.enqueue('ALLON')
			queueReturn = qph.NextQueue.waitAndReturn()
			if queueReturn == QPCOMMAND['True']:
				logger.logSystem([["TodoParser: Solenoids enabled. Beginning experiment."]])
				experimentEvent.set()
				parserThread.start()
			else:
				logger.logSystem([["TodoParser: Solenoids not enabled. Experiment is being purged from the list."]])
		else: # If experimentEvent does not exist or is set, return True to know there is a failure.
			return False
	elif currentTask == "BACKUP":  #Back up a file
		copy(task[2],task[3]) #Copy the file from task[2] to task[3]
		logger.logSystem([["Attempting to create a backup.",task[2],task[3]]]) # Placeholder
	elif currentTask == "REPORT":  #Get the status
		logger.logSystem([["TodoParser: Saving status to file."]])
		cmd.Command.saveStatus(None,None,None)
	else:
		logger.logSystem([["TodoParser: Unknown task!", str(task[1:])]])

	return True # If we reach here, assume everything was a success.

def executeTodoList(chip,todo_list, shutdownEvent, experimentEvent = None):
	"""
		This function will execute the todoList in order. If it is interrupted, it will return the todolist

		Parameters
		----------
		todo_list - List - Sorted todo_list. (Sorted by the timestamp to execute.)
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

	# We ideally want to use the global threading.Event, but worst case is it doesn't exist.
	# If it doesn't, lets create one locally so we have something to use regardless.
	if experimentEvent is None:
		experimentEvent = threading.Event()
	while todo_list and not shutdownEvent.isSet():
		# How many seconds until our next task?
		try:
			wait_time = ceil((todo_list[0][0] - datetime.now()).total_seconds()) # Determine how long to wait.
		except:
			todo_list = todo_list[1:] # IF there is a problem determining when to execute, remove it from the list.
		else:
			# Wait until it's time to run our next task. If the time has already passed wait a second and then do it.
			wait_time = wait_time if wait_time > 0 else 1
			logger.logSystem([["TodoParser: Waiting " + str(wait_time) + " seconds for "+todo_list[0][1]+"."]])
			# Wait for wait_time seconds but also check the interrupt every second.
			for i in range(wait_time):
				if shutdownEvent.isSet():
					return todo_list
				time.sleep(.5)
			# run the next item on the todolist.
			taskCompleted = _processTask(chip,todo_list[0],experimentEvent)
			if taskCompleted:
				logger.logSystem([["TodoParser: Task completed.",str(todo_list[0])]])
				todo_list = todo_list[1:] # pop the first item off the list.


	return todo_list

def updateTodoFile(todo_list):
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
		with open(TODO_PATH + TODO_TEMP,"w") as tempTodo:
			for line in todo_list:
				# Convert the datetime object back to a string for writing
				line[0] = line[0].strftime("%Y%m%d-%H%M%S")
				tempTodo.write(" ".join(line)+"\n")
		# Try to change the name of the temp file. Delete the old file.
		# TODO do we want to archive the old todo file or just let it die?
		os.remove(TODO_FILE_PATH)
		os.rename(TODO_PATH+TODO_TEMP, TODO_FILE_PATH)
	except (OSError, PermissionError) as e:
		logger.logError("TodoParser: Could not record new todo list.", e)
		return False
	except FileNotFoundError as e:
		logger.logError("TodoParser: The todo file does not exist right now!", e)
		return False
	return True

def run(chip,experimentEvent, runEvent, shutdownEvent):
	"""
	Method to handle the todo parser when running it. This allows the parser to be used when calling
	it from another module.

	Paramters
	---------
	experimentEvent - threading.Event - pass through an event object to determine whether or not an experiment
									 is running.

	Raises
	-------
	None

	Returns
	-------
	None
	"""

	logger.logSystem([["TodoParser: Starting ...", TODO_FILE_PATH]])
	try:
		todo_list = getTodoList()
		if todo_list:
			# We will assume the todo-list is NOT sorted, and sort it.
			sortTodoList(todo_list)
			if chip is not None:
				todo_list = executeTodoList(chip,todo_list,shutdownEvent,experimentEvent)

			if todo_list:
				logger.logSystem([["TodoParser: The TodoParser has terminated early. Updating the todo file."]])
				if updateTodoFile(todo_list): # If we terminated early, re-write the todo file before leaving.
					logger.logSystem([
						["TodoParser: Successfuly updated the todo file.", TODO_FILE_PATH],
						["TodoParser: Done"]
					])
				else:
					logger.logError("TodoParser: Encountered a problem when trying to update the todo file!")
			else:
				logger.logSystem([["TodoParser: Finished execution", TODO_FILE_PATH]])
				#os.remove(TODO_FILE_PATH) # Do we want to delete the file or just leave it alone
		else:
			logger.logSystem([["TodoParser: Todo list is empty."]])
	except InterruptedError as interrupt:
		logger.logSystem([["TodoParser: Interrupted."]])

	logger.logSystem([["TodoParser: Shutting down..."]])
	return