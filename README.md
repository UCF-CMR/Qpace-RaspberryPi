# Qpace-RaspberryPi
Repository for QPACE's RaspberryPi
## IMPORTANT
* The Pi (CCDR) uses the chip SC16IS740 to communicate with the WTC sub-system.  The chip converts I2C to UART (vise-versa).  The hardware for the chip is different for the Flight Model and the Developement Board.  The Flight Model uses a crystal frequency of 1843200 and the Development Board currently uses 11059200. Please revert the software define `XTAL_FREQ` back to Flight Model Configuration before launch! (_currently defined in qpaceMain.py_)

## System Logging / Debug Printing
While developing code for the Pi/CCDR sub-system please use the `sysargv` feature to display a variety of information about the system.
Do not use `startupQPACE.sh` anymore. Use `python3 qpaceMain.py *{}` from now on.
### User selected logging modes
* no arguments will print only sys messages
* v - verbose (prints everything)
* e - errors
* w - warnings
* i - info
* d - debug
* r - results
* s - successes
* f - failures
### Creating a Log
To produce a log message you must use the functions provided. Each `sysargv` or `logging mode` corresponds to a Logger function inside of the qpaceLogger.py file.
<br>
* **logSystem("Some String")** - Sys logs will always be printed! Should be used to print sys config / init loggings
* **logError("Some String")** - Critical Errors
* **logWarning("Some String")** - Warnings about system features or function uses
* **logInfo("Some String")** - Useful for mid-function data.
* **logDebug("Some String")** - Useful when developing a specific feature
* **logResults("Some String")** - Typically for byte arrays. **Use this for especially for COMMS data!**
<br> _if you wish to display bytearray data (example 128-byte packets) please use_ `''.join(map(chr, someByteArray))`
* **logSuccess("Some String")** - Useful to see if process executed correctly
* **logFailure("Some String")** - Useful to see if process didn't execute correctly

### Color Scheme

![I'm a relative reference to a repository file](/other/loggingColorScheme.png)
### Example(s) of Use

```
python3 qpaceMain.py e w d
#This will print errors, warnings, and debug messages (and of course sys logs)

logger.LogDebug("Hello")
logger.LogResults("Data")
-> Hello
```
```
python3 qpaceMain.py v
#This will print everything that enters the logging functions!
```
