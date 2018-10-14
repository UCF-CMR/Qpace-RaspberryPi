#! /usr/bin/env python3
# qpaceExperimentParser.py by Minh Pham, Chris Britt, Jonathn Kessluk
#3-06-2018, Rev. 2
#Q-Pace project, Center for Microgravity Research
#University of Central Florida

import qpaceExperiment as exp
import qpaceLogger as logger
import datetime
import time

def run(filepath, isRunningEvent):
	"""
	This function handles the parsing and execution of the raw text experiment files.

	Parameters
	----------
	filepath - string - The path of the experiment file to be parsed.
	isRunningEvent - threading.event - If an experiment is running, isRunningEvent should be .set()

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
	START [AUTHOR]
	SUBROUTINE [PROFILE NAME]
	CALL [PROFILE NAME]
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
	LED STROBE [ON_DELAY] [OFF_DELAY]
	LED STROBE [HZ]
	GOPRO ON
	GOPRO OFF
	GOPRO START
	GOPRO STOP
	GOPRO TRANSFER
	STEPPER QTURN [N] [Delay_per_qturn]
	STEPPER STEP [N] [Delay_per_step]
	SOLENOID [GROUP] TAP
	SOLENOID [GROUP] [HZ] [DURATION] [OVERRIDE] <OVERRIDE>
	SOLENOID [GROUP] RAMP [START_HZ] [END_HZ] [ACCURACY] <OVERRIDE>



	This example file will:
	turn on the led
	initialize the gopro
	start recording
	move the stepper motor forward by some amount at some speed (actual speeds should be tunned on EM stack)
	move the stpper motor in revese by the same amount
	vibrate the experimant for 30 seconds and 100 Hz
	Wait an addition 500 seconds of recording time
	Stop the recording and transfer the video to the Pis

	"""
	experimentStartTime = None
	experimentLog = None
	isRecording = False
	try:
		with open(filepath, 'r') as inputFile:
			for line in inputFile:
				instruction = line.upper().split()
				try:

					if (instruction[0][:2] == "//" or instruction[0][:2] == '#' or instruction[0].upper() == "COMMENT"): #COMMENT
						# This is a comment so ignore that line.
						pass
					elif(instruction[0] == 'START'):
						# Start an experiment if one hasn't started yet.
						if isRunningEvent.is_set():
							raise StopIteration('An experiment is already running.')
						isRunningEvent.set()
						experimentStartTime= datetime.datetime.now()
						author = ' '.join(instruction[1:]) or 'Unknown'
						experimentLog = open('exp_{}_{}'.format(experimentStartTime,author),'w')
						logger.logSystem('ExpParser: Starting Experiment written by {}.'.format(author))
					elif(instruction[0] == 'END' or instruction[0] == 'EXIT'):
						# End the experiment if one is running.
						if isRunningEvent.is_set():
							isRunningEvent.clear()
							if experimentLog:
								experimentLog.close()
							logger.logSystem('ExpParser: Ending an Experiment. Execution time:{} seconds.'.format((experimentStartTime - datetime.datetime.now()).seconds))
					elif(instruction[0] == 'INIT'):
						# Initialize an Experiment.
						# Reset pins, turn on LED, start camera recording.
						logger.logSystem('ExpParser: Initializing an Experiment. (Reset,LED,GoPro)')
						exp.reset()
						exp.led(1)
						exp.gopro_on()

					elif(instruction[0] == 'RESET'):
						# Just reset all the pins or one pin
						if len(instruction) == 1:
							who = 'all'
							group = None
						elif instruction[1] == 'SOLENOID':
							who = 'solenoid'
							group = exp.PINGROUP.solenoid
						elif instruction[1] == 'STEPPER':
							who = 'stepper'
							group = exp.PINGROUP.stepper
						elif instruction[1] == 'LED':
							who = 'LED'
							group = exp.PINGROUP.led
						elif instruction[1] == 'GOPRO':
							who = 'GoPro'
							group = exp.PINGROUP.gopro

						logger.logSystem('ExpParser: Resetting {} pins to their defaults.')
						exp.reset(group)
					elif(instruction[0] == 'CLEANUP'):
						# Clean up will turn off the LED, GoPro, and reset the pins.
						exp.reset()
						logger.logSystem('ExpParser: Cleanup. I.e. reset the pins.')
					elif(instruction[0] == 'DELAY'):
						# Do a delay in ms
						ms = 200
						try:
							if len(instruction) > 1:
								ms = int(instruction[1])
						except: pass
						logger.logSystem('ExpParser: Delay for {} ms'.format(ms))
						time.sleep(ms/1000)
					elif(instruction[0] == 'LED'):
						# Modify the LED
						if len(instruction) > 1:
							logger.logSystem('ExpParser: The LED has been set to {}.'.format(instruction[1]))
							if instruction[1] == 'ON':
								exp.led(1)
							elif instruction[1] == 'OFF':
								exp.led(0)
							elif instruction[1] == 'STROBE':
								# TODO: Write a seperate process for this to happen in the background.
								pass
					elif(instruction[0] == 'GOPRO'):
						# Modify gopro attributes
						if len(instruction)>1:
							startTime = datetime.datetime.now()
							logger.logSystem('ExpParser: The GoPro has been set to {}.'.format(instruction[1]))
							if instruction[1] == 'ON':
								if not exp.read(exp.PIN.GOPPWR):
									exp.gopro_on()
							elif instruction[1] == 'OFF':
								if exp.read(exp.PIN.GOPPWR):
									exp.reset(exp.PINGROUP.gopro)
							elif instruction[1] == 'START':
								if exp.read(exp.PIN.GOPPWR) and not isRecording:
									exp.press_capture()
							elif instruction[1] == 'STOP':
								if exp.read(exp.PIN.GOPPWR) and isRecording:
									exp.press_capture()
							elif instruction[1] == 'TRANSFER':
								if exp.read(exp.PIN.GOPPWR):
									exp.goProTransfer()
							duration = (startTime - datetime.datetime.now()).seconds
							logger.logSystem('ExpControl: GoPro done. This took {} seconds.'.format(duration))
					elif(instruction[0] == 'STEPPER'):
						if len(instruction) > 3 and instruction[1] in ('QTURN','STEP'):
							logger.logSystem('ExpParser: Stepper will perform {} {}(s)'.format(instruction[2],instruction[1].lower()))
							delay = 0.2
							try:
								if len(instruction) == 4:
									delay = int(instruction[3])/1000
							except:pass
							try:
								turns = int(instruction[2])
							except:
								pass
							else:
								if instruction[1] == 'QTURN':
									exp.stepper_turn(delay,turns,multiplier=4)
								elif instruction[1] == 'STEP':
									exp.stepper_turn(delay,turns)


					elif(instruction[0] == 'SOLENOID'):
						if len(instruction) > 2:
							group = []
							if instruction[1].find('X') is not -1:
								group.push(exp.PIN.SOLX)
							if instruction[1].find('Y') is not -1:
								group.push(exp.PIN.SOLY)
							if instruction[1].find('Z') is not -1:
								group.push(exp.PIN.SOLZ)
							group = tuple(group)

							if 'OVERRIDE' in instruction:
								override = True
								instruction.remove('OVERRIDE')
							else:
								override = False

							if len(group)>0:
								if instruction[2] == 'TAP':
									exp.solenoid_tap(group[0])
								elif instruction[2] == 'RUN':
									if len(instruction) >= 5:
										exp.solenoid_run(group[0],int(instruction[3]),int(instruction[4]),override=override)
								elif instruction[2] == 'RAMP':
									if len(instruction) == 5:
										exp.solenoid_ramp(group[0],int(instruction[3]),int(instruction[4]),override=override)
									elif len(instruction) == 6:
										exp.solenoid_ramp(group[0],int(instruction[3]),int(instruction[4]),int(instruction[5]),override=override)

					elif(instruction[0] == 'SUBROUTINE' or instruction[0] == 'CALL'):
						print('Not implemented yet')
						#TODO Implement subroutine calls
				except StopIteration as e:
					pass

	# Output to the logger here.
	except IOError as e:
		qpaceLogger.logError("ExpParser: Could not open experiment file at " + str(filepath) + ".", e)
	else:
		if isRunningEvent.is_set():
			isRunningEvent.clear()
		if experimentLog:
			experimentLog.close()
