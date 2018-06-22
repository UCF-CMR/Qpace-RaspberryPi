from enum import Enum


SSCOMMAND = {
	"PIALIVE":        0x41, # WTC Is the Pi alive?
	"TIMESTAMP":      0x42, # WTC Send the timestamp
	"CONFIGURATION":  0x43, # WTC Send the configuration packet
	"WHATISNEXT":     0x4A, # WTC Where do we go from here?
	"SCIENCEMODE":    0x44, # PI  Start science mode
	"SCIENCESTART":   0x4C, # WTC Start doing science
	"SCIENCESTOPREQ": 0x4D, # WTC Request stop doing science
	"SCIENCEWAIT":    0x4E, # PI  Not stopping, need to finish
	"SCIENCESTOP":    0x4F, # WTC No more waiting, stop now
	"DUMPDATAMODE":   0x45, # PI  Start datadump mode
	"DUMPDATA":       0x48, # WTC Send me the data
	"VALIDATE":       0x47, # WTC Validate my data
	"DUMPDONE":       0x4B, # PI  Data dump completed
	"SHUTDOWN":       0x46, # WTC Shutdown now!

	"SENDBACK":       0x60, # WTC Send data back
	"CHUNK1":         0x61, # WTC Sending chunk 1
	"CHUNK2":         0x62, # WTC Sending chunk 2
	"CHUNK3":         0x63, # WTC Sending chunk 3
	"CHUNK4":         0x64, # WTC Sending chunk 4

	"CHECKSUMGOOD":   0x70,
	"CHECKSUMBAD":    0x71,
	"SDTIMEOUT":      0x72
}

SSERRORS = {
	"ERRNONE":     0x00,
	"ERRTIMEOUT":  0x01,
	"ERRMISMATCH": 0x02,
	"ERRWRONGPI":  0x03
}

class SSState(Enum):
	Initialize    = 0
	PiAlive       = 1
	Timestamp     = 2
	Configuration = 3
	Science       = 4
	DumpData      = 5
	Shutdown      = 6

class SSTimeState(Enum):
	Initialize    = 0
	SetTimestamp  = 1
	Finalize      = 2

class SSConfigState(Enum):
	Initialize      = 0
	ReceiveChunks   = 1
	ValidatePacket  = 2
	Finalize        = 3

class SSDumpState(Enum):
	SendPacket      = 1
	ValidatePacket  = 2
	Finalize        = 3