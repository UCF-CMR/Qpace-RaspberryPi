#!/usr/bin/env python3
# qpacePiCommands.py by Jonathan Kessluk
# 4-24-2018, Rev. 1
# Q-Pace project, Center for Microgravity Research
# University of Central Florida
#
# This module handles the individual commands for the Pi
import os

import time
from subprocess import check_output,Popen
from math import ceil
from time import strftime,gmtime
import socket
import qpaceInterpreter
import qpaceLogger as logger
import qpaceQUIP as quip

CMD_DEFAULT_TIMEOUT = 5 #seconds
CMD_POLL_DELAY = .5 #seconds
STATUSPATH = ''
WHO_FILEPATH = ''
SOCKET_PORT = 8675 #Jenny, who can I turn to?
ETHERNET_BUFFER = 2048
def _waitForWTCResponse(chip, trigger = None, timeout = None):
    """
    Wait for the WTC to respond with a continue code and then return.

    Parameters
    ----------
    chip - SC16IS750 - an SC16IS750 object which handles the WTC Connection
    trigger - bytes - waits until it receives a specific byte sequence from the WTC. If None
                      is given, then it will read and return from the WTC, otherwise it will return None.
    timeout - int - number of seconds to wait for a response from the WTC. If None, then the default timeout
                    will be used.

    Returns
    -------
    bytes - The bytes read from the registers on the WTC if the trigger is None.
    True - If a trigger is given and it matched
    False - If the trigger never matched the input and the timeout occurred

    Raises
    ------
    TypeError - If the trigger is not bytes or string OR the timeout is not an int.
    """
    if isinstance(trigger,str):
        trigger = trigger.encode('utf-8')
    elif not isinstance(timeout,int) and not isinstance(timeout,float) and not isinstance(trigger,bytes) and not isinstance(trigger,bytearray):
        raise TypeError("Trigger must be bytes or string.")
    logText = "Waiting for {} seconds for the WTC to respond".format(timeout or CMD_DEFAULT_TIMEOUT)
    if trigger:
        logText += " with '{}'".format(trigger)
    logger.logSystem([[logText]])

    attempts_remaining = ceil((timeout or CMD_DEFAULT_TIMEOUT)/CMD_POLL_DELAY)
    if attempts_remaining < 1:
        attempts_remaining = 1

    buf = b''
    while attempts_remaining > 0 and buf != trigger:
        time.sleep(CMD_POLL_DELAY)
        attempts_remaining -= 1
        waiting = chip.byte_read(SC16IS750.REG_RXLVL)
        if waiting > 0 :
            for i in range(waiting):
                buf += chip.byte_read(SC16IS750.REG_RHR)
    if buf == trigger:
        return True
    elif trigger is None and buf is not b'':
        return buf
    else:
        return False
def _sendBytesToWTC(chip,sendData):
    """
    Send a string or bytes to the WTC. This method, by default, is dumb. It will pass whatever
    is the input and passes it directly on to the WTC.

    Parameters
    ----------
    chip - SC16IS750 - an SC16IS750 object which handles the WTC Connection
    sendData - a string or bytes that we want to send to the WTC

    Raises
    ------
    TypeError - thrown if sendData is not a string or bytes
    """
    if isinstance(sendData,str):
        sendData = sendData.encode('utf-8')
    elif not isinstance(sendData,bytes) and not isinstance(sendData,bytearray):
        logger.logSystem([['Data will not be sent to the WTC: not string or bytes.']])
        raise TypeError("Data to the WTC must be in the form of bytes or string")
    try:
        logger.logSystem([['Sending to the WTC:', str(sendData)]])
        for byte in sendData:
            chip.byte_write(SC16IS750.REG_THR, byte)
    except Exception as err:
        #TODO do we actually handle the case where it just doesn't work?
        logger.logError('SendBytesToWTC: An error has occured when attempting to send data to the WTC. Data to send:' + str(sendData) + 'The data will not be send',err)
        pass

