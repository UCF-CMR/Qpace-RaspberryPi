import qpaceLogger as logger

def _sendResponseToWTC(response): # private method. Send something to the WTC
    pass

def immediateShutdown(args): # Shutdown the Pi
    pass

def immediateReboot(args): # Reboot the Pi
    pass

def sendFile(args): # Initiate sending files to WTC from the pi filesystem
    pass

def asynchronusSendPackets(args): # Send specific packets from the Pi to the WTC
    pass

def pingPi(args): # Ping the pi!
    pass

def returnStatus(args): # Accumulate status about the operation of the pi, assemble a txt file, and send it. (Invokes sendFile)
    pass

def checkSiblingPi(args): # Check to see if the sibling Pi is alive. Similar to ping but instead it's through ethernet
    pass

def pipeCommandToSiblingPi(args): # Take the args that are in the form of a command and pass it along to the sibling pi through ethernet
    pass

def performUARTCheck(args): # Tell the pi to perform a "reverse" ping to the WTC. Waits for a response from the WTC.
    pass