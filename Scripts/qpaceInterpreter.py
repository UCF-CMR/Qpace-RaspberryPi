#! /usr/bin/env python3
# qpaceQUIP.py by Jonathan Kessluk
# 2-20-2018, Rev. 1
# Q-Pace project, Center for Microgravity Research
# University of Central Florida
#
# Credit to the SurfSat team for CCDR driver and usage.
#
# The interpreter will be invoked when pin 7 goes high. This will grab QUIP packets and direct them to the packet directory, then decode them.

import time
import SC16IS750
import RPi.GPIO as gpio

INTERP_PACKETS_PATH = "packets/" #TODO determine actual path

# I2C bus identifier
I2C_BUS = 1

# Interrupt GPIO pins for WTC and PLP comm chips
PIN_IRQ_WTC = 25 # BCM pin 25, header pin 22

# I2C addresses for WTC and PLP comm chips
I2C_ADDR_WTC = 0x4C

# UART baudrates for WTC and PLP comm chips
I2C_BAUD_WTC = 115200

# Crystal frequency for comm chips
XTAL_FREQ = 1843200


chip = SC16IS750.SC16IS750(I2C_ADDR_WTC, I2C_BUS, I2C_BAUD_WTC, XTAL_FREQ)

# Reset chip and handle exception thrown by NACK
try: chip.byte_write_verify(SC16IS750.REG_IOCONTROL, 0x01 << 3)
except OSError: print("REG_IOCONTROL: %s 0x00" % (chip.byte_read(SC16IS750.REG_IOCONTROL) == 0x00))

# Define UART with 8 databits, 1 stopbit, and no parity
chip.write_LCR(SC16IS750.DATABITS_8, SC16IS750.STOPBITS_1, SC16IS750.PARITY_NONE)

# Toggle divisor latch bit in LCR register and set appropriate DLH and DLL register values
chip.define_register_set(special = True)
chip.set_divisor_latch()
chip.define_register_set(special = False)
#print("REG_LCR:       %s 0x%02X" % chip.define_register_set(special = True))
#print("REG_DLH/DLL:   %s 0x%04X" % chip.set_divisor_latch())
#print("REG_LCR:       %s 0x%02X" % chip.define_register_set(special = False))

# Enable RHR register interrupt
chip.byte_write(SC16IS750.REG_IER, 0x01)

# Reset TX and RX FIFOs and disable FIFOs
chip.byte_write(SC16IS750.REG_FCR, 0x06)
time.sleep(2.0/XTAL_FREQ)

# Initialize the pins
gpio.set_mode(gpio.BCM)
gpio.setup(PIN_IRQ_WTC, gpio.IN)

# Enable FIFOs
chip.byte_write(SC16IS750.REG_FCR, 0x01)
time.sleep(2.0/XTAL_FREQ)

print("Waiting for data. Hit Ctrl+C to abort.")
buf = b''
while True:
    try:
        if not gpio.input(PIN_IRQ_WTC):
            break

        time.sleep(1)
        waiting = chip.byte_read(SC16IS750.REG_RXLVL)
        if waiting > 0:
            for i in range(waiting):
                buf += chip.byte_read(SC16IS750.REG_RHR)
                #print(" 0x%02X" % char)
    except KeyboardInterrupt: # If we get a SIGINT, we can also break off.
        break

gpio.cleanup() #TODO do we actually want to cleanup?

#TODO do we need to determine the opcode or can we force the packets to be sent in order?
#TODO we will need to determine the opcode iff we use control packets.

def isolateOpCode():
    pass

if len(buf) > 0:
    # write the initial init packet
    with open(INTERP_PACKETS_PATH+"init.qp",'wb') as f:
        f.write(buf[:256])
    buf = buf[256:]

    counter = 0
    while len(buf) > 0:
        with open(INTERP_PACKETS_PATH+str(counter) + ".qp",'wb') as f: # we can just name them with the counter iff we don't determine the opcodes
            f.write(buf[:256])
        buf = buf[256:]
        counter += 1


