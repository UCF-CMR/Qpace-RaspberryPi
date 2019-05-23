#!/usr/bin/env python3
# qpaceControl.py by Jonathan Kessluk
# 9-2-2018, Rev. 2
# Q-Pace project, Center for Microgravity Research
# University of Central Florida
#
# This file only contains a dictionary with the control characters between the WTC and Pi.

QPCONTROL = {
	"NOOP":			  0x0F, # No-operation. Has no use. More like a "ping" than anything else
	"DEBUG":		  0x23,

	"STEPON":		  0x83, # Pi request for the Steppers to be turned on
	"STEPOFF":		  0x84, # Pi request for the Steppers to be turned off
	"SOLON":		  0x81, # Pi request for the Solenoids to be turned on
	"SOLOFF":		  0x82,	# Pi request for the Solenoids to be turned off

	"ACCEPTED":		  0x8A, # Acts as a "TRUE" flag from the WTC to indicate that the Pi may do something
	"DENIED":		  0x8B, # Acts as a "FALSE" flag from the WTC to indicate that the Pi may not do something
	"PENDING":		  0x8C, # Acts as a flag that is neither TRUE nor FALSE from the WTC to indicate that the Pi must wait for a response.
	"DONE":			  0xAA, # used as an end-of-transmission iff nothing should be sent back anyway

	"SENDPACKET":	  0x20,	# Implies the pi would like to send data.
	"NEXTPACKET":	  0x21,	# Sent by WTC. Asks for next packet.
	"BUFFERFULL":	  0x22,	# Sent by WTC. Implies the buffer is full. (Rev2 Pi ignores this message)
	"WHATISNEXT":     0x4A, # WTC request to Pi to see if the Pi wants to do anything.
	"CANTSEND":       0x23, # WTC is not within transmittion range

	"TIMESTAMP":      0x42, # WTC request to set the timestamp of the Pi
	"SHUTDOWN":       0x46, # WTC request to shutdown now! If sent from Pi, implies the Pi would like to shutdown.
	"REBOOT":		  0x49, # WTC request to reboot now. If sent from Pi, implies the Pi would like to reboot.
	"IDLE":			  0x48, # WTC may send the Pi packets. The pi has no intentions. Could be running an experiment during IDLE.

	"CHUNK1":         0x61, # Response for the WTC Sending chunk 1
	"CHUNK2":         0x62, # Response for the WTC Sending chunk 2
	"CHUNK3":         0x63, # Response for the WTC Sending chunk 3
	"CHUNK4":         0x64  # Response for the WTC Sending chunk 4

}