
#
# wycliffe -- Clean room implementation of Dante protocol
#
# Copyright (C) 2014 Jeff Sharkey, http://jsharkey.org/
# All Rights Reserved.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import random, collections, operator
import serial
import io


ser = serial.Serial('/dev/ttyUSB0')


ser.write("\r\n")
print ser.readline()

ser.write("InCtlA 1\r\n")
ser.flush()
print ser.readline()

ser.write("Preset 5\r\n")
ser.flush()
print ser.readline()


ser.close()


#sio = io.TextIOWrapper(io.BufferedRWPair(ser, ser))
#sio.write(unicode("InCtlA 1\n"))
#sio.flush()

#print sio.readline()


#ser.write("\n\n")
#ser.write("InCtlA 1\n")
#ser.flush()
#ser.write("Preset 2\n")
#ser.write("?\n")

#try:
#	while True:
#		print ser.readline()
#finally:

#ser.close()

