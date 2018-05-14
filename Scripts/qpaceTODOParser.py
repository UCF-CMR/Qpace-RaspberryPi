#! /usr/bin/env python3
<<<<<<< HEAD
# qpaceLogger.py by Jonathan Kessluk & Minh Pham
# 2-13-2018, Rev. 1.1
=======
# qpaceTODOParser.py by Jonathan Kessluk and Minh
# 2-13-2018, Rev. 1
>>>>>>> 5f4b21dad6e6717fcd6f37b438004667f9c4111b
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
from multiprocessing import Process
import qpaceLogger

TODO_PATH = "/mnt/c/Users/Jonat/Desktop/CMR/Scripts/PiInternal/todo_dir/"
TODO_FILE = "todo.txt"
TODO_FILE_PATH = TODO_PATH + TODO_FILE
TODO_TEMP = "todo_temp.tmp"

WTC_IRQ = 7

def _checkInterrupt(irq):
    if gpio.input(irq):
        raise InterruptedError("The WTC has requested to end processes and relinquish control.")

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
			qpaceLogger.logSystem([["Closing todo file."]])

	except OSError as e:
		# Couldn't open the todo file. Send an error to the error log.
		qpaceLogger.logError("Could not open todo file for reading.", e)
		qpaceLogger.logSystem([["Error opening the todo file."]])

	return todo_list

def sortTodoList(todo_list: list):
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
				qpaceLogger.logSystem([
					["Todo list","Time to invoke command is an invalid format and will be removed from the queue."].append(todo_list[i][0])
				])
				del todo_list[i]
			else:
				i+=1
		todo_list.sort() # Python will sort a 2D list based off the first argument of each nested list in ascending order.
	return todo_list

def executeTodoList(todo_list: list):
	"""
		This function will execute the todoList in order. If it is interrupted, it will return the todolist

	    Parameters
	    ----------
	    List - Sorted todo_list.

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
	try:
		while todo_list:
			#If we need to stop execution:
			_checkInterrupt(WTC_IRQ) # Check the interrupt BEFORE doing anything
			# How many seconds until our next task?
			wait_time = (todo_list[0][0] - datetime.now()).total_seconds()
			# Wait until it's time to run our next task. If the time has already passed wait a second and then do it.
			wait_time = wait_time if wait_time > 0 else 1
			qpaceLogger.logSystem([["Going to sleep for " + str(wait_time) + " seconds"]])
			time.sleep(wait_time)
			_checkInterrupt(WTC_IRQ) # Check the interrupt immediately upon waking up.
			# pop the item off the todo_list and run it.
			processTask(todo_list.pop(0))
	except InterruptedError as interrupt:
		qpaceLogger.logSystem([["The interrupt pin was set to high. Stopping execution of the todo list."]])
	finally:
		return todo_list

def processTask(task: list):
	"""
		This function handles processing a specific command given. This is what does the real "parsing"

		Parameters
		----------
		List - List that is the arguments to a command.
			   task[0] is when the command should execute.
			   task[1] is the name of the command.

		Returns
		-------
		Nothing!

		Raises
		------
		Nothing!

		Revisions
		---------
		Rev. 1.1 - 4/10/2018 Minh Pham (Added code execution to tasks.)
	"""
	qpaceLogger.logSystem([["Beginning execution of a task", task[1:]]])
	currentTask = task[1].upper()
	if currentTask == "EXPERIMENT":
		#Run an experiment file from the experiment directory
		print("We are running the experiment contained in: ", task[2]) # Placeholder
	elif currentTask == "SEND":
		#Sending data on the downlink? What's going to go here? Do we need this or is it handled
		#somewhere else?
		print("We are adding", task[2] ,"to the queue for sending down to ground station") # Placeholder
	elif currentTask == "VERIFY":
		#Verification methods. Figure out what this is actually going to be.
		print("Verifying the integrety of", task[2]) # Placeholder
	elif currentTask == "BACKUP":
		copy(task[2],task[3]) #Copy the file from task[2] to task[3]
		print("Attempting to create a backup of", task[2]) # Placeholder
		time.sleep(8)
	elif currentTask == "REPORT":
		#Reporting method. Figure out if this is necessary or what exactly it will do
		print("Saving data to the system log.") # Placeholder
	elif currentTask == "CODE":
		#Executing specified python file.
		os.system('python' + task[2])
	else:
		qpaceLogger.logSystem([["Unknown task!", task[1:]]])

def updateTodoFile(todo_list: list):
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
		qpaceLogger.logError("Could not record new todo list.", e)
		return False
	except FileNotFoundError as e:
		qpaceLogger.logError("The todo file does not exist right now!", e)
		return False
	return True


def run():

	gpio.set_mode(gpio.BOARD)
    gpio.setup(WTC_IRQ, gpio.IN)

	qpaceLogger.logSystem([
		["Entering main in the TODO parser", os.getcwd()],
		["Opening up the todo file and begining execution.",TODO_FILE_PATH]
	])
	try:
		_checkInterrupt(WTC_IRQ) # Check the interrupt pin before interacting with the todo list
		todo_list = getTodoList()
		if todo_list:
			_checkInterrupt(WTC_IRQ) # Chek the interrupt pin before sorting
			# We will assume the todo-list is NOT sorted, and sort it.
			sortTodoList(todo_list)
			_checkInterrupt(WTC_IRQ) # Check the interrupt pin before execution
			todo_list = executeTodoList(todo_list)

			if todo_list:
				qpaceLogger.logSystem([["The TODO parser has terminated early. Updating the todo file."]])
				if updateTodoFile(todo_list): # If we terminated early, re-write the todo file before leaving.
					qpaceLogger.logSystem([
						["Successfuly updated the todo file.", TODO_FILE_PATH],
						["Exiting the TODO parser.", os.getcwd()]
					])
				else:
					message = "Encountered a problem when trying to update the todo file!"
					qpaceLogger.logSystem([[message, TODO_FILE_PATH]])
					qpaceLogger.logError(message)
			else:
				qpaceLogger.logSystem([["Todo file has finished execution", TODO_FILE_PATH]])
				os.remove(TODO_FILE_PATH) # Do we want to delete the file or just leave it alone
	except InterruptedError as interrupt:
        logger.logSystem([["The Interpreter was interrupted. Shutting down the Interpreter..."]])
# Only do the following if we are running this as a script.
if __name__ == "__main__":
	run()