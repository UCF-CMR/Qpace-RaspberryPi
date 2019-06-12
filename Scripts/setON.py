import os
import pigpio

SCRIPT = "terminalFlood.py"
GPIO21 = 29 # GPIO 21 is Pin 29
pi = pigpio.pi()

while True:
    curProcesses = os.system("ps -fA | grep python")
    if SCRIPT in curProcesses:
        pi.write(GPIO21, 1) # If the script is running set the GPIO 21 to high
    else:
        pi.write(GPIO21, 0)