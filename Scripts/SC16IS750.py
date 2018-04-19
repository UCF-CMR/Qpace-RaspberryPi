import sys
import time
import smbus

# General Registers (Require LCR[7] = 0)
REG_RHR       = 0x00 # Receive Holding Register (R)
REG_THR       = 0x00 # Transmit Holding Register (W)
REG_IER       = 0x01 # Interrupt Enable Register (R/W)
REG_IIR       = 0x02 # Interrupt Identification Register (R)
REG_FCR       = 0x02 # FIFO Control Register (W)
REG_LCR       = 0x03 # Line Control Register (R/W)
REG_MCR       = 0x04 # Modem Control Register (R/W
REG_LSR       = 0x05 # Line Status Register (R)
REG_MSR       = 0x06 # Modem Status Register (R)
REG_SPR       = 0x07 # Scratchpad Register (R/W)
REG_TCR       = 0x06 # Transmission Control Register (R/W)
REG_TLR       = 0x07 # Trigger Level Register (R/W)
REG_TXLVL     = 0x08 # Transmit FIFO Level Register (R)
REG_RXLVL     = 0x09 # Receive FIFO Level Register (R)
REG_IODIR     = 0x0A # I/O Pin Direction Register (R/W)
REG_IOSTATE   = 0x0B # I/O Pin State Register (R)
REG_IOINTENA  = 0x0C # I/O Interrupt Enable Register (R/W)
REG_IOCONTROL = 0x0E # I/O Pin Control Register (R/W)
REG_EFCR      = 0x0F # Extra Features Register (R/W)

# Special Registers (Require LCR[7] = 1 and LCR != 0xBF)
REG_DLL       = 0x00 # Divisor Latch LSB Register (R/W)
REG_DLH       = 0x01 # Divisor Latch MSB Register (R/W)

# Enhanced Registers (Require LCR[7] = 1 and LCR = 0xBF)
REG_EFR       = 0x02 # Enhanced Feature Register (R/W)
REG_XON1      = 0x04 # XON1 Word Register (R/W)
REG_XON2      = 0x05 # XON2 Word Register (R/W)
REG_XOFF1     = 0x06 # XOFF1 Word Register (R/W)
REG_XOFF2     = 0x07 # XOFF2 Word Register (R/W)

DATABITS_5    = 0x05
DATABITS_6    = 0x06
DATABITS_7    = 0x07
DATABITS_8    = 0x08

STOPBITS_1    = 0x01
STOPBITS_2    = 0x02

PARITY_NONE   = 0x00
PARITY_ODD    = 0x01
PARITY_EVEN   = 0x02

# Define names for bitfields in IIR, LSR, and MSR registers
REG_IIR_BITS  = { 0: "Interrupt Status",         1: "Interrupt Priority Bit 0",
                  2: "Interrupt Priority Bit 1", 3: "Interrupt Priority Bit 2",
                  4: "Interrupt Priority Bit 3", 5: "Interrupt Priority Bit 4",
                  6: "FIFO Enable Bit 0",        7: "FIFO Enable Bit 1" }

REG_LSR_BITS  = { 0: "Data In Receiver", 1: "Overrun Error", 2: "Parity Error",      3: "Framing Error",
                  4: "Break Interrupt",  5: "THR Empty",     6: "THR and TSR Empty", 7: "FIFO Data Error" }

REG_MSR_BITS  = { 0: "Delta CTS", 1: "Delta DSR", 2: "Delta RI", 3: "Delta CD",
                  4: "CTS",       5: "DSR",       6: "RI",       7: "CD" }

