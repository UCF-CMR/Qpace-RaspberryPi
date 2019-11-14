from qpacePiCommands import *
from qpaceLogger import *

logger = Logger()

cmd = Command()


def task_HealthCheck():
    print("RUN HEALTHCHECK")
    try:
        cmd.status(logger, None, silent=True)
    except Exception as e:
        print(e)
    print("DONE")
    
    
