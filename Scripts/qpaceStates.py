#!/usr/bin/env python3
# qpaceStates.py by Jonathan Kessluk
# 9-2-2018, Rev. 2
# Q-Pace project, Center for Microgravity Research
# University of Central Florida
#
# The location of the list of different WTC states. This was derived from SurfSat. It has since
# been changed slightly.

QPCOMMAND = {
	"True":			  0x00,
	"False":		  0x02,
	"NOOP":			  0x0F,
	"STEPON":		  0x10,
	"STEPOFF":		  0x11,
	"SOLON":		  0x12,
	"SOLOFF":		  0x13,
	"ALLON":		  0x14,
	"ALLOFF":		  0x15,

	"PIALIVE":        0x41, # WTC Is the Pi alive?
	"TIMESTAMP":      0x42, # WTC Send the timestamp
	"CONFIGURATION":  0x43, # WTC Send the configuration packet
	"WHATISNEXT":     0x4A, # WTC Where do we go from here?
	# "SCIENCEMODE":    0x44, # PI  Start science mode
	# "SCIENCESTART":   0x4C, # WTC Start doing science
	# "SCIENCESTOPREQ": 0x4D, # WTC Request stop doing science
	# "SCIENCEWAIT":    0x4E, # PI  Not stopping, need to finish
	# "SCIENCESTOP":    0x4F, # WTC No more waiting, stop now
	# "DUMPDATAMODE":   0x45, # PI  Start datadump mode
	# "DUMPDATA":       0x48, # WTC Send me the data
	# "VALIDATE":       0x47, # WTC Validate my data
	# "DUMPDONE":       0x4B, # PI  Data dump completed
	"SHUTDOWN":       0x46, # WTC Shutdown now!

	#Specific QPACE States. Some of these may be the same as above states.
	"IDLE":			  0x48, # WTC may send the Pi packets. The pi has no intentions. Could be running an experiment.
	"REBOOT":		  0x49, # Informing the WTC that the Pi is about to reboot.

	# "SENDBACK":       0x60, # WTC Send data back
	"CHUNK1":         0x61, # WTC Sending chunk 1
	"CHUNK2":         0x62, # WTC Sending chunk 2
	"CHUNK3":         0x63, # WTC Sending chunk 3
	"CHUNK4":         0x64, # WTC Sending chunk 4

	"CHECKSUMGOOD":   0x70,
	"CHECKSUMBAD":    0x71,
	"SDTIMEOUT":      0x72,

	"ERRNONE":    	  0x00,
	"ERRTIMEOUT": 	  0x01,
	"ERRMISMATCH":	  0x02,
	"ERRWRONGPI": 	  0x03
}