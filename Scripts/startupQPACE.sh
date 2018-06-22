#!/usr/bin/env sh
#
#
# Startup shell script to envoke python modules

cd /home/pi/scripts
python3 startup.py
python3 qpaceWTCHandler.py
cd /home/pi