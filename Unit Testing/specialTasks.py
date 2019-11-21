from qpacePiCommands import *
from qpaceLogger import *
from qpaceMain import Queue, initWTCConnection
import qpaceControl as qpc
from qpaceInterpreter import *
import os
import threading

logger = Logger()

cmd = Command()

cmd.experimentEvent = threading.Event()
cmd.disableCallback = threading.Event()
cmd.nextQueue = Queue(logger)

chip = initWTCConnection()


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
        cmd.startExperiment(logger, 'UT.ep'.encode('ascii'),cmd.nextQueue, silent=True)
        
        while experimentEvent.is_set():
            next = cmd.nextQueue.peek()
            if next == qpc['SOLON'] or next == qpc['STEPON']:
                wtc_respond(next)
                if waitForBytesFromCCDR(chip,1,timeout=WHATISNEXT_WAIT): # Wait for 15s for a response from the WTC
                    response = chip.byte_read(SC16IS750.REG_RHR)
                    # THIS IS A BLOCKING CALL
                    cmd.nextQueue.blockWithResponse(response,timeout=1) # Blocking until the response is read or timeout.
        
    except Exception as e:
        print(e)
    
