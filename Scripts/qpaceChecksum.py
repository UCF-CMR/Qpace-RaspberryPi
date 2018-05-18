#! /usr/bin/env python
#qpaceChecksum.py by Minh Pham
#03-29-2018, Rev. 1.1
#Q-Pace project, Center for Microgravity Research
#University of Central Florida

import zlib
import os.path
import qpaceLogger

def compareChecksum(input1, input2):
    """
    This function checks if two inputs return the same checksum value.

    Parameters
    ----------
    String / File / Bytes - input1 - The first filepath, file, or checksum value.

    String / File / Bytes - input2 - The second filepath, file, or checksum value.

    Returns
    -------
    Boolean - True if the files are identical in content.

    Raises
    ------
    TypeError - Function handles invalid variable types.

    See Also
    --------
    Makes use of qpaceLogger.py to track errors.

    Revisions
    ---------
    Ver. 1.0 - 03-27-2018 Minh Pham (Initial Release)
    Ver. 1.1 - 03-29-2018 Minh Pham (Added TypeError handling)
    """

    try:
        # If not already a checksum, convert to one.
        if instanceof(input1, string) or instanceof(input1, file):
            input1 = checksum(turntofile(input1))

        # Once we reach here, input1 must be a bytes object.
        if not instanceof(input1, bytes):
            raise TypeError("Not string, file, or bytes.")

        # If not already a checksum, convert to one.
        if instanceof(input2, string) or instanceof(input2, file):
            input2 = checksum(turntofile(input2))

        # Similarly, input2 must be a btyes object here.
        if not instanceof(input2, bytes):
            raise TypeError("Not string, file, or bytes.")

        return (input1 == input2)

    except TypeError as e:
        qpaceLogger.logError("Variable was not of valid type.", e)
        qpaceLogger.logSystem([["Type error of variable occured."]])

def turntofile(input):
    """
    This function takes an input and converts it to a file object.

    We import os.path here to verify if a file with a given pathnames exists.

    Parameters
    ----------
    String / File - input - A filepath or a file.

    Returns
    -------
    File - A file that can be read to calculate a checksum.

    Raises
    ------
    IOError - Function handles file I/O errors.
    OSError - Functions handles invalid variable types.

    See Also
    --------
    Makes use of qpaceLogger.py to track errors.

    Revisions
    ---------
    Ver. 1.0 - 03-27-2018 Minh Pham (Initial Release)
    Ver. 1.1 - 03-29-2018 Minh Pham (Added IOError and TypeError handling)
    """

    try:
        # If we already have a file, we do not need to open it.
        if instanceof(input, file):
            return input

        # If we have a string, it must be a filepath. Otherwise, we have an error.
        if instanceof(input, string):
            if os.path.isfile(input):
                return input.open('rb')
            else:
                raise TypeError("Not valid filepath.")

    except IOError as e:
        qpaceLogger.logError("Could not open experiment file at " + str(input) + ".", e)
        qpaceLogger.logSystem([["File I/O error occured."]])

    except TypeError as e:
        qpaceLogger.logError("Variable was not of valid type", e)
        qpaceLogger.logSystem([["Type error of variable occured."]])


def checksum(filein):
    """
    This function takes a file and generates a checksum value.

    We import hashlib here in order to use the SHA256 hashing algorithm.

    Parameters
    ----------
    File - input - The file that will be read.

    Returns
    -------
    Bytes - The resulting hash value / digest of the algorithm.

    Raises
    ------
    OSError - Function handles when a file is does not have read permissions.

    See Also
    --------
    Makes use of qpaceLogger.py to track errors.

    Revisions
    ---------
    Ver. 1.0 - 03-27-2018 Minh Pham (Initial Release)
    Ver. 1.1 - 03-29-2018 Minh Pham (Added OSError handling)
    """

    try:
        if hasattr(filein, 'read'): #Check if it's a file in the first place
            filein = filein.read()

        # If filein is a string, we have to convert it to a byte string so that
        # we can give it to the hashing algorithm.
        if isinstance(filein, str):
            return str(zlib.crc32(filein.encode('utf-8')))

        # If filein is a byte string, we simply give it to the hashing algorithm.
        elif isinstance(filein, bytes):
            return str(zlib.crc32(filein))


    # In the event that the file does not have read permissions, raise an error.
    except OSError as e:
        qpaceLogger.logError("File does not have read permissions.", e)
        qpaceLogger.logSystem([["OS error occured."]])
