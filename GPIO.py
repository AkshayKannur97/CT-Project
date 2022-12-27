"""****************************************************************************************
Author:         Akshay C P
Date:           01 Dec 2022
Description:    Proxy library of RPi.GPIO library for using in non-raspberry-pi devices
****************************************************************************************"""

import random


""" GPIO pin reference method """
BCM = 1
BOARD = 2

""" GPIO pin states """
LOW = 0
HIGH = 1

""" GPIO input/output mode """
IN = 0
OUT = 1


""" Sets pin reference method """
def setmode(*args):
    pass


""" Sets pin as input or output """
def setup(*args):
    pass


""" Returns current state of a particular pin """
def input(*args):
    return random.choice([LOW, HIGH])


""" Sets state of a particular pin """
def output(*args):
    pass


""" Release GPIO resources """
def cleanup():
    pass
