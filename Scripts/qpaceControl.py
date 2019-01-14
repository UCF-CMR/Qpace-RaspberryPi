#!/usr/bin/env python3
# qpaceControl.py by Jonathan Kessluk
# 9-2-2018, Rev. 2
# Q-Pace project, Center for Microgravity Research
# University of Central Florida
#
# The location of the list of different WTC states. This was derived from SurfSat. It has since
# been changed slightly.

QPCONTROL = {
	"NOOP":			  0x0F,

	"STEPON":		  0x83,
	"STEPOFF":		  0x84,
	"SOLON":		  0x81,
	"SOLOFF":		  0x82,

	"ACCEPTED":		  0x8A,
	"DENIED":		  0x8B,
	"PENDING":		  0x8C,
	"DONE":			  0xAA, #used for end-of-transmission iff nothing should be sent back anyway

	"SENDPACKET":	  0x20,	# Added to queue. Implies the pi would like to send data.
	"NEXTPACKET":	  0x21,	# Sent by WTC. Asks for next packet.
	"BUFFERFULL":	  0x22,	# Sent by WTC. Implies the buffer is full.
	"TIMESTAMP":      0x42, # WTC Send the timestamp
	"WHATISNEXT":     0x4A, # WTC Where do we go from here?


	#Specific QPACE States. Some of these may be the same as above states.
	"SHUTDOWN":       0x46, # WTC Shutdown now!
	"IDLE":			  0x48, # WTC may send the Pi packets. The pi has no intentions. Could be running an experiment.
	"REBOOT":		  0x49, # Informing the WTC that the Pi is about to reboot.

	# "SENDBACK":       0x60, # WTC Send data back
	"CHUNK1":         0x61, # WTC Sending chunk 1
	"CHUNK2":         0x62, # WTC Sending chunk 2
	"CHUNK3":         0x63, # WTC Sending chunk 3
	"CHUNK4":         0x64  # WTC Sending chunk 4

}