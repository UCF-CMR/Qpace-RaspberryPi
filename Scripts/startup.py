#!/usr/bin/env python3
# startup.py by Jonathan Kessluk
# 6-22-18, Rev 1
#
# This script ensures that the pins are initialized in the correct state on boot

try:
    import qpaceExperiment
    qpaceExperiment.pinInit()
except:
    raise

try:
    import time
    time.sleep(2) # Give 2 seconds for the other cron jobs to run their course.
    import qpaceWTCHandler
    qpaceWTCHandler.run()
except:
    raise