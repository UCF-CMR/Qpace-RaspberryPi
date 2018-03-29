import usb.core
import usb.util

# find our device
dev = usb.core.find()

# was it found?
if dev is None:
    raise ValueError('Device not found')