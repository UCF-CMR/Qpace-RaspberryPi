#! /usr/bin/env python3
# qpaceExperimentParser.py by Minh Pham, Chris Britt, Jonathn Kessluk, and Connor Westcott
#3-06-2018, Rev. 2
#Q-Pace project, Center for Microgravity Research
#University of Central Florida

import datetime
import time
import qpaceExperiment as expModule
import qpaceLogger as qpLog

def run(filename, isRunningEvent, runEvent,logger,nextQueue,disableCallback):
	"""
	This function handles the parsing and execution of the raw text experiment files.

	Parameters
	----------
	filename - string - The name of the experiment file to be parsed.
	isRunningEvent - threading.Event() - If an experiment is running, isRunningEvent should be .set()
	runEvent - threading.Event() - pause if runEvent is .clear()
	logger - qpaceLogger.Logger() -  used for writing log messages
	nextQueue - qpaceMain.Queue() -  the nextQueue to enqueue control characters for the solenoids and steppers
	disableCallback - threading.Event() - If we want to disable the callback, this should be .set()

	Returns
	-------
	None.

	Raises
	------
	None

	-----------------------------------------------------------------------------------

	Syntax:
	// [Comment]
	# [Comment]
	COMMENT [COMMENT]
	LOG [COMMENT]
	START [title]
	END
	INIT
	RESET
	RESET SOLENOID
	RESET STEPPER
	RESET LED
	RESET GOPRO
	CLEANUP
	DELAY [MS]
	LED ON
	LED OFF

	GOPRO ON
	GOPRO OFF
	GOPRO START
	GOPRO STOP
	GOPRO TRANSFER

	CAMERA SET OPTION:VALUE OPTION:VALUE OPTION:VALUE....
	CAMERA RECORD MILLISECONDS [FILENAME]
	CAMERA ESTOP
	CAMERA CAPTURE

	STEPPER QTURN [N] [Delay_in_ms_per_qturn]
	STEPPER STEP [N] [Delay_in_ms_per_step]
	SOLENOID [GROUP] TAP
	SOLENOID [GROUP] RUN [HZ] [DURATION] <OVERRIDE>
	SOLENOID [GROUP] RAMP [START_HZ] [END_HZ] [ACCURACY] <OVERRIDE>

	Also supports inline comments.
	"""
	logger.logSystem('ExpParser: Starting...')
	picam = expModule.Camera()
	exp = expModule.Action(logger=logger,queue=nextQueue)
	comment_tuple = ('#','//') # These are what will be used to have comments in the profile.
	logLocation = '/home/pi/data/text/'
	expLocation = '/home/pi/data/exp/'
	experimentStartTime = datetime.datetime.now() # Just in case the parser gets invoked on an empty file, seed the start time.
	experimentLog = None
	isRecording = False
	try:
		with open(expLocation + filename, 'r') as inputFile:
			# Determine if we need solenoids and/or steppers. Act accordingly.
			solenoidRequest = False
			stepperRequest = False
			inputLines = inputFile.readlines()
			# Look for SOLENOID or STEPPER. If we see that, we'll need to ask for them to turn on.
			for line in inputLines:
				instruction = line.upper().split()
				instruction = instruction[0] if instruction else None
				if instruction == 'SOLENOID':
					solenoidRequest = True
				elif instruction == 'STEPPER':
					stepperRequest = True

				if solenoidRequest and stepperRequest:
					break
			disableCallback.set()
			time.sleep(.35)
			# If we want the solenoids, let's request them. Failure to enable will abort the experiment.
			if solenoidRequest:
				logger.logSystem('ExpParser: WTC... may I have the solenoids please?')
				if not exp.wtc_request('SOLON'):
					raise StopIteration('WTC denied access to the solenoids.')

			# If we want the steppers, let's request them. Failure to enable will abort the experiment.
			if stepperRequest:
				logger.logSystem('ExpParser: WTC... may I have the steppers please?')
				if not exp.wtc_request('STEPON'):
					raise StopIteration('WTC denied access to the steppers.')
			disableCallback.clear()


			# At this point the solenoids and steppers should be enabled. NOW we can do some science!
			logger.logSystem('ExpParser: Experiment is ready to begin. Time to do science!')
			title = 'Unknown'
			# Begin interpreting the experiment.
			for line in inputLines:
				# Remove comments from the instructions.
				instruction = line
				for delimiter in comment_tuple:
					if delimiter in instruction:
						instruction = instruction.split(delimiter)
						instruction = (instruction[0] if instruction else ' ')
				instruction = instruction.upper().split()
				runEvent.wait() # If we should be waiting, then wait.

				if instruction:
					# Begin interpreting the instructions that matter.
					try:
						if(instruction[0] == 'START'):
							# Start an experiment if one hasn't started yet.
							if isRunningEvent.is_set():
								raise StopIteration('ExpParser: Attempted a start, but an experiment is already running: {}'.format(title))
							title = ' '.join(instruction[1:]) or 'Unknown'
							experimentStartTime= datetime.datetime.now()
							experimentLog = open('{}exp_{}_{}.qpe'.format(logLocation,experimentStartTime.strftime('%Y%m%d-%H%M%S'),title),'w')
							isRunningEvent.set()
							logMessage = 'ExpParser: Starting Experiment "{}" ({}).'.format(filename,title)
							logger.logSystem(logMessage)
							experimentLog.write('{}\n'.format(logMessage))
							exp.reset() # Reset the pins
						elif(instruction[0] == 'END' or instruction[0] == 'EXIT'):
							# End the experiment if one is running.
							logger.logSystem('ExpParser: Ending the experiment..')
							exp.reset()
							break
						# elif(instruction[0] == 'INIT'):
						# 	if isRunningEvent.is_set():
						# 		# Initialize an Experiment.
						# 		# Reset pins, turn on LED, start camera recording.
						# 		logMessage = 'ExpParser: Initializing an Experiment. (Reset,LED,GoPro)'
						# 		logger.logSystem(logMessage)
						# 		experimentLog.write('{}\n'.format(logMessage))
						# 		exp.reset()
						# 		exp.led(1)
						# 		# exp.gopro_on()
						elif(instruction[0] == 'COMMENT' or instruction[0] == 'LOG'):
							if isRunningEvent.is_set():
								# Write to the log whatever comment is here.
								comment = ' '.join(instruction[1:])
								experimentLog.write("Comment: {}\n".format(comment))

						elif(instruction[0] == 'RESET'):
							if isRunningEvent.is_set():
								# Just reset all the pins or one pin
								if len(instruction) == 1:
									who = 'all'
									group = None
								if 'SOLENOID' in instruction:
									who = 'solenoid'
									group = expModule.PINGROUP.solenoid
								if 'STEPPER' in instruction:
									who = 'stepper'
									group = expModule.PINGROUP.stepper
								if 'LED' in instruction:
									who = 'LED'
									group = expModule.PINGROUP.led
								if 'GOPRO' in instruction:
									who = 'GoPro'
									group = expModule.PINGROUP.gopro

								logMessage = 'ExpParser: Resetting {} pins to their defaults.'.format(who)
								logger.logSystem(logMessage)
								experimentLog.write('{}\n'.format(logMessage))
								exp.reset(group)
						# elif(instruction[0] == 'CLEANUP'):
						# 	if isRunningEvent.is_set():
						# 		# Clean up will turn off the LED, GoPro, and reset the pins.
						# 		exp.reset()
						# 		logMessage = 'ExpParser: Cleanup. I.e. reset the pins.'
						# 		logger.logSystem(logMessage)
						# 		experimentLog.write('{}\n'.format(logMessage))
						elif(instruction[0] == 'DELAY'):
							if isRunningEvent.is_set():
								# Do a delay in ms
								ms = 200
								try:
									if len(instruction) > 1:
										ms = int(instruction[1])
									else:
										logger.logSystem("No delay given, defaulting to 200 ms...")
								except: pass
								logMessage = 'ExpParser: Delay for {} ms'.format(ms)
								logger.logSystem(logMessage)
								experimentLog.write('{}\n'.format(logMessage))
								time.sleep(ms/1000)
						elif(instruction[0] == 'LED'):
							if isRunningEvent.is_set():
								# Modify the LED
								if len(instruction) > 1:
									logMessage = 'ExpParser: The LED has been set to {}.'.format(instruction[1])
									logger.logSystem(logMessage)
									experimentLog.write('{}\n'.format(logMessage))
									if instruction[1] == 'ON':
										exp.led(1)
									elif instruction[1] == 'OFF':
										exp.led(0)
									elif instruction[1] == 'STROBE':
										# TODO: Write a seperate process for this to happen in the background.
										pass
						elif(instruction[0] == 'STEPPER'):
							if isRunningEvent.is_set():
								if len(instruction) > 3 and instruction[1] in ('QTURN','STEP'):
									logMessage = 'ExpParser: Stepper will perform {} {}(s)'.format(instruction[2],instruction[1].lower())
									logger.logSystem(logMessage)
									experimentLog.write('{}\n'.format(logMessage))
									delay = 0.2
									turns = 0
									try:
										if len(instruction) == 4:
											delay = int(instruction[3])/1000
									except:
										log.logError("Problem parsing STEPPER command")
										pass
									try:
										turns = int(instruction[2])
									except:
										pass
									else:
										if instruction[1] == 'QTURN':
											exp.stepper_turn(delay,turns,multiplier=4)
										elif instruction[1] == 'STEP':
											exp.stepper_turn(delay,turns)

						elif(instruction[0] == 'CAMERA'):
							try:
								filename = 'exp_{}_{}'.format(title,str(round(time.time())))
								if instruction[1] == 'CAPTURE':
									try:
										capFile = instruction[2]
									except:
										capFile = filename
									picam.capture(filename=capFile)

								elif instruction[1] == 'RECORD':
									try:
										toRec = int(instruction[2])
									except:
										toRec = 300000 # 5 minutes
									try:
										recFile = instruction[3]
										if '/' in recFile:
											directory = '/home/pi/data/vid/' + recFile[:recFile.rindex('/')+1] # make sure to get the '/'
											print(directory)
											import os
											if not os.path.isdir(directory):
												try:
													os.mkdir(directory)
												except Exception as e:
													print(e)
									except:
										recFile = filename
									# This becomes a forked process... It can be shutdown by sending a signal to it with linux 'Kill'
									picam.record(time=toRec,filename=recFile)
								elif instruction[1] == 'SET':
									for inst in instruction[2:]:
										option,value = inst.split(':')
										option = option.lower()
										if option =='cfx':
											value = value.split(',')
											try:
												value = (int(value[0]),int(value[1]))
											except:
												value = (0,0)
										elif option == 'roi':
											value = value.split(',')
											try:
												value = (float(value[0]), float(value[1]), float(value[2]), float(value[3]))
											except:
												value = picam.attr['roi']
										else:
											value = int(value)
											
										if option in picam.attr:
											picam.attr[option] = value

										picam.verifySettings()
							except picam.CameraConfigurationError as cce:
								pass
								#TODO do something with the error. back out of the experiment. log it.
							except picam.CameraProcessFailed as cpe:
								pass
								#TODO Handle this
						elif(instruction[0] == 'SOLENOID'):
							if isRunningEvent.is_set():
								logMessage = 'ExpParser: Solenoid group {} will {} with these paramaters: {}'.format(instruction[1],instruction[2],instruction[3:])
								logger.logSystem(logMessage)
								experimentLog.write('{}\n'.format(logMessage))
								if len(instruction) > 2:
									group = []
									if instruction[1].find('X') is not -1:
										group.append(expModule.PIN.SOLX)
									if instruction[1].find('Y') is not -1:
										group.append(expModule.PIN.SOLY)
									if instruction[1].find('Z') is not -1:
										group.append(expModule.PIN.SOLZ)
									group = tuple(group)

									if 'OVERRIDE' in instruction:
										override = True
										instruction.remove('OVERRIDE')
									else:
										override = False

									if len(group)>0:
										if instruction[2] == 'TAP':
											exp.solenoid_tap(group)
										elif instruction[2] == 'RUN':
											if len(instruction) >= 5:
												exp.solenoid_run(group,int(instruction[3]),int(instruction[4]),override=override)
										elif instruction[2] == 'RAMP':
											if len(instruction) == 5:
												exp.solenoid_ramp(group,int(instruction[3]),int(instruction[4]),override=override)
											elif len(instruction) == 6:
												exp.solenoid_ramp(group,int(instruction[3]),int(instruction[4]),int(instruction[5]),override=override)

					except StopIteration as e:
						raise e

	# Output to the logger here.
	except FileNotFoundError:
		logger.logSystem("ExpParser: The experiment '{}' does not exist.".format(filename))
	except IOError as e:
		logger.logError("ExpParser: Could not open experiment file at {}. {}".format(str(expLocation + filename),str(e)))

	except StopIteration as e:
		logger.logSystem('ExpParser: Aborted the experiment. {}'.format(str(e)))
	except Exception as e:
		logger.logError('ExpParser: Aborted the experiment. Error: {}'.format(e.__class__),e)
	finally:
		# Clean up and close out all nicely.
		# if isRecording: # Ensure the gopro isn't recording anymore
		# 	exp.press_capture()

		if isRunningEvent.is_set(): # Ensure we are no longer running an experiment
			isRunningEvent.clear()

			if solenoidRequest:
				if not exp.wtc_request('SOLOFF'): # Request to turn off the solenoids
					logger.logSystem('ExpParser: The WTC denied turning off the steppers.')
			if stepperRequest:
				if not exp.wtc_request('STEPOFF'): # REquest to turn off the steppers
					logger.logSystem('ExpParser: The WTC denied turning off the steppers.')

			logMessage = 'ExpParser: Ending an Experiment. Execution time: {} seconds.'.format((datetime.datetime.now() - experimentStartTime).seconds)
			logger.logSystem(logMessage)
			if experimentLog:
				experimentLog.write('{}\n'.format(logMessage))
		if experimentLog: # Close the experiment Log
			experimentLog.close()

		# exp.reset() # Reset all the pins

		logger.logSystem("ExpParser: Closing ExpParser and returning to normal function...")
