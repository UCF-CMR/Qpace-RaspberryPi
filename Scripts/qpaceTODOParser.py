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
import RPi.GPIO as gpio
from datetime import datetime, date, timedelta
from shutil import copy
import threading
import qpaceLogger as logger
import qpaceExperimentParser as exp
import qpacePiCommands as cmd
import qpaceChecksum as checksum

TODO_PATH = "/home/pi/todo_dir/"
TODO_FILE = "todo.txt"
TODO_FILE_PATH = TODO_PATH + TODO_FILE
TODO_TEMP = "todo_temp.tmp"

WTC_IRQ = 7

def _checkInterrupt():
    """
    Check the WTC_IRQ pin to see if it's HIGH or LOW. If it's HIGH, throw an InterruptedError

    Raises
    ------
    InterruptedError - If the WTC_IRQ pin is HIGH
    """
    if gpio.input(WTC_IRQ):
        raise InterruptedError("The WTC has requested to relinquish control.")

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
			task_list = todofile.read().splitlines()
			for task in task_list:
				# Convert every string to uppercase and then add it to the todo_list
				todo_list.append(task.split(" "))
			logger.logSystem([["Closing todo file."]])

	except OSError as e:
		# Couldn't open the todo file. Send an error to the error log.
		logger.logError("Could not open todo file for reading.", e)
		logger.logSystem([["Error opening the todo file."]])

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
					["Todo list","Time to invoke command is an invalid format and will be removed from the queue."].append(todo_list[i][0])
				])
				del todo_list[i]
			else:
				i+=1
		todo_list.sort() # Python will sort a 2D list based off the first argument of each nested list in ascending order.
	return todo_list

def _processTask(chip,task,runningEvent = None):
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
	logger.logSystem([["Beginning execution of a task", str(task[1:])]])
	currentTask = task[1].upper()
	if currentTask == "EXPERIMENT":
        # If runningEvent exists and is not set, then let's run an experiment.
        if runningEvent is not None and not runningEvent.is_set():
    		#Run an experiment file from the experiment directory
    		logger.logSystem([["Running an experiment.", task[2]]]) # Placeholder
            parserThread = threading.Thread(name='experimentParser',target=exp.experimentparser, args=(task[2],runningEvent))
            parserThread.start()
            runningEvent.set()
        else: # If runningEvent does not exist or is set, return True to know there is a failure.
            return False
	elif currentTask == "BACKUP":  #Back up a file
		copy(task[2],task[3]) #Copy the file from task[2] to task[3]
		print("Attempting to create a backup of", task[2]) # Placeholder
        #TODO write backup scripts
	elif currentTask == "REPORT":  #Get the status
		status = cmd.getStatus()
        status = status.split('\n')
        cmd.saveStatus(None,None,None)
        cmd.sendFile(chip,'REPORT','status_*.txt') #TODO test if this actually works
	else:
		logger.logSystem([["Unknown task!", str(task[1:])]])

    return True # If we reach here, assume everything was a success.

def executeTodoList(chip,todo_list, runningEvent = None):
	"""
		This function will execute the todoList in order. If it is interrupted, it will return the todolist

	    Parameters
	    ----------
	    todo_list - List - Sorted todo_list. (Sorted by the timestamp to execute.)
        runningEvent - threading.Event - pass through an event object to determine whether or not an experiment
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
	try:
        # We ideally want to use the global threading.Event, but worst case is it doesn't exist.
        # If it doesn't, lets create one locally so we have something to use regardless.
        if runningEvent is None:
            runningEvent = threading.Event()
		while todo_list:
			#If we need to stop execution:
			_checkInterrupt() # Check the interrupt BEFORE doing anything
			# How many seconds until our next task?
			try:
                wait_time = (todo_list[0][0] - datetime.now()).total_seconds() # Determine how long to wait.
            except:
                todo_list = todo_list[1:] # IF there is a problem determining when to execute, remove it from the list.
			else:
                # Wait until it's time to run our next task. If the time has already passed wait a second and then do it.
			    wait_time = wait_time if wait_time > 0 else 1
    			logger.logSystem([["Waiting for " + str(wait_time) + " seconds to complete the next task."]])
                # Wait for wait_time seconds but also check the interrupt every second.
                for i in range(wait_time):
                    time.sleep(.5)
                    _checkInterrupt()
    			# run the next item on the todolist.
    			taskCompleted = _processTask(chip,todo_list[0],runningEvent)
                if taskCompleted:
                    logger.logSystem([["Task completed.",str(todo_list[0])]])
                    todo_list = todo_list[1:] # pop the first item off the list.

	except InterruptedError as interrupt:
		logger.logSystem([["The interrupt pin was set to high. Stopping execution of the todo list."]])
	finally:
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
		logger.logError("Could not record new todo list.", e)
		return False
	except FileNotFoundError as e:
		logger.logError("The todo file does not exist right now!", e)
		return False
	return True

def run(chip = None,runningEvent = None):
    """
    Method to handle the todo parser when running it. This allows the parser to be used when calling
    it from another module.

    Paramters
    ---------
    runningEvent - threading.Event - pass through an event object to determine whether or not an experiment
                                     is running.

    Raises
    -------
    None

    Returns
    -------
    None
    """

	gpio.set_mode(gpio.BOARD)
    gpio.setup(WTC_IRQ, gpio.IN)

	logger.logSystem([
		["Entering main in the TODO parser", os.getcwd()],
		["Opening up the todo file and begining execution.",TODO_FILE_PATH]
	])
	try:
		_checkInterrupt() # Check the interrupt pin before interacting with the todo list
		todo_list = getTodoList()
		if todo_list:
			_checkInterrupt() # Chek the interrupt pin before sorting
			# We will assume the todo-list is NOT sorted, and sort it.
			sortTodoList(todo_list)
			_checkInterrupt() # Check the interrupt pin before execution
            if chip is not None:
			    todo_list = executeTodoList(chip,todo_list,runningEvent)

			if todo_list:
				logger.logSystem([["The TODO parser has terminated early. Updating the todo file."]])
				if updateTodoFile(todo_list): # If we terminated early, re-write the todo file before leaving.
					logger.logSystem([
						["Successfuly updated the todo file.", TODO_FILE_PATH],
						["Exiting the TODO parser.", os.getcwd()]
					])
				else:
					message = "Encountered a problem when trying to update the todo file!"
					logger.logSystem([[message, TODO_FILE_PATH]])
					logger.logError(message)
			else:
				logger.logSystem([["Todo file has finished execution", TODO_FILE_PATH]])
				os.remove(TODO_FILE_PATH) # Do we want to delete the file or just leave it alone
	except InterruptedError as interrupt:
        logger.logSystem([["The Interpreter was interrupted. Shutting down the Interpreter..."]])