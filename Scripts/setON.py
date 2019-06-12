import os
import pigpio
from subprocess import check_output

SCRIPT = "terminalFlood.py"
GPIO21 = 21 # GPIO 21 is Pin 29
pi = pigpio.pi()

while True:
    #curProcesses = os.system("ps -fA | grep python")
    if SCRIPT in str(check_output("ps -fA | grep python", shell=True)):
        pi.write(GPIO21, 1) # If the script is running set the GPIO 21 to high
    else:
        pi.write(GPIO21, 0)
