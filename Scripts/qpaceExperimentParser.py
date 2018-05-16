#! /usr/bin/env python3
# qpaceExperimentParser.py by Minh Pham
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

    """
    try:
        with open(filepath, 'r') as inputFile:
            for line in inputFile:
                instruction = line.split()
                if (instruction[0].upper() == "GOPRO"):
                    recordingTime = int(instruction[1])
                    Experiment.goPro(recordingTime)

                elif (instruction[0].upper() == "LED"):
                    power = (instruction[1].upper() == "TRUE")
                    Experiment.led(power)

                elif (instruction[0].upper() == "STEPPER"):
                    delay = int(instruction[1])
                    qturn = int(instruction[2])
                    Experiment.stepper(delay, qturn)

                elif (instruction[0].upper() == "SOLENOID"):
                    solPins = list()
                    duration = float(instruction[1])
                    for i in range(2, len(instruction), 2):
                        solPins.append(tuple((float(instruction[i]), int(instruction[i+1]))))
                    Experiment.solenoid(solPins)

    # Output to the logger here.
    except IOError as e:
        qpaceLogger.logError("Could not open experiment file at " + str(filepath) + ".", e)
        qpaceLogger.logSystem([["File I/O error occured."]])
    else:
        isRunningEvent.clear()
