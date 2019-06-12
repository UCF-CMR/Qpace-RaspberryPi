#!/usr/bin/env sh
# startupQPACE.sh by Jonathan Kessluk
# 9-30-2018, Rev. 1b
# Q-Pace project, Center for Microgravity Research
# University of Central Florida
#
# Startup shell script to envoke python modules

cd /home/pi/Scripts
#python3 qpaceMain.py
python3 terminalFlood.py
python3 setON.py
cd /home/pi
