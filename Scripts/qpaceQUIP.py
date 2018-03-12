#! /usr/bin/env python3
# qpaceLogger.py by Jonathan Kessluk
# 2-20-2018, Rev. 1.2
# Q-Pace project, Center for Microgravity Research
# University of Central Florida

import argparse
import sys
import os
from math import ceil,log

class Packet():
    sync = 0xFFFF           # 2 bytes
    start = 0xABCD          # 2 bytes
    end = 0xDCBA            # 2 bytes
    id_bits = 32            # 4 bytes
    overflow = 0            # 0 for false. (1 bit)
    placeholder_bits = 4    # in bits
    op_code = 0x0           # 3 bits

    max_size = 256          # in bytes
    data_size = 81          # in bytes
    max_id = 0xFFFFFFFF     # in hex
    packet_data_size = None # packet_data_size in bytes
    last_id = -1            # -1 if there are no packets.

    def __init__(self,data, pid):
        """
        Constructor for a packet.

        Parameters
        ---------
        data - int, str, bytes, bytearray - If a str it must be hex and valid bytes.
        pid - int - Integer to be the PID of the packet. Can not be negative and must be
                    +1 the last pid used.

        Exceptions
        ----------
        ValueError - if the data passed to the packet is too large to fit in the packet.
                     or the pid is out of order.
                     or the pid is negative.
                     or input data is not a string of hex

        """
        if pid < 0:
            raise ValueError("Packet pid is invalid. Must be a positive number.")
        if isinstance(data,int):
            data = bytearray(data.to_bytes(data.bit_length//8+1),byteorder='little')
        elif isinstance(data,bytearray):
            pass
        elif isinstance(data,bytes):
            data = bytearray(data)
        elif isinstance(data,str):
            data = bytearray.fromhex(data)
        else:
            TypeError("Input data is of incorrect type. Must input str, int, bytes, or bytearray")

        data_in_bytes = len(data)
        if data_in_bytes <= Packet.data_size:
            if Packet.last_id is None or (Packet.last_id + 1) == pid:
                Packet.last_id = pid
                self.pid = pid % Packet.max_id # If the pid is > max_id, force it to be smaller!
            else:
                raise ValueError("Packet pid out of order.")
            if pid > Packet.max_id:
                # Set the overflow to 0 for even multiples of pid and 1 for odd.
                Packet.overflow = (Packet.max_id / pid) % 2
            self.data = data
            self.bytes = data_in_bytes
        else:
            raise ValueError("Packet size is too large for the current header information. Data input restricted to " + str(Packet.data_size) + " Bytes.")

    def buildHeader(self):
        """
            Build the header for the packet.

            Returns
            -------
            bytearray - packet header data.
        """
        sync = bytearray(Packet.sync.to_bytes(2,byteorder='little'))  # 2 bytes
        start = bytearray(Packet.start.to_bytes(2,byteorder='little'))# 2 bytes
        pid = bytearray(self.pid.to_bytes(4,byteorder='little'))    # 4 bytes
        header_end = bytearray(((Packet.overflow << 7) | (Packet.op_code << 4)).to_bytes(1,byteorder='little'))
        return sync + start + pid + header_end

    def buildData(self):
        """
            Build the data for the packet. All data is repeated 3 times for FEC.

            Returns
            -------
            bytearray - packet data that is triple redundant and interlaced by size of the data
        """
        # Do a TMR expansion where the data is replicated 3 times but not next to each other
        # to avoid burst errors.
        return self.data*3

    def buildFooter(self):
        """
            Build the footer for the packet.

            Returns
            -------
            bytearray - packet footer data.
        """
        sync = bytearray(Packet.sync.to_bytes(2,byteorder='little'))  # 2 bytes
        end = bytearray(Packet.end.to_bytes(2,byteorder='little'))# 2 bytes
        return sync + end

    def build(self):
        """
            Build the entire packet.

            Returns
            -------
            int - the whole packet. if converted to binary/hex it will be the packet.
        """
        header = self.buildHeader()
        data = self.buildData()
        footer = self.buildFooter()
        packet = header + data + footer
        return packet


class Encoder():
    def __init__(self,path_for_encode,path_for_packets, suppress=False,destructive=False):
        """
        Constructor for the Encoder.

        Parameters
        ----------
        path_for_encode - str - The path with a filename on it to encode the file.
        path_for_packets - str - where to store the packets.
        suppress - bool - suppress output to the terminal.
        destructive - bool - delete the file when done with it.
        """
        self.file = path_for_encode
        self.packets = path_for_packets
        self.suppress = suppress
        self.destructive = destructive

    def run(self):
        """
        Main method to run for the encoder. This will encode a file into packets.
        """
        try:
            #file_size = os.path.getsize(self.file) # in bytes
            if not self.suppress: print("Beginning to encode file into packets.")
            with open(self.file,'rb') as fileToEncode:
                pid = -1
                try:
                    while True:
                        pid = pid + 1
                        data = fileToEncode.read(Packet.data_size)
                        if not data: break
                        with open(self.packets+str(pid)+".qp", 'wb') as packet:
                            packet.write(Packet(data,pid).build())
                except IOError:
                    print("Could not write to the directory: ", self.packets)
                    print("Could not write packet: ", pid)
                else:
                    if not self.suppress: print("Successfully built ", pid, " packets.")
                    if self.destructive: os.remove(fileToEncode.name)
        except FileNotFoundError:
            print("Can not find file: ", self.file)
        except IOError:
            print("There was a problem encoding: ",self.file)
        else:
            if not self.suppress: print("Successfully encoded file into packets.")

class Decoder():
    def __init__(self, path_for_decode, path_for_packets, suppress=False,destructive=False):
        """
        Constructor for the Encoder.

        Parameters
        ----------
        path_for_encode - str - The path with a filename on it to decode to.
        path_for_packets - str - where the packets are stored.
        suppress - bool - suppress output to terminal
        destructive - bool - delete the packets when done with them.
        """
        self.file = path_for_decode
        self.packets = path_for_packets
        self.suppress = suppress
        self.destructive = destructive

    def run(self):
        """
        Main method to run for the decoder. Takes packets and decodes them into a file.
        """
        try:
            if not self.suppress: print("Beginning to decode packets into a file.")
            if os.path.exists(self.file): raise FileExistsError
            with open(self.file, 'ab') as fileToBuild:
                pid = -1
                try:
                    while True:
                        pid = pid +1
                        with open(self.packets+str(pid)+".qp",'rb') as packet:
                            packet_data = packet.read()
                            header = packet_data[:9]
                            information = packet_data[9:len(packet_data)-4]
                            footer = packet_data[len(packet_data)-4:]
                            fileToBuild.write(information)
                            if self.destructive: os.remove(packet.name)
                except FileNotFoundError as e:
                    if not self.suppress: print("Completed read of packets. Packets read: ", pid)
                except IOError:
                    print("Could not open packet for reading: packet ", pid)
                else:
                    if not self.suppress: print("Successfully built ", pid, " packets.")
        except FileExistsError:
            print("The file already exists. Please choose a file that does not yet exist (" + self.file +")")
        except IOError:
            print("Could not open file for writing: ", self.file)
        else:
            if not self.suppress: print("Successfully decoded packets into a file.")

# Code to be run after importing everything.
# -------------------------------------------

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Interat with QUIP and encode/decode packets.')
    parser.add_argument('--version',action='version', version = 'Version: 1.2')
    mutex_group = parser.add_mutually_exclusive_group(required=True)

    parser.add_argument('-s','--suppress',
                        help="hide the terminal outputs.",
                        default=False,
                        action='store_true')
    parser.add_argument('--destructive',
                        help="delete the file or packets when the script is done with them",
                        default=False,
                        action='store_true')
    mutex_group.add_argument('-e','--encode',
                        help="set to encode.",
                        default=False,
                        action='store_true')
    mutex_group.add_argument('-d','--decode',
                        help="set to decode.",
                        default=False,
                        action='store_true')
    parser.add_argument('-p','--packets',
                        dest="packet_location",
                        help="set the path of packets.",
                        type=str,
                        required=True)
    parser.add_argument('-f','--file',
                        dest='file_location',
                        help="set the path of the file.",
                        type=str,
                        required=True)

    args = parser.parse_args()

    if args.encode:
        en = Encoder(args.file_location,args.packet_location,suppress=args.suppress,destructive=args.destructive)
        en.run()
    else:
        de = Decoder(args.file_location,args.packet_location,suppress=args.suppress,destructive=args.destructive)
        de.run()