class SC16IS750:
	def __init__(self, addr = 0x48, bus = 1, baudrate = 115200, freq = 1843200):
		self.bus = smbus.SMBus(bus)
		self.addr = addr
		self.baudrate = baudrate
		self.freq = freq
		self.delay = 0

	def print_register(self, reg, prefix):
		print("%s 0x%02X" % (prefix, self.byte_read(reg)))

	def print_registers(self):
		self.print_register(REG_RHR,       "0x00 REG_RHR:      ")
		self.print_register(REG_IER,       "0x01 REG_IER:      ")
		self.print_register(REG_IIR,       "0x02 REG_IIR:      ")
		self.print_register(REG_LCR,       "0x03 REG_LCR:      ")
		self.print_register(REG_MCR,       "0x04 REG_MCR:      ")
		self.print_register(REG_LSR,       "0x05 REG_LSR:      ")
		self.print_register(REG_MSR,       "0x06 REG_MSR:      ")
		self.print_register(REG_SPR,       "0x07 REG_SPR:      ")
		self.print_register(REG_TXLVL,     "0x08 REG_TXLVL:    ")
		self.print_register(REG_RXLVL,     "0x09 REG_RXLVL:    ")
		self.print_register(REG_IODIR,     "0x0A REG_IODIR:    ")
		self.print_register(REG_IOSTATE,   "0x0B REG_IOSTATE:  ")
		self.print_register(REG_IOINTENA,  "0x0C REG_IOINTENA: ")
		self.print_register(REG_IOCONTROL, "0x0E REG_IOCONTROL:")
		self.print_register(REG_EFCR,      "0x0F REG_EFCR:     ")

	def print_IIR(self):
		byte = self.byte_read(REG_IIR)
		sys.stdout.write("REG_IIR: 0x%02X" % byte)
		for i in reversed(range(8)):
			if byte & (0x01 << i): sys.stdout.write(", %s" % REG_IIR_BITS[i])
		print()

	def print_LSR(self):
		byte = self.byte_read(REG_LSR)
		sys.stdout.write("REG_LSR: 0x%02X" % byte)
		for i in reversed(range(8)):
			if byte & (0x01 << i): sys.stdout.write(", %s" % REG_LSR_BITS[i])
		print()

	def print_MSR(self):
		byte = self.byte_read(REG_MSR)
		sys.stdout.write("REG_MSR: 0x%02X" % byte)
		for i in reversed(range(8)):
			if byte & (0x01 << i): sys.stdout.write(", %s" % REG_MSR_BITS[i])
		print()

	def write_LCR(self, databits, stopbits, parity):
		lcr = 0x00

		# LCR[1:0]
		if   databits == DATABITS_5: lcr |= 0x00
		elif databits == DATABITS_6: lcr |= 0x01
		elif databits == DATABITS_7: lcr |= 0x02
		elif databits == DATABITS_8: lcr |= 0x03
		else: return False

		# LCR[2]
		if   stopbits == STOPBITS_1: lcr |= 0x00
		elif stopbits == STOPBITS_2: lcr |= 0x04
		else: return False

		# LCR[5:3]
		if   parity == PARITY_NONE: lcr |= 0x00
		elif parity == PARITY_ODD:  lcr |= 0x08
		elif parity == PARITY_EVEN: lcr |= 0x18
		else: return False

		success, value = self.byte_write_verify(REG_LCR, lcr)
		print("REG_LCR:       %s 0x%02X" % (success, value))
		return success

	# Compute required divider values for DLH and DLL registers
	# Return tuple indicating (boolean success, new values in registers)
	def set_divisor_latch(self, prescaler = 1):
		if prescaler not in [1, 4]: prescaler = 1
		div = round(self.freq/(prescaler*self.baudrate*16))
		dlh, dll = divmod(div, 0x100)
		dlhb, dlhv = self.byte_write_verify(REG_DLH, dlh)
		dllb, dllv = self.byte_write_verify(REG_DLL, dll)
		return (dlhb and dllb, (dlhv<<8)|dllv)

	# Write I2C byte to specified register and read it back
	# Return tuple indicating (boolean success, new value in register)
	def byte_write_verify(self, reg, byte):
		self.byte_write(reg, byte)
		value = self.byte_read(reg)
		return (value == byte, value)

	# Change single bit inside register
	def enable_register_bit(self, reg, bit, enable):
		if bit < 0 or bit > 7: return False
		if enable not in [True, False]: return False

		oldvalue = self.byte_read(reg)
		if enable: newvalue = oldvalue |  (0x01 << bit)
		else:      newvalue = oldvalue & ~(0x01 << bit)
		return self.byte_write_verify(REG_LCR, newvalue)

	# MCR[4]: True for local loopback enable, False for disable
	def enable_local_loopback(self, enable):
		return self.enable_register_bit(REG_MCR, 4, enable)

	# LCR[7]: True for special register set, False for general register set
	def define_register_set(self, special):
		return self.enable_register_bit(REG_LCR, 7, special)

	# Write I2C byte to specified register and wait for value to be written
	def byte_write(self, reg, byte):
		self.bus.write_byte_data(self.addr, self.reg_conv(reg), byte)
		time.sleep(self.delay)

	# Read I2C byte from specified register
	# Return byte received from SMBus
	def byte_read(self, reg):
		return self.bus.read_byte_data(self.addr, self.reg_conv(reg))

	# Convert register address given in datasheet to actual address on chip
	def reg_conv(self, reg):
		return reg << 3