def immediateShutdown(chip,cmd,args):
    """
    Initiate the shutdown proceedure on the pi and then shut it down. Will send a status to the WTC
    The moment before it actually shuts down.

    Parameters
    ----------
    chip - SC16IS750 - an SC16IS750 object which handles the WTC Connection
    cmd,args - string, array of args (seperated by ' ') - the actual command, the args for the command
    """
    logger.logSystem([['Shutting down...']])
    _sendBytesToWTC(chip,b'SP') # SP = Shutdown Proceeding
    Popen(["sudo", "halt"],shell=True) #os.system('sudo halt')
    raise SystemExit # Close the interpreter and clean up the buffers before reboot happens.


def immediateReboot(chip,cmd,args):
    """
    Initiate the reboot proceedure on the pi and then reboot it. Will send a status to the WTC
    the moment before it actually reboots.

    Parameters
    ----------
    chip - SC16IS750 - an SC16IS75 object which handles the WTC Connection
    cmd,args - string, array of args (seperated by ' ') - the actual command, the args for the command
    """
    logger.logSystem([['Rebooting...']])
    _sendBytesToWTC(chip,b'SP') # SP = Shutdown Proceeding
    Popen(["sudo", "reboot"],shell=True) #os.system('sudo reboot')
    raise SystemExit # Close the interpreter and clean up the buffers before reboot happens.

def sendFile(chip,cmd,args):
    """
    Encode a file with the QUIP protocol and then send the raw data to the WTC to send to ground.

    Parameters
    ----------
    chip - SC16IS750 - an SC16IS750 object which handles the WTC Connection
    cmd,args - string, array of args (seperated by ' ') - the actual command, the args for the command
    """
    #TODO this is not complete.
    from qpaceInterpreter import INTERP_PACKETS_PATH

    logger.logSystem([['Running the QUIP Encoder...']+args])
    success = quip.Encoder(args[0],INTERP_PACKETS_PATH,suppress=False).run()
    if success:
        logger.logSystem([['The encoding was successful. Beginning the transfer sequences.']])
        try:
            for filepath in os.listdir(INTERP_PACKETS_PATH):
                try:
                    with open(INTERP_PACKETS_PATH+filepath,'rb') as f:
                        data = f.read()
                        if len(data) is 256:
                            #TODO Figure out a protocol if we can't just bulk send 256 bytes.
                            _sendBytesToWTC(chip,data)
                except OSError as err:
                    logger.logError('Could not read packet for sending: ' + filepath, err)
        except OSError:
            logger.logError('Could not read directory for sending packets.')
    else:
        logger.logSystem([['There was a problem fully encoding the file.']])


def asynchronousSendPackets(chip,cmd,args):
    """
    Aggregate and then pass along individual, specific packets to the WTC to send to ground.

    Parameters
    ----------
    chip - SC16IS750 - an SC16IS750 object which handles the WTC Connection
    cmd,args - string, array of args (seperated by ' ') - the actual command, the args for the command
    """
    #TODO this may not be complete.
    from simInterpreter import INTERP_PACKETS_PATH
    if args and isinstance(args[0],bytes):
        args = [entry.decode('utf-8') for entry in args]
    for pak in args:
        try:
            with open(INTERP_PACKETS_PATH+pak+'.qp','rb') as f:
                data = f.read()
                if len(data) is 256:
                    #TODO Figure out a protocol if we can't just bulk send 256 bytes.
                    _sendBytesToWTC(chip,data)
        except OSError as err:
            logger.logError('Could not read packet for sending.', err)


def pingPi(chip,cmd,args):
    """
    A ping was received from the WTC. Respond back!

    Parameters
    ----------
    chip - SC16IS750 - an SC16IS750 object which handles the WTC Connection
    cmd,args - string, array of args (seperated by ' ') - the actual command, the args for the command
    """
    logger.logSystem([["Pong!"]])
    _sendBytesToWTC(chip,b'OK')

