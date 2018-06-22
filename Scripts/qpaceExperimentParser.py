#! /usr/bin/env python3
# qpaceExperimentParser.py by Minh Pham, Chris Britt
#3-06-2018, Rev. 1.1
#Q-Pace project, Center for Microgravity Research
#University of Central Florida

import qpaceExperiment
import qpaceLogger

def experimentparser(filepath, isRunningEvent):
    """
    This function handles the parsing and execution of the raw text experiment files.

    Parameters
    ----------
    String - filepath - The path of the experiment file to be parsed.

    Returns
    -------
    None.

    Raises
    ------
    IOError - Function handles file I/O errors.
	
-----------------------------------------------------------------------------------
files should be formatted as such

command1 paramater1-1 paramter1-2
command2 paramater2-1 paramter2-2

paramters are optional for many of the commands

Example:

led true
init_gopro
press_capture
stepper_forawrd .1 15
stepper_reverse .1 15
soleniod 100 30
gopro_wait 500
gopro_stop_and_USB


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
    try:
        with open(filepath, 'r') as inputFile:
            for line in inputFile:
                instruction = line.split()
                if (instruction[0].upper() == "INIT_GOPRO"):
                    Experiment.init_gopro()
					
				elif (instruction[0].upper() == "PRESS_CAPTURE"):
                    Experiment.press_capture()
					
				elif (instruction[0].upper() == "GOPRO_WAIT"):
					wait_time = int(instruction[1])
					Experiment.gopro_wait(wait_time)
					
				elif (instruction[0].upper() == "GOPRO_START"):
					Experiment.gopro_start()
					
				elif (instruction[0].upper() == "GOPRO_STOP_AND_USB"):
					Experiment.gopro_stop_and_USB()
					
				elif (instruction[0].upper() == "STEPPER_FORWARD"):
					delay = int(instruction[1])
                    qturn = int(instruction[2])
					Experiment.stepper_forward(delay, qturn)
					
				elif (instruction[0].upper() == "STEPPER_REVERSE"):
					delay = int(instruction[1])
                    qturn = int(instruction[2])
					Experiment.stepper_reverse(delay, qturn)

                elif (instruction[0].upper() == "LED"):
                    power = (instruction[1].upper() == "TRUE")
                    Experiment.led(power)


                elif (instruction[0].upper() == "SOLENOID"):
                    enables = list()
                    frequency = float(instruction[1])
                    duration = float(instruction[2])
                    for i in range(3, len(instruction)):
                        enables.append(int(instruction[i]))
                    Experiment.solenoid(frequency, duration, enables)


    # Output to the logger here.
    except IOError as e:
        qpaceLogger.logError("Could not open experiment file at " + str(filepath) + ".", e)
        qpaceLogger.logSystem([["File I/O error occured."]])
    else:
        isRunningEvent.clear()
