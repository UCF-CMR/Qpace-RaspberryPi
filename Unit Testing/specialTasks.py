from qpacePiCommands import *
from qpaceLogger import *
from qpaceMain import Queue
import os
import threading

logger = Logger()

cmd = Command()

cmd.experimentEvent = threading.Event()
cmd.disableCallback = threading.Event()
cmd.nextQueue = Queue(logger)


def task_HealthCheck():
    print("RUN HEALTHCHECK")
    try:
        cmd.status(logger, None, silent=True)
    except Exception as e:
        print(e)
    print("DONE")
    
    

def task_CreateExp():
    print("Create EXP")
    
    exp = """#UnitTest exp. Will turn on the LED bed, shake the solenoids, and record a video
START UnitTest
RESET
DELAY 300 # wait for 300 ms
LOG Setting the camera to 90 FPS at 640x480. Monochrome. Brightnexx 80%. Sharpness 75%
CAMERA SET fps:90 w:640 h:480 cfx:128,128 br:80 sh:75
    
LED ON
DELAY 10
CAMERA RECORD 120000
DELAY 120000
LED OFF
END
    """
    print(os.getcwd())
    try:
        with open('./data/exp/UT.ep', 'w') as f:
            f.write(exp)
        print("EXP is CREATED")
    except Exception as e:
        print(e)
    
def task_RunExp():
    try:
        cmd.startExperiment(logger, 'UT.ep'.encode('ascii'), silent=True)
    except Exception as e:
        print(e)