def returnStatus(chip,cmd,args):
    """
    Create a text file with status items and then send that file.
    Invokes sendFile

    Accumulates the following data: CPU Usage, CPU Temp, IP Address, Pi Identity,
                                    Last command received, Uptime, Running processes,
                                    RAM Usage, Disk Space used, Disk space total,
                                    Connected COM ports.
    Parameters
    ----------
    chip - SC16IS750 - an SC16IS750 object which handles the WTC Connection
    cmd,args - string, array of args (seperated by ' ') - the actual command, the args for the command
    """
    from simInterpreter import LastCommand
    logger.logSystem([["Attempting to get the status of the Pi"]])
    identity = 0
    cpu = 'Unknown'
    cpu_temp = 'Unknown'
    uptime = 'Unknown'
    ram_tot = 'Unknown'
    ram_used = 'Unknown'
    ram_free = 'Unknown'
    disk_free = 'Unknown'
    disk_total = 'Unknown'
    last_command = LastCommand.type
    last_command_when = LastCommand.timestamp
    last_command_from = LastCommand.fromWhom
    try:
        cpu = str(round(100 - float(check_output("top -b -n 2 |grep Cpu|tail -1|awk -v N=8 '{print $N}'", shell=True)),3))
        cpu_temp = str(int(os.popen('cat /sys/class/thermal/thermal_zone0/temp').read()[:-1])/1000)
    except Exception as err:
        logger.logError("There was a problem accessing the CPU stats", err)
    try:
        ip = (([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")] or [[(s.connect(("8.8.8.8", 53)), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) + ["no IP found"])[0]
    except Exception as err:
        logger.logError("There was a problem accessing the IP address", err)
    try:
        uptime =  os.popen("uptime | awk -v N=3 '{print $N}'").read()[:-2]
    except Exception as err:
        logger.logError("There was a problem accessing the uptime", err)
    try:
        mem=str(os.popen('free -b').readlines())
        mem=[num for num in mem.split('\n')[1].split(' ') if num]
        ram_tot = mem[1]
        ram_used = mem[2]
        ram_free = mem[3]
    except Exception as err:
        logger.logError("There was a problem accessing the RAM stats", err)
    try:
        statvfs = os.statvfs('/')
        disk_used = statvfs.f_frsize * statvfs.f_blocks     # Size of filesystem in bytes
        disk_free = statvfs.f_frsize * statvfs.f_bfree      # Actual number of free bytes
    except Exception as err:
        logger.logError("There was a problem accessing the Disk stats", err)
    try:
        # Read in only the first character from the WHO file to get the current identity.
        with open(WHO_FILEPATH,'r') as f:
            identity = f.read(1)
        chip = initWTCConnection()
    except Exception as err:
        logger.logError("There was a problem determining the Pi's identity", err)

    text_to_write = "Identity: Pi {}\n"     +\
                    "Last Command Executed was \"{}\" at {} invoked by \"{}\"\n" +\
                    "CPU Usage: {}%\n"      +\
                    "CPU Temp: {}C\n"       +\
                    "Uptime: {} (hh:mm)\n"  +\
                    "RAM Total: {} bytes\n" +\
                    "RAM Used: {} bytes\n"  +\
                    "RAM Free: {} bytes\n"  +\
                    "Disk total: {}\n"      +\
                    "Disk free: {}\n"
    text_to_write = text_to_write.format(identity,last_command,last_command_when,last_command_from,cpu,cpu_temp,
                            uptime,ram_tot,ram_used,ram_free,disk_total,disk_free)
    logger.logSystem([["Status finished."] + text_to_write.split('\n')])
    timestamp = strftime("%Y%m%d-%H%M%S",gmtime())
    try:
        with open(STATUSPATH+'status_'+timestamp+'.txt','w') as statFile:
            statFile.write(text_to_write)
    except Exception as err:
        logger.logError("There was a problem writing the status file.",err)
        try:
            with open(STATUSPATH+'status_'+timestamp+'.txt','w') as statFile:
                statFile.write("Unable to write status file.")
        except:pass


def _getEthernetConnection():
    """
    This method establishes the ethernet connection for methods that use it.

    Parameters
    ----------
    Nothing.

    Returns
    -------
    The socket connection.

    Raises
    ------
    ConnectionError - if it cannot make a connection for some reason.
    """
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    logger.logSystem([['Attempting to connect to the other Pi via Ethernet.']])
    try:
        with open(WHO_FILEPATH,'r') as f:
            identity = f.read(1)
        if identity == 1:
            host = "192.168.1.2"
        elif identity == 2:
            host = "192.168.1.1"
        else:
            err = ConnectionError("Could not connect to Sibling. Bad Identity: " + identity)
            logger.logError('EthernetConnection: Bad Identity', err)
            raise err
        client.connect((host,SOCKET_PORT))
        logger.logSystem([['EthernetConnection: Connection Established','Identity: Pi '+identity,'Host IP Address: '+host]])
    except (OSError,ConnectionError) as err:
        newErr = ConnectionError(str(err))
        logger.logError('EthernetConnection: There was a problem connecting via Ethernet', newErr)
        raise newErr from err
    client.settimeout(20)
    return client

def checkSiblingPi(chip,cmd,args): # TODO some kind of listener will have to be written for this and run as a seperate process on the pi.
    """
    Check the sibling pi via ethernet to see if it's alive.

    Parameters
    ----------
    chip - SC16IS750 - an SC16IS750 object which handles the WTC Connection
    cmd,args - string, array of args (seperated by ' ') - the actual command, the args for the command
    """
    try:
        connection = _getEthernetConnection()
        logger.logSystem([['Attempting to ping the other Pi.']])
        connection.send(b'Hello?') # See if the other guy is there by sending this.
        recvval = connection.recv(ETHERNET_BUFFER) # Will wait for response
        if recvval == b'Here!':
            logger.logSystem([['PiPong: Received message back from other pi. Everything Nominal.']])
            connection.close()
            _sendBytesToWTC(chip,b"OK")
    except TimeoutError:
        logger.logSystem([['EthernetConnection: Timeout has occured in qpacePiCommands.checkSiblingPi()']])
        _sendBytesToWTC(chip,b'NO')
    except ConnectionError as err:
        logger.logError('There was a connection Error in qpacePiCommands.checkSibilingPi()',err)
        _sendBytesToWTC(chip,b'NO')



def pipeCommandToSiblingPi(chip,cmd,args): # TODO some kind of listener will have to be written for this and run as a seperate process on the pi
    """
    Inform the sibling pi to run a command found in the "args"

    Parameters
    ----------
    chip - SC16IS750 - an SC16IS750 object which handles the WTC Connection
    cmd,args - string, array of args (seperated by ' ') - the actual command, the args for the command
    """
    try:
        connection = _getEthernetConnection()
        logger.logSystem([['Attempting to pipe a command to the the other Pi.']])
        connection.send(b'PIPE') # See if the other guy is there by sending this.
        recvval = connection.recv(ETHERNET_BUFFER) # Will wait for response
        if recvval == b'OK':
            logger.logSystem([['Handshake complete. Args:']+args])
            connection.send(' '.join(args).encode('utf-8'))
            ret = connection.recv(ETHERNET_BUFFER)
            if ret == b'working':
                logger.logSystem([['Command was received by the other pi and is attempting to be completed.']])
                _sendBytesToWTC(chip,b'OK')
            else:
                logger.logSystem([['Command has an issue for some reason and will not be run on the other pi.']])
                _sendBytesToWTC(chip,b'NO')
    except TimeoutError:
        logger.logSystem([['EthernetConnection: Timeout has occured in qpacePiCommands.checkSiblingPi()']])
        _sendBytesToWTC(chip,b'NO')
    except ConnectionError as err:
        logger.logError('There was a connection Error in qpacePiCommands.checkSibilingPi()',err)
        _sendBytesToWTC(chip,b'NO')
def performUARTCheck(chip,cmd,args):
    """
    Tell the pi to ping the WTC and wait for a response back. Similar to a "reverse" ping.

    Parameters
    ----------
    chip - SC16IS750 - an SC16IS750 object which handles the WTC Connection
    cmd,args - string, array of args (seperated by ' ') - the actual command, the args for the command
    """
    logger.logSystem([['Attempting to use UART...']])
    _sendBytesToWTC(chip, b'HI')
    _waitForWTCResponse(chip,trigger = 'OK') #Wait until timeout